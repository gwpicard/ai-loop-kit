#!/usr/bin/env sh
# watch-and-mailbox.sh: the watch and the mailbox of a run, through the real run script.
#
# The project is a throwaway one (tests/lib/run-project.sh) with the GitHub stand-in and the
# Claude stand-in. Real gates and a real judge (pytest) decide each piece. Only the builder's
# session is the stand-in, and it prints what a builder prints.
#
# What it shows:
#   - run.py starts caffeinate before the pre-run check, so a bare run on a Mac passes the check
#     that refuses a computer nothing holds awake (a stateful pmset stand-in reports sleep held
#     only while the caffeinate stand-in lives);
#   - a builder that repeats one error is ended at once, and the gate counts the attempt;
#   - a usage limit waits for the reset, counts nothing, and the tokens are recorded per piece;
#   - pause holds new pieces back (the run stays alive), continue lets them go, a stop line left
#     by an earlier run is not obeyed, and stop sends the building piece back to ready by move 7;
#   - the run-level real stops notify once and the run carries on with independent work: two
#     environment failures in a row, the same refused command in two pieces, the same failure in
#     three pieces.
#
# No network, no GitHub account, no model. Without pytest it prints a visible "skipped" line.
# Run it alone: tests/watch-and-mailbox.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
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
  echo "skipped: pytest is not installed, so the watch and mailbox check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Watch and mailbox checks:"
RP_NAME=watch-demo
PIECES="awake:awake.py:aw stuck:stuck.py:st limit:limit.py:li slow:slow.py:mb after1:after1.py:mb \
after2:after2.py:mb hold1:hold1.py:mh hold2:hold2.py:mh env1:env1.py:e1 env2:env2.py:e2 \
indep:indep.py:e3 ref1:ref1.py:r1 ref2:ref2.py:r2 same1:same1.py:f1 same2:same2.py:f2 \
same3:same3.py:f3"
. "$ROOT/tests/lib/run-project.sh" 2>"$TP_BASE/setup.err" >"$TP_BASE/setup.out" \
  || { cat "$TP_BASE/setup.err" >&2; fail "the project could not be made"; }

FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
AWAKE="$TP_BASE/awake-bin"
mkdir -p "$TP_BASE/tmp" "$AWAKE"
TMPDIR="$TP_BASE/tmp"
AWAKE_MARKER="$TP_BASE/caffeinate.live"
export TMPDIR AWAKE_MARKER
unset FAKE_COMPUTER_POWER FAKE_COMPUTER_SLEEP FAKE_COMPUTER_FREE_MB FAKE_COMPUTER_DISK_GB \
  FAKE_CLAUDE_VERSION

# A caffeinate stand-in that lives while the process it was told to watch (-w) lives, and a
# pmset stand-in that says sleep is held only while that stand-in lives. So the pre-run check
# passes only when caffeinate was started before it.
cat > "$AWAKE/caffeinate" <<'SH'
#!/usr/bin/env sh
pid=""
while [ $# -gt 0 ]; do
  [ "$1" = "-w" ] && pid=$2
  shift
done
echo "$$" > "$AWAKE_MARKER"
while [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; do
  sleep 0.2
done
rm -f "$AWAKE_MARKER"
SH
cat > "$AWAKE/pmset" <<'SH'
#!/usr/bin/env sh
case "$*" in
  "-g batt")
    echo "Now drawing from 'AC Power'"
    printf ' -InternalBattery-0 (id=1)\t100%%; charged; 0:00 remaining present: true\n'
    ;;
  "-g assertions")
    held=0
    if [ -f "$AWAKE_MARKER" ] && kill -0 "$(cat "$AWAKE_MARKER")" 2>/dev/null; then held=1; fi
    echo "Assertion status system-wide:"
    echo "   PreventUserIdleSystemSleep     $held"
    ;;
  *) exit 64 ;;
esac
SH
chmod +x "$AWAKE/caffeinate" "$AWAKE/pmset"
PATH="$TP_BIN:$AWAKE:$FAKE_COMPUTER:$PATH"
export PATH

# --- the pieces ----------------------------------------------------------------------------
N=0
for item in $PIECES; do
  name=${item%%:*}; rest=${item#*:}; file=${rest%%:*}; area=${rest#*:}
  num=$(make_piece "$name" "$file" "$area") || fail "the piece $name could not be made"
  N=$((N + 1))
  [ "$num" = "$N" ] || fail "piece $name is number $num, not $N"
  eval "P_$name=$num"
done
unset FAKE_CLAUDE_SCRIPT
ok "$N pieces are ready"

FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
# script <number> <json>: the stand-in's script for one piece.
script() {
  printf '%s\n' "$2" > "$FAKE/$1.json"
}
# The scripts are made by one program, so each piece gets the same kind of hand-off.
python3 - "$FAKE" "$KIT" "$P_awake" "$P_stuck" "$P_limit" "$P_slow" "$P_after1" "$P_after2" \
  "$P_hold1" "$P_hold2" "$P_env1" "$P_env2" "$P_indep" "$P_ref1" "$P_ref2" "$P_same1" \
  "$P_same2" "$P_same3" <<'PY'
import json, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
(awake, stuck, limit, slow, after1, after2, hold1, hold2, env1, env2, indep, ref1, ref2,
 same1, same2, same3) = sys.argv[3:19]
hand = kit + "/scripts/handoff.py"
ERROR = "AssertionError: expected 3 but got 4 in tests/test_menu.py"


def done(name, file, good=True, **more):
    body = f'def {name}():\n    return "{name} ok"\n' if good else \
        f'def {name}():\n    return "wrong"\n'
    script = {"files": {file: body}, "commits": [{"message": f"Build {name}", "paths": [file]}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}."]],
              "cost_usd": 0.1}
    script.update(more)
    return script


def only(*words, **more):
    return {"runs": [["python3", hand, *words]], **more}


scripts = {
    awake: done("awake", "awake.py"),
    # A builder that repeats one error: ended while it runs, and the gate counts the attempt.
    stuck: {"sequence": [{"output": [ERROR, "tool call", ERROR, "tool call", ERROR, "tool call"],
                          "sleep_after": 90, "cost_usd": 0.1},
                         done("stuck", "stuck.py")]},
    # A usage limit that resets in 4 seconds: the piece waits and goes on, counting nothing.
    limit: {"sequence": [{"usage_limit_in": 4, "exit_code": 1, "cost_usd": 0.1},
                         done("limit", "limit.py")]},
    # The mailbox runs. The first piece is slow, so the test can write to the mailbox.
    slow: done("slow", "slow.py", sleep=6),
    after1: done("after1", "after1.py"),
    after2: done("after2", "after2.py"),
    hold1: done("hold1", "hold1.py", sleep=90),
    hold2: done("hold2", "hold2.py"),
    # Two environment failures in a row, on different pieces, and a piece that does not care.
    env1: only("blocked-by-environment", "--reason", "the registry is refused", sleep=0.3),
    env2: only("blocked-by-environment", "--reason", "the registry is refused", sleep=0.6),
    indep: done("indep", "indep.py", sleep=3),
    ref1: done("ref1", "ref1.py", sleep=0.5),
    ref2: done("ref2", "ref2.py", sleep=1.5),
    # The same failure in three pieces: each builder says it once, then does better.
    same1: {"sequence": [done("same1", "same1.py", good=False,
                              output=["Error: the database is not running at port 5431"]),
                         done("same1", "same1.py")]},
    same2: {"sequence": [done("same2", "same2.py", good=False,
                              output=["Error: the database is not running at port 5432"]),
                         done("same2", "same2.py")]},
    same3: {"sequence": [done("same3", "same3.py", good=False,
                              output=["Error: the database is not running at port 5433"]),
                         done("same3", "same3.py")]},
    "trim": only("done", "--summary", "Nothing to trim."),
    "default": {"runs": [["python3", "-c", "import os; open(os.environ['AI_LOOP_KIT_FINDINGS_FILE'], "
                                           "'w').write('{\"findings\": []}')"]]},
}
for number, body in scripts.items():
    (fake / f"{number}.json").write_text(json.dumps(body))
PY

# poll <seconds> <python expression over d, the run record> <record file>
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
runs="$TP_ROOT/.agents/runs"
# rec <run> <python expression over d>: print the value.
rec() {
  python3 - "$runs/$1/run.json" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))
PY
}
# held <run> <python expression>: fail unless it holds.
held() {
  python3 - "$runs/$1/run.json" "$2" <<'PY' || fail "$3"
import json, sys
d = json.load(open(sys.argv[1]))
assert eval(sys.argv[2]), (sys.argv[2], d)
PY
}

# --- the run script starts caffeinate before the pre-run check -------------------------------
if [ "$(uname)" = Darwin ]; then
  python3 "$RUN" --pieces "$P_awake" --run awake-1 --json > "$TP_BASE/awake.json" \
    2> "$TP_BASE/awake.err" \
    || { cat "$TP_BASE/awake.err" >&2; cat "$TP_BASE/awake.json" >&2
         fail "a bare run.py was refused: caffeinate must start before the pre-run check"; }
  grep -q "caffeinate -i holds the computer awake" "$TP_BASE/awake.err" \
    || fail "the run did not say it holds the computer awake"
  [ ! -f "$AWAKE_MARKER" ] || fail "the caffeinate stand-in outlived the run"
  [ "$(state_of "$P_awake")" = review ] || fail "the awake piece is not in review"
  ok "a bare run.py passes the pre-run check, because caffeinate started first, and ends it after"
else
  echo "  skipped: caffeinate and pmset exist on a Mac only, so the start order was not checked"
  python3 "$RUN" --pieces "$P_awake" --run awake-1 --json > /dev/null 2>&1 || true
fi
