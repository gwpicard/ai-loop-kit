#!/usr/bin/env sh
# state-moves.sh: guard that every command moves a piece through the gate.
#
# pieces.md says every open piece is in exactly one state, and only the gate
# script, gate.py, changes one. That holds only while the commands call the
# gate. A command that writes a state label itself goes round the condition the
# gate checks, and the board then shows a move nobody earned. Nothing fails when
# that happens: the board just stops describing the work.
#
# So this reads the skills two ways. Mechanically, it finds every `gh issue
# edit`, `gh issue create` and `gh label` line in .agents/skills/ and fails on
# one that writes a state label, in the v1 families or the old words, and on any
# `parked` left behind. In prose, it requires a gate.py call for each move a
# command makes, and proves each one load-bearing.
#
# plan-printout.sh proves the printout draws the board, piece-states.sh that
# pieces.md still defines it, and gate-script.sh that the gate keeps it. This
# proves the commands still go through the gate.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
TRIAGE="$SKILLS/change-triage/SKILL.md"
SHAPE="$SKILLS/shape/SKILL.md"
IMPLEMENT="$SKILLS/implement/SKILL.md"
LONGER="$SKILLS/implement/references/running-longer.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
MERGE="$SKILLS/section-builder/references/merge.md"
FIX="$SKILLS/fix/SKILL.md"
WHATNOW="$SKILLS/what-now/SKILL.md"
QUEUE="$SKILLS/queue/SKILL.md"
SYNC="$SKILLS/sync/SKILL.md"
BLOCKED="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
WORKFLOW="$ROOT/WORKFLOW.md"
SCENARIOS="$ROOT/.agents/tests/scenarios.md"

rs_init "State-move checks"
rs_exists "$TRIAGE" "$SHAPE" "$IMPLEMENT" "$LONGER" "$BUILDER" "$MERGE" "$FIX" \
  "$WHATNOW" "$QUEUE" "$SYNC" "$BLOCKED" "$WORKFLOW" "$SCENARIOS"

# --- read mechanically ------------------------------------------------------

# direct_writes <dir>: each gh command in the skills that writes a state label
# rather than going through the gate. Only the command itself is read, up to
# the end of its code span, so a sentence that names a state beside a command
# for another label is not taken for one. The lists of refused spellings in
# blocked-commands.md, and the gate, hook and deny rules that do the refusing,
# are where those spellings are meant to be, so they are left out.
direct_writes() {
  grep -rnoE 'gh (issue (edit|create)|label)[^`]*' "$1" \
    | grep -v '/setup-ai-build-kit/references/blocked-commands\.md:' \
    | grep -v '/templates/foundation/gate\.py:' \
    | grep -v '/templates/foundation/state-guard\.sh:' \
    | grep -v '/templates/foundation/claude-settings\.json:' \
    | grep -E '(state|shaping|review):|--(add|remove)-label[ =]"?(ready|building|idea|parked|shaping|blocked|broken|to check|needs-)' \
    || true
}
# parked_left <dir>: each `parked` left in the skills. The gate's list of AI
# Build Kit's labels, and pieces.md's, name it so the report can say it is a
# label the kit does not use.
parked_left() {
  grep -rni 'park' "$1" \
    | grep -v '"to check", "parked", "blocked"' \
    | grep -v '`to check`, `parked`, `blocked`' \
    || true
}

found=$(direct_writes "$SKILLS")
[ -z "$found" ] || printf '%s\n' "$found" >&2
rs_report "no skill, reference or template writes a state label with gh directly" \
  "$([ -z "$found" ] && echo yes || echo no)"
found=$(parked_left "$SKILLS")
[ -z "$found" ] || printf '%s\n' "$found" >&2
rs_report "parked is gone from every skill" "$([ -z "$found" ] && echo yes || echo no)"

cp -R "$SKILLS" "$rs_dir/planted"
printf '\n`gh issue edit <number> --add-label state:ready --remove-label shaping:check`\n' \
  >> "$rs_dir/planted/section-builder/SKILL.md"
rs_report "a copy with one direct state-label write planted fails" \
  "$([ -n "$(direct_writes "$rs_dir/planted")" ] && echo yes || echo no)"
rm -rf "$rs_dir/planted"
cp -R "$SKILLS" "$rs_dir/planted"
printf '\n`gh issue edit <number> --add-label building --remove-label ready`\n' \
  >> "$rs_dir/planted/fix/SKILL.md"
rs_report "a copy with one old-label write planted fails" \
  "$([ -n "$(direct_writes "$rs_dir/planted")" ] && echo yes || echo no)"
rm -rf "$rs_dir/planted"
cp -R "$SKILLS" "$rs_dir/planted"
printf '\nThe piece is parked with its reason.\n' >> "$rs_dir/planted/sync/SKILL.md"
rs_report "a copy with parked planted fails" \
  "$([ -n "$(parked_left "$rs_dir/planted")" ] && echo yes || echo no)"
rm -rf "$rs_dir/planted"

# A missing state label is never created by hand: gate.py labels made the set.
for site in "$SHAPE" "$IMPLEMENT" "$BUILDER" "$FIX"; do
  rs_require_absent "$(basename "$(dirname "$site")") no longer creates a missing state label" \
    "$site" 'creating the label first if the project lacks it'
done

# --- capture, in change-triage ----------------------------------------------

rs_rule "a note for later is not classified or routed" 'do not classify or route it'
rs_rule "a note is captured through the gate in the person's words, nothing settled" \
  'capture it through the gate, `python3 \.agents/tools/gate\.py capture --title "<title>" --body-file <file>`, which opens it in `state:shaping` and `shaping:raw` with the person.s own words as the body and nothing settled'
rs_rule "/shape later and /shape idea are capture too" '`/shape later` or `/shape idea`'
rs_rule "a duplicate note is added to the existing piece as a comment" \
  'add the person.s words to that issue as a comment and say which one'
rs_rule "a new issue only when the person says it is different" \
  'file a new issue only if the person says theirs is different'
rs_rule "a request that becomes a piece is captured through the gate" \
  'take it in through the gate with `python3 \.agents/tools/gate\.py capture --title "<title>" --body-file <file>`, never with `gh issue create`'
rs_rule "a captured piece gets exactly one type label before its first move" \
  'give it exactly one `type:` label before its first move, `gh issue edit <number> --add-label type:<feature[|]bug[|]chore>`'
rs_rule "a repair of promised behaviour is type:bug" \
  'a repair of behaviour the masterplan promised is `type:bug`'
rs_rule "upkeep nobody sees is type:chore" \
  'upkeep that changes nothing a person sees in the tool is `type:chore`'
rs_rule "anything else is type:feature" 'anything else is `type:feature`'
rs_rule "a routed question moves the piece to the sub-state that names it" \
  'write the question under `## open question` and move the piece through the gate to the sub-state that names the route'
rs_rule "the three sub-states a question can route to" \
  '`python3 \.agents/tools/gate\.py move <number> clarify` for clarify, `prototype` for a decision prototype, `research` for a source check or a search for existing work'
rs_rule "a piece in check is waiting for its readiness check" \
  'a piece in `shaping:check` is waiting for its readiness check'
rs_rule "an earlier idea is searched among the issues closed as not planned" \
  'an idea left out is an issue closed as not planned, so search the issues closed as not planned too'
rs_rule "the overlap read looks at what is being built now" 'and at anything in `state:building`'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_guard "$TRIAGE" "change-triage"
rs_require_absent "change-triage no longer files an idea label" "$TRIAGE" 'labelled `idea`'
rs_require_absent "change-triage no longer writes broken" "$TRIAGE" '`broken`'
rs_require_absent "change-triage no longer writes a needs- label" "$TRIAGE" 'needs-clarification'

# --- every move in /shape -----------------------------------------------------

rs_reset
rs_rule "only the gate moves a piece, old state off as the new goes on" \
  'only the gate script moves a piece\. it takes the old state off in the same step as it puts the new one on'
rs_rule "an open question for the person moves raw to clarify" \
  'to `shaping:clarify` for a decision only the person makes, `python3 \.agents/tools/gate\.py move <number> clarify`'
rs_rule "a fact from outside moves raw to research" \
  'to `shaping:research` for a fact from outside, `python3 \.agents/tools/gate\.py move <number> research`'
rs_rule "a flow nobody has seen moves raw to prototype" \
  'to `shaping:prototype` for a flow the person has not seen, `python3 \.agents/tools/gate\.py move <number> prototype`'
rs_rule "the question is written before the move" 'once the question is written under `## open question`'
rs_rule "no open question moves raw to spec" \
  'a piece with no open question moves from `shaping:raw` to `shaping:spec`, `python3 \.agents/tools/gate\.py move <number> spec`'
rs_rule "a settled question is written, then the piece moves to spec" \
  'a settled question is written under `## decided` for clarify and prototype, or under `## research` with a source for each claim for research, and the piece moves to `shaping:spec`'
rs_rule "research that needs the person moves to clarify" \
  'research whose result needs the person moves to `shaping:clarify`'
rs_rule "a written contract moves to check" \
  'once its contract is written, the piece moves to `shaping:check`, `python3 \.agents/tools/gate\.py move <number> check`, and the readiness check runs'
rs_rule "ready on Ready" 'on ready the piece moves to `state:ready`, `python3 \.agents/tools/gate\.py move <number> ready`'
rs_rule "not ready goes to the sub-state that closes its gaps" \
  'on not ready it moves to the sub-state that closes its gaps'
rs_rule "typed alone, an issue with no state is captured, never opened twice" \
  'take it in with `python3 \.agents/tools/gate\.py capture <number>`, and never open a second issue for it'
rs_rule "a captured issue gets exactly one type label first" \
  'give it exactly one `type:` label before its first move, `gh issue edit <number> --add-label type:<feature[|]bug[|]chore>`'
rs_rule "research says before it starts whether it needs the person" \
  'before it starts, write one line on the piece: "needs your decision: yes" or "needs your decision: no"'
rs_rule "research that leaves a question open stays in research with the gap" \
  'the piece stays in `shaping:research` with the gap written on it'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_rule "an unreachable GitHub leaves the piece as it is" \
  'the gate changes nothing, so say so and leave the piece as it is'
rs_rule "capture is change-triage's" 'that is capture, and change-triage handles it'
rs_guard "$SHAPE" "the /shape skill"
rs_require_absent "/shape no longer swaps needs- labels" "$SHAPE" 'needs-clarification'
rs_require_absent "/shape no longer labels an idea" "$SHAPE" 'labelled `idea`'

# --- the claim, in /implement and section-builder ---------------------------

rs_reset
rs_rule "the claim comes before any work" 'claim the piece before any work'
rs_rule "the claim goes through the gate" \
  '`python3 \.agents/tools/gate\.py move <number> building --assignee .me`'
rs_rule "a claim that cannot be made starts nothing" \
  'a piece nobody could claim may be claimed by somebody else'
rs_rule "an issue with no state is not built, however full its body" \
  'has not been taken in yet, however full its body'
rs_rule "a piece in two states is not built" 'a piece carrying two states is not built'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_guard "$IMPLEMENT" "the /implement skill"

rs_reset
rs_rule "the claim goes through the gate with the builder as assignee" \
  'through the gate, which writes `state:building` and the assignee in one call, `python3 \.agents/tools/gate\.py move <number> building --assignee <login>`'
rs_rule "a run's claim names the run" 'adding `--run <run name>` in a run'
rs_rule "an unreachable GitHub fails the claim and starts nothing" \
  'the claim fails: say so, and do not start the piece'
rs_rule "the open pull request moves the piece to review through the gate" \
  'when the pull request opens, move the piece to `to check`, which is `state:in-review` with `review:person`, through the gate: `python3 \.agents/tools/gate\.py move <number> in-review`'
rs_rule "the checkpoint route closes the piece on save" \
  'close the issue on save, `gh issue close <number> --reason completed`, and then run `python3 \.agents/tools/gate\.py tidy`'
rs_rule "the checkpoint route is named as the one exception" \
  'the one route where a piece closes when it is saved rather than when a pull request merges'
rs_rule "the flagged route kicks the piece back to clarify with the caution" \
  'write a `## kickback` section naming the caution and the condition, and move the piece back to `shaping:clarify` through the gate, `python3 \.agents/tools/gate\.py move <number> clarify`'
rs_rule "it stays in shaping until the acceptance is recorded" \
  'it stays in shaping until the person carries on after the risk notice and the acceptance is recorded'
rs_rule "three failed attempts kick back to spec for an impossible check" \
  'to `shaping:spec`, `python3 \.agents/tools/gate\.py move <number> spec`, when an attempt showed a check that cannot be met as written'
rs_rule "and to research otherwise" \
  'and to `shaping:research`, `python3 \.agents/tools/gate\.py move <number> research`, otherwise'
rs_rule "software outside the folder in a run kicks back to clarify" \
  'in a run with nobody watching, kick the piece back to `shaping:clarify` instead'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_guard "$BUILDER" "section-builder"

# --- the run ------------------------------------------------------------------

rs_reset
rs_rule "a run claims through the gate, naming the run" \
  'make the claim through the gate, `python3 \.agents/tools/gate\.py move <number> building --run <run name> --assignee .me`'
rs_rule "a hard choice seen at the plan goes back through the gate" \
  'then move it with no claim to undo: `python3 \.agents/tools/gate\.py move <number> clarify`'
rs_rule "a hard choice met while building is kicked back through the gate" \
  'write the question on the piece under a `## kickback` section, push the branch and keep it, and send it back to shaping, `python3 \.agents/tools/gate\.py move <number> clarify --run <run name>`'
rs_rule "three failed attempts kick back through the gate" \
  'after the third, kick it back: write a `## kickback` section on the piece'
rs_rule "a piece in hand at the end goes back to ready through the gate" \
  'give the piece back to `state:ready` with `python3 \.agents/tools/gate\.py move <number> ready --run <run name>`'
rs_rule "the checkpoint route in a run closes on save, then tidies" \
  '`gh issue close <number> --reason completed` followed by `python3 \.agents/tools/gate\.py tidy`'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_guard "$LONGER" "running-longer.md"
rs_require_absent "a run never drops a piece it stops" "$LONGER" 'gate\.py drop'
sed 's#python3 \.agents/tools/gate\.py move <number> ready --run <run name>#python3 .agents/tools/gate.py drop <number> --reason "run ended"#' \
  "$LONGER" > "$rs_dir/longer-drops.md"
rs_fold "$rs_dir/longer-drops.md" > "$rs_dir/longer-drops"
if rs_check "$rs_dir/longer-drops" >/dev/null \
  && ! grep -q 'gate\.py drop' "$rs_dir/longer-drops"; then
  rs_report "a copy of running-longer.md that sends a run stop to gate.py drop fails" no
else
  rs_report "a copy of running-longer.md that sends a run stop to gate.py drop fails" yes
fi

# --- /fix -----------------------------------------------------------------------

rs_reset
rs_rule "/fix claims only a repair in ready, through the gate" \
  'claim it before step 1 only when the repair is in `state:ready`: `python3 \.agents/tools/gate\.py move <number> building --assignee .me`'
rs_rule "a repair in shaping is not claimed" 'a repair in `state:shaping` is not claimed'
rs_rule "an issue with no state is captured with type:bug" \
  'nor is an issue with no state, which `/fix` first takes in with `python3 \.agents/tools/gate\.py capture <number>` and `gh issue edit <number> --add-label type:bug`'
rs_rule "either goes to /shape first" \
  'for either, say in one line that the repair is shaped first, and hand it to `/shape`'
rs_rule "a claim that belongs to /shape goes back through the gate" \
  'goes back with a `## kickback` section saying why, `python3 \.agents/tools/gate\.py move <number> clarify`'
rs_rule "a repair with no issue is built without a claim" 'a repair with no issue is built without a claim'
rs_rule "/fix reads the bug pieces" 'the open issues labelled `type:bug`'
rs_rule "a refused gate call is reported and that move stops" \
  'where the gate refuses a move, tell the person its line in plain words and stop that move'
rs_guard "$FIX" "the /fix skill"
rs_require_order "/fix claims after the promise check" "$FIX" \
  'never promised there' 'the repair is confirmed as promised'
rs_require_absent "/fix no longer reads broken" "$FIX" '`broken`'
rs_require_absent "/fix no longer calls a repair labelled broken" "$FIX" 'labelled broken'

# --- /what-now --------------------------------------------------------------

rs_reset
rs_rule "a piece in review for the person is theirs" \
  'a piece in `state:in-review` with `review:person` is the person.s own'
rs_rule "it waits for them to try it or merge it" 'waiting for them to try it or merge it'
rs_rule "the gate's findings lead" \
  'where `python3 \.agents/tools/gate\.py report` names anything, lead with it'
rs_rule "a bug comes first among the rest" 'an open piece labelled `type:bug` comes next'
rs_guard "$WHATNOW" "the /what-now skill"
rs_require_order "the gate's findings come before the bugs" "$WHATNOW" \
  'gate\.py report` names anything' 'labelled `type:bug` comes next'
rs_require_absent "/what-now no longer reads broken" "$WHATNOW" '`broken`'
rs_require_absent "/what-now no longer names a to-check column" "$WHATNOW" 'under `to check`'

# --- /queue -----------------------------------------------------------------

rs_reset
rs_rule "a claimed piece or one in review is in neither group" \
  'a piece under `building` or under either `in review` column is in neither group'
rs_rule "the waiting group is the held-up pieces" 'the pieces under `held up`'
rs_guard "$QUEUE" "the /queue skill"

# --- /sync's repair, and the tidy after a merge -----------------------------

rs_reset
rs_rule "sync runs the gate's report" \
  'run `python3 \.agents/tools/gate\.py report`'
rs_rule "the person chooses what each finding becomes" \
  'then let the person choose'
rs_rule "the evidence is named beside each finding" \
  'an open pull request that closes it means `state:in-review`'
rs_rule "the kit never writes a gate label by hand" \
  'the labels the gate owns are never written by hand'
rs_rule "sync tidies the closed issues after the report" \
  'then run `python3 \.agents/tools/gate\.py tidy`'
rs_rule "it says what changed" 'say what changed, piece by piece'
rs_rule "a stale piece may be closed as not planned" 'should it be closed as not planned'
rs_guard "$SYNC" "the /sync skill"
rs_require_order "the report comes before the tidy" "$SYNC" \
  'gate\.py report`' 'gate\.py tidy`'
rs_require_absent "/sync no longer repairs two states by hand" "$SYNC" 'take the others off in one step'

rs_require_load_bearing "the merge step tidies once a merge has gone through" "$MERGE" \
  'once a merge has gone through, run `python3 \.agents/tools/gate\.py tidy`'

# --- a refused gate call ----------------------------------------------------

rs_require_load_bearing "blocked-commands says a refused gate move is reported and stopped" \
  "$BLOCKED" 'if the gate refuses the move too, tell the person what it said and stop that move'
rs_require_load_bearing "and never reached another way" \
  "$BLOCKED" 'never reach the same change another way'

# --- WORKFLOW.md section 5 --------------------------------------------------

rs_require_load_bearing "WORKFLOW.md says every command moves a piece through the gate" \
  "$WORKFLOW" 'every command moves a piece through the gate script and takes the old state off in the same step'
rs_require_load_bearing "WORKFLOW.md says a refused move is explained and stopped" \
  "$WORKFLOW" 'when the gate refuses a move, the command tells you why and stops that move'
rs_require_load_bearing "WORKFLOW.md says the open pull request moves it to review for you" \
  "$WORKFLOW" 'moves it to `state:in-review` with `review:person` when its pull request opens'
rs_require_load_bearing "WORKFLOW.md says an unreachable GitHub starts nothing" \
  "$WORKFLOW" 'does not start a piece it could not claim'
rs_require_load_bearing "WORKFLOW.md says /fix starts no repair it could not claim" \
  "$WORKFLOW" 'does not start a repair it could not claim'
rs_require_load_bearing "WORKFLOW.md says a failed or stopped piece goes back to shaping" \
  "$WORKFLOW" 'goes back to shaping with a `## kickback` section'
rs_require_load_bearing "WORKFLOW.md says a note is taken in raw" \
  "$WORKFLOW" 'as a raw piece in your own words'
rs_require_absent "WORKFLOW.md no longer parks a piece" "$WORKFLOW" 'is parked with'
rs_require_absent "WORKFLOW.md no longer names to check as a column" \
  "$WORKFLOW" 'moves it to to check when its pull request opens'

rs_require_absent "the scenario no longer gives blocked two meanings" \
  "$SCENARIOS" 'the `blocked` label keeps the two meanings'

rs_done
