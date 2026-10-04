#!/usr/bin/env sh
# coverage-read.sh: guard the read that compares the masterplan against the
# pieces.
#
# The masterplan says what the tool must do and the pieces say what gets built.
# The coverage read compares them at the end of founding and inside /sync, says
# what nothing would build, and changes nothing by itself. A
# machine cannot watch that conversation without paying a model, so this guards
# its source on every push: the rules that keep the read honest, the two
# commands that call it, and the plain explanation a person actually reads.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READFILE="$ROOT/.agents/skills/setup-ai-build-kit/references/coverage-read.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Coverage-read checks"

rs_rule "the read applies to every path" 'it runs on every build path'
rs_rule "permissions are checked as promises" 'include who can see and do what'
rs_rule "data and its origin are checked" 'what data it holds and where it comes from'
rs_rule "outside connections are checked" 'and what it connects to'
rs_rule "counts pieces open and closed" 'open and closed'
rs_rule "the line said when the plan covers the page" 'has a piece that builds it\."'
rs_rule "a promise left to a parked piece is a gap" 'parked counts as a gap'
rs_rule "reads each piece's change to the masterplan" 'read each piece.*masterplan change.*alongside its promised result'
rs_rule "a missing applied change is recovery rather than a new piece" 'it must not be offered as a new piece'
rs_rule "the read compares key terms against decisions and planned changes" 'compare the masterplan.s key terms with settled terms in every piece.s `## decided` and `## masterplan change`'
rs_rule "parked and reshaped pieces keep their terms visible" 'including parked and reshaped pieces'
rs_rule "missing and different terms are record gaps" 'name a settled term missing from the masterplan, or one whose meaning differs, as a record gap'
rs_rule "a settled name cannot promise a future capability" 'do not turn a future capability into a present promise'
rs_rule "a clean report also requires the terms to agree" 'when every promise has a piece and no term is missing or different'
rs_rule "terms share the existing list and offer" 'include missing or different terms in that same short list and single offer'
rs_rule "term reconciliation requires a yes" 'with a yes, /sync reconciles the term against the current tool'
rs_rule "the piece keeps its note until reconciliation" 'keep the note on its piece until that happens'
rs_rule "future terms stay on their pieces" 'a term for work that is still only planned stays on its piece'
rs_rule "declining or silence preserves both records" 'a declined or unanswered offer leaves both records alone'
rs_rule "never names a promise that is not on the page" 'not on the page'
rs_rule "never adds a piece without a yes" 'without a yes'
rs_rule "never edits or closes a piece by itself" 'never edits, closes'
rs_rule "offers once rather than repeatedly" 'one offer'
rs_rule "reports and stops on explore privately" 'explore privately'
rs_guard "$READFILE" "the shipped coverage-read.md"

rs_require "/setup runs the coverage read once the pieces are cut" \
  "$SETUP" 'references/coverage-read\.md'
rs_require "/sync runs the coverage read while reconciling" \
  "$SYNC" 'coverage-read\.md'

# The house rule is that a behaviour is told in three places or it is not
# finished. The skills carry two of them; WORKFLOW.md carries the plain one, in
# both the founding and the sync sections.
rs_require_twice "WORKFLOW.md explains it for founding and for sync" \
  "$WORKFLOW" 'piece that builds it'
rs_require_load_bearing "WORKFLOW names the wider founding read" \
  "$WORKFLOW" 'the coverage read includes who can see and do what, the data the tool holds, and its outside connections'
rs_require_load_bearing "WORKFLOW names the wider sync read" \
  "$WORKFLOW" 'the coverage read includes permissions, data and outside connections here too'
rs_require_load_bearing "WORKFLOW explains that parking cannot hide terms" \
  "$WORKFLOW" 'it also compares settled terms on every piece with the masterplan, even if a piece was parked or reshaped'

rs_done
