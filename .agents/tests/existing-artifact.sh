#!/usr/bin/env sh
# existing-artifact.sh: guard the route that lets something the person already
# has settle a visual or behavioural question.
#
# The kit could always build a throwaway to settle such a question. It now
# prefers a mock, sketch, screenshot, or spreadsheet the person already has
#. The rules that keep that safe are the whole of it: an artifact
# settles look and behaviour and never the build path, its gaps are asked rather
# than invented, its real data and secrets stay out, and the decision is written
# in words because the artifact may live somewhere the project cannot reach.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

ARTIFACT="$ROOT/.agents/skills/clarify/references/existing-artifact.md"
PROTOTYPE="$ROOT/.agents/skills/clarify/references/decision-prototype.md"
CLARIFY="$ROOT/.agents/skills/clarify/SKILL.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Existing-artifact checks"
rs_exists "$ARTIFACT" "$PROTOTYPE" "$CLARIFY" "$SHAPE" "$SETUP" "$WORKFLOW"

rs_rule "says back what it sees, guesses attached" 'say what you found'
rs_rule "never claims to have seen what it cannot open" \
  'never pretend to have seen it'
rs_rule "settles look and behaviour, never the build path" \
  'never settles the build path'
rs_rule "the fit check and risk notice still apply" 'risk notice'
rs_rule "an artifact is a design, not production code" \
  'design rather than production code'
rs_rule "real data and secrets stay out" 'never take real data'
rs_rule "builds a slice rather than the whole mock" 'never build the whole mock'
rs_rule "names what the artifact does not cover" 'rather than inventing it'
rs_rule "a conflict goes to the person" 'let them choose'
rs_rule "records the decision in words" 'record the decision rather than'
rs_rule "a recorded design-tool file may be opened directly" \
  'file in the recorded design tool'
rs_rule "the harness must be able to reach that tool" \
  'where the harness can reach it'
rs_guard "$ARTIFACT" "the shipped existing-artifact.md"

# Every route that could build a throwaway has to check first, or the old
# behaviour survives in whichever one was missed.
rs_require "clarify asks before it builds a throwaway" \
  "$CLARIFY" 'existing-artifact\.md'
rs_require "/shape settles a needs-prototype piece with what exists" \
  "$SHAPE" 'existing-artifact\.md'
rs_require "decision-prototype.md checks before building one" \
  "$PROTOTYPE" 'existing-artifact\.md'
rs_require "/setup names it in the founding interview" \
  "$SETUP" 'mock or.*sketch the person already has'

rs_require_twice "WORKFLOW.md explains it for founding and for day-to-day work" \
  "$WORKFLOW" 'mock'

rs_done
