#!/usr/bin/env sh
# stale-branches.sh: guard the monthly step that lists old branches.
#
# The step lists branches whose work already reached the default branch and
# gives the command that removes each one. Two rules carry the weight. It never
# removes a branch, since a branch removed by mistake can hold the only copy of
# some work. And it keeps the branches Git can confirm apart from the ones only
# GitHub records as merged. A pull request merged by squashing leaves the
# branch's own commits outside the default branch, so Git's own check misses
# it, and folding the two groups together would hand the person the forceful
# command with no word about why it is forceful.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READ="$ROOT/.agents/skills/maintain/references/stale-branches.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Old branch rules"
rs_exists "$READ" "$MAINTAIN" "$WORKFLOW"

# Where it applies.
rs_rule "it runs at every monthly visit" 'at every monthly visit, on every build path'
rs_rule "no remote means this computer only" 'say that only this computer was checked'
rs_rule "no default branch means the step did not run" 'say the branch check did not run'
rs_rule "the fetch waits for an origin remote" 'where the project has a remote called `origin`, run `git fetch origin`'
rs_rule "the fetch never prunes" 'do not add `--prune`'

# What is never listed.
rs_rule "a checked-out branch in any working copy" '`git worktree list` names them all'
rs_rule "a branch with an open pull request" 'a branch with an open pull request'
rs_rule "a branch the project says stays" 'a branch the project.s own agents\.md or masterplan says stays'
rs_rule "no long-lived branch is invented" 'never set one aside because of its name alone'
rs_rule "classic protection counts" 'protected when the first answer is `true`'
rs_rule "only a deletion rule counts" 'a rule whose `type` is `deletion`\. any other rule does not count'
rs_rule "an unchecked protection is said" 'say that protection was not checked'

# The two groups.
rs_rule "git's own check for local branches" '`git branch --merged origin/<default>`'
rs_rule "remote branches come from the remote itself" '`git ls-remote --heads origin`, which asks github directly'
rs_rule "squash merges are named as the gap" 'merged by squashing or rebasing'
rs_rule "the second group asks github" '`gh pr list --state merged --head <name> --base <default>'
rs_rule "the branch must end where the pull request ended" 'its last commit is the last commit of that merged pull request, or comes before it'
rs_rule "later work keeps a branch off both groups" 'commits added after its pull request merged holds work the default branch may not have'
rs_rule "that branch is still named" 'because github shows it as merged and it is not'
rs_rule "a missing github tool is said" 'this second group cannot be read\. say so in one line'

# The commands.
rs_rule "the careful local command" '`git branch -d <name>`\. git refuses this command'
rs_rule "the forceful command is explained" 'the capital `d` removes the branch without that check'
rs_rule "the remote command" '`git push origin --delete <name>`\. where'
rs_rule "the step never deletes" 'never run one of these commands'

# What it cannot tell.
rs_rule "it cannot tell who still wants a branch" 'whether somebody still means to use a branch'
rs_rule "a later change could undo a squash" 'a later change could have undone part of it'
rs_rule "a teammate's copy is untouched" 'leaves theirs alone'

# What the person sees.
rs_rule "silent when there is nothing" 'when no branch qualifies and nothing was left out, say nothing'
rs_rule "a protected branch counts as left out" 'counts as left out when it would have qualified but was set aside: because github protects it from deletion'
rs_rule "a set-aside branch is never silent" 'a report is never silent about a branch it set aside'
rs_rule "computer and github stay apart" 'it keeps this computer and github apart'
rs_rule "the report says nothing was removed" 'i have not removed anything'
rs_rule "the report says what it cannot tell" 'i cannot tell whether somebody still plans to use it'
rs_rule "the example explains the capital d" 'the capital d removes the branch without git.s own check\. it is safe here only because github records the same work as merged'
rs_rule "the example names a branch with later work" 'it has work added after the merge\. i have left it alone'
rs_rule "the example names a protected branch" 'github protects this branch from deletion, so i have left it alone'
rs_guard "$READ" "the shipped stale-branches.md"

rs_reset
rs_rule "maintain loads the read" 'load `references/stale-branches\.md`'
rs_rule "the two groups stay apart" 'keep the ones git confirms apart from the ones only github records as merged'
rs_rule "maintain never removes a branch" 'never remove a branch\.'
rs_guard "$MAINTAIN" "maintain's old-branch step"

rs_require_order "the branch step sits in the monthly pass" "$MAINTAIN" \
  'references/stale-branches\.md' '^## Quarterly, or before a handover'

rs_require "WORKFLOW says what is listed" "$WORKFLOW" \
  'lists old branches whose work is already in your main branch'
rs_require "WORKFLOW names the two kinds" "$WORKFLOW" \
  'the ones git can confirm, and the ones only github records as merged'
rs_require "WORKFLOW says it never removes one" "$WORKFLOW" \
  'it never removes a branch itself'

rs_done
