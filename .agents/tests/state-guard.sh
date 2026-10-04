#!/usr/bin/env sh
# state-guard.sh: guard the hook and the deny rules that stop the agent moving
# a piece by hand.
#
# Only the gate script changes a piece's state, so a board can be trusted only
# while nothing goes round it. In Claude Code two things refuse a direct change
# to a `state:`, `shaping:` or `review:` label: a hook that reads each command
# before it runs, and deny rules that read the command as written. A guard
# that let one spelling through would look the same as one that works, until a
# piece reached `state:ready` that nobody had checked.
#
# So this feeds the hook each refused spelling and each allowed one, as Claude
# Code's hook input, and reads the exit code and the message. It runs the hook
# the way the settings template wires it, with the file present, missing and
# not runnable. A chained command that also runs the gate is refused too,
# since a guard that waved through anything naming the gate would wave through
# `gate.py report; gh issue edit 4 --add-label state:ready`.
#
# The deny rules go through the shared matcher in lib/permission-matcher.py,
# the one push-to-main-rules.sh uses. The spellings come from the section of
# blocked-commands.md that lists them, so the written lists and the rules
# cannot disagree without this failing. Each rule is then taken out in turn to
# prove it is needed.
#
# This repository's own issues keep today's labels until the release, so its
# own settings must carry neither the hook nor the rules. The validator holds
# that, and this runs the validator's block on a copy with the hook planted.
# Last, `gate.py report` names a hook the settings wire and the project lacks.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation"
HOOK="$FOUNDATION/state-guard.sh"
SETTINGS="$FOUNDATION/claude-settings.json"
GATE="$FOUNDATION/gate.py"
BLOCKED="$ROOT/.agents/skills/setup-ai-build-kit/references/blocked-commands.md"
VALIDATOR="$ROOT/.agents/tools/validate-kit.sh"
OWN_SETTINGS="$ROOT/.claude/settings.json"
FAKE="$ROOT/.agents/tests/replay/fake-github"

rs_init "State guard checks"
rs_exists "$SETTINGS" "$GATE" "$BLOCKED" "$VALIDATOR" "$OWN_SETTINGS"

if [ -z "${RS_LIST:-}" ]; then
  command -v python3 >/dev/null 2>&1 || rs_fail "python3 is needed to run the matcher"
  [ -f "$HOOK" ] || rs_fail "the setup skill carries no hook at templates/foundation/state-guard.sh"
  [ -x "$HOOK" ] || rs_fail "templates/foundation/state-guard.sh is not runnable"

  # The validator's block that checks this repository's own settings, run on
  # its own so this check cannot recurse when the validator runs this family.
  awk '/^# --- own settings carry no state guard: begin/ {copy=1} copy {print}
       /^# --- own settings carry no state guard: end/ {exit}' \
    "$VALIDATOR" > "$rs_dir/own-settings-block"
  [ -s "$rs_dir/own-settings-block" ] || \
    rs_fail "the validator has no block checking that this repository's settings carry no state guard"

  python3 - "$HOOK" "$SETTINGS" "$GATE" "$BLOCKED" "$OWN_SETTINGS" \
    "$ROOT/.agents/tests/lib" "$rs_dir" "$FAKE" > "$rs_dir/guard.out" 2>&1 <<'PY' || {
import json
import os
import re
import shutil
import stat
import subprocess
import sys

HOOK, SETTINGS, GATE, BLOCKED, OWN, LIB, WORK, FAKE = sys.argv[1:9]
sys.path.insert(0, LIB)
matcher = __import__("permission-matcher")
denied = matcher.any_match

problems = []


def problem(message):
    problems.append(message)
    print("  FAIL: " + message)


def ok(message):
    print("  ok: " + message)


problems_before = matcher.self_test()
if problems_before:
    print("\n".join(problems_before))
    sys.exit(1)
ok("the matcher agrees with every example in the documentation's table")

# --- the written lists ------------------------------------------------------

HEADING = "Changing a piece's state by hand"
blocked = open(BLOCKED).read()


def spelling(s):
    return " " in s and "gh" in s


both = matcher.read_list(blocked, "These spellings are refused by the hook and by the deny rules",
                         spelling, HEADING)
hook_only = matcher.read_list(blocked, "The hook refuses these spellings, and the deny rules miss them",
                              spelling, HEADING)
neither = matcher.read_list(blocked, "Neither refuses these spellings", lambda s: " " in s, HEADING)
for name, found in (("refused by both", both), ("refused by the hook alone", hook_only),
                    ("refused by neither", neither)):
    if not found:
        print("blocked-commands.md has no section %r with a list of spellings %s" % (HEADING, name))
        sys.exit(1)

# Spellings the reference has to keep listing, so taking one out fails here.
listed_both = [
    "gh issue edit 12 --add-label state:ready",
    "gh issue edit 12 --add-label shaping:spec",
    "gh issue edit 12 --add-label review:person",
    "gh issue edit 12 --remove-label state:building",
    "gh issue edit 12 --remove-label shaping:raw",
    "gh issue edit 12 --remove-label review:auto",
    "gh issue edit 12 --add-label state:ready,type:bug",
    "gh label delete state:ready",
    "gh label edit state:ready --color 000000",
    "gh label create state:done",
]
listed_hook_only = [
    'gh issue edit 12 --add-label "state:ready"',
    "gh issue edit 12 --add-label 'state:ready'",
    "gh issue edit 12 --add-label type:bug,state:ready",
    'gh issue edit 12 --add-label "type:bug, state:ready"',
    "gh issue edit 12 --add-label=state:ready",
    'gh issue create --title "Login" -l state:shaping',
    "/opt/homebrew/bin/gh issue edit 12 --add-label state:ready",
    "sh -c 'gh issue edit 12 --add-label state:ready'",
]
listed_neither = [
    'gh issue edit 12 --add-label "$LABEL"',
    "sh scripts/relabel.sh 12",
]
for command in listed_both:
    if command not in both:
        problem("blocked-commands.md does not list %r as refused by both" % command)
for command in listed_hook_only:
    if command not in hook_only:
        problem("blocked-commands.md does not list %r as refused by the hook alone" % command)
for command in listed_neither:
    if command not in neither:
        problem("blocked-commands.md does not list %r as refused by neither" % command)

# Refused by the hook, beyond the written lists: a chained command that also
# runs the gate, and the same moves in other places on the line.
chained = [
    ".agents/tools/gate.py report; gh issue edit 4 --add-label state:ready",
    "python3 .agents/tools/gate.py move 4 ready && gh issue edit 4 --remove-label state:building",
    "gh issue view 4 | cat; gh label delete review:auto --yes",
]
more_refused = chained + [
    "gh issue edit --add-label state:ready 12",
    "gh -R someone/project issue edit 12 --add-label shaping:check",
    "gh issue edit 12 --add-label STATE:READY",
    'gh label delete "shaping:raw" --yes',
    "gh label edit 'review:person' --name review:people",
    "gh api -X POST repos/o/r/issues/12/labels --input labels.json",
    "gh api --method DELETE repos/o/r/issues/12/labels/state%3Aready",
]

# Allowed by both: the gate's own commands, other labels, and reads.
must_run = [
    ".agents/tools/gate.py move 12 ready",
    "python3 .agents/tools/gate.py move 12 state:ready --run night",
    '.agents/tools/gate.py capture --title "Login" --body-file body.md',
    ".agents/tools/gate.py capture 12",
    ".agents/tools/gate.py labels",
    '.agents/tools/gate.py drop 12 --reason "nobody needs it"',
    ".agents/tools/gate.py tidy",
    ".agents/tools/gate.py report",
    "gh issue edit 12 --add-label type:bug",
    "gh issue edit 12 --add-label visual,data",
    'gh issue edit 12 --remove-label "how it works"',
    'gh issue edit 12 --title "Explain state:ready on the board"',
    "gh issue edit 12 --body-file body.md",
    'gh issue create --title "Login" --body-file body.md --label type:feature',
    "gh issue view 12 --json labels",
    "gh issue list --label state:ready",
    "gh label list",
    "gh label create type:feature --color 1D76DB",
    'git commit -m "Move the piece to state:ready through the gate"',
]
# The deny rule on the labels path also refuses a read there. The hook lets a
# read through, and the reference says so.
api_read = "gh api repos/o/r/issues/12/labels"

# --- the hook, fed Claude Code's hook input ---------------------------------


def hook_input(tool, tool_input):
    return json.dumps({"session_id": "rehearsal", "hook_event_name": "PreToolUse",
                       "tool_name": tool, "tool_input": tool_input})


def run_hook(tool, tool_input, hook=HOOK, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    done = subprocess.run([hook], input=hook_input(tool, tool_input), capture_output=True,
                          text=True, env=env)
    return done.returncode, done.stdout + done.stderr


def bash(command, **kw):
    return run_hook("Bash", {"command": command, "description": "rehearsal"}, **kw)


def refused(result):
    code, said = result
    return code == 2 and "gate.py" in said


for command in dict.fromkeys(both + hook_only + listed_both + listed_hook_only + more_refused):
    result = bash(command)
    if not refused(result):
        problem("the hook let %r through, or refused it without naming the gate command: %r"
                % (command, result))
ok("the hook refuses every spelling the reference lists and the chained ones, naming the gate")

for command in dict.fromkeys(must_run + neither + listed_neither + [api_read]):
    code, said = bash(command)
    if code != 0:
        problem("the hook refused %r, which must still run: %r" % (command, said))
ok("the hook lets the gate's commands, other labels, reads and the written gap through")

# The message says what to run instead, for each kind of write.
for command, wanted in (("gh issue edit 12 --add-label state:ready", "gate.py move"),
                        ('gh issue create --title "Login" --label state:shaping', "gate.py capture"),
                        ("gh label delete state:ready", "gate.py labels")):
    code, said = bash(command)
    if wanted not in said:
        problem("the refusal of %r does not name %r: %r" % (command, wanted, said))
    if "another way" not in said:
        problem("the refusal of %r does not say never to reach the move another way" % command)
ok("each refusal names the gate command to use instead")

# A GitHub tool call whose labels include one. Any tool whose name starts with
# mcp__ and contains github, with a labels field.
mcp_refused = [
    ("mcp__github__add_issue_labels",
     {"owner": "o", "repo": "r", "issue_number": 12, "labels": ["state:ready"]}),
    ("mcp__plugin_engineering_github__issue_write",
     {"method": "update", "issue_number": 12, "labels": ["type:bug", "shaping:spec"]}),
    ("mcp__github__create_issue", {"title": "Login", "labels": [{"name": "review:person"}]}),
    ("mcp__GitHub__update_issue", {"issue_number": 12, "labels": "type:bug, state:building"}),
]
mcp_allowed = [
    ("mcp__github__add_issue_labels", {"issue_number": 12, "labels": ["type:bug", "visual"]}),
    ("mcp__github__get_issue", {"issue_number": 12}),
    ("mcp__linear__update_issue", {"id": "x", "labels": ["state:ready"]}),
    ("Read", {"file_path": "README.md"}),
]
for tool, args in mcp_refused:
    if not refused(run_hook(tool, args)):
        problem("the hook let the GitHub tool call %s %r through" % (tool, args))
for tool, args in mcp_allowed:
    code, said = run_hook(tool, args)
    if code != 0:
        problem("the hook refused %s %r: %r" % (tool, args, said))
ok("the hook refuses a GitHub tool call carrying a state label, and nothing else")

# Input that is not what the hook expects never blocks a command.
for raw in ("", "not json", "{}"):
    done = subprocess.run([HOOK], input=raw, capture_output=True, text=True)
    if done.returncode != 0:
        problem("the hook blocked on input %r: %r" % (raw, done.stderr))
ok("input the hook cannot read never blocks a command")

# --- the hook as the settings template wires it -----------------------------

settings = json.load(open(SETTINGS))
entries = settings.get("hooks", {}).get("PreToolUse", [])
wired = [(e.get("matcher", ""), h.get("command", "")) for e in entries for h in e.get("hooks", [])
         if "state-guard.sh" in h.get("command", "")]
if len(wired) != 1:
    problem("the settings template wires the state guard %d times in PreToolUse, not once"
            % len(wired))
else:
    pattern, command = wired[0]
    for tool in ("Bash", "mcp__github__add_issue_labels", "mcp__plugin_engineering_github__issue_write"):
        if not re.fullmatch(pattern, tool):
            problem("the hook's matcher %r does not reach %s" % (pattern, tool))
    if ".agents/hooks/state-guard.sh" not in command or "-x" not in command:
        problem("the hook command does not run .agents/hooks/state-guard.sh only when runnable: %r"
                % command)
    project = os.path.join(WORK, "wired")
    os.makedirs(os.path.join(project, ".agents", "hooks"))
    placed = os.path.join(project, ".agents", "hooks", "state-guard.sh")
    write = hook_input("Bash", {"command": "gh issue edit 12 --add-label state:ready"})

    def wired_run():
        env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
        done = subprocess.run(["sh", "-c", command], input=write, capture_output=True, text=True,
                              env=env)
        return done.returncode, done.stdout + done.stderr

    code, said = wired_run()
    if code != 0:
        problem("with no hook in the project, the wired command blocked: %r" % said)
    shutil.copy(HOOK, placed)
    os.chmod(placed, 0o644)
    code, said = wired_run()
    if code != 0:
        problem("with a hook that is not runnable, the wired command blocked: %r" % said)
    os.chmod(placed, 0o755)
    code, said = wired_run()
    if code != 2 or "gate.py" not in said:
        problem("with the hook in place, the wired command did not refuse: %r" % ((code, said),))
    ok("the wired command refuses with the hook in place, and never blocks without it")

# --- the deny rules, through the shared matcher -----------------------------

rules = settings.get("permissions", {}).get("deny", [])


def evaluate(rules):
    found = []
    for command in both + listed_both:
        if not denied(rules, command):
            found.append("%r is not refused" % command)
    if not denied(rules, api_read):
        found.append("%r is not refused" % api_read)
    for command in hook_only + listed_hook_only + neither + listed_neither + must_run:
        if denied(rules, command):
            found.append("%r is refused" % command)
    return found


for command in dict.fromkeys(both + hook_only + neither + must_run + [api_read]):
    print("  %-7s %s" % ("denied" if denied(rules, command) else "allowed", command))
for found in evaluate(rules):
    problem("deny rules: " + found)
ok("the deny rules refuse what the reference says, and miss what it says they miss")

guard_rules = [r for r in rules if r.startswith("Bash(gh ")]
families = ("state:", "shaping:", "review:")
for family in families:
    for kind in ("issue edit * --add-label ", "issue edit * --remove-label ",
                 "issue create * --label ", "label delete ", "label edit ", "label create "):
        if not any(r.startswith("Bash(gh " + kind + family) for r in guard_rules):
            problem("the settings template has no deny rule for gh %s%s" % (kind, family))
if "Bash(gh api *issues/*/labels*)" not in rules:
    problem("the settings template has no deny rule for gh api on an issue's labels path")
for rule in guard_rules:
    if not evaluate([r for r in rules if r != rule]):
        problem("taking out %s changes nothing, so the check does not need it" % rule)
ok("taking out any one of the %d state guard rules is caught" % len(guard_rules))

# --- this repository's own settings -----------------------------------------

block = os.path.join(WORK, "own-settings-block")


def own_block_passes(content):
    copy = os.path.join(WORK, "own-copy")
    os.makedirs(os.path.join(copy, ".claude"), exist_ok=True)
    with open(os.path.join(copy, ".claude", "settings.json"), "w") as handle:
        json.dump(content, handle, indent=2)
    script = 'ROOT=$1; FAIL=0; fail() { FAIL=1; }; pass() { :; }; note() { :; }; . "$2"; exit $FAIL'
    done = subprocess.run(["sh", "-c", script, "sh", copy, block], capture_output=True, text=True)
    return done.returncode == 0


own = json.load(open(OWN))
if not own_block_passes(own):
    problem("the validator's own-settings block fails on this repository's real settings")
planted = json.loads(json.dumps(own))
planted.setdefault("hooks", {})["PreToolUse"] = entries
if own_block_passes(planted):
    problem("the validator passed this repository's settings with the state guard hook planted")
planted = json.loads(json.dumps(own))
planted["permissions"]["deny"] = planted["permissions"]["deny"] + [guard_rules[0]]
if own_block_passes(planted):
    problem("the validator passed this repository's settings with a state guard rule planted")
ok("the validator refuses this repository's settings with the hook or a rule planted")

# --- gate.py report names a missing hook ------------------------------------

project = os.path.join(WORK, "reported")
os.makedirs(os.path.join(project, ".claude"))
subprocess.run(["git", "init", "-q", project], check=True)
subprocess.run(["git", "-C", project, "-c", "user.name=R", "-c", "user.email=r@example.invalid",
                "commit", "-q", "--allow-empty", "-m", "first"], check=True)
shutil.copy(SETTINGS, os.path.join(project, ".claude", "settings.json"))
state = os.path.join(WORK, "gh-state.json")
with open(state, "w") as handle:
    json.dump({"repo": "rehearsal/project", "next": 900, "issues": [
        {"number": 1, "title": "Login", "body": "", "state": "open",
         "labels": ["state:shaping", "shaping:raw"], "assignees": [], "blocked_by": [],
         "sub_issues": []}]}, handle)
env = dict(os.environ, PATH=FAKE + os.pathsep + os.environ["PATH"], FAKE_GH_STATE=state,
           FAKE_GH_LOG=os.path.join(WORK, "gh.log"))


def report():
    done = subprocess.run([sys.executable, GATE, "report"], cwd=project, env=env,
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


code, said = report()
if code != 0 or "state-guard.sh" not in said:
    problem("gate.py report did not name the missing hook: %r" % said)
placed = os.path.join(project, ".agents", "hooks", "state-guard.sh")
os.makedirs(os.path.dirname(placed))
shutil.copy(HOOK, placed)
os.chmod(placed, 0o644)
code, said = report()
if code != 0 or "state-guard.sh" not in said:
    problem("gate.py report did not name a hook that is not runnable: %r" % said)
os.chmod(placed, 0o755)
code, said = report()
if code != 0 or "state-guard.sh" in said or len([l for l in said.splitlines() if l.strip()]) != 1:
    problem("gate.py report named the hook, or printed more than one line, with it in place: %r"
            % said)
os.remove(os.path.join(project, ".claude", "settings.json"))
os.remove(placed)
code, said = report()
if "state-guard.sh" in said:
    problem("gate.py report named the hook in a project whose settings do not wire it: %r" % said)
ok("gate.py report names a hook the settings wire and the project lacks, and only then")

if problems:
    sys.exit(1)
PY
    cat "$rs_dir/guard.out"
    rs_fail "the state guard, its deny rules and the written lists disagree"
  }
  cat "$rs_dir/guard.out"
fi

# The written rule, in the section that lists the spellings.
rs_rule "the section" "## changing a piece's state by hand"
rs_rule "only the gate moves a piece" 'only the gate script, `\.agents/tools/gate\.py`, changes them'
rs_rule "a refused move is never reached another way" 'never reach the same change another way'
rs_rule "a refused gate move goes to the person" 'if the gate refuses the move too, tell the person what it said'
rs_rule "the list refused by both" 'these spellings are refused by the hook and by the deny rules:'
rs_rule "the list the deny rules miss" 'the hook refuses these spellings, and the deny rules miss them:'
rs_rule "the list neither refuses" 'neither refuses these spellings, and the rule above still forbids them:'
rs_rule "a label inside a variable is missed" 'with the label in a variable'
rs_rule "a call from another script is missed" 'a call from another script'
rs_rule "a person's own browser is missed" "a change made in a browser on github"
rs_rule "the api rule refuses reads too" 'refuses every call on an issue.s labels path, reads included'
rs_rule "another coding agent runs neither" 'another coding agent runs neither the hook nor the deny rules'
rs_rule "a missing hook is named by the report" 'names a hook the settings expect and the project lacks'
rs_guard "$BLOCKED" "blocked-commands.md"

rs_done
