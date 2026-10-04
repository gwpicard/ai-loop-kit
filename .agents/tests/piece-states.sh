#!/usr/bin/env sh
# piece-states.sh: guard the rule that every open piece is in exactly one state.
#
# A piece's state used to be read from the labels it lacked. An idea was a piece
# with no Done when, shaping was a needs- label, building was `building`, and
# nothing marked a piece whose pull request was waiting for the person. So a
# piece could look like two things at once, no board could be drawn from the
# labels, and a missing `building` label once let two runs start the same piece.
#
# pieces.md owns the model. The printout's behaviour is proved in
# plan-printout.sh by running it; this proves the written model still says what
# the printout does, that founding creates the labels, and that WORKFLOW.md
# explains the states in one place. The rule that matters most is "exactly one",
# so a copy of pieces.md that allows two has to fail here.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"

rs_init "Piece-state checks"
rs_exists "$PIECES" "$SETUP" "$WORKFLOW" "$WHATNOW"

# The model itself.
rs_rule "exactly one state sits on an open piece" \
  'exactly one of the six sits on an open piece, never two'
rs_rule "the six states are defined in board order" \
  '[-] `idea`, [^;]*; - `shaping`, [^;]*; - `ready`, [^;]*; - `building`, [^;]*; - `to check`, [^;]*; - `parked`, '
rs_rule "two states on one piece is named, never guessed" \
  'two state labels on one piece is a mistake'
rs_rule "a closed issue is done and carries no state" \
  'a closed issue is done and carries no state label'
rs_rule "an idea left out stays closed and parked" \
  'stays a closed issue labelled `parked`'
rs_rule "an open issue with no state counts as an idea" \
  'an open issue with no state label counts as `idea`'
rs_rule "a ready issue without Done when is still an idea" \
  'labelled `ready` without a `## done when` is an idea too'
rs_rule "a parked open piece carries its reason" \
  'either way the reason is written on the piece'
rs_rule "parked replaces blocked" '`parked` replaces the `blocked` label'
rs_rule "an older project's blocked reads as parked" \
  'may still carry `blocked`, and the printout shows it as parked'
rs_rule "held up by another piece is a link, not a state" \
  'held up by another piece is never a state'
rs_rule "a needs- label is the reason beside shaping only" \
  'the reason beside `shaping`, and only ever beside it'
rs_rule "broken sits beside the state" 'sits beside the state rather than replacing it'
rs_rule "the label count matches the set" 'those seventeen are the only labels the kit owns'
rs_rule "founding creates the labels, states among them" \
  'founding creates the kit.s labels at the start, the six states among them'

# The printout reads the states as the columns of a board.
rs_rule "the printout's order is written down" \
  'needs attention, broken, then the states in the order idea, shaping, ready, building, to check and parked, and last made of parts'
rs_rule "the held-up group has its own heading" \
  'the ones waiting on another piece are headed `held up`'
rs_rule "a closed issue never prints" 'a closed issue never prints'
rs_rule "an unreachable GitHub still gives the printout's age" \
  'says when that one was written'
# A piece can reach building or to check without being shaped or checked, and
# then it looks exactly like one that was. The printout names it, and these
# say so where the model is written down.
rs_rule "a building or to check piece that skipped a step needs attention" \
  'it also lists a `building` or `to check` piece that skipped a step'
rs_rule "with no Done when it was never shaped" \
  'with no `## done when` it says the piece was never shaped'
rs_rule "with no Readiness it had no readiness check" \
  'no `## readiness` section it says the piece had no readiness check'
rs_rule "only the first note shows when both are missing" \
  'where both are missing, only the first is said'
rs_rule "such a piece stays in its own column too" \
  'such a piece stays in its own column as well'
rs_rule "a parent and a broken piece get neither note" \
  'a parent and a `broken` piece get neither note'
rs_guard "$PIECES" "pieces.md"

# The sentences this model replaced. Put back, either would sit beside the new
# model and contradict it with every rule above still present.
rs_require_absent "labels are no longer made only when first needed" \
  "$PIECES" 'a label is created when it is first needed'
rs_require_absent "blocked is no longer a label the kit defines" \
  "$PIECES" '[-] `blocked`,'

# "Exactly one" is the rule a careless edit loosens rather than deletes. A copy
# that allows two must fail the rule set, not only a copy with the line gone.
rs_fold "$PIECES" \
  | sed -E 's@exactly one of the six sits on an open piece, never two@one or more of the six may sit on an open piece@' \
  > "$rs_dir/allows-two"
if rs_check "$rs_dir/allows-two" >/dev/null; then
  rs_report "a copy of pieces.md that allows two states fails" no
else
  rs_report "a copy of pieces.md that allows two states fails" yes
fi

# Founding makes the labels, so a piece can carry its state from the day it is
# opened.
rs_require_load_bearing "founding's label step names the six states" \
  "$SETUP" 'the six states `idea`, `shaping`, `ready`, `building`, `to check` and `parked`'
rs_require_load_bearing "founding labels a piece with a question shaping, with its reason" \
  "$SETUP" '`shaping` with the matching `needs-` label'

# WORKFLOW.md explains the states once, in plain words.
rs_require_load_bearing "WORKFLOW.md explains the states" \
  "$WORKFLOW" 'every open piece is in exactly one state'
told=$(grep -ci 'exactly one state' "$WORKFLOW" || true)
rs_report "WORKFLOW.md explains the states in one place" \
  "$([ "$told" -eq 1 ] && echo yes || echo no)"
rs_require_load_bearing "WORKFLOW.md says the printout draws them as a board" \
  "$WORKFLOW" 'the columns of a board'
rs_require_absent "WORKFLOW.md no longer offers blocked as a label" \
  "$WORKFLOW" '`blocked` when something outside the project holds it up'
rs_require_load_bearing "WORKFLOW.md says a piece built without shaping shows under needs attention" \
  "$WORKFLOW" 'a piece being built or checked that was never shaped'

# /what-now names such a piece where it names a failing check, before the
# counts, so the person hears it before the work is merged.
rs_require_load_bearing "/what-now names a piece built or checked that was never shaped or checked" \
  "$WHATNOW" 'a piece being built or waiting for the person.s check that was never shaped, or never had its readiness check, is named in the same place'
rs_require_load_bearing "/what-now says it once, with what is missing" \
  "$WHATNOW" 'once, with what it is missing'

rs_done
