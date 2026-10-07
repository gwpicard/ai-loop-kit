#!/usr/bin/env sh
# run-skill.sh: hold what a script can hold about the /run skill.
#
# The skill is a conversation and needs a model, so its scenario evals sit in
# kit/skills/run/evals/ and run by hand. This check holds the rest:
#
# - the skill text carries the exact start command: run.py under `caffeinate -i`,
#   the plugin folder variable in double quotes, `--pieces` for the first answer and
#   `--merge-pre-approved` for the second, with "not pre-approved" as the default;
# - the pre-run check comes before the run script, in the text and under caffeinate;
# - the skill builds nothing, edits nothing and stores no answer, and each rule
#   is guarded: the check fails on a copy that lost the rule;
# - the scripts behind the skill hold the rules a second time, in a founded
#   throwaway project: a missing guard refuses the check and the run script and
#   names the half of /setup; no ready piece starts nothing; a policy key for
#   pre-approval is refused; an unattended or pre-approved run needs the App.
#
# No network, no GitHub account and no model. Run it alone: tests/run-skill.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"

SKILL="$ROOT/kit/skills/run/SKILL.md"
PRC="$ROOT/kit/scripts/pre-run-check.py"
RUN="$ROOT/kit/scripts/run.py"
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

rs_init "Run skill checks"
rs_exists "$SKILL" "$PRC" "$RUN"

# --- the skill text -------------------------------------------------------------

START='caffeinate -i python3 "\$\{claude_plugin_root\}/scripts/run\.py" --run run-<date-time> --pieces'
CHECK='caffeinate -i python3 "\$\{claude_plugin_root\}/scripts/pre-run-check\.py" --pieces'
rs_rule "the start command: run.py under caffeinate, with the quoted plugin folder" "$START"
rs_rule "the pre-run check command, under caffeinate, with the same pieces" "$CHECK"
rs_rule "the pieces answer goes in as --pieces" 'first answer as `--pieces`'
rs_rule "the merge answer goes in as --merge-pre-approved" 'second as `--merge-pre-approved`'
rs_rule "the default is not pre-approved" '"not pre-approved" as the default'
rs_rule "the two questions are asked once" 'ask the two questions once'
rs_rule "the pre-run check runs before the run script" 'run the pre-run check before you start the run script'
rs_rule "a refusal starts nothing" 'points at `/shape`, and start nothing'
rs_rule "a refusal names the guard and the half of setup" 'names? the (missing )?guard and the half of `/setup`'
rs_rule "no ready piece is said in one line" 'no piece is ready\. say so in one line'
rs_rule "the skill only starts the script" 'only starts the run script'
rs_rule "the answer is never stored" 'never write (the|an) answer'
rs_rule "the stop for a build" 'never build a piece'
rs_rule "the run starts in the background" 'start the run script in the background'
rs_rule "the skill chooses the run name and passes --run" 'choose a run name.*--run run-<date-time>'
rs_rule "the step is done when the command is started and the name is known" 'done when: the command is started and you have its run name'
rs_rule "the run is unattended only on the person's word" 'add `--unattended` only when the person said nobody will watch'
rs_guard "$SKILL" "the shipped run skill"

# The pre-run check comes first in the file, and the run script after it.
python3 - "$SKILL" <<'PY' || rs_fail "the pre-run check does not come before the run script in the steps"
import sys
text = open(sys.argv[1], encoding="utf-8").read()
steps = text.split("## Steps", 1)[1].split("## Gotchas", 1)[0]
check = steps.find("pre-run-check.py")
start = steps.find("/scripts/run.py")
assert 0 <= check < start, (check, start)
PY
rs_ok "the pre-run check comes before the run script in the steps"

# The start command carries --run, and --unattended is absent from it by default.
START_LINE=$(grep -E 'caffeinate -i python3 .*scripts/run\.py' "$SKILL" | head -1)
case "$START_LINE" in *'--run run-<date-time>'*) ;; *) rs_fail "the start command does not carry --run run-<date-time>" ;; esac
rs_ok "the start command carries --run with a name the skill chooses"
case "$START_LINE" in *--unattended*) rs_fail "the start command carries --unattended by default" ;; esac
rs_ok "--unattended is absent from the start command by default"

# The second layer for "never build or edit": the frontmatter removes the edit tools.
python3 - "$SKILL" <<'PY' || rs_fail "the skill frontmatter does not remove the edit tools"
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
front = text.split("---", 2)[1]
m = re.search(r"^disallowed-tools:\s*(.+)$", front, re.M)
assert m, "no disallowed-tools line"
tools = set(re.split(r"[ ,]+", m.group(1).strip()))
assert {"Edit", "Write", "NotebookEdit"} <= tools, tools
allowed = re.search(r"^allowed-tools:\s*(.+)$", front, re.M)
if allowed:
    assert not re.search(r"\b(Edit|Write|NotebookEdit)\b", allowed.group(1)), allowed.group(1)
PY
rs_ok "the frontmatter removes Edit, Write and NotebookEdit while the skill runs, and allows none of them"

rs_require "the skill injects the gate's report" "$SKILL" 'gate\.py report --json --brief'
rs_require "the skill turns model invocation off" "$SKILL" 'disable-model-invocation: true'
rs_require_absent "the skill has no bare kit path to the run script" "$SKILL" '[ "]kit/scripts/run\.py'
rs_require_absent "the skill never calls gh" "$SKILL" 'gh (issue|pr|label|api)'

# The skill lint accepts the skills.
python3 "$ROOT/kit/scripts/check-skills.py" --json --glossary "$ROOT/kit/glossary.md" \
  > "$rs_dir/lint.out" 2>&1 || { cat "$rs_dir/lint.out"; rs_fail "check-skills refuses the skills"; }
rs_ok "check-skills accepts the skills under kit/skills/"

# --- the scripts behind the skill -------------------------------------------------

unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_PLUGIN_ROOT ANTHROPIC_API_KEY 2>/dev/null || true
. "$ROOT/tests/lib/throwaway-project.sh"

js() {
  printf '%s' "$1" | python3 -c 'import json,sys; d=json.load(sys.stdin); v=eval(sys.argv[1]); print(v if isinstance(v,str) else json.dumps(v,sort_keys=True))' "$2" 2>/dev/null
}

tp_new run-skill
KIT="$TP_BASE/plugin"
cp -R "$ROOT/kit" "$KIT"
mkdir -p "$TP_BASE/data-no-app" "$TP_BASE/tmp"
AI_LOOP_KIT_DATA="$TP_BASE/data-no-app"
PATH="$FAKE_COMPUTER:$PATH"
TMPDIR="$TP_BASE/tmp"
export AI_LOOP_KIT_DATA PATH TMPDIR
: > "$FAKE_GH_LOG"

(cd "$TP_ROOT" && python3 "$KIT/scripts/setup.py" --json found --test-command "sh -c 'exit 0'" \
  --billing-mode subscription --repo-visibility private --plan paid --language node) \
  > "$TP_BASE/found.out" 2> "$TP_BASE/found.err" || { cat "$TP_BASE/found.err" >&2; rs_fail "setup.py found failed"; }
# The policy gets a test command, so the check can show main green.
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
path = sys.argv[1]
body = json.load(open(path))
body["test_command"] = "sh -c 'exit 0'"
json.dump(body, open(path, "w"), indent=2)
PY
git -C "$TP_ROOT" add -A
git -C "$TP_ROOT" commit -q -m "Found the project"
git -C "$TP_ROOT" push -q origin main
CLAUDE_PLUGIN_ROOT="$KIT"
export CLAUDE_PLUGIN_ROOT

prc() {
  set +e
  (cd "$TP_ROOT" && python3 "$KIT/scripts/pre-run-check.py" --json "$@") > "$TP_BASE/prc.out" 2> "$TP_BASE/prc.err"
  PRC_CODE=$?
  set -e
}

prc --pieces 1
[ "$PRC_CODE" -eq 0 ] || { cat "$TP_BASE/prc.out" "$TP_BASE/prc.err" >&2; rs_fail "the pre-run check refused a founded project (got $PRC_CODE)"; }
rs_ok "the pre-run check passes an attended run in a founded project"

# Sleep is not held off: why the skill runs the check under caffeinate.
set +e
(cd "$TP_ROOT" && FAKE_COMPUTER_SLEEP=free python3 "$KIT/scripts/pre-run-check.py" --json) > "$TP_BASE/o" 2> "$TP_BASE/e"
CODE=$?
set -e
[ "$CODE" -eq 3 ] || rs_fail "the check passed with nothing holding the computer awake (got $CODE)"
grep -q 'caffeinate -i' "$TP_BASE/o" "$TP_BASE/e" || rs_fail "the sleep refusal does not name caffeinate"
rs_ok "a check with nothing holding the computer awake is refused, and the text names caffeinate"

# Refusal: the pre-push hook is missing (a guard of the first half).
mv "$TP_ROOT/.githooks/pre-push" "$TP_BASE/pre-push-kept"
prc
[ "$PRC_CODE" -eq 3 ] || rs_fail "a missing pre-push hook was not refused (got $PRC_CODE)"
[ "$(js "$(cat "$TP_BASE/prc.out")" '[r["guard"] for r in d["refusals"]]')" = '["pre-push-hook"]' ] \
  || { cat "$TP_BASE/prc.out" >&2; rs_fail "the refusal does not name the pre-push hook alone"; }
[ "$(js "$(cat "$TP_BASE/prc.out")" 'd["refusals"][0]["half"]')" = first ] || rs_fail "the refusal does not name the first half of /setup"
grep -q '^next:' "$TP_BASE/prc.err" || rs_fail "the refusal has no next: line"
rs_ok "a missing guard is refused: it names the guard and the first half of /setup"

# The run script holds the same rule a second time, and starts nothing.
set +e
(cd "$TP_ROOT" && python3 "$KIT/scripts/run.py" --json --pieces 1) > "$TP_BASE/o" 2> "$TP_BASE/e"
CODE=$?
set -e
[ "$CODE" -eq 3 ] || { cat "$TP_BASE/o" "$TP_BASE/e" >&2; rs_fail "the run script started with a guard missing (got $CODE)"; }
[ ! -d "$TP_ROOT/.agents/runs" ] || rs_fail "a refused run left a run record"
[ ! -s "$FAKE_CLAUDE_LOG" ] || rs_fail "a refused run started a builder session"
rs_ok "the run script refuses the same guard, leaves no run record and starts no builder"
mv "$TP_BASE/pre-push-kept" "$TP_ROOT/.githooks/pre-push"

# Edge: nothing is ready, so the run script says so and starts nothing.
set +e
(cd "$TP_ROOT" && python3 "$KIT/scripts/run.py" --json) > "$TP_BASE/o" 2> "$TP_BASE/e"
CODE=$?
set -e
[ "$CODE" -eq 3 ] || { cat "$TP_BASE/o" "$TP_BASE/e" >&2; rs_fail "a run with no ready piece did not exit 3 (got $CODE)"; }
grep -q 'nothing to run' "$TP_BASE/o" "$TP_BASE/e" || rs_fail "the no-ready-piece reply does not say there is nothing to run"
grep -q '^next:.*shape' "$TP_BASE/e" || rs_fail "the no-ready-piece reply has no next: line that names /shape"
[ ! -d "$TP_ROOT/.agents/runs" ] || rs_fail "a run with no ready piece left a run record"
rs_ok "with no ready piece the run script says so, names /shape and starts nothing"

# Pre-approval is a flag only: the policy has no key for it.
cp "$TP_ROOT/.agents/loop/policy.json" "$TP_BASE/policy-kept"
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
path = sys.argv[1]
body = json.load(open(path))
body["merge_pre_approved"] = True
json.dump(body, open(path, "w"))
PY
prc
cp "$TP_BASE/policy-kept" "$TP_ROOT/.agents/loop/policy.json"
[ "$PRC_CODE" -eq 3 ] || rs_fail "a policy key for pre-approval was accepted (got $PRC_CODE)"
grep -q 'no pre-approval key' "$TP_BASE/prc.out" "$TP_BASE/prc.err" || rs_fail "the refusal does not say the policy has no pre-approval key"
rs_ok "a policy key for pre-approval is refused: it is asked for each run, as a flag"

python3 "$RUN" --help | tr '\n' ' ' | tr -s ' ' | grep -q 'merge-pre-approved .*default is no' || rs_fail "run.py --help does not say the default is no"
rs_ok "run.py --help says the merge is not pre-approved by default"

# Before the App exists: unattended and pre-approved runs are refused, and name the second half.
prc --pieces 1 --unattended
[ "$PRC_CODE" -eq 3 ] || rs_fail "an unattended run was accepted with no App (got $PRC_CODE)"
grep -q '"half": "second"' "$TP_BASE/prc.out" || rs_fail "the unattended refusal does not name the second half"
prc --pieces 1 --merge-pre-approved
[ "$PRC_CODE" -eq 3 ] || rs_fail "a pre-approved merge was accepted with no App (got $PRC_CODE)"
grep -q '"half": "second"' "$TP_BASE/prc.out" || rs_fail "the pre-approved refusal does not name the second half"
rs_ok "an unattended run and a pre-approved merge are refused with no App, and name the second half"

# The run script's own plan changes nothing.
set +e
(cd "$TP_ROOT" && python3 "$KIT/scripts/run.py" --json --plan) > "$TP_BASE/o" 2> "$TP_BASE/e"
set -e
[ ! -d "$TP_ROOT/.agents/runs" ] || rs_fail "--plan left a run record"
rs_ok "run.py --plan leaves no run record"

rs_done
