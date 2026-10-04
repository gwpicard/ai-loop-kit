#!/usr/bin/env sh
# founding-branch.sh: guard the read of which branch founding is on.
#
# In a real project, founding adopted an existing repository while the person
# had a feature branch checked out, and saved its checkpoint there. `main`
# never received the masterplan or the kit's files. Another session then cut a
# release from `main` without them, and the commits had to be moved across by
# hand. Founding read the records, the pieces and the unsaved work before it
# started, and never the branch.
#
# The rules below close that. They are prose a coding agent reads, so this reads
# the source: each rule is still there, and removing it breaks the check. The
# rules worth holding hardest are the two that protect the person's work: a
# folder holding unsaved work is never switched, and a switch that fails never
# stops founding.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILL_DIR="$ROOT/.agents/skills/setup-ai-build-kit"
SETUP="$SKILL_DIR/SKILL.md"
REPORT="$SKILL_DIR/references/completion-report.md"
ADOPT="$SKILL_DIR/references/adopting.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Founding branch checks"
rs_exists "$SETUP" "$REPORT" "$ADOPT" "$WORKFLOW"

# The read itself, in the order the rule gives, and the cases where it says
# nothing at all.
rs_rule "the branch is read before anything is written" \
  'before anything is written, read which branch'
rs_rule "the current branch comes from git branch --show-current" \
  'git branch --show-current'
rs_rule "with a fallback for a Git too old to have it" \
  'git rev-parse --abbrev-ref head'
rs_rule "the default branch is the remote's first" \
  'git symbolic-ref --short refs/remotes/origin/head'
rs_rule "with the remote's name taken off" 'origin/. taken off'
rs_rule "else a local main, else a local master" \
  'else a local .main., else a local .master.'
rs_rule "with no remote and neither, the current branch is the default" \
  'with no remote and neither of those, the current branch is the default'
rs_rule "no commits, or already on the default, gets nothing said" \
  'with no commits yet, or one already on the default branch, gets nothing said'
rs_rule "a detached checkout counts as another branch" \
  'a detached checkout counts as another branch'
rs_rule "and is named and returned to by its commit" \
  'git switch --detach <commit>'

# A clean tree on another branch: switch, and say so once.
rs_rule "unsaved work is read before any switch" 'git status --porcelain'
rs_rule "the switch uses git switch" 'switch with .git switch <default>.'
rs_rule "with a fallback for an older Git" 'git checkout <default>'
rs_rule "a default branch only on the remote is created from it" \
  'creates the default branch from the remote.s copy'
rs_rule "the switch is said once, in one line" 'say once, in one line'
rs_rule "the line is not a question founding waits on" \
  'not a question, and founding does not wait for an answer'

# Unsaved work: never switched.
rs_rule "a folder holding unsaved work is never switched" \
  'never switch, because switching would carry or disturb'
rs_rule "and the person is told when the records reach the default" \
  'reach .<default>. only when this branch merges'

# The switch fails.
rs_rule "a failed switch leaves founding where it is, and it carries on" \
  'carry on founding; never stop for it'
rs_rule "a worktree made by another tool is the named cause" \
  'a worktree made by another tool'

# The person's own choice.
rs_rule "the person can choose their own branch, and founding goes back to it" \
  'switch back to it before the founding save'
rs_rule "and the choice survives a resume" \
  'write that choice into the setup notes'
rs_rule "a refused switch back does not stop founding either" \
  'where git refuses the switch back'

# Resuming, and the kit's own source.
rs_rule "the read runs again on resume" 'runs again whenever founding resumes'
rs_rule "founding's own files from an earlier session are not the person's" \
  'files founding wrote itself in an earlier session are not the person'
rs_rule "the kit's own source is never switched, named by what marks it" \
  'where .release-manifest.txt. and .docs/maintaining.md. sit at the root, switch nothing'

# A founding saved off the default branch says so where it lasts.
rs_rule "a save off the default branch is named" \
  'where founding saves anywhere but the default branch'
rs_rule "in a dated changelog line naming the branch" \
  'write a line in changelog.md under today.s date naming the branch'
rs_rule "which says when the records reach the default branch" \
  'the records reach the default branch when it merges'
rs_rule "and the completion report says the same" \
  'the completion report says the same'

rs_guard "$SETUP" "the /setup-ai-build-kit skill"

# Position is the point: the bootstrap script writes files, and a folder with
# new files in it reads as holding unsaved work, so the read has to come first.
rs_require_order "the branch is read before the bootstrap script writes" \
  "$SETUP" 'Before anything is written, read which branch' \
  'Then run `scripts/bootstrap-project.sh`'

# The completion report tells the person in their own words.
rs_reset
rs_rule "the report translates a save off the default branch" \
  'saved on a branch other than the default ->'
rs_rule "and its shape carries the line where it applies" \
  'and reaches .\[default branch\]. only when that branch is merged'
rs_guard "$REPORT" "the completion report reference"

# The other two places the story is told.
rs_require_load_bearing "adopting a project points to the branch read" \
  "$ADOPT" 'settled which branch it is on'
rs_require_load_bearing "WORKFLOW.md tells the person" \
  "$WORKFLOW" 'checks which branch your folder is on'

rs_done
