#!/usr/bin/env sh
# review-loop.sh: the review loop, end to end, through the real run script.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with every guard the pre-run
# check wants, the GitHub stand-in and the stand-in App. Real ready, claim and attempt gates, a
# real judge (pytest) and real Git decide each piece. The builder and the reviewer are the
# Claude stand-in: each replays a script, and the reviewer's script writes a scripted findings
# file where the real reviewer would.
#
# Run A: two pieces. Round one: a failing check for beta. The loop commits the reviewer's test
#   to the piece branch, beta goes back to building by move 8 with the test and a written
#   justification, the gate freezes the test in the bar, and the combined branch is rebuilt
#   under a fresh name with no revert. The second builder is told what was found and cannot
#   write the test. Round two is clean. The reviewer saw only the specs and the diff, carried no
#   GitHub credential, and could write only its findings file.
# Run B: a wrong spec. The piece goes to shaping by move 9 with needs-you, the others go ahead.
# Run C: a finding left after two rounds. Only that piece goes to shaping, no test is frozen in
#   the last round, and the combined branch is rebuilt without the piece.
# Run D: a spec edited by hand after ready. Its fingerprint is taken again before review, the
#   piece goes to shaping, and no reviewer reads the changed spec.
# Run E: a reviewer session that fails is a refusal and a problem, never a clean review.
# Run F: a builder that edits the reviewer's test fails the attempt as possible gaming.
#
# No network, no GitHub account, no model. Without pytest it prints a visible "skipped" line and
# does not count a pass. Run it alone: tests/review-loop.sh

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
  echo "skipped: pytest is not installed, so the review-loop check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Review loop checks:"
tp_new review-demo
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
mkdir -p "$TP_ROOT/.githooks" "$TP_ROOT/.agents/loop" "$TP_ROOT/.agents/guard" \
  "$TP_ROOT/docs" "$TP_ROOT/.github/workflows"
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
printf '{"language": "python", "allowedDomains": ["pypi.org", "files.pythonhosted.org"]}\n' \
  > "$TP_ROOT/.agents/loop/network-allowlist.json"

# --- the project: the records the docs commit must keep right ---------------------------------
cd "$TP_ROOT"
mkdir -p tests/acceptance
cat > tests/test_old.py <<'PY'
import pathlib


def test_old_behaviour_holds():
    """No two command files may hold the same command."""
    texts = [p.read_text() for p in sorted(pathlib.Path(".").glob("*/command.txt"))]
    assert len(texts) == len(set(texts)), "two command files hold the same command"
PY
cp "$KIT/templates/blocked-commands.md" .agents/guard/blocked-commands.md
cp "$KIT/templates/AGENTS.md" AGENTS.md
cp "$KIT/templates/CLAUDE.md" CLAUDE.md
cp "$KIT/templates/CHANGELOG.md" CHANGELOG.md
cp "$KIT/templates/docs-README.md" docs/README.md
sed 's/{{KIT_REF}}/main/' "$KIT/templates/checks.yml" > .github/workflows/checks.yml
AREAS="ra rb rc rd re rf rg rh ri"
{
  echo "# One line for each rule: a pattern, then the area. The last matching line wins."
  echo "docs/ project-records"
  echo "tests/ project-records"
  for area in ra rb rc rd re rf rg rh ri; do
    echo "$area/ $area"
  done
} > docs/area-map
python3 - "$KIT/templates/overview.md" docs/overview.md $AREAS <<'PY'
import sys
text = open(sys.argv[1]).read().rstrip("\n")
for area in sys.argv[3:]:
    text += f"\n| {area} | The {area} area | no | | `docs/{area}.md` |"
open(sys.argv[2], "w").write(text + "\n")
for area in sys.argv[3:]:
    open(f"docs/{area}.md", "w").write(f"# {area}\n\n")
PY
for area in $AREAS; do
  mkdir -p "$area"
  printf 'The %s area holds its files in this folder.\n' "$area" > "$area/README.md"
done
git add -A
git commit -q -m "Found the project: records, an old test and the area map"
git push -q origin main
(cd "$TP_ROOT" && python3 "$KIT/scripts/records-check.py" --json >/dev/null) \
  || fail "the founded project does not pass the records check, so the docs commit cannot"
ok "the founded project passes the records check"

# --- the pieces: issues, ready, with hidden cases kept outside git ----------------------------
tp_app
python3 "$GATE" labels --create --json >/dev/null || fail "gate.py labels failed"

cat > "$TP_BASE/make-spec.py" <<'PY'
import sys

# title name area judged-file held-fingerprint must-look new-area
title, name, area, judged, held, look, new_area = sys.argv[1:8]
print(title + ".\n")
print("<!-- spec:start version=1 -->")
print("Path: quick\n")
print("## Goal\nThe " + name + " works, and the edge case is handled.\n")
print("## Expected flow\nFL-1 The user uses the " + name + " and sees it work.\n")
print("## Edge cases\nEC-1 When the input is empty, then the " + name + " says so.\n")
print("## Changes to current behaviour\nAdded: The " + name + " command exists."
      + ((" New area: " + new_area) if new_area != "-" else "") + "\n")
print("## Must stay the same\nThe old behaviour still holds.\n"
      "Check: python3 -m pytest tests/test_old.py\n")
line = "Held-out cases: fingerprint " + held + "\n" if held != "-" else ""
print("## Judge\nKind: acceptance tests, a single test\n"
      "Command: python3 -m pytest tests/acceptance/test_" + name + ".py\n"
      "Proves: FL-1, EC-1\n" + line)
print("## Links\nRelies on: pytest\nTouches: " + area + "\n")
if look == "yes":
    print("## Decisions\n- must-look: the person wants to read this piece.")
print("<!-- spec:end -->")
PY

# make_piece <name> <area> <judged file> [look] [new-area]: capture, branch, judge,
# hidden cases, and ready. Prints the piece number, which is the issue number.
make_piece() {
  name=$1 area=$2 judged=$3 look=${4:-no} new_area=${5:--}
  python3 "$TP_BASE/make-spec.py" "Review $name" "$name" "$area" "$judged" - "$look" "$new_area" \
    > "$TP_BASE/spec-$name.md"
  url=$(gh issue create --title "Review $name" --body "$(cat "$TP_BASE/spec-$name.md")")
  n=${url##*/}
  python3 "$GATE" capture "$n" --json > "$TP_BASE/capture-$name.json" \
    || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  python3 "$GATE" branch "$n" --json >/dev/null || fail "gate.py branch $n failed"
  git checkout -q "piece-$n"
  mkdir -p tests/acceptance
  cat > "tests/acceptance/test_$name.py" <<PY
import os


def test_${name}_works_and_handles_the_edge():
    assert os.path.exists("$judged"), "FL-1 the $name works; EC-1 the empty input is handled"
PY
  git add "tests/acceptance/test_$name.py"
  git commit -q -m "Add the acceptance test of $name"
  git checkout -q main
  for id in FL-1 EC-1; do
    cat > "$TP_BASE/case-$name-$id.txt" <<PY
# held-out-path: tests/held_out/test_hidden_${name}_$(printf '%s' "$id" | tr -d '-').py
# HELDOUT-MARKER-$name-$id
import os


def test_hidden_${name}_$(printf '%s' "$id" | tr -d '-')():
    assert os.path.exists("$judged")
PY
  done
  python3 -m loop.heldout store --piece "$n" --case "FL-1=$TP_BASE/case-$name-FL-1.txt" \
    --case "EC-1=$TP_BASE/case-$name-EC-1.txt" --json > "$TP_BASE/held-$name.json" \
    || fail "the held-out store refused the cases of $name: $(cat "$TP_BASE/held-$name.json")"
  print_=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' \
    "$TP_BASE/held-$name.json")
  python3 "$TP_BASE/make-spec.py" "Review $name" "$name" "$area" "$judged" "$print_" "$look" \
    "$new_area" > "$TP_BASE/spec2-$name.md"
  python3 "$GATE" spec "$n" --body-file "$TP_BASE/spec2-$name.md" --json >/dev/null \
    || fail "gate.py spec failed for $name"
  tp_claude_script "$(python3 - "$KIT" <<'PY'
import json, sys
summary = "FL-1: test_works\nEC-1: test_edge"
print(json.dumps({"runs": [["python3", sys.argv[1] + "/scripts/handoff.py", "done",
                            "--summary", summary]]}))
PY
)"
  python3 "$GATE" move "$n" ready --json > "$TP_BASE/ready-$name.json" \
    2> "$TP_BASE/ready-$name.err" \
    || fail "move 2 was refused for $name: $(cat "$TP_BASE/ready-$name.err")"
  echo "$n"
}

N1=$(make_piece alpha ra ra/command.txt)
N2=$(make_piece beta rb rb/command.txt)
N3=$(make_piece gamma rc rc/command.txt)
N4=$(make_piece delta rd rd/command.txt)
N5=$(make_piece epsilon re re/command.txt)
N6=$(make_piece zeta rf rf/command.txt)
N7=$(make_piece eta rg rg/command.txt)
N8=$(make_piece theta rh rh/command.txt)
N9=$(make_piece iota ri ri/command.txt)
[ "$N1,$N2,$N3,$N4,$N5,$N6,$N7,$N8,$N9" = "1,2,3,4,5,6,7,8,9" ] \
  || fail "the pieces are not numbered 1 to 9: $N1 $N2 $N3 $N4 $N5 $N6 $N7 $N8 $N9"
ok "nine pieces are ready"

state_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
needs_you_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["needs_you"])'
}
moves_of() {
  python3 - "$1" <<'PY'
import json, sys
from pathlib import Path
from loop import moves
from loop.paths import Paths, find_project_root
paths = Paths.for_project(find_project_root(Path.cwd()))
piece = moves.read_piece(paths, int(sys.argv[1]))
print(json.dumps([{"move": e.get("move"), "reason": e.get("reason")} for e in piece.record
                  if e.get("kind") == "move"]))
PY
}
record_of() {
  # record_of <piece> <kind>: the entries of that kind in the piece's record, as JSON.
  python3 - "$1" "$2" <<'PY'
import json, sys
from pathlib import Path
from loop import moves
from loop.paths import Paths, find_project_root
paths = Paths.for_project(find_project_root(Path.cwd()))
piece = moves.read_piece(paths, int(sys.argv[1]))
print(json.dumps([e for e in piece.record if e.get("kind") == sys.argv[2]]))
PY
}
trailers_of() {
  git log --first-parent --reverse --format=%B "main..$1" | sed -n 's/^Piece: #\([0-9][0-9]*\)$/\1/p' | tr '\n' ' ' | sed 's/ $//'
}

# --- the stand-in builder and the stand-in reviewer: one script for each -----------------------
FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
sed 's/and the edge case is handled/and a surprise/' "$TP_BASE/spec2-eta.md" > "$TP_BASE/edited-eta.md"
python3 - "$FAKE" "$KIT" "$TP_BASE/edited-eta.md" <<'PY'
import json, sys
from pathlib import Path

fake, kit, edited = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
hand = kit + "/scripts/handoff.py"


def done(name, files, **more):
    script = {"files": files, "commits": [{"message": f"Build {name}", "paths": list(files)}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}.",
                        "--decision", f"Made {name} a plain file."]]}
    script.update(more)
    return script


def check(piece, path, needs, evidence):
    text = ("import os\n\n\ndef test_" + path.split("/")[-1][5:-3] + "():\n"
            f"    assert os.path.exists('{needs}'), 'the blank command is not handled'\n")
    return {"kind": "failing-check", "gap": "missing", "piece": piece, "evidence": evidence,
            "check": {"path": path, "text": text, "command": f"python3 -m pytest {path}"},
            "justification": f"Edge case EC-1 of piece {piece} says a blank command is "
                             f"handled, and {needs} is what handling it leaves."}


def reviewer(run, number, findings, **more):
    write = "import os, sys; open(os.environ['AI_LOOP_KIT_FINDINGS_FILE'], 'w').write(sys.argv[1])"
    script = {"runs": [["python3", "-c", write, json.dumps({"findings": findings})]]}
    script.update(more)
    (fake / f"review-{run}-main-r{number}.json").write_text(json.dumps(script))


note = {"kind": "worth-knowing", "gap": "unrequested", "piece": 1,
        "evidence": "Alpha adds an extra line to its command file that nobody asked for."}
scripts = {
    "1": done("alpha", {"ra/command.txt": "go alpha\n"}),
    "2": {"sequence": [done("beta", {"rb/command.txt": "go beta\n"}),
                       done("beta again", {"rb/handled.txt": "handled\n"})]},
    "3": done("gamma", {"rc/command.txt": "go gamma\n"}),
    "4": done("delta", {"rd/command.txt": "go delta\n"}),
    "5": done("epsilon", {"re/command.txt": "go epsilon\n"}),
    "6": {"sequence": [done("zeta", {"rf/command.txt": "go zeta\n"}),
                       done("zeta again", {"rf/handled.txt": "handled\n"})]},
    "7": done("eta", {"rg/command.txt": "go eta\n"}),
    # The trim of eta edits the issue by hand, after the gate judged the attempt.
    "7-trim": {"runs": [["gh", "issue", "edit", "7", "--body-file", edited],
                        ["python3", hand, "done", "--summary", "Nothing to trim."]]},
    "8": done("theta", {"rh/command.txt": "go theta\n"}),
    "9": {"sequence": [
        done("iota", {"ri/command.txt": "go iota\n"}),
        # The second builder edits the reviewer's test to make it pass.
        done("iota cheat", {"tests/test_review_iota.py": "def test_iota():\n    assert True\n"}),
        {"runs": [["sh", "-c", "git checkout $(git log --format=%H --diff-filter=A -1 -- "
                               "tests/test_review_iota.py) -- tests/test_review_iota.py"],
                  ["sh", "-c", "printf 'handled\\n' > ri/handled.txt"],
                  ["git", "add", "-A"],
                  ["git", "commit", "-q", "-m", "Handle the blank command"],
                  ["python3", hand, "done", "--summary", "Handled the blank command."]]}]},
    "trim": {"runs": [["python3", hand, "done", "--summary", "Nothing to trim."]]},
}
for name, script in scripts.items():
    (fake / f"{name}.json").write_text(json.dumps(script))

# Run A: a failing check for beta in round one, then a clean second round with a note.
reviewer("rev-a", 1, [check(2, "tests/test_review_beta.py", "rb/handled.txt",
                            "Beta takes a blank command and leaves no sign that it handled it."),
                      note])
reviewer("rev-a", 2, [note])
# Run B: the spec of delta is wrong in round one. The second round is clean.
reviewer("rev-b", 1, [{"kind": "wrong-spec", "gap": "contradicts", "piece": 4,
                       "evidence": "The flow and the edge case of delta cannot both hold."}])
reviewer("rev-b", 2, [])
# Run C: zeta fails a check in both rounds. No round is left after the second.
reviewer("rev-c", 1, [check(6, "tests/test_review_zeta.py", "rf/handled.txt",
                            "Zeta takes a blank command and leaves no sign that it handled it.")])
reviewer("rev-c", 2, [check(6, "tests/test_review_zeta_again.py", "rf/second.txt",
                            "Zeta also needs a second file, and the spec asks for it.")])
# Run D: nobody reads the spec of eta, so the reviewer never starts. No script is needed.
# Run E: the reviewer session fails.
reviewer("rev-e", 1, [], exit_code=1)
# Run F: iota fails a check in round one. The cheating builder is caught.
reviewer("rev-f", 1, [check(9, "tests/test_review_iota.py", "ri/handled.txt",
                            "Iota takes a blank command and leaves no sign that it handled it.")])
reviewer("rev-f", 2, [])
PY

# ==============================================================================================
# Run A: a failing check sends beta back with the new test in the frozen bar
# ==============================================================================================
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 1,2 --run rev-a --json > "$TP_BASE/runa.json" 2> "$TP_BASE/runa.err" \
  || { cat "$TP_BASE/runa.err" >&2; cat "$TP_BASE/runa.json" >&2; fail "run A failed"; }
RECORD_A="$TP_ROOT/.agents/runs/rev-a/run.json"
python3 - "$RECORD_A" <<'PY' || fail "the run record of run A is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
status = {n: p["status"] for n, p in d["pieces"].items()}
assert status == {"1": "built", "2": "built"}, status
assert d["status"] == "finished" and not d["problems"], (d["status"], d["problems"])
assert d["pieces"]["1"]["sessions"] == 1 and d["pieces"]["2"]["sessions"] == 2, d["pieces"]
track = d["review"]["tracks"]["main"]
assert track["status"] == "clean" and track["rounds"] == 2, track
assert d["review"]["verdicts"]["2"]["verdict"] == "clean", d["review"]["verdicts"]
assert d["review"]["verdicts"]["2"]["round"] == 2, d["review"]["verdicts"]
assert d["pieces"]["2"]["review_finding"], d["pieces"]["2"]
PY
ok "run A reviewed twice: the first round sent beta back, and the second round was clean"

python3 - "$(moves_of 2)" "$(record_of 2 review-test)" <<'PY' || fail "beta's record lacks move 8 or the review test"
import json, sys
eights = [m for m in json.loads(sys.argv[1]) if m["move"] == 8]
assert len(eights) == 1, eights
reason = eights[0]["reason"]
assert "Beta takes a blank command" in reason and "frozen bar" in reason, reason
assert "Edge case EC-1" in reason, reason
tests = json.loads(sys.argv[2])
assert len(tests) == 1, tests
t = tests[0]
assert t["path"] == "tests/test_review_beta.py" and "pytest" in t["command"], t
assert "EC-1" in t["justification"], t
PY
ok "beta went back to building by move 8, and the gate wrote the new test and its justification"

COMMIT=$(git log -1 --format=%H --diff-filter=A piece-2 -- tests/test_review_beta.py)
[ -n "$COMMIT" ] || fail "the piece branch of beta holds no commit of the review test"
git show "$COMMIT:tests/test_review_beta.py" | grep -q "rb/handled.txt" || fail "the test is not the reviewer's"
git log -1 --format=%B "$COMMIT" | grep -qi "co-authored" && fail "the review commit holds a model co-author line"
FIRST=$(git rev-list --reverse --first-parent main..piece-2 | head -1)
git show "$FIRST" --name-only --format= | grep -q "tests/acceptance/test_beta.py" \
  || fail "the first commit on the piece branch is no longer the judge commit"
ok "the review loop, not the builder, committed the reviewer's test to the piece branch"

SETTINGS_1="$TP_ROOT/.agents/runs/rev-a/settings-p2-a1.json"
SETTINGS_2="$TP_ROOT/.agents/runs/rev-a/settings-p2-a2.json"
grep -q "tests/test_review_beta.py" "$SETTINGS_1" && fail "the first builder was told about a test that did not exist"
grep -q "tests/test_review_beta.py" "$SETTINGS_2" \
  || fail "the settings of the second builder do not deny a write to the review test"
grep -q "Beta takes a blank command" "$TP_ROOT/.agents/runs/rev-a/brief-p2-a2.md" \
  || fail "the second builder of beta was not told what the reviewer found"
ok "the second builder cannot write the review test, and its brief says what the reviewer found"

[ "$(trailers_of combined-rev-a | tr ' ' '\n' | sort | tr '\n' ' ')" = "1 2 " ] \
  || fail "the first combined branch does not hold both pieces: $(trailers_of combined-rev-a)"
[ "$(trailers_of combined-rev-a-r2)" = "1 2" ] \
  || fail "the rebuilt branch holds $(trailers_of combined-rev-a-r2), not 1 2"
case "$(git log --format=%s main..combined-rev-a-r2)" in
  *[Rr]evert*) fail "the rebuild reverted something" ;;
esac
git ls-tree -r --name-only combined-rev-a-r2 | grep -qx "tests/test_review_beta.py" \
  || fail "the rebuilt branch does not hold the review test"
[ "$(git -C "$TP_BASE/origin.git" rev-parse combined-rev-a-r2)" = "$(git rev-parse combined-rev-a-r2)" ] \
  || fail "the rebuilt branch is not on origin at the checked commit"
git worktree list --porcelain | grep -q "review-rev-a" && fail "a scratch copy of the reviewer is left behind"
ok "the combined branch was rebuilt under a fresh name with no revert, and holds the review test"

python3 - "$RECORD_A" "$FAKE_CLAUDE_LOG" <<'PY' || fail "the reviewer's session is not isolated"
import json, sys
d = json.load(open(sys.argv[1]))
calls = [json.loads(line) for line in open(sys.argv[2])]
review = [c for c in calls if "/review-rev-a-main-r" in c["cwd"]]
assert len(review) == 2, [c["cwd"] for c in calls]
for call in review:
    argv = call["argv"]
    assert argv[:2] == ["-p", "--settings"] and len(argv) == 9, argv
    assert argv[3:] == ["--permission-mode", "dontAsk", "--output-format", "json",
                        "--permission-prompts", "none"], argv
    bad = [k for k in call["env_keys"] if k.startswith(("GH_", "GITHUB_"))]
    assert not bad, bad
    assert "AI_LOOP_KIT_FINDINGS_FILE" in call["env_keys"], call["env_keys"]
runs = d["review"]["tracks"]["main"]
notes = [n for n in d["integration"]["worth_knowing"] if n.get("source") == "review"]
assert len(notes) == 2 and all(n["piece"] == 1 for n in notes), notes
PY
BRIEF_R1="$TP_ROOT/.agents/runs/rev-a/brief-review-main-r1.md"
python3 - "$BRIEF_R1" <<'PY' || fail "the reviewer's brief holds more than the specs and the diff"
import re, sys
text = open(sys.argv[1]).read()
labels = re.findall(r"<<<DATA BEGIN (\S+) nonce=", text)
assert labels == ["spec", "diff"], labels
for forbidden in ("Made beta a plain file", "Built beta", "attempt", "hand-off file"):
    assert forbidden not in text.replace("hand-off", "").replace("attempt-log", ""), forbidden
assert "The beta works" in text and "go beta" in text, "the specs or the diff are missing"
PY
python3 - "$TP_ROOT/.agents/runs/rev-a/settings-review-main-r1.json" "$TP_ROOT/.agents/runs/rev-a" <<'PY' \
  || fail "the reviewer's settings let it write more than its findings file"
import json, os, sys
d = json.load(open(sys.argv[1]))
findings = os.path.realpath(sys.argv[2]) + "/findings-review-main-r1.json"
written = [os.path.realpath(p) for p in d["sandbox"]["filesystem"]["allowWrite"]]
assert written == [findings], d["sandbox"]["filesystem"]
edits = [r for r in d["permissions"]["allow"] if r.startswith(("Edit", "Write"))]
assert [os.path.realpath(r[5:-1]) for r in edits] == [findings] and len(edits) == 1, edits
assert "Bash" in d["permissions"]["deny"] and not [r for r in d["permissions"]["allow"] if r.startswith("Bash")]
PY
ok "the reviewer saw only the specs and the diff, carried no GitHub credential and may write one file"

[ "$(state_of 2)" = review ] && [ "$(state_of 1)" = review ] \
  || fail "a piece is not in review after a clean review: $(state_of 1) $(state_of 2)"
ok "both pieces wait in review with a clean verdict"

# ==============================================================================================
# Run B: a wrong spec sends delta to shaping, with needs-you, and gamma goes ahead
# ==============================================================================================
python3 "$RUN" --pieces 3,4 --run rev-b --json > "$TP_BASE/runb.json" 2> "$TP_BASE/runb.err" \
  || { cat "$TP_BASE/runb.err" >&2; cat "$TP_BASE/runb.json" >&2; fail "run B failed"; }
python3 - "$TP_ROOT/.agents/runs/rev-b/run.json" "$(moves_of 4)" <<'PY' || fail "run B went wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "finished" and not d["problems"], (d["status"], d["problems"])
assert d["pieces"]["3"]["status"] == "built", d["pieces"]["3"]
assert d["pieces"]["4"]["status"] == "sent-back", d["pieces"]["4"]
track = d["review"]["tracks"]["main"]
assert track["status"] == "clean" and track["rounds"] == 2 and track["removed"] == [4], track
assert d["review"]["verdicts"]["4"]["verdict"] == "shaping", d["review"]["verdicts"]
nines = [m for m in json.loads(sys.argv[2]) if m["move"] == 9]
assert len(nines) == 1 and "cannot both hold" in nines[0]["reason"], nines
PY
[ "$(state_of 4)" = shaping ] || fail "delta is $(state_of 4), not shaping"
[ "$(needs_you_of 4)" = True ] || fail "delta has no needs-you flag"
[ "$(state_of 3)" = review ] || fail "gamma is $(state_of 3), not review"
[ "$(trailers_of combined-rev-b-r2)" = "3" ] || fail "the rebuilt branch holds $(trailers_of combined-rev-b-r2), not 3"
git ls-tree -r --name-only combined-rev-b-r2 | grep -qx "rd/command.txt" && fail "delta is still on the rebuilt branch"
ok "a wrong spec sent only delta to shaping by move 9 with needs-you, and the branch was rebuilt without it"

# ==============================================================================================
# Run C: a finding left after two rounds sends only that piece to shaping
# ==============================================================================================
python3 "$RUN" --pieces 5,6 --run rev-c --json > "$TP_BASE/runc.json" 2> "$TP_BASE/runc.err" \
  || { cat "$TP_BASE/runc.err" >&2; cat "$TP_BASE/runc.json" >&2; fail "run C failed"; }
python3 - "$TP_ROOT/.agents/runs/rev-c/run.json" "$(moves_of 6)" <<'PY' || fail "run C went wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "finished" and not d["problems"], (d["status"], d["problems"])
assert d["pieces"]["5"]["status"] == "built" and d["pieces"]["6"]["status"] == "sent-back", d["pieces"]
track = d["review"]["tracks"]["main"]
assert track["status"] == "clean" and track["rounds"] == 2 and track["removed"] == [6], track
assert d["pieces"]["6"]["sessions"] == 2, d["pieces"]["6"]
moves = json.loads(sys.argv[2])
eights = [m for m in moves if m["move"] == 8]
nines = [m for m in moves if m["move"] == 9]
assert len(eights) == 1 and len(nines) == 1, moves
assert "2 rounds" in nines[0]["reason"] and "second file" in nines[0]["reason"], nines
PY
[ "$(state_of 6)" = shaping ] && [ "$(needs_you_of 6)" = True ] \
  || fail "zeta is $(state_of 6) with needs-you $(needs_you_of 6)"
[ "$(state_of 5)" = review ] || fail "epsilon is $(state_of 5), not review"
[ "$(trailers_of combined-rev-c-r3)" = "5" ] \
  || fail "the last rebuilt branch holds $(trailers_of combined-rev-c-r3), not 5"
git ls-tree -r --name-only piece-6 | grep -qx "tests/test_review_zeta_again.py" \
  && fail "a test was frozen in the last round, when no round was left"
git ls-tree -r --name-only piece-6 | grep -qx "tests/test_review_zeta.py" \
  || fail "the first round's test is missing from the piece branch"
[ "$(record_of 6 review-test | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" = 1 ] \
  || fail "zeta holds more than one review test"
ok "after two rounds the piece with a finding went to shaping with needs-you, and the others went ahead"

# ==============================================================================================
# Run D: a spec edited by hand is not read, and its piece goes to shaping
# ==============================================================================================
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 7 --run rev-d --json > "$TP_BASE/rund.json" 2> "$TP_BASE/rund.err" \
  || { cat "$TP_BASE/rund.err" >&2; cat "$TP_BASE/rund.json" >&2; fail "run D failed"; }
python3 - "$(moves_of 7)" <<'PY' || fail "the changed spec did not send eta to shaping"
import json, sys
nines = [m for m in json.loads(sys.argv[1]) if m["move"] == 9]
assert len(nines) == 1 and "fingerprint" in nines[0]["reason"], nines
assert "edited the spec" in nines[0]["reason"], nines
PY
grep -q "/review-rev-d" "$FAKE_CLAUDE_LOG" && fail "a reviewer read a spec that was edited by hand"
[ "$(state_of 7)" = shaping ] || fail "eta is $(state_of 7), not shaping"
ok "the fingerprint was taken again before review, and a spec edited by hand was not read"

# ==============================================================================================
# Run E: a reviewer session that fails is a refusal, never a clean review
# ==============================================================================================
set +e
python3 "$RUN" --pieces 8 --run rev-e --json > "$TP_BASE/rune.json" 2> "$TP_BASE/rune.err"
code=$?
set -e
[ "$code" -eq 1 ] || fail "run E exited $code, not 1: $(cat "$TP_BASE/rune.err")"
python3 - "$TP_ROOT/.agents/runs/rev-e/run.json" <<'PY' || fail "the failed reviewer was taken for a review"
import json, sys
d = json.load(open(sys.argv[1]))
track = d["review"]["tracks"]["main"]
assert track["status"] == "refused" and "exit code 1" in track["reason"], track
assert "reviewed" not in track, track
assert any("exit code 1" in p["text"] for p in d["problems"]), d["problems"]
assert not d["review"]["verdicts"], d["review"]["verdicts"]
PY
[ "$(state_of 8)" = review ] || fail "theta moved after a refused review: $(state_of 8)"
ok "a reviewer session that failed was a refusal, was recorded as a problem, and moved nothing"

# ==============================================================================================
# Run F: a builder that edits the reviewer's test fails the attempt
# ==============================================================================================
python3 "$RUN" --pieces 9 --run rev-f --json > "$TP_BASE/runf.json" 2> "$TP_BASE/runf.err" \
  || { cat "$TP_BASE/runf.err" >&2; cat "$TP_BASE/runf.json" >&2; fail "run F failed"; }
python3 - "$TP_ROOT/.agents/runs/rev-f/run.json" "$(record_of 9 attempt)" <<'PY' || fail "run F went wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "finished" and not d["problems"], (d["status"], d["problems"])
assert d["pieces"]["9"]["status"] == "built" and d["pieces"]["9"]["sessions"] == 3, d["pieces"]["9"]
assert d["review"]["tracks"]["main"]["status"] == "clean", d["review"]["tracks"]
attempts = json.loads(sys.argv[2])
failed = [a for a in attempts if a["result"] == "failed"]
assert len(failed) == 1 and failed[0]["possible_gaming"], attempts
texts = " ".join(f["text"] for f in failed[0]["findings"])
assert "tests/test_review_iota.py" in texts and "review" in texts, texts
assert [f["check"] for f in failed[0]["findings"]] == ["frozen-bar"], failed[0]["findings"]
PY
ok "the attempt that edited the reviewer's test failed as possible gaming, and the honest one passed"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the runs changed the project folder"
git worktree list --porcelain | grep -q "review-rev" && fail "a scratch copy of a reviewer is left behind"
ok "the runs left the project folder as it was, and no reviewer folder is left"

echo "Review loop checks passed."
