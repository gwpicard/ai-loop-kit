#!/usr/bin/env sh
# triage-overlap.sh: guard the warning that two pieces would be built in the
# same place.
#
# change-triage already reads the pieces for a duplicate and for a parked idea.
# It now also names an open piece that would be built where this request is
# going, before it routes anything. The failure modes are quiet
# ones: the check disappears, or it grows into a pause on every request, which
# teaches people to skip the pause.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Triage overlap checks"
rs_exists "$TRIAGE" "$WORKFLOW"

rs_rule "compares against the open pieces sharing a subject" \
  'open pieces that carry one of the same'
rs_rule "looks at what somebody is building now" 'labelled .building.'
rs_rule "reads titles and the outcome line" 'so that. lines'
rs_rule "names the clash before routing" 'name it before routing'
rs_rule "blocks nothing" 'nothing is blocked'
rs_rule "leaves the decision with the person" 'the person decides'
rs_rule "stays silent when nothing is shared" 'say nothing where no open piece'
rs_rule "does not pause on every request" 'skip the pause'
rs_guard "$TRIAGE" "change-triage"

# Position matters: named after Step 4 has routed, the warning arrives once the
# work is already under way.
rs_require_order "the overlap is named before the routing step, not after" \
  "$TRIAGE" 'name it before routing' '^## Step 4: Route'

rs_require "WORKFLOW.md explains it in plain words" \
  "$WORKFLOW" 'built in the same place'

rs_done
