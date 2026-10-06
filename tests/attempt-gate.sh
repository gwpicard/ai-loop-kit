#!/usr/bin/env sh
# attempt-gate.sh: run three scripted attempts on one piece through the real attempt gate
# (move 5), and read the attempt log after each.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with the GitHub stand-in and
# the stand-in App. A piece goes to ready by the real ready gate and is claimed by the real
# claim gate, with a real judge (pytest). The builder's work is committed in the piece's
# worktree by this script, as the Claude stand-in would, and the real gate then judges it:
#
#   attempt 1 edits the bar: it makes the acceptance test pass by weakening it;
#   attempt 2 special-cases the visible test, and fails a held-out case;
#   attempt 3 is honest, and passes.
#
# After each attempt the test reads the attempt log in the piece record: the result, whether
# it was logged as possible gaming, the findings, and that no hidden case leaked into it. It
# also checks that each attempt's settings file denies a write to every bar file.
#
# No network, no GitHub account and no model. Without pytest it prints a visible "skipped"
# line and does not count a pass. Run it alone: tests/attempt-gate.sh

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
  echo "skipped: pytest is not installed, so the attempt-gate check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Attempt gate checks:"
tp_new attempt-demo
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
JUDGE=$(git rev-parse HEAD)
git checkout -q main

# --- the held-out cases: two hidden tests, each with the path the gate lays it at --------
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

# --- ready and the claim, both real --------------------------------------------------------
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
ok "the real ready gate and the real claim gate take the piece to building"

state_of() {
  python3 "$GATE" report 1 --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
[ "$(state_of)" = building ] || fail "the piece is not building"

# --- the piece's worktree, where the builder works ------------------------------------------
WT="$TP_ROOT/.agents/worktrees/1-menu"
git worktree add -q "$WT" piece-1
BASE=$(git rev-parse main)

# The attempt log, as the next builder's brief reads it, and what the record holds.
read_log() {
  python3 - "$TP_ROOT" "$ROOT" "$1" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import attempt_log, evidence
from loop.paths import Paths

record = evidence.read(Paths.for_project(Path(sys.argv[1])), 1)
print(json.dumps({"attempts": attempt_log.attempts(record), "text": attempt_log.render(record)}))
PY
}

# A move 5 that must fail as an attempt: exit 3, a next: line, the piece still building.
judge_failing() {
  set +e
  python3 "$GATE" move 1 review --json > "$TP_BASE/$1.json" 2> "$TP_BASE/$1.err"
  code=$?
  set -e
  [ "$code" -eq 3 ] || fail "$1: the failed attempt exited $code, not 3: $(cat "$TP_BASE/$1.err")"
  grep -qF "next:" "$TP_BASE/$1.err" || fail "$1: the refusal has no next: line"
  [ "$(state_of)" = building ] || fail "$1: a failed attempt moved the piece out of building"
  read_log "$1" > "$TP_BASE/$1-log.json"
}

# --- attempt 1: edit the bar -----------------------------------------------------------------
cat > "$WT/tests/acceptance/test_menu.py" <<'PY'
from menu import opens


def test_menu_opens_and_an_empty_menu_says_so():
    assert True
PY
git -C "$WT" add -A
git -C "$WT" commit -q -m "Make the acceptance test pass"
judge_failing attempt-1
grep -qF "possible gaming" "$TP_BASE/attempt-1.err" || fail "attempt 1 was not logged as possible gaming"
grep -qF "acceptance-check" "$TP_BASE/attempt-1.err" || fail "attempt 1 does not name the edited judge file"
python3 - "$TP_BASE/attempt-1-log.json" <<'PY' || fail "the attempt log after attempt 1 is wrong"
import json, sys
log = json.load(open(sys.argv[1]))
items = log["attempts"]
assert len(items) == 1, items
a = items[0]
assert (a["n"], a["result"], a["possible_gaming"]) == (1, "failed", True), a
assert [f["check"] for f in a["findings"]] == ["frozen-bar"], a
assert "tests/acceptance/test_menu.py" in a["findings"][0]["text"], a
assert "possible gaming" in log["text"], log["text"]
PY
ok "attempt 1 edited the bar: a failed attempt, logged as possible gaming, still building"

# --- the attempt's settings deny a write to every bar file -------------------------------------
python3 - "$TP_ROOT" "$ROOT" "$BASE" "$JUDGE" <<'PY' || fail "the attempt settings do not deny the bar files"
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
sys.path.insert(0, sys.argv[2] + "/tests/lib")
import importlib.util
from loop import bar, sessions
from loop.paths import Paths

spec = importlib.util.spec_from_file_location("pm", sys.argv[2] + "/tests/lib/permission-matcher.py")
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

root = Path(sys.argv[1])
paths = Paths.for_project(root, kit_folder=Path(sys.argv[2]) / "kit")
listed = bar.paths(root, sys.argv[3], ["tests/acceptance/test_menu.py"])
assert "tests/acceptance/test_menu.py" in listed and "tests/test_old.py" in listed, listed
worktree = root / ".agents" / "worktrees" / "1-menu"
files = []
for label in ("p1-a1", "p1-a2"):
    session = sessions.plan(paths, run="night-1", label=label, worktree=worktree,
                            brief="Do the piece.\n", bar_paths=listed)
    data = json.loads(session.settings_file.read_text())
    for name in listed:
        target = str(worktree / name)
        assert pm.file_denied(data["permissions"]["deny"], "Edit", target, str(worktree), str(root)), name
        assert target in data["sandbox"]["filesystem"]["denyWrite"], name
    files.append(session.settings_file)
assert files[0] != files[1], "two attempts share one settings file"
PY
ok "each attempt's settings file denies a write to every bar file, by rule and by sandbox"

# --- attempt 2: special-case the visible test, fail a held-out case ---------------------------
git -C "$WT" checkout -q -B piece-1 "$JUDGE"
cat > "$WT/menu.py" <<'PY'
def opens():
    return True
PY
git -C "$WT" add -A
git -C "$WT" commit -q -m "Make the visible test pass"
judge_failing attempt-2
grep -qF "held-out" "$TP_BASE/attempt-2.err" || fail "attempt 2 does not name the held-out check"
grep -qF "possible gaming" "$TP_BASE/attempt-2.err" || fail "attempt 2 was not logged as possible gaming"
python3 - "$TP_BASE/attempt-2-log.json" <<'PY' || fail "the attempt log after attempt 2 is wrong"
import json, sys
log = json.load(open(sys.argv[1]))
items = log["attempts"]
assert [a["n"] for a in items] == [1, 2], items
a = items[1]
assert (a["result"], a["possible_gaming"]) == ("failed", True), a
assert [f["check"] for f in a["findings"]] == ["held-out"], a
assert "1 of 2" in a["findings"][0]["text"], a
# The visible judge passed, so only the hidden cases failed. The log holds no hidden case.
text = json.dumps(log)
for secret in ("held_out", "test_hidden", "render", "No items"):
    assert secret not in text, secret
PY
ok "attempt 2 special-cased the visible test: the held-out case failed, logged as possible gaming"

# --- attempt 3: honest ---------------------------------------------------------------------------
git -C "$WT" checkout -q -B piece-1 "$JUDGE"
cat > "$WT/menu.py" <<'PY'
def opens():
    return True


def render(items):
    return "\n".join(items) if items else "No items"
PY
cat > "$WT/tests/test_menu_render.py" <<'PY'
from menu import render


def test_a_menu_with_items_lists_them():
    assert render(["tea", "milk"]) == "tea\nmilk"
PY
git -C "$WT" add -A
git -C "$WT" commit -q -m "Open the menu and render it"
python3 "$GATE" move 1 review --json > "$TP_BASE/attempt-3.json" 2> "$TP_BASE/attempt-3.err" \
  || fail "the honest attempt was refused: $(cat "$TP_BASE/attempt-3.err")"
[ "$(state_of)" = review ] || fail "the honest attempt did not move the piece to review"
read_log attempt-3 > "$TP_BASE/attempt-3-log.json"
python3 - "$TP_ROOT" "$ROOT" "$TP_BASE/attempt-3-log.json" <<'PY' || fail "the attempt log after attempt 3 is wrong"
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import evidence
from loop.paths import Paths

log = json.load(open(sys.argv[3]))
items = log["attempts"]
assert [(a["n"], a["result"]) for a in items] == [(1, "failed"), (2, "failed"), (3, "passed")], items
assert items[2]["findings"] == [] and not items[2]["possible_gaming"], items[2]
record = evidence.read(Paths.for_project(Path(sys.argv[1])), 1)
runs = [e for e in record if e["kind"] == "judge-run"]
assert any(e["command"].endswith("tests/test_old.py") and e["outcome"] == "passed" for e in runs), runs
move = [e for e in record if e["kind"] == "move"][-1]
assert (move["move"], move["from"], move["to"]) == (5, "building", "review"), move
PY
ok "attempt 3 was honest: it passed, and the piece moved to review by move 5"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the gate changed the project folder"
ok "the gate left the project folder as it was"

echo "attempt-gate.sh: all checks passed"
