#!/usr/bin/env sh
# structure-read.sh: guard the rules of the quarterly structure read.
#
# structure-read-rehearsal.sh runs the comparison. This half reads back what
# the run cannot show. The earlier state is derived again from history and
# never kept. A loop that was already there is not news. A reliability finding
# is only ever a missing pattern at a named place. And a comparison that could
# not happen says so rather than passing for "nothing got worse".
#
# The shared rules file carries the earlier-state clause because this read is
# the one that needed it. Keeping a copy of an earlier graph would have been
# the easy route, and the saved-index rule exists because a stale copy answers
# confidently and wrongly.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READ="$ROOT/.agents/skills/maintain/references/structure-read.md"
SHARED="$ROOT/.agents/skills/setup-ai-build-kit/references/whole-project-reads.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Structure read rules"
rs_exists "$READ" "$SHARED" "$MAINTAIN" "$WORKFLOW"

rs_rule "it follows the shared rules" 'whole-project-reads\.md` apply'
rs_rule "it does not run on Explore privately" 'not on explore privately'
rs_rule "the last engine is reading the imports" 'read the imports directly, limited to the areas'
rs_rule "one engine for both sides" 'use the same engine for both sides of the comparison'
rs_rule "the earlier state is derived, not kept" 'the earlier state is derived again, every time'
rs_rule "the first visit compares with the first commit" "use the project's first commit"
rs_rule "the copy only reads history" 'this only reads the saved history'
rs_rule "a failed comparison is said" 'the structure comparison did not happen'
rs_rule "loops compare as sets of files" 'compare the loops as sets of files'
rs_rule "an old loop is not news" 'a loop that was already there at the last visit is not news'
rs_rule "the place is the import line" 'find the line in each file where it imports the next one'
rs_rule "reliability is a missing pattern" 'say it as a missing pattern at a named place'
rs_rule "no reliability verdict either way" 'never say the tool is unreliable, and never say it is reliable'
rs_rule "the cap of three is shared" 'the cap of three proposals holds for all of them together'
rs_rule "nothing worse is complete and silent" 'when nothing got worse, say nothing about structure'
rs_guard "$READ" "the shipped structure-read.md"

rs_require_load_bearing "the shared rules derive an earlier state rather than keep it" "$SHARED" 'derive that state again from the project.s saved history'
rs_require_load_bearing "the quarterly step loads the read" "$MAINTAIN" 'load `references/structure-read\.md`'
rs_require "WORKFLOW says the earlier structure is read again" "$WORKFLOW" 'the earlier structure is read again from the saved history each time'

rs_done
