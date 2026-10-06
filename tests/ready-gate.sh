#!/usr/bin/env sh
# ready-gate.sh: take one piece to ready with the real ready gate.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with a failing
# acceptance test on its piece branch, two held-out cases in the gate-only store
# and a scripted spec. The two fresh test-list sessions run through the session
# code with the Claude stand-in, and the judge runs for real, on main, in a
# temporary checkout (pytest). Then the gate makes move 2.
#
# The test checks the move, the `Fails today:` line the gate writes, the
# fingerprint, the must-look reason the person's own mark gives, the judge run
# and the test lists in the piece record, and the two sessions the stand-in saw.
# A second piece with no held-out cases and no branch is refused with a `next:`
# line, and stays in shaping.
#
# No network, no GitHub account and no model. Without pytest it prints a visible
# "skipped" line and does not count a pass. Run it alone: tests/ready-gate.sh

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
  echo "skipped: pytest is not installed, so the ready-gate check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Ready gate checks:"
tp_new ready-demo
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
print("## Links\nTouches: menus\n")
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

# --- before the spec holds the fingerprint, the gate refuses -------------------------
set +e
python3 "$GATE" move 1 ready --json > "$TP_BASE/early.json" 2> "$TP_BASE/early.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "a spec with no held-out fingerprint exited $code, not 3"
grep -qF "next:" "$TP_BASE/early.err" || fail "the refusal has no next: line"
grep -qF "Held-out cases" "$TP_BASE/early.err" || fail "the refusal does not name the held-out line"
ok "a spec with no held-out fingerprint is refused (exit 3, with a next: line)"

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

python3 "$GATE" move 1 ready --json > "$TP_BASE/ready.json" 2> "$TP_BASE/ready.err" \
  || fail "move 2 was refused: $(cat "$TP_BASE/ready.err")"
ok "the gate takes the piece to ready"

python3 - "$TP_BASE/ready.json" "$TP_ROOT" <<'PY' || fail "the move's answer is wrong: $(cat "$TP_BASE/ready.json")"
import json, sys
r = json.load(open(sys.argv[1]))
assert r["to"] == "ready" and r["move"] == 2, r
assert r["must_look"] == ["the person's mark"], r
assert r.get("fingerprint"), r
PY
ok "the move answers with the person's mark as the must-look reason"

python3 "$GATE" report 1 --json > "$TP_BASE/report.json"
python3 - "$TP_BASE/report.json" <<'PY' || fail "the report is wrong: $(cat "$TP_BASE/report.json")"
import json, sys
row = json.load(open(sys.argv[1]))["pieces"][0]
assert row["state"] == "ready", row
assert row["must_look"] == ["the person's mark"], row
assert row["needs"] == [], row
assert row["fingerprint"], row
PY
ok "the report shows ready, the must-look reason, no need and a fingerprint"

python3 - "$TP_ROOT" "$TP_DATA" "$ROOT" <<'PY' || fail "the record is wrong"
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3] + "/kit/scripts")
from loop import evidence, fingerprint
from loop.paths import Paths

paths = Paths.for_project(Path(sys.argv[1]))
record = evidence.read(paths, 1)
kinds = [e["kind"] for e in record]
assert "test-lists" in kinds and kinds.count("judge-run") == 2, kinds
lists = next(e for e in record if e["kind"] == "test-lists")["lists"]
assert lists == [["EC-1", "FL-1"], ["EC-1", "FL-1"]], lists
runs = [e for e in record if e["kind"] == "judge-run"]
assert runs[0]["outcome"] == "failed" and runs[0]["runner"] == "pytest", runs[0]
assert sorted(runs[0]["failing_ids"]) == ["EC-1", "FL-1"], runs[0]
assert runs[0]["ref"] != "main", runs[0]  # the first commit on the piece branch
assert runs[1]["command"] == "python3 -m pytest tests/test_old.py", runs[1]
assert runs[1]["outcome"] == "passed", runs[1]
move = [e for e in record if e["kind"] == "move"][-1]
assert move["must_look"] == ["the person's mark"], move
body = [e for e in record if e["kind"] == "body"][-1]["text"]
assert "(written by the gate)" in body, body
prints = [e for e in record if e["kind"] == "fingerprint"]
assert prints, kinds
taken = prints[-1]["fingerprint"]
assert taken["fingerprint"] == fingerprint.take(body, taken["judge_commit"])["fingerprint"]
PY
ok "the record holds the judge runs, the test lists, the reason and the fingerprint"

[ -z "$(git status --porcelain -- . ':!.agents')" ] \
  || fail "the gate left the project folder changed"
[ "$(git worktree list | grep -c 'p1-list')" -eq 2 ] || fail "the two test-list worktrees are not there"
[ "$(wc -l < "$FAKE_CLAUDE_LOG" | tr -d ' ')" -eq 2 ] || fail "the stand-in did not see two sessions"
python3 - "$FAKE_CLAUDE_LOG" <<'PY' || fail "a test-list session held a GitHub credential or was resumed"
import json, sys
for line in open(sys.argv[1]):
    call = json.loads(line)
    bad = [k for k in call["env_keys"] if k.startswith(("GH_", "GITHUB_"))]
    assert not bad, bad
    assert "--resume" not in call["argv"] and "--continue" not in call["argv"], call["argv"]
    assert call["argv"][0] == "-p" and "--settings" in call["argv"], call["argv"]
PY
ok "two fresh sessions ran, with no GitHub credential and no resume"

# --- a piece with no branch and no held-out cases is refused -------------------------
python3 "$TP_BASE/make-spec.py" > "$TP_BASE/spec-2.md"
python3 "$GATE" capture --title "Close the menu" --body-file "$TP_BASE/spec-2.md" --type feature \
  --json > "$TP_BASE/capture2.json" || fail "the second capture failed"
set +e
python3 "$GATE" move 2 ready --json > /dev/null 2> "$TP_BASE/refused.err"
code=$?
set -e
[ "$code" -eq 3 ] || fail "the second piece exited $code, not 3"
grep -qF "piece-2" "$TP_BASE/refused.err" || fail "the refusal does not name the missing branch"
grep -qF "gate.py branch 2" "$TP_BASE/refused.err" || fail "the refusal does not name gate.py branch"
python3 "$GATE" report 2 --json | grep -qF '"state": "shaping"' \
  || fail "the refused piece left shaping"
ok "a piece with no branch is refused, and stays in shaping"

echo "ready-gate.sh: all checks passed"
