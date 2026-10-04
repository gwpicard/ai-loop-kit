#!/usr/bin/env sh
# document-bloat.sh: guard the rules of the quarterly read for documents that
# repeat each other or are no longer needed.
#
# document-bloat-rehearsal.sh runs the script. This half reads back what the
# script cannot enforce: that the read stays off Explore privately, reads every
# document rather than only the ones AGENTS.md points at, never offers the
# README for deletion, confirms each finding before the person sees it, offers
# a tidy-up rather than making one, shares the cap of three proposals, and says
# plainly that it cannot find two documents saying one thing in different
# words.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READ="$ROOT/.agents/skills/maintain/references/document-bloat.md"
SCRIPT="$ROOT/.agents/skills/maintain/scripts/document-bloat.py"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Document bloat rules"
rs_exists "$READ" "$SCRIPT" "$MAINTAIN" "$WORKFLOW"

rs_rule "it follows the shared rules" 'whole-project-reads\.md` apply'
rs_rule "it does not run on Explore privately" 'not on explore privately'
rs_rule "it reads every document" 'every markdown document the project saves, not only the ones agents\.md points at'
rs_rule "the records and kit files are left out" 'the kit.s own files, and anything in a folder whose name starts with a dot are left out'
rs_rule "a README is never unreferenced" 'a readme is never one of these'
rs_rule "stale names are left to the sync read" 'a document that names things the project no longer has is not counted here'
rs_rule "the shipped script is an engine" '`python3 <skill folder>/scripts/document-bloat\.py`, where `<skill folder>` is this installed maintain skill.s folder'
rs_rule "the last resort is reading directly" 'read the documents directly for the same two kinds'
rs_rule "each finding is confirmed" 'drop anything that does not survive'
rs_rule "a finding is only an offer" 'that is why a finding is only ever an offer'
rs_rule "the cap of three is shared" 'the cap of three proposals holds for all of them together'
rs_rule "nothing changes without a yes" 'change nothing without a yes'
rs_rule "the person's words are kept" "keep the person's own words in the copy that stays"
rs_rule "it says what it cannot find" 'it cannot find two documents that say the same thing in different words'
rs_rule "finding nothing is silent" 'when the read finds nothing, say nothing about it'
rs_guard "$READ" "the shipped document-bloat.md"

rs_require_load_bearing "the quarterly step loads the read" "$MAINTAIN" 'load `references/document-bloat\.md`'
rs_require "the script never lists a README" "$SCRIPT" 'a readme is never listed'
rs_require "WORKFLOW explains it" "$WORKFLOW" 'a paragraph written out in full in two places, and a document nothing mentions any more'
rs_require "WORKFLOW says what it cannot find" "$WORKFLOW" 'not two documents that say the same thing in different words'

rs_done
