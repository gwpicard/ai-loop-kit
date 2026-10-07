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
PIECES="awake:awake.py:aw stuck:stuck.py:st limit:limit.py:li steady:steady.py:mb after1:after1.py:mb \
after2:after2.py:mb hold1:hold1.py:mh hold2:hold2.py:mh env1:env1.py:e1 env2:env2.py:e2 \
indep:indep.py:e3 ref1:ref1.py:r1 ref2:ref2.py:r2 same1:same1.py:f1 same2:same2.py:f2 \
same3:same3.py:f3"
. "$ROOT/tests/lib/run-project.sh"

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
trap 'rm -f "$AWAKE_MARKER"; exit 0' TERM
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
python3 - "$FAKE" "$KIT" "$P_awake" "$P_stuck" "$P_limit" "$P_steady" "$P_after1" "$P_after2" \
  "$P_hold1" "$P_hold2" "$P_env1" "$P_env2" "$P_indep" "$P_ref1" "$P_ref2" "$P_same1" \
  "$P_same2" "$P_same3" <<'PY'
import json, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
(awake, stuck, limit, steady, after1, after2, hold1, hold2, env1, env2, indep, ref1, ref2,
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
    steady: done("steady", "steady.py", sleep=6),
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

# attempt_results <piece>: the results in the gate's attempt log, in order, on one line.
attempt_results() {
  PYTHONPATH="$KIT/scripts" python3 -m loop.evidence show --piece "$1" --root "$TP_ROOT" --json \
    | python3 -c '
import json, sys
entries = json.load(sys.stdin)["entries"]
print(" ".join(e["result"] for e in entries if e.get("kind") == "attempt"))'
}

# --- a stuck builder is ended while it runs, and the attempt counts through the gate ------------
started=$(date +%s)
python3 "$RUN" --pieces "$P_stuck" --run stuck-1 --json > "$TP_BASE/stuck.json" \
  2> "$TP_BASE/stuck.err" \
  || { cat "$TP_BASE/stuck.err" >&2; fail "the stuck run failed"; }
took=$(($(date +%s) - started))
[ "$took" -lt 80 ] || fail "the stuck builder was not ended: the run took $took seconds"
held stuck-1 'd["pieces"]["'"$P_stuck"'"]["status"] == "built" and d["pieces"]["'"$P_stuck"'"]["stuck"] == 1' \
  "the stuck piece did not end built with one stuck attempt"
held stuck-1 'any("as stuck" in x["text"] and "counts as an attempt" in x["text"] for x in d["decisions"])' \
  "the run did not record the stuck attempt as a decision"
attempt_results "$P_stuck" > "$TP_BASE/stuck-attempts.txt"
[ "$(cat "$TP_BASE/stuck-attempts.txt")" = "failed passed" ] \
  || fail "the gate's attempt log is not 'failed passed': $(cat "$TP_BASE/stuck-attempts.txt")"
ok "a builder that repeated one error was ended; the gate counted that attempt, and the next passed"

# --- a usage limit waits for the reset, counts nothing, and the tokens are recorded --------------
python3 "$RUN" --pieces "$P_limit" --run limit-1 --json > "$TP_BASE/limit.json" \
  2> "$TP_BASE/limit.err" \
  || { cat "$TP_BASE/limit.err" >&2; fail "the usage-limit run failed"; }
held limit-1 'd["pieces"]["'"$P_limit"'"]["status"] == "built"' "the limited piece did not end built"
held limit-1 'any("usage limit" in x["text"] and "no attempt" in x["text"] for x in d["decisions"])' \
  "the run did not record the usage limit as a decision that counts no attempt"
held limit-1 '(lambda w: len(w) == 2 and w[1][0] - w[0][1] >= 2.0)(d["pieces"]["'"$P_limit"'"]["windows"])' \
  "the piece did not wait for the reset between its two sessions"
held limit-1 'd["pieces"]["'"$P_limit"'"]["tokens"] == {"input_tokens": 200, "output_tokens": 100}' \
  "the tokens of both sessions are not recorded for the piece"
python3 "$GATE" report "$P_limit" --json | python3 -c '
import json, sys
piece = json.load(sys.stdin)["pieces"][0]
assert piece["state"] == "review", piece["state"]
' || fail "the limited piece is not in review"
[ "$(attempt_results "$P_limit")" = "passed" ] || fail "a usage limit counted as an attempt"
ok "a usage limit waited for the reset and counted no attempt; the tokens of both sessions are recorded"

# --- the mailbox: pause, continue and a stop left by an earlier run ------------------------------
# Three pieces share the area mb, so they run one after another. The mailbox already holds a
# stop, left by an earlier run: it must not be obeyed.
mkdir -p "$runs/mail-1"
printf 'stop\n' > "$runs/mail-1/mailbox"
python3 "$RUN" --pieces "$P_steady,$P_after1,$P_after2" --run mail-1 --json \
  > "$TP_BASE/mail.json" 2> "$TP_BASE/mail.err" &
MAIL_PID=$!
poll 60 'd["pieces"]["'"$P_steady"'"]["status"] == "building"' "$runs/mail-1/run.json" \
  || { cat "$TP_BASE/mail.err" >&2; fail "the first mailbox piece never started"; }
printf 'pause\n' >> "$runs/mail-1/mailbox"
poll 20 'any("said pause" in n["text"] for n in d["notes"])' "$runs/mail-1/run.json" \
  || fail "the run did not read the pause"
poll 150 'd["pieces"]["'"$P_steady"'"]["status"] == "built"' "$runs/mail-1/run.json" \
  || fail "the piece in flight did not end its work while the run was paused"
sleep 4
kill -0 "$MAIL_PID" 2>/dev/null || fail "a paused run ended as if it had finished"
held mail-1 'd["status"] == "running" and d["pieces"]["'"$P_after1"'"]["status"] == "pending" and d["pieces"]["'"$P_after2"'"]["status"] == "pending"' \
  "a paused run started a new piece"
ok "a stop line from an earlier run was not obeyed, and a pause held the next pieces back while the run lived"
printf 'continue\n' >> "$runs/mail-1/mailbox"
set +e
wait "$MAIL_PID"
code=$?
set -e
[ "$code" -eq 0 ] || fail "the run after continue exited $code: $(cat "$TP_BASE/mail.err")"
held mail-1 'd["status"] == "finished" and all(p["status"] == "built" for p in d["pieces"].values())' \
  "the pieces did not all end built after continue"
held mail-1 '[e["command"] for e in d["mailbox"]["events"]] == ["pause", "continue"]' \
  "the run record does not hold the pause and the continue"
held mail-1 'any("from before the run started" in n["text"] for n in d["notes"])' \
  "the run did not say it left the earlier stop alone"
held mail-1 'all(p["tokens"] == {"input_tokens": 100, "output_tokens": 50} for p in d["pieces"].values())' \
  "the tokens are not recorded for each piece"
ok "continue let the run finish; the run record holds each command and the tokens of each piece"

# --- the mailbox: stop sends the building piece back to ready by move 7 -------------------------
mkdir -p "$runs/mail-2"
python3 "$RUN" --pieces "$P_hold1,$P_hold2" --run mail-2 --json \
  > "$TP_BASE/stop.json" 2> "$TP_BASE/stop.err" &
STOP_PID=$!
poll 60 'd["pieces"]["'"$P_hold1"'"]["status"] == "building"' "$runs/mail-2/run.json" \
  || { cat "$TP_BASE/stop.err" >&2; fail "the stop piece never started"; }
sleep 1
printf 'stop\n' >> "$runs/mail-2/mailbox"
i=0
while kill -0 "$STOP_PID" 2>/dev/null && [ "$i" -lt 80 ]; do
  i=$((i + 1))
  sleep 0.5
done
if kill -0 "$STOP_PID" 2>/dev/null; then
  kill -TERM "$STOP_PID"  # the run script this test started, by its own number
  fail "the run did not stop on a stop line"
fi
set +e
wait "$STOP_PID"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the stopped run exited $code, not 3: $(cat "$TP_BASE/stop.err")"
grep -q "^next:" "$TP_BASE/stop.err" || fail "the stopped run printed no next: line"
held mail-2 'd["status"] == "stopped" and d["pieces"]["'"$P_hold1"'"]["status"] == "stopped"' \
  "the run record does not say stopped"
[ "$(state_of "$P_hold1")" = ready ] || fail "the stopped piece is not back in ready"
python3 "$GATE" report "$P_hold1" --json | python3 -c '
import json, sys
assert json.load(sys.stdin)["pieces"][0]["moves"][-1] == 7
' || fail "the stop was not move 7"
git rev-parse --verify -q "refs/heads/piece-$P_hold1" >/dev/null || fail "the stop lost the branch"
[ "$(state_of "$P_hold2")" = ready ] || fail "the piece that never started is not still in ready"
held mail-2 '[e["command"] for e in d["mailbox"]["events"]] == ["stop"]' \
  "the run record does not hold the stop"
ok "a stop line ended the run: the building piece went back to ready by move 7, with its branch kept"

# --- the real stops notify once, and the run carries on -----------------------------------------
# Two environment failures in a row on different pieces. A third piece is independent.
python3 "$RUN" --pieces "$P_env1,$P_env2,$P_indep" --run stops-env --json \
  > "$TP_BASE/env.json" 2> "$TP_BASE/env.err" \
  || { cat "$TP_BASE/env.err" >&2; fail "the environment run failed"; }
held stops-env 'len(d["real_stops"]) == 1 and d["real_stops"][0]["kind"] == "environment" and d["real_stops"][0]["pieces"] == ['"$P_env1,$P_env2"']' \
  "the two environment failures were not notified once"
[ "$(grep -c "^real stop:" "$TP_BASE/env.err")" -eq 1 ] || fail "the real stop was not on the log once"
held stops-env 'd["status"] == "finished" and d["pieces"]["'"$P_indep"'"]["status"] == "built" and d["pieces"]["'"$P_env1"'"]["status"] == "returned-ready"' \
  "the run did not carry on with the independent piece"
ok "two environment failures in a row notified once, and the run built the independent piece"

# The same refused command in two pieces. The command log is what the guard hook writes; here
# the test writes the rows the hook would, for each piece's folder.
mkdir -p "$runs/stops-cmd"
python3 - "$runs/stops-cmd/commands.log" "$TP_ROOT/.agents/worktrees" "$P_ref1" "$P_ref2" <<'PY'
import json, sys
log, base, one, two = sys.argv[1:5]
rows = [{"event": "refuse", "command": "npm install left-pad", "session": f"s{n}",
         "cwd": f"{base}/{n}-run-ref{i}", "tool": "Bash"} for i, n in ((1, one), (2, two))]
open(log, "w").write("".join(json.dumps(r) + "\n" for r in rows))
PY
python3 "$RUN" --pieces "$P_ref1,$P_ref2" --run stops-cmd --json \
  > "$TP_BASE/cmd.json" 2> "$TP_BASE/cmd.err" \
  || { cat "$TP_BASE/cmd.err" >&2; fail "the refused-command run failed"; }
held stops-cmd 'len(d["real_stops"]) == 1 and d["real_stops"][0]["kind"] == "refused-command"' \
  "the same refused command in two pieces was not notified once"
held stops-cmd 'all(p["status"] == "built" for p in d["pieces"].values())' \
  "the run did not carry on and build both pieces"
ok "the same refused command in two pieces notified once, and the run carried on"

# The same failure in three pieces.
python3 "$RUN" --pieces "$P_same1,$P_same2,$P_same3" --run stops-same --json \
  > "$TP_BASE/same.json" 2> "$TP_BASE/same.err" \
  || { cat "$TP_BASE/same.err" >&2; fail "the same-failure run failed"; }
held stops-same 'len(d["real_stops"]) == 1 and d["real_stops"][0]["kind"] == "same-failure" and len(d["real_stops"][0]["pieces"]) == 3' \
  "the same failure in three pieces was not notified once"
held stops-same 'all(p["status"] == "built" for p in d["pieces"].values())' \
  "the run did not carry on and build the three pieces"
ok "the same failure in three pieces notified once, and the run carried on"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the runs changed the project folder"
ok "the runs left the project folder as it was"

echo "Watch and mailbox checks passed."
