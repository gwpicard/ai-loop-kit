#!/usr/bin/env sh
# trim.sh: run scripted trim sessions on a piece that passed the attempt gate, through the real
# trim script, in a throwaway project.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with the GitHub stand-in, the
# stand-in App and the Claude stand-in. A piece goes to ready by the real ready gate, is claimed
# by the real claim gate, and its honest attempt passes the real attempt gate (move 5), with a
# real judge (pytest). Then the trim script runs a scripted session five times:
#
#   1. a trim that edits a test: thrown away before any check, the piece branch unchanged;
#   2. a trim that breaks the judge: the attempt checks run again on it and fail, the piece
#      branch is unchanged, the scratch branch is left, no attempt is counted;
#   3. a trim that changes a line the piece did not add: thrown away;
#   4. a clean fold, with a stand-in `vulture` on the PATH: the brief the session read holds
#      the report inside a data block, and the piece branch moves to the scratch head by a
#      fast-forward only;
#   5. a project with no such tool: the brief says so.
#
# No network, no GitHub account and no model. Without pytest it prints a visible "skipped"
# line and does not count a pass. Run it alone: tests/trim.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GATE="$ROOT/kit/scripts/gate.py"
TRIM="$ROOT/kit/scripts/trim-check.py"
PYTHONPATH="$ROOT/kit/scripts"
CLAUDE_PLUGIN_ROOT="$ROOT/kit"
PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH CLAUDE_PLUGIN_ROOT PYTHONDONTWRITEBYTECODE

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

if ! python3 -m pytest --version >/dev/null 2>&1; then
  echo "skipped: pytest is not installed, so the trim check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Trim pass checks:"
tp_new trim-demo
tp_app
cd "$TP_ROOT"

# --- the project, the spec, the held-out cases: as in attempt-gate.sh ---------------------------
mkdir -p tests docs
cat > menu.py <<'PY'
def opens():
    return False
PY
cat > tests/test_old.py <<'PY'
def test_old_behaviour_holds():
    assert 1 + 1 == 2
PY
cat > docs/area-map <<'MAP'
/menu.py menus
tests/ menus
docs/ records
MAP
git add menu.py tests docs
git commit -q -m "Add the menu, an old test and the area map"
git push -q origin main

cat > "$TP_BASE/make-spec.py" <<'PY'
import sys

held = sys.argv[1] if len(sys.argv) > 1 else ""
line = "Held-out cases: fingerprint " + held + "\n" if held else ""
print("A user can open the menu.\n")
print("<!-- spec:start version=1 -->")
print("Path: quick\n")
print("## Goal\nThe user can open the menu, and an empty menu says so.\n")
print("## Expected flow\nFL-1 The user opens the menu and sees the items.\n")
print("## Edge cases\nEC-1 When the menu holds 0 items, then it shows the text \"No items\".\n")
print("## Must stay the same\nThe old behaviour still holds.\n"
      "Check: python3 -m pytest tests/test_old.py\n")
print("## Judge\nKind: acceptance tests, a single test\n"
      "Command: python3 -m pytest tests/acceptance/test_menu.py\n"
      "Proves: FL-1, EC-1\n" + line)
print("## Links\nRelies on: menu.py\nTouches: menus\n")
print("## Decisions\n- must-look: the person wants to read this piece.")
print("<!-- spec:end -->")
PY
python3 "$TP_BASE/make-spec.py" > "$TP_BASE/spec-1.md"
python3 "$GATE" capture --title "Open the menu" --body-file "$TP_BASE/spec-1.md" --type feature \
  --json > "$TP_BASE/capture.json" || fail "capture failed: $(cat "$TP_BASE/capture.json")"
python3 "$GATE" branch 1 --json > "$TP_BASE/branch.json" || fail "gate.py branch failed"
git checkout -q piece-1
mkdir -p tests/acceptance
cat > tests/acceptance/test_menu.py <<'PY'
from menu import opens


def test_menu_opens_and_an_empty_menu_says_so():
    assert opens() is True, "FL-1 the user opens the menu; EC-1 an empty menu says No items"
PY
git add tests/acceptance
git commit -q -m "Add the acceptance test"
git checkout -q main

cat > "$TP_BASE/case-1.txt" <<'PY'
# held-out-path: tests/held_out/test_hidden_opens.py
from menu import opens


def test_hidden_the_menu_opens_again():
    assert opens() is True
PY
cat > "$TP_BASE/case-2.txt" <<'PY'
# held-out-path: tests/held_out/test_hidden_empty.py
from menu import render


def test_hidden_an_empty_menu_says_no_items():
    assert render([]) == "No items"
PY
python3 -m loop.heldout store --piece 1 --case "FL-1=$TP_BASE/case-1.txt" \
  --case "EC-1=$TP_BASE/case-2.txt" --json > "$TP_BASE/held.json" \
  || fail "the held-out store refused the cases: $(cat "$TP_BASE/held.json")"
PRINT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' \
  "$TP_BASE/held.json")
python3 "$TP_BASE/make-spec.py" "$PRINT" > "$TP_BASE/spec-1b.md"
python3 "$GATE" spec 1 --body-file "$TP_BASE/spec-1b.md" --json > /dev/null \
  || fail "gate.py spec failed"

for _ in 1 2; do
  tp_claude_script "$(python3 - "$ROOT" <<'PY'
import json, sys
kit = sys.argv[1] + "/kit"
summary = "FL-1: test_menu_opens\nEC-1: test_empty_menu_says_no_items"
print(json.dumps({"runs": [["python3", kit + "/scripts/handoff.py", "done", "--summary", summary]]}))
PY
)"
done
python3 "$GATE" move 1 ready --json > "$TP_BASE/ready.json" 2> "$TP_BASE/ready.err" \
  || fail "move 2 was refused: $(cat "$TP_BASE/ready.err")"
python3 "$GATE" move 1 building --json > "$TP_BASE/claim.json" 2> "$TP_BASE/claim.err" \
  || fail "move 4 was refused: $(cat "$TP_BASE/claim.err")"

# --- the honest attempt, which has code that can be folded, and passes move 5 ----------------------
WT="$TP_ROOT/.agents/worktrees/1-menu"
git worktree add -q "$WT" piece-1
cat > "$WT/menu.py" <<'PY'
def opens():
    return True


def render(items):
    if not items:
        return "No items"
    return "\n".join(items)


def spare():
    return 0
PY
cat > "$WT/tests/test_menu_render.py" <<'PY'
from menu import render


def test_a_menu_with_items_lists_them():
    assert render(["tea", "milk"]) == "tea\nmilk"
PY
git -C "$WT" add -A
git -C "$WT" commit -q -m "Open the menu and render it"
python3 "$GATE" move 1 review --json > "$TP_BASE/attempt.json" 2> "$TP_BASE/attempt.err" \
  || fail "the honest attempt was refused: $(cat "$TP_BASE/attempt.err")"
ok "the real gates take the piece to review with an honest attempt"

PIECE_HEAD=$(git rev-parse piece-1)

attempts() {
  python3 - "$TP_ROOT" "$ROOT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import attempt_log, evidence
from loop.paths import Paths

print(attempt_log.used(evidence.read(Paths.for_project(Path(sys.argv[1])), 1)))
PY
}
ATTEMPTS=$(attempts)

# script_trim <name> <file> <text>: the next stand-in session rewrites one file, commits it
# and hands back as done.
script_trim() {
  tp_claude_script "$(python3 - "$ROOT" "$1" "$2" <<'PY'
import json, sys
kit = sys.argv[1] + "/kit"
name, text = sys.argv[2], open(sys.argv[3]).read()
print(json.dumps({
    "files": {name: text},
    "commits": [{"message": "Trim", "paths": [name]}],
    "runs": [["python3", kit + "/scripts/handoff.py", "done", "--summary", "Trimmed."]],
}))
PY
)"
}

run_trim() {
  # run_trim <label>: the exit code lands in TRIM_CODE, the answer in $TP_BASE/<label>.json
  set +e
  python3 "$TRIM" run --piece 1 --run night-1 --json > "$TP_BASE/$1.json" 2> "$TP_BASE/$1.err"
  TRIM_CODE=$?
  set -e
}

field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"
}

piece_unchanged() {
  [ "$(git rev-parse piece-1)" = "$PIECE_HEAD" ] || fail "$1: the piece branch moved"
  [ "$(attempts)" = "$ATTEMPTS" ] || fail "$1: an attempt was counted"
  [ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] || fail "$1: main moved"
}

# --- 1. a trim that edits a test --------------------------------------------------------------
cat > "$TP_BASE/edited-test.py" <<'PY'
from menu import render


def test_a_menu_with_items_lists_them():
    assert True
PY
script_trim tests/test_menu_render.py "$TP_BASE/edited-test.py"
run_trim trim-1
[ "$TRIM_CODE" -eq 1 ] || fail "a trim that edits a test exited $TRIM_CODE, not 1: $(cat "$TP_BASE/trim-1.err")"
[ "$(field "$TP_BASE/trim-1.json" outcome)" = untrimmed ] || fail "the outcome is not untrimmed"
grep -qF "touches-test" "$TP_BASE/trim-1.json" || fail "the answer does not name touches-test"
grep -qF "next:" "$TP_BASE/trim-1.err" || fail "the refusal has no next: line"
SCRATCH_1=$(field "$TP_BASE/trim-1.json" scratch_branch)
git rev-parse --verify -q "refs/heads/$SCRATCH_1" >/dev/null || fail "the scratch branch was not left"
piece_unchanged "trim 1"
ok "a trim that edits a test is thrown away, and the piece branch is unchanged"

# --- 2. a trim that breaks the judge ------------------------------------------------------------
cat > "$TP_BASE/broken.py" <<'PY'
def opens():
    return False


def render(items):
    if not items:
        return "No items"
    return "\n".join(items)
PY
script_trim menu.py "$TP_BASE/broken.py"
run_trim trim-2
[ "$TRIM_CODE" -eq 1 ] || fail "a trim that breaks the judge exited $TRIM_CODE, not 1: $(cat "$TP_BASE/trim-2.err")"
[ "$(field "$TP_BASE/trim-2.json" outcome)" = untrimmed ] || fail "the outcome is not untrimmed"
grep -qF "visible-judge" "$TP_BASE/trim-2.json" || fail "the attempt checks did not run again and fail"
SCRATCH_2=$(field "$TP_BASE/trim-2.json" scratch_branch)
[ "$SCRATCH_2" != "$SCRATCH_1" ] || fail "two passes share one scratch branch"
git rev-parse --verify -q "refs/heads/$SCRATCH_2" >/dev/null || fail "the scratch branch was not left"
piece_unchanged "trim 2"
ok "a trim that breaks the judge fails the attempt checks run again, counts no attempt, and is left on its scratch branch"

# --- 3. a trim that changes a line the piece did not add -----------------------------------------
cat > "$TP_BASE/readme.txt" <<'PY'
# Another title
PY
script_trim README.md "$TP_BASE/readme.txt"
run_trim trim-3
[ "$TRIM_CODE" -eq 1 ] || fail "a trim of a line the piece did not add exited $TRIM_CODE, not 1"
grep -qF "not-piece-code" "$TP_BASE/trim-3.json" || fail "the answer does not name not-piece-code"
piece_unchanged "trim 3"
ok "a trim that changes a line the piece did not add is thrown away"

# --- 4. a clean fold, and the project's own report reaches the session ------------------------------
mkdir -p "$TP_BASE/tools"
cat > "$TP_BASE/tools/vulture" <<'SH'
#!/bin/sh
echo "menu.py:11: unused function 'spare' (60% confidence)"
exit 3
SH
chmod +x "$TP_BASE/tools/vulture"
cat > "$TP_BASE/folded.py" <<'PY'
def opens():
    return True


def render(items):
    if not items:
        return "No items"
    return "\n".join(items)
PY
script_trim menu.py "$TP_BASE/folded.py"
SAVED_PATH=$PATH
PATH="$TP_BASE/tools:$PATH"
run_trim trim-4
PATH=$SAVED_PATH
[ "$TRIM_CODE" -eq 0 ] || fail "a clean fold exited $TRIM_CODE, not 0: $(cat "$TP_BASE/trim-4.err")"
[ "$(field "$TP_BASE/trim-4.json" outcome)" = trimmed ] || fail "the outcome is not trimmed"
SCRATCH_4=$(field "$TP_BASE/trim-4.json" scratch_branch)
[ "$(git rev-parse piece-1)" = "$(git rev-parse "refs/heads/$SCRATCH_4")" ] \
  || fail "the piece branch is not at the scratch head"
git merge-base --is-ancestor "$PIECE_HEAD" piece-1 || fail "the piece branch did not move by a fast-forward"
git show piece-1:menu.py | grep -q spare && fail "the folded function is still in the piece"
[ "$(attempts)" = "$ATTEMPTS" ] || fail "the trim counted an attempt"
BRIEF=$(field "$TP_BASE/trim-4.json" brief_file)
python3 - "$BRIEF" <<'PY' || fail "the report is not inside a data block of the brief"
import re, sys
text = open(sys.argv[1]).read()
blocks = re.findall(r"<<<DATA BEGIN findings nonce=(\w+)>>>\n(.*?)\n<<<DATA END findings nonce=\1>>>",
                    text, re.S)
assert blocks, "no findings block"
assert "unused function 'spare'" in blocks[0][1], blocks[0][1]
assert "unused function 'spare'" not in re.sub(r"<<<DATA BEGIN.*?<<<DATA END [^>]*>>>", "", text,
                                               flags=re.S)
PY
ok "a clean fold passes, the piece branch fast-forwards to it, and the unused-code report reached the session in a data block"

# --- 5. a project with no such tool ----------------------------------------------------------------
PIECE_HEAD=$(git rev-parse piece-1)
cat > "$TP_BASE/folded-again.py" <<'PY'
def opens():
    return True


def render(items):
    return "\n".join(items) or "No items"
PY
script_trim menu.py "$TP_BASE/folded-again.py"
run_trim trim-5
[ "$TRIM_CODE" -eq 0 ] || fail "the second fold exited $TRIM_CODE, not 0: $(cat "$TP_BASE/trim-5.err")"
BRIEF=$(field "$TP_BASE/trim-5.json" brief_file)
grep -qi "no tool" "$BRIEF" || fail "the brief does not say the project has no such tool"
ok "a project with no tool gets a brief that says so"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the trim changed the project folder"
ok "the trim left the project folder as it was"

echo "trim.sh: all checks passed"
