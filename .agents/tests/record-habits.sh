#!/usr/bin/env sh
# record-habits.sh: guard the evidence behind decisions and the trail between
# pieces. Missing support and untouched work can otherwise look settled forever.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Record habit checks"

rs_rule "decisions may name their support on every path" 'a decision in `## decided`, or a key term or decided line in the masterplan, may carry an optional one-line "rests on" clause in plain words\. this applies on every build path'
rs_rule "support names something a later read can find" 'name what supports it: a test, a piece, a source, or a person.s answer with its date'
rs_rule "a clause is not invented to fill a field" 'leave the clause out when there is no evidence to name\. never invent support to fill the line'
rs_rule "the source is checked before use" 'before relying on a clause, read the thing it names against the current branch or source'
rs_rule "a disappeared or contradicted source loses its force" 'a missing or contradicted source no longer supports the decision'
rs_rule "unreachable does not mean gone" 'an unreachable source is unconfirmed, rather than gone'
rs_rule "the person gets one plain line" 'say which in one plain line, without asking the person to read code or understand a test name'
rs_rule "missing evidence cannot silently reverse a decision" 'keep the decision visible until it is settled through the command.s usual route; a missing source is not permission to reverse the decision'
rs_rule "new work names and links to the build that found it" 'when a build uncovers work and files a new piece, write "found while building <piece title>" on the new piece.s surface, with the title linked to the piece that surfaced it'
rs_rule "the originating record links back" 'the originating piece.s record names and links to the new piece too'
rs_rule "shared outcomes remain parts" 'parts of the same outcome stay sub-issues'
rs_rule "different outcomes get a discovery link" 'a find with a different outcome gets the found-while-building link'
rs_rule "discovery alone is not a dependency" 'it gains a blocked-by relationship only if one piece really must land before the other'
rs_rule "discovery cannot expand the current build" 'finding work does not add it to the piece being built'
rs_guard "$PIECES" "the decision and discovery rules"

rs_reset
rs_rule "the masterplan allows the same optional line" 'on every build path, key terms and decided lines may carry an optional one-line "rests on" clause in plain words'
rs_rule "the template points to the decision rules" 'follow the decision rules in the `setup-ai-build-kit` skill.s `references/pieces\.md`'
rs_guard "$TEMPLATE" "the masterplan template"

rs_reset
rs_rule "shape rereads a decision it touches" 'whenever shaping touches a decision, re-read any "rests on" clause in the piece.s `## decided` or the masterplan'
rs_rule "already-ready work still gets the read" 'check what it names before relying on it, including when the piece is already ready'
rs_rule "shape names disappeared support in one line" 'when its support has gone, say in one line: "the rule that a job closes once rested on a test that no longer exists\."'
rs_rule "shape settles the question through its usual route" 'name the actual rule in plain words, then settle any question this opens through the usual shaping route'
rs_guard "$SHAPE" "the shaping read"

rs_reset
rs_rule "building follows the discovery rule when it files work" 'when filing a new piece for work this build uncovers, follow the rule for work found during a build in the `setup-ai-build-kit` skill.s `references/pieces\.md`'
rs_rule "building writes both records" 'put the originating title on the new piece.s surface and name the new piece on the originating record'
rs_rule "building says where the work came from" 'say one line such as "found while building the invoice list\."'
rs_guard "$BUILDER" "the build's discovery record"

rs_reset
rs_rule "sync checks age before changing the records" 'check for stale pieces before correcting their records'
rs_rule "sync reads current open-piece dates on every path" 'on every build path, read the open pieces. last-updated times from github'
rs_rule "the list includes the thirty-day boundary" 'list pieces untouched for at least 30 days once, in one short list by title'
rs_rule "one question covers every listed piece" 'ask once: "for each of these, is it still wanted, should it be parked, or is it done\?"'
rs_rule "each change needs the person's yes" 'change nothing on that list without a yes to the proposed action for that piece'
rs_rule "no answer leaves the piece alone and work continues" 'silence leaves it as it is, and sync carries on without asking again'
rs_rule "age alone cannot change a piece" 'age alone never closes or relabels a piece'
rs_rule "missing dates are not guessed" 'if the dates cannot be read, say the stale-piece check could not be made; do not guess from the local printout'
rs_rule "sync rereads all masterplan support" 're-read every "rests on" clause in the masterplan against what it names'
rs_rule "sync names lost support in one line" 'when its support has gone, say in one line which decision lost its ground'
rs_rule "sync leaves the decision visible for settlement" 'keep the decision on the page and ask what should settle it'
rs_guard "$SYNC" "the sync record checks"

rs_require_order "stale inspection precedes piece corrections" "$SYNC" 'Check for stale pieces' 'Correct the pieces to match reality'
rs_require_load_bearing "WORKFLOW explains evidence rereads" "$WORKFLOW" 'when /shape uses that decision, or /sync checks the masterplan, the agent reads its support again'
rs_require_load_bearing "WORKFLOW explains links in both directions" "$WORKFLOW" 'both pieces link to each other, so you can follow where the work came from'
rs_require_load_bearing "WORKFLOW explains the one stale-work question" "$WORKFLOW" '/sync names open pieces untouched for 30 days in one short list and asks once'
rs_require_load_bearing "WORKFLOW keeps the choice with the person" "$WORKFLOW" 'it changes nothing on that list without your yes'

rs_done
