#!/usr/bin/env sh
# state-moves.sh: guard that every command moves a piece to its next state.
#
# pieces.md says every open piece is in exactly one state, and the printout
# draws the states as a board. That holds only while the commands keep it true.
# A command that adds the new state and forgets the old one leaves a piece in
# two columns, and one that never moves a piece leaves the board wrong within a
# day. Both are quiet: nothing fails, the board just stops describing the work.
#
# So this reads each command for its moves. The one that matters most is the
# pairing, the old state taken off in the same step as the new one goes on, and
# it is checked mechanically as well as in prose: every label command the
# building and shaping skills write has to carry its removal on the same line.
#
# plan-printout.sh proves the printout draws the board. piece-states.sh proves
# pieces.md still defines it. This proves the commands still move pieces on it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
TRIAGE="$SKILLS/change-triage/SKILL.md"
SHAPE="$SKILLS/shape/SKILL.md"
IMPLEMENT="$SKILLS/implement/SKILL.md"
LONGER="$SKILLS/implement/references/running-longer.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
FIX="$SKILLS/fix/SKILL.md"
WHATNOW="$SKILLS/what-now/SKILL.md"
QUEUE="$SKILLS/queue/SKILL.md"
SYNC="$SKILLS/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
SCENARIOS="$ROOT/.agents/tests/scenarios.md"

rs_init "State-move checks"
rs_exists "$TRIAGE" "$SHAPE" "$IMPLEMENT" "$LONGER" "$BUILDER" "$FIX" \
  "$WHATNOW" "$QUEUE" "$SYNC" "$WORKFLOW" "$SCENARIOS"

# Capture. A note asked for outright is filed as an idea in the person's words,
# with nothing settled, and never routed. Without this a note either sits in
# nobody's list or arrives looking shaped when nobody shaped it.
rs_rule "a note for later is not classified or routed" 'do not classify or route it'
rs_rule "it is filed as an idea in the person's words, nothing settled" \
  'file it as an issue labelled `idea`, with the person.s own words as the body and nothing settled'
rs_rule "/shape later and /shape idea are capture too" '`/shape later` or `/shape idea`'
rs_rule "a duplicate note is added to the existing piece as a comment" \
  'add the person.s words to that issue as a comment and say which one'
rs_rule "a new issue only when the person says it is different" \
  'file a new issue only if the person says theirs is different'
rs_rule "a routed question labels the piece shaping with its reason" \
  'label the issue `shaping` with the `needs-` label that names the route'
rs_guard "$TRIAGE" "change-triage"

# /shape moves idea to shaping, and shaping to ready only at the bar.
rs_reset
rs_rule "the old state comes off in the same step" \
  'takes the old state off in the same step as it puts the new one on'
rs_rule "starting on an idea moves it to shaping" \
  '<number> --add-label shaping --add-label needs-clarification --remove-label idea'
rs_rule "ready only when the readiness check finds no blocking gap" \
  'reaches `ready` only when the readiness check finds no blocking gap'
rs_rule "shaping and its reason come off as ready goes on" \
  '<number> --add-label ready --remove-label shaping --remove-label'
rs_rule "a piece it cannot finish stays in shaping with its reason" \
  'cannot finish stays `shaping` with the `needs-` label that says why'
rs_rule "a parked piece back for another look moves to shaping" \
  'a `parked` piece sent back for another look moves to `shaping`'
rs_rule "an unreachable GitHub leaves the piece as it is" \
  'the label cannot move, so say so and leave the piece as it is'
rs_rule "capture is filed as an idea, not shaped" \
  'that is capture, and change-triage handles it'
rs_rule "research says before it starts whether it needs the person" \
  'before it starts, write one line on the piece: "needs your decision: yes" or "needs your decision: no"'
rs_rule "research needing nobody moves the piece to ready" \
  'with no, and a result that settles every question, move the piece to `ready` once the readiness check finds no blocking gap'
rs_rule "research that leaves a question open stays shaping with the gap" \
  'the piece stays `shaping` with `needs-research` and the gap written on it'
rs_rule "research needing the person hands the piece back to them" \
  'swap `needs-research` for `needs-clarification` in one step'
rs_guard "$SHAPE" "the /shape skill"

# /implement claims before any work, and never builds an idea however full.
rs_reset
rs_rule "the claim comes before any work" 'claim the piece before any work'
rs_rule "the claim swaps ready for building" '<number> --add-label building --remove-label ready'
rs_rule "a claim that cannot be made starts nothing" \
  'a piece nobody could claim may be claimed by somebody else'
rs_rule "a hand-opened issue with no state is an idea and is never built" \
  'counts as an idea, however full its body'
rs_rule "a parked piece whose condition is met moves straight to building" \
  'move it from `parked` to `building` in one step'
rs_rule "a piece in two states is not built" \
  'a piece carrying two states is not built'
rs_guard "$IMPLEMENT" "the /implement skill"
rs_require_absent "/implement no longer calls blocked a hint" \
  "$IMPLEMENT" 'the `blocked` label is only a hint'

# section-builder: building to to check, to parked, and off after merge.
rs_reset
rs_rule "the claim takes whatever state it had off" \
  'whatever state it carried comes off in that step'
rs_rule "an unreachable GitHub fails the claim and starts nothing" \
  'the claim fails: say so, and do not start the piece'
rs_rule "opening the pull request moves it to to check" \
  '<number> --add-label "to check" --remove-label building'
rs_rule "the checkpoint route closes the piece and takes building off" \
  'close the issue and take `building` off it in the same step'
rs_rule "the checkpoint route is named as the one exception" \
  'the one route where a piece closes when it is saved rather than when a pull request merges'
rs_rule "the flagged route parks it with the condition written on it" \
  'move the piece from `building` to `parked` in one step, with the condition written on it'
rs_rule "three failed attempts park it with the reason" \
  'fails three attempts stops there: move it from `building` to `parked`'
rs_rule "after the merge, to check comes off the closed issue" \
  'take `to check` off the closed issue'
rs_guard "$BUILDER" "section-builder"
rs_require_absent "section-builder no longer labels a piece blocked" \
  "$BUILDER" 'label the piece `blocked`'
rs_require_absent "and no longer calls a stopped piece safely blocked" \
  "$BUILDER" 'safely blocked'

rs_require_load_bearing "an unattended run parks a failing piece the same way" \
  "$LONGER" 'move it from `building` to `parked` in one step'
rs_require_absent "and no longer marks it blocked" "$LONGER" 'mark it `blocked`'

# /fix follows the same moves.
rs_require_load_bearing "/fix claims the repair before it starts" \
  "$FIX" 'add `building` and take off whatever state it carried, in one step'
rs_require_load_bearing "/fix claims only once the repair is confirmed as promised" \
  "$FIX" 'only once the repair is confirmed as promised behaviour'
rs_require_order "/fix claims after the promise check" "$FIX" \
  'never promised there' 'the repair is confirmed as promised'
rs_require_load_bearing "/fix moves a claim back when the request goes to /shape" \
  "$FIX" 'move it back to the state it had in one step'
rs_require_load_bearing "/fix adds building alone to an issue with no state" \
  "$FIX" 'where the issue carries no state label, add `building` alone'
rs_require_load_bearing "/fix parks the repair when the person does not carry on" \
  "$FIX" 'move the repair.s piece from `building` to `parked` in one step'

# The pairing, read mechanically. Every label command these skills write puts
# its removal on the same line, so none of them can leave a piece in two states.
pairs_ok() {
  # pairs_ok <file>...: yes when every --add-label line also removes a label.
  if grep -h -- '--add-label' "$@" | grep -v -- '--remove-label' | grep -q .; then
    echo no
  else
    echo yes
  fi
}
rs_report "every label command in shape, implement, section-builder and fix removes the old state" \
  "$(pairs_ok "$SHAPE" "$IMPLEMENT" "$BUILDER" "$FIX" "$LONGER")"
grep -c -- '--add-label' "$SHAPE" "$IMPLEMENT" "$BUILDER" "$FIX" \
  | grep -q ':0$' && rs_report "each of the four writes its moves as commands" no \
  || rs_report "each of the four writes its moves as commands" yes
sed -E 's/ --remove-label ready//' "$IMPLEMENT" > "$rs_dir/implement-unpaired"
# An older project may lack a state label until /maintain moves it. Each move
# site points at pieces.md's rule rather than failing on the missing label.
for site in "$SHAPE" "$IMPLEMENT" "$BUILDER" "$FIX"; do
  rs_require_load_bearing "$(basename "$(dirname "$site")") creates a missing state label first" \
    "$site" 'creating the label first if the project lacks it'
done

rs_report "a copy that drops a removal is caught" \
  "$([ "$(pairs_ok "$rs_dir/implement-unpaired")" = no ] && echo yes || echo no)"

# /what-now names a piece in to check as the person's own.
rs_reset
rs_rule "a piece in to check is the person's own" \
  'a piece under `to check` is the person.s own'
rs_rule "it waits for them to try it or merge it" 'waiting for them to try it or merge it'
rs_guard "$WHATNOW" "the /what-now skill"

# /queue reads the states rather than the old labels.
rs_reset
rs_rule "a claimed piece or one waiting for the person is in neither group" \
  'a piece under `building` or `to check` is in neither group'
rs_rule "the waiting group is the held-up pieces" 'the pieces under `held up`'
rs_guard "$QUEUE" "the /queue skill"

# /sync repairs the two label mistakes and never unparks a closed idea.
rs_reset
rs_rule "two states on one piece is repaired" 'a piece carrying two state labels keeps the one'
rs_rule "the evidence decides which state stays" \
  'an open pull request that closes it means `to check`'
rs_rule "a pair containing parked stays parked" \
  'never repair a pair containing it to a state that can be built'
rs_rule "with no evidence, the earliest state stays" \
  'keep the state earliest in the board order'
rs_rule "a closed issue loses a state other than parked" \
  'a closed issue carrying a state other than `parked` loses that label'
rs_rule "a closed parked issue is never touched" 'never remove `parked` from a closed issue'
rs_rule "it says what it changed" 'say what you changed, piece by piece'
rs_rule "an older blocked label is left for /maintain" \
  'an older project.s `blocked` label is `/maintain`.s to move'
rs_guard "$SYNC" "the /sync skill"
rs_require_absent "/sync no longer offers to remove a stale blocked label" \
  "$SYNC" 'a stale `blocked` label is worth offering to remove'

# WORKFLOW.md tells the moves in its day-to-day section.
rs_require_load_bearing "WORKFLOW.md says each command moves the piece and drops the old state" \
  "$WORKFLOW" 'each command moves a piece to its next state and takes the old one off in the same step'
rs_require_load_bearing "WORKFLOW.md says to check is yours" \
  "$WORKFLOW" 'moves it to to check when its pull request opens'
rs_require_load_bearing "WORKFLOW.md says an unreachable GitHub starts nothing" \
  "$WORKFLOW" 'does not start a piece it could not claim'
rs_require_load_bearing "WORKFLOW.md says /fix starts no repair it could not claim" \
  "$WORKFLOW" 'does not start a repair it could not claim'
rs_require_load_bearing "WORKFLOW.md says a note is filed as an idea" \
  "$WORKFLOW" 'as an idea in your own words'
rs_require_absent "WORKFLOW.md no longer says a stopped piece is marked blocked" \
  "$WORKFLOW" 'plan marked blocked'

rs_require_absent "the scenario no longer gives blocked two meanings" \
  "$SCENARIOS" 'the `blocked` label keeps the two meanings'

rs_done
