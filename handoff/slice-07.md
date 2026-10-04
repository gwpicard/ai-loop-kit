# Slice 7: A shaped piece is built or fixed in a loop that stops on its own, and says plainly why it stopped

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 4: Shaping sub-states in /shape; slice 6: Frozen-bar enforcement.

## So that
A piece marked `loop:build` or `loop:fix` is built with nobody there, each try starts fresh from what the last one proved, and every ending is one of five statuses with one route, so a gap goes back to shaping rather than being finished by hand.

## Done when

### Part a: the build loop, statuses and attempts

#### Works
- section-builder gains `references/build-loop.md`, and its SKILL.md steps 4 and 5 point to it for `loop:build`: show the acceptance checks failing (through the gate's `before` evidence from slice 6), build until they pass, and end each attempt with exactly one status. Check: new `.agents/tests/loop-modules.sh` (rule-shape) reads `build-loop.md` and section-builder's SKILL.md.
- The builder's result file (the task handoff's `result` from the overnight batch branch's `references/task-handoff.md`, brought onto main in this slice) carries `status`, one of `done`, `done_with_concerns`, `needs_context`, `blocked`, `environment_failed`, with `concerns`, `needs` and `could_not_check` lists. `gate.py result <number> <result-file>` reads it and refuses a result with no status or an unknown one. Check: new `.agents/tests/builder-status-rehearsal.sh` feeds the gate each status and a malformed one.
- Each status has one route, taken by the gate script: `done` goes to checking (slice 6's evidence run, then review); `done_with_concerns` goes to checking and records a reason that forces `review:person`; `needs_context` and `blocked` are a kickback to the sub-state the builder names (`clarify` for a decision, `research` for a fact, `spec` for a contract that needs rewriting), with a `## Kickback` section saying what happened, what was tried and what is needed, and the branch kept; `environment_failed` is retried once as a fresh attempt that does not count, then the piece stops with the run paused and the person told, and is never a kickback. Check: `builder-status-rehearsal.sh` against the stand-in GitHub (`replay/fake-github`) reads labels, the Kickback section and the pushed branch for each.
- Every attempt is a fresh builder started with the bounded brief from `references/task-handoff.md` and the route from `references/task-context-capabilities.md` (both from the overnight batch branch), carrying the previous attempt's note and nothing of its conversation. Check: `task-handoff.sh` from the overnight batch branch, brought onto main, plus a rule in `loop-modules.sh`.
- A new implement script, `scripts/attempt-note.py <number> <worktree>`, writes `.agents/pieces/<number>/attempt-<n>.md` from the evidence record and Git alone: each failing check with its exit code and its last 40 lines of output, the files the attempt touched, the commit it ended on, and its status. No model writes or summarises it. Check: new `.agents/tests/attempt-note-rehearsal.sh` runs it on a throwaway attempt and compares with a stored expected note.
- A failed attempt's work is kept before the next starts, with `recovery.py preserve` from the overnight batch branch's `implement/scripts/recovery.py`, and the next attempt starts from the piece's start commit. Check: `failure-recovery.sh` from the overnight batch branch, brought onto main.
- The loop stops at whichever comes first of the attempt limit and the piece's time budget, read from a new tracked project settings file `.agents/loop-settings.json` (`"attempts": 3`, `"piece_budget_minutes": 120`), which founding writes from `templates/loop-settings.json`. Tokens count toward the budget where the coding agent's session record carries usage; where it does not, the brief says the budget is time alone. Check: `builder-status-rehearsal.sh` runs the loop driver, `implement/scripts/run.py`, with a stub builder that always fails and reads three attempts, then the stop.
- At the limit, a `loop:build` piece is kicked back to `research` with every attempt note linked in its Kickback section, or to `spec` where a note shows an acceptance check that cannot be met as written. Check: `builder-status-rehearsal.sh`.
- Within the limits the builder researches and repairs by itself, and a finding that would change a `Done when` line, a `Decided` line or the boundary ends the attempt as `needs_context` rather than being acted on. Check: rule in `loop-modules.sh` against `build-loop.md`.
- The builder switches loop module only through `gate.py switch-module <number> <module>`, which the gate allows only when the contract already holds the new module's bar (a reproduction for `fix`, acceptance checks for `build`) and which logs the switch in the evidence record; anything else is refused and the builder ends with `needs_context`. Check: `builder-status-rehearsal.sh`.

#### When it is not the normal case
- The coding agent cannot start a fresh builder: the run pauses at a resumable point and says to open a new session and type `/implement`, as `task-handoff.md` says. Check: `task-handoff.sh`.
- The builder ends with no result file (the session died): counted as a failed attempt only once the builder is known to have ended, its work kept. Check: `failure-recovery.sh`.
- `environment_failed` twice in a row on different pieces: the run pauses at once rather than trying a third. Check: `builder-status-rehearsal.sh`.
- No `.agents/loop-settings.json` (the person deleted it): the defaults above apply, said once. Check: `builder-status-rehearsal.sh`.

### Part b: the fix loop

#### Works
- `section-builder/references/fix-loop.md`, which slice 4 moved across unchanged from the fix skill, becomes the fix loop for a `loop:fix` piece. It keeps the order of steps 1 to 7: define the symptom, the tightest feedback loop, reproduce and minimise, read earlier repairs in the changelog and `changes/`, rank two to five causes each with a prediction, test one at a time, fix and lock it down, clean up. Check: `fix-history-first.sh` and `notice-is-owed-by-the-refusal.sh`, already pointed at `fix-loop.md` by slice 4, and `loop-modules.sh`.
- No cause is tested before a reproduction exists: the gate refuses a code commit on a `loop:fix` piece until its evidence record holds the reproduction failing on the start commit. Check: `builder-status-rehearsal.sh`.
- Three failed fixes kick the piece back to `research` with the ranked causes and their outcomes, because the architecture is in question; a reproduction that cannot be built kicks it back to `clarify`. Check: `builder-status-rehearsal.sh`.
- Each fix adds the cheapest check that would have caught the fault, and the contract's "must not change" line becomes a guard check the gate runs with the others. Check: rules in `loop-modules.sh`; `builder-status-rehearsal.sh` reads the guard check in the gate's run.

#### When it is not the normal case
- A reproduction that passes only sometimes: recorded as unreliable, ranked as a cause of its own, never counted as fixed on a retry. Check: `fix-history-first.sh`.
- The fault survives three attempts and the person had carried on after a notice: the record of the acceptance stands and the kickback still happens, since nobody is present in the loop. Check: `notice-is-owed-by-the-refusal.sh`, updated.

### Documents, both parts
- section-builder's SKILL.md: steps 4, 5 and 8 point to the loop references, and the "three attempts then parked" paragraph is replaced by the routes above. Check: `loop-modules.sh`.
- The implement skill's `references/running-longer.md`: "When a piece fails" names the statuses and kickback instead of `parked`. Check: `the-runner.sh`, updated.
- WORKFLOW.md section 5, "Day to day": what a build does without you, the five endings and where each goes; the paragraph on three failed rounds now says kickback. Check: `loop-modules.sh`.
- `docs/COMPATIBILITY.md`, "Harness map": which coding agents can start a fresh builder, from `task-context-capabilities.md`. Check: `compatibility-grades.sh` rule.
- Root `AGENTS.md` names each new or brought-over rehearsal. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Loop modules" (the fix and build rows, limits, self-repair, switching), "Review" (the builder status table), and "Projects founded with AI Build Kit" (the recovery helper and fresh builder contexts reused from the overnight batch). The note needs one sentence under "Loop modules" saying where a build loop at its limit goes: `research`, or `spec` when a check cannot be met as written.

## Not in this piece
- The automatic reviewer the `done` route leads to: slice 8: Automatic reviewer. Until it lands, `done` leads to today's section-builder step 7.
- What a kickback does to the other pieces of a run, and the run status `paused`: slice 9: Run controller. Until it lands, "the run pauses" means the single build stops and tells the person.
- The heartbeat, the stuck-builder timeouts and the wall-clock cap: slice 10: Crews and computer resources.
- Goal and gauntlet loops: slice 11: Goal loop module and slice 12: Gauntlet loop module.
- Removing the `/fix` command and the bug fast path: slice 4: Shaping sub-states in /shape.

## Decided
- Five builder statuses, each with one route, `environment_failed` never a kickback. (Decisions 29 and 46.)
- An attempt is a fresh builder with a note built by a script from failed checks, exit codes and files touched, never a model's summary. (Decision 46.)
- Defaults: three attempts, as today, and a 120-minute piece budget, matching the design's two-hour cap. Both are settings, to be measured by the real runs in slice 20. (Design note, "Settled when built".)
- A build loop at its limit goes to `research` by default, since failure to meet a clear bar is a missing fact; this is this slice's choice, listed in OPEN-DECISIONS.md.
- The fix discipline is built on, not rewritten: slice 4 moved the `fix` skill's order and escalation into `fix-loop.md` unchanged, and this slice reduces the escalation's six routes to the two kickbacks the design names. (Decision 36.)
- Project settings live in one tracked file, `.agents/loop-settings.json`, which later slices add keys to.

## Data
New tracked `.agents/loop-settings.json` in each founded project, written by founding, edited by the person, with keys added by slices 8 and 9. New attempt notes under the git-ignored `.agents/pieces/<number>/` from slice 6. Preserved failed work under `.agents/recovery/`, git-ignored, as `recovery.py` writes it. No project founded with AI Build Kit receives the file (decision 63).

## Leaves the tool
A kickback writes a `## Kickback` section on the piece's issue and pushes its branch to the project's GitHub repository, the branch push being one of the run's own branches. Nothing else new leaves.

## Must still hold
- A piece is claimed before any work, and nothing it could not claim is started: `state-moves.sh`.
- A missing tool on this computer is never installed by a run; the piece stops with the reason: `own-computer-work.sh`.
- A sensitive area with no acceptance stops the piece, never the run, and a run never accepts for the person: `acceptance-is-earned.sh`.
- Checks are written by the spec and fail before the code: `checks-first.sh`.
- A refused command is told, not worked round: `refused-commands.sh`.
- No issue numbers in tracked files; rehearsals named in AGENTS.md: `validate-kit.sh`.

## Relies on
- `section-builder/references/fix-loop.md`, the fix skill's discipline moved unchanged by slice 4: Shaping sub-states in /shape.
- `.agents/skills/section-builder/SKILL.md`, `.agents/skills/implement/references/running-longer.md`: on main today.
- `implement/scripts/recovery.py`, `section-builder/references/task-handoff.md`, `section-builder/references/task-context-capabilities.md`, `.agents/tests/failure-recovery.sh`, `.agents/tests/task-handoff.sh` and their fixtures: on the overnight batch branch `gwpicard/v1-overnight-integration-20261001` of the old repository, gwpicard/ai-build-kit, which stays; brought over in this slice.
- The gate script and the kickback transition: slice 2. The `loop:` label, the must-not-change line and acceptance checks: slice 3. The shaping sub-states a kickback lands in: slice 4. The evidence record and the gate's own check run: slice 6.

## Reach and risk
Boundary: section-builder (SKILL.md, the two new loop references, task handoff references), the implement skill (attempt-note script, recovery helper, running-longer reference), the gate script's status routes, the setup-ai-build-kit templates (loop settings), WORKFLOW.md, COMPATIBILITY.md.
Reaches: runs of several pieces, guarded by `the-runner.sh` and `parallel-run.sh`; worktrees, guarded by `kit-owns-worktrees-rehearsal.sh`; repairs, guarded by `fix-history-first.sh` and `notice-is-owed-by-the-refusal.sh`; the replay runner scenario 57, guarded by `replay-state.sh`.
If it breaks: a piece loops past its limit or is kicked back wrongly, and the person sees it on the issue. Undone by reverting the slice's pull request; preserved attempts stay on disk.
Depends on: 2, 3, 4, 6.
Loop module: build, because each route is a gate outcome a stub builder can drive.
Crew: default for the module.

## Under the hood
- Bring over from the overnight batch branch, one at a time and checked: `recovery.py` (`preserve` now; slice 9 uses `baseline` and `eligible`), `task-handoff.md`, `task-context-capabilities.md`, their rehearsals and fixtures. Drop the parked state and the `needs-` labels in them for the v1 states.
- Add `build-loop.md`, `attempt-note.py`, `templates/loop-settings.json`; change `fix-loop.md` from slice 4 for the v1 escalation; add `implement/scripts/run.py`, a small loop driver that starts each attempt and hands the result to `gate.py result`, which routes it. Slice 9 grows `run.py` into the run controller. The gate script itself never starts an agent.
- Expected to change: `the-runner.sh` (three attempts park), `state-moves.sh` (parked removed), `checks-first.sh`, `fix-history-first.sh`, `notice-is-owed-by-the-refusal.sh`, `manual-step.sh` (`parked` meanings), `replay-state.sh` (scenario 57's parked expectations), `parallel-run.sh` (background agents become fresh builders).
- SOURCES.md: credit obra/superpowers for the builder statuses and EveryInc/Anthropic harness work for fresh contexts, as `agentic-loop-research.md` records.
- Kit rules: five questions in the pull request; adapters rebuilt; `validate-kit.sh`; the Humanizer before saving prose; no issue numbers.

## Evidence
Rule-shape rehearsal for the loop references (`loop-modules.sh`), script rehearsals driving the gate with stub builders against the stand-in GitHub (`builder-status-rehearsal.sh`, `attempt-note-rehearsal.sh`), and the overnight batch's own rehearsals brought over. The real run of one `loop:build` and one `loop:fix` piece belongs to slice 20.

## Size
Two parts, two sittings: Part a (statuses, attempts, notes, settings, the handoff and recovery brought over); Part b (the fix loop moved and its gate rule).

## Consistency notes
- The project settings file is `.agents/loop-settings.json`, introduced here from `templates/loop-settings.json`. Slice 8 adds `review_rounds`, slice 9 adds `at_once`, `run_budget_minutes`, `ci_rounds` and `merge`, and slice 10 adds the computer numbers, with a git-ignored per-computer file, `.agents/loop-settings.local.json`, beside it.
- The gate subcommands this slice adds are `gate.py result` and `gate.py switch-module`. Starting attempts belongs to `implement/scripts/run.py`, the loop driver that slice 9 grows into the run controller, so the gate script only checks and writes state and never starts an agent.
- `section-builder/references/fix-loop.md` is slice 4's file, moved there unchanged when `/fix` went. This slice builds the v1 fix loop on it.
- Mechanisms from the overnight batch are read from the old repository's branch, `gwpicard/v1-overnight-integration-20261001` in gwpicard/ai-build-kit, which stays.
