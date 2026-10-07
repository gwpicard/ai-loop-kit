#!/usr/bin/env sh
# answers.sh: the person's answers, read from GitHub comments as the gate's App.
#
# The project is a throwaway one with the GitHub stand-in, the stand-in App credential and the
# Claude stand-in. A builder parks a piece with a question. The person answers in a comment, in the stand-in, and:
#
#   - during the run, a comment on the piece's issue and a comment on a pull request made
#     directly in the stand-in (the run's own pull request comes with the pull request piece)
#     each resume the parked piece, and the answer reaches the builder only inside the marked
#     data block of its brief. Nothing writes the answer into the spec while the run goes;
#   - after the run, a comment on the issue of a parked piece goes in through `gate.py answer`,
#     which writes it into the spec (the spec holds no open question for a builder's question, so
#     move 6 puts it there first); the piece goes back to ready; and the person is told in a
#     comment, made as the App.
#
# With no App, inbox.py reads nothing from GitHub: tests/unit/test_inbox.py checks that.
#
# Without pytest it prints a visible "skipped" line. Run it alone: tests/answers.sh

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
  echo "skipped: pytest is not installed, so the answers check did not run"
  exit 0
fi

. "$ROOT/tests/lib/throwaway-project.sh"

echo "Answers checks:"
RP_NAME=answers-demo
PIECES="ask:ask.py:a1 hold:hold.py:a2 late:late.py:a3 font:font.py:a4"
. "$ROOT/tests/lib/run-project.sh"

FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
mkdir -p "$TP_BASE/tmp"
TMPDIR="$TP_BASE/tmp"
PATH="$TP_BIN:$FAKE_COMPUTER:$PATH"
export PATH TMPDIR
unset FAKE_COMPUTER_POWER FAKE_COMPUTER_SLEEP FAKE_COMPUTER_FREE_MB FAKE_COMPUTER_DISK_GB \
  FAKE_CLAUDE_VERSION

# --- four pieces, each from an issue, with the App on ---------------------------------------
tp_app
python3 "$GATE" labels --create --json >/dev/null || fail "gate.py labels failed"
for item in $PIECES; do
  name=${item%%:*}; rest=${item#*:}; file=${rest%%:*}; area=${rest#*:}
  num=$(make_piece "$name" "$file" "$area" issue) || fail "the piece $name could not be made"
  eval "P_$name=$num"
done
unset FAKE_CLAUDE_SCRIPT
[ "$P_ask,$P_hold,$P_late,$P_font" = "1,2,3,4" ] || fail "the pieces are not 1 to 4"
for n in 1 2 3 4; do
  [ "$(state_of $n)" = ready ] || fail "piece $n is not ready"
done
ok "four pieces, each with an issue, are ready"

FAKE="$TP_BASE/fake-claude"
mkdir -p "$FAKE"
FAKE_CLAUDE_DIR="$FAKE"
export FAKE_CLAUDE_DIR
python3 - "$FAKE" "$KIT" <<'PY'
import json, sys
from pathlib import Path

fake, kit = Path(sys.argv[1]), sys.argv[2]
hand = kit + "/scripts/handoff.py"


def done(name, file, **more):
    body = f'def {name}():\n    return "{name} ok"\n'
    script = {"files": {file: body}, "commits": [{"message": f"Build {name}", "paths": [file]}],
              "runs": [["python3", hand, "done", "--summary", f"Built {name}."]]}
    script.update(more)
    return script


def asks(question, **more):
    return {"runs": [["python3", hand, "needs-the-person", "--question", question]], **more}


scripts = {
    "1": {"sequence": [asks("Which colour should it be?", sleep=0.3), done("ask", "ask.py")]},
    # A piece that keeps the run alive while the answers come in.
    "2": done("hold", "hold.py", sleep=40),
    "3": asks("What size is it?", sleep=0.3),
    "4": {"sequence": [asks("Which font should it use?", sleep=0.3), done("font", "font.py")]},
    "trim": {"runs": [["python3", hand, "done", "--summary", "Nothing to trim."]]},
    "default": {"runs": [["python3", "-c", "import os; open(os.environ['AI_LOOP_KIT_FINDINGS_FILE'], "
                                           "'w').write('{\"findings\": []}')"]]},
}
for number, body in scripts.items():
    (fake / f"{number}.json").write_text(json.dumps(body))
PY

runs="$TP_ROOT/.agents/runs"
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
held() {
  python3 - "$runs/$1/run.json" "$2" <<'PY' || fail "$3"
import json, sys
d = json.load(open(sys.argv[1]))
assert eval(sys.argv[2]), (sys.argv[2], d)
PY
}
# comment <issue-or-pull-request number> <text>: the person writes a comment in the stand-in.
comment() {
  gh api -X POST "repos/{owner}/{repo}/issues/$1/comments" -f body="$2" >/dev/null \
    || fail "the stand-in refused the comment on #$1"
}
body_of_issue() {
  python3 - "$FAKE_GH_STATE" "$1" <<'PY'
import json, sys
state = json.load(open(sys.argv[1]))
issue = next(i for i in state["issues"] if str(i["number"]) == sys.argv[2])
print(issue["body"])
PY
}

# --- during the run: a comment on the issue, and a comment on a pull request --------------------
# Pull requests made directly in the stand-in. The numbers of pull requests and issues are kept
# apart there, so the sixth is the first that no issue shares.
for _ in 1 2 3 4 5 6; do
  gh pr create --title "A change" --body "Nothing." --head some-branch --base main >/dev/null \
    || fail "the stand-in refused a pull request"
done
PULL=6
mkdir -p "$runs"
python3 - "$TP_ROOT" "$PULL" <<'PY'
import sys
from pathlib import Path

from loop.paths import Paths
from loop.run import record

paths = Paths.for_project(Path(sys.argv[1]))
run = record.RunRecord.create(paths, "ans-1", [1, 2, 4], attended=True, merge_pre_approved=False)
run.data["pull_request"] = int(sys.argv[2])  # the run's own pull request comes with the next piece
run.save()
PY
BODY_BEFORE=$(body_of_issue "$P_ask")
AI_LOOP_KIT_INBOX_POLL=1
export AI_LOOP_KIT_INBOX_POLL
python3 "$RUN" --run ans-1 --json > "$TP_BASE/ans1.json" 2> "$TP_BASE/ans1.err" &
RUN_PID=$!
poll 90 'd["pieces"]["'"$P_ask"'"]["status"] == "parked-needs-person" and d["pieces"]["'"$P_font"'"]["status"] == "parked-needs-person" and d.get("inbox", {}).get("pull_after") is not None' \
  "$runs/ans-1/run.json" \
  || { cat "$TP_BASE/ans1.err" >&2; fail "the pieces did not park, or the inbox did not read the pull request"; }
kill -0 "$RUN_PID" 2>/dev/null || fail "the run ended while two pieces were parked"
comment "$P_ask" "Make it blue, please."
comment "$PULL" "piece $P_font: Garamond"
poll 60 'd["pieces"]["'"$P_ask"'"]["status"] in ("building", "built") and d["pieces"]["'"$P_font"'"]["status"] in ("building", "built")' \
  "$runs/ans-1/run.json" || fail "the answers did not resume the parked pieces"
ok "an answer in a comment on the issue, and one on the pull request, resumed the parked pieces"
poll 90 'd["pieces"]["'"$P_ask"'"]["status"] == "built" and d["pieces"]["'"$P_font"'"]["status"] == "built"' \
  "$runs/ans-1/run.json" || { cat "$TP_BASE/ans1.err" >&2; fail "the resumed pieces did not finish"; }
kill -TERM "$RUN_PID"  # the run script this test started, by its own number: the hold piece sleeps
set +e
wait "$RUN_PID"
set -e

# The answer reached the builder inside a marked data block, and never outside it.
python3 - "$runs/ans-1" "$ROOT" <<'PY' || fail "the answer is not inside a data block of the brief"
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2] + "/kit/scripts")
from loop import sessions

run = Path(sys.argv[1])
for label, words in (("p1-a2", "Make it blue, please."), ("p4-a2", "Garamond")):
    brief = (run / f"brief-{label}.md").read_text()
    assert words in brief, (label, "the answer is not in the brief")
    assert words not in sessions.outside_the_blocks(brief), (label, "the answer is outside a block")
    assert any(words in text for _name, text in sessions.parse_blocks(brief)), label
PY
[ "$(body_of_issue "$P_ask")" = "$BODY_BEFORE" ] \
  || fail "something other than the gate changed the spec of the piece while the run went"
held ans-1 'd["pieces"]["'"$P_ask"'"]["answer"]["text"] == "Make it blue, please."' "the answer is not in the run record"
held ans-1 'd["pieces"]["'"$P_font"'"]["answer"]["source"].startswith("a comment on the pull request 6")' \
  "the record does not say the answer came from the pull request"
ok "the answers reached the builders as data in a marked block, and the spec was not touched"

# --- after the run: the answer goes in through the gate, to ready, and the person is told -------
python3 "$RUN" --pieces "$P_late" --run ans-2 --json > "$TP_BASE/ans2.json" 2> "$TP_BASE/ans2.err" \
  || { cat "$TP_BASE/ans2.err" >&2; fail "the run with a piece that waits failed"; }
held ans-2 'd["status"] == "finished" and d["pieces"]["'"$P_late"'"]["status"] == "parked-needs-person"' \
  "the piece is not parked when the run ends"
[ "$(state_of "$P_late")" = building ] || fail "the parked piece is not inside building"
comment "$P_late" "A size of 4, please."
# The ready gate asks for two test lists, so the stand-in builder writes them.
tp_claude_script "$(python3 - "$KIT" <<'PY'
import json, sys
print(json.dumps({"runs": [["python3", sys.argv[1] + "/scripts/handoff.py", "done", "--summary",
                            "FL-1: test_works\nEC-1: test_edge"]]}))
PY
)"
python3 "$KIT/scripts/loop/run/inbox.py" --run ans-2 --project "$TP_ROOT" --json \
  > "$TP_BASE/inbox.json" 2> "$TP_BASE/inbox.err" \
  || { cat "$TP_BASE/inbox.err" >&2; cat "$TP_BASE/inbox.json" >&2; fail "inbox.py failed after the run"; }
[ "$(state_of "$P_late")" = ready ] || fail "the piece is not back in ready"
python3 "$GATE" report "$P_late" --json | python3 -c '
import json, sys
moves = json.load(sys.stdin)["pieces"][0]["moves"]
assert moves[-2:] == [6, 2], moves
' || fail "the piece did not go back to ready"
body_of_issue "$P_late" | grep -q "What size is it?.*A size of 4, please." \
  || fail "the gate did not write the answer under Decisions"
held ans-2 'd["pieces"]["'"$P_late"'"]["status"] == "returned-ready"' "the run record does not say the piece is back in ready"
python3 - "$FAKE_GH_STATE" "$P_late" <<'PY' || fail "the person was not told in a comment as the App"
import json, sys
state = json.load(open(sys.argv[1]))
issue = next(i for i in state["issues"] if str(i["number"]) == sys.argv[2])
told = [c for c in issue["comments"] if "Your answer is in" in c["body"]]
assert len(told) == 1, [c["body"][:60] for c in issue["comments"]]
assert told[0]["author"].endswith("[bot]"), told[0]
PY
grep -q "ready" "$runs/ans-2/summary.md" || fail "the summary does not say the piece is ready again"
ok "after the run the answer went in through gate.py answer, the piece went back to ready, and the person was told as the App"

# A second call finds nothing more to do, and changes nothing.
python3 "$KIT/scripts/loop/run/inbox.py" --run ans-2 --project "$TP_ROOT" --json \
  > "$TP_BASE/inbox2.json" 2>/dev/null || fail "the second inbox.py call failed"
grep -q '"answers": \[\]' "$TP_BASE/inbox2.json" || fail "the second call did something again"
ok "inbox.py called again does nothing more"

[ -z "$(git status --porcelain -- . ':!.agents')" ] || fail "the runs changed the project folder"
echo "Answers checks passed."
