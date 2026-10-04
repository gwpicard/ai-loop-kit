#!/usr/bin/env sh
# manual-step.sh: guard the step only the person can do.
#
# The one thing the agent cannot do for somebody was the least visible thing on
# their list. A piece now records it as `## Waiting on you`, /implement stops on
# it, and /what-now names it as the person's own to-do.
#
# Three ways this could go wrong quietly, so all three are checked: the section
# disappears; it turns into another meaning for `parked`, which would make the
# two it already has on an open piece unreadable; or it becomes a place to ask
# for a key, which would put a secret in a tracked file.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
IMPLEMENT="$ROOT/.agents/skills/implement/SKILL.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Manual-step checks"
rs_exists "$PIECES" "$TRIAGE" "$IMPLEMENT" "$WHATNOW" "$WORKFLOW"

rs_rule "the section exists on a piece" '## waiting on you <only when'
rs_rule "it says where to go and what to bring back" 'what to bring back'
rs_rule "it appears only where the work truly stops" 'cannot go further until'
rs_rule "the agent does what it can rather than asking" \
  'never ask for something the agent could'
rs_rule "it never carries the secret it asks for" \
  'never carries the secret it asks for'
rs_rule "it is not another meaning for parked" 'this is not .parked'
# The reason this is a section rather than a third meaning for `parked` is that
# both meanings an open piece already has are load-bearing for /implement. If
# either is ever dropped, the reasoning behind the section goes with it.
rs_rule "parked still covers a piece stopped at a recorded condition" \
  'covers a piece stopped at a recorded condition'
rs_rule "parked still covers a piece parked after three failed attempts" \
  'a piece parked after three failed attempts'
rs_rule "a piece waiting on the person keeps its state" \
  'keeps whatever state it had'
rs_guard "$PIECES" "pieces.md"

rs_require "change-triage routes the setup task it already classifies" \
  "$TRIAGE" 'a step only the person can do'
rs_require "and does the step itself where it can" \
  "$TRIAGE" 'do the step yourself where you can'

rs_require "/implement neither builds it nor skips it quietly" \
  "$IMPLEMENT" 'do not attempt it, and do not pass it over in silence'
# Without this line an unattended run would either stop dead or pass the piece
# over without saying so.
rs_require_load_bearing "an unattended run names it and takes the next ready piece" \
  "$IMPLEMENT" 'in an unattended run, name the step'

# /implement is where the two meanings of `parked` are acted on, so they are
# held there too. Without them a piece parked at a condition and one parked
# after three failures would be read alike, and a third meaning could creep in.
rs_require_load_bearing "/implement still skips a piece parked at a recorded condition" \
  "$IMPLEMENT" 'one safely prepared and stopped at a recorded condition stays skipped'
rs_require_load_bearing "/implement still routes a piece parked after failure to /shape" \
  "$IMPLEMENT" 'one parked after repeated failure'

rs_require "/what-now names it apart from work the agent is doing" \
  "$WHATNOW" 'their own thing to do'
rs_require "/what-now carries a recovery route for it" \
  "$WHATNOW" '### a step only you can do'
rs_require "and never asks for a key in a message" \
  "$WHATNOW" 'never ask for one to be pasted into a message'
rs_require "WORKFLOW.md explains it in plain words" \
  "$WORKFLOW" 'waiting on something only you can do'

rs_done
