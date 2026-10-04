#!/usr/bin/env sh
# settled-is-recorded.sh: guard the record a settled question has to leave.
#
# A piece waiting on a question carries a `needs-` label. Settling it writes what
# settled it into `## Decided` and only then takes the label off. Both /shape and
# pieces.md said so, correctly and in the right order, and three measured runs
# still relabelled with nothing written. One reached `ready` carrying no
# `## Done when` at all, so it had never been sized either.
#
# Every other defect this suite guards is visible in the conversation. This one
# is not: a grader reading the transcript sees a good interview and passes it,
# and only the files say the record does not exist. That is why the rule is a
# read-back rather than an order to follow. Doing the steps in sequence is what a
# run believes it did; reading the piece back is what tells it whether it did.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"

rs_init "Settled-is-recorded checks"
rs_exists "$SHAPE" "$PIECES"

# The order, which was always right and was always going to be believed rather
# than done. Kept because a check that only demanded the read-back could be
# satisfied by reading a piece nobody had written to.
rs_rule "what settled it is written before the label comes off" \
  'and only then take the label off'
rs_rule "because the label is the only sign the question was open" \
  'the only thing saying the question was ever open'

# The part that makes it happen rather than be intended.
rs_rule "the piece is read back before relabelling" \
  'read the piece back before the label comes off'
rs_rule "and what is read decides whether the label goes" \
  'let what you read decide whether it does'
rs_rule "the decision has to be in Decided" 'has to hold what settled the question'
rs_rule "and Done when has to exist at all" 'has to be there at all'
rs_rule "a good conversation is not the record" \
  'however well the conversation went'
rs_rule "a missing one is written, re-read, and only then relabelled" \
  'write it, read it again'
rs_rule "it is named as a check rather than a reminder" \
  'this is a check, not a reminder'
rs_rule "because a run believes it did the steps in order" \
  'is what a run believes it did'
rs_rule "and nobody in the conversation can see this part" \
  'nobody in the conversation can see'
rs_guard "$SHAPE" "the /shape skill"

# pieces.md is where somebody reading about a piece meets the rule.
rs_reset
rs_rule "settling writes into Decided before the label goes" \
  'before the label comes off'
rs_rule "and says what kind of thing gets written" \
  'the decision the prototype produced'
rs_rule "without it the piece reads the same either way" \
  'whether the work happened or not'
rs_guard "$PIECES" "the shipped pieces.md"

rs_done
