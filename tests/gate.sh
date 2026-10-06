#!/usr/bin/env sh
# gate.sh: drive one piece through capture, shaping and drop with the real gate.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh). GitHub is the
# stand-in, and the gate acts as the stand-in App, whose key is made at test
# time. The test checks the labels, the needs written below the spec, the
# needs-you flag and the piece record. A second project has no App: the gate
# then starts no gh at all, queues its GitHub writes and names gate.py sync,
# which the person runs.
#
# Last, it checks that the session start hook prints the gate's brief report.
# That hook comes with the settings piece; until it calls the gate, the check
# prints a visible "skipped" line, which never counts as a pass.
#
# Run it alone: tests/gate.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GATE="$ROOT/kit/scripts/gate.py"
EVIDENCE="-m loop.evidence"
PYTHONPATH="$ROOT/kit/scripts"
export PYTHONPATH
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

# The person's own checks below must not run as an agent session.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

. "$ROOT/tests/lib/throwaway-project.sh"

# py <expression over the stand-in state as S>: print the value.
py_state() {
  python3 - "$FAKE_GH_STATE" "$1" <<'PYEOF'
import json, sys
S = json.load(open(sys.argv[1]))
issue = lambda n: next(i for i in S["issues"] if i["number"] == n)
value = eval(sys.argv[2])
print(json.dumps(value, sort_keys=True) if not isinstance(value, str) else value)
PYEOF
}

app_settings() {
  mkdir -p "$TP_ROOT/.agents/loop"
  python3 - "$ROOT/tests/stand-ins/fake-app/app.json" "$TP_ROOT/.agents/loop/local.json" <<'PYEOF'
import json, sys
app = json.load(open(sys.argv[1]))
json.dump({"github_app": {"app_id": app["app_id"], "installation_id": app["installation_id"],
                          "slug": app["slug"]}},
          open(sys.argv[2], "w"))
PYEOF
}

echo "Gate checks:"

# --- with the stand-in App ---------------------------------------------------------

tp_new gate-demo
FAKE_APP_KEY=$TP_APP_KEY
export FAKE_APP_KEY
app_settings
cd "$TP_ROOT"
BOT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["slug"] + "[bot]")' \
  "$ROOT/tests/stand-ins/fake-app/app.json")

python3 "$GATE" labels --create --json > "$TP_BASE/labels.json" || fail "labels --create failed"
for name in state:shaping state:ready state:building state:review state:approval state:done \
  state:dropped needs-you type:feature type:bug type:chore; do
  py_state "[l['name'] for l in S['labels']]" | grep -qF "\"$name\"" \
    || fail "labels --create did not make $name"
done
ok "labels --create makes the gate's own set"
python3 "$GATE" labels --create --json | grep -qF '"created": []' \
  || fail "a second labels --create made labels again"
ok "a second labels --create changes nothing"

BODY="$TP_BASE/body.md"
cp "$ROOT/tests/fixtures/specs/full.md" "$BODY"
python3 "$GATE" capture --title "Rename a report" --body-file "$BODY" --type feature --json \
  > "$TP_BASE/capture.json" || fail "capture failed: $(cat "$TP_BASE/capture.json")"
grep -qF '"piece": 1' "$TP_BASE/capture.json" || fail "capture did not make piece 1"
[ "$(py_state 'sorted(issue(1)["labels"])')" = '["needs-you", "state:shaping", "type:feature"]' ] \
  || fail "capture labels are $(py_state 'sorted(issue(1)["labels"])')"
ok "capture opens the issue with state:shaping, type:feature and needs-you"
[ "$(py_state 'sorted({e["actor"] for e in issue(1)["events"]})')" = "[\"$BOT\"]" ] \
  || fail "the labels were not written as the App"
ok "every label was written as the App"
py_state 'issue(1)["body"].split("<!-- spec:end -->")[1]' > "$TP_BASE/below.txt"
grep -qF '## Needs (written by the gate; do not edit)' "$TP_BASE/below.txt" \
  || fail "no needs list below the spec"
grep -qF 'Should a rename be undoable?' "$TP_BASE/below.txt" \
  || fail "the open question is not in the needs list"
[ "$(py_state 'issue(1)["body"].count("## Needs (written by the gate")')" = 1 ] \
  || fail "the needs list was not replaced"
ok "the needs are written below the spec, once"

python3 $EVIDENCE show --piece 1 --root "$TP_ROOT" --json > "$TP_BASE/record.json" \
  || fail "the piece record cannot be read"
grep -qF '"kind": "capture"' "$TP_BASE/record.json" || fail "the record holds no capture"
grep -qF '"unkeyed": 0' "$TP_BASE/record.json" || fail "the record has unkeyed lines"
[ -f "$TP_ROOT/.agents/pieces/1/evidence.jsonl" ] || fail "no piece record in .agents/pieces/1"
ok "the piece record holds the capture, keyed"

set +e
python3 "$GATE" move 1 building --json > "$TP_BASE/refused.json" 2> "$TP_BASE/refused.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "a move outside the table exited $code, not 3"
grep -q '^next: ' "$TP_BASE/refused.err" || fail "the refusal has no next: line"
ok "a move outside the table is refused with a next: line"

python3 "$GATE" answer 1 --question "Should a rename be undoable?" --answer "No, not now." \
  --by "the person" --json > "$TP_BASE/answer.json" || fail "answer failed: $(cat "$TP_BASE/answer.json")"
py_state 'issue(1)["body"]' > "$TP_BASE/body-after.txt"
grep -q 'Should a rename be undoable?.*No, not now\.' "$TP_BASE/body-after.txt" \
  || fail "the answer is not under Decisions"
py_state 'issue(1)["body"].split("<!-- spec:end -->")[1]' | grep -qF 'undoable' \
  && fail "the answered question is still in the needs list"
py_state 'issue(1)["labels"]' | grep -qF 'needs-you' && fail "needs-you is still set"
ok "answer writes the decision, rewrites the needs and clears needs-you"

python3 "$GATE" drop 1 --reason "The person chose another route." --json \
  > "$TP_BASE/drop.json" || fail "drop failed: $(cat "$TP_BASE/drop.json")"
[ "$(py_state 'sorted(issue(1)["labels"])')" = '["state:dropped", "type:feature"]' ] \
  || fail "after drop the labels are $(py_state 'sorted(issue(1)["labels"])')"
[ "$(py_state 'issue(1)["state"] + " " + issue(1).get("state_reason", "")')" = "closed not_planned" ] \
  || fail "drop did not close the issue as not planned"
py_state 'issue(1)["comments"][-1]["body"]' | grep -qF 'The person chose another route.' \
  || fail "the reason is not on the issue"
[ "$(py_state 'issue(1)["comments"][-1]["author"]')" = "$BOT" ] \
  || fail "the reason was not posted as the App"
ok "drop moves to state:dropped, closes the issue and posts the reason as the App"

python3 $EVIDENCE show --piece 1 --root "$TP_ROOT" --json > "$TP_BASE/record.json"
python3 - "$TP_BASE/record.json" <<'PYEOF' || fail "the record does not hold the drop"
import json, sys
entries = json.load(open(sys.argv[1]))["entries"]
moves = [e for e in entries if e["kind"] == "move"]
assert moves[-1]["move"] == 14 and moves[-1]["to"] == "dropped", moves
assert moves[-1]["reason"] == "The person chose another route.", moves
PYEOF
ok "the piece record holds move 14 and its reason"

python3 "$GATE" report --json > "$TP_BASE/report.json" || fail "report failed"
grep -qF '"state": "dropped"' "$TP_BASE/report.json" || fail "report does not show the drop"
grep -qF '"hand_changed": []' "$TP_BASE/report.json" || fail "report found a hand change"
ok "report shows the piece and no hand change"

# A label changed by hand on GitHub is reported and left alone.
python3 - "$FAKE_GH_STATE" <<'PYEOF'
import json, sys
S = json.load(open(sys.argv[1]))
issue = S["issues"][0]
issue["labels"] = [n for n in issue["labels"] if n != "state:dropped"] + ["state:ready"]
json.dump(S, open(sys.argv[1], "w"))
PYEOF
python3 "$GATE" report --json > "$TP_BASE/report.json" || fail "report failed"
grep -qF '"record": "dropped"' "$TP_BASE/report.json" || fail "report missed the hand change"
py_state 'issue(1)["labels"]' | grep -qF 'state:ready' || fail "the gate undid the hand change"
ok "a hand-changed label is reported and not undone"

# --- the session start hook ------------------------------------------------------

HOOK="$ROOT/kit/scripts/session-start.sh"
if grep -qF 'gate.py" report' "$HOOK" || grep -qF 'gate.py report' "$HOOK"; then
  out=$(cd "$TP_ROOT" && sh "$HOOK")
  printf '%s\n' "$out" | grep -qF '"pieces"' || fail "the session start hook did not print the report: $out"
  printf '%s\n' "$out" | grep -qF 'dropped' || fail "the hook's report does not show the piece"
  ok "the session start hook prints the gate's brief report"
else
  echo "  skipped: the session start hook does not call gate.py report yet (it comes with the settings piece)"
fi

# --- with no App ------------------------------------------------------------------

tp_new gate-no-app
unset FAKE_APP_KEY
cd "$TP_ROOT"
python3 "$GATE" capture --title "Export invoices" --body-file "$BODY" --type feature --json \
  > "$TP_BASE/capture.json" || fail "capture with no App failed: $(cat "$TP_BASE/capture.json")"
grep -qF '"waiting": true' "$TP_BASE/capture.json" || fail "capture with no App is not waiting"
grep -qF "$GATE sync" "$TP_BASE/capture.json" || fail "capture with no App does not name gate.py sync"
if [ -f "$FAKE_GH_LOG" ] && grep -q '^CALL' "$FAKE_GH_LOG"; then
  fail "the gate started gh with no App: $(cat "$FAKE_GH_LOG")"
fi
ok "with no App, capture starts no gh and names gate.py sync"
python3 "$GATE" move 1 dropped --reason "Not wanted." --json > /dev/null \
  || fail "a move with no App failed"
python3 "$GATE" report --json --brief | grep -qF '"waiting_for_sync": [1]' \
  || fail "the brief report does not show the waiting piece"
ok "with no App, the move is made in the record and the piece waits for sync"

set +e
CLAUDECODE=1 python3 "$GATE" sync --json > /dev/null 2> "$TP_BASE/sync.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "gate.py sync in an agent session exited $code, not 3"
ok "gate.py sync refuses to run in an agent session"

python3 "$GATE" comment 1 --text "Looks good, merge it" --json > /dev/null \
  || fail "a comment with no App was not queued"
python3 "$GATE" sync --dry-run --json > "$TP_BASE/dry.json" \
  || fail "sync --dry-run failed: $(cat "$TP_BASE/dry.json")"
for words in "Looks good, merge it" "Not wanted." "state:dropped" "Export invoices"; do
  grep -qF "$words" "$TP_BASE/dry.json" || fail "sync --dry-run does not show \"$words\""
done
ok "sync --dry-run lists every queued write in full"

set +e
python3 "$GATE" sync --json < /dev/null > /dev/null 2> "$TP_BASE/sync-pipe.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "gate.py sync with no terminal exited $code, not 3"
grep -q "terminal" "$TP_BASE/sync-pipe.err" || fail "the refusal does not name the terminal"
ok "gate.py sync refuses unless a person is at a terminal"

# The person at a terminal: a pseudo-terminal stands in for one.
python3 - "$GATE" "$TP_BASE/sync.out" <<'PYEOF' || fail "the person's sync failed: $(cat "$TP_BASE/sync.out")"
import os, pty, sys
gate, out = sys.argv[1:3]
captured = bytearray()
def read(fd):
    data = os.read(fd, 1024)
    captured.extend(data)
    return data
status = pty.spawn([sys.executable, gate, "sync"], read)
open(out, "wb").write(bytes(captured))
sys.exit(os.waitstatus_to_exitcode(status))
PYEOF
[ "$(py_state 'sorted(issue(1)["labels"])')" = '["state:dropped", "type:feature"]' ] \
  || fail "after sync the labels are $(py_state 'sorted(issue(1)["labels"])')"
[ "$(py_state 'issue(1)["state"]')" = "closed" ] || fail "sync did not close the dropped issue"
[ "$(py_state 'sorted({e["actor"] for e in issue(1)["events"]})')" = '["replay-person"]' ] \
  || fail "the person's sync did not act as the person"
python3 "$GATE" report --json --brief | grep -qF '"waiting_for_sync": []' \
  || fail "the queue is not empty after sync"
ok "the person's sync sends the queue with their own sign-in and empties it"

echo "gate.sh: all checks passed"
