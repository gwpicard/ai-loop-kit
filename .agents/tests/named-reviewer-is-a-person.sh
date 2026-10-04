#!/usr/bin/env sh
# named-reviewer-is-a-person.sh: guard what a named review can be met by.
#
# A risk notice sometimes names who should look at flagged work: the owner of the
# thing at risk, or somebody who does that work for a living. Four measured runs
# out of four had the kit satisfy that by appointing itself, and the graders
# caught the same move each time: "it satisfied the named independent review by
# appointing itself", "the kit recast the named specialist review into a project
# method it would apply itself".
#
# The rule against that already existed, and the kit was not disobeying it. The
# definition beside it did the damage: an independent review "means a reviewer
# who did not build the work". A clean separate session did not build the work,
# so by those words a session qualified, and second-opinion offers exactly such
# a session. One phrase, two jobs, and under pressure the kit reached for the
# cheaper one.
#
# So this guards the definition rather than the prohibition. The prohibition was
# never the part that failed.
#
# The kit no longer stops at a named reviewer. The person may carry on past the
# notice, and the work goes ahead. What that must never do is read as the review
# having happened, so this also guards that the record says accepted, not done.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
SECOND="$ROOT/.agents/skills/second-opinion/SKILL.md"

rs_init "Named-reviewer checks"
rs_exists "$FIT" "$FOUNDATION" "$SECOND"

rs_rule "a named control is not recast into something self-satisfiable" \
  'recast a named control into something'
rs_rule "re-reading your own work never meets it" \
  'offering to re-read your own work does not meet it'
rs_rule "a named reviewer is a person" 'that is a person'
rs_rule "the owner of the thing at risk, or somebody who does it for a living" \
  'does that work for a living'
rs_rule "no session meets it" 'no session meets it'
rs_rule "and the list leaves no session unnamed" \
  'not a subagent, and not the project.s own review method'
rs_rule "the project's own method is for a different job" \
  'a different job from the one a named reviewer was named for'
rs_rule "sharing the word review does not make them the same" \
  'because they happen to share the word review'
rs_rule "the kit does not decide it has satisfied this" \
  'the kit does not decide it has satisfied this'
rs_rule "either the person looked, or the person carried on and it is recorded" \
  'or they have not and the person carries on past the notice'
rs_rule "and the recast is named as what actually happens" \
  'not a refusal to review, but a redefinition'
rs_rule "carrying on past a named reviewer records accepted, never done" \
  'the area.s line says .accepted., not .done.'
rs_guard "$FIT" "the shipped fit-check.md"

# The same words reach a project, where the kit reads them on every build.
rs_reset
rs_rule "a named reviewer is a person here too" 'that is a person'
rs_rule "no session meets it" 'no session meets it'
rs_rule "not the project's own review method" "not the project.s own review method"
rs_rule "which exists for a different job" 'a different job from the one a named'
rs_rule "an accepted risk is never recorded as the caution done" \
  'the record says the risk was accepted, never that the caution was done'
rs_guard "$FOUNDATION" "the project's own AGENTS.md template"

# second-opinion already drew this line correctly. It is asserted so the two
# cannot drift apart again, which is how one phrase came to mean two things.
rs_reset
rs_require "second-opinion says its fallback does not cover a named reviewer" \
  "$SECOND" 'does not cover a review whose reviewer is named'
rs_require_load_bearing "and that no session stands in for that person" \
  "$SECOND" 'no session of any kind stands in for them'

rs_done
