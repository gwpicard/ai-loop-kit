#!/usr/bin/env sh
# merge-ask-rule.sh: guard the confirmation box Claude Code shows before a
# merge that goes live.
#
# The rule that a person decides what merges is written in the merge step and
# the project's own AGENTS.md. It holds only while an agent has loaded and
# followed it. Where the host puts every merge to `main` live, a merge is a
# launch, and nothing mechanical stood between an agent and `gh pr merge`. Two
# projects built with the kit saw merges made on the agent's own judgement,
# one of them over a red check. Claude Code evaluates an ask rule before an
# allow rule, and shows its confirmation box even in auto mode, so an ask rule
# binds every session on that project whatever it was told.
#
# The first half is mechanical. The rules live in one template file, and the
# shared matcher in lib/permission-matcher.py, tested first against the
# documentation's own table, reads back which spellings they ask about. The
# lists come from blocked-commands.md as well as from here, so the written gap
# and the rules cannot disagree. Each rule is taken out in turn to prove it is
# needed. Then the script every writer runs is driven on a copy of the founded
# settings file and on the awkward cases: no file, a file that is not JSON, a
# person's own ask rule, and a line that stops saying `on every merge`.
#
# The second half guards prose: the three places that write the `Goes live:`
# line run the script, /maintain offers the rules to an older project once,
# and WORKFLOW.md and COMPATIBILITY.md say the box is Claude Code's alone.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
RULES="$SKILLS/setup-ai-build-kit/templates/merge-ask-rules.json"
SCRIPT="$SKILLS/setup-ai-build-kit/scripts/merge-ask-rules.py"
FOUNDED="$SKILLS/setup-ai-build-kit/templates/foundation/claude-settings.json"
OWN="$ROOT/.claude/settings.json"
BLOCKED="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
MERGE="$SKILLS/section-builder/references/merge.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
SHIP="$SKILLS/ship/SKILL.md"
MAINTAIN="$SKILLS/maintain/SKILL.md"
RECORD="$SKILLS/setup-ai-build-kit/templates/maintenance-record"
WORKFLOW="$ROOT/WORKFLOW.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"

rs_init "Merge confirmation box checks"
rs_exists "$RULES" "$SCRIPT" "$FOUNDED" "$OWN" "$BLOCKED" "$MERGE" "$SETUP" \
  "$SHIP" "$MAINTAIN" "$RECORD" "$WORKFLOW" "$COMPAT"

if [ -z "${RS_LIST:-}" ]; then
  command -v python3 >/dev/null 2>&1 || \
    rs_fail "python3 is needed to read the settings files and run the matcher"

  python3 - "$RULES" "$SCRIPT" "$FOUNDED" "$OWN" "$BLOCKED" "$ROOT/.agents/tests/lib" "$rs_dir" \
    > "$rs_dir/matcher.out" 2>&1 <<'PY' || {
import json
import os
import shutil
import subprocess
import sys

rules_path, script, founded, own, blocked_path, lib_dir, work = sys.argv[1:8]
sys.path.insert(0, lib_dir)
matcher = __import__("permission-matcher")
asked = matcher.any_match


def stop(message):
    print(message)
    sys.exit(1)


problems = matcher.self_test()
if problems:
    stop("\n".join(problems))
print("  ok: the matcher agrees with every example in the documentation's table")

# --- the rules ----------------------------------------------------------------

template = json.load(open(rules_path))
expected = {"ask": ["Bash(gh pr merge *)", "Bash(gh api *pulls/*/merge*)"]}
if template != expected:
    stop("merge-ask-rules.json holds %r, not %r" % (template, expected))
rules = template["ask"]
print("  ok: the template holds the two rules and nothing else")

must_ask = [
    "gh pr merge 12",
    "gh pr merge 12 --squash",
    "gh pr merge --merge 12",
    "gh api -X PUT repos/o/r/pulls/12/merge",
]
never_ask = ["gh pr view 12", "gh pr list", "gh pr checks 12"]

blocked = open(blocked_path).read()
if "## A merge that goes live" not in blocked:
    stop("blocked-commands.md has no section on a merge that goes live")
section = blocked.split("## A merge that goes live", 1)[1]
listed_ask = matcher.read_list(section, "These merges are asked about", lambda s: s.startswith("gh "))
listed_never = matcher.read_list(section, "These commands are never asked about", lambda s: s.startswith("gh "))
listed_missed = matcher.read_list(section, "These merges are not asked about", lambda s: " " in s)
for name, found in (("asked about", listed_ask), ("never asked about", listed_never),
                    ("missed", listed_missed)):
    if not found:
        stop("blocked-commands.md has no list of the merges %s" % name)
for command in must_ask:
    if command not in listed_ask:
        problems.append("blocked-commands.md does not list %r as asked about" % command)
for command in never_ask:
    if command not in listed_never:
        problems.append("blocked-commands.md does not list %r as never asked about" % command)


def evaluate(rule_set):
    found = []
    for command in listed_ask + must_ask:
        if not asked(rule_set, command):
            found.append("%r is not asked about" % command)
    for command in listed_never + never_ask + listed_missed:
        if asked(rule_set, command):
            found.append("%r is asked about" % command)
    return found


for command in dict.fromkeys(listed_ask + must_ask + listed_never + never_ask + listed_missed):
    print("  %-7s %s" % ("asked" if asked(rules, command) else "runs", command))
problems += evaluate(rules)
if problems:
    stop("\n".join(problems))
print("  ok: every merge listed as asked about is asked, and nothing else is")

for rule in rules:
    if not evaluate([r for r in rules if r != rule]):
        stop("taking out %s changes nothing, so the check does not need it" % rule)
print("  ok: taking out either rule is caught")

# The founded settings carry no ask list: founding adds the rules only where
# every merge goes live. The maintainer repository's own settings never do.
for path, what in ((founded, "the founded settings template"), (own, "this repository's own settings")):
    held = json.load(open(path)).get("permissions", {}).get("ask", [])
    if any(r in held for r in rules):
        stop("%s already holds a merge ask rule" % what)
print("  ok: neither the founded template nor this repository's own settings holds the rules")

# --- the script ----------------------------------------------------------------


def run(action, path):
    done = subprocess.run([sys.executable, script, action, path],
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def read(path):
    return open(path, "rb").read()


settings = os.path.join(work, "settings.json")

# A copy of the founded file.
shutil.copy(founded, settings)
before = json.load(open(settings))
code, out, err = run("add", settings)
if code != 0:
    stop("add on the founded settings exited %d: %s" % (code, err))
after = json.load(open(settings))
if after["permissions"].get("ask") != rules:
    stop("add left the ask list as %r" % after["permissions"].get("ask"))
if after["permissions"]["deny"] != before["permissions"]["deny"]:
    stop("add changed the deny list")
if after.get("hooks") != before.get("hooks"):
    stop("add changed the session-start hook")
rest_before = {k: v for k, v in before.items() if k != "permissions"}
rest_after = {k: v for k, v in after.items() if k != "permissions"}
if rest_before != rest_after or set(after["permissions"]) != {"deny", "ask"}:
    stop("add changed something besides the ask list")
if not all(rule in out for rule in rules):
    stop("add did not print the rules it added: %r" % out)
print("  ok: add on the founded settings keeps every deny rule and the hook, and says what it added")

added = read(settings)
code, out, err = run("add", settings)
if code != 0 or out.strip() or read(settings) != added:
    stop("a second add changed the file or printed something: %d %r" % (code, out))
print("  ok: a second add changes nothing and prints nothing")

code, out, err = run("remove", settings)
if code != 0:
    stop("remove exited %d: %s" % (code, err))
if json.load(open(settings)) != before:
    stop("remove did not give back the settings as founded")
if not all(rule in out for rule in rules):
    stop("remove did not print the rules it took out: %r" % out)
print("  ok: remove gives back the founded settings, with the ask list the kit made taken out")

code, out, err = run("remove", settings)
if code != 0 or out.strip():
    stop("a second remove changed something or printed something: %d %r" % (code, out))
print("  ok: remove with nothing to take out prints nothing")

# No settings file: a project not using Claude Code.
missing = os.path.join(work, "nowhere", "settings.json")
for action in ("add", "remove"):
    code, out, err = run(action, missing)
    if code != 2 or os.path.exists(missing):
        stop("%s with no settings file exited %d or wrote one" % (action, code))
print("  ok: with no settings file, nothing is written and the exit is 2")

# A file that is not valid JSON.
with open(settings, "w") as f:
    f.write('{ "permissions": { "deny": [ ,, }\n')
broken = read(settings)
for action in ("add", "remove"):
    code, out, err = run(action, settings)
    if code != 1 or read(settings) != broken:
        stop("%s on a file that is not JSON exited %d or changed it" % (action, code))
print("  ok: a file that is not valid JSON is left untouched and the exit is 1")

# The person's own ask rules, one of them for gh pr merge.
own_rules = {"permissions": {"ask": ["Bash(gh pr merge:*)", "Bash(npm publish *)"],
                             "allow": ["Bash(npm test)"]},
             "model": "opus"}
with open(settings, "w") as f:
    json.dump(own_rules, f, indent=2)
code, out, err = run("add", settings)
after = json.load(open(settings))
if code != 0 or after["permissions"]["ask"] != own_rules["permissions"]["ask"] + rules:
    stop("add beside the person's own ask rules gave %r" % after["permissions"].get("ask"))
if after["permissions"]["allow"] != own_rules["permissions"]["allow"] or after.get("model") != "opus":
    stop("add changed another key")
print("  ok: the person's own ask rules stay, and the kit's are added after them")

# The line stops saying on every merge: the kit's rules come out, the person's stay.
code, out, err = run("remove", settings)
if code != 0 or json.load(open(settings)) != own_rules:
    stop("remove beside the person's own ask rules gave %r" % json.load(open(settings)))
print("  ok: remove takes out the kit's rules only, and keeps an ask list that still holds the person's")

# One rule already there: add puts in only the missing one.
with open(settings, "w") as f:
    json.dump({"permissions": {"ask": [rules[0]]}}, f)
code, out, err = run("add", settings)
if code != 0 or json.load(open(settings))["permissions"]["ask"] != rules or rules[0] in out:
    stop("add with one rule already there gave %r, printing %r" % (json.load(open(settings)), out))
print("  ok: add puts in only the rule that is missing")

# No permissions at all: add creates the list.
with open(settings, "w") as f:
    f.write("{}\n")
code, out, err = run("add", settings)
if code != 0 or json.load(open(settings)) != {"permissions": {"ask": rules}}:
    stop("add on an empty object gave %r" % json.load(open(settings)))
print("  ok: add creates the ask list where there is none")
PY
    cat "$rs_dir/matcher.out"
    rs_fail "the merge ask rules, the script or the written gap are wrong"
  }
  cat "$rs_dir/matcher.out"
fi

# --- the merge step ---------------------------------------------------------------

rs_rule "the rules come from the template file" \
  'the rules sit in the `setup-ai-build-kit` skill.s `templates/merge-ask-rules\.json`\. take them from that file, never from memory'
rs_rule "every writer runs the same script" \
  'the same skill.s `scripts/merge-ask-rules\.py` writes them, so every step that records the `goes live:` line changes the file the same way'
rs_rule "every merge adds them in the same save" \
  'whoever writes `goes live: on every merge`, whether founding, this step or `/ship`, runs `python3 <installed setup-ai-build-kit skill>/scripts/merge-ask-rules\.py add \.claude/settings\.json` from the project root, in the same save'
rs_rule "add keeps everything else" \
  'it adds only the rules that are missing to the end of `permissions\.ask`, creates that list when there is none, and keeps every other entry and setting as it is'
rs_rule "the one line after adding" \
  'claude code will now show a confirmation box before each merge, because every merge goes live'
rs_rule "a recipe that settles a missing line writes it and sets the box" \
  'where the recipe settled it with no question asked, write the line the same way, `on every merge` or `through /ship`, and set the box with it'
rs_rule "a recipe that wins over not hosted adds the box" \
  'where a recipe wins over a `not hosted` line and says a change to `main` goes live, as above, the merge goes live, so run `add` there too'
rs_rule "any other value removes them" \
  'whoever writes any other value runs the same command with `remove`'
rs_rule "remove takes out only the kit's rules" \
  'it takes out exactly the template.s rules, and the `ask` list too when that leaves it empty\. a rule the person wrote stays'
rs_rule "the one line after removing" \
  'claude code will no longer show its confirmation box before a merge, because a merge no longer goes live'
rs_rule "nothing changed means nothing said" \
  'it prints each rule it added or took out, and nothing when nothing changed: say nothing then'
rs_rule "a file that is not JSON is named and left" \
  '1: the file is not valid json, and it was left untouched\. write nothing, and say in the reply that `\.claude/settings\.json` could not be read, so the box was not set up'
rs_rule "no settings file means nothing said" \
  '2: the project has no `\.claude/settings\.json`, because it does not use claude code\. write nothing, and leave the line out of the reply'
rs_rule "the written rule still holds everywhere" \
  'the box is a second guard\. the written rule, a yes that names the merge, still holds on every route'
rs_rule "recording the answer sets the box" \
  'so the question is asked once for each project\. in the same save, set the confirmation box as "the confirmation box on a merge that goes live" says'
rs_rule "a pre-approved run never meets the box" \
  'a pre-approved run never meets the confirmation box, because condition 6 keeps it from making a merge that goes live'
rs_guard "$MERGE" "the merge step"

# --- founding and /ship -------------------------------------------------------------

rs_reset
rs_rule "founding sets the box with the line" \
  'in the same save, set the confirmation box as the `section-builder` skill.s `references/merge\.md` says under "the confirmation box on a merge that goes live": `add` for `on every merge`, `remove` for any other value'
rs_guard "$SETUP" "founding"
rs_guard "$SHIP" "/ship"

# --- /maintain ------------------------------------------------------------------------

rs_reset
rs_rule "no settings file or another value ends the step" \
  'where the project has no `\.claude/settings\.json`, or the masterplan.s `goes live:` line does not say `on every merge`, this step ends'
rs_rule "the rules come from the installed template" \
  'read the rules in the installed setup-ai-build-kit skill.s `templates/merge-ask-rules\.json`, never from memory'
rs_rule "nothing missing means nothing said on the visit" \
  'list each one the project.s `permissions\.ask` list lacks\. where it lacks none, say nothing'
rs_rule "an earlier no stands for the box" \
  'read the `merge-ask-declined` line in `\.ai-build-kit-maintenance`, if there is one\. where that line names every missing rule, the person.s no stands'
rs_rule "offered once, naming what they do" \
  'offer them once, in one reply\. name the rules, and say in plain words what they do: claude code shows a confirmation box before each merge, because every merge puts the tool live'
rs_rule "the offer says it changes nothing else" \
  'it adds lines to the ask list, leaves the rest of the file as it was, and works on claude code only\. wait for a yes'
rs_rule "a yes runs the script" \
  'on a yes, run `python3 <installed setup-ai-build-kit skill>/scripts/merge-ask-rules\.py add \.claude/settings\.json`'
rs_rule "a no changes nothing and is recorded" \
  'on a no, leave the file as it is\. record the no as one line in `\.ai-build-kit-maintenance`, replacing any earlier one: `merge-ask-declined\|<yyyy-mm-dd>\|<the rules offered, separated by " ; ">`'
rs_rule "the offer returns only for a new rule" \
  'a later visit offers again only when the template holds a rule that line does not list'
rs_guard "$MAINTAIN" "maintain's confirmation box offer"
rs_require "the monthly pass runs the offer" "$MAINTAIN" \
  'rules before\. then run "adding the confirmation box on merges that go live" below'
rs_require "the maintenance record names the declined line" "$RECORD" 'merge-ask-declined'

# --- the written gap --------------------------------------------------------------------

rs_reset
rs_rule "the section says when the rules are added" \
  'where the masterplan.s `goes live:` line says `on every merge`, each merge puts the tool live\. there the kit adds two rules to the ask list'
rs_rule "the asked list" 'these merges are asked about:'
rs_rule "the never-asked list" 'these commands are never asked about:'
rs_rule "the missed list" 'these merges are not asked about, and a merge still needs a yes that names it:'
rs_rule "a website merge is missed" 'a merge made on github.s website'
rs_rule "another program is missed" 'a merge through another program'
rs_rule "bypassPermissions skips the box" 'any merge in a session in `bypasspermissions` mode, which skips every confirmation box'
rs_rule "the rules read the words as written" 'like a deny rule, an ask rule matches only the command as it is typed'
rs_guard "$BLOCKED" "blocked-commands.md"

# --- the story ------------------------------------------------------------------------

rs_require_load_bearing "WORKFLOW.md tells the box" "$WORKFLOW" \
  'claude code also shows its own confirmation box before each merge, so no merge goes live without a person seeing it'
rs_require_load_bearing "WORKFLOW.md says who adds and removes it" "$WORKFLOW" \
  'founding, the merge step and /ship add the box when they record that every merge goes live, and take it out when that changes'
rs_require_load_bearing "WORKFLOW.md says other agents keep the written rule" "$WORKFLOW" \
  'other coding agents have no such box and keep the written rule alone'
rs_require_load_bearing "COMPATIBILITY.md says the box is Claude Code's alone" "$COMPAT" \
  'only claude code shows a confirmation box before a merge that goes live'

rs_done
