#!/usr/bin/env sh
# run-loop.sh: run ready pieces through the real run script, with the Claude stand-in.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with every guard the pre-run
# check wants, the GitHub stand-in and the stand-in App. Real ready and claim gates, a real
# attempt gate and a real judge (pytest) decide each piece. Only the builder's session is the
# stand-in, and it replays a script for each piece (FAKE_CLAUDE_DIR).
#
# Six pieces in the first run, before the App:
#   1 greet   passes first time                 (area menus)
#   2 menu    fails, then passes                (area menus: it waits for piece 1)
#   3 colour  says the bar is wrong             (back to shaping by move 6)
#   4 paint   needs the person                  (parked inside building)
#   5 net     is blocked by its environment     (back to ready by move 7)
#   6 sync    has an issue, and the App is off  (waits for the person, with a next: line)
#
# The script is killed while piece 5 is in flight, and started again with the same name. Pieces
# that were finished are not redone, and a second copy of a live run is refused by the lock.
# Then a stop signal, a per-piece spend cap and a per-run spend cap, each in its own run.
#
# No network, no GitHub account, no model. Without pytest it prints a visible "skipped" line
# and does not count a pass. Run it alone: tests/run-loop.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GATE="$ROOT/kit/scripts/gate.py"
CHECK="$ROOT/kit/scripts/pre-run-check.py"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SIMPLE ANTHROPIC_API_KEY \
  FAKE_CLAUDE_SCRIPT 2>/dev/null || true

if ! python3 -m pytest --version >/dev/null 2>&1; then
  echo "skipped: pytest is not installed, so the run-loop check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Run loop checks:"
tp_new run-demo
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
mkdir -p "$TP_BASE/tmp"
TMPDIR="$TP_BASE/tmp"
PATH="$TP_BIN:$FAKE_COMPUTER:$PATH"
export PATH TMPDIR
unset FAKE_COMPUTER_POWER FAKE_COMPUTER_SLEEP FAKE_COMPUTER_FREE_MB FAKE_COMPUTER_DISK_GB \
  FAKE_CLAUDE_VERSION

# --- the kit, as installed, and every guard the pre-run check wants -------------------------
KIT="$TP_BASE/plugin"
cp -R "$ROOT/kit" "$KIT"
CLAUDE_PLUGIN_ROOT="$KIT"
PYTHONPATH="$KIT/scripts"
export CLAUDE_PLUGIN_ROOT PYTHONPATH
GATE="$KIT/scripts/gate.py"
RUN="$KIT/scripts/run.py"
python3 - "$ROOT/kit/scripts/pre-run-check.py" "$KIT" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("pre_run_check", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["pre_run_check"] = module
spec.loader.exec_module(module)
module.write_record(Path(sys.argv[2]))
PY
python3 "$KIT/scripts/merge-settings.py" "$KIT/templates/claude-settings.json" \
  "$TP_ROOT/.claude/settings.json" --set "KIT_DIR=$KIT" >/dev/null 2>&1 \
  || fail "the settings could not be merged"
mkdir -p "$TP_ROOT/.githooks" "$TP_ROOT/.agents/loop"
sed "s#{{KIT_DIR}}#$KIT#g" "$KIT/templates/githooks/pre-push" > "$TP_ROOT/.githooks/pre-push"
chmod +x "$TP_ROOT/.githooks/pre-push"
git -C "$TP_ROOT" config core.hooksPath .githooks
cp "$KIT/templates/policy.json" "$TP_ROOT/.agents/loop/policy.json"
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["test_command"] = "python3 -m pytest tests/test_old.py -q"
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
printf '{"language": "python", "allowedDomains": ["pypi.org", "files.pythonhosted.org", "registry.allowlist-probe.test"]}\n' \
  > "$TP_ROOT/.agents/loop/network-allowlist.json"

# --- the project: a stub and an acceptance test for each piece ------------------------------
cd "$TP_ROOT"
mkdir -p tests/acceptance docs
cat > tests/test_old.py <<'PY'
def test_old_behaviour_holds():
    assert 1 + 1 == 2
PY
: > "$TP_BASE/area-map"
echo "tests/test_old.py records" >> "$TP_BASE/area-map"
echo "docs/ records" >> "$TP_BASE/area-map"
# name file area: the pieces of the runs.
PIECES="greet:greet.py:menus menu:menu.py:menus colour:colour.py:colours paint:paint.py:paints \
net:net.py:nets sync:sync_it.py:syncs hold:hold.py:holds cap1:cap1.py:capa cap2:cap2.py:capb"
for item in $PIECES; do
  name=${item%%:*}; rest=${item#*:}; file=${rest%%:*}; area=${rest#*:}
  printf 'def %s():\n    return None\n' "$name" > "$file"
  echo "/$file $area" >> "$TP_BASE/area-map"
  echo "tests/acceptance/test_$name.py $area" >> "$TP_BASE/area-map"
done
cp "$TP_BASE/area-map" docs/area-map
# The records the integration loop's docs commit keeps right (the run joins what it builds).
mkdir -p .agents/guard .github/workflows
cp "$KIT/templates/blocked-commands.md" .agents/guard/blocked-commands.md
cp "$KIT/templates/AGENTS.md" AGENTS.md
cp "$KIT/templates/CLAUDE.md" CLAUDE.md
cp "$KIT/templates/CHANGELOG.md" CHANGELOG.md
cp "$KIT/templates/docs-README.md" docs/README.md
sed 's/{{KIT_REF}}/main/' "$KIT/templates/checks.yml" > .github/workflows/checks.yml
python3 - "$KIT/templates/overview.md" docs/area-map <<'PY'
import sys

text = open(sys.argv[1]).read().split("| project-records")[0].rstrip("\n")
names = []
for line in open(sys.argv[2]):
    parts = line.split()
    if len(parts) == 2 and not line.startswith("#") and parts[1] not in names:
        names.append(parts[1])
for area in names:
    doc = "docs/README.md" if area == "records" else f"docs/{area}.md"
    text += f"\n| {area} | The {area} area | no | | `{doc}` |"
    if area != "records":
        open(doc, "w").write(f"# {area}\n\n")
open("docs/overview.md", "w").write(text + "\n")
PY
git add -A
git commit -q -m "Add the stubs, an old test and the area map"
git push -q origin main

cat > "$TP_BASE/make-spec.py" <<'PY'
import sys

title, area, source = sys.argv[1:4]
print(title + ".\n")
print("<!-- spec:start version=1 -->")
print("Path: quick\n")
print("## Goal\nThe " + title.lower() + " works, and the edge case is handled.\n")
print("## Expected flow\nFL-1 The user uses the " + title.lower() + " and sees it work.\n")
print("## Edge cases\nEC-1 When the input is empty, then the " + title.lower() + " says so.\n")
print("## Must stay the same\nThe old behaviour still holds.\n"
      "Check: python3 -m pytest tests/test_old.py\n")
held = sys.argv[5] if len(sys.argv) > 5 else ""
line = "Held-out cases: fingerprint " + held + "\n" if held else ""
print("## Judge\nKind: acceptance tests, a single test\n"
      "Command: python3 -m pytest tests/acceptance/test_" + sys.argv[4] + ".py\n"
      "Proves: FL-1, EC-1\n" + line)
print("## Links\nRelies on: " + source + "\nTouches: " + area + "\n")
print("## Decisions\n- must-look: the person wants to read this piece.")
print("<!-- spec:end -->")
PY

# make_piece <name> <file> <area> [issue]: capture, branch, commit the judge, and make it ready.
make_piece() {
  name=$1 file=$2 area=$3
  python3 "$TP_BASE/make-spec.py" "Run $name" "$area" "$file" "$name" > "$TP_BASE/spec-$name.md"
  if [ "${4:-}" = issue ]; then
    url=$(gh issue create --title "Run $name" --body "$(cat "$TP_BASE/spec-$name.md")")
    n=${url##*/}
    python3 "$GATE" capture "$n" --json > "$TP_BASE/capture-$name.json" \
      || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  else
    python3 "$GATE" capture --title "Run $name" --body-file "$TP_BASE/spec-$name.md" \
      --type feature --json > "$TP_BASE/capture-$name.json" \
      || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  fi
  number=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["piece"])' \
    "$TP_BASE/capture-$name.json")
  python3 "$GATE" branch "$number" --json >/dev/null || fail "gate.py branch $number failed"
  git checkout -q "piece-$number"
  mkdir -p tests/acceptance
  cat > "tests/acceptance/test_$name.py" <<PY
from $(printf '%s' "${file%.py}") import $name


def test_${name}_works_and_handles_the_edge():
    assert $name() == "$name ok", "FL-1 the $name works; EC-1 the empty input is handled"
PY
  git add "tests/acceptance/test_$name.py"
  git commit -q -m "Add the acceptance test of $name"
  git checkout -q main
  # The hidden cases, outside git, and the fingerprint the spec then names.
  for id in FL-1 EC-1; do
    cat > "$TP_BASE/case-$name-$id.txt" <<PY
# held-out-path: tests/held_out/test_hidden_${name}_$(printf '%s' "$id" | tr -d '-').py
from $(printf '%s' "${file%.py}") import $name


def test_hidden_${name}_$(printf '%s' "$id" | tr -d '-')():
    assert $name() == "$name ok"
PY
  done
  python3 -m loop.heldout store --piece "$number" --case "FL-1=$TP_BASE/case-$name-FL-1.txt" \
    --case "EC-1=$TP_BASE/case-$name-EC-1.txt" --json > "$TP_BASE/held-$name.json" \
    || fail "the held-out store refused the cases of $name: $(cat "$TP_BASE/held-$name.json")"
  print_=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' \
    "$TP_BASE/held-$name.json")
  python3 "$TP_BASE/make-spec.py" "Run $name" "$area" "$file" "$name" "$print_" \
    > "$TP_BASE/spec2-$name.md"
  python3 "$GATE" spec "$number" --body-file "$TP_BASE/spec2-$name.md" --json >/dev/null \
    || fail "gate.py spec failed for $name"
  tp_claude_script "$(python3 - "$KIT" <<'PY'
import json, sys
summary = "FL-1: test_works\nEC-1: test_edge"
print(json.dumps({"runs": [["python3", sys.argv[1] + "/scripts/handoff.py", "done",
                            "--summary", summary]]}))
PY
)"
  python3 "$GATE" move "$number" ready --json > "$TP_BASE/ready-$name.json" \
    2> "$TP_BASE/ready-$name.err" \
    || fail "move 2 was refused for $name: $(cat "$TP_BASE/ready-$name.err")"
  echo "$number"
}

# The five pieces before the App exists, so they have no issue. Their moves queue GitHub steps.
N1=$(make_piece greet greet.py menus)
N2=$(make_piece menu menu.py menus)
N3=$(make_piece colour colour.py colours)
N4=$(make_piece paint paint.py paints)
N5=$(make_piece net net.py nets)
# The piece with an issue is made with the App, and then the App is switched off.
tp_app
python3 "$GATE" labels --create --json >/dev/null || fail "gate.py labels failed"
# A piece captured from an issue takes the issue's number. Five other issues come first, so
# that this piece is number 6 and no number is both a piece and an issue.
for _ in 1 2 3 4 5; do
  gh issue create --title "Something else" --body "Not a piece." >/dev/null
done
N6=$(make_piece sync sync_it.py syncs issue)
mv "$TP_ROOT/.agents/loop/local.json" "$TP_BASE/local.json.off"
N7=$(make_piece hold hold.py holds)
N8=$(make_piece cap1 cap1.py capa)
N9=$(make_piece cap2 cap2.py capb)
[ "$N1,$N2,$N3,$N4,$N5,$N6,$N7,$N8,$N9" = "1,2,3,4,5,6,7,8,9" ] \
  || fail "the pieces are not numbered 1 to 9: $N1 $N2 $N3 $N4 $N5 $N6 $N7 $N8 $N9"
ok "nine pieces are ready: five with no issue, one with an issue, and three for the later runs"

state_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
for n in 1 2 3 4 5 6 7 8 9; do
  [ "$(state_of $n)" = ready ] || fail "piece $n is not ready"
done

# --- the stand-in builder: one script for each piece ---------------------------------------
FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
python3 - "$FAKE" "$KIT" <<'PY'
import json, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
hand = kit + "/scripts/handoff.py"


def done(name, file, good=True, **more):
    body = f'def {name}():\n    return "{name} ok"\n' if good else \
        f'def {name}():\n    return "wrong"\n'
    script = {"files": {file: body}, "commits": [{"message": f"Build {name}", "paths": [file]}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}.",
                        "--decision", f"Made {name} return a plain string."]]}
    script.update(more)
    return script


def only(*words, **more):
    return {"runs": [["python3", hand, *words]], **more}


scripts = {
    "1": done("greet", "greet.py", sleep=0.3),
    # Fails the judge first, then passes: the sequence is read for each session.
    "2": {"sequence": [done("menu", "menu.py", good=False, sleep=0.3),
                       done("menu", "menu.py", sleep=0.3)]},
    "3": only("bar-is-wrong", "--evidence", "FL-1 and EC-1 cannot both hold", sleep=0.3),
    "4": only("needs-the-person", "--question", "Which colour should it be?", sleep=0.3),
    # The first session is slow, so the test can end the run script while it is in flight. The
    # second copy of the run starts after the pre-run check, which can take many seconds on a busy
    # computer, so the sleep must outlast it. The test ends the run script anyway.
    "5": {"sequence": [only("blocked-by-environment", "--reason", "npm is refused", sleep=30),
                       only("blocked-by-environment", "--reason", "npm is refused")]},
    "6": done("sync", "sync_it.py"),
    "7": only("done", "--summary", "never reached", sleep=60),
    # A session that costs money, and fails the judge: the first session of a spend test.
    "8": {"sequence": [done("cap1", "cap1.py", good=False, cost_usd=0.6),
                       done("cap1", "cap1.py", cost_usd=0.1)]},
    "9": {"sequence": [done("cap2", "cap2.py", good=False, cost_usd=1.2),
                       done("cap2", "cap2.py", cost_usd=0.1)]},
    "trim": only("done", "--summary", "Nothing to trim."),
}
for name, script in scripts.items():
    (fake / f"{name}.json").write_text(json.dumps(script))
PY

# --- the plan: dependencies, chains, areas, slots ---------------------------------------------
python3 "$RUN" --plan --pieces 1,2,3,4,5,6 --json > "$TP_BASE/plan.json" 2> "$TP_BASE/plan.err" \
  || fail "run.py --plan failed: $(cat "$TP_BASE/plan.err")"
python3 - "$TP_BASE/plan.json" <<'PY' || fail "the plan is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["pieces"] == [1, 2, 3, 4, 5, 6], d
assert d["plan"]["slots"] == 3, d["plan"]
assert d["plan"]["chains"] == [] and d["plan"]["order"] == [1, 2, 3, 4, 5, 6], d["plan"]
for wave in d["plan"]["waves"]:
    assert not ({1, 2} <= set(wave)), "two pieces in the area menus share a wave: %s" % wave
assert d["plan"]["waves"][0] == [1, 3, 4], d["plan"]
assert d["dry_run"] is True and "pre_run_check" in d, d
PY
! ls "$TP_ROOT/.agents/runs" 2>/dev/null | grep -q "^run-" || fail "a plan wrote a run folder"
ok "--plan shows the order and the waves, and changes nothing"

# --- the pre-run check holds: no App for an unattended run, and no --bare ----------------------
mv "$TP_APP_KEY" "$TP_BASE/app-key.pem.off"
set +e
python3 "$RUN" --pieces 1 --unattended --json > "$TP_BASE/un.json" 2> "$TP_BASE/un.err"
code=$?
python3 "$RUN" --pieces 1 --merge-pre-approved --json > "$TP_BASE/pre.json" 2> "$TP_BASE/pre.err"
code_pre=$?
set -e
mv "$TP_BASE/app-key.pem.off" "$TP_APP_KEY"
[ "$code_pre" -eq 3 ] || fail "--merge-pre-approved with no App exited $code_pre, not 3"
grep -qF '"guard": "app-key"' "$TP_BASE/pre.json" || fail "the pre-approval refusal does not name the App key"
[ "$code" -eq 3 ] || fail "--unattended with no App exited $code, not 3: $(cat "$TP_BASE/un.err")"
grep -qF '"guard": "app-key"' "$TP_BASE/un.json" || fail "the refusal does not name the App key"
grep -qF "second half" "$TP_BASE/un.json" || fail "the refusal does not name the second half of /setup"
grep -q "^next:" "$TP_BASE/un.err" || fail "the refusal has no next: line"
! ls "$TP_ROOT/.agents/runs" 2>/dev/null | grep -q "^run-" || fail "a refused run left a run folder"
ok "--unattended with no App is refused by the pre-run check, naming the second half of /setup"

set +e
CLAUDE_CODE_SIMPLE=1 python3 "$RUN" --pieces 1 --json > "$TP_BASE/bare.json" 2> "$TP_BASE/bare.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "a bare environment exited $code, not 3"
grep -qF '"guard": "bare"' "$TP_BASE/bare.json" || fail "the refusal does not name the bare guard"
ok "a run whose sessions would skip the hooks (--bare) is refused"

# --- run 1: five outcomes and a waiting piece, killed in the middle, started again ------------
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 1,2,3,4,5,6 --run night-1 --json \
  > "$TP_BASE/run1.json" 2> "$TP_BASE/run1.err" &
RUN_PID=$!

# poll <seconds> <python expression over d, the run record>: wait until it holds.
poll() {
  limit=$1 expr=$2 file=$3
  i=0
  while [ "$i" -lt $((limit * 2)) ]; do
    if [ -f "$file" ] && python3 - "$file" "$expr" <<'PY' 2>/dev/null
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)
PY
    then
      return 0
    fi
    i=$((i + 1))
    sleep 0.5
  done
  return 1
}
RECORD="$TP_ROOT/.agents/runs/night-1/run.json"
poll 90 'all(d["pieces"][n]["status"] in ("built","sent-back","parked-needs-person","waiting-for-person","returned-ready") for n in ("1","2","3","4","6"))' "$RECORD" \
  || { cat "$TP_BASE/run1.err" >&2; fail "pieces 1, 2, 3, 4 and 6 did not settle in time"; }
poll 20 'True' "$RECORD" || fail "no run record"
grep -q "/5-run-net" "$FAKE_CLAUDE_LOG" || fail "piece 5 has no session in flight"

# A second copy of the same live run is refused by the lock. The first run must hold the lock for
# the whole step: its process is alive before and after, or the step proves nothing.
kill -0 "$RUN_PID" 2>/dev/null || fail "the first run ended before the second copy started"
[ -f "$TP_ROOT/.agents/runs/night-1/lock" ] || fail "the first run holds no lock file"
set +e
python3 "$RUN" --run night-1 --json > "$TP_BASE/second.json" 2> "$TP_BASE/second.err"
code=$?
set -e
kill -0 "$RUN_PID" 2>/dev/null \
  || fail "the first run ended while the second copy was checking, so the lock step proves nothing"
[ "$code" -eq 3 ] || fail "a second copy of a live run exited $code, not 3: $(cat "$TP_BASE/second.err")"
grep -qF '"lock": true' "$TP_BASE/second.json" || fail "the refusal does not name the lock: $(cat "$TP_BASE/second.json")"
ok "a second copy of a live run is refused by the lock file"

count_calls() {
  python3 - "$FAKE_CLAUDE_LOG" <<'PY'
import json, os, sys
counts = {}
for line in open(sys.argv[1]):
    if line.strip():
        name = os.path.basename(json.loads(line)["cwd"])
        counts[name] = counts.get(name, 0) + 1
print(json.dumps(counts, sort_keys=True))
PY
}
BEFORE=$(count_calls)
moves_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["moves"])'
}
MOVES1_BEFORE=$(moves_of 1)
MOVES2_BEFORE=$(moves_of 2)

# The kill: the run script only, by its own process number.
kill -9 "$RUN_PID"
wait "$RUN_PID" 2>/dev/null || true
[ -f "$TP_ROOT/.agents/runs/night-1/lock" ] || fail "a killed run took its lock with it, which only a clean exit does"
# The stand-in session that was in flight finishes by itself. Wait for its hand-off.
i=0
while [ ! -f "$TP_ROOT/.agents/runs/night-1/handoff-p5-a1.json" ] && [ "$i" -lt 160 ]; do
  i=$((i + 1))
  sleep 0.5
done
[ -f "$TP_ROOT/.agents/runs/night-1/handoff-p5-a1.json" ] || fail "the session in flight never finished"
ok "the run script was killed while piece 5 was in flight"

python3 "$RUN" --pieces 1,2,3,4,5,6 --run night-1 --json \
  > "$TP_BASE/run1b.json" 2> "$TP_BASE/run1b.err" \
  || { cat "$TP_BASE/run1b.err" >&2; cat "$TP_BASE/run1b.json" >&2; fail "the run started again failed"; }
[ ! -f "$TP_ROOT/.agents/runs/night-1/lock" ] || fail "the lock file is still there after a clean end"
AFTER=$(count_calls)

python3 - "$RECORD" <<'PY' || fail "the run record is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
status = {n: p["status"] for n, p in d["pieces"].items()}
assert status == {"1": "built", "2": "built", "3": "sent-back", "4": "parked-needs-person",
                  "5": "returned-ready", "6": "waiting-for-person"}, status
assert d["status"] == "finished" and d["starts"] == 2, (d["status"], d["starts"])
assert d["pieces"]["2"]["attempts"] == 2, d["pieces"]["2"]
assert "Which colour" in d["pieces"]["4"]["question"], d["pieces"]["4"]
six = d["pieces"]["6"]
assert "gate.py" in six["next"] and "sync" in six["next"], six
assert "App" in six["reason"], six
texts = [x["text"] for x in d["decisions"]]
assert any("greet return a plain string" in t for t in texts), texts
assert any("Made menu return a plain string" in t for t in texts), texts
assert any(x["by"] == "run" for x in d["decisions"]), d["decisions"]
# Pieces 1 and 2 share the area menus, so their sessions never overlap.
w1, w2 = d["pieces"]["1"]["windows"], d["pieces"]["2"]["windows"]
for a in w1:
    for b in w2:
        assert a[1] <= b[0] or b[1] <= a[0], (w1, w2)
PY
ok "five outcomes and a waiting piece: built, built after a failed attempt, sent back, parked, returned, waiting with a next: line"

# The gate holds each state, and the run never wrote one.
[ "$(state_of 1)" = review ] || fail "piece 1 is not in review"
[ "$(state_of 2)" = review ] || fail "piece 2 is not in review"
[ "$(state_of 3)" = shaping ] || fail "piece 3 (the bar is wrong) is not back in shaping"
[ "$(state_of 4)" = building ] || fail "piece 4 (needs the person) is not parked inside building"
[ "$(state_of 5)" = ready ] || fail "piece 5 (blocked by its environment) is not back in ready"
[ "$(state_of 6)" = ready ] || fail "piece 6 (no App) is not still ready"
ok "the gate holds each piece where its outcome sends it: review, review, shaping, building, ready, ready"

python3 - "$BEFORE" "$AFTER" <<'PY' || fail "finished work was redone after the restart"
import json, sys
before, after = json.loads(sys.argv[1]), json.loads(sys.argv[2])
for name in ("1-run-greet", "2-run-menu", "3-run-colour", "4-run-paint", "1-trim", "2-trim"):
    if name in before:
        assert after.get(name) == before[name], (name, before.get(name), after.get(name))
assert before.get("1-run-greet") == 1, before
assert after.get("5-run-net", 0) == before.get("5-run-net", 0) + 1, (before, after)
PY
[ "$(moves_of 1)" = "$MOVES1_BEFORE" ] || fail "the gate's record of piece 1 changed after the restart"
[ "$(moves_of 2)" = "$MOVES2_BEFORE" ] || fail "the gate's record of piece 2 changed after the restart"
ok "a killed run started again redid no finished piece: the sessions and the gate's records are as they were"

# Every session: the exact short command line, no --bare, no --resume, the guard settings.
python3 - "$FAKE_CLAUDE_LOG" "$TP_BASE/gh.log" <<'PY' || fail "a session command line is wrong"
import json, sys
calls = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
builders = [c for c in calls if c["argv"] and c["argv"][0] == "-p"]
assert len(builders) >= 6, len(builders)
for c in builders:
    argv = c["argv"]
    assert "--bare" not in argv and "--resume" not in argv and "--continue" not in argv, argv
    assert "--settings" in argv and "--permission-mode" in argv, argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk", argv
    assert not any(k.startswith(("GH_", "GITHUB_")) for k in c["env_keys"]), c["env_keys"]
PY
ok "every session command line has --settings, dontAsk, no --bare and no GitHub credential"

# The settings file a session really read holds the /setup network allowlist and a deny rule for
# a bar file of its piece. The command line only names the file, so the file is read here.
python3 - "$TP_ROOT/.agents/runs/night-1" "$TP_ROOT/.agents/loop/network-allowlist.json" <<'PY' \
  || fail "a session settings file lacks the network allowlist or the bar deny rule"
import json, sys
run, allow = sys.argv[1], sys.argv[2]
wanted = json.load(open(allow))["allowedDomains"]
# One host that the kit template does not hold, so only the /setup file can put it there.
assert "registry.allowlist-probe.test" in wanted, wanted
settings = json.load(open(run + "/settings-p1-a1.json"))
hosts = settings["sandbox"]["network"]["allowedDomains"]
assert all(h in hosts for h in wanted), (wanted, hosts)
deny = settings["permissions"]["deny"]
assert any(r.startswith("Edit(") and r.endswith("tests/acceptance/test_greet.py)") for r in deny), deny
blocks = settings["sandbox"]["filesystem"]["denyWrite"]
assert any(b.endswith("tests/acceptance/test_greet.py") for b in blocks), blocks
PY
ok "a session settings file holds the network allowlist and a deny rule for a bar file of its piece"

# The summary lists the decisions made alone, the builders' included.
SUMMARY="$TP_ROOT/.agents/runs/night-1/summary.md"
[ -f "$SUMMARY" ] || fail "no morning summary"
grep -qF "Made greet return a plain string." "$SUMMARY" || fail "the summary lacks a builder's decision"
grep -qF "Which colour should it be?" "$SUMMARY" || fail "the summary lacks the parked question"
grep -q "next:" "$SUMMARY" || fail "the summary lacks the next: line of the waiting piece"
ok "the morning summary names the decisions made alone, the question and the next: line"

# The heartbeat file was written.
[ -f "$TP_ROOT/.agents/runs/night-1/heartbeat" ] || fail "no heartbeat"
ok "the heartbeat was written"

# --- a stop signal: the building piece goes back to ready, with its branch kept ----------------
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 7 --run night-2 --json > "$TP_BASE/run2.json" 2> "$TP_BASE/run2.err" &
RUN2_PID=$!
i=0
while ! grep -q "/7-run-hold" "$FAKE_CLAUDE_LOG" 2>/dev/null && [ "$i" -lt 180 ]; do
  i=$((i + 1))
  sleep 0.5
done
grep -q "/7-run-hold" "$FAKE_CLAUDE_LOG" || { cat "$TP_BASE/run2.err" >&2; fail "piece 7 never started"; }
kill -TERM "$RUN2_PID"
set +e
wait "$RUN2_PID"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the stopped run exited $code, not 3: $(cat "$TP_BASE/run2.err")"
grep -q "^next:" "$TP_BASE/run2.err" || fail "the stopped run printed no next: line"
[ "$(state_of 7)" = ready ] || fail "the stopped piece is not back in ready"
git rev-parse --verify -q refs/heads/piece-7 >/dev/null || fail "the stop lost the branch of piece 7"
[ -d "$TP_ROOT/.agents/worktrees/7-run-hold" ] || fail "the stop lost the worktree of piece 7"
python3 - "$TP_ROOT/.agents/runs/night-2/run.json" <<'PY' || fail "the stopped run record is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "stopped" and d["pieces"]["7"]["status"] == "stopped", d
assert d["pieces"]["7"]["attempts"] == 0, d["pieces"]["7"]
PY
python3 "$GATE" report 7 --json | python3 -c '
import json, sys
d = json.load(sys.stdin)["pieces"][0]
assert d["moves"][-1] == 7, d["moves"]
' || fail "the stop was not move 7"
ok "a stop signal sent the building piece back to ready by move 7, with its branch and worktree kept"

# --- a spend cap per piece parks the run until the person answers ------------------------------
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["billing"] = {"mode": "api_key", "spend_cap_per_piece_usd": 0.5, "spend_cap_per_run_usd": 50}
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
: > "$FAKE_CLAUDE_LOG"
set +e
python3 "$RUN" --pieces 8 --run night-3 --json > "$TP_BASE/run3.json" 2> "$TP_BASE/run3.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the run at a piece cap exited $code, not 3: $(cat "$TP_BASE/run3.err")"
python3 - "$TP_ROOT/.agents/runs/night-3/run.json" "$FAKE_CLAUDE_LOG" <<'PY' || fail "the piece cap run is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "parked", d["status"]
piece = d["pieces"]["8"]
assert piece["status"] == "parked-spend" and abs(piece["spend_usd"] - 0.6) < 1e-6, piece
assert "policy.json" in piece["next"], piece
calls = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
first = calls[0]["argv"]
assert first[first.index("--max-budget-usd") + 1] == "0.5", first
assert len([c for c in calls if "8-run-cap1" in c["cwd"]]) == 1, calls
PY
grep -q "^next:" "$TP_BASE/run3.err" || fail "the parked run printed no next: line"
[ "$(state_of 8)" = building ] || fail "the parked piece left building"
ok "a per-piece spend cap parks the run; --max-budget-usd was on the session; the next: line names the policy"

# The person raises the cap, and the run goes on from the record.
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["billing"]["spend_cap_per_piece_usd"] = 5
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
python3 "$RUN" --pieces 8 --run night-3 --json > "$TP_BASE/run3b.json" 2> "$TP_BASE/run3b.err" \
  || { cat "$TP_BASE/run3b.err" >&2; fail "the run did not go on after the cap was raised"; }
[ "$(state_of 8)" = review ] || fail "the piece did not finish after the cap was raised"
ok "after the person raised the cap the run went on and built the piece"

# --- a spend cap per run -------------------------------------------------------------------------
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["billing"] = {"mode": "api_key", "spend_cap_per_piece_usd": 50, "spend_cap_per_run_usd": 1.0}
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
set +e
python3 "$RUN" --pieces 9 --run night-4 --json > "$TP_BASE/run4.json" 2> "$TP_BASE/run4.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the run at a run cap exited $code, not 3: $(cat "$TP_BASE/run4.err")"
python3 - "$TP_ROOT/.agents/runs/night-4/run.json" <<'PY' || fail "the run cap record is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "parked" and d["pieces"]["9"]["status"] == "parked-spend", d
assert abs(d["spend_usd"] - 1.2) < 1e-6, d["spend_usd"]
assert any("cap for the run" in n["text"] for n in d["notes"]), d["notes"]
PY
ok "a per-run spend cap parks the run, with the total in the run record"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the run changed the project folder"
ok "the run left the project folder as it was"

echo "Run loop checks passed."
