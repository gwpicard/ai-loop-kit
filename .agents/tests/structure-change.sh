#!/usr/bin/env sh
# structure-change.sh: guard the before-and-after structure comparison.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Structure-change rules"
rs_exists "$BUILDER" "$MAINTAIN" "$WORKFLOW"

rs_rule "takes the baseline before code changes" 'take a small structure baseline before code changes'
rs_rule "uses the reach-check engine" 'load `references/reach-check\.md` and use its current engine'
rs_rule "falls back to reading imports" 'where no engine is present, read those imports directly'
rs_rule "does not save the comparison" 'do not save the baseline as a project file'
rs_rule "compares with the same engine" 'compare the finished structure with the baseline from step 4, using the same engine'
rs_rule "speaks only when structure worsened" 'say one line only when it got worse'
rs_rule "names a new loop without a number" 'this change added a loop between <part> and <part>'
rs_rule "names a crossed boundary" 'this change crossed the boundary around <area>'
rs_rule "stays silent when unchanged" 'when nothing worsened, say nothing'
rs_rule "never shows a score" 'never show a score'
rs_rule "records the person's choice" 'record the choice on the piece and carry on'
rs_guard "$BUILDER" "section-builder's structure comparison"

rs_reset
rs_rule "quarterly spread comes from Git" "read the quarter's landed changes from git"
rs_rule "spread is counted by changed files" 'count the files each change touched in each area'
rs_rule "the count replaces a guess" 'rather than judging them from memory'
rs_rule "the quarterly read is not a score" 'this is a comparison, not a health score'
rs_guard "$MAINTAIN" "maintain's hot-spot count"

rs_require "WORKFLOW explains the one-line comparison" "$WORKFLOW" "compares the tool's structure before and after the build"
rs_require "WORKFLOW says there is no score" "$WORKFLOW" 'there is no score to interpret'

rs_done
