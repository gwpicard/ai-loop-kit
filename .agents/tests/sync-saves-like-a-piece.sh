#!/usr/bin/env sh
# sync-saves-like-a-piece.sh: guard how /sync saves what it corrects.
#
# Every skill that changes the records says how it saves them, except that sync
# did not. It corrected the pieces, the changelog, the masterplan and the check's
# own file, and stopped. On a project whose guard blocks a direct push to main,
# that left the corrections uncommitted, or committed onto whatever branch was
# checked out, and a record that disagrees with what is saved is the drift sync
# exists to remove. So the corrections take the save route the build path
# already requires, the same three a piece uses, and on the shared route they
# arrive as a pull request that merges only on the person's yes.
#
# The rule about uncommitted work is the one worth guarding hardest. Sync is run
# after an interruption, so a dirty tree is the ordinary case rather than the
# exception, and the two easy ways to get a clean branch are to sweep the work
# into sync's own commit or to discard it. Both destroy the thing sync was called
# to reconcile.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SYNC="$ROOT/.agents/skills/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Sync-saves-like-a-piece checks"
rs_exists "$SYNC" "$WORKFLOW"

# Arrival: start from a current main, and treat what is found as a finding.
rs_rule "main is brought up to date first" 'bring the shared `main` branch up to date'
rs_rule "uncommitted work is a finding" 'uncommitted work found here is the first finding'
rs_rule "and is left where it is" 'leave it exactly where it is'
rs_rule "never swept into sync's own commit" 'never sweep it into a commit of your own'
rs_rule "never discarded for a clean tree" 'discard it to get a clean tree'

# The save itself.
rs_rule "the corrections use the build path's route" \
  'the save route the build path already requires'
rs_rule "the routes are section-builder's three" 'the three routes section-builder names'
rs_rule "the branch is cut from the current main" \
  'short-lived branch from the up-to-date `main`'
rs_rule "only sync's own files are staged" 'stage only the files sync itself changed'
rs_rule "a pull request is opened" 'open a pull request titled after the reconciliation'
rs_rule "the project check runs" 'run the project check'
rs_rule "the summary paragraph is the pull request body" \
  'is the body of that pull request'
# Whether sync's pull request merges is the one merge step's to say, and
# one-merge-step.sh holds the rule there. Sync keeps the pointer.
rs_rule "sync merges only through the merge step" 'merge it only as the `section-builder` skill.s `references/merge\.md` says'
rs_rule "sync never deletes the branch" 'never delete the branch yourself'
rs_rule "and it says why a direct commit is drift" 'a second kind of drift'
rs_rule "an unreachable github is a missing step, not a hazard" \
  'a missing step is not a hazard'
rs_guard "$SYNC" "the /sync skill"

# WORKFLOW.md is where the person reads it.
rs_reset
rs_rule "sync saves the way a piece does" 'saved the way a piece is saved'
rs_rule "on a shared project that is a pull request" \
  'arrive as a pull request you decide to merge'
rs_rule "and found work is left alone" 'reported and left alone'
rs_guard "$WORKFLOW" "the shipped WORKFLOW.md"

rs_done
