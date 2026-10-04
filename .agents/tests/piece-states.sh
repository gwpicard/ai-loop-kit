#!/usr/bin/env sh
# piece-states.sh: guard the rule that every open piece is in exactly one state,
# with exactly one sub-label where its state has them.
#
# A piece's state used to be read from the labels it lacked, and later from six
# plain labels any command could write. A command that forgot to take the old
# label off left a piece in two states, no board could be trusted, and a missing
# `building` label once let two runs start the same piece. So the model now has
# four states, each written as a `state:` label, sub-labels for shaping and for
# review, and one script, the gate, that is the only thing allowed to move them.
#
# pieces.md owns the model. The printout's behaviour is proved in
# plan-printout.sh by running it, and the gate's in gate-script.sh; this proves
# the written model still says what they do, that founding creates the labels
# and moves each piece through the gate with one type label, and that
# WORKFLOW.md explains the states in one place. The rule that matters most is
# "exactly one", so a copy of pieces.md that allows two states, or two
# sub-labels, has to fail here.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"

rs_init "Piece-state checks"
rs_exists "$PIECES" "$SETUP" "$WORKFLOW" "$WHATNOW"

# The four states.
rs_rule "the four states are defined in board order" \
  '[-] `state:shaping`, [^;]*; - `state:ready`, [^;]*; - `state:building`, [^;]*; - `state:in-review`, '
rs_rule "exactly one state sits on an open piece" \
  'exactly one `state:` label sits on an open piece, never two'
rs_rule "two states on one piece is named, never guessed" \
  'two state labels on one piece is a mistake'
rs_rule "a closed issue carries no state" \
  'a closed issue is done, or was dropped, and carries no state label'
rs_rule "an open issue with no state is named, then taken in" \
  'an open issue with no state label has not been taken in yet'
rs_rule "it is taken in with capture, never as a second issue" \
  '`gate\.py capture <number>` rather than opening a second issue'
rs_rule "a parent carries no state" \
  'a parent, an issue with open parts, carries no state of its own: its parts carry the states'
rs_rule "the gate refuses to give a parent one" 'the gate refuses to capture or move a parent'
rs_rule "held up by another piece is a link, not a state or a label" \
  'held up by another piece is never a state or a label'

# The sub-labels beside shaping and beside review.
rs_rule "the six shaping sub-states are defined in order" \
  '[-] `shaping:raw`, [^;]*; - `shaping:research`, [^;]*; - `shaping:clarify`, [^;]*; - `shaping:prototype`, [^;]*; - `shaping:spec`, [^;]*; - `shaping:check`, '
rs_rule "exactly one shaping sub-label, only beside shaping" \
  'exactly one `shaping:` label sits beside `state:shaping`, never two, and never beside another state'
rs_rule "a question is written on the piece before it moves" \
  'a question goes under `## open question` on the piece, one question to a piece'
rs_rule "only a Ready readiness section lets a piece reach ready" \
  'only a `## readiness` section saying ready with no blocking line lets the gate move it to `state:ready`'
rs_rule "the two review sub-labels" \
  'a piece in `state:in-review` carries exactly one review sub-label: `review:auto` .*or `review:person`'
rs_rule "every piece reaches review as the person's until the automatic review exists" \
  'every piece reaching review gets `review:person`'

# The other two dimensions, and the subjects.
rs_rule "every piece carries exactly one type" 'every piece carries exactly one `type:` label'
rs_rule "the three types" '[-] `type:feature`, [^;]*; - `type:bug`, [^;]*; - `type:chore`, '
rs_rule "the four loops" '`loop:fix`, `loop:build`, `loop:goal` and `loop:gauntlet`'

# The gate is the one way a state changes.
rs_rule "only the gate script changes a state" \
  'only the gate script, `\.agents/tools/gate\.py`, changes a state, a sub-state or a review label'
rs_rule "a refusal says what failed and the next command" \
  'a refusal says what failed and gives the next command to run'
rs_rule "a person's change is reported and never undone" \
  'the report names what it finds and never puts it back'
rs_rule "the label count matches the set" 'those 26 are the only labels the kit owns'
rs_rule "AI Build Kit's labels are reported and left alone" \
  'names each as a label the kit does not use and leaves it alone'
rs_rule "founding creates the labels through the gate" \
  'founding creates the kit.s labels with `gate\.py labels` before the first issue'

# The printout reads the states as the columns of a board.
rs_rule "the printout's order is written down" \
  'needs attention, then one column for each shaping sub-state, then ready, building, and in review split into waiting for you and automatic, and last made of parts'
rs_rule "the held-up group has its own heading" \
  'the ones waiting on another piece are headed `held up`'
rs_rule "needs attention is what the gate's report would print" \
  'needs attention lists the findings `gate\.py report` would print'
rs_rule "the printout asks the gate rather than working them out again" \
  'takes them from the gate script beside it rather than working them out again'
rs_rule "a bug is marked in whichever column it sits" \
  'a `type:bug` piece carries a `\(bug\)` mark in whichever column it sits'
rs_rule "a closed issue never prints" 'a closed issue never prints'
rs_rule "an unreachable GitHub still gives the printout's age" \
  'says when that one was written'
# A piece can carry a later state without being shaped or checked, because a
# person can add a label by hand, and then it looks exactly like one that went
# the proper way. The printout names it, and these say so where the model is
# written down.
rs_rule "a piece that skipped a step needs attention" \
  'it also lists a `state:ready`, `state:building` or `state:in-review` piece that skipped a step'
rs_rule "with no Done when it was never shaped" \
  'with no `## done when` it says the piece was never shaped'
rs_rule "with no Readiness it had no readiness check" \
  'no `## readiness` section it says the piece had no readiness check'
rs_rule "only the first note shows when both are missing" \
  'where both are missing, only the first is said'
rs_rule "a piece being built or reviewed stays in its own column too" \
  'stays in its own column as well'
rs_rule "a parent gets neither note" 'a parent gets neither note'
rs_guard "$PIECES" "pieces.md"

# The model these replaced. Put back, any of them would sit beside the new
# model and contradict it with every rule above still present.
rs_require_absent "the six states are no longer defined" \
  "$PIECES" '[-] `idea`, [^;]*; - `shaping`, '
rs_require_absent "to check is no longer a state" "$PIECES" '[-] `to check`,'
rs_require_absent "the seventeen-label count is gone" "$PIECES" 'those seventeen'
rs_require_absent "labels are no longer made only when first needed" \
  "$PIECES" 'a label is created when it is first needed'
rs_require_absent "blocked is no longer a label the kit defines" \
  "$PIECES" '[-] `blocked`,'

# "Exactly one" is the rule a careless edit loosens rather than deletes. A copy
# that allows two must fail the rule set, not only a copy with the line gone,
# and that holds for the sub-labels as much as for the states.
rs_fold "$PIECES" \
  | sed -E 's@exactly one `state:` label sits on an open piece, never two@one or more `state:` labels may sit on an open piece@' \
  > "$rs_dir/allows-two"
if rs_check "$rs_dir/allows-two" >/dev/null; then
  rs_report "a copy of pieces.md that allows two states fails" no
else
  rs_report "a copy of pieces.md that allows two states fails" yes
fi
rs_fold "$PIECES" \
  | sed -E 's@exactly one `shaping:` label sits beside `state:shaping`, never two@one or more `shaping:` labels may sit beside `state:shaping`@' \
  > "$rs_dir/allows-two-subs"
if rs_check "$rs_dir/allows-two-subs" >/dev/null; then
  rs_report "a copy of pieces.md that allows two sub-labels fails" no
else
  rs_report "a copy of pieces.md that allows two sub-labels fails" yes
fi

# Founding makes the labels through the gate, opens each piece through it with
# one type label, and moves it only through it. starter-rehearsal.sh runs the
# commands; these hold the sentences that name them.
rs_require_load_bearing "founding creates the labels with the gate before the first issue" \
  "$SETUP" 'create the label set with `python3 \.agents/tools/gate\.py labels`'
rs_require_load_bearing "founding opens each piece through the gate" \
  "$SETUP" 'open it with `gate\.py capture`'
rs_require_load_bearing "founding gives each piece exactly one type before its first move" \
  "$SETUP" 'give it exactly one `type:` label with `gh issue edit` before its first move'
rs_require_load_bearing "the founding commands carry the type step" \
  "$SETUP" 'gh issue edit <number> --add-label "type:<feature\|bug\|chore>"'
rs_require_load_bearing "a piece founding shapes fully ends in check" \
  "$SETUP" 'a piece founding shapes fully moves to `spec`, then to `check` once its contract is written, and ends in `shaping:check`'
rs_require_load_bearing "and reaches ready only through the gate" \
  "$SETUP" 'moves to `state:ready` only through the gate'
rs_require_absent "founding no longer names the six states" \
  "$SETUP" 'the six states `idea`, `shaping`, `ready`, `building`, `to check` and `parked`'

# WORKFLOW.md explains the states once, in plain words.
rs_require_load_bearing "WORKFLOW.md explains the states" \
  "$WORKFLOW" 'every open piece is in exactly one state'
told=$(grep -ci 'exactly one state' "$WORKFLOW" || true)
rs_report "WORKFLOW.md explains the states in one place" \
  "$([ "$told" -eq 1 ] && echo yes || echo no)"
rs_require_load_bearing "WORKFLOW.md names the four states" \
  "$WORKFLOW" '`state:shaping` while it is not ready to build, `state:ready` once it is shaped and checked, `state:building` while somebody or a run is on it, and `state:in-review`'
rs_require_load_bearing "WORKFLOW.md names the shaping sub-states" \
  "$WORKFLOW" '`shaping:raw` .*`shaping:research`, `shaping:clarify` or `shaping:prototype` .*`shaping:spec` .*`shaping:check`'
rs_require_load_bearing "WORKFLOW.md says only the gate script moves a piece" \
  "$WORKFLOW" 'only the gate script, `\.agents/tools/gate\.py`, moves a piece'
rs_require_load_bearing "WORKFLOW.md says how to pull a ready piece back" \
  "$WORKFLOW" 'to pull a ready piece back before anybody claims it'
rs_require_load_bearing "WORKFLOW.md says the printout draws them as a board" \
  "$WORKFLOW" 'the columns of a board'
rs_require_absent "WORKFLOW.md no longer offers blocked as a label" \
  "$WORKFLOW" '`blocked` when something outside the project holds it up'
rs_require_absent "WORKFLOW.md no longer describes the six states" \
  "$WORKFLOW" '`to check` when its pull request is waiting for you'
rs_require_load_bearing "WORKFLOW.md says a piece built without shaping shows under needs attention" \
  "$WORKFLOW" 'a piece being built or checked that was never shaped'

# /what-now names such a piece where it names a failing check, before the
# counts, so the person hears it before the work is merged.
rs_require_load_bearing "/what-now names a piece built or checked that was never shaped or checked" \
  "$WHATNOW" 'a piece being built or waiting for the person.s check that was never shaped, or never had its readiness check, is named in the same place'
rs_require_load_bearing "/what-now says it once, with what is missing" \
  "$WHATNOW" 'once, with what it is missing'

# /what-now names a piece waiting in review for the person as theirs, and leads
# with what the gate's report finds, since a board that says something untrue
# makes every other line it reads wrong.
rs_require_load_bearing "/what-now names a piece in review for the person as theirs" \
  "$WHATNOW" 'a piece in `state:in-review` with `review:person` is the person.s own'
rs_require_load_bearing "/what-now leads with the gate's report" \
  "$WHATNOW" 'where `python3 \.agents/tools/gate\.py report` names anything, lead with it'
rs_require_absent "/what-now no longer reads a broken label" "$WHATNOW" 'anything labelled `broken`'
rs_require_absent "/what-now no longer reads a to-check column" "$WHATNOW" 'a piece under `to check`'

rs_done
