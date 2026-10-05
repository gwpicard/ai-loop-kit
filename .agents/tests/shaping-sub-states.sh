#!/usr/bin/env sh
# shaping-sub-states.sh: guard the one route every piece takes through shaping.
#
# A piece is shaped through sub-states, and each one holds a different job:
# raw holds the person's words, research finds facts, clarify asks the person,
# prototype shows them something, spec writes the contract and check runs the
# readiness check. The rules for each live as prose in change-triage and
# /shape, so this reads them back and proves each one load-bearing.
#
# The first part guards triage in raw and the bug fast path. Triage writes the
# type, a guess at the loop module, any overlap and the first open question
# onto the piece, then moves it on. Two failures matter most. A guess written
# as if it were the bar would pass the ready-gate lint as a decided loop
# module. And a bug with a reproduction a person can follow that is still sent
# round the questions makes the person answer what they already said.
#
# The second part guards research, clarify and prototype, the three sub-states
# that settle a question. Research finds facts and never decides, so a finding
# that needs a choice goes to the person. Clarify asks the person, once, the
# questions only they can answer: the pre-mortem when the reach touches
# something that hurts when it breaks, and the bar for a goal or a gauntlet.
# Prototype shows them something and keeps the throwaway out of the build.
#
# The third part guards spec, check and kickback intake. Spec writes the whole
# contract alone and commits the acceptance checks on a branch of their own,
# so the bar exists before the build. Check runs the lint and then a session
# that did not shape the piece, and sends each gap to the sub-state that can
# close it. A kicked-back piece is read before anybody is asked anything, and
# its branch is never lost. The words a person reads, in WORKFLOW.md and the
# skill's description, are held here too.
#
# The fourth part guards the removal of /fix. A bug is shaped like any other
# piece and built by the fix loop, which section-builder loads for a `loop:fix`
# piece. No skill may send the person to a command that is gone, so every
# `/fix` left under .agents/skills/ fails, except the one sentence in
# change-triage that takes a `/fix` typed from habit as a repair report.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
CLARIFY="$ROOT/.agents/skills/clarify/SKILL.md"

rs_init "Shaping sub-state checks"
rs_exists "$TRIAGE" "$SHAPE" "$CLARIFY" "$WORKFLOW"

# --- triage in raw, in change-triage ------------------------------------------

# The report check /fix made before a repair. Without it a wish worded as a
# complaint is shaped as a bug, and the fix loop hunts for a fault nobody made.
rs_rule "a repair of promised behaviour is told from a wish against the masterplan" \
  'behaviour the masterplan promised and the tool does not do is a repair, and becomes `type:bug`'
rs_rule "a wish the masterplan never made becomes type:feature" \
  'behaviour the masterplan never promised is a wish, however it is worded, and becomes `type:feature`'

rs_rule "raw triage writes its findings on the piece before it moves" \
  'triage it and write what it found on the piece, in this order, before it moves'
rs_rule "it writes the type label first" 'its `type:` label, from step 1.s comparison with the masterplan'
rs_rule "the loop module is written as a marked guess" \
  'under `## loop`: `loop module: <module> \(guess, <one line why>\)`'
rs_rule "so the lint never reads a guess as the bar" 'so the lint never reads a guess as the bar'
rs_rule "spec replaces the guess" \
  '`shaping:spec` replaces the line with the module the contract is written for'
rs_rule "overlaps with open and closed pieces are written on the piece" \
  'any piece this one repeats or overlaps, open or closed, completed or not planned, under `## overlaps`'
rs_rule "a not-planned match brings its reason back" \
  'add the reason it was left out'
rs_rule "the first open question is written under Open question" \
  'the first open question, under `## open question`'
rs_rule "the piece moves to the sub-state of that question" \
  'move it through the gate to the sub-state that answers that question'
rs_rule "or to spec when there is none" \
  'with no open question, move it to `shaping:spec`'
rs_rule "the fit check comes before any sub-state" \
  'stops for the fit check before the piece moves to any sub-state'

# The bug fast path. Each route removed sends a bug the wrong way: one with a
# reproduction is asked for it again, one without is specified from a guess.
rs_rule "a bug with a reproduction a person can follow" \
  'a `type:bug` piece with a reproduction a person can follow'
rs_rule "the reproduction is steps, expected result and actual result" \
  'the steps, the expected result and the actual result'
rs_rule "it goes straight from raw to spec" 'it goes from `shaping:raw` straight to `shaping:spec`'
rs_rule "and takes loop:fix" \
  'takes `loop:fix`: write `loop module: fix` under `## loop` with no guess mark'
rs_rule "the fix label is written directly" '`gh issue edit <number> --add-label loop:fix`'
rs_rule "a bug with no clear reproduction goes to clarify with the missing step" \
  'a bug with no clear reproduction goes to `shaping:clarify` with the missing step as its question'
rs_guard "$TRIAGE" "change-triage"

# The capture path still files a note untriaged; the triage waits for /shape.
rs_require_order "triage in raw sits inside the routing step" "$TRIAGE" \
  '^## Step 4: Route' '^### Triage in raw'

# --- /shape -------------------------------------------------------------------

rs_reset
rs_rule "a raw piece is triaged first" \
  'a piece in `shaping:raw` is triaged first, as change-triage.s "triage in raw" says'
# The order is one rule: a piece that needs nobody is taken before one that
# needs the person, and new raw notes come last so half-shaped work finishes.
rs_rule "typed alone, /shape takes pieces in one order" \
  'a piece with a `## kickback` section first, then a piece waiting in `shaping:check`, then `shaping:research`, which needs nobody, then `shaping:clarify` and `shaping:prototype` when the person is there, then `shaping:spec`, then the oldest `shaping:raw`'
rs_rule "a fast-path bug is offered to /implement once ready" \
  'offer `/implement <number>` as soon as it is ready'
rs_rule "spec replaces a guessed loop module" 'replace a guessed `loop module:` line'
rs_rule "and writes the loop label where the piece has none" \
  'where it has none, `gh issue edit <number> --add-label loop:<module>`'
rs_rule "an unreachable GitHub files nothing" \
  'where github cannot be reached when a request would become a piece, nothing is filed'
rs_rule "and the person's words are repeated back" \
  'repeat the person.s words back to them in full'
rs_guard "$SHAPE" "the /shape skill"
rs_require_absent "/shape no longer takes the lowest-numbered piece in shaping" \
  "$SHAPE" 'take the lowest-numbered piece still in shaping'

# --- research, clarify and prototype, in /shape ------------------------------

rs_reset
rs_rule "the three asking sub-states have no fixed order" \
  'there is no fixed order between research, clarify and prototype'
rs_rule "a sub-state with nothing to do is skipped" \
  'a sub-state with nothing to do is skipped'
# Research finds facts. A research step that chose would hand the person a
# decision already made, written up as if it were a fact.
rs_rule "research answers what is true and never decides" \
  '`shaping:research` answers what is true and never decides'
rs_rule "on a project with code research runs the reach check on origin/main" \
  'run the reach check in the `section-builder` skill.s `references/reach-check\.md` on `origin/main`'
rs_rule "it adds one query of saved history" \
  'add one query of saved history for files that change together'
rs_rule "through the shipped history script" \
  'the `section-builder` skill.s `scripts/co-change\.sh`'
rs_rule "each hit is mapped to a named area" \
  'map each hit to a named area of the project'
rs_rule "research says which engine it used" \
  'say which reach-check engine you used'
rs_rule "each claim names its source" \
  'one list item for each claim, each naming its source'
rs_rule "research ends with a recommendation" \
  'end with one line that is not a list item, `recommendation:`'
rs_rule "the recommendation decides nothing" \
  'research itself decides nothing'
rs_rule "a finding that needs a choice goes to clarify as its question" \
  'a finding that needs a choice moves the piece to `shaping:clarify` with the choice as its question'
# Clarify asks the person what they want, and the answer is on the piece
# before the gate moves it.
rs_rule "clarify answers what the person wants, one question at a time" \
  '`shaping:clarify` answers what the person wants, through the clarify skill, one question at a time'
rs_rule "each answer is written into Decided before the gate moves the piece" \
  'each answer is written into `## decided` before the gate moves the piece'
rs_rule "clarify asks the pre-mortem and agrees a goal's or gauntlet's bar" \
  'asks the pre-mortem once, and a goal or gauntlet piece agrees its bar here'
# Prototype shows the person something, and the throwaway never ships.
rs_rule "prototype runs the decision prototype or builds toward their mock" \
  '`shaping:prototype` settles the piece with something to look at'
rs_rule "the decision goes into Decided in words" \
  'the decision goes into `## decided` in words'
rs_guard "$SHAPE" "the /shape sub-state sections"

for heading in '^### Research: what is true$' '^### Clarify: what the person wants$' \
  '^### Prototype: what the person has to see$'; do
  rs_require_order "/shape gives each asking sub-state a section of its own" "$SHAPE" \
    '^## When a piece is waiting on a question$' "$heading"
done

# --- the pre-mortem and the bars, in clarify ---------------------------------

# Asked everywhere it becomes noise; asked nowhere and the If it breaks: line is
# written from a guess. So the trigger and the words are both held.
rs_reset
rs_rule "the pre-mortem's trigger" \
  'where the reach touches a sensitive area, stored data or anything that leaves the tool, ask once'
rs_rule "the pre-mortem's words" \
  '"say this went live and went wrong\. who noticed, and what did they see\?"'
rs_rule "the answer becomes the If it breaks line" \
  'the answer becomes the piece.s `if it breaks:` line'
rs_rule "a change that cannot be undone is marked not reversible" \
  'a data change that cannot be undone is marked there with the words `not reversible`'
rs_rule "it is skipped where the reach touches none of the three" \
  'skip it where the reach touches none of the three'
rs_rule "a goal's metric, command, target and budget are agreed" \
  'for a goal piece, the person names or approves what is measured, the command that measures it, the target and a budget'
rs_rule "and written under Loop with the date" \
  'write all four under `## loop` with the date'
rs_rule "a gauntlet's reference and budget are agreed" \
  'for a gauntlet piece, the person names or approves a reference, a web address or a file in the project, and a budget'
rs_rule "and written under Loop with the date too" \
  'write both under `## loop` with the date'
rs_rule "a guess at the bar is written only once approved" \
  'written only once the person approves it'
rs_guard "$CLARIFY" "the clarify skill"

# --- spec: the contract, in /shape -------------------------------------------

# Spec has no question, so the system writes the contract alone. The checks are
# real tests on a branch of their own, which is what makes the bar exist
# before anybody builds against it.
rs_reset
rs_rule "spec writes the whole contract alone" \
  '`shaping:spec` has no open question, so write the whole contract alone'
rs_rule "the contract holds the loop module and bar, the reach and Not in this piece" \
  'the loop module and its bar, the reach fields, `## not in this piece`'
rs_rule "a build or fix piece gets its acceptance checks as real tests" \
  'for a build or fix piece, write the acceptance checks as real tests'
rs_rule "on a spec branch cut from origin/main" \
  'commit them on a branch named `spec/<number>-<short name>`, cut from `origin/main`'
rs_rule "holding test files only, and pushed" 'holding test files only, and push it'
rs_rule "Acceptance branch names it" '`acceptance branch:` under `## loop` names it'
rs_rule "a goal or gauntlet piece gets no acceptance branch here" \
  'a goal or gauntlet piece gets no acceptance branch here'
# A check that already passes guards a line that is already true, so the
# person has to say what the piece is for.
rs_rule "a check passing on origin/main sends the piece to clarify" \
  'an acceptance check that passes on `origin/main` when written means the line it guards is already true'
rs_rule "with that finding as its question" \
  'write that finding as the one question under `## open question` and move the piece to `shaping:clarify`'
rs_rule "a question found while writing sends the piece back" \
  'a question found while writing sends the piece back to the sub-state it needs'
rs_rule "only a new question leaves spec for asking" \
  'the gate moves a piece out of spec to research, clarify or prototype only with a new question'
rs_rule "a question already asked and answered is refused" \
  'a question already asked and answered, still written on the piece, is refused'
rs_rule "spec leaves for check only once Loop and Reach changed" \
  'the gate refuses that move until the two sections have changed since the piece entered spec'
# A second spec run never loses the first branch's work, and a half-finished
# run is resumed rather than forked.
rs_rule "a kickback or a passing check cuts a new acceptance branch" \
  'after a kickback or after a check was found passing on `origin/main`, cut a new acceptance branch from `origin/main`'
rs_rule "named with the next unused number from 2" \
  'name it `spec/<number>-<short name>-<n>`, where `<n>` is the next unused number from 2'
rs_rule "the new branch holds test files only" 'hold test files only on it'
rs_rule "still-valid checks are carried over" 'carry the checks that are still valid onto it'
rs_rule "the earlier branch is never deleted, and named as kept" \
  'never delete the earlier branch: name it on a `kept branch:` line, never as `acceptance branch:`'
rs_rule "even when it holds commits the person wants kept" \
  'even when it holds commits the person wants kept'
# Where the kept branch is written depends on why spec ran again. A piece that
# never left shaping must not gain a Kickback section, because /shape reads
# that section first and takes it for a build that came back.
rs_rule "after a kickback the kept branch goes under Kickback" \
  'after a kickback, the `kept branch:` line goes under `## kickback`'
rs_rule "after a passing check it goes in Loop beside Acceptance branch" \
  'after a check was found passing on `origin/main`, it goes in `## loop` beside `acceptance branch:`'
rs_rule "a piece that never came back from a build gains no Kickback section" \
  'a piece that never came back from a build gains no `## kickback` section'
rs_rule "since /shape reads that section first, as a returned build" \
  '`/shape` reads that section first and as a build that came back'
rs_rule "a half-finished spec run reuses its branch" \
  'when neither applies and `acceptance branch:` is not yet written, as after a spec run stopped half-way with its branch pushed, reuse that branch and cut no new one'
# A project with no code online.
rs_rule "a spec branch's first push asks first" \
  'the first push of a spec branch on a project whose code is not online asks first, as a piece.s first push does'
rs_rule "with no origin/main the first-upload question comes before anything is cut" \
  'where `origin/main` does not exist, ask the first-upload question before cutting anything'
rs_rule "after a yes main is created and the branch stands on origin/main" \
  'after a yes, cut the spec branch from the local `main`, push it, and create `main` on github at the commit it was cut from'
rs_rule "after a no the piece stays in spec with the reason" \
  'after a no, push nothing: the piece stays in `shaping:spec` with the reason written on it'
rs_rule "the lint refuses the piece until then" \
  'answer the first-upload question in `/shape`'
rs_rule "with no test command the checks are written for the floor's runner" \
  'where agents\.md.s stack section records `test command: none for <language>`, write the acceptance checks as test files for the runner'
rs_rule "named under Loop as Test runner" \
  'name it under `## loop` as `test runner: <runner>`, the field the lint reads'
rs_rule "the build that adds the runner records the test command" \
  'the build that adds the runner records the test command in the stack section'
rs_guard "$SHAPE" "the /shape spec section"

# --- check: the lint, the fresh checker and where a gap goes -----------------

rs_reset
rs_rule "check runs the lint, then the fresh checker, then the move to ready" \
  '`shaping:check` runs the ready-gate lint, then the fresh checker, then `gate\.py move <number> ready`'
rs_rule "on a lint refusal the fresh checker does not run" \
  'on a lint refusal the fresh checker does not run'
rs_rule "the lint's gaps become the Readiness section" \
  'write the lint.s gaps as the piece.s `## readiness` section'
rs_rule "its first line names the lint" 'a first line `<date>, ready-gate lint: not ready`'
rs_rule "one BLOCKING lint line for each gap" \
  'then one `- blocking lint: <gap>` line for each gap the lint printed'
rs_rule "the gate reads that section as the checker's" \
  'the gate.s move out of `shaping:check` reads that section as it reads the fresh checker.s'
rs_rule "each gap goes to the sub-state that closes it" \
  'write each blocking gap on the piece and move it through the gate to the sub-state that closes the gap'
rs_rule "a person's gap goes to clarify as its Open question" \
  '`shaping:clarify` for a gap a person must settle, with the gap as its `## open question`'
rs_rule "including a Relies on line that does not hold" \
  'including a relies on line whose code does not exist or does not return what the piece needs'
rs_rule "a fact from outside goes to research" '`shaping:research` for a fact from outside the project'
rs_rule "an unseen flow goes to prototype" \
  '`shaping:prototype` for a gap on item 13, a flow the person has not seen'
rs_rule "a lint refusal or the contract's wording goes to spec" \
  '`shaping:spec` for a lint refusal, or a gap in the contract.s own wording'
rs_rule "several gaps: the first of clarify, prototype, research and spec" \
  'where gaps need different sub-states, the piece goes to the first of clarify, prototype, research and spec, and the other gaps stay written on it'
rs_rule "where it went is said in one line" 'say in one line where the piece went and why'
rs_rule "no needs- label is written" 'no `needs-` label is written'
rs_rule "check leaves for a sub-state only once Readiness changed" \
  'the gate moves a piece out of `shaping:check` to another sub-state only once `## readiness` has changed since the piece entered check'
rs_guard "$SHAPE" "the /shape check section"

# --- kickback intake ---------------------------------------------------------

# A kicked-back piece carries what a run learned. Asking the person again
# before reading it, or losing its branch, throws that away.
rs_reset
rs_rule "a kickback section is read first" \
  'a piece arriving in shaping with a `## kickback` section came back from a build\. read that section first'
rs_rule "what happened, what was tried, what decision is needed" \
  'what happened, what was tried, and what decision is needed'
rs_rule "answers left as comments are read before asking again" \
  'answers the person already left there are read before any question is asked again'
rs_rule "an incomplete or empty answer leaves the question open" \
  'an incomplete, unrelated or empty answer leaves the question open'
rs_rule "the branch is kept" 'keep the piece.s branch, and never delete it'
rs_rule "the question is settled in the sub-state the kickback named" \
  'settle the question in the sub-state the kickback named'
rs_rule "the contract is rewritten in spec" 'rewrite the contract in `shaping:spec`'
rs_rule "the old Readiness result is removed" 'remove the old `## readiness` result'
rs_rule "and the check runs again" 'and run the check again'
rs_guard "$SHAPE" "the /shape kickback intake"

# --- the description a person and the harness read --------------------------

DESC="$rs_dir/description.md"
grep -m1 '^description:' "$SHAPE" > "$DESC" || true
rs_reset
rs_rule "the description names the shaping sub-states" \
  'the shaping sub-states, raw, research, clarify, prototype, spec and check'
rs_rule "the description names the bug route" \
  'a bug with a clear reproduction takes the bug route, straight from raw to spec'
rs_guard "$DESC" "the /shape description line"

# --- WORKFLOW.md tells the same story ----------------------------------------

rs_reset
rs_rule "WORKFLOW section 2 says what spec and check do" \
  'in `shaping:spec` the agent writes the whole contract alone'
rs_rule "WORKFLOW says the asking sub-states have no fixed order" \
  'a piece sits in whichever of those three its next question needs, in no fixed order'
rs_rule "WORKFLOW gives the pre-mortem question" \
  'clarify asks you one question once: "say this went live and went wrong\. who noticed, and what did they see\?"'
rs_rule "WORKFLOW gives the bug fast path" \
  'if your report says what you did, what you expected and what happened instead, it goes straight from raw to spec'
rs_rule "WORKFLOW says a bug missing a step is asked for it" \
  'if a step is missing, /shape asks you for it first'
rs_rule "WORKFLOW says what a kicked-back piece looks like" \
  'a piece that comes back from a build carries a kickback section saying what happened, what was tried and what decision is needed'
rs_rule "WORKFLOW says your comments are read before you are asked again" \
  '/shape reads it first, and reads any answer you left as a comment, before asking you again'
rs_rule "WORKFLOW says the branch is kept and the check runs again" \
  'it keeps the branch, settles the question, rewrites the contract and runs the check again'
rs_guard "$WORKFLOW" "WORKFLOW.md"
rs_require_order "WORKFLOW names spec and check in section 2" "$WORKFLOW" \
  '^## 2\. ' 'In `shaping:spec` the agent writes the whole contract alone'
rs_require_order "and before section 3" "$WORKFLOW" \
  'In `shaping:spec` the agent writes the whole contract alone' '^## 3\. '
rs_require_order "WORKFLOW gives the bug route in section 5" "$WORKFLOW" \
  '^## 5\. ' 'it goes straight from raw to spec'
rs_require_order "and the kickback before section 6" "$WORKFLOW" \
  'carries a Kickback section saying what happened' '^## 6\. '

# --- removing /fix --------------------------------------------------------

BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FIXLOOP="$ROOT/.agents/skills/section-builder/references/fix-loop.md"
README="$ROOT/README.md"
SKILLS="$ROOT/.agents/skills"
rs_exists "$BUILDER" "$FIXLOOP" "$README"

# A person used to the old command still types it. There is no such command, so
# the words that follow are a repair report and /shape takes them.
rs_reset
rs_rule "a request naming /fix is a repair report" \
  'a request that names `/fix` is a repair report'
rs_rule "there is no such command" 'typed from habit: there is no such command'
rs_rule "so /shape takes it and runs" \
  'say in one line that `/shape` takes it, and run `/shape` with the words that follow'
rs_rule "the fast path names the loop that builds a bug" \
  'built by the fix loop, the `section-builder` skill.s `references/fix-loop\.md`'
rs_guard "$TRIAGE" "change-triage's route for a bug"

# The repair discipline moved, unchanged in substance, into a reference
# section-builder loads. Without the load a bug piece is built like a feature,
# with no reproduction first and no limit on attempts.
rs_require_load_bearing "section-builder loads the fix loop for a loop:fix piece" \
  "$BUILDER" 'a piece labelled `loop:fix` is a repair: load `references/fix-loop\.md`'

# fix_left <dir>: each file under the folder that still names /fix, once the one
# habit sentence in change-triage is taken out. A path such as
# `references/fix-loop.md` is not the command, so a letter, dot, dash or
# underscore on either side rules a match out.
HABIT='a request that names `/fix` is a repair report'
FIX_COMMAND='(^|[^a-z0-9_.-])/fix([^a-z0-9_-]|$)'
fix_left() {
  find "$1" -type f | sort | while IFS= read -r f; do
    folded=$(rs_fold "$f")
    case "$f" in
      */change-triage/SKILL.md) folded=$(printf '%s' "$folded" | sed -E "s@$HABIT@@") ;;
    esac
    if printf '%s' "$folded" | grep -qE "$FIX_COMMAND"; then
      echo "$f"
    fi
  done
}

if [ -z "${RS_LIST:-}" ]; then
  left=$(fix_left "$SKILLS")
  [ -z "$left" ] || printf '  still names /fix: %s\n' $left >&2
  rs_report "no skill, reference or template sends the person to /fix" \
    "$([ -z "$left" ] && echo yes || echo no)"
  cp -R "$SKILLS" "$rs_dir/planted-fix"
  printf '\nIf it is broken, type /fix.\n' >> "$rs_dir/planted-fix/what-now/SKILL.md"
  rs_report "a copy with one /fix planted fails" \
    "$([ -n "$(fix_left "$rs_dir/planted-fix")" ] && echo yes || echo no)"
  rm -rf "$rs_dir/planted-fix"
  cp -R "$SKILLS" "$rs_dir/planted-fix"
  printf '\nOr type /fix for a repair.\n' >> "$rs_dir/planted-fix/change-triage/SKILL.md"
  rs_report "a second /fix beside the habit sentence still fails" \
    "$([ -n "$(fix_left "$rs_dir/planted-fix")" ] && echo yes || echo no)"
  rm -rf "$rs_dir/planted-fix"
fi

# The README a person reads first, and WORKFLOW.md, send a broken tool to /shape.
rs_require_load_bearing "the README's broken row points at /shape" \
  "$README" '\| it.s broken \| `/shape` \|'
rs_require_absent "the README names no /fix, in the table, the diagram or the questions" \
  "$README" "$FIX_COMMAND"
rs_require_load_bearing "WORKFLOW's broken row points at /shape" \
  "$WORKFLOW" '\| it.s broken \| /shape \|'
rs_require_load_bearing "WORKFLOW section 1 has one command that changes the tool" \
  "$WORKFLOW" 'one of them changes the tool\. /implement builds a ready piece, whether it makes the tool do something new or brings it back to doing what it already should'
rs_require_load_bearing "WORKFLOW says a bug is shaped and built by the fix loop" \
  "$WORKFLOW" 'a bug is shaped like any other piece and built by the fix loop'
rs_require_absent "WORKFLOW names no /fix" "$WORKFLOW" "$FIX_COMMAND"

rs_done
