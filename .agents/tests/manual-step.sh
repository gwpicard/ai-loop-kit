#!/usr/bin/env sh
# manual-step.sh: guard the step only the person can do.
#
# The one thing the agent cannot do for somebody was the least visible thing on
# their list. A piece now records it as `## Waiting on you`, /implement stops on
# it, and /what-now names it as the person's own to-do.
#
# Three ways this could go wrong quietly, so all three are checked: the section
# disappears; the piece stays where a run can take it, so a run meets a step
# nobody can do; or it becomes a place to ask for a key, which would put a
# secret in a tracked file.

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
# A piece with a step only the person can do sits in shaping:clarify, so no
# run takes it, and the two other ways a piece comes back from a build stay
# apart from it: a caution kicks it back to clarify and three failed attempts
# to spec or research, each with a ## Kickback section saying why.
rs_rule "a piece waiting on the person sits in clarify" \
  'a piece with a `## waiting on you` step sits in `shaping:clarify` until the step is done'
rs_rule "so no run takes it" 'so no run takes it'
rs_rule "a caution is a kickback, not this" \
  'a piece stopped at a sensitive-area caution is kicked back to `shaping:clarify` with a `## kickback` section naming the caution'
rs_rule "three failed attempts are a kickback to spec or research" \
  'a piece that failed three attempts is kicked back to `shaping:spec` or `shaping:research`'
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

# /implement is where the two kickbacks are acted on, so they are held there
# too. Without them a piece stopped at a caution and one that kept failing
# would be read alike.
rs_require_load_bearing "/implement leaves a piece kicked back at a caution until the acceptance" \
  "$IMPLEMENT" 'one kicked back at a sensitive-area caution sits in `shaping:clarify` with a `## kickback` section naming the caution, and stays there until the person carries on after the risk notice and the acceptance is recorded'
rs_require_load_bearing "/implement leaves a piece that kept failing to /shape" \
  "$IMPLEMENT" 'one kicked back after three failed attempts sits in `shaping:spec` or `shaping:research` for `/shape` to look at again'
rs_require_load_bearing "/implement says a piece waiting on the person sits in clarify" \
  "$IMPLEMENT" 'such a piece sits in `shaping:clarify`'
rs_require_absent "/implement no longer names parked" "$IMPLEMENT" 'parked'

rs_require "/what-now names it apart from work the agent is doing" \
  "$WHATNOW" 'their own thing to do'
rs_require "/what-now carries a recovery route for it" \
  "$WHATNOW" '### a step only you can do'
rs_require "and never asks for a key in a message" \
  "$WHATNOW" 'never ask for one to be pasted into a message'
rs_require "WORKFLOW.md explains it in plain words" \
  "$WORKFLOW" 'waiting on something only you can do'

rs_done
