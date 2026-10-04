# Slice 4: A person shapes every piece, a bug included, through one route that ends at the ready gate

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint.

## So that
A person who has an idea, a wish or a bug types `/shape`, answers only the questions that are theirs to answer, and ends with a piece that carries its bar, its acceptance checks and its loop module and can be built with nobody there.

## Done when

Four parts, each its own pull request in order: a (raw triage and the bug fast path), b (the decision sub-states), c (spec, check and kickback intake), d (removing /fix).

### Part a: triage in raw, capture, and the bug fast path

#### Works
- Capture: change-triage files a note through `gate.py capture`, so a captured piece is `state:shaping` with `shaping:raw` and carries the person's words and nothing settled. `/shape later` and `/shape idea` keep working. Check: `.agents/tests/shape-later.sh` and `.agents/tests/state-moves.sh`, their `idea` rules rewritten to `shaping:raw` and the gate call.
- Triage in raw: `/shape` on a raw piece runs change-triage, which writes on the piece a `type:` label (feature, bug or chore), a first guess at the loop module with one line why, any duplicate or overlap with an open piece or a closed piece (completed or not planned), and the first open question in `## Open question`, then moves it with `gate.py` to the sub-state of that question, or to `shaping:spec` when there is none. Check: new `.agents/tests/shaping-sub-states.sh` (rule-shape) holds each output in `change-triage/SKILL.md` and `shape/SKILL.md`, each proved load-bearing; `gate-script.sh` already refuses a raw piece leaving without a `type:` label.
- The report check that `/fix` step 0 did today, telling a repair of promised behaviour from a wish the masterplan never made, moves into change-triage's raw triage: a wish becomes `type:feature`, a repair `type:bug`. Check: `shaping-sub-states.sh`, a rule on the masterplan comparison in change-triage.
- Bug fast path: a `type:bug` with a reproduction a person can follow (steps, expected result, actual result) goes from `shaping:raw` straight to `shaping:spec`, takes `loop:fix`, and `/shape` offers `/implement <number>` as soon as it is ready. A bug with no clear reproduction goes to `shaping:clarify` with the missing step as its question. Check: `shaping-sub-states.sh`, both routes, proved load-bearing.
- `/shape` typed alone takes pieces in this order: a kicked-back piece first, then a piece waiting in `shaping:check`, then `shaping:research` (which needs nobody), then `shaping:clarify` and `shaping:prototype` when the person is there, then `shaping:spec`, then the oldest `shaping:raw`. Check: `shaping-sub-states.sh`, the order read as one rule; `.agents/tests/who-can-settle.sh`, its "takes the pieces the agent can settle alone" rule moved to `shaping:research`.
#### When it is not the normal case
- The note matches an open or closed piece: the words go on that piece as a comment and the person is told which, as capture does today. Check: `shape-later.sh`.
- GitHub cannot be reached: nothing is filed and `/shape` says so in one line; the person's words are repeated back so nothing is lost. Check: `shaping-sub-states.sh`, a rule in `shape/SKILL.md`.
- A request that would change what kind of project this is: triage stops and reruns the fit check before any sub-state, as today. Check: `.agents/tests/acceptance-is-earned.sh` passes unchanged on this rule.

### Part b: research, clarify and prototype

#### Works
- `shaping:research` answers what is true and never decides: it runs the source check (`change-triage/references/source-check.md`) or the existing-work search (`change-triage/references/existing-work.md`), and on a project with code the reach check (`section-builder/references/reach-check.md`) on `origin/main` plus one query of saved history for files that change together, mapping each hit to a named area. It writes `## Research` with a source for each claim and a recommendation. A finding that needs a choice moves the piece to `shaping:clarify` with the choice as its question. Check: `shaping-sub-states.sh`, each rule load-bearing; `.agents/tests/shape-research.sh`, its `needs-research` rules moved to the sub-state; `.agents/tests/reach-check.sh`, a new rule that shaping's research calls the reach check.
- The history query is one shipped script, `section-builder/scripts/co-change.sh <path>...`, printing the files that changed in the same commits as the given ones over the last 200 commits, most often first, and nothing when there is no history. Check: new `.agents/tests/co-change-rehearsal.sh`, a throwaway repository whose history pairs two files, read back in order; an empty history prints nothing and exits 0.
- `shaping:clarify` answers what the person wants, through the clarify skill, one question at a time, with the question box from the overnight batch: one short sentence, a labelled guess, choices only when the real answers form a short complete list, the guess first, and free text kept. The answer is written into `## Decided` before `gate.py` moves the piece. Check: `.agents/tests/question-box.sh`, brought over from the overnight batch with its parking rule replaced by the one below; `.agents/tests/settled-is-recorded.sh`, its read-back rule pointed at the gate's answer marker.
- The pre-mortem: when the reach touches a sensitive area, stored data or anything that leaves the tool, clarify asks once, "Say this went live and went wrong. Who noticed, and what did they see?", and the answer becomes the piece's `If it breaks:` line. A data change that cannot be undone is marked there as not reversible. Check: `shaping-sub-states.sh`, the question word for word and its trigger, each load-bearing.
- The risk notice and its acceptance happen in `shaping:clarify`: where the boundary or the reach touches a sensitive area with no recorded acceptance, the notice is given once, in full, and the person carrying on is recorded as an `Accepted:` line with their words and the date before the piece leaves clarify. Check: `acceptance-is-earned.sh`, its rules moved from build time to clarify, with the existing rules about silence, form answers and quoting kept.
- A gauntlet piece's reference is approved in `shaping:clarify`: the person names or approves a reference that can be fetched, and a budget; both go into `## Loop` with the date. Check: `shaping-sub-states.sh`, a rule on the reference and budget, load-bearing.
- `shaping:prototype` runs the decision prototype (`clarify/references/decision-prototype.md`), or builds toward a mock the person already has (`clarify/references/existing-artifact.md`), and writes the decision into `## Decided`; the prototype is deleted or kept apart, never merged. Check: `.agents/tests/prototype-recipes.sh` and `.agents/tests/existing-artifact.sh`, their `needs-prototype` rules moved to the sub-state.
#### When it is not the normal case
- The person is not there for a clarify or prototype question: the piece stays in its sub-state with the question and the labelled guess written on it, and `/shape` names it as waiting for them; no guess is ever written as an answer. Check: `question-box.sh` (the rule that replaces parking) and `who-can-settle.sh`.
- A form or menu answer with nothing selected, or silence: no answer and no acceptance. Check: `question-box.sh` and `acceptance-is-earned.sh`.
- The person says "later": the piece stays in its sub-state with what was agreed so far written on it, and nothing more is asked in that session. Check: `shape-later.sh`.
- The reach check finds no engine and the project is new: the fallback reads imports and callers directly, as `reach-check.md` says, and research says which engine it used. Check: `reach-check.sh` passes unchanged.

### Part c: spec, check and kickback intake

#### Works
- `shaping:spec` has no open question, so the system writes the whole contract v2 alone: the loop module and its bar, the reach fields, `## Not in this piece`, and for a build or fix piece the acceptance checks as real tests, committed on a branch named `spec/<number>-<short name>` cut from `origin/main`, holding test files only, and pushed. `Acceptance branch:` names it. A question found while writing sends the piece back to the sub-state it needs. Check: `shaping-sub-states.sh`, each rule load-bearing; `.agents/tests/first-upload-asks.sh`, a rule that the first push of a spec branch on a project whose code is not online asks first, as a piece's first push does.
- `shaping:check` runs `ready-lint.py`, then the fresh checker in a session that did not shape the piece, then `gate.py move <n> state:ready`, and reports the result in one line. Check: `.agents/tests/piece-contract.sh`, its `/shape` readiness rules pointed at the sub-state and the lint.
- Section-builder builds a piece that names an `Acceptance branch:` on that branch itself, so the build's pull request comes from it, and its step 4 confirms the committed checks still fail rather than writing them again; a piece with no acceptance branch keeps today's step 4. Check: `.agents/tests/checks-first.sh`, a rule for each route, proved load-bearing.
- Kickback intake: a piece arriving in shaping with a `## Kickback` section is read first: what happened, what was tried, what decision is needed. `/shape` keeps its branch, settles the question in the sub-state the kickback named, rewrites the contract in `shaping:spec`, removes the old `## Readiness` result, and runs the check again. Answers the person already left on the piece as comments are read before any question is asked again, following the overnight batch's "Answers already on the piece" route. Check: `shaping-sub-states.sh`, each rule load-bearing.
- WORKFLOW.md section 2 and section 5 describe the shaping sub-states, the pre-mortem question, the bug fast path and what a kicked-back piece looks like. Check: `shaping-sub-states.sh`, a rule for each on WORKFLOW.md.
- The shape skill's description names the sub-states and the bug route, and the adapters are rebuilt. Check: `.agents/tools/validate-kit.sh` (adapter drift).
- Root AGENTS.md's maintainer checks describe `shaping-sub-states.sh`, `co-change-rehearsal.sh` and `question-box.sh`, and the changed entries for the rehearsals listed under Under the hood. Check: guided check: the maintainer reads each entry beside the rehearsal's rule list; `validate-kit.sh` passes.
#### When it is not the normal case
- The spec branch cannot be pushed because the first upload has not been agreed: the piece stays in `shaping:spec` with the reason written on it, and `/shape` asks the first-upload question. Check: `first-upload-asks.sh`.
- An acceptance check passes on `origin/main` when written: the line it guards is already true, so the piece goes back to `shaping:clarify` with that finding. Check: `shaping-sub-states.sh`; the lint refuses the same piece (`ready-lint-rehearsal.sh`).
- The fresh checker cannot be started: `/shape` gives the line to paste in a new session, `/shape <number> check readiness`, and the piece stays in `shaping:check`. Check: `piece-contract.sh` passes on that rule.
- A kicked-back piece's branch has commits the person wants kept: the branch is never deleted, and the rewritten spec names it. Check: `shaping-sub-states.sh`.

### Part d: removing /fix

#### Works
- The `fix` skill folder is gone and the kit has eight commands and five background skills. `.agents/tools/validate-kit.sh`'s `expected_commands`, `.agents/tools/build-adapters.sh`'s count, `release-manifest.txt`, `.claude-plugin/plugin.json` and the generated adapters under `.claude/`, `.cursor/` and `.gemini/` all say so. Check: `validate-kit.sh`, `.agents/tests/release-builder.sh`, `.agents/tests/claude-plugin.sh` and `.agents/tests/agent-plugin.sh`.
- The repair discipline from `fix/SKILL.md` steps 1 to 7 and its escalation move unchanged in substance to `section-builder/references/fix-loop.md`, which section-builder loads for a `loop:fix` piece. Check: `.agents/tests/fix-history-first.sh`, `.agents/tests/notice-is-owed-by-the-refusal.sh`, `.agents/tests/test-strength.sh`, `.agents/tests/trim.sh`, `.agents/tests/reach-check.sh`, `.agents/tests/checks-first.sh`, `.agents/tests/changelog-files.sh`, `.agents/tests/one-merge-step.sh`, `.agents/tests/request-record.sh`, `.agents/tests/secret-location.sh`, `.agents/tests/acceptance-is-earned.sh` and `.agents/tests/state-moves.sh` read the new file in place of `fix/SKILL.md` and pass.
- Every skill, reference and template that told the person to type `/fix` says `/shape` with what broke: `what-now`, `sync`, `section-builder/references/merge.md`, `setup-ai-build-kit/references/project-check.md`, `check-floor.md`, `boundary-rules.md`, `adopting.md`, `pieces.md`, `blocked-commands.md`, the foundation `AGENTS.md` command line and `plan-refresh.sh`. Check: `shaping-sub-states.sh` fails on any `/fix` left under `.agents/skills/`.
- README.md: the command table's "It's broken" row points at `/shape`, the count reads eight, and the flow diagram and the FAQ drop `/fix`. Check: `validate-kit.sh`'s command-count claims; `shaping-sub-states.sh`, a rule on the README row.
- WORKFLOW.md: the command table and section 1's "Two of them change the tool" paragraph drop `/fix`, and section 6's repair paragraphs say a bug is shaped like any other piece and built by the fix loop. Check: `shaping-sub-states.sh`, rules on WORKFLOW.md; `validate-kit.sh`'s stale-claims check.
- docs/PHILOSOPHY.md: the paragraph on how the count moved says eight became the count when `/fix` was found to be a shaping route plus a loop module; the worked examples that answered "type /fix" answer `/shape`, and "Tight bug reproduction before a fix, added" fits under `/shape` and the fix loop. Check: `.agents/tests/loop-first-ground.sh`, rules on the count paragraph; the `check_five` calls still pass.
- docs/COMPATIBILITY.md's command list and per-route table drop `fix`. Check: `.agents/tests/compatibility-grades.sh` and `validate-kit.sh`.
- Root AGENTS.md says eight commands and thirteen canonical skills wherever it counted nine and fourteen, and its maintainer-checks entries name `fix-loop.md` where they named the fix skill. Check: `validate-kit.sh` (inventory and adapter counts); guided check: the maintainer searches AGENTS.md for "fourteen", "nine commands" and "/fix" and finds none.
- The skill lists `/maintain`'s existing steps read (the shared route's lockfile count and `scripts/old-skill-pointers.py`) say thirteen skills, so their rehearsals keep passing. No step is added for a project that still holds `fix`, because AI Loop Kit has no project founded before `/fix` went (decision 63), and slice 17: /maintain absorbs /sync removes those old-project steps. Check: `.agents/tests/shared-route-adds.sh` and `.agents/tests/older-project-upkeep.sh` pass with the count of thirteen.
- The scenarios that typed `/fix` in `.agents/tests/scenarios.md` and the replay case that types it say `/shape` with the same report. Check: `.agents/tests/replay/check-parser.sh` parses them; grading them again belongs to slice 20.
#### When it is not the normal case
- A person types `/fix` from habit: there is no such command; the agent treats the words that follow as a request, says that `/shape` takes it, and runs `/shape`, since the kit starts a command when the person asks for its job in plain words. Check: `shaping-sub-states.sh`, a rule in change-triage that a request naming `/fix` is a repair report.
- A project founded with AI Build Kit, which still holds `fix`: does not arise, because AI Loop Kit does not move such a project (decision 63); it stays on AI Build Kit.

## Masterplan change
Design note: realises "Shaping" (the sub-states, who does each, skipping a sub-state, the bug short route, sensitive areas settled in shaping), the shaping half of "Reach and risk" (research's reach and history query, clarify's one question), "Kickback" (intake), and the `/fix` line of "Commands" in `docs/design/agentic-loop.md`. The note needs one clarification: shaping reads the lessons earlier runs recorded before it researches, and that reading starts with slice 17: /maintain absorbs /sync, which first records lessons.

## Not in this piece
- Checking `Boundary:` areas against a whole-project map: slice 5: area map for the whole project. Until then research names areas from the masterplan and the sensitive-area map where one exists.
- The fix loop's v1 discipline (three failed fixes kick back to `shaping:research`, an unreproducible bug to `shaping:clarify`, a check added for each fault): slice 7: build and fix loop modules. This slice moves today's discipline across unchanged.
- Several research readers in parallel and several prototype variants: slice 10: crews and computer resources.
- Filing a bug piece when `main` is red, and running a bug at once as a run of one: slice 9: run controller.
- Reading the lessons file before research: slice 17: /maintain absorbs /sync.
- The final pass that makes every document tell the same story: slice 21: documentation sweep.

## Decided
- There is no fixed order between research, clarify and prototype; a piece sits in the sub-state of its next open question, and a sub-state with nothing to do is skipped (design note, "Shaping"; decision 33).
- Research never decides: a finding that needs a choice moves the piece to clarify (decision 5).
- The pre-mortem is asked once, in the design note's words, and only when the reach touches a sensitive area, stored data or something leaving the tool (decision 39).
- The risk notice and acceptance move into clarify, so a run never meets an unaccepted sensitive area (decision 8 and the points resolved with the decision record).
- A gauntlet reference and its budget are approved in clarify (the points resolved with the decision record).
- Acceptance checks are written in spec and committed on a `spec/<number>-<short name>` branch holding tests only, so the bar exists before the build; the build continues on that branch, so one branch carries the piece from bar to pull request (decision 28).
- A bug with a reproduction a person can follow skips to spec; one without goes to clarify (decision 38 and the design note's short route).
- `/fix` is removed in this slice, with its discipline moved to `section-builder/references/fix-loop.md` rather than deleted, so no repair loses its rules between this slice and slice 7 (decision 21).
- The question box's rule for a worker with no way to reach the person keeps the piece in `shaping:clarify` with the question on it, because v1 has no parked state.
- The history query looks back 200 commits, enough to cover months of a small project's work while staying fast on a large one; slice 20's real runs measure it.

## Data
- Issue bodies gain `## Open question`, `## Research`, the pre-mortem's `If it breaks:` line, `Accepted:` lines in the masterplan, and the contract v2 fields; `/shape` and the person write them, the gate and the lint read them.
- A `spec/<number>-<short name>` branch per build or fix piece, pushed to the project's repository. The build continues on it, so it is deleted automatically when the build's pull request merges, by the repository setting founding already turns on, and a kicked-back piece keeps it.
- No move for projects founded with AI Build Kit: no `fix` folder is tidied and no `broken` label is read as `type:bug` (decision 63).

## Leaves the tool
- A spec branch is pushed to the person's own repository; on a project whose code is not yet online, the first push asks first, as a piece's does today.
- Research's source check reads public pages; nothing about the project is sent, as today.
- Comments and body edits go to the project's issues through the GitHub command-line tool, as bookkeeping; anything addressed to a colleague still waits for a yes.

## Must still hold
- The fixed readiness list, run by a session that did not shape the piece (`piece-contract.sh`).
- Acceptance is earned: notice first, the person's own words, read back before work (`acceptance-is-earned.sh`).
- A person-present question is never answered by the agent (`who-can-settle.sh`).
- The first upload asks (`first-upload-asks.sh`).
- Speaking for the person waits for a yes (`speaks-for-the-person.sh`).
- A refused command is never reached another way (`refused-commands.sh`).
- The founded AGENTS.md ceiling (`standing-instructions.sh`).
- No issue numbers in tracked files; no attribution lines (`validate-kit.sh`).

## Relies on
- `gate.py` with its sub-state conditions and answer marker, from slice 2: label model and gate script.
- Contract v2, `ready-lint.py` and the gate's ready condition, from slice 3: contract v2 and the ready-gate lint.
- `change-triage`, `clarify` (with `decision-prototype.md`, `existing-artifact.md`), `shape` (with `readiness-check.md`), `section-builder/references/reach-check.md`, `fix/SKILL.md`, `maintain/scripts/old-skill-pointers.py`, on main today.
- `clarify/SKILL.md`'s question box and `.agents/tests/question-box.sh`, and `shape/SKILL.md`'s "Answers already on the piece", on the overnight batch branch `gwpicard/v1-overnight-integration-20261001` of the old repository, gwpicard/ai-build-kit, which stays; read with `git show` from the old repository added as a second remote, as the epic describes.

## Reach and risk
Boundary: shape, change-triage, clarify, section-builder (fix-loop.md, co-change.sh, step 4 start), fix (removed), what-now, sync, maintain (its skill counts only), setup-ai-build-kit references and foundation templates that name `/fix`, README.md, WORKFLOW.md, PHILOSOPHY.md, COMPATIBILITY.md, root AGENTS.md, the validator, the adapter builder, the release allowlist and the plugin metadata.
Reaches: the installation routes and their counts (`claude-plugin.sh`, `agent-plugin.sh`, `release-builder.sh`, `plan-helper-routes.sh`); the readiness check (`piece-contract.sh`); acceptance (`acceptance-is-earned.sh`, `named-reviewer-is-a-person.sh`); the run's claim and the merge step (`the-runner.sh`, `one-merge-step.sh`); the replay harness's parser (`check-parser.sh`).
If it breaks: a person cannot shape a piece to ready, or a bug has no route; they see `/shape` stop with the gate's or the lint's message. Each part is reverted on its own, part d first, which brings `/fix` back.
Depends on: 2, 3.
Loop module: build, because every rule is a written rule or a script behaviour a rehearsal can pass or fail.
Crew: default for the module.

## Under the hood
Write `shaping-sub-states.sh` first with every rule above and see it fail. Part a reshapes change-triage's capture and Step 4 routes into sub-states and moves `/fix` step 0's report check into Step 1. Part b changes `shape/SKILL.md`'s "When a piece is waiting on a question" into one section per sub-state, adds the pre-mortem and the gauntlet reference to `clarify/SKILL.md`'s "When a piece touches states, data or the outside", and ports the question box from the overnight batch with its parking rule replaced. It adds `co-change.sh` beside `reach-check.md`. Part c adds the spec and check sections to `shape/SKILL.md`, kickback intake adapted from the overnight batch's "Answers already on the piece", and section-builder's start from an acceptance branch. Part d moves `fix/SKILL.md` to `section-builder/references/fix-loop.md`, deletes the folder with `git rm -r`, and updates every count and pointer.

Reused from the overnight batch branch: the clarify question box and `question-box.sh`; the "Answers already on the piece" reading for kickback intake. Not reused: the overnight shaping recovery for work started too soon, because the gate now refuses a build of an unready piece.

Existing rehearsals expected to change: `shape-later.sh`, `state-moves.sh`, `who-can-settle.sh`, `shape-research.sh`, `reach-check.sh`, `settled-is-recorded.sh`, `acceptance-is-earned.sh`, `prototype-recipes.sh`, `existing-artifact.sh`, `piece-contract.sh`, `checks-first.sh`, `first-upload-asks.sh`, and in part d every rehearsal that read `fix/SKILL.md` (listed above), `loop-first-ground.sh`, `compatibility-grades.sh`, `shared-route-adds.sh` and `older-project-upkeep.sh` (the count of thirteen only), `claude-plugin.sh`, `agent-plugin.sh`, `release-builder.sh` and `validate-kit.sh`. New: `shaping-sub-states.sh`, `co-change-rehearsal.sh`, `question-box.sh`.

The kit's own rules: answer the five questions in PHILOSOPHY.md in each pull request (fits under /shape; the person sees the sub-state their piece is in and only their own questions; "you shape it until a machine and a fresh session say it can be built alone"; when it goes wrong they type /shape with the piece's number; they never need to learn the sub-state order); credit the pre-mortem and the decision and fact split in `docs/SOURCES.md`; rebuild adapters with `.agents/tools/build-adapters.sh`; run `validate-kit.sh`; humanizer on all prose; no issue numbers.

## Evidence
Rule-shape rehearsals with load-bearing checks for each sub-state's rules (`shaping-sub-states.sh`, `question-box.sh` and the changed rehearsals); a script run in a throwaway repository for the history query (`co-change-rehearsal.sh`); the gate's sub-state rows (`gate-script.sh`); the installation and count rehearsals for the removal (`claude-plugin.sh`, `agent-plugin.sh`, `release-builder.sh`, `validate-kit.sh`). One replay scenario per sub-state is owed to slice 20: replay harness rewrite and real runs.

## Size
Four sittings, one per part: a (raw triage and the bug fast path), b (research, clarify and prototype), c (spec, check and kickback intake), d (removing /fix).

## Consistency notes
- This slice removes `/fix` and moves its repair discipline unchanged into `section-builder/references/fix-loop.md`. Slice 7: Build and fix loop modules builds the v1 fix loop on that file (three failed fixes kick back to `shaping:research`, no reproduction kicks back to `clarify`) rather than writing it again, so no repair loses its rules between the two slices.
- Approving a gauntlet's reference and its budget in `shaping:clarify` is this slice's. Saving the approved reference as a fixed copy with its hash is slice 12: Gauntlet loop module's.
- No step is added to `/maintain` for a project that still holds `fix` or carries `broken` (decision 63). The count edits to `/maintain`'s existing steps keep their rehearsals green until slice 17 removes those steps.
- Mechanisms from the overnight batch are read from the old repository's branch, `gwpicard/v1-overnight-integration-20261001` in gwpicard/ai-build-kit, which stays.
