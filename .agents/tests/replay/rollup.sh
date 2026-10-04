#!/usr/bin/env sh
# rollup.sh: turn the graded runs into the table a maintainer reads.
#
# The unit of interest is a rate, not a pass. A scenario that holds five times
# out of five is a contract. One that holds twice out of five is the finding
# worth having, and a boolean suite would have filed it as a flake.

set -eu

REPLAY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESULTS=${1:-"$REPLAY_DIR/results"}

command -v python3 >/dev/null 2>&1 || {
  echo "FAIL: python3 is needed to read the graded runs" >&2
  exit 1
}

python3 - "$RESULTS" <<'PY'
import json, os, sys, collections

results = sys.argv[1]
if not os.path.isdir(results):
    print("No results directory yet at %s" % results)
    raise SystemExit(0)

runs = []
for name in sorted(os.listdir(results)):
    if not name.endswith(".json"):
        continue
    try:
        runs.append((name, json.load(open(os.path.join(results, name)))))
    except Exception:
        print("unreadable: %s" % name)

if not runs:
    print("No graded runs found in %s" % results)
    raise SystemExit(0)

broken = [(n, d["error"]) for n, d in runs if d.get("error")]
runs = [(n, d) for n, d in runs if not d.get("error")]

by_scenario = collections.defaultdict(list)
for name, data in runs:
    by_scenario[data.get("scenario")].append(data)

print()
print("=" * 74)
print("REPLAY ROLL-UP".center(74))
print("=" * 74)

held_rows = []
state_rows = []
pushback_rows = []
for scenario in sorted(k for k in by_scenario if k is not None):
    entries = by_scenario[scenario]
    total = len(entries)
    held = sum(1 for e in entries if e.get("held") is True)
    held_rows.append((scenario, held, total))

    with_state = [e for e in entries if e.get("state_held") is not None]
    if with_state:
        state_held = sum(1 for e in with_state if e.get("state_held") is True)
        state_rows.append((scenario, state_held, len(with_state)))

    # Withdrawing a notice under pressure no longer fails a run, so it is
    # counted here rather than folded into the rate. A kit that gives the right
    # warning and then talks itself out of it every time is still worth seeing.
    judged = [e for e in entries
              if ((e.get("pushback") or {}).get("verdict")) in ("held", "withdrew")]
    if judged:
        withdrew = sum(1 for e in judged
                       if e["pushback"]["verdict"] == "withdrew")
        pushback_rows.append((scenario, withdrew, len(judged)))

    fields = collections.OrderedDict()
    for entry in entries:
        for field, verdict in (entry.get("verdicts") or {}).items():
            fields.setdefault(field, []).append(verdict.get("verdict"))
        for field, verdict in (entry.get("state_verdicts") or {}).items():
            fields.setdefault("state:" + field, []).append(verdict.get("verdict"))

    print()
    print("Scenario %s   held %s/%s" % (scenario, held, total))
    print("-" * 74)
    print("  %-24s %5s %6s %6s %14s" % ("field", "hit", "drift", "miss", "unobservable"))
    for field, verdicts in fields.items():
        counts = collections.Counter(verdicts)
        print("  %-24s %5s %6s %6s %14s" % (
            field[:24],
            counts.get("hit", 0),
            counts.get("drift", 0),
            counts.get("miss", 0),
            counts.get("unobservable", 0),
        ))

print()
print("=" * 74)
print("HELD RATE: did the kit give the notice when due and record the acceptance before the work")
print("=" * 74)
for scenario, held, total in held_rows:
    bar = "#" * held + "." * (total - held)
    print("  scenario %-4s %s  %s/%s" % (scenario, bar, held, total))

if state_rows:
    print()
    print("=" * 74)
    print("STATE HELD: did the run leave the right result on disk")
    print("=" * 74)
    for scenario, held, total in state_rows:
        bar = "#" * held + "." * (total - held)
        print("  scenario %-4s %s  %s/%s" % (scenario, bar, held, total))

if pushback_rows:
    print()
    print("=" * 74)
    print("NOTICE UNDER PUSHBACK: reported, and not counted in the rate above")
    print("=" * 74)
    for scenario, withdrew, judged in pushback_rows:
        bar = "." * (judged - withdrew) + "!" * withdrew
        print("  scenario %-4s %s  withdrew in %s of %s" % (
            scenario, bar, withdrew, judged))

if broken:
    print()
    print("Runs not graded, not counted above:")
    for name, reason in broken:
        print("  %s: %s" % (name, reason))

print()
PY
