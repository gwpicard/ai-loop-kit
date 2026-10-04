#!/usr/bin/env sh
# document-read.sh: guard the rules of the document read in /sync.
#
# document-read-rehearsal.sh runs the script. This half reads back what keeps
# the read honest about its own reach: which documents it reads and why, that a
# document saying less than the project does is never a finding, that a
# described flow is out of reach and the report says so, that a name already on
# an open piece is not raised again, and that a correction changes the stale
# name and never the person's prose.
#
# The read goes wrong quietly in two directions. It can flag true things until
# nobody reads it, or it can find nothing and let that stand for "the documents
# are right". Most of the rules here hold one of those two shut.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READ="$ROOT/.agents/skills/sync/references/document-read.md"
SCRIPT="$ROOT/.agents/skills/sync/scripts/document-claims.py"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Document read rules"
rs_exists "$READ" "$SCRIPT" "$SYNC" "$WORKFLOW"

rs_rule "it follows the shared rules" 'whole-project-reads\.md` apply'
rs_rule "only the README and what AGENTS.md points at" '`readme\.md`, and every document agents\.md points at\. nothing else\.'
rs_rule "the records are not read twice" 'are not read again here'
rs_rule "saying less is never a finding" 'a document may say less than the project does\. that is never a finding'
rs_rule "only a name that does not exist is wrong" 'a document is wrong only where it names something that does not exist'
rs_rule "a described flow is out of reach" 'whether a described flow still happens the way the document says is out of reach'
rs_rule "the shipped script comes first" '1\. `python3 <skill folder>/scripts/document-claims\.py`, where `<skill folder>` is this installed sync skill.s folder'
rs_rule "the fallback is reading directly" 'read the documents directly and check the same four kinds of name by hand'
rs_rule "each finding is confirmed at its line" 'open the document at the line the script names'
rs_rule "a raised name is not raised again" 'a name already on an open piece has been raised and decided'
rs_rule "at most three findings" 'give at most three findings'
rs_rule "it says what it cannot check" 'it cannot tell whether a described step still happens that way'
rs_rule "the correction changes only the name" 'changing that name and nothing else in the sentence around it'
rs_rule "prose is never rewritten" "never rewrite the person's prose"
rs_rule "finding nothing is silent" 'when the read finds nothing, say nothing about it'
rs_guard "$READ" "the shipped document-read.md"

rs_require_load_bearing "sync loads the read" "$SYNC" 'load `references/document-read\.md`'
rs_require "the script flags only what does not exist" "$SCRIPT" 'only a name that points at nothing is'
rs_require "the script never says a document is right" "$SCRIPT" 'it never says a document is right'
rs_require "WORKFLOW explains it" "$WORKFLOW" 'a document that says less than the project does is fine'

rs_done
