#!/usr/bin/env sh
# check-up-counts-work.sh: guard the written half of the reminder that counts
# work as well as days.
#
# The reminder script itself is rehearsed in session-start.sh, which runs it
# in a throwaway project with dated changes. What a rehearsal there cannot
# reach is the prose around it. /what-now has to take its answer from the
# script, or a session that opens quietly and a /what-now that says a visit is
# overdue would disagree. /maintain has to offer the newer script to a project
# that kept the old one, since an update refreshes skills and never the
# project's copy. And WORKFLOW.md has to say days or changes, whichever comes
# first, or a person reminded after a busy week has no idea why.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
HOOK="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh"

rs_init "Check-up counts work"
rs_exists "$WHATNOW" "$MAINTAIN" "$WORKFLOW" "$HOOK"

# /what-now takes its answer from the script, so the two always agree.
rs_rule "what-now runs the script in its plain mode" \
  'run `\.agents/hooks/session-start\.sh` with no options, its plain mode, and take its answer'
rs_rule "the script counts both days and changes" \
  'it counts both the days and the changes landed since the last visit'
rs_rule "the dates are read only where the script is missing" \
  'only where the project has no such script, take it from `\.ai-build-kit-maintenance`'
rs_guard "$WHATNOW" "the what-now skill"

# /maintain offers the newer script to a project that kept the old one.
rs_reset
rs_rule "a differing script is noticed" \
  'where the project has the script and it differs from that template'
rs_rule "the offer is one line" \
  '"a newer reminder script counts the work landed since the last visit as well as the days\. shall i replace yours\?"'
rs_rule "the offer says a hand change goes too" \
  'replacing it also drops any change made to the project.s copy by hand'
rs_rule "it is replaced only on a yes" 'replace it only on a yes'
rs_rule "no offer after a request for no kit updates" \
  'make no offer when the person asked for no kit updates'
rs_rule "a no changes nothing and the offer returns" \
  'a no changes nothing, and the next visit makes the same one-line offer again'
rs_guard "$MAINTAIN" "the maintain skill"

# WORKFLOW.md tells it.
rs_reset
rs_rule "days or changes, whichever comes first" \
  'or once 20 changes have landed since the last visit, whichever comes first'
rs_rule "the count is read from this computer" \
  'counts only what this computer already holds'
rs_rule "an older project is offered the newer script" \
  'a project whose reminder script came before the change count is offered the newer one'
rs_guard "$WORKFLOW" "WORKFLOW.md"

# The script holds the number the prose names.
rs_require "the script speaks at 20 changes" "$HOOK" 'changes_since_visit=20'

rs_done
