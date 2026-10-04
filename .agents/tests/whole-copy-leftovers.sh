#!/usr/bin/env sh
# whole-copy-leftovers.sh: guard the tidy step for a project founded from a
# whole copy of the kit.
#
# A project founded that way carries the kit's own generated adapters under
# .claude/commands/, .cursor/commands/ and .gemini/commands/. The shared
# installer never refreshes them, because it does not know they exist, and its
# own symlinks under .claude/skills/ already do the job. So Claude Code shows
# every command twice, and after the rename of plan to shape the project still
# offers /plan from a file nothing will ever remove. The retired skill folder
# survives the same way, because the lockfile no longer lists it.
#
# The obvious fix is to delete the files by hand, and that was refused: it
# fixes one project and leaves the next one to be found the same way. So the
# tidy is a step in maintain, and this check reads its rules back. The two
# that matter keep it safe: an adapter is recognised by its generated marker
# and never by its name, so a command file the person wrote survives, and a
# retired skill folder only by the kit's former names and absence from the
# lockfile, so the person's own skills survive.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Whole-copy-leftovers checks"
rs_exists "$MAINTAIN" "$WORKFLOW"

# Why the step exists, and why it is a step rather than advice.
rs_rule "the installer never refreshes the adapters" \
  'never refreshes them because it does not know they exist'
rs_rule "a hand deletion fixes one project" \
  'deleting the files by hand in one project fixes one project'

# The two rules that keep it safe.
rs_rule "an adapter is recognised by its marker" \
  'recognised only by the generated marker on its first lines'
rs_rule "and never by its name" \
  'never by its name: a command file the person wrote'
rs_rule "retired folders are looked for in both skill folders" \
  'look in both .\.agents/skills/. and .\.claude/skills/.'
rs_rule "a retired folder is one of the former names" \
  'one of the kit.s former names, .build., .start. or .plan.'
rs_rule "and absent from the lockfile" \
  'and the lockfile does not list it'
rs_rule "any other folder is the person's own" \
  'any other folder there is the person.s own and is left alone'

# The step is offered, applied on approval, and recorded.
rs_rule "the list is shown with what removing it does" \
  'show the list and say what removing it does'
rs_rule "and removed on approval" 'remove on approval, and remove the empty'
rs_rule "and recorded" 'a changelog line saying what was removed and why'

# It runs from the monthly pass and does nothing on a clean project.
rs_rule "the monthly pass calls it on the shared route" \
  'on the shared route, also run .tidying a project founded from a whole copy'
rs_rule "a project without the leftovers gets nothing" \
  'a project that has none of them gets nothing here'
rs_guard "$MAINTAIN" "the maintain skill"

rs_require "WORKFLOW.md says the visit offers to remove the kit's command files" \
  "$WORKFLOW" 'the visit offers to remove those and leaves anything you wrote yourself alone'

rs_done
