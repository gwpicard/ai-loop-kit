#!/usr/bin/env sh
# claim-gate.sh: claim one ready piece with the real claim gate (move 4).
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with the GitHub
# stand-in and the stand-in App. A piece goes to ready by the real ready gate,
# with a real judge (pytest) on main. Then the claim runs.
#
# The test checks: a dry run of the claim passes and moves nothing; a blocker
# that is not done refuses the claim and the piece stays ready; then the issue
# body is edited by hand, as a person would on GitHub, and the claim sends the
# piece back to shaping by move 3 with the reason on the move, in the record,
# in a comment on the issue and as an open question in the spec; and a piece
# whose spec is untouched is claimed, becomes building and keeps its fingerprint.
#
# No network, no GitHub account and no model. Without pytest it prints a visible
# "skipped" line and does not count a pass. Run it alone: tests/claim-gate.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GATE="$ROOT/kit/scripts/gate.py"
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
  echo "skipped: pytest is not installed, so the claim-gate check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Claim gate checks:"
tp_new claim-demo
tp_app
cd "$TP_ROOT"

# --- the project: code, a passing old test, the area map ---------------------------
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

# --- the spec (the quick path: one area, one test, nothing sensitive) --------------
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
grep -qF '"piece": 1' "$TP_BASE/capture.json" || fail "capture did not make piece 1"
ok "the piece is captured in shaping"

# --- the piece branch: the judge files as the first commit --------------------------
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

# --- the held-out cases, in the gate-only store -------------------------------------
echo "a held-out case for FL-1" > "$TP_BASE/case-1.txt"
echo "a held-out case for EC-1" > "$TP_BASE/case-2.txt"
python3 -m loop.heldout store --piece 1 --case "FL-1=$TP_BASE/case-1.txt" \
  --case "EC-1=$TP_BASE/case-2.txt" --json > "$TP_BASE/held.json" \
  || fail "the held-out store refused the cases: $(cat "$TP_BASE/held.json")"
PRINT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' \
  "$TP_BASE/held.json")
[ -z "$(git status --porcelain -- . ':!.agents')" ] \
  || fail "the held-out cases reached the project folder"
python3 "$TP_BASE/make-spec.py" "$PRINT" > "$TP_BASE/spec-1b.md"

python3 "$GATE" spec 1 --body-file "$TP_BASE/spec-1b.md" --json > /dev/null \
  || fail "gate.py spec failed"

# --- the two test-list sessions, scripted ---------------------------------------------
tp_claude_script "$(python3 - "$ROOT" <<'PY'
import json, sys
kit = sys.argv[1] + "/kit"
summary = "FL-1: test_menu_opens\nEC-1: test_empty_menu_says_no_items"
print(json.dumps({"runs": [["python3", kit + "/scripts/handoff.py", "done", "--summary", summary]]}))
PY
)"

python3 "$GATE" spec 1 --body-file "$TP_BASE/spec-1b.md" --json > /dev/null \
  || fail "gate.py spec failed"

tp_claude_script "$(python3 - "$ROOT" <<'PY'
import json, sys
kit = sys.argv[1] + "/kit"
summary = "FL-1: test_menu_opens\nEC-1: test_empty_menu_says_no_items"
print(json.dumps({"runs": [["python3", kit + "/scripts/handoff.py", "done", "--summary", summary]]}))
PY
)"

python3 "$GATE" move 1 ready --json > "$TP_BASE/ready.json" 2> "$TP_BASE/ready.err" \
  || fail "move 2 was refused: $(cat "$TP_BASE/ready.err")"
ok "the gate takes the piece to ready"

state_of() {
  python3 "$GATE" report 1 --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
[ "$(state_of)" = ready ] || fail "the piece is not ready"
python3 - "$TP_ROOT" "$ROOT" <<'PY' || fail "ready wrote no relied-on entry"
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import evidence
from loop.paths import Paths
record = evidence.read(Paths.for_project(Path(sys.argv[1])), 1)
entry = [e for e in record if e["kind"] == "relied-on"]
assert len(entry) == 1 and list(entry[0]["files"]) == ["menu.py"], entry
PY
ok "ready recorded the relied-on file and its fingerprint"

# --- a dry run of the claim passes and moves nothing ----------------------------------
python3 "$GATE" move 1 building --dry-run --json > "$TP_BASE/dry.json" 2> "$TP_BASE/dry.err" \
  || fail "the dry run of the claim was refused: $(cat "$TP_BASE/dry.err")"
[ "$(state_of)" = ready ] || fail "the dry run moved the piece"
[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the claim changed the project folder"
ok "a dry run of the claim passes with the real judge on main, and moves nothing"

# --- a blocker that is not done refuses the claim; the piece stays ready ---------------
gh issue create --title "Blocker" --body "Needed first." > /dev/null
gh api --method POST "repos/{owner}/{repo}/issues/1/dependencies/blocked_by" -F issue_id=2 > /dev/null \
  || fail "could not link the blocker"
set +e
python3 "$GATE" move 1 building --json > "$TP_BASE/blocked.json" 2> "$TP_BASE/blocked.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "a blocked claim exited $code, not 3: $(cat "$TP_BASE/blocked.err")"
grep -qF "issue 2" "$TP_BASE/blocked.err" || fail "the refusal does not name the blocker"
grep -qF "next:" "$TP_BASE/blocked.err" || fail "the refusal has no next: line"
[ "$(state_of)" = ready ] || fail "a blocked claim moved the piece"
ok "a blocker that is not done refuses the claim (exit 3), and the piece stays ready"

python3 - "$FAKE_GH_STATE" <<'PY'
import json, sys
S = json.load(open(sys.argv[1]))
for issue in S["issues"]:
    issue["blocked_by"] = []
json.dump(S, open(sys.argv[1], "w"))
PY

# --- the spec edited by hand on GitHub: sent back to shaping ---------------------------
python3 - "$FAKE_GH_STATE" <<'PY'
import json, sys
S = json.load(open(sys.argv[1]))
issue = next(i for i in S["issues"] if i["number"] == 1)
old = "The user can open the menu, and an empty menu says so."
assert old in issue["body"], issue["body"]
issue["body"] = issue["body"].replace(old, old + " It also remembers the last item.")
json.dump(S, open(sys.argv[1], "w"))
PY
set +e
python3 "$GATE" move 1 building --json > "$TP_BASE/claim.json" 2> "$TP_BASE/claim.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the claim of a hand-edited spec exited $code, not 3: $(cat "$TP_BASE/claim.err")"
grep -qF "fingerprint changed" "$TP_BASE/claim.err" || fail "the refusal does not name the fingerprint"
grep -qF "sent back to shaping" "$TP_BASE/claim.err" || fail "the refusal does not say it sent the piece back"
grep -qF "next:" "$TP_BASE/claim.err" || fail "the refusal has no next: line"
[ "$(state_of)" = shaping ] || fail "the piece is not back in shaping"
ok "a spec edited by hand: the claim is refused and the piece goes back to shaping"

python3 - "$TP_ROOT" "$ROOT" "$FAKE_GH_STATE" <<'PY' || fail "the reason is not on the move, the issue and the spec"
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import evidence, spec
from loop.paths import Paths

record = evidence.read(Paths.for_project(Path(sys.argv[1])), 1)
move = [e for e in record if e["kind"] == "move"][-1]
assert move["move"] == 3 and move["from"] == "ready" and move["to"] == "shaping", move
assert "fingerprint changed" in move["reason"], move
S = json.load(open(sys.argv[3]))
issue = next(i for i in S["issues"] if i["number"] == 1)
assert "state:shaping" in issue["labels"] and "state:ready" not in issue["labels"], issue["labels"]
comments = " ".join(c if isinstance(c, str) else c["body"] for c in issue.get("comments", []))
assert "fingerprint changed" in comments, comments
assert any("fingerprint changed" in q for q in spec.parse(issue["body"]).open_questions), issue["body"]
PY
ok "the reason is on the move, in the record, in a comment and as an open question"

echo "claim-gate.sh: all checks passed"
