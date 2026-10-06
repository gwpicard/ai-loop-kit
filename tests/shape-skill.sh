#!/usr/bin/env sh
# shape-skill.sh: drive the helper scripts of the /shape skill in throwaway projects.
#
# The skill is a conversation, and a conversation needs a model, so its scenario
# evals sit in kit/skills/shape/evals/ and run by hand. This check holds what a
# script can hold:
#
# - the duplicate search finds a dropped piece and a closed issue that share the
#   words of a new idea, warns about the dropped one, and reads GitHub only as
#   the App;
# - a duplicate gets the new words as a kit comment through the gate, signed by
#   the App, and no new issue opens. With no App, the comment waits for the
#   person and a next: line says how;
# - with no App the search reads nothing on GitHub and says so with a next: line;
# - held-out cases land in the gate-only store, and never in git, the issue or
#   the command's own output;
# - the skill text names the commands that hold its rules, and the check fails
#   on a copy that lost one.
#
# No network, no GitHub account and no model. Run it alone: tests/shape-skill.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GATE="$ROOT/kit/scripts/gate.py"
SKILL_DIR="$ROOT/kit/skills/shape"
FIND="$SKILL_DIR/scripts/find-duplicates.py"
SKILL="$SKILL_DIR/SKILL.md"
PYTHONPATH="$ROOT/kit/scripts"
PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH PYTHONDONTWRITEBYTECODE

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

[ -f "$FIND" ] || fail "missing $FIND"
[ -f "$SKILL" ] || fail "missing $SKILL"

. "$ROOT/tests/lib/throwaway-project.sh"

# jq-free JSON reading: js <file> <python expression over the parsed file as J>.
js() {
  python3 - "$1" "$2" <<'PYEOF'
import json, sys
J = json.load(open(sys.argv[1]))
value = eval(sys.argv[2])
print(json.dumps(value, sort_keys=True) if not isinstance(value, str) else value)
PYEOF
}

# py_state <expression over the stand-in state as S>: print the value.
py_state() {
  python3 - "$FAKE_GH_STATE" "$1" <<'PYEOF'
import json, sys
S = json.load(open(sys.argv[1]))
issue = lambda n: next(i for i in S["issues"] if i["number"] == n)
value = eval(sys.argv[2])
print(json.dumps(value, sort_keys=True) if not isinstance(value, str) else value)
PYEOF
}

echo "Shape skill checks:"

# --- the script follows the contract ------------------------------------------------

python3 "$FIND" --help | grep -q 'exit codes' || fail "find-duplicates.py --help names no exit codes"
python3 "$FIND" search --help | grep -q -- '--text' || fail "search --help does not name --text"
python3 "$FIND" comment --help | grep -q -- '--dry-run' || fail "comment --help has no --dry-run"
ok "find-duplicates.py has --help, with exit codes"

# --- with the stand-in App -----------------------------------------------------------

tp_new shape-demo
tp_app
cd "$TP_ROOT"
BOT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["slug"] + "[bot]")' \
  "$ROOT/tests/stand-ins/fake-app/app.json")
python3 "$GATE" labels --create --json > /dev/null || fail "labels --create failed"

HEADER="$TP_BASE/header.md"
printf 'A header that says what the piece is for.\n' > "$HEADER"

# A dropped piece, made through the gate, with its reason.
python3 "$GATE" capture --title "Export invoices to a CSV file" --body-file "$HEADER" --json \
  > /dev/null || fail "capture of the first piece failed"
python3 "$GATE" drop 1 --reason "The accountant wants a PDF, not a CSV file." --json \
  > /dev/null || fail "drop failed"
# A closed issue made by hand, with no state label, as an old issue may be.
(cd "$TP_ROOT" && gh issue create --title "Dark mode on the settings page" \
  --body "Add a dark theme to the settings page." >/dev/null)
(cd "$TP_ROOT" && gh issue close 2 >/dev/null)
# An open piece.
python3 "$GATE" capture --title "Late payment reminders by email" --body-file "$HEADER" --json \
  > /dev/null || fail "capture of the third piece failed"
ISSUES_BEFORE=$(py_state 'len(S["issues"])')
: > "$FAKE_GH_LOG"

python3 "$FIND" search --text "Let people export their invoices as a CSV file" --json \
  > "$TP_BASE/search.json" || fail "search failed: $(cat "$TP_BASE/search.json")"
[ "$(js "$TP_BASE/search.json" 'J["github_read"]')" = "true" ] || fail "search did not read GitHub"
[ "$(js "$TP_BASE/search.json" 'J["matches"][0]["number"]')" = "1" ] \
  || fail "the dropped piece is not the first match: $(cat "$TP_BASE/search.json")"
[ "$(js "$TP_BASE/search.json" 'J["matches"][0]["state"]')" = "closed" ] \
  || fail "the dropped piece is not shown as closed"
[ "$(js "$TP_BASE/search.json" 'len(J["matches"])')" = "1" ] \
  || fail "search matched more than the one piece with the same words"
ok "the search finds a closed piece with the same words"

[ "$(js "$TP_BASE/search.json" 'J["matches"][0]["dropped"]')" = "true" ] \
  || fail "the match is not marked as dropped"
js "$TP_BASE/search.json" 'J["matches"][0]["reason"]' | grep -qF 'PDF' \
  || fail "the drop reason is not shown"
js "$TP_BASE/search.json" '" ".join(J["warnings"])' | grep -qi 'dropped' \
  || fail "the dropped piece gave no warning"
ok "the dropped-piece search warns and shows the reason"

# Every read was made as the App, never as the person.
grep -q '^AS' "$FAKE_GH_LOG" || fail "the search made no call as the App"
if grep '^AS' "$FAKE_GH_LOG" | grep -vqF "$BOT"; then
  fail "the search read GitHub as someone other than the App: $(grep '^AS' "$FAKE_GH_LOG" | sort -u)"
fi
ok "the search reads GitHub only as the App"

python3 "$FIND" search --text "Dark mode for the settings page" --json \
  > "$TP_BASE/search2.json" || fail "second search failed"
[ "$(js "$TP_BASE/search2.json" 'J["matches"][0]["number"]')" = "2" ] \
  || fail "the closed issue with the same words is not found"
[ "$(js "$TP_BASE/search2.json" 'J["matches"][0]["dropped"]')" = "false" ] \
  || fail "a closed issue with no dropped label is marked as dropped"
ok "a closed issue with the same words is found, and is not called dropped"

python3 "$FIND" search --text "A weather widget on the dashboard" --json \
  > "$TP_BASE/search3.json" || fail "third search failed"
[ "$(js "$TP_BASE/search3.json" 'len(J["matches"])')" = "0" ] \
  || fail "an unrelated idea matched: $(cat "$TP_BASE/search3.json")"
ok "an unrelated idea matches nothing"

# The new words go to the duplicate as a kit comment, through the gate.
python3 "$FIND" comment 1 --text "Asked again: a CSV file for the bookkeeper." --dry-run --json \
  > "$TP_BASE/comment-dry.json" || fail "comment --dry-run failed: $(cat "$TP_BASE/comment-dry.json")"
[ "$(py_state 'len(issue(1)["comments"])')" = "1" ] || fail "--dry-run posted a comment"
ok "comment --dry-run posts nothing"

python3 "$FIND" comment 1 --text "Asked again: a CSV file for the bookkeeper." --json \
  > "$TP_BASE/comment.json" || fail "comment failed: $(cat "$TP_BASE/comment.json")"
py_state 'issue(1)["comments"][-1]["body"]' | grep -qF 'a CSV file for the bookkeeper' \
  || fail "the new words are not on the duplicate"
[ "$(py_state 'issue(1)["comments"][-1]["author"]')" = "$BOT" ] \
  || fail "the comment was not signed by the App"
[ "$(py_state 'len(S["issues"])')" = "$ISSUES_BEFORE" ] || fail "an issue was opened for a duplicate"
ok "a duplicate gets the new words as a comment signed by the App, and no issue opens"

# An issue the gate never captured cannot take a gate comment. The refusal names the next step.
set +e
python3 "$FIND" comment 2 --text "Asked again." --json > "$TP_BASE/refused.json" 2> "$TP_BASE/refused.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "a comment on an issue outside the gate's record exited $code, not 3"
grep -q '^next: ' "$TP_BASE/refused.err" || fail "the refusal has no next: line"
[ "$(py_state 'len(issue(2).get("comments", []))')" = "0" ] || fail "a comment reached an uncaptured issue"
ok "a comment the gate cannot post is refused with a next: line"

# --- held-out cases ------------------------------------------------------------------

CASE_A="$TP_BASE/case-a.txt"
CASE_B="$TP_BASE/case-b.txt"
printf 'When the month has 40000 invoices, then the file still has one header line (HIDDEN-ONE).\n' > "$CASE_A"
printf 'When an invoice has a comma in the name, then the name is quoted (HIDDEN-TWO).\n' > "$CASE_B"
python3 -m loop.heldout store --piece 3 --case HO-1="$CASE_A" --case HO-2="$CASE_B" --json \
  > "$TP_BASE/heldout.json" || fail "heldout store failed: $(cat "$TP_BASE/heldout.json")"
FINGERPRINT=$(js "$TP_BASE/heldout.json" 'J["fingerprint"]')
printf '%s' "$FINGERPRINT" | grep -qE '^[0-9a-f]{64}$' || fail "the fingerprint is not 64 hex digits"
grep -q 'HIDDEN' "$TP_BASE/heldout.json" && fail "the store printed a case"
find "$TP_DATA" -name 'HO-1.case' | grep -q . || fail "the case is not in the gate-only store"
ok "held-out cases land in the store, and only the fingerprint is printed"

BODY="$TP_BASE/body.md"
cat > "$BODY" <<BODYEOF
A header that says what the piece is for.

<!-- spec:start version=1 -->
## Goal
Export invoices as a CSV file.

## Judge
Kind: acceptance test
Command: python3 -m pytest tests/test_export.py
Proves: EC-1
Held-out cases: $FINGERPRINT
<!-- spec:end -->
BODYEOF
python3 "$GATE" spec 3 --body-file "$BODY" --json > /dev/null || fail "gate.py spec failed"
py_state 'issue(3)["body"]' | grep -qF "$FINGERPRINT" || fail "the fingerprint is not in the spec"
py_state 'json.dumps(S)' 2>/dev/null | grep -q 'HIDDEN' && fail "a held-out case reached the issue"
if git -C "$TP_ROOT" grep -q 'HIDDEN' 2>/dev/null; then fail "a held-out case is in git"; fi
if grep -rq 'HIDDEN' "$TP_ROOT" --include='*' --exclude-dir=.git 2>/dev/null; then
  fail "a held-out case is in a file of the project"
fi
ok "the spec holds the fingerprint, and no case is in git, in the project or on the issue"

# --- with no App ---------------------------------------------------------------------

tp_new shape-no-app
unset FAKE_APP_KEY
cd "$TP_ROOT"
python3 "$GATE" capture --title "Export invoices to a CSV file" --body-file "$HEADER" --json \
  > /dev/null || fail "capture with no App failed"
python3 "$GATE" move 1 dropped --reason "The accountant wants a PDF." --json > /dev/null \
  || fail "drop with no App failed"
: > "$FAKE_GH_LOG"

python3 "$FIND" search --text "Export my invoices as a CSV file" --json \
  > "$TP_BASE/noapp.json" 2> "$TP_BASE/noapp.err" || fail "search with no App failed"
[ "$(js "$TP_BASE/noapp.json" 'J["github_read"]')" = "false" ] \
  || fail "search with no App says it read GitHub"
grep -q '^next: ' "$TP_BASE/noapp.err" || fail "search with no App has no next: line"
js "$TP_BASE/noapp.json" 'J["next"]' | grep -qi 'app' || fail "the next: line does not name the App"
if grep -q '^CALL' "$FAKE_GH_LOG"; then fail "search with no App started gh: $(cat "$FAKE_GH_LOG")"; fi
ok "with no App, the search reads no GitHub, starts no gh and says so with a next: line"

[ "$(js "$TP_BASE/noapp.json" 'J["matches"][0]["dropped"]')" = "true" ] \
  || fail "the gate's own record did not give the dropped piece"
js "$TP_BASE/noapp.json" '" ".join(J["warnings"])' | grep -qi 'dropped' \
  || fail "no dropped warning from the record"
ok "the gate's own record still warns about a dropped piece"

python3 "$FIND" comment 1 --text "Asked again." --json > "$TP_BASE/noapp-comment.json" \
  || fail "comment with no App failed: $(cat "$TP_BASE/noapp-comment.json")"
grep -qF "$GATE sync" "$TP_BASE/noapp-comment.json" || fail "the waiting comment does not name gate.py sync"
if grep -q '^CALL' "$FAKE_GH_LOG"; then fail "comment with no App started gh"; fi
ok "with no App, the comment waits for the person, with a next: line"

# --- the skill text ------------------------------------------------------------------

# Each rule is a phrase that must stay in SKILL.md. A copy without it must fail.
need() {
  # need <description> <pattern> <file>
  grep -qiE "$2" "$3" || return 1
}
check_skill() {
  need "capture" 'gate\.py capture' "$1" &&
    need "ready move" 'gate\.py move .*ready' "$1" &&
    need "lint before ready" 'spec\.py lint' "$1" &&
    need "held-out store" 'loop\.heldout store' "$1" &&
    need "question cap" 'question_cap' "$1" &&
    need "duplicates" 'find-duplicates\.py' "$1" &&
    need "co-change" 'co-change\.sh' "$1" &&
    need "acceptance" 'Accepted:' "$1" &&
    need "silence" 'silence' "$1"
}
check_skill "$SKILL" || fail "SKILL.md lost a command or rule that holds the skill"
ok "SKILL.md names each command that holds its rules"

MUT=$(mktemp -d)
for pattern in 'gate\.py capture' 'spec\.py lint' 'loop\.heldout store' 'question_cap' \
  'find-duplicates\.py' 'co-change\.sh' 'Accepted:' 'silence'; do
  sed -E "s@$pattern@@Ig" "$SKILL" > "$MUT/SKILL.md"
  if check_skill "$MUT/SKILL.md"; then fail "removing '$pattern' from a copy of SKILL.md was not caught"; fi
done
ok "the skill text check fails on a copy that lost a rule"

python3 "$ROOT/kit/scripts/check-skills.py" "$ROOT/kit/skills" > "$TP_BASE/skills.out" \
  || fail "check-skills fails on kit/skills: $(cat "$TP_BASE/skills.out")"
ok "check-skills passes on kit/skills"

echo "Shape skill checks passed."
