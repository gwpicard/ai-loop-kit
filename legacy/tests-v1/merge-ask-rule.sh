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
# The second half guards the written gap in blocked-commands.md.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"

RULES="$ROOT/kit/templates/merge-ask-rules.json"
SCRIPT="$ROOT/kit/scripts/merge-ask-rules.py"
FOUNDED="$ROOT/kit/templates/claude-settings.json"
BLOCKED="$ROOT/kit/templates/blocked-commands.md"

rs_init "Merge confirmation box checks"
rs_exists "$RULES" "$SCRIPT" "$FOUNDED" "$BLOCKED"

if [ -z "${RS_LIST:-}" ]; then
  command -v python3 >/dev/null 2>&1 || \
    rs_fail "python3 is needed to read the settings files and run the matcher"

  python3 - "$RULES" "$SCRIPT" "$FOUNDED" "$BLOCKED" "$ROOT/tests/lib" "$rs_dir" \
    > "$rs_dir/matcher.out" 2>&1 <<'PY' || {
import json
import os
import shutil
import subprocess
import sys

rules_path, script, founded, blocked_path, lib_dir, work = sys.argv[1:7]
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
merge_rules = ["Bash(gh pr merge *)", "Bash(gh api *pulls/*/merge*)"]
if set(template) != {"ask"} or template["ask"][:2] != merge_rules:
    stop("merge-ask-rules.json holds %r, and its first two rules must be %r" % (template, merge_rules))
# Every other rule asks before something posted in the person's name; settings.sh tests those.
for other in template["ask"][2:]:
    if not other.startswith("Bash(gh "):
        stop("merge-ask-rules.json holds %r, which is not a gh posting rule" % other)
rules = template["ask"]
print("  ok: the template holds the two merge rules first, then only gh posting rules")

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

# Each merge rule is tested alone, so the posting rules (which also match gh api -X PUT)
# do not make a merge rule look needless.
for rule in merge_rules:
    if not evaluate([r for r in merge_rules if r != rule]):
        stop("taking out %s changes nothing, so the check does not need it" % rule)
print("  ok: taking out either rule is caught")

# The founded settings carry no merge ask rule: founding adds those only where
# every merge goes live. Their ask list holds only the pre-approved run rule.
for path, what in ((founded, "the founded settings template"),):
    held = json.load(open(path)).get("permissions", {}).get("ask", [])
    if any(r in held for r in rules):
        stop("%s already holds a merge ask rule" % what)
print("  ok: the founded template does not hold the rules")

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
founded_ask = before["permissions"].get("ask", [])
if after["permissions"].get("ask") != founded_ask + rules:
    stop("add left the ask list as %r" % after["permissions"].get("ask"))
if after["permissions"]["deny"] != before["permissions"]["deny"]:
    stop("add changed the deny list")
if after.get("hooks") != before.get("hooks"):
    stop("add changed the session-start hook")
rest_before = {k: v for k, v in before.items() if k != "permissions"}
rest_after = {k: v for k, v in after.items() if k != "permissions"}
if rest_before != rest_after or set(after["permissions"]) != set(before["permissions"]) | {"ask"}:
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

rs_done
