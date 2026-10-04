#!/usr/bin/env sh
# fold-at-merge.sh: guard the fold the merge step makes before it merges.
#
# Each piece writes its changelog entry to its own file in `changes/`, and only
# /sync or /ship used to fold those files into CHANGELOG.md. Two projects used
# the kit for weeks and nobody typed either command once, so the files piled up
# and the history stopped on the day the files were introduced. The fold now
# rides on the merge, which the kit makes one at a time, so it always runs on a
# branch that already holds every earlier merge and two pieces built side by
# side still never conflict.
#
# The rules are prose a coding agent reads, so this reads them back and proves
# each one load-bearing. What the shipped script and the fold do is rehearsed in
# fold-at-merge-rehearsal.sh. The design addendum for the second round of the
# redesign lands with this change, so its nine decisions are held here too.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
MERGE="$SKILLS/section-builder/references/merge.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
SCRIPT="$SKILLS/section-builder/scripts/bring-up-to-date.sh"
SYNC="$SKILLS/sync/SKILL.md"
SHIP="$SKILLS/ship/SKILL.md"
AGENTS="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
README="$SKILLS/setup-ai-build-kit/templates/foundation/README.md"
TEMPLATE="$SKILLS/setup-ai-build-kit/templates/CHANGELOG.md"
WORKFLOW="$ROOT/WORKFLOW.md"
NOTE="$ROOT/docs/design/loop-first-round-2.md"

rs_init "Fold at the merge checks"
rs_exists "$MERGE" "$BUILDER" "$SYNC" "$SHIP" "$AGENTS" "$README" "$TEMPLATE" "$WORKFLOW" "$NOTE"

# --- the merge step -----------------------------------------------------------

rs_rule "the section is there" '## the fold before the merge'
rs_rule "it runs after the named yes or pre-approval, before gh pr merge" \
  'after the yes that names the merge, or under pre-approval, and before `gh pr merge`'
rs_rule "step 1: take in main with a merge commit" \
  '1\. on the pull request.s branch, take in the latest `main` with a merge commit, never a rebase or a force push'
rs_rule "step 2: fold every waiting file" '2\. fold every file now in `changes/` into `changelog\.md`'
rs_rule "the piece's own and any left behind" "the piece.s own, and any a merge made elsewhere left behind"
rs_rule "step 3: commit, push and wait on the new commit" \
  '3\. commit the fold as `fold the changelog`, push the branch, and wait for the project check on that new commit, as "waiting for the check" says'
rs_rule "step 4: merge only on green" '4\. merge only when that check is green'
rs_rule "red merges nothing and goes to /fix" 'red means nothing merges: say so and take it to `/fix`'
rs_rule "an unfinished check makes the merge wait, said once" \
  'because it is queued or github is slow, the merge waits: say so once'
rs_rule "never on an unfinished check" 'never merge on an unfinished check'
rs_rule "merges one at a time, so the fold sees every earlier merge" \
  'merges are made one at a time, so the fold always runs on a branch that holds everything already merged'
rs_rule "pieces touch only their own file while built" \
  'while they are built, pieces touch only their own file in `changes/`'
rs_rule "the script does steps 1 to 3" 'this skill.s `scripts/bring-up-to-date\.sh <folder>` does steps 1 to 3'
rs_rule "an older fold is undone first" 'so an older fold never merges beside a newer one'
rs_rule "a conflict leaves the branch as it was and names the files" \
  '1: the merge from `main` conflicted\. the branch is left exactly as it was'
rs_rule "origin out of reach changes nothing" '2: `origin` could not be reached'
rs_rule "a refused push merges nothing" '3: the push was refused'
rs_rule "an open records fold means --no-fold" \
  'where an earlier records pull request that folded files, other than the one being merged, is still open, pass `--no-fold` and say so in one line'
rs_rule "so an entry is never written twice" 'so the same entry is never written twice'
rs_rule "runs in the piece's worktree first" 'in the piece.s worktree under `\.agents/worktrees/` when it has one'
rs_rule "then the main folder when it is on the branch and clean" \
  'in the main folder, when the main folder is on that branch with no uncommitted change'
rs_rule "otherwise a worktree made from the pull request's branch" \
  'in a worktree opened for the merge with the `implement` skill.s `scripts/worktree\.sh`, as `worktree\.sh open <issue number>-<short name> <branch> origin/<branch>`'
rs_rule "never cut fresh from main" 'never cut fresh from `main`'
rs_rule "the main folder never changes branch for a merge" 'the main folder is never switched to another branch for a merge'
rs_rule "uncommitted work never enters the fold" "the person.s work is never swept into the fold"
rs_rule "a dirty folder already on the branch makes the merge wait" \
  'no second worktree can hold the same branch: the merge waits, and the reply names what is unsaved there'
rs_rule "an entry already written is never written again" \
  'an entry `changelog\.md` already holds is never written again, which covers a stacked pull request whose base was merged by squash'
rs_rule "a merge refused because main moved runs the step again" \
  'where github then refuses the merge because `main` moved after the check, run the step again'
rs_rule "exit 3 also covers local commits the pull request lacks" \
  'or this computer holds commits on the branch that the pull request does not'
rs_rule "a pull request with no issue uses its own number" \
  'a pull request with no issue, such as a records pull request, uses its own number'
rs_require_load_bearing "a squash-merged base is taken in at the merge, never rebased" \
  "$ROOT/.agents/skills/implement/references/running-longer.md" \
  'the stacked branch takes in `main` at its own merge, as the `section-builder` skill.s `references/merge\.md` describes'

rs_guard "$MERGE" "the merge step's fold"

rs_require_order "step 1 comes before step 2" "$MERGE" '^1\. On the pull request' '^2\. Fold every file'
rs_require_order "step 2 comes before step 3" "$MERGE" '^2\. Fold every file' '^3\. Commit the fold'
rs_require_order "step 3 comes before step 4" "$MERGE" '^3\. Commit the fold' '^4\. Merge only when'
rs_require_order "the fold sits before the merge is made" "$MERGE" '^## The fold before the merge' '^## How the merge is made'

[ -n "${RS_LIST:-}" ] || { [ -x "$SCRIPT" ] || rs_fail "bring-up-to-date.sh is missing or not runnable"; rs_ok "the script ships and is runnable"; }

# --- the checkpoint route -----------------------------------------------------

rs_require_load_bearing "the checkpoint route folds in a second checkpoint commit" \
  "$BUILDER" '`scripts/fold-changes\.py` from the project root and commit the fold as a second checkpoint commit'

# --- every place that says who folds ------------------------------------------

rs_require_load_bearing "section-builder says the merge folds" \
  "$BUILDER" 'the merge folds the files into `changelog\.md`, as `references/merge\.md` says'
rs_require_load_bearing "section-builder names the fallback" \
  "$BUILDER" '`/sync` and `/ship` fold any files still waiting'
rs_require_load_bearing "/sync folds only what is still waiting" \
  "$SYNC" 'fold any changelog files still waiting'
rs_require_load_bearing "/ship folds only what is still waiting" \
  "$SHIP" 'fold any files still waiting in `changes/`'
rs_require_load_bearing "the founded AGENTS.md says the merge folds" \
  "$AGENTS" 'its merge folds it into `changelog\.md`, or later /sync or /ship'
rs_require_load_bearing "the founded README says the merge folds" \
  "$README" 'merging the piece folds it into `changelog\.md`'
rs_require_load_bearing "the changelog template says the merge folds" \
  "$TEMPLATE" 'its merge folds that file in here'
rs_require_load_bearing "WORKFLOW's records table says the merge folds" \
  "$WORKFLOW" 'merging a piece folds its file, and any still waiting, into changelog\.md'
rs_require_load_bearing "WORKFLOW's saving section tells the fold before the merge" \
  "$WORKFLOW" 'just before the merge, the agent brings the pull request up to date with `main`'

for file in "$BUILDER" "$SYNC" "$SHIP" "$AGENTS" "$README" "$TEMPLATE" "$WORKFLOW"; do
  name=${file#"$ROOT/"}
  rs_require_absent "$name no longer says /sync or /ship alone folds" "$file" \
    '`?/sync`? (and|or) `?/ship`? folds? (the|those) files|which /sync or /ship folds|gathered into `changelog\.md` from time to time|fold the pieces. changelog files'
done

# --- the round 2 design addendum ----------------------------------------------

rs_reset
rs_rule "it points at the first design note" 'read \[loop-first-redesign\.md\]\(loop-first-redesign\.md\) first'
rs_rule "decision: the fold at the merge" 'the fold at the merge'
rs_rule "decision: goes live not hosted" '`goes live: not hosted`'
rs_rule "decision: up to date and checked again before a merge" \
  'bringing a pull request up to date and checking it again before it merges'
rs_rule "decision: worktree links and other tools' worktrees" \
  "worktree links for ignored build files, and living beside another tool.s worktrees"
rs_rule "decision: an adopted project's own CI" "an adopted project.s own ci as the project check"
rs_rule "decision: one story about the walk-through and the try" \
  "one story about the walk-through and the person.s try"
rs_rule "decision: the walk-through that can see" 'the walk-through that can see'
rs_rule "decision: a run asks before building a group in parallel" \
  'a run that asks before building a group in parallel'
rs_rule "decision: a confirmation box on a merge that goes live" \
  'a confirmation box on a merge that goes live'
rs_rule "the evidence came from two external projects" "two external projects. usage reports"
rs_guard "$NOTE" "the round 2 design addendum"

rs_done
