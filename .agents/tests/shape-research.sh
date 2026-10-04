#!/usr/bin/env sh
# shape-research.sh: guard the two research steps behind one label.
#
# `needs-research` covers two different questions: confirm one external fact, or
# find something that already does the job. /shape picks the step
# from the question, so the risk is a silent collapse back to one step, or an
# existing-work search that recommends something unmaintained, costly, or with a
# licence the project cannot live with.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

EXISTING="$ROOT/.agents/skills/change-triage/references/existing-work.md"
SOURCE="$ROOT/.agents/skills/change-triage/references/source-check.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Shape research-step checks"
rs_exists "$EXISTING" "$SOURCE" "$SHAPE" "$TRIAGE" "$PIECES" "$WORKFLOW"

rs_rule "searches the project before anything new" 'the project itself'
rs_rule "a new dependency is the last resort" 'last resort'
rs_rule "checks the candidate is maintained" 'is it maintained'
rs_rule "checks what the licence allows" 'licence allow'
rs_rule "checks the cost, account, and limits" 'what does it cost'
rs_rule "checks where the data goes" 'where does the data go'
rs_rule "checks how hard it is to remove later" 'hard is it to remove'
rs_rule "reads the provider's own pages rather than memory" "provider's own pages rather than from memory"
rs_rule "records the finding on the piece" 'record the date checked'
rs_rule "installs nothing" 'never installs'
rs_guard "$EXISTING" "the shipped existing-work.md"

rs_require "/shape still runs the source check for a single fact" \
  "$SHAPE" 'references/source-check\.md'
rs_require "/shape runs the existing-work search for a question about existing work" \
  "$SHAPE" 'references/existing-work\.md'
# Without this instruction a question matching both steps could be answered
# without the person ever learning which was run.
rs_require_load_bearing "/shape names which step it ran, and why" \
  "$SHAPE" 'say which step you ran'

rs_require "change-triage routes both steps under one label" \
  "$TRIAGE" 'needs-research. for a source check or a search for existing work'
rs_require "pieces.md describes the label as covering both" \
  "$PIECES" 'a fact to confirm, or existing work'
rs_require "WORKFLOW.md tells the person in plain words" \
  "$WORKFLOW" 'a search for something that already does the job'

rs_done
