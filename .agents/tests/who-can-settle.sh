#!/usr/bin/env sh
# who-can-settle.sh: guard which waiting pieces need the person in the room.
#
# Three labels say a piece is waiting on a question. Two of them cannot be
# settled without the person: an interview needs somebody to interview, and a
# prototype exists so somebody can react to it. Research needs nobody.
#
# The dangerous failure is silent and worse than the problem it replaces: an
# agent answers its own interview question, writes the guess onto the piece, and
# marks it `ready`. The label that said the question was open has gone, so
# /implement builds on the guess.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Who-can-settle checks"
rs_exists "$PIECES" "$SHAPE" "$WHATNOW" "$WORKFLOW"

rs_rule "the labels say who can answer" 'each says who can answer'
rs_rule "an interview needs the person" 'the person has to be there: an interview'
rs_rule "a prototype needs the person" 'reacting to the thing is the whole point'
rs_rule "research needs nobody" 'the agent settles this one alone'
rs_rule "no further label is needed for it" 'no further label carries that'
rs_guard "$PIECES" "pieces.md"

# Without this refusal an eager session settles an interview alone, and the
# piece then looks shaped rather than guessed.
rs_require_load_bearing "/shape never answers a person-present question itself" \
  "$SHAPE" 'never answer a person-present question yourself'
rs_require "/shape says why a guess marked ready is worse than the open question" \
  "$SHAPE" 'worse than an open question'

rs_require "/shape settles a named piece, not only the next in line" \
  "$SHAPE" 'given an issue number, settle that piece'
rs_require "/shape clears what it can when the person leaves" \
  "$SHAPE" 'where the person says they are not staying'
rs_require "and leaves every person-present piece untouched" \
  "$SHAPE" 'settle none of those in their absence'

rs_require "/what-now describes research as the agent's own work" \
  "$WHATNOW" 'a fact the agent can go and confirm on its own'
rs_require "/what-now tells the three apart for the person" \
  "$WHATNOW" 'the first two need the person in the room and the third does not'
rs_require "WORKFLOW.md explains it in plain words" \
  "$WORKFLOW" 'two of those need you there'

rs_done
