#!/usr/bin/env sh
# merge-decision.sh: the pull request and the merge decision, end to end, through the real run
# script and the real gate.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with every guard the pre-run
# check wants, the GitHub stand-in and the stand-in App. Real ready, claim and attempt gates, a
# real judge (pytest) and real Git decide each piece. The builder and the reviewer are the
# Claude stand-in.
#
# Run A (not pre-approved): the pull request body lists each piece with its judge, held-out,
#   review and worth-knowing items, one Closes line for each, and no closing word anywhere else
#   (a reviewer note that says "fixes" a number is broken first). Nothing merges. Then main moves:
#   nothing merges until the branch is brought up to date and checked again (move 12), which
#   makes a new pull request. Then a comment names one piece: only that piece goes back to
#   building (move 13), the other goes back to review (move 12), the branch is rebuilt under a
#   fresh name with no revert, and a new pull request replaces the old one. Then a yes that names
#   the merge makes the gate merge the exact tested commit, with --match-head-commit.
# Run B (pre-approved, every condition met): the gate merges the exact tested commit in the run.
# Run C (pre-approved, a piece must be looked at): both pull requests wait for the person.
# Run D: an isolated piece and a dependent on it get a pull request each, the second based on the
#   branch of the first, and merge in order.
# Run E: a pull request past the policy's size limit is split, each part holds whole pieces.
# Run F: a pull request whose named doc did not change is refused.
# Run G: a merge the person makes after main moved is found by `gate.py check-main`, which the
#   session start hook reports and the pre-run check runs when no run is going.
# Run H: with no App, nothing is pushed or opened, and the next line names the commands.
#
# No network, no GitHub account, no model. Without pytest it prints a visible "skipped" line and
# does not count a pass. Run it alone: tests/merge-decision.sh

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
  echo "skipped: pytest is not installed, so the merge-decision check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Merge decision checks:"
tp_new merge-demo
# Keep the original scratch. The hosted artifact is a filtered copy of this
# rehearsal only, never the runner's whole temporary folder.
rehearsal_exit() {
  code=$?
  trap - EXIT
  if [ "$code" -ne 0 ]; then
    echo "Failed merge rehearsal scratch: $TP_BASE" >&2
    if [ -n "${MERGE_DECISION_ARTIFACT_DIR:-}" ]; then
      python3 "$ROOT/tests/lib/merge-rehearsal-evidence.py" "$TP_BASE" \
        "$MERGE_DECISION_ARTIFACT_DIR" \
        || echo "FAIL: could not prepare merge rehearsal evidence" >&2
    fi
  fi
  exit "$code"
}
trap rehearsal_exit EXIT
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
PRS="python3 -m loop.run.pull_request"
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
set_policy() {
  # set_policy <python statement over d>
  python3 - "$TP_ROOT/.agents/loop/policy.json" "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
exec(sys.argv[2])
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
}
set_policy 'd["test_command"] = "python3 -m pytest tests/test_old.py -q"'
printf '{"language": "python", "allowedDomains": ["pypi.org", "files.pythonhosted.org"]}\n' \
  > "$TP_ROOT/.agents/loop/network-allowlist.json"

# --- the project: the records the docs commit must keep right --------------------------------
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
AREAS="ra rb rc rd re rf rg rh ri rj rk rl rm sp"
{
  echo "# One line for each rule: a pattern, then the area. The last matching line wins."
  echo "docs/ project-records"
  echo "tests/ project-records"
  for area in $AREAS; do
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

# title name area judged-file held-fingerprint must-look docs
title, name, area, judged, held, look, docs = sys.argv[1:8]
print(title + ".\n")
print("<!-- spec:start version=1 -->")
print("Path: quick\n")
print("## Goal\nThe " + name + " works, and the edge case is handled.\n")
print("## Expected flow\nFL-1 The user uses the " + name + " and sees it work.\n")
print("## Edge cases\nEC-1 When the input is empty, then the " + name + " says so.\n")
print("## Changes to current behaviour\nAdded: The " + name + " command exists."
      + ((" Docs: " + docs + ".") if docs != "-" else "") + "\n")
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

# make_piece <name> <area> <judged file> [look] [docs]: capture, branch, judge, hidden cases, and
# ready. Prints the piece number, which is the issue number.
make_piece() {
  name=$1 area=$2 judged=$3 look=${4:-no} docs=${5:--}
  python3 "$TP_BASE/make-spec.py" "Merge $name" "$name" "$area" "$judged" - "$look" "$docs" \
    > "$TP_BASE/spec-$name.md"
  url=$(gh issue create --title "Merge $name" --body "$(cat "$TP_BASE/spec-$name.md")")
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
  python3 "$TP_BASE/make-spec.py" "Merge $name" "$name" "$area" "$judged" "$print_" "$look" \
    "$docs" > "$TP_BASE/spec2-$name.md"
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
N4=$(make_piece delta rd rd/command.txt yes)
N5=$(make_piece epsilon re re/command.txt)
N6=$(make_piece zeta rf rf/command.txt yes)
N7=$(make_piece eta rg rg/command.txt)
N8=$(make_piece theta rh rh/command.txt)
N9=$(make_piece iota ri ri/command.txt)
N10=$(make_piece kappa rj rj/command.txt)
N11=$(make_piece lambda rk rk/command.txt no docs/lambda-notes.md)
N12=$(make_piece mu rl rl/command.txt)
N13=$(make_piece nu rm rm/command.txt)
[ "$N1,$N2,$N3,$N4,$N5,$N6,$N7,$N8,$N9,$N10,$N11,$N12,$N13" = "1,2,3,4,5,6,7,8,9,10,11,12,13" ] \
  || fail "the pieces are not numbered 1 to 13"
gh api --method POST "repos/{owner}/{repo}/issues/7/dependencies/blocked_by" -F issue_id=6 \
  >/dev/null || fail "could not link piece 7 as blocked by piece 6"
ok "thirteen pieces are ready"

# The person's own terminal: standard input and output are a pseudo-terminal, with no agent-session
# marker. Only that, or the run script's own process, may merge.
as_person() {
  python3 "$ROOT/tests/lib/as-person.py" "$@"
}
state_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
trailers_of() {
  git log --first-parent --reverse --format=%B "main..$1" | sed -n 's/^Piece: #\([0-9][0-9]*\)$/\1/p' | tr '\n' ' ' | sed 's/ $//'
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
pulls_json() {
  # The pull requests the GitHub stand-in holds, as JSON.
  python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("pull_requests", [])))' \
    "$FAKE_GH_STATE"
}
pull() {
  # pull <number> <python expression over p>: one field of one pull request.
  pulls_json | python3 -c 'import json,sys; p = [x for x in json.load(sys.stdin) if x["number"] == int(sys.argv[1])][0]; print(eval(sys.argv[2]))' "$1" "$2"
}
run_state() {
  # run_state <run> <python expression over d>
  python3 -c 'import json,sys; d = json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
    "$TP_ROOT/.agents/runs/$1/run.json" "$2"
}
move_main() {
  # move_main <label>: the person's own work lands on main after the run's final check.
  printf '%s\n' "$1" > "$TP_ROOT/sp/$1.txt"
  git -C "$TP_ROOT" add -- "sp/$1.txt"
  git -C "$TP_ROOT" commit -q -m "Work on main: $1" -- "sp/$1.txt"
  git -C "$TP_ROOT" push -q origin main
}
sync_main() {
  # What the person does after a merge on GitHub: pull it.
  git -C "$TP_ROOT" fetch -q origin main
  git -C "$TP_ROOT" merge -q --ff-only origin/main
}

# --- the stand-in builder and the stand-in reviewer -----------------------------------------
FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
python3 - "$FAKE" "$KIT" "$TP_ROOT" <<'PY'
import json, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
hand = kit + "/scripts/handoff.py"


def done(name, files, **more):
    script = {"files": files, "commits": [{"message": f"Build {name}", "paths": list(files)}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}.",
                        "--decision", f"Made {name} a plain file."]]}
    script.update(more)
    return script


names = {"1": ("alpha", "ra"), "3": ("gamma", "rc"), "4": ("delta", "rd"), "5": ("epsilon", "re"),
         "6": ("zeta", "rf"), "7": ("eta", "rg"), "8": ("theta", "rh"), "9": ("iota", "ri"),
         "10": ("kappa", "rj"), "11": ("lambda", "rk"), "12": ("mu", "rl"), "13": ("nu", "rm")}
scripts = {n: done(name, {f"{area}/command.txt": f"go {name}\n"}) for n, (name, area) in
           names.items()}
# Nu takes the App away while it builds, so the run reaches the pull request step with no App.
local = sys.argv[3] + "/.agents/loop/local.json"
scripts["13"]["runs"].insert(0, ["mv", local, local + ".aside"])
scripts["2"] = {"sequence": [done("beta", {"rb/command.txt": "go beta\n"}),
                             done("beta again", {"rb/command.txt": "go beta, the second way\n"})]}
scripts["trim"] = {"runs": [["python3", hand, "done", "--summary", "Nothing to trim."]]}
# The fresh reviewer finds nothing, and says so in its findings file.
scripts["default"] = {"runs": [["python3", "-c", "import os; open(os.environ["
                                "'AI_LOOP_KIT_FINDINGS_FILE'], 'w').write('{\"findings\": []}')"]]}
for name, script in scripts.items():
    (fake / f"{name}.json").write_text(json.dumps(script))

# Run A's reviewer leaves a note about alpha. Its words would close a number on GitHub.
note = {"kind": "worth-knowing", "gap": "unrequested", "piece": 1,
        "evidence": "Alpha adds an extra line that nobody asked for, and also fixes #5 by "
                    "accident, so Closes #6 would be a mistake."}
write = "import os, sys; open(os.environ['AI_LOOP_KIT_FINDINGS_FILE'], 'w').write(sys.argv[1])"
script = {"runs": [["python3", "-c", write, json.dumps({"findings": [note]})]]}
(fake / "review-mrg-a-main-r1.json").write_text(json.dumps(script))
PY

# ==============================================================================================
# Run A: the pull request, a main that moved, a comment on one piece, and the merge
# ==============================================================================================
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 1,2 --run mrg-a --json > "$TP_BASE/runa.json" 2> "$TP_BASE/runa.err" \
  || { cat "$TP_BASE/runa.err" >&2; cat "$TP_BASE/runa.json" >&2; fail "run A failed"; }
[ "$(run_state mrg-a 'd["status"]')" = "finished" ] || fail "run A did not finish"
[ "$(run_state mrg-a 'len(d["problems"])')" = "0" ] \
  || fail "run A holds problems: $(run_state mrg-a 'd["problems"]')"
[ "$(state_of 1)" = "approval" ] && [ "$(state_of 2)" = "approval" ] \
  || fail "the pieces are not in approval after the pull request opened"
[ "$(pulls_json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" = "1" ] \
  || fail "run A did not open exactly one pull request"
ok "run A opened one pull request, and both pieces went to approval by move 10"

BODY_A="$TP_BASE/body-a.md"
pull 1 'p["body"]' > "$BODY_A"
TITLE_A=$(pull 1 'p["title"]')
for needle in "### Piece 1: Merge alpha" "### Piece 2: Merge beta" "Judge: \`python3 -m pytest tests/acceptance/test_alpha.py\`" \
  "green at the final combined check" "Held-out: the hidden cases ran at the final check and passed" \
  "Review: clean" "Alpha adds an extra line that nobody asked for" "Decided alone by" "Made alpha a plain file."; do
  grep -qF -- "$needle" "$BODY_A" || fail "the pull request body lacks: $needle"
done
FIRST=$(grep -n "### Piece 1" "$BODY_A" | cut -d: -f1)
SECOND=$(grep -n "### Piece 2" "$BODY_A" | cut -d: -f1)
NOTE_AT=$(grep -n "Alpha adds an extra line" "$BODY_A" | head -1 | cut -d: -f1)
[ "$NOTE_AT" -gt "$FIRST" ] && [ "$NOTE_AT" -lt "$SECOND" ] \
  || fail "the note about alpha does not sit beside piece 1"
ok "the body lists each piece with its judge, held-out result, review verdict and notes beside it"

[ "$(grep -c '^Closes #' "$BODY_A")" = "2" ] || fail "the body does not hold one Closes line for each piece"
grep -q '^Closes #1$' "$BODY_A" && grep -q '^Closes #2$' "$BODY_A" || fail "the Closes lines name the wrong issues"
python3 "$KIT/scripts/closing-words.py" --title "$TITLE_A" --body-file "$BODY_A" \
  --range "main..combined-mrg-a" --piece 1 --piece 2 --json > "$TP_BASE/words-a.json" \
  || fail "closing-words.py refuses the pull request: $(cat "$TP_BASE/words-a.json")"
grep -v '^Closes #' "$BODY_A" | grep -qiE '(fix(es|ed)?|close[sd]?|resolve[sd]?)[: ]+#[0-9]' \
  && fail "a closing word stands before a number outside the Closes lines"
ok "one Closes line for each piece, and no closing word anywhere else (a reviewer note was made safe)"

python3 - "$TP_ROOT/.agents/runs/mrg-a/run.json" <<'PY' || fail "the run record of run A holds no pull request"
import json, sys
d = json.load(open(sys.argv[1]))
entry = d["pull_requests"]["main"]
assert entry["state"] == "open" and entry["pull_request"] == 1, entry
assert entry["branch"] == "combined-mrg-a", entry
PY
HEAD_A=$(git rev-parse combined-mrg-a)
[ "$(pull 1 'p["state"]')" = "OPEN" ] || fail "the pull request is not open"
[ "$(pull 1 'p.get("match_head_commit")')" = "None" ] || fail "something merged before anyone said so"
ok "nothing merged: the person has not said so, and the run was not pre-approved"

# Main moves after the final check: nothing merges (move 12).
move_main moved-once
set +e
as_person python3 -m loop.run.pull_request merge --run mrg-a --said "Yes, merge it." --json \
  > "$TP_BASE/merge-a1.json" 2> "$TP_BASE/merge-a1.err"
set -e
python3 - "$TP_BASE/merge-a1.json" <<'PY' || fail "a merge went ahead although main had moved"
import json, sys
d = json.load(open(sys.argv[1]))
report = d["merged"][0]
assert report["status"] == "waits", report
assert "main moved after the final check" in report["why"] and "move 12" in report["why"], report
PY
[ "$(pull 1 'p["state"]')" = "OPEN" ] || fail "the pull request merged after main moved"
ok "main moved after the final check, so the gate refused the merge and named move 12"

python3 -m loop.run.pull_request refresh --run mrg-a --json > "$TP_BASE/refresh-a.json" \
  2> "$TP_BASE/refresh-a.err" || { cat "$TP_BASE/refresh-a.err" >&2; fail "refresh failed"; }
[ "$(state_of 1)" = "review" ] && [ "$(state_of 2)" = "review" ] \
  || fail "the pieces did not go back to review by move 12"
[ "$(pull 1 'p["state"]')" = "CLOSED" ] || fail "the old pull request was not closed"
python3 "$RUN" --run mrg-a --json > "$TP_BASE/runa2.json" 2> "$TP_BASE/runa2.err" \
  || { cat "$TP_BASE/runa2.err" >&2; cat "$TP_BASE/runa2.json" >&2; fail "run A again failed"; }
[ "$(pull 2 'p["state"]')" = "OPEN" ] || fail "no new pull request replaced the old one"
[ "$(pull 2 'p["head"]')" = "combined-mrg-a-r2" ] || fail "the new pull request is not from the rebuilt branch"
git ls-tree -r --name-only combined-mrg-a-r2 | grep -qx "sp/moved-once.txt" \
  || fail "the rebuilt branch does not hold the work on main"
[ "$(git rev-parse combined-mrg-a)" = "$HEAD_A" ] || fail "the old combined branch was changed"
case "$(git log --format=%s main..combined-mrg-a-r2)" in *[Rr]evert*) fail "the rebuild reverted something" ;; esac
[ "$(state_of 1)" = "approval" ] && [ "$(state_of 2)" = "approval" ] || fail "the pieces are not in approval again"
ok "the branch was brought up to date and checked again (move 12), and a new pull request replaced the old"

# A comment that names one piece sends back only that piece (move 13).
gh pr comment 2 --body "Piece 2 is wrong: the beta must say what it did." >/dev/null
python3 -m loop.run.pull_request sweep --run mrg-a --json > "$TP_BASE/sweep-a.json" \
  2> "$TP_BASE/sweep-a.err" || { cat "$TP_BASE/sweep-a.err" >&2; fail "sweep failed"; }
[ "$(state_of 2)" = "building" ] || fail "the named piece did not go back to building"
[ "$(state_of 1)" = "review" ] || fail "the other piece did not go back to review"
python3 - "$(moves_of 2)" "$(moves_of 1)" <<'PY' || fail "the gate's record lacks move 13 or move 12"
import json, sys
two, one = json.loads(sys.argv[1]), json.loads(sys.argv[2])
thirteen = [m for m in two if m["move"] == 13]
assert thirteen and "the beta must say what it did" in thirteen[-1]["reason"], two
twelve = [m for m in one if m["move"] == 12]
assert twelve and "Piece 2 was sent back" in twelve[-1]["reason"], one
assert not [m for m in one if m["move"] == 13], one
PY
[ "$(pull 2 'p["state"]')" = "CLOSED" ] || fail "the old pull request was not closed"
[ "$(trailers_of combined-mrg-a-r3)" = "1" ] || fail "the rebuilt branch holds $(trailers_of combined-mrg-a-r3), not only piece 1"
git ls-tree -r --name-only combined-mrg-a-r3 | grep -qx "rb/command.txt" && fail "the rebuilt branch still holds beta"
ok "a comment naming one piece sent back only that piece (move 13), and the rest was rebuilt (move 12)"

python3 "$RUN" --run mrg-a --json > "$TP_BASE/runa3.json" 2> "$TP_BASE/runa3.err" \
  || { cat "$TP_BASE/runa3.err" >&2; cat "$TP_BASE/runa3.json" >&2; fail "run A the third time failed"; }
[ "$(run_state mrg-a 'd["pieces"]["2"]["sessions"]')" = "2" ] || fail "the second builder of beta did not run"
[ "$(pull 3 'p["state"]')" = "OPEN" ] || fail "no pull request replaced the closed one"
[ "$(trailers_of combined-mrg-a-r3 | tr ' ' '\n' | sort | tr '\n' ' ')" = "1 2 " ] \
  || fail "the last combined branch holds $(trailers_of combined-mrg-a-r3)"
[ "$(pull 3 'p["head"]')" = "combined-mrg-a-r3" ] || fail "the third pull request is not from the last branch"
[ "$(run_state mrg-a 'd["pull_request"]')" = "3" ] \
  || fail "the run record does not name the run's pull request for the inbox: $(run_state mrg-a 'd.get("pull_request")')"
[ "$(state_of 1)" = "approval" ] && [ "$(state_of 2)" = "approval" ] || fail "the pieces are not in approval again"
ok "the rejected piece was built again, and a third pull request holds both pieces"

# An agent session cannot merge by any door, with a terminal or without one, whatever words it
# gives. The pull request stays open each time.
PR_OPEN=$(pull 3 'p["state"]')
[ "$PR_OPEN" = "OPEN" ] || fail "pull request 3 is not open before the agent doors are tried"
for door in cli gate; do
  for marker in "CLAUDECODE=1" "CLAUDE_CODE_ENTRYPOINT=cli"; do
    for terminal in "python3 $ROOT/tests/lib/as-person.py" ""; do
      set +e
      if [ "$door" = cli ]; then
        env "$marker" $terminal python3 -m loop.run.pull_request merge --run mrg-a \
          --said "Yes, merge the pull request." --json > "$TP_BASE/agent-door.json" 2> "$TP_BASE/agent-door.err"
      else
        env "$marker" $terminal python3 "$GATE" move 1 done --option merge=agent \
          --option said="Yes, merge the pull request." --json > "$TP_BASE/agent-door.json" 2> "$TP_BASE/agent-door.err"
      fi
      set -e
      [ "$(pull 3 'p["state"]')" = "OPEN" ] || fail "an agent session merged by the $door door ($marker, terminal: ${terminal:-none})"
      grep -q "only the person" "$TP_BASE/agent-door.json" "$TP_BASE/agent-door.err" \
        || fail "the $door door did not say that only the person merges ($marker, terminal: ${terminal:-none})"
    done
  done
done
# No agent marker and no terminal is no person either: a pipe, a hook or a script.
set +e
python3 -m loop.run.pull_request merge --run mrg-a --said "Yes, merge the pull request." --json \
  > "$TP_BASE/agent-door.json" 2> "$TP_BASE/agent-door.err"
python3 "$GATE" move 1 done --option merge=agent --option said="Yes, merge the pull request." --json \
  > "$TP_BASE/agent-door2.json" 2> "$TP_BASE/agent-door2.err"
python3 "$GATE" move 1 done --option merge=pre-approved --json \
  > "$TP_BASE/agent-door3.json" 2> "$TP_BASE/agent-door3.err"
set -e
[ "$(pull 3 'p["state"]')" = "OPEN" ] || fail "a call with no terminal merged"
grep -q "only the person" "$TP_BASE/agent-door.json" || fail "the pull request script did not refuse a call with no terminal"
grep -q "only the person" "$TP_BASE/agent-door2.json" "$TP_BASE/agent-door2.err" || fail "gate.py move done did not refuse a call with no terminal"
grep -q "only the run script" "$TP_BASE/agent-door3.json" "$TP_BASE/agent-door3.err" || fail "the pre-approved door was not refused for a command line"
ok "an agent session cannot merge by the pull request script or gate.py move, with a terminal or without; the pull request stays open"

# A yes that does not name the merge does not merge. A yes that names it does, on the tested commit.
as_person python3 -m loop.run.pull_request merge --run mrg-a --said "Yes, put it live." --json \
  > "$TP_BASE/merge-a2.json" 2>/dev/null || true
python3 - "$TP_BASE/merge-a2.json" <<'PY' || fail "a yes that does not name the merge went ahead"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["merged"][0]["status"] == "waits" and "do not name the merge" in d["merged"][0]["why"], d
PY
[ "$(pull 3 'p["state"]')" = "OPEN" ] || fail "the pull request merged on a yes that did not name the merge"
as_person python3 -m loop.run.pull_request merge --run mrg-a --said "Yes, merge the pull request." --json \
  > "$TP_BASE/merge-a3.json" 2> "$TP_BASE/merge-a3.err" \
  || { cat "$TP_BASE/merge-a3.err" >&2; cat "$TP_BASE/merge-a3.json" >&2; fail "the merge failed"; }
TESTED=$(git rev-parse combined-mrg-a-r3)
[ "$(pull 3 'p["state"]')" = "MERGED" ] || fail "the pull request did not merge"
[ "$(pull 3 'p["match_head_commit"]')" = "$TESTED" ] \
  || fail "the merge did not name the tested commit: $(pull 3 'p.get("match_head_commit")') is not $TESTED"
[ "$(state_of 1)" = "done" ] && [ "$(state_of 2)" = "done" ] || fail "the pieces are not done"
[ "$(gh issue view 1 --json state | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')" = "closed" ] \
  || fail "issue 1 is not closed"
ok "a yes that names the merge made the gate merge the exact tested commit, with --match-head-commit"
sync_main

# ==============================================================================================
# Run B: pre-approved, every condition met: the gate merges inside the run
# ==============================================================================================
# An agent cannot start this run alone: the guard hook asks, so the person's yes is the start.
# The hook sees the command line as an agent session would send it.
HOOK_JSON=$(RUN="$RUN" PWD_NOW="$PWD" python3 -c '
import json, os
print(json.dumps({"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
  "tool_input": {"command": "python3 " + os.environ["RUN"] + " --pieces 3 --run mrg-b --merge-pre-approved"},
  "cwd": os.environ["PWD_NOW"]}))')
HOOK_OUT=$(printf '%s' "$HOOK_JSON" | env CLAUDECODE=1 CLAUDE_CODE_ENTRYPOINT=cli python3 "$ROOT/kit/hooks/guard.py" 2>/dev/null) || true
echo "$HOOK_OUT" | grep -q '"permissionDecision": "ask"' \
  || fail "the guard hook did not ask before an agent started a pre-approved run: $HOOK_OUT"
ok "an agent session that starts a pre-approved run meets the guard's ask, so the person's yes starts it"
# With that yes given, run.py starts. The agent-session markers stay set: /run starts run.py from
# a Claude session. The merge is the run script's own process, so it goes ahead.
env CLAUDECODE=1 CLAUDE_CODE_ENTRYPOINT=cli python3 "$RUN" --pieces 3 --run mrg-b --merge-pre-approved --json > "$TP_BASE/runb.json" \
  2> "$TP_BASE/runb.err" || { cat "$TP_BASE/runb.err" >&2; cat "$TP_BASE/runb.json" >&2; fail "run B failed"; }
PRB=$(pulls_json | python3 -c 'import json,sys; print([p["number"] for p in json.load(sys.stdin) if p["head"] == "combined-mrg-b"][0])')
[ "$(pull "$PRB" 'p["state"]')" = "MERGED" ] || fail "the pre-approved run did not merge its pull request"
[ "$(pull "$PRB" 'p["match_head_commit"]')" = "$(git rev-parse combined-mrg-b)" ] \
  || fail "the pre-approved merge did not name the tested commit"
[ "$(state_of 3)" = "done" ] || fail "the piece of run B is not done"
[ "$(run_state mrg-b 'd["merge_pre_approved"]')" = "True" ] || fail "the run record does not say the run was pre-approved"
ok "a pre-approved run with every condition met merged the tested commit, with --match-head-commit"
sync_main

# ==============================================================================================
# Run C: pre-approved, but a piece must be looked at: both pull requests wait
# ==============================================================================================
python3 "$RUN" --pieces 4,5 --run mrg-c --merge-pre-approved --json > "$TP_BASE/runc.json" \
  2> "$TP_BASE/runc.err" || { cat "$TP_BASE/runc.err" >&2; cat "$TP_BASE/runc.json" >&2; fail "run C failed"; }
python3 - "$TP_ROOT/.agents/runs/mrg-c/run.json" <<'PY' || fail "run C merged or lost its pull requests"
import json, sys
d = json.load(open(sys.argv[1]))
prs = d["pull_requests"]
assert sorted(prs) == ["main", "piece-4"], sorted(prs)
for key, entry in prs.items():
    assert entry["state"] == "open", (key, entry)
    assert "must-look" in entry["waits"], (key, entry)
PY
[ "$(state_of 4)" = "approval" ] && [ "$(state_of 5)" = "approval" ] || fail "run C pieces are not in approval"
[ "$(pulls_json | python3 -c 'import json,sys; print(len([p for p in json.load(sys.stdin) if p["head"].startswith("combined-mrg-c") and p["state"] != "OPEN"]))')" = "0" ] \
  || fail "a pull request of run C is not open"
ok "a pre-approved run with a must-look piece merged nothing: both pull requests wait for the person"

# ==============================================================================================
# Run D: an isolated piece and its dependent, one pull request each, stacked
# ==============================================================================================
python3 "$RUN" --pieces 6,7 --run mrg-d --json > "$TP_BASE/rund.json" 2> "$TP_BASE/rund.err" \
  || { cat "$TP_BASE/rund.err" >&2; cat "$TP_BASE/rund.json" >&2; fail "run D failed"; }
python3 - "$TP_ROOT/.agents/runs/mrg-d/run.json" <<'PY' || fail "run D did not open a stacked pair of pull requests"
import json, sys
d = json.load(open(sys.argv[1]))
prs = d["pull_requests"]
assert sorted(prs) == ["piece-6-part-1", "piece-6-part-2"], sorted(prs)
one, two = prs["piece-6-part-1"], prs["piece-6-part-2"]
assert one["base"] == "main" and two["base"] == one["branch"], (one, two)
assert str(two["base_pr"]) == str(one["pull_request"]), (one, two)
assert one["pieces"] == "6" and two["pieces"] == "7", (one, two)
assert two["branch"] == "combined-mrg-d-piece-6", two
PY
PR6=$(run_state mrg-d 'd["pull_requests"]["piece-6-part-1"]["pull_request"]')
PR7=$(run_state mrg-d 'd["pull_requests"]["piece-6-part-2"]["pull_request"]')
[ "$(pull "$PR7" 'p["base"]')" = "$(pull "$PR6" 'p["head"]')" ] || fail "the dependent is not based on the branch of its dependency"
pull "$PR6" 'p["body"]' | grep -q '^Closes #6$' || fail "the isolated pull request does not close piece 6"
pull "$PR6" 'p["body"]' | grep -q '^Closes #7$' && fail "the isolated pull request closes the dependent"
pull "$PR7" 'p["body"]' | grep -q '^Closes #7$' || fail "the dependent's pull request does not close piece 7"
pull "$PR6" 'p["body"]' | grep -q "The person must look at this piece" || fail "the must-look reason is not in the body"
ok "an isolated piece got its own pull request, and the dependent's is based on its branch"

as_person python3 -m loop.run.pull_request merge --run mrg-d --said "Merge both pull requests." --json \
  > "$TP_BASE/merge-d.json" 2> "$TP_BASE/merge-d.err" \
  || { cat "$TP_BASE/merge-d.err" >&2; cat "$TP_BASE/merge-d.json" >&2; fail "the stack did not merge"; }
[ "$(pull "$PR6" 'p["state"]')" = "MERGED" ] && [ "$(pull "$PR7" 'p["state"]')" = "MERGED" ] || fail "the stack is not merged"
[ "$(pull "$PR7" 'p["base"]')" = "main" ] || fail "the second pull request was not retargeted to main"
[ "$(state_of 6)" = "done" ] && [ "$(state_of 7)" = "done" ] || fail "the stacked pieces are not done"
ok "the stack merged in order, the second pull request retargeted to main after its base merged"
sync_main

# ==============================================================================================
# Run E: a pull request past the size limit is split, each part holds whole pieces
# ==============================================================================================
set_policy 'd["pull_request_size_limit"] = 8'
python3 "$RUN" --pieces 8,9,10 --run mrg-e --json > "$TP_BASE/rune.json" 2> "$TP_BASE/rune.err" \
  || { cat "$TP_BASE/rune.err" >&2; cat "$TP_BASE/rune.json" >&2; fail "run E failed"; }
set_policy 'd["pull_request_size_limit"] = 800'
python3 - "$TP_ROOT/.agents/runs/mrg-e/run.json" "$FAKE_GH_STATE" <<'PY' || fail "the pull request was not split into whole pieces"
import json, re, sys
run = json.load(open(sys.argv[1]))
prs = sorted(run["pull_requests"].values(), key=lambda e: e["part"])
assert [e["part"] for e in prs] == [1, 2, 3], prs
held = []
state = json.load(open(sys.argv[2]))["pull_requests"]
mine = {p["head"]: p for p in state}
for entry in prs:
    body = mine[entry["branch"]]["body"]
    closes = [int(n) for n in re.findall(r"^Closes #(\d+)$", body, re.MULTILINE)]
    assert closes == [int(n) for n in entry["pieces"].split(",")], (closes, entry)
    held += closes
assert sorted(held) == [8, 9, 10], held
assert prs[0]["base"] == "main" and prs[1]["base"] == prs[0]["branch"] and prs[2]["base"] == prs[1]["branch"], prs
assert prs[2]["branch"] == "combined-mrg-e", prs
PY
[ "$(git rev-parse combined-mrg-e-part-1)" != "$(git rev-parse combined-mrg-e)" ] || fail "the first part is the whole branch"
git merge-base --is-ancestor combined-mrg-e-part-2 combined-mrg-e || fail "a part is not part of the tested branch"
[ "$(trailers_of combined-mrg-e-part-1)" = "8" ] || fail "part 1 does not hold only piece 8: $(trailers_of combined-mrg-e-part-1)"
ok "a pull request past the policy's size limit was split in three parts of whole pieces, each based on the one before"

# ==============================================================================================
# Run F: a pull request whose named doc did not change is refused
# ==============================================================================================
BEFORE=$(pulls_json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
set +e
python3 "$RUN" --pieces 11 --run mrg-f --json > "$TP_BASE/runf.json" 2> "$TP_BASE/runf.err"
code=$?
set -e
[ "$code" -eq 1 ] || fail "run F exited $code, not 1: $(cat "$TP_BASE/runf.err")"
[ "$(pulls_json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" = "$BEFORE" ] \
  || fail "a pull request was opened although its named doc did not change"
python3 - "$TP_ROOT/.agents/runs/mrg-f/run.json" <<'PY' || fail "the named doc was not refused"
import json, sys
d = json.load(open(sys.argv[1]))
text = " ".join(p["text"] for p in d["problems"])
assert "names the doc docs/lambda-notes.md" in text and "did not change it" in text, text
PY
[ "$(state_of 11)" = "review" ] || fail "the piece of run F left review"
ok "a pull request whose named doc did not change was refused, and nothing opened"

# ==============================================================================================
# Run G: a merge the person makes after main moved, found with no run going
# ==============================================================================================
python3 "$RUN" --pieces 12 --run mrg-g --json > "$TP_BASE/rung.json" 2> "$TP_BASE/rung.err" \
  || { cat "$TP_BASE/rung.err" >&2; cat "$TP_BASE/rung.json" >&2; fail "run G failed"; }
PRG=$(run_state mrg-g 'd["pull_requests"]["main"]["pull_request"]')
[ "$(state_of 12)" = "approval" ] || fail "the piece of run G is not in approval"
move_main moved-g
gh pr merge "$PRG" --merge >/dev/null || fail "the person's merge failed"
[ "$(pull "$PRG" 'p["state"]')" = "MERGED" ] || fail "the person's merge did not happen"
( cd "$TP_ROOT" && "$KIT/scripts/session-start.sh" ) > "$TP_BASE/session.txt"
grep -q "The person merged pull request $PRG after main moved" "$TP_BASE/session.txt" \
  || fail "the session start hook did not tell of the merge: $(cat "$TP_BASE/session.txt")"
[ "$(state_of 12)" = "approval" ] || fail "the hook changed a piece: it must only report"
ok "the session start hook told of a merge the person made after main moved, and changed nothing"
python3 "$KIT/scripts/pre-run-check.py" --project "$TP_ROOT" --json > "$TP_BASE/pre-g.json" \
  2> "$TP_BASE/pre-g.err" || { cat "$TP_BASE/pre-g.err" >&2; cat "$TP_BASE/pre-g.json" >&2; fail "the pre-run check refused"; }
python3 - "$TP_BASE/pre-g.json" "$PRG" <<'PY' || fail "the pre-run check did not report the merge and the check on main"
import json, sys
d = json.load(open(sys.argv[1]))
text = " ".join(d["notices"])
assert f"the person merged pull request {sys.argv[2]} since the last run after main moved" in text, d
assert "the check on main: green" in text, d
PY
[ "$(state_of 12)" = "done" ] || fail "the pre-run check did not settle the merge by move 11"
python3 "$GATE" check-main --json > "$TP_BASE/check-g.json" || fail "check-main failed after the merge was settled"
python3 -c 'import json,sys; d = json.load(open(sys.argv[1])); assert d["merges"] == [] and d["unreadable"] == [], d' "$TP_BASE/check-g.json" \
  || fail "check-main finds the same merge twice"
sync_main
ok "a merge the person made after main moved was found by gate.py check-main, run by the pre-run check, and main was checked"

# ==============================================================================================
# Run H: with no App nothing is pushed or opened, and the next line names the commands
# ==============================================================================================
BEFORE=$(pulls_json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
# The remote looks like GitHub, so a push needs the App. (A folder as the remote takes a plain push.)
git remote set-url origin https://github.com/rehearsal/project.git
set +e
python3 "$RUN" --pieces 13 --run mrg-h --json > "$TP_BASE/runh.json" 2> "$TP_BASE/runh.err"
code=$?
set -e
git remote set-url origin "$TP_BASE/origin.git"
mv "$TP_ROOT/.agents/loop/local.json.aside" "$TP_ROOT/.agents/loop/local.json" \
  || fail "the builder did not take the App away, so the test proved nothing"
[ "$code" -eq 0 ] || fail "run H exited $code: $(cat "$TP_BASE/runh.err")"
[ "$(pulls_json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" = "$BEFORE" ] \
  || fail "a pull request was opened with no App"
git -C "$TP_BASE/origin.git" rev-parse -q --verify refs/heads/combined-mrg-h >/dev/null 2>&1 \
  && fail "a branch was pushed with no App"
python3 - "$TP_ROOT/.agents/runs/mrg-h/run.json" "$TP_BASE/runh.json" <<'PY' || fail "the run did not stop at the pull request step with the commands"
import json, os, sys
d = json.load(open(sys.argv[1]))
entry = d["pull_requests"]["main"]
assert entry["state"] == "waiting", entry
command = entry["next"]
assert "in their own terminal" in command, command
assert "git push origin combined-mrg-h" in command, command
assert "gh pr create --base main --head combined-mrg-h" in command, command
assert os.path.isfile(entry["body_file"]), entry
assert "Closes #1" "3" in open(entry["body_file"]).read()
out = json.load(open(sys.argv[2]))
assert "gh pr create --base main --head combined-mrg-h" in out["next"], out["next"]
PY
[ "$(state_of 13)" = "review" ] || fail "the piece did not wait in review"
ok "with no App nothing was pushed or opened, the run stopped with the exact push and pull request commands, and the piece waits"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the runs changed the project folder"
ok "the runs left the project folder as it was"

echo "Merge decision checks passed."
