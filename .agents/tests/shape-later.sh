#!/usr/bin/env sh
# shape-later.sh: guard when /shape shapes now and when it files a piece for later.
#
# The kit once offered "settle it now, or file it for later" every time a request
# routed to a question. A person who typed /shape had already chosen to shape, so
# the offer asked them the same thing twice, and somebody who only wanted to note
# an idea sat through triage and routing and then the offer as well. So /shape
# now starts the step, says in one line when that step is a whole sitting, and
# files the piece when the person says "later" or asks for a note in the first
# place.
#
# Two failures matter, and they pull against each other. A /shape that drifts
# back to asking first puts the double question back. A filing route with
# nothing that points at the backlog afterwards is worse still: pieces pile up
# and no session ever calls itself a planning one. So the filing rules and the
# /what-now half are guarded together here, and neither can be dropped without
# this check failing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Shape-now and file-for-later checks"
rs_exists "$SHAPE" "$TRIAGE" "$PIECES" "$WHATNOW" "$WORKFLOW"

# The route itself. Remove any one of these and /shape either asks before it
# starts, which is the double question back again, or files a piece so thin
# that coming back to it means starting again.
rs_rule "typed with words, /shape shapes now" 'typed with words, this command shapes now'
rs_rule "because asking again is the same question twice" 'asks the same question twice'
rs_rule "a routed question starts its step" 'start the step the route names'
rs_rule "a sitting is named in one line and then started" 'takes a sitting, so say so in one line and start'
rs_rule "the person can say later mid-step" 'can say "later" at any point in a step'
rs_rule "what the step agreed goes onto the filed piece" 'anything the step has already agreed written onto it'
rs_rule "filing can be asked for outright" 'note this for later'
rs_rule "a note starts no step" 'file it without starting any step'
# A note asked for outright used to be routed and, when it was clear, written
# as a ready piece. Now it is captured through the gate as a raw piece in the
# person's words with nothing settled, because the person asked to write it
# down, not to have it shaped.
rs_rule "a note asked for outright is captured raw" \
  'through the gate as a piece in `shaping:raw`, in their own words, with nothing settled'
rs_rule "filing is not a new command" 'it is not a separate command'
rs_rule "the filed piece keeps the person's own words" "the person's own words"
rs_rule "it carries the question in plain language" 'the question it still waits on in plain language'
rs_rule "a fresh session can pick it up" 'a fresh session picks it up with nothing lost'
rs_rule "the session stops rather than starting the step" 'do not begin the step'
rs_rule "a filed piece has the sub-state of its question and no ready label" 'carries the sub-state that names its question and no `state:ready` label'
rs_rule "deferring never opens a route into /implement" 'never lets the piece be built with the question still open'
rs_guard "$SHAPE" "the /shape skill"

# The rule this check replaced. Put back, it would sit beside "shapes now" and
# the two would contradict each other with every rule above still present.
rs_require_absent "/shape no longer makes the offer every time" \
  "$SHAPE" 'every time a request routes to a question'
rs_require_absent "nor offers the choice before the step starts" \
  "$SHAPE" 'offer the choice before'

rs_require_absent "a note asked for outright is no longer written as a ready piece" \
  "$SHAPE" 'simply a ready piece'

# Without these the two files disagree about whether a routed question starts
# now, which is the contradiction this check exists to hold shut, and a request
# for a note would never reach /shape marked as one.
rs_require_load_bearing "change-triage says /shape starts the step unless asked to file" \
  "$TRIAGE" 'unless the person asked only to file the piece'
rs_require_load_bearing "change-triage recognises a request to file" \
  "$TRIAGE" 'just file this idea'
# A note that repeats an earlier piece goes onto that piece, whether it is open
# or closed, and closed for either reason. Searching only the ideas left out
# missed a note repeating a piece already built, and filed it twice.
rs_require_load_bearing "a note matching an open or closed piece goes onto that piece" \
  "$TRIAGE" 'where it matches an open piece, or a closed one whether completed or not planned'

# The cost is what the one-line warning before a sitting draws on.
rs_reset
rs_rule "the waiting labels cost different amounts" 'cost different amounts to settle'
rs_rule "a sitting is named before it starts" 'names the cost in one line before it starts a sitting'
rs_rule "research is minutes" 'is minutes, and nobody has to'
rs_rule "an interview or a prototype is a sitting" 'are a sitting'
rs_rule "the estimate stays coarse" 'guess dressed as a number'
rs_guard "$PIECES" "pieces.md"

# The half that stops a silent backlog. A way to file without this makes things
# worse than leaving both out.
rs_reset
rs_rule "waiting pieces are weighed against ready ones" 'weigh the waiting pieces against the ready ones'
rs_rule "it never outranks something broken" 'never ahead of anything broken'
rs_rule "it says when the session is a planning one" 'better spent planning than building'
rs_rule "it stays quiet when ready pieces outnumber waiting ones" 'say nothing about it and let the usual advice stand'
rs_guard "$WHATNOW" "the /what-now skill"

rs_require "/shape's Done when records that a routed question was started" \
  "$SHAPE" 'started unless the person asked to file it'
rs_require "WORKFLOW.md says typing /shape is the choice to shape" \
  "$WORKFLOW" 'typing /shape is the choice to shape'
rs_require "WORKFLOW.md says you can say later mid-step" \
  "$WORKFLOW" 'you can say "later" at any point'
rs_require "WORKFLOW.md says a note starts nothing" \
  "$WORKFLOW" 'it is filed with nothing started'
rs_require_absent "/shape no longer files an idea label" "$SHAPE" 'labelled `idea`'
rs_require "and says a filed piece still cannot be built" \
  "$WORKFLOW" 'nothing filed can be built until the question is answered'

rs_done
