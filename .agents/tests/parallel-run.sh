#!/usr/bin/env sh
# parallel-run.sh: guard the question a run asks before it builds a group's
# pieces at the same time, and the rules that hold once the person says yes.
#
# A run used to build its pieces one after another, whatever /queue's groups
# said. People who took on several pieces wanted them built at once, and when
# the kit offered nothing they built their own coordinator, with the kit's
# steps pasted into a brief. The rules travelled only as far as the brief
# remembered them: claims were skipped, reviews were skipped, and a merge went
# ahead on a standing yes.
#
# So on Claude Code the run asks, warns that it uses more memory, and builds one
# at a time unless the person gives a number. The session that started the run
# stays the only one that claims, writes the run state, reviews, opens pull
# requests and merges. A background agent builds one piece and reports back. A
# machine cannot watch a run without paying a model, so this check reads the
# rules back and proves each one load-bearing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
LONGER="$SKILLS/implement/references/running-longer.md"
IMPLEMENT="$SKILLS/implement/SKILL.md"
QUEUE="$SKILLS/queue/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"

rs_init "Parallel run checks"
rs_exists "$LONGER" "$IMPLEMENT" "$QUEUE" "$WORKFLOW" "$COMPAT"

# --- the capability rule ----------------------------------------------------

rs_rule "one at a time is the default everywhere" \
  'one piece at a time is the default on every coding agent'
rs_rule "on Claude Code the person may choose more" \
  'on claude code the person may choose more'

# --- the question -----------------------------------------------------------

# Asked in the same reply as the merge question, only on Claude Code, and only
# when the plan holds a group a run can take two pieces of.
rs_rule "the question rides with the merge question" \
  'ask one more question in the same reply as the merge question'
rs_rule "only with a group of two or more pieces the run can take" \
  'where the plan holds a `go together` group of two or more pieces the run can take'
rs_rule "the question, word for word" \
  'build the pieces in a group at the same time\? each one runs its own install and its own copy of the tool, so this uses more memory, and on a machine with little memory it can crash it\. one at a time is the default\. say how many at once if you want more than one\.'
rs_rule "not asked on another agent, an older Git, or with no group" \
  'on any other coding agent, where git is older than 2\.17, or where the plan holds no such group, do not ask'
rs_rule "no answer or silence means one at a time" \
  'no answer, or silence, means one at a time'
rs_rule "the answer is bounded by the largest group" \
  'a number from 1 up to the size of the largest group in the plan'
rs_rule "a larger number is taken as that size, and the reply says so" \
  'a larger number is taken as that size, and the reply says so'
rs_rule "zero or words mean one at a time, said in one line" \
  'zero, or words that are not a number, mean one at a time, said in one line'

# --- the state file ---------------------------------------------------------

rs_rule "field: at_once in the example" '"at_once": 1'
rs_rule "at_once is defined and bounded" \
  '`at_once` is how many pieces of one group are built at the same time'
rs_rule "at_once holds for this run and is kept on resume" \
  'like `merge_preapproved`, it holds for this run alone and is kept when the run is resumed'

# --- building a group at the same time --------------------------------------

rs_rule "the section exists" '## building a group at the same time'
rs_rule "only pieces of one group run at once" \
  'only pieces in the same `go together` group run at the same time'
rs_rule "never more than at_once agents" \
  'never more than `at_once` background agents at once'
rs_rule "a stacked piece is built after its base" \
  'a piece that stacks on another is never in its base.s group, so it is built after its base, never alongside it'
rs_rule "the coordinating session claims each piece itself" \
  'the coordinating session makes the claim itself, one piece at a time, as step 1 says'
rs_rule "the worktree is opened before the agent starts" \
  'opens the piece.s worktree with `worktree\.sh open` and takes its port with `worktree\.sh port`, before it starts that piece.s background agent'
rs_rule "each agent is given the number, worktree, port and run name" \
  'it is given the piece.s number, its worktree path, its port and the run name'
rs_rule "each agent does steps 3 to 6 in its worktree" \
  'it loads section-builder and does steps 3 to 6 of "for each piece" inside its worktree'
rs_rule "each agent commits and reports back" \
  'it commits its work on the piece.s branch and reports back'
# A pushing agent would make a first upload nobody was asked about, and push a
# checkpoint-route piece that must stay on this computer.
rs_rule "a background agent never pushes" \
  'it never pushes, since a first upload waits for the person and the checkpoint route stays on this computer'
rs_rule "the groups are taken in the plan's order" \
  'the groups are taken in the plan.s order'
rs_rule "a smoke failure on main starts no new agent" \
  'start no new agent, wait for the ones still building to report'
rs_rule "a background agent never reviews a piece" \
  'it never reviews any piece'
rs_rule "the coordinating session runs each review" \
  'the coordinating session starts that piece.s independent review itself, as step 7 says'
rs_rule "the coordinating session opens each pull request, one at a time" \
  'it then opens the pull request and writes the changelog file, as steps 8 and 9 say, one piece at a time'
rs_rule "a background agent never meets a named review" \
  'a background agent never meets a named review'
rs_rule "one writer of the run state" \
  'the coordinating session is the only writer of `state\.json`, `progress\.md` and the live page'
rs_rule "only the coordinating session moves to to check and merges" \
  'it moves each piece to `to check`, and only it merges, one pull request at a time'
rs_rule "two pieces finishing during a merge merge one after the other" \
  'where two pieces finish while a merge is under way, it merges them one after the other, each checked again'
rs_rule "an agent that never reports is a failed attempt" \
  'a background agent that ends without reporting back counts as a failed attempt at its piece'
rs_rule "the same file despite different Touches goes to /fix by the merge rule" \
  'the second merge.s check against the latest `main` then finds the conflict, and the `section-builder` skill.s `references/merge\.md` takes it to `/fix`'
rs_rule "a walk-through that cannot get the browser could not look" \
  'where a walk-through cannot get the browser because another agent holds it, it records that it could not look'

# --- resuming ---------------------------------------------------------------

rs_rule "resuming keeps at_once" 'so does its `at_once`'
rs_rule "the resume offer names the number and it can be lowered" \
  'the offer to resume names that number and says the person can lower it in their reply'
rs_rule "a dead session leaves each piece building with its worktree" \
  'the state file shows each of them `building` with its worktree'

rs_guard "$LONGER" "running-longer.md"

# The old promise is gone.
rs_require_absent "the capability rule no longer rules out background agents" \
  "$LONGER" 'no background agents'

# --- the story in the other places -----------------------------------------

rs_require_load_bearing "/implement says the run asks" "$IMPLEMENT" \
  'the run asks once whether to build a group.s pieces at the same time'
rs_require_load_bearing "/queue says the run asks and the default" "$QUEUE" \
  '`/implement queue` builds one piece at a time by default, whatever the groups say\. on claude code it asks before the run starts'
rs_require_absent "/queue no longer says a run always builds one at a time" \
  "$QUEUE" 'still builds the whole plan one piece at a time'
rs_require_load_bearing "WORKFLOW's /queue paragraph says the run asks" "$WORKFLOW" \
  'a run builds the plan one piece at a time unless you choose otherwise'
rs_require_load_bearing "WORKFLOW's run section tells the question" "$WORKFLOW" \
  'the run also asks whether to build a group.s pieces at the same time'
rs_require_load_bearing "WORKFLOW says each piece still gets every step" "$WORKFLOW" \
  'each piece built alongside others still gets every step of a single build, its own review and its own pull request'
rs_require_absent "WORKFLOW no longer says a run always builds one at a time" \
  "$WORKFLOW" 'a run still builds the whole plan one piece at a time'
rs_require_load_bearing "COMPATIBILITY says only Claude Code offers it" "$COMPAT" \
  'only claude code offers to build a group.s pieces at the same time'
rs_require_load_bearing "COMPATIBILITY says the older Git is not asked" "$COMPAT" \
  'on claude code with git older than 2\.17, the run does not ask'

rs_done
