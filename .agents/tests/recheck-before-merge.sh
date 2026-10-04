#!/usr/bin/env sh
# recheck-before-merge.sh: guard the rule that no pull request merges on a check
# that ran against an older `main`.
#
# A green check says a pull request passed against the `main` it was cut from.
# Once another pull request merges, that answer is out of date. On an outside
# project two pull requests merged one after the other, each green, and together
# they turned `main` red; the agent then called merging over the red `main` its
# own mistake. The kit's end-of-run sweep merged every piece whose check was
# green, one after another, with no check against the `main` the earlier merges
# had just made, and `/queue` told the person a group could merge in any order.
#
# So every merge now brings the branch up to date and waits for the check on
# that commit, the sweep finishes one merge before it starts the next, and no
# file promises a group can merge in any order. The rules are prose a coding
# agent reads, so this reads them back and proves each one load-bearing. What
# the shipped script does to two branches that pass alone is rehearsed in
# recheck-before-merge-rehearsal.sh.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
MERGE="$SKILLS/section-builder/references/merge.md"
LONGER="$SKILLS/implement/references/running-longer.md"
QUEUE="$SKILLS/queue/SKILL.md"
PIECES="$SKILLS/setup-ai-build-kit/references/pieces.md"
HELPER="$SKILLS/setup-ai-build-kit/templates/foundation/plan-refresh.sh"
SYNC="$SKILLS/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Re-check before the merge checks"
rs_exists "$MERGE" "$LONGER" "$QUEUE" "$PIECES" "$HELPER" "$SYNC" "$WORKFLOW"

# --- the merge step -------------------------------------------------------------

rs_rule "every merge is brought up to date and checked again" \
  'every merge, fold or no fold, first brings the branch up to date with `main` and checks it again'
rs_rule "it waits for the check on the commit the script prints" \
  'wait for the project check on the commit its last line prints'
rs_rule "the check is the one on github, never a local run" \
  'the check waited on is the project check on github, never a run on this computer'
rs_rule "no movement and nothing to fold makes no commit" \
  'the script makes no commit and prints the head the branch already has'
rs_rule "then the green check on that head stands" \
  'the green check already on that head stands, with no second wait'
rs_rule "a piece's own changelog file is always left to fold" \
  "a piece.s own file in \`changes/\` is always left to fold"
rs_rule "a check that has not reported makes the merge wait" \
  'because it is queued or github is slow, the merge waits: say so once in the reply'
rs_rule "a conflict gets one comment on the pull request" \
  'add one comment to the pull request naming them'
rs_rule "a conflict goes to /fix as a red check does" \
  'take the piece to `/fix`, as a red check is'
rs_rule "red only after the update says it passed alone" \
  'say that the piece passed alone and fails with what merged since'
rs_rule "it names what merged since the last green check" \
  'git log --first-parent --oneline <old base>\.\.origin/main'
rs_rule "the old base is where the checked head met main" \
  'the old base is `git merge-base <head before the update> origin/main`'
rs_rule "red only after the update goes to /fix" 'where the subject names only the branch\. take it to `/fix`'
rs_rule "origin out of reach merges nothing" \
  'where `origin` cannot be reached, the script exits 2 and nothing changed'
rs_rule "a stacked pull request is re-aimed, then brought up to date" \
  'then bring it up to date and check it again, as above, before you merge it'
rs_rule "pre-approval needs green on the up-to-date commit" \
  '1\. its project check is green on the commit brought up to date with `main`'
rs_guard "$MERGE" "the merge step"

rs_require_order "the re-check sits before the merge is made" "$MERGE" \
  'fold or no fold' '^## How the merge is made'

# --- the run's sweep -------------------------------------------------------------

rs_reset
rs_rule "the sweep merges one piece at a time, each whole" \
  'merge them one at a time: each one.s update, its check and its `gh pr merge` finish before the next piece is brought up to date'
rs_rule "a piece that conflicts or turns red stays in to check with its reason" \
  'is not merged\. it stays in `to check`, and its `reason` says which of the two happened'
rs_rule "the sweep goes on, skipping what stacks on it" \
  'the sweep goes on with the pieces that do not stack on it, and skips each one that does, with that reason'
rs_rule "the report says how long the sweep waited" 'how long the sweep waited for checks'
rs_rule "the other five conditions are tested before the update" \
  'test the other five before bringing a piece up to date'
rs_rule "a conflict in the sweep still gets its comment" 'a conflict still gets its one comment on the pull request'
rs_require_load_bearing "/sync says when no run was ever green" "$SYNC" 'where no run has ever been green'
rs_guard "$LONGER" "the run's sweep"
rs_require_absent "the sweep no longer merges on a check that is merely green now" "$LONGER" \
  'merge each one whose project check is now green'

# --- the groups ------------------------------------------------------------------

rs_require_load_bearing "/queue says a group is built in any order" "$QUEUE" \
  'can be built at the same time in any order'
rs_require_load_bearing "/queue says each still merges one at a time after the re-check" "$QUEUE" \
  'each still merges one at a time, brought up to date with `main` and checked again first'
rs_require_load_bearing "pieces.md says a group is built in any order" "$PIECES" \
  'can be built at the same time in any order'
rs_require_load_bearing "pieces.md says each still merges one at a time after the re-check" "$PIECES" \
  'each still merges one at a time, brought up to date with `main` and checked again first'
rs_require_load_bearing "the helper's comment says a group is built in any order" "$HELPER" \
  'can be built at the same time in any order'
rs_require_load_bearing "the helper's comment says each merges one at a time after the re-check" "$HELPER" \
  'each still merges one at a time, brought up to date'
rs_require_load_bearing "WORKFLOW says a group is built in any order" "$WORKFLOW" \
  'can be built at the same time in any order'
rs_require_load_bearing "WORKFLOW says each still merges one at a time after the re-check" "$WORKFLOW" \
  'each still merges one at a time, brought up to date with `main` and checked again first'

if [ -z "${RS_LIST:-}" ]; then
  found=""
  for file in $(find "$SKILLS" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' \)) "$WORKFLOW"; do
    if rs_fold "$file" | tr -d '#' | tr -s ' ' | grep -qE 'merge in any order'; then
      found="$found ${file#"$ROOT/"}"
    fi
  done
  [ -z "$found" ] || rs_fail "a kit file still says a group can merge in any order:$found"
  rs_ok "no skill, template or WORKFLOW.md says a group can merge in any order"
fi

# --- the merge step's story in WORKFLOW -----------------------------------------

rs_require_load_bearing "WORKFLOW says every merge is brought up to date" "$WORKFLOW" \
  'up to date with `main`, on every merge whether or not there is anything to fold'
rs_require_load_bearing "WORKFLOW says a piece green alone can fail with what merged since" "$WORKFLOW" \
  'passed alone and fails with what merged since'
rs_require_load_bearing "WORKFLOW says the sweep merges one at a time" "$WORKFLOW" \
  'a pre-approved run merges its pieces one at a time'

# --- /sync reads the check on main -----------------------------------------------

rs_require_load_bearing "/sync reads the newest check run on main" "$SYNC" \
  'gh run list --branch main --workflow <file> --limit 1 --json status,conclusion'
rs_require_load_bearing "/sync names a run still going as waiting" "$SYNC" \
  'a run still in progress is named as waiting, never as a finding'
rs_require_load_bearing "/sync leads with a red main" "$SYNC" \
  'where the finished run is red, it leads the findings'
rs_require_load_bearing "/sync names what merged since the last green run" "$SYNC" \
  'name the pull requests merged since the last green run'
rs_require_load_bearing "/sync points a red main to /fix" "$SYNC" \
  'sync fixes no code, so point to `/fix`'
rs_require_load_bearing "WORKFLOW says /sync reads a red main first" "$WORKFLOW" \
  '/sync reads the newest check on `main`'

rs_done
