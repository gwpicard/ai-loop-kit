#!/usr/bin/env sh
# ship-merges-and-deploys-once.sh: guard how /ship merges and deploys.
#
# Two real runs went wrong at the same step. In one, the person said only "put
# it live", and /ship merged two pull requests nobody had named to them. In the
# other, /ship cut a deploy's output short, could not tell whether it had
# worked, and deployed again, so the same version was live twice and the
# earlier build a rollback would reach was gone. It also listed warnings again
# that it had already given in the same visit.
#
# Two more came from the same launch. With GitHub out of reach, the kit merged
# on this computer and pushed `main`. With GitHub in reach, it merged properly
# but pushed its changelog entries and a later confirmation straight to `main`,
# saying they only changed the record. So a merge is made on the pull request,
# and the launch records take the save route a piece takes, on a pull request of
# their own that needs its own yes.
#
# Each rule here is prose an agent reads, and its absence would not show on
# screen until the next run did the same thing again.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHIP="$ROOT/.agents/skills/ship/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Ship merge and deploy rules"
rs_exists "$SHIP" "$WORKFLOW"

# Where the rules reach.
rs_rule "go-live points at the merge and deploy rules" 'any merge or deploy on the way follows "merging and deploying" below'
rs_rule "the rules hold on every path that goes live" 'these rules hold at every go-live, on a recipe or off one, and on build with care as well'

# The merge itself. The rule that a merge waits for a yes naming it, is made on
# the pull request, and waits when GitHub cannot be reached lived here until
# every route needed it. It moved to section-builder's references/merge.md,
# and one-merge-step.sh guards it there. /ship keeps the pointer, so a launch
# that merges still reaches the rule.
rs_rule "every merge follows the one merge step" 'any merge follows the `section-builder` skill.s `references/merge\.md`, as it does on every route'

# How the launch records are saved.
rs_rule "the records take the build path's save route" 'take the save route the build path already requires: the three routes section-builder names, with no fourth for records'
rs_rule "the records include a later confirmation" 'a confirmation the person gives later'
rs_rule "a checkpoint commit is enough on the checkpoint route" 'on the checkpoint route, a checkpoint commit is enough'
rs_rule "one branch for each ship, cut from the current main" 'one branch for this /ship, cut from the up-to-date `main`'
rs_rule "only ship's own files are staged" 'stage only the files /ship itself changed'
rs_rule "the records get one pull request, once, after the launch is checked" 'open one pull request for them, once, after the launch is checked and its records are written'
rs_rule "its yes is asked in the reply that reports the launch" 'ask for its yes in the reply that reports the launch'
rs_rule "an unreachable github keeps the records on their branch" 'where github cannot be reached, save the records on that branch, note in one plain line the step that did not happen, and open the pull request once github is reachable'
rs_rule "records are never pushed straight to main" 'never push records straight to `main`'
rs_rule "a later confirmation joins the open records branch, or a new one" 'a later confirmation joins that branch while its pull request is open, or a new branch and pull request once it has merged'
rs_rule "the records merge follows the merge step" 'the records pull request is a merge like any other, so `merge\.md` applies to it'
rs_rule "the earlier merge yes does not cover it" 'the yes to the earlier merge does not cover it'
# A host that builds every change to main builds the records merge too, and
# that build becomes what a rollback returns to.
rs_rule "a records merge on a building host is one more build" 'where the host builds every change to `main`, merging it starts one more build of the same code and moves the rollback target'
rs_rule "the extra build is said in the line asking for the yes" 'say so in the line that asks for its yes'
rs_rule "leaving it open for the next change is offered" 'offer to leave it open so it goes out with the next change'
rs_rule "the rollback line is corrected before that merge" 'if they say yes, correct the rollback line on that branch before the merge'
rs_rule "merging the records writes no record of its own" 'merging it writes no record of its own'
rs_rule "the person's uncommitted work stays where it is" 'uncommitted work of the person.s stays exactly where it is'
rs_rule "it is never swept into the records commit" 'never sweep it into the records commit'
rs_rule "and never discarded for a clean tree" 'never discard it to get a clean tree'

# The deploy runs once unless it plainly did not go live.
rs_rule "the whole output or the deployment list is read first" 'before you decide a deploy failed, read its whole output, or read the host.s own list of deployments or have it read'
# On a server the kit never contacts, the list comes back as a paste.
rs_rule "an unreachable host's list is read by the person or a companion" 'where the kit cannot reach the host, the person or a companion reads that list and pastes it here'
rs_rule "the output is never cut short" 'never cut the output short'
rs_rule "an unclear result is checked at the live address" 'ask the live address which version it serves'
rs_rule "no second deploy before the first is checked" 'never run a deploy a second time until you have checked that the first did not go live'
rs_rule "a second deploy of one version spends the rollback target" 'a second deploy of the same version replaces the earlier build as the rollback target'
rs_rule "a second deploy is announced before it runs" 'when a second deploy is still needed, say that in one line before you run it'
rs_rule "the rollback line is corrected after it" 'correct the rollback line to match'

# A warning once.
rs_rule "a warning said once is not said again in the same ship" 'a warning said once in a /ship is not said again in that /ship, even when a step runs twice'
rs_rule "a later mention is a pointer to the changelog" 'one line saying the changelog already holds it is enough'
rs_rule "the area risk notice is not caught by it" 'the risk notice for a named area is not a warning'
rs_guard "$SHIP" "ship's merge and deploy rules"

rs_require_order "the rules sit after the recipe checks and before Build with care" "$SHIP" '^#### Merging and deploying$' '^### Build with care$'

# The WORKFLOW lines on the merge itself moved to one-merge-step.sh with the rule.
rs_require_load_bearing "WORKFLOW says ship checks before deploying again" "$WORKFLOW" '/ship checks whether it went live before it tries again'
rs_require_load_bearing "WORKFLOW says a second deploy spends the rollback" "$WORKFLOW" 'a second deploy of the same version leaves nothing older to roll back to'
rs_require_load_bearing "WORKFLOW says a warning is not repeated" "$WORKFLOW" 'a warning you have already heard is not repeated in the same /ship'
rs_require_load_bearing "WORKFLOW says records are saved the way a piece is" "$WORKFLOW" 'the records /ship writes during a launch, such as its changelog entries and a colleague later saying the new version is live, take the same save route as a piece'
rs_require_load_bearing "WORKFLOW says a records merge is one more build" "$WORKFLOW" 'merging it starts one more build and moves the rollback target, and offers to leave it for the next change'
rs_require_load_bearing "WORKFLOW says records get their own pull request, never main" "$WORKFLOW" 'one pull request for each /ship, never straight to `main`'
rs_require_load_bearing "WORKFLOW says the records merge needs its own yes" "$WORKFLOW" 'merging that pull request needs its own yes'
rs_require_load_bearing "WORKFLOW says unsaved work is left alone" "$WORKFLOW" 'kept out of the records and never thrown away'

rs_done
