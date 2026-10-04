#!/usr/bin/env sh
# piece-contract.sh: guard the piece contract and the readiness check.
#
# A real project's pieces were detailed and still missed whole categories:
# states nobody named, data and sync rules, things leaving the device, and rules
# or numbers the change broke. Its builders then made dozens of choices alone.
# The piece template asked for none of those, the guidance told the shaper that
# most pieces leave `Decided` empty, and the session that shaped a piece was
# the one that judged it complete, so it missed the same gaps twice.
#
# So a piece now carries a short header and a complete agent layer, and a
# session that did not shape it checks it against a fixed list before it turns
# ready. Every rule here is prose a coding agent reads, so this reads it back
# and proves each one load-bearing. The quiet failure is a rule dropped in a
# tidy-up: the piece still looks shaped, the label still reads ready, and the
# gap only shows in review, after the build.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
FORM="$SKILLS/setup-ai-build-kit/templates/foundation/piece-issue.yml"
PIECES="$SKILLS/setup-ai-build-kit/references/pieces.md"
READINESS="$SKILLS/shape/references/readiness-check.md"
SHAPE="$SKILLS/shape/SKILL.md"
CLARIFY="$SKILLS/clarify/SKILL.md"
TRIAGE="$SKILLS/change-triage/SKILL.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"
FOUNDED="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
WORKFLOW="$ROOT/WORKFLOW.md"
PHILOSOPHY="$ROOT/docs/PHILOSOPHY.md"
SCENARIOS="$ROOT/.agents/tests/scenarios.md"
CASE="$ROOT/.agents/tests/replay/cases/56.txt"
FLOOR="$SKILLS/setup-ai-build-kit/references/check-floor.md"
REPORT="$SKILLS/setup-ai-build-kit/references/completion-report.md"
BASELINE="$ROOT/.agents/tests/replay/baseline.md"

rs_init "Piece contract and readiness checks"
rs_exists "$FORM" "$PIECES" "$READINESS" "$SHAPE" "$CLARIFY" "$FOUNDED" \
  "$TRIAGE" "$SETUP" "$COMPAT" "$FLOOR" "$REPORT" \
  "$WORKFLOW" "$PHILOSOPHY" "$SCENARIOS" "$CASE" "$BASELINE"

# --- the issue form: the header, then the agent layer ---------------------

rs_rule "the form asks for So that" 'id: so-that'
rs_rule "the form asks for Done when, the Works group" 'id: done-when'
rs_rule "the form asks for the cases that are not the normal one" 'id: not-the-normal-case'
rs_rule "the form asks for the masterplan change" 'id: masterplan-change'
rs_rule "the form asks what is not in this piece" 'id: not-in-this-piece'
rs_rule "the form asks for Decided" 'id: decided'
rs_rule "the form asks for Data" 'id: data '
rs_rule "the form asks what leaves the tool" 'id: leaves-the-tool'
rs_rule "the form asks what must still hold" 'id: must-still-hold'
rs_rule "the form asks what the piece relies on" 'id: relies-on'
rs_rule "the form asks for the loop module" 'id: loop-module'
rs_rule "the form asks for the bar in the Loop field" 'id: loop '
rs_rule "the form asks for the reach" 'id: reach'
rs_rule "the form asks for a crew that differs from the default" 'id: crew'
rs_rule "the form asks what the piece needs from the computer" 'id: needs-from-the-computer'
rs_rule "the loop module is a dropdown" 'type: dropdown id: loop-module'
rs_rule "the dropdown offers the four modules" 'options: - fix - build - goal - gauntlet'
rs_rule "Not in this piece is required on the form" \
  'placeholder: cancelling\. deposits\. validations: required: true'
rs_rule "the form keeps the build notes" 'id: under-the-hood'
rs_rule "the form asks for the evidence" 'id: evidence'
# The order is the contract: the header a person reads comes first, and the
# agent layer sits below the line that says so.
rs_rule "the header comes before the agent layer, in order" \
  'id: so-that.*id: done-when.*id: not-the-normal-case.*id: masterplan-change.*id: not-in-this-piece.*the fields below are the agent layer.*id: decided.*id: data .*id: leaves-the-tool.*id: must-still-hold.*id: relies-on.*id: loop-module.*id: loop .*id: reach.*id: crew.*id: needs-from-the-computer.*id: under-the-hood.*id: evidence'
rs_rule "a field that does not apply says why" \
  'a field that does not apply says why in one line\.'
rs_rule "the Reach field asks for the five lines" \
  'boundary:, reaches:, if it breaks:, depends on: and reach derived at:'
rs_guard "$FORM" "the piece form"

# The one-line Touches field is gone. Reach replaced it, and a form that still
# asked for it would give a piece a line nothing reads.
rs_require_absent "the form no longer asks for Touches" "$FORM" 'id: touches'

rs_require_absent "the form no longer says most pieces leave Decided empty" \
  "$FORM" 'most pieces leave this empty'
# The form used to put a subject label on every issue it opened. A form-opened
# issue now carries no label at all, so it has no state until the gate's report
# names it and /shape takes it in. A default label would also be a subject
# chosen before anybody read the piece.
rs_require_absent "the form applies no label by default" "$FORM" 'labels: \['

# --- pieces.md: the fields and the rules that are not fields -------------

rs_reset
rs_rule "the header and the agent layer are named" \
  'the header is `so that`, `done when`, `masterplan change`, `not in this piece` and `waiting on you`\. everything from `## decided` down is the agent layer'
rs_rule "Done when holds Works" '## done when ### works - <a rule somebody can check>'
rs_rule "Done when holds the cases that are not the normal one" \
  '### when it is not the normal case - <a case this change can show>'
rs_rule "the template carries Data" '## data <each stored record'
rs_rule "the template carries Leaves the tool" '## leaves the tool <what goes where'
rs_rule "the template carries Must still hold" '## must still hold <each rule'
rs_rule "the template carries Relies on" '## relies on <each existing thing'
rs_rule "the template carries the Loop section" '## loop loop module: <fix \| build \| goal \| gauntlet>'
rs_rule "the template carries the Reach section" '## reach boundary: <area>, <area>'
rs_rule "the template carries the Crew line" 'crew: <step> <width>, because <reason>'
rs_rule "the template carries Needs from the computer" \
  '## needs from the computer heavy: <yes \| no>'
rs_rule "the template ends on Readiness" '## readiness <written only by the readiness check>'
rs_rule "every field is considered" \
  'every field is considered\. a field in the agent layer that does not apply says why in one line'
rs_rule "the bar scales with the change" \
  'a colour change answers most fields that way and runs only the checks its change needs\. the standards always apply'
rs_rule "So that is one outcome" '`## so that` states one outcome for the person'
rs_rule "the Done when heading stays for the printout" \
  '`## done when` keeps that heading, because the printout and `/implement` read it, and holds two groups as `###` subheadings'
rs_rule "Works lines are rules naming their check" '`### works` holds checkable rules, each naming its check'
rs_rule "every case that can arise has a line" \
  'each with its check, or "does not arise, because" and the reason'
rs_rule "Not in this piece is required on every piece" \
  '`## not in this piece` is required on every piece'
rs_rule "the new Decided guidance" 'every choice a person would notice is decided here, with its reason'
rs_rule "the Data field rule" \
  'who else writes it and how the writes merge, the order on first open, limits and what goes at the limit, backup and restore, and delete and undo'
rs_rule "the Leaves the tool field rule" \
  'whether the recipient is new, which keys, the gate that decides who can reach it, and whether the build path.s personal-data line changes'
rs_rule "the Must still hold field rule" \
  'with its number and where it is measured, and which rule wins where two apply'
rs_rule "the Relies on field rule" \
  'confirmed to exist and to give the data needed, by reading or trying it'
# Contract v2: the loop module and its bar, the reach, the crew and what the
# piece needs from the computer. Each field is named with its rule, because a
# field the shaper never hears of is a field the lint will refuse every time.
rs_rule "Loop holds the module and the bar it needs" \
  '`## loop` holds `loop module: fix \| build \| goal \| gauntlet` and the bar that module needs'
rs_rule "a build bar: the acceptance branch" \
  'for `build`: `acceptance branch:`, the branch that holds the acceptance checks'
rs_rule "a build bar: a Check on every Works line, naming one test file" \
  'a `check:` on every works line, written `check: <path of one test file on the acceptance branch>`'
rs_rule "a project with no code yet still carries the branch, cut after the yes" \
  'a project with no code yet carries the branch too, cut after the person.s yes to the first upload'
rs_rule "a fix bar: the branch, the reproduction and what must not change" \
  'for `fix`: `acceptance branch:`; `reproduction:`, naming one test file on that branch that fails today, in the same form as `check:`; and `must not change:`'
rs_rule "a test runner where the project records none" \
  'for `build` or `fix` where agents\.md.s stack section records `test command: none for <language>`: `test runner:`, naming the runner'
rs_rule "a goal bar" \
  'for `goal`: `metric:`, `measured by:` \(a command\), `target:`, `budget:`, `guard checks:` and `held-out check:`'
rs_rule "the held-out check's form" \
  'a command, then `on held-out/<number>-<short name> at <commit>`, the branch and commit the spec step writes'
rs_rule "a gauntlet bar" \
  'for `gauntlet`: `reference:`, a link that can be fetched, with the person.s approval and its date; `compared by:`; `budget:`; and `guard checks:`'
rs_rule "a line the module does not need is left out" \
  'a line the module does not need is left out, never written as "none"'
rs_rule "Reach holds five lines in place of Touches" \
  '`## reach` holds five lines, and replaces the one-line `touches:`'
rs_rule "Boundary: the areas the piece may change" \
  '`boundary:` names the areas the piece may change, as `boundary: <area>, <area>`'
rs_rule "Boundary names areas, never paths" \
  'each named by the skill, record or document name, never a file path, because paths go stale'
rs_rule "Reaches: each area with its tests, or no test and the acceptance check" \
  '`reaches:` names the areas it affects without changing them, each with the existing tests that guard it by name, or "no test covers it" and the acceptance check that guards it'
rs_rule "If it breaks: who notices and how it is undone" \
  '`if it breaks:` says who notices what, and how it is undone'
rs_rule "Depends on: numbers or nothing" \
  '`depends on:` gives `#<number>` for each piece it needs, separated by commas, or `nothing`'
rs_rule "Reach derived at: a commit" '`reach derived at:` names the commit the reach was worked out on'
rs_rule "the reach line the person reads" \
  '"this changes sign-in\. it also reaches billing, which 14 checks guard\. if it breaks, people cannot sign in, and a rollback undoes it\."'
rs_rule "Crew is written only where it differs from the default" \
  '`crew:` is written only where the crew differs from the loop module.s default, as `crew: <step> <width>, because <reason>`'
rs_rule "the crew steps and their caps" \
  '`research` \(readers, cap 5\), `prototype` \(variants, cap 3\), `fix` \(reading probes, cap 3\), `goal` \(race entries, each in its own worktree, cap 3\) and `gauntlet` \(critics, cap 3\)'
rs_rule "the width never counts the builder" \
  'the width counts that step.s members and never the builder'
rs_rule "a crew with two writers is refused" \
  'naming the build or readiness check step, naming the run, or asking for more than one builder is a crew with two writers, and is refused'
rs_rule "Needs from the computer holds its five lines" \
  '`## needs from the computer` holds `heavy:`, `dev server:`, `browser:`, `expected duration:` and `cannot share:`'
# The brief rules hold the contract to what a builder can use alone.
rs_rule "brief rule: behaviour rather than steps" 'behaviour rather than steps\.'
rs_rule "brief rule: interfaces rather than file paths or line numbers" \
  'interfaces rather than file paths or line numbers\.'
rs_rule "brief rule: each acceptance criterion checkable on its own" \
  'each acceptance criterion checkable on its own\.'
rs_rule "the Under the hood field rule" \
  'holds the build approach, and the existing tests this piece may change, with the reason'
rs_rule "the Evidence field rule" \
  'names the kind of proof, summarising the checks on the done when lines'
rs_rule "Readiness is the stored result later steps read" \
  '`## readiness` is written by the readiness check and read by every later step'
rs_rule "no open choice a person would notice, pointing at item 10" \
  'no open choice a person would notice\. the refused phrases, and the rule that a vague count or size needs a number, are item 10 of the list'
rs_rule "a form-made piece is rewritten to this layout" \
  'a piece opened with the github form shows every field as a `###` heading'
rs_rule "and /shape rewrites it" '`/shape` rewrites it to the layout above'
rs_rule "lists are complete" 'lists are complete: a list of examples does not stand in for the whole'
rs_rule "each Done when line is false before and true after" \
  'false on today.s code and true after, through this piece alone'
rs_rule "split, never shrink" 'split, never shrink\. no stub, placeholder or "for now" stands in for a line'
rs_rule "a missed number is a fail" 'a missed number is a fail, stated at the top of the pull request'
rs_rule "a wrong test is reported" 'report a wrong test or an impossible line\. never work round it'
rs_rule "ready needs a Readiness section with no blocking gap" \
  'written by a session that did not shape it, names no blocking gap'
rs_guard "$PIECES" "pieces.md"

rs_require_absent "pieces.md no longer says most pieces leave Decided out" \
  "$PIECES" 'which is most of them'
rs_require_absent "pieces.md no longer carries the one-line Touches" \
  "$PIECES" 'touches: <area>'

# --- the readiness list ----------------------------------------------------

# Founding takes a piece no further than spec, and says so in the readiness
# check, the setup skill and the completion report.
FOUNDING_SPEC='founding takes each piece it shapes no further than `shaping:spec`, because writing the acceptance checks pushes a branch and founding uploads no code'

rs_reset
rs_rule "each item is answered pass, gap or does not apply" \
  'answer each item pass, gap or does not apply \(one line why\)'
rs_rule "only what the change can show" \
  'ask only about states and cases the change.s own screen, route or record can show'
rs_rule "the severity rule" \
  'a gap is blocking when closing it would change what a person sees or does, what is stored, or what leaves the tool\. anything else is a note\. a piece is ready when no blocking gap remains'
rs_rule "nothing outside the list is raised" 'do not raise anything outside this list'
rs_rule "item 1, outcome" '1\. \*\*outcome\.\*\* so that states one outcome for the person'
rs_rule "item 2, Done when works" '2\. \*\*done when, works\.\*\* each line is a rule, not an example'
rs_rule "item 3, coverage" '3\. \*\*coverage\.\*\* done when delivers all of so that'
rs_rule "item 4, not the normal case" '4\. \*\*not the normal case\.\*\* for each case the change can show'
rs_rule "item 4 names every kind of failure" \
  'failure, by kind: service down; answer empty, cut off, malformed or in the wrong language'
rs_rule "item 5, data" '5\. \*\*data\.\*\* for a new kind of stored record: where it lives'
rs_rule "item 6, leaves the tool" '6\. \*\*leaves the tool\.\*\* what goes where'
rs_rule "item 7, must still hold" '7\. \*\*must still hold\.\*\* each rule the change touches'
rs_rule "item 7, a missed number means not done" 'a missed number means not done'
rs_rule "item 8, relies on" '8\. \*\*relies on\.\*\* each existing thing used and not built here, confirmed by reading or trying it'
rs_rule "item 9 reads the Reach fields" '9\. \*\*reach\.\*\* the `## reach` fields\.'
rs_rule "item 9 still names open pieces changing the same thing, and the merge order" \
  'change the same file, schema, prompt or record are named with the merge order'
rs_rule "item 10, no open choice" '10\. \*\*no open choice a person would notice\.\*\*'
rs_rule "item 10 says the lint has refused its fixed phrases" \
  'the ready-gate lint has already refused its fixed phrases'
rs_rule "item 10 keeps the judgement-only words for the checker" \
  'refused here where a person would see the difference: "may", "optional", "some", "most", "short", "fast", an open "x or y", and any other count or size without a number'
rs_rule "item 11, complete and consistent" '11\. \*\*complete and consistent\.\*\* lists are complete'
rs_rule "item 12, size" '12\. \*\*size\.\*\* one sitting'
rs_rule "item 13, a flow the person has not seen" '13\. \*\*a flow the person has not seen\.\*\*'
rs_rule "item 14, screen" '14\. \*\*screen\.\*\* for each new control or message'
rs_rule "item 15, each check tests its criterion" \
  '15\. \*\*each check tests its criterion\.\*\* match each acceptance check to the criterion it claims to test'
rs_rule "item 15, a check that tests something else blocks" \
  'a check that tests something else is a blocking gap'
rs_rule "what the list cannot catch" \
  'what this list cannot catch, so ready never reads as safe: domain and model quality, visual polish, platform quirks, gaps in test tools, a builder missing a correct piece, and gates ignored at merge'
rs_rule "the review and screen-check stay required" \
  'the independent review and screen-check stay required'
rs_rule "a session that did not shape the piece runs it" \
  'a subagent that starts with none of the shaping conversation'
rs_rule "a fork of the shaping session does not count" \
  'a fork or a copy of the shaping session carries its blind spots, so it does not count'
rs_rule "without a subagent, one line and the line to paste" \
  'says in one line that the check needs a new session, and gives the exact line to paste there: `/shape <number> check readiness`'
rs_rule "the check scales with the change" \
  'a colour change answers most items with does not apply and one line why, and runs only the checks its change needs'
rs_rule "the reach check serves Relies on and Reach" \
  'use the reach check in the `section-builder` skill.s `references/reach-check\.md`'
rs_rule "unreadable code behind Relies on is a blocking gap" \
  'a relies on line whose code or data the checker cannot read is a blocking gap, never a pass'
rs_rule "a container passes when its parts are pieces" \
  'a container with parts passes item 12 when every part is its own piece and the container.s own done when is only the joined outcome'
rs_rule "the section carries the date, who checked, the verdict and notes" \
  '## readiness <yyyy-mm-dd>, checked by a session that did not shape it: ready \| not ready - blocking <item>: .* - note <item>:'
rs_rule "the section is the stored result" 'that section is the stored result every later step reads'
rs_rule "a blocking line rules out Ready" 'a piece with a blocking line cannot carry the verdict ready'
rs_rule "notes never hold a piece back" 'notes stay on the piece for the builder, and never hold the piece back'
rs_rule "not ready moves the piece to the sub-state its first gap needs, the gaps on it" \
  'not ready moves it to the sub-state its first blocking line needs, with each blocking gap written on the piece'
rs_rule "a gap a person must settle is clarify" \
  '`shaping:clarify` for a gap a person must settle, including a relies on line whose code does not exist or does not return what the piece needs'
rs_rule "a fact from outside is research" '`shaping:research` for a fact from outside the project'
rs_rule "an unseen flow is prototype" '`shaping:prototype` for a gap on item 13'
rs_rule "a gap the contract can close is spec" '`shaping:spec` for a gap the contract can close with no new answer'
rs_rule "reading code is never a label" 'reading code is never the reason for a label'
rs_rule "founding stops each piece it shapes at spec" \
  "$FOUNDING_SPEC"
rs_rule "and /shape takes each piece on from there" \
  '`/shape` takes each piece on from there'
rs_guard "$READINESS" "readiness-check.md"

# The case that let a ready piece with no Readiness section stay ready is gone,
# and so is founding running the check itself: writing the acceptance checks
# pushes a branch, and founding uploads no code.
rs_require_absent "the skipped-check case is gone" \
  "$READINESS" 'skipped the check\. it stays where it is'
rs_require_absent "founding no longer runs the check" \
  "$READINESS" 'founding runs this check on each piece it shapes'

# The list itself, byte for byte. The rules above hold each item's opening, and
# this holds the bodies, since a softened clause inside an item reads as well
# as the original and would pass every pattern. The sum is of the block from
# "How to run it:" to "stay required.", copied from the slice that wrote it.
LIST_SUM=b062ac77e4745eb17f6a08c02e128d2e1b7eb74eb0815e1ed3345966bd2ed2f6
list_sum() {
  sed -n '/^How to run it:$/,/screen-check stay required\.$/p' "$1" > "$rs_dir/list"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$rs_dir/list" | cut -c1-64
  else
    shasum -a 256 "$rs_dir/list" | cut -c1-64
  fi
}
if [ -z "${RS_LIST:-}" ]; then
  [ "$(list_sum "$READINESS")" = "$LIST_SUM" ] \
    && rs_ok "the readiness list matches its stored copy word for word" \
    || rs_fail "the readiness list no longer matches its stored copy"
  sed 's/One sitting\./Roughly one sitting./' "$READINESS" > "$rs_dir/softened.md"
  [ "$(list_sum "$rs_dir/softened.md")" != "$LIST_SUM" ] \
    && rs_ok "a softened item is caught" \
    || rs_fail "a softened item was not caught"
fi

# --- the test runner table ------------------------------------------------

# A project with no code yet has no test command, so its acceptance checks are
# written for the runner this table names. The lint keeps the same table, so a
# row that went from here would refuse every piece in that language.
rs_reset
rs_rule "the floor has a Test runner table" '## test runner'
rs_rule "Python's runner is pytest" '\| `pytest` \| python \|'
rs_rule "TypeScript's runner is Vitest" '\| `vitest` \| typescript \|'
rs_rule "JavaScript's runner is Vitest" '\| `vitest` \| javascript \|'
rs_rule "Go's runner is go test" '\| `go test` \| go \|'
rs_rule "Rust's runner is cargo test" '\| `cargo test` \| rust \|'
rs_rule "any other language has none, so no Test runner line" \
  'any other language has none\. spec then writes no `test runner:` line'
rs_rule "Test runner names a runner from this table for the stack's language" \
  '`test runner:` names a runner from this table for the language of agents\.md.s stack section'
rs_rule "the lint keeps the same table" 'the ready-gate lint keeps the same table'
rs_guard "$FLOOR" "check-floor.md"

# --- /shape runs the check and moves by its result ------------------------

rs_reset
rs_rule "a session that did not shape the piece checks it before ready" \
  'before a piece moves to `state:ready`, a session that did not shape it checks it against the fixed list in the `shape` skill.s `references/readiness-check\.md`'
rs_rule "it starts a subagent carrying none of the conversation" \
  'start a subagent that carries none of this conversation, where the coding agent has one'
rs_rule "a fork does not count" 'a fork of this session does not count'
rs_rule "without a subagent, one line saying a new session is needed" \
  'where the coding agent cannot start a subagent, say in one line that the check needs a new session, and give the exact line to paste there'
rs_rule "the exact line to paste" 'paste: /shape <number> check readiness'
rs_rule "a session typed that way runs the check itself" \
  'typed that way, in a session that did not shape the piece, run the check yourself'
rs_rule "the section is read back and decides the move" \
  'read that section back and let it decide the move'
rs_rule "no blocking gap moves the piece to ready through the gate" 'with no blocking gap, move the piece to `state:ready` through the gate'
rs_rule "a blocking gap sends the piece back, written on it" \
  'a blocking gap sends it back through the gate to the sub-state its first blocking line needs, with the gap written on it'
rs_rule "every field is considered when shaping" \
  'consider every field, and where one does not apply, say why in one line'
rs_rule "every noticeable choice is decided" \
  'every choice a person would notice by trying the tool is decided in `## decided`'
rs_rule "shaping scales with the change" 'a colour change answers most fields in one line'
rs_rule "the pasted line is routed, never triaged" \
  'typed as `/shape <number> check readiness`, this is not a request\. skip change-triage'
rs_rule "given a number with check readiness, only the check runs" \
  'given it as `/shape <number> check readiness`, run the readiness check on that piece and nothing else'
rs_rule "typed alone picks up a piece waiting for its check" \
  'a piece in `shaping:check` is waiting for its readiness check: its shaping finished and the check never ran'
rs_rule "Done when of /shape names the check" \
  'moved to `state:ready` only after a session that did not shape it wrote a `## readiness` section naming no blocking gap'
rs_guard "$SHAPE" "the /shape skill"

rs_require_absent "the old bar is gone from /shape" "$SHAPE" 'meets the bar'

# --- change-triage and founding go through the check too -----------------

rs_require_load_bearing "change-triage makes a clear piece ready only after the check" \
  "$TRIAGE" 'becomes a ready piece once the readiness check finds no blocking gap'
rs_require_load_bearing "change-triage moves an answered question to ready only after the check" \
  "$TRIAGE" 'question is answered and the readiness check finds no blocking gap'
rs_require_load_bearing "change-triage says what a piece in check is" \
  "$TRIAGE" 'a piece in `shaping:check` is waiting for its readiness check'
rs_require_load_bearing "founding stops each piece it shapes at spec" "$SETUP" "$FOUNDING_SPEC"
rs_require_absent "founding no longer runs the readiness check itself" \
  "$SETUP" 'founding runs the readiness check in the'
rs_require_load_bearing "the completion report says founding stops at spec" "$REPORT" "$FOUNDING_SPEC"
rs_require_load_bearing "the compatibility page gives the route without a subagent" \
  "$COMPAT" '/shape <number> check readiness'

# --- clarify asks only what the piece touches ------------------------------

rs_reset
rs_rule "three subjects come up only when the piece touches them" \
  'three subjects come up only when the piece touches them'
rs_rule "the cases that are not the normal one" \
  'where the change can show a case that is not the normal one'
rs_rule "the data questions" \
  'where it stores or changes a record, ask who else writes it, what happens at its limit, and what delete and undo mean'
rs_rule "what leaves the tool" \
  'where anything leaves the tool, ask what goes, to whom, and whether the recipient is new'
rs_rule "a subject the piece does not touch is skipped" 'skip each subject the piece does not touch'
rs_guard "$CLARIFY" "the clarify skill"

# --- told in the other places ---------------------------------------------

rs_require_load_bearing "WORKFLOW.md says a session that did not shape the piece checks it" \
  "$WORKFLOW" 'a session that did not shape it checks it against a fixed list'
rs_require_load_bearing "WORKFLOW.md says a blocking gap keeps the piece in shaping" \
  "$WORKFLOW" 'keeps the piece in shaping, with the gap written on it'
rs_require_load_bearing "WORKFLOW.md says what happens without a second session" \
  "$WORKFLOW" 'gives you one line to paste into a new one'
rs_require_load_bearing "WORKFLOW.md says the agent layer is complete" \
  "$WORKFLOW" 'below it sits the agent layer, which is complete'
rs_require_load_bearing "WORKFLOW.md's two-layer paragraph names the loop module and the bar" \
  "$WORKFLOW" 'the loop module, and the bar that module needs'
rs_require_load_bearing "WORKFLOW.md gives the reach line the person reads" \
  "$WORKFLOW" '"this changes sign-in\. it also reaches billing, which 14 checks guard\. if it breaks, people cannot sign in, and a rollback undoes it\."'
rs_require_load_bearing "WORKFLOW.md says the lint checks the rest" \
  "$WORKFLOW" 'the ready-gate lint checks the rest'
rs_require_load_bearing "WORKFLOW.md says founding stops each piece at spec" \
  "$WORKFLOW" 'each piece it shapes stops in spec'
rs_require_load_bearing "PHILOSOPHY's example keeps the header short" \
  "$PHILOSOPHY" 'the person sees a short header in plain words'
rs_require_load_bearing "PHILOSOPHY's example makes the agent layer complete" \
  "$PHILOSOPHY" 'below it the agent layer is complete'

# The list lives in the shape skill. The founded AGENTS.md sits at its line
# ceiling, and a copy there would drift from the one the check reads.
rs_require_absent "the readiness list stays out of the founded AGENTS.md" \
  "$FOUNDED" 'does not apply \(one line why\)'

# --- the replay case -------------------------------------------------------

rs_require "a scenario shapes a small piece that stores a record" \
  "$SCENARIOS" '## 56\. a small piece that stores a record is checked before it turns ready'
rs_require "its evidence asks for a Data section and a Readiness section" \
  "$SCENARIOS" 'carrying a `## data` section .* and a `## readiness` section'
rs_require "the case starts with /shape and a request" "$CASE" '^# setup: fixture .*/shape '
rs_require "the baseline lists its run as owed" "$BASELINE" 'scenario 56 .*owed'

rs_done
