#!/usr/bin/env sh
# integration-loop.sh: the integration loop, end to end, through the real run script.
#
# The project is a throwaway one (tests/lib/throwaway-project.sh) with every guard the pre-run
# check wants, the GitHub stand-in and the stand-in App. Real ready, claim and attempt gates, a
# real judge (pytest) and real Git decide each piece. Only the builder's session is the stand-in.
#
# Run A: three pieces. Alpha and beta pass alone and clash together: each writes a command file
#   under commands/, and the old test says no two command files may match. The clash is found at
#   the second trial join. The trial is thrown away, the combined branch never moves, beta goes
#   back to building with the clash written on it, the run carries on, and beta joins after its
#   rebuild. Then the docs commit, the final combined check with the held-out cases, the secret
#   scan and the push. The run is started again and joins nothing twice. A piece leaves after it
#   joined: the branch is rebuilt from main under a fresh name, with no revert and no force push.
# Run B: two pieces that change the same file. The merge conflict goes back the same way.
# Run C: a planted flaky test. The gate runs the same commit once more, and a different result
#   marks the check flaky: a worth-knowing item, never a pass.
# Run D: a dependent stacks on its dependency's branch, an isolated piece follows the same steps
#   on its own branch, and a piece that names a new area gets it in the overview.
# Run E: a piece that holds a secret. The secret scan refuses the push.
#
# No network, no GitHub account, no model. Without pytest it prints a visible "skipped" line and
# does not count a pass. Run it alone: tests/integration-loop.sh

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
  echo "skipped: pytest is not installed, so the integration-loop check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Integration loop checks:"
tp_new integ-demo
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
mkdir -p "$TP_BASE/tmp"
TMPDIR="$TP_BASE/tmp"
PATH="$TP_BIN:$FAKE_COMPUTER:$PATH"
FLAKE_STATE="$TP_BASE/flake-state"
export PATH TMPDIR FLAKE_STATE
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
AREAS="cmda cmdb cmdc shr fl stk1 stk2 iso sec"
{
  echo "# One line for each rule: a pattern, then the area. The last matching line wins."
  echo "docs/ project-records"
  echo "tests/ project-records"
  for area in cmda cmdb cmdc shr fl stk1 stk2 iso sec; do
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

# make_piece <name> <area> <judged file> [look] [new-area] [flaky]: capture, branch, judge,
# hidden cases, and ready. Prints the piece number, which is the issue number.
make_piece() {
  name=$1 area=$2 judged=$3 look=${4:-no} new_area=${5:--} flaky=${6:-no}
  python3 "$TP_BASE/make-spec.py" "Integ $name" "$name" "$area" "$judged" - "$look" "$new_area" \
    > "$TP_BASE/spec-$name.md"
  url=$(gh issue create --title "Integ $name" --body "$(cat "$TP_BASE/spec-$name.md")")
  n=${url##*/}
  python3 "$GATE" capture "$n" --json > "$TP_BASE/capture-$name.json" \
    || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  python3 "$GATE" branch "$n" --json >/dev/null || fail "gate.py branch $n failed"
  git checkout -q "piece-$n"
  mkdir -p tests/acceptance
  if [ "$flaky" = yes ]; then
    cat > "tests/acceptance/test_$name.py" <<PY
import os
import subprocess


def test_${name}_works_and_handles_the_edge():
    assert os.path.exists("$judged"), "FL-1 the $name works; EC-1 the empty input is handled"
    subject = subprocess.run(["git", "log", "-1", "--format=%s"], capture_output=True,
                             text=True).stdout
    state = os.environ["FLAKE_STATE"]
    if subject.startswith("Join piece") and not os.path.exists(state):
        open(state, "w").write("seen")
        assert False, "FL-1 the $name is flaky at a join, the first time"
PY
  else
    cat > "tests/acceptance/test_$name.py" <<PY
import os


def test_${name}_works_and_handles_the_edge():
    assert os.path.exists("$judged"), "FL-1 the $name works; EC-1 the empty input is handled"
PY
  fi
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
  python3 "$TP_BASE/make-spec.py" "Integ $name" "$name" "$area" "$judged" "$print_" "$look" \
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

N1=$(make_piece alpha cmda cmda/command.txt)
N2=$(make_piece beta cmdb cmdb/command.txt)
N3=$(make_piece gamma cmdc cmdc/command.txt)
N4=$(make_piece delta shr shr/shared.txt)
N5=$(make_piece epsilon shr shr/other.txt)
N6=$(make_piece zeta fl fl/flaky.txt no - yes)
N7=$(make_piece eta stk1 stk1/base.txt)
N8=$(make_piece theta stk2 stk2/dep.txt)
N9=$(make_piece iota iso iso/iso.txt yes)
N10=$(make_piece kappa widgets widgets/w.txt no widgets)
N11=$(make_piece lambda sec sec/secret.txt)
[ "$N1,$N2,$N3,$N4,$N5,$N6,$N7,$N8,$N9,$N10,$N11" = "1,2,3,4,5,6,7,8,9,10,11" ] \
  || fail "the pieces are not numbered 1 to 11: $N1 $N2 $N3 $N4 $N5 $N6 $N7 $N8 $N9 $N10 $N11"
ok "eleven pieces are ready"
gh api --method POST "repos/{owner}/{repo}/issues/8/dependencies/blocked_by" -F issue_id=7 \
  >/dev/null || fail "could not link piece 8 as blocked by piece 7"

state_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}

# --- the stand-in builder: one script for each piece ---------------------------------------
FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
SECRET_PARTS="AK IA ABCDEFGHIJKLMNOP"
export SECRET_PARTS
python3 - "$FAKE" "$KIT" <<'PY'
import json, os, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
hand = kit + "/scripts/handoff.py"


def done(name, files, **more):
    script = {"files": files, "commits": [{"message": f"Build {name}", "paths": list(files)}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}.",
                        "--decision", f"Made {name} a plain file."]]}
    script.update(more)
    return script


a, b, c = os.environ["SECRET_PARTS"].split()
scripts = {
    "1": done("alpha", {"cmda/command.txt": "go\n"}),
    # Beta writes the same command as alpha: it passes alone and clashes at the join.
    "2": {"sequence": [done("beta", {"cmdb/command.txt": "go\n"}, sleep=4),
                       done("beta", {"cmdb/command.txt": "go beta\n"})]},
    "3": done("gamma", {"cmdc/command.txt": "go gamma\n"}),
    "4": done("delta", {"shr/shared.txt": "four\n"}),
    # Epsilon first writes the same file as delta, then drops it.
    "5": {"sequence": [
        done("epsilon", {"shr/shared.txt": "five\n", "shr/other.txt": "five\n"}),
        {"runs": [["git", "rm", "-q", "shr/shared.txt"],
                  ["git", "commit", "-q", "-m", "Drop the shared file"],
                  ["python3", hand, "done", "--summary", "Dropped the shared file."]]}]},
    "6": done("zeta", {"fl/flaky.txt": "x\n"}),
    "7": done("eta", {"stk1/base.txt": "go base\n"}),
    # Theta can only be built when the work of eta is in its folder: it reads it.
    "8": {"runs": [["sh", "-c", "test -f stk1/base.txt && printf 'go on top\\n' > stk2/dep.txt"],
                   ["git", "add", "stk2/dep.txt"],
                   ["git", "commit", "-q", "-m", "Build theta"],
                   ["python3", hand, "done", "--summary", "Built theta on eta."]]},
    "9": done("iota", {"iso/iso.txt": "go alone\n"}),
    "10": {"runs": [["mkdir", "-p", "widgets"],
                    ["sh", "-c", "printf 'go widget\\n' > widgets/w.txt"],
                    ["sh", "-c", "printf '/widgets/ widgets\\n' >> docs/area-map"],
                    ["git", "add", "widgets/w.txt", "docs/area-map"],
                    ["git", "commit", "-q", "-m", "Build kappa"],
                    ["python3", hand, "done", "--summary", "Built kappa."]]},
    "11": done("lambda", {"sec/secret.txt": "key = " + a + b + c + "\n"}),
    "trim": {"runs": [["python3", hand, "done", "--summary", "Nothing to trim."]]},
    # The fresh reviewer (the review loop) finds nothing, and says so in its findings file.
    "default": {"runs": [["python3", "-c", "import os; open(os.environ['AI_LOOP_KIT_FINDINGS_FILE'], "
                                           "'w').write('{\"findings\": []}')"]]},
}
for name, script in scripts.items():
    (fake / f"{name}.json").write_text(json.dumps(script))
PY

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
trailers_of() {
  # trailers_of <branch>: the piece numbers joined on a combined branch, oldest first.
  git log --first-parent --reverse --format=%B "main..$1" | sed -n 's/^Piece: #\([0-9][0-9]*\)$/\1/p' | tr '\n' ' ' | sed 's/ $//'
}
reflog_of() {
  git reflog show "$1" --format=%gs
}

# ==============================================================================================
# Run A: a clash found at the second trial join
# ==============================================================================================
: > "$FAKE_CLAUDE_LOG"
python3 "$RUN" --pieces 1,2,3 --run int-a --json > "$TP_BASE/runa.json" 2> "$TP_BASE/runa.err" \
  || { cat "$TP_BASE/runa.err" >&2; cat "$TP_BASE/runa.json" >&2; fail "run A failed"; }
RECORD_A="$TP_ROOT/.agents/runs/int-a/run.json"
python3 - "$RECORD_A" <<'PY' || fail "the run record of run A is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
status = {n: p["status"] for n, p in d["pieces"].items()}
assert status == {"1": "built", "2": "built", "3": "built"}, status
assert d["status"] == "finished" and not d["problems"], (d["status"], d["problems"])
assert d["pieces"]["2"]["sessions"] == 2, d["pieces"]["2"]
assert d["pieces"]["1"]["sessions"] == 1 and d["pieces"]["3"]["sessions"] == 1, d["pieces"]
texts = [x["text"] for x in d["decisions"]]
assert any("back to building after a red trial join" in t for t in texts), texts
PY
ok "run A built three pieces, and the second builder session of beta is the only extra one"

[ "$(trailers_of combined-int-a | tr ' ' '\n' | sort | tr '\n' ' ')" = "1 2 3 " ] \
  || fail "the combined branch does not hold each piece once: $(trailers_of combined-int-a)"
[ "$(trailers_of combined-int-a | awk '{print $NF}')" = "2" ] \
  || fail "beta did not join last: $(trailers_of combined-int-a)"
ok "each piece joined the combined branch once, and beta joined last, after its rebuild"

python3 - "$(moves_of 2)" <<'PY' || fail "the gate's record of beta lacks move 8 with the clash"
import json, sys
found = json.loads(sys.argv[1])
eights = [m for m in found if m["move"] == 8]
assert len(eights) == 1, found
reason = eights[0]["reason"]
assert "piece 1" in reason and "tests/test_old.py" in reason, reason
assert "did not move" in reason and "thrown away" in reason, reason
PY
ok "the culprit went back to building by the gate's move 8, with the clash as the reason"

# The combined branch moved only on green: one cut, three joins and the docs commits.
REFLOG=$(reflog_of combined-int-a)
joins=$(printf '%s\n' "$REFLOG" | grep -c "join piece" || true)
[ "$joins" -eq 3 ] || fail "the combined branch moved $joins times for joins, not 3: $REFLOG"
[ "$(printf '%s\n' "$REFLOG" | grep -c "join piece 2")" -eq 1 ] \
  || fail "the clash moved the combined branch: $REFLOG"
log_subjects=$(git log --first-parent --format=%s main..combined-int-a)
case "$log_subjects" in
  *Revert*|*revert*) fail "the combined branch holds a revert: $log_subjects" ;;
esac
ok "the combined branch moved three times, once for each join, and the clash never moved it"

# The trial is a scratch copy: no branch, no folder is left.
git branch --format='%(refname:short)' | sort | tr '\n' ' ' > "$TP_BASE/branches.txt"
for stray in $(git branch --format='%(refname:short)'); do
  case "$stray" in
    main|piece-*|combined-*|list-*|trim-*) ;;
    *) fail "a stray branch is left: $stray" ;;
  esac
done
git worktree list --porcelain | grep -q "join-" && fail "a scratch copy of a trial is left behind"
[ ! -d "$TP_ROOT/.agents/runs/int-a/trial" ] || [ -z "$(ls "$TP_ROOT/.agents/runs/int-a/trial")" ] \
  || fail "the trial folder is not empty: $(ls "$TP_ROOT/.agents/runs/int-a/trial")"
ok "no trial branch or scratch copy is left"

# The clash reached the next builder's brief, inside the data block of the attempt log.
BRIEF1="$TP_ROOT/.agents/runs/int-a/brief-p2-a1.md"
BRIEF2="$TP_ROOT/.agents/runs/int-a/brief-p2-a2.md"
[ -f "$BRIEF1" ] && [ -f "$BRIEF2" ] || fail "beta has no two briefs in the run folder"
grep -q "sent this piece back after a trial join" "$BRIEF1" && fail "the first brief of beta holds a clash"
grep -q "sent this piece back after a trial join" "$BRIEF2" \
  || fail "the second builder of beta never saw the clash"
ok "the next builder of beta was told the clash"

# The docs commit: one entry for each piece, the records check passes, and the combined branch
# is checked out in a scratch folder to prove it.
CHECK_A="$TP_BASE/check-a"
git worktree add -q --detach "$CHECK_A" combined-int-a
for n in 1 2 3; do
  [ "$(grep -c "piece $n)" "$CHECK_A/CHANGELOG.md")" -eq 1 ] \
    || fail "CHANGELOG.md does not hold one entry for piece $n: $(cat "$CHECK_A/CHANGELOG.md")"
done
(cd "$CHECK_A" && python3 "$KIT/scripts/records-check.py" --closing 1 --closing 2 --closing 3 \
  --json >/dev/null) || fail "the records check fails on the combined branch"
grep -q "The alpha command exists." "$CHECK_A/docs/cmda.md" \
  || fail "the area doc holds no line from the piece's Added field"
[ ! -d "$CHECK_A/changes" ] || fail "changes/ still holds files after the fold"
git worktree remove "$CHECK_A"
ok "the docs commit wrote one changelog entry for each piece and the records check passes"

# The final combined check, and the held-out cases only there.
python3 - "$RECORD_A" <<'PY' || fail "the final check of run A is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
final = d["integration"]["final"]["main"]
assert final["status"] == "green", final
assert final["checked"]["held_out"] == 6 and final["checked"]["pieces"], final["checked"]
assert final["push"] == "pushed" and final["scanned"], final
PY
python3 - "$TP_ROOT" <<'PY' || fail "a held-out case reached the object store"
import subprocess, sys

root = sys.argv[1]
listing = subprocess.run(["git", "-C", root, "cat-file", "--batch-all-objects", "--batch-check"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
blobs = [line.split()[0] for line in listing if line.split()[1] == "blob"]
assert blobs, "the object store holds no blob, so nothing was searched"
for sha in blobs:
    text = subprocess.run(["git", "-C", root, "cat-file", "-p", sha], capture_output=True,
                          check=True).stdout.decode("utf-8", "replace")
    assert "HELDOUT-MARKER" not in text, f"blob {sha} holds a held-out case"
PY
[ "$(git -C "$TP_BASE/origin.git" rev-parse combined-int-a)" = "$(git rev-parse combined-int-a)" ] \
  || fail "the combined branch is not on origin at the checked commit"
ok "the final check ran six hidden cases, no case reached the object store, and the push was scanned"

# A resumed run reads the Piece trailers and joins nothing twice.
HEAD_A=$(git rev-parse combined-int-a)
CALLS_BEFORE=$(wc -l < "$FAKE_CLAUDE_LOG")
python3 "$RUN" --pieces 1,2,3 --run int-a --json > "$TP_BASE/runa2.json" 2> "$TP_BASE/runa2.err" \
  || { cat "$TP_BASE/runa2.err" >&2; fail "run A started again failed"; }
[ "$(git rev-parse combined-int-a)" = "$HEAD_A" ] || fail "a resumed run moved the combined branch"
[ "$(trailers_of combined-int-a | wc -w | tr -d ' ')" -eq 3 ] || fail "a resumed run joined a piece twice"
[ "$(wc -l < "$FAKE_CLAUDE_LOG")" -eq "$CALLS_BEFORE" ] || fail "a resumed run started a session"
ok "a resumed run joined nothing twice and started no session"

# A piece leaves after it joined: the branch is rebuilt from main under a fresh name.
HEAD_A=$(git rev-parse combined-int-a)
python3 -m loop.run.integrate leave --run int-a --piece 3 --reason "review sent it back" \
  > "$TP_BASE/leave.json" 2> "$TP_BASE/leave.err" \
  || { cat "$TP_BASE/leave.err" >&2; fail "the rebuild failed"; }
grep -q '"branch": "combined-int-a-r2"' "$TP_BASE/leave.json" \
  || fail "the rebuilt branch has no fresh name: $(cat "$TP_BASE/leave.json")"
[ "$(git rev-parse combined-int-a)" = "$HEAD_A" ] || fail "the old combined branch was changed"
[ "$(trailers_of combined-int-a-r2 | tr ' ' '\n' | sort | tr '\n' ' ')" = "1 2 " ] \
  || fail "the rebuilt branch does not hold pieces 1 and 2: $(trailers_of combined-int-a-r2)"
[ "$(git merge-base main combined-int-a-r2)" = "$(git rev-parse main)" ] \
  || fail "the rebuilt branch was not cut from main"
case "$(git log --format=%s main..combined-int-a-r2)" in
  *[Rr]evert*) fail "the rebuild reverted something" ;;
esac
python3 -m loop.run.integrate final --run int-a > "$TP_BASE/final-r2.json" 2> "$TP_BASE/final-r2.err" \
  || { cat "$TP_BASE/final-r2.err" >&2; fail "the final check of the rebuilt branch failed"; }
grep -q '"push": "pushed"' "$TP_BASE/final-r2.json" || fail "the rebuilt branch was not pushed"
[ "$(git -C "$TP_BASE/origin.git" rev-parse combined-int-a)" = "$HEAD_A" ] \
  || fail "the old branch on origin changed, so history was rewritten"
[ "$(git -C "$TP_BASE/origin.git" rev-parse combined-int-a-r2)" = "$(git rev-parse combined-int-a-r2)" ] \
  || fail "the rebuilt branch is not on origin"
ok "a piece that left after it joined caused a rebuild from main under a fresh name, with no revert and no force push"

# ==============================================================================================
# Run B: a merge conflict goes back the same way, and no agent resolves it
# ==============================================================================================
python3 "$RUN" --pieces 4,5 --run int-b --json > "$TP_BASE/runb.json" 2> "$TP_BASE/runb.err" \
  || { cat "$TP_BASE/runb.err" >&2; cat "$TP_BASE/runb.json" >&2; fail "run B failed"; }
python3 - "$(moves_of 5)" <<'PY' || fail "the conflict was not sent back by move 8 with the file named"
import json, sys
eights = [m for m in json.loads(sys.argv[1]) if m["move"] == 8]
assert len(eights) == 1, eights
reason = eights[0]["reason"]
assert "shr/shared.txt" in reason and "conflict" in reason and "piece 4" in reason, reason
assert "No agent resolves" in reason, reason
PY
[ "$(trailers_of combined-int-b | tr '\n' ' ')" = "4 5" ] \
  || fail "run B joined $(trailers_of combined-int-b)"
[ "$(reflog_of combined-int-b | grep -c 'join piece')" -eq 2 ] || fail "the conflict moved the branch"
ok "a merge conflict went back to building by move 8, nobody resolved it, and the piece joined after its rebuild"

# ==============================================================================================
# Run C: a planted flaky test is never a pass
# ==============================================================================================
rm -f "$FLAKE_STATE"
python3 "$RUN" --pieces 6 --run int-c --json > "$TP_BASE/runc.json" 2> "$TP_BASE/runc.err" || true
python3 - "$TP_ROOT/.agents/runs/int-c/run.json" <<'PY' || fail "the flaky trial was not kept apart from a pass"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["pieces"]["6"]["status"] == "waiting-for-person", d["pieces"]["6"]
items = d["integration"]["worth_knowing"]
assert len(items) == 1 and "flaky" in items[0]["text"], items
assert "test_zeta" in items[0]["check"], items
assert any("flaky" in n["text"] for n in d["notes"]), d["notes"]
assert "make the flaky check steady" in d["pieces"]["6"]["next"], d["pieces"]["6"]
PY
[ -z "$(trailers_of combined-int-c)" ] || fail "a flaky trial joined the piece"
[ "$(reflog_of combined-int-c | grep -c 'join piece')" -eq 0 ] || fail "a flaky trial moved the branch"
[ "$(state_of 6)" = review ] || fail "the flaky piece was blamed and moved: $(state_of 6)"
ok "a red that passed on the same commit was marked flaky: a worth-knowing item, no join, no blame"
python3 "$RUN" --pieces 6 --run int-c --json > "$TP_BASE/runc2.json" 2> "$TP_BASE/runc2.err" \
  || { cat "$TP_BASE/runc2.err" >&2; fail "run C started again failed"; }
[ "$(trailers_of combined-int-c)" = "6" ] || fail "the piece did not join after the flaky check settled"
ok "the piece joined when the same check ran green on a later trial"

# ==============================================================================================
# Run D: a stacked dependent, an isolated piece and a new area
# ==============================================================================================
python3 "$RUN" --pieces 7,8,9,10 --run int-d --json > "$TP_BASE/rund.json" 2> "$TP_BASE/rund.err" \
  || { cat "$TP_BASE/rund.err" >&2; cat "$TP_BASE/rund.json" >&2; fail "run D failed"; }
python3 - "$TP_ROOT/.agents/runs/int-d/run.json" <<'PY' || fail "the record of run D is wrong"
import json, sys
d = json.load(open(sys.argv[1]))
status = {n: p["status"] for n, p in d["pieces"].items()}
assert status == {"7": "built", "8": "built", "9": "built", "10": "built"}, status
assert d["pieces"]["8"]["stacked_on"] == [7] and d["pieces"]["8"]["stack_base"], d["pieces"]["8"]
assert not d["problems"], d["problems"]
tracks = d["integration"]["tracks"]
assert sorted(tracks) == ["main", "piece-9"], tracks
PY
[ "$(git log --first-parent --format=%s piece-8 | grep -c '^Stack on piece 7$')" -eq 1 ] \
  || fail "piece 8 was not stacked on piece 7 with a merge commit"
ok "a dependent was built on its dependency's branch, with a merge commit"
[ "$(trailers_of combined-int-d | tr ' ' '\n' | sort | tr '\n' ' ')" = "10 7 8 " ] \
  || fail "the main track of run D holds $(trailers_of combined-int-d)"
[ "$(trailers_of combined-int-d | awk '{print $1}')" != "8" ] || fail "the dependent joined before its dependency"
[ "$(trailers_of combined-int-d-piece-9)" = "9" ] || fail "the isolated piece has no branch of its own"
git ls-tree -r --name-only combined-int-d | grep -qx "iso/iso.txt" && fail "the isolated piece joined the shared branch"
git ls-tree -r --name-only combined-int-d-piece-9 | grep -qx "stk1/base.txt" && fail "the isolated branch holds other pieces"
ok "the dependent joined after its dependency, and the isolated piece followed the same steps on its own branch"
CHECK_D="$TP_BASE/check-d"
git worktree add -q --detach "$CHECK_D" combined-int-d
grep -q "^/widgets/ widgets$" "$CHECK_D/docs/area-map" || fail "the new area is not in the area map"
grep -q "^| widgets |" "$CHECK_D/docs/overview.md" || fail "the new area is not in the overview"
grep -q "The kappa command exists." "$CHECK_D/docs/widgets.md" || fail "the new area has no area doc"
(cd "$CHECK_D" && python3 "$KIT/scripts/records-check.py" --closing 7 --closing 8 --closing 10 \
  --json >/dev/null) || fail "the records check fails on the branch with the new area"
git worktree remove "$CHECK_D"
ok "a piece that named a new area got it in the area map, the overview and an area doc"

# ==============================================================================================
# Run E: the secret scan refuses a push
# ==============================================================================================
set +e
python3 "$RUN" --pieces 11 --run int-e --json > "$TP_BASE/rune.json" 2> "$TP_BASE/rune.err"
code=$?
set -e
[ "$code" -eq 1 ] || fail "run E exited $code, not 1: $(cat "$TP_BASE/rune.err")"
python3 - "$TP_ROOT/.agents/runs/int-e/run.json" <<'PY' || fail "the secret was not kept off the push"
import json, sys
d = json.load(open(sys.argv[1]))
final = d["integration"]["final"]["main"]
assert final["push"] == "refused" and "secret scan" in final["message"], final
assert final["status"] == "green", final
assert any("secret scan" in p["text"] for p in d["problems"]), d["problems"]
PY
git -C "$TP_BASE/origin.git" rev-parse -q --verify refs/heads/combined-int-e >/dev/null 2>&1 \
  && fail "the branch with a secret reached origin"
ok "the secret scan ran before the push and refused it, so the branch never reached origin"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the runs changed the project folder"
ok "the runs left the project folder as it was"

echo "Integration loop checks passed."
