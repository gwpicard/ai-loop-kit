#!/usr/bin/env sh
# ship-runs-recipe.sh: guard how /ship runs a project's recipe.
#
# On a recipe, /ship reads the recipe the project named and runs its eight
# checks in order, one plain line each. Off a recipe, it keeps the general
# readiness list. Either way a check not done is a warning, said once and
# written in the changelog, and the launch goes ahead. The one wait left is
# the address, because a tool with no recorded address is not live.
#
# The rules most likely to go quietly are the ones that turn a warning back
# into a stop, and the one that keeps the skill free of product names. A skill
# that learned one recipe's commands would read wrongly on every other recipe,
# and nothing on screen would say so.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHIP="$ROOT/.agents/skills/ship/SKILL.md"
EVIDENCE="$ROOT/.agents/skills/ship/references/evidence-run.md"
WORKFLOW="$ROOT/WORKFLOW.md"
SCENARIOS="$ROOT/.agents/tests/scenarios.md"
SECOND="$ROOT/.agents/skills/second-opinion/SKILL.md"
FORMAT="$ROOT/.agents/skills/ship/references/recipe-format.md"

rs_init "Ship-runs-recipe rules"
rs_exists "$SHIP" "$EVIDENCE" "$WORKFLOW" "$SCENARIOS" "$SECOND" "$FORMAT"

# Which recipe, if any.
rs_rule "reads the project's Recipe line" 'read the `recipe:` line in the stack section of the project.s agents\.md'
rs_rule "the file name carries its .md, as founding records it" 'a file name there, written with its `\.md` as founding records it'
rs_rule "reads the named file and its shared parts" 'read that file in this skill.s `recipes/` folder, and each part it links with `shared part:`'
rs_rule "none or no line is off a recipe" '`recipe: none`, or no line at all, means the project is off a recipe'
rs_rule "a missing recipe file is said once and treated as off a recipe" 'if the named file is not there, say so once and treat the project as off a recipe'

# On a recipe.
rs_rule "the recipe's checks replace the general list" 'on a recipe, the recipe.s own checks replace the general list'
rs_rule "going live follows the recipe's going-live section" 'on a recipe, go live the way its going-live section says'
rs_rule "commands and products come from the recipe at run time" 'every command, service and address comes from it at run time\. this skill names none of them'
rs_rule "runs every section in the recipe's order" 'take the recipe.s eight sections in its order: preview, going live, rollback, backup, restore, secrets, logs and health'
rs_rule "reads how it works and how it is checked" 'read `how it works:` for what happens and `how it is checked:` for what a pass looks like'
rs_rule "Who runs it decides how" 'then let `who runs it:` decide how the check is done'
rs_rule "the kit runs its own checks" '`the kit`: run the check from the project and read the output against the pass'
rs_rule "a read-back check asks for a paste and reads it" '`a companion or the person, result read back`: the check runs somewhere this session cannot reach\. say in one plain sentence what to fetch and from where, ask the person to paste it here, and read it against the pass yourself'
rs_rule "a person looking is asked and recorded" '`a person looking`: no machine can judge it\. ask the person to look, say in one sentence what they are looking for, and record what they say'
rs_rule "a check that changes the live tool is not forced" 'a check that would change the live tool only to prove it can, as a rollback does, is not run against the live tool'
# "Possible" has to rest on something the kit saw, and the line must not read
# as a rollback that was tried.
rs_rule "rollback is confirmed by a listed earlier build" 'for rollback, confirm with the recipe.s own commands that an earlier production build is listed'
rs_rule "the rollback line says it was not tried" 'report the line as "rollback possible, not tried", so it never claims more than was checked'

# A deploy the kit runs has nobody to carry a request to. Without these rules,
# the hosting request would send the person to a server nobody runs, and the
# launch would wait for an answer that never comes.
rs_rule "no hosting request when the kit runs the going-live" 'on a recipe whose going-live section the kit runs itself, no hosting request is written'
rs_rule "the kit's own address is the one the wait needs" 'the address that section produces, recorded as "on a recipe" below says, is the address the first launch waits for'
rs_rule "the wait is met by the kit's own going-live" 'recorded under the request, or by the kit.s own going-live on a recipe'

# Build with care reaches the recipe for its ordinary work and for an area
# once its caution is settled.
rs_rule "care work outside areas uses the recipe's checks" 'on a recipe, readiness and going live are the recipe.s checks, as "on a recipe" says'
rs_rule "a settled area goes live on the next run of the checks" 'an area whose caution is done or accepted goes live through the next run of the eight checks, not through a separate deploy'
rs_rule "one plain line per section, in order" 'report each section in one plain line, in this order: preview up, live address updated, rollback possible, backup present, restore works, no secret in the repo, logs readable, health answers'
rs_rule "a line leaves the command out" 'leaves the command out'

# A warning, not a stop.
rs_rule "a check not done is a warning said once" 'a check that failed, could not run, or got no answer is a warning\. say it once'
rs_rule "the warning is recorded and the next section runs" 'record it in changelog\.md with the date and the section, and go on to the next section'
rs_rule "the launch is not held for a check" 'do not hold the launch for it, and do not ask the person to choose to go live without it'
rs_rule "the address is the one wait" 'the one wait that remains is the address'
rs_rule "a kit-run launch records its address" 'where the kit ran the going-live section itself, record the live address it produced'
rs_rule "no recorded address, not called live" 'a tool with no recorded address is not called live, on a recipe or off one'
rs_rule "a later ship runs the checks again" 'on a recipe, run its eight checks again'

# A later launch. The pointer rule once sat only under "After the first
# launch", a hundred lines below the steps that write the lines, and a real
# second launch gave every old warning again in full, twice. So it sits beside
# the reporting now, and each half of it is held: the changelog is read first,
# an old warning is only a pointer, and a new one is still said in full, since
# a rule that folded new warnings into pointers would hide them.
rs_rule "a later launch reads the changelog first" 'on a launch after the first, read changelog\.md before you write these lines'
rs_rule "an old warning is a one-line pointer" 'where it already holds the same warning for the same section, that section.s line is a one-line pointer and nothing more'
rs_rule "the pointer drops the reason and the risk" 'leave out the reason and the risk, and add no second changelog entry for it'
rs_rule "a new or changed warning is said in full" 'a warning the changelog does not hold, or one whose cause has changed, is new: say it once in full'
rs_rule "the later-launch section points to the rule" '"on a recipe" says how a warning the changelog already holds is given: as a one-line pointer, never again in full'

# Off a recipe.
rs_rule "off a recipe the general list applies" 'off a recipe, check whatever of this actually applies'
rs_rule "the general list is warnings" 'each item that applies and is not in place is a warning: name it once in one plain line, record it in changelog\.md with the date, and carry on\. none of them holds the launch'

# A setting the kit can read. A real run stopped and asked the person to open
# a dashboard for a setting the service answered in public with the key the
# tool already sends to the browser. Asking costs the person a turn and a trip
# they did not need, so the kit reads first, with nothing secret, and asks only
# for what it cannot read, saying why.
rs_rule "the review follows the setting rule" 'before the review asks the person to look up a setting, it follows "a setting the kit can read" below'
rs_rule "the rule holds for the review and every check" 'this holds for the launch review and for every check in this skill, on a recipe or off one'
rs_rule "the kit checks whether it can read the setting first" 'before you ask the person to look up a setting of a service the tool uses, check whether the kit can read it with what it already has'
rs_rule "the three routes it already has" 'an address the service answers in public, a command-line tool this session is already signed in to, through that tool.s own commands, or the project.s own files'
rs_rule "it reads and reports instead of asking" 'where it can, read the setting and report its value in one plain line, instead of asking'
rs_rule "the recipe says which settings and how" 'its `settings the kit can read` section, where it has one, says which settings the kit reads and how'
rs_rule "only a key the browser already has" 'such a read uses only a key the project already sends to the browser'
rs_rule "never a secret for a read" 'never use a secret key, a service key or a password to read a setting, and never sign in to anything new for it'
rs_rule "it asks only for what it cannot read, and says why" 'ask the person only for a setting the kit cannot read that way, and say in the same sentence why it cannot'
rs_guard "$SHIP" "ship's recipe rules"
rs_require_order "the setting rule sits beside the other go-live rules" "$SHIP" '^#### A setting the kit can read$' '^#### A secret a check needs$'

# The review may run in a session that reads only second-opinion, so the rule
# has to be there as well.
rs_require_load_bearing "second-opinion reads a setting before asking" "$SECOND" 'before a finding asks the person to look up a setting of a service the tool uses, check whether you can read it yourself with what you already have'
rs_require_load_bearing "second-opinion points at the recipe's section" "$SECOND" 'the recipe.s `settings the kit can read` section says how'
rs_require_load_bearing "second-opinion uses no secret for a read" "$SECOND" 'use only a key the project already sends to the browser, never a secret key, a service key or a password'
rs_require_load_bearing "second-opinion asks only for what it cannot read" "$SECOND" 'ask the person only for a setting you cannot read that way, and say why you cannot'

# The format lets a recipe say which settings the kit reads.
rs_require_load_bearing "the format has the optional settings section" "$FORMAT" 'a recipe may carry one more section, `## settings the kit can read`, between health and the proven section'
rs_require_load_bearing "the format keeps secrets out of the section" "$FORMAT" 'a setting that needs a secret key to read does not belong here'
rs_require_load_bearing "the section is not one of the eight" "$FORMAT" 'it is not one of the eight, and /ship gives it no line of its own'

rs_require_absent "the general list is no longer a requirement" "$SHIP" 'require whatever of this actually applies'
rs_require_order "the Recipe line is read before any path runs" "$SHIP" 'Read the `Recipe:` line' '^## 1\. Follow the current path'
rs_require_order "the recipe's checks come after the hosting request" "$SHIP" 'references/hosting-request\.md' '^#### On a recipe$'

# No product name in the skill. The names come from the recipes themselves, the
# word after " on " in each recipe title, so a new recipe's target is covered
# the day its file arrives, together with a fixed list of the obvious others.
if [ -z "${RS_LIST:-}" ]; then
  targets=$(for rf in "$ROOT"/.agents/skills/ship/recipes/*.md "$ROOT"/.agents/tests/recipes-awaiting-run/*.md; do
    [ -f "$rf" ] || continue
    sed -n 's/^# Recipe: .* on \(.*\)$/\1/p' "$rf" | head -1
  done | tr '[:upper:]' '[:lower:]' | sort -u | paste -sd'|' -)
  [ -n "$targets" ] || rs_fail "no recipe title named a deploy target, so the product read would check nothing"
  PRODUCTS="$targets|supabase|netlify|heroku|railway|fly\.io|firebase"
  names_in() {
    tr '[:upper:]' '[:lower:]' < "$1" | grep -nE "$PRODUCTS" || true
  }
  for sf in "$SHIP" "$EVIDENCE"; do
    found=$(names_in "$sf")
    if [ -n "$found" ]; then
      printf '%s\n' "$found" >&2
      rs_fail "$sf names a product that belongs in a recipe"
    fi
  done
  rs_ok "ship and the evidence run name no product from any recipe"
  cp "$SHIP" "$rs_dir/ship-named"
  first_target=$(printf '%s' "$targets" | cut -d'|' -f1)
  printf '%s\n' "Deploy it with $first_target." >> "$rs_dir/ship-named"
  [ -n "$(names_in "$rs_dir/ship-named")" ] ||
    rs_fail "a product named in the skill was not noticed"
  rs_ok "a product named in the skill is noticed"
fi

rs_require "the evidence run points at ship's recipe steps" "$EVIDENCE" 'on a project with a recipe, the rollback, backup, restore, secrets, logs and health checks are the recipe.s own'

rs_require_load_bearing "WORKFLOW says the recipe's checks replace the list" "$WORKFLOW" 'on a recipe, the recipe.s own checks take the place of that list'
rs_require_load_bearing "WORKFLOW gives the eight lines" "$WORKFLOW" 'preview up, live address updated, rollback possible, backup present, restore works, no secret in the repo, logs readable, health answers'
rs_require_load_bearing "WORKFLOW says the rollback was not tried" "$WORKFLOW" 'the rollback line says a rollback is possible and was not tried'
rs_require_load_bearing "WORKFLOW says who runs each check" "$WORKFLOW" 'where a check runs on a server the kit cannot reach, you paste the result back and the kit reads it'
rs_require_load_bearing "WORKFLOW says a check is a warning" "$WORKFLOW" 'a check that fails or cannot run is a warning, said once and written in the changelog, and the launch goes ahead'
rs_require_load_bearing "WORKFLOW keeps the address wait" "$WORKFLOW" 'the one thing a first launch waits for is its address'
rs_require_load_bearing "WORKFLOW says the general list is warnings" "$WORKFLOW" 'anything missing from it is a warning you hear once and find in the changelog'
rs_require_load_bearing "WORKFLOW says an old warning comes back as a pointer" "$WORKFLOW" 'a warning the changelog already holds comes back as one line pointing to it, so anything given in full is new'

rs_require_load_bearing "WORKFLOW says the kit reads a setting before asking" "$WORKFLOW" 'before the launch review asks you to look up a setting, the kit reads it itself where it can'
rs_require_load_bearing "WORKFLOW says it asks only for what it cannot read" "$WORKFLOW" 'it asks you only about a setting it cannot read, and says why it cannot'

rs_require_load_bearing "scenario 20 runs the eight checks" "$SCENARIOS" 'on a recipe, operational readiness is the recipe.s eight checks in its order'
rs_require_load_bearing "scenario 20 keeps the general list off a recipe" "$SCENARIOS" 'off a recipe, operational readiness is the general list, and each missing item is a warning'
rs_require_load_bearing "scenario 20 keeps the address wait" "$SCENARIOS" 'the first launch still waits for a recorded address'

rs_done
