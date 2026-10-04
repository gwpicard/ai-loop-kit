# Slice 9: The person picks pieces and a run builds them all, joins them one at a time and opens one pull request

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 5: Area map for the whole project, kept by the project check; slice 6: Frozen-bar enforcement; slice 7: Build and fix loop modules; slice 8: Automatic reviewer.

## So that
`/implement` with one number, several numbers or `queue` starts a run that asks nothing, keeps every piece's status in one record the gate writes with the labels, and hands back one pull request whose combined code passed the full checks, with any piece that broke it sent back to shaping alone.

## Done when

### Part a: the run record, a run of one, and the plan

#### Works
- The run controller, `implement/scripts/run.py` (slice 7's loop driver, grown here), drives every run, and a run keeps one record, the run record `.agents/runs/<run name>/run.json` in the main folder, replacing `state.json`: the run's status (`planned`, `running`, `paused`, `in preview`, `merged`, `abandoned`), its integration branch or `null` for a run of one, its pull request, its budget used, its CI rounds, and for each piece its status (`queued`, `building`, `checking`, `integrated`, `kicked back`, `withdrawn`), branch, worktree, attempts and a pointer to `.agents/pieces/<number>/`. Check: new `.agents/tests/run-record-rehearsal.sh` drives the gate through a run with stub builders and the stand-in GitHub (`replay/fake-github`) and validates every written record against a stored schema.
- The gate script writes a piece's status in the record in the same step as its labels, and refuses when either write fails, leaving both as they were; each pair in the design note's table holds at every step (`queued` with `state:ready`, `building` and `checking` with `state:building`, `integrated` with `state:in-review`, `kicked back` with `state:shaping`, `withdrawn` with `state:ready`). Check: `run-record-rehearsal.sh` reads labels and record after every step, and once with the stand-in refusing the label write.
- `/implement <number>` is a run of one: one piece on its own branch, with a pull request to `main` once the piece reaches `state:in-review`, and a run record like any other. Check: `run-record-rehearsal.sh`.
- `/implement` with several numbers, or `queue` for every `state:ready` piece, prints the plan once (waves in order, each piece's loop module, what is left out and why) and starts without a question; the parallel count, the budgets and the merge policy are read from `.agents/loop-settings.json` (new keys `at_once`, default 1; `run_budget_minutes`, default 480; `ci_rounds`, default 3; `merge`, default `person`). Check: new `.agents/tests/run-controller.sh` (rule-shape) reads the implement skill and `references/running-longer.md`, replacing `the-runner.sh`'s plan, merge-question and `at_once`-question rules; `run-record-rehearsal.sh` reads the printed plan.
- No run starts while `main` is red: before planning, the run reads the project check's result on `main`'s latest commit (the job named on the capability profile's `Project check:` line), and on a red result files a `type:bug` piece in `shaping:raw` through the gate, naming the failing job and its link, prints that one line, and starts nothing. Check: `run-record-rehearsal.sh` with the stand-in reporting red, then green.
- At the start of a run, each chosen piece passes slice 3's ready-gate lint again on today's `main`, which works out its reach again; a piece whose reach no longer matches is kicked back to `shaping:spec` before it is claimed, and the run carries on without it. Check: `run-record-rehearsal.sh`.
- The `/queue` command is removed: its skill folder goes, `validate-kit.sh`'s command list drops it, the adapters are rebuilt, and `/implement`'s plan is the only plan. Check: `validate-kit.sh` and `claude-plugin.sh` (the plugin's command set); `queue-groups.sh` removed and its surviving rules moved to `run-controller.sh`.

#### When it is not the normal case
- The code is not on GitHub yet: no run starts, and the one line says the first upload waits for the person's yes, as today's first-upload rule says. Check: `first-upload-asks.sh`, extended.
- GitHub cannot be reached for `main`'s result: the run does not start and says so, never treating an unknown result as green. Check: `run-record-rehearsal.sh`.
- `main` has no project check result at all: treated as unknown, said once, and the run does not start. Check: `run-record-rehearsal.sh`.
- Nothing is ready: the run ends at once with what would make something ready. Check: `run-record-rehearsal.sh`.

### Part b: waves and the integration branch

#### Works
- A new implement script, `scripts/plan-run.py`, reads each piece's `Depends on:` and `Boundary:` and prints waves: a piece comes after every piece it depends on, two pieces whose boundaries share an area are never in the same wave, a wave holds at most `at_once` pieces, and when every piece shares an area the count is one. Check: new `.agents/tests/plan-run-rehearsal.sh` runs it over fixed contracts and compares with stored waves, including a dependency cycle, which it refuses by name.
- A run of several cuts `run/<run name>` from `main` at the start, pushes it, and integrates each finished piece one at a time: the piece's branch takes in the integration branch with a merge commit (a new `--base <branch>` option on section-builder's `scripts/bring-up-to-date.sh`, with no fold), `gate.py integrate <number> --run <run name>` runs the full checks on that combined commit (slice 6's evidence run), and only on green does it move the integration branch to it and write the piece `integrated`. Check: new `.agents/tests/integration-rehearsal.sh` with two pieces in a throwaway repository and a bare remote, reading the integration branch's history.
- An agent never resolves a conflict by judgement: a piece whose merge from the integration branch conflicts is rebuilt once by a fresh builder from the integration branch's head, as an attempt counted against its limit, and a second conflict kicks it back to `shaping:spec` with the conflicting files named. Check: `integration-rehearsal.sh` with two pieces that change the same line.
- Once every piece is integrated, kicked back or withdrawn, the run opens one pull request from the integration branch to `main`, carrying a `Closes #<number>` line for each integrated piece and no closing word anywhere else, and the run's status becomes `in preview`. Check: `integration-rehearsal.sh` reads the pull request body; `closing-words.sh` reads the new body template.
- The run's pull request merges only as the `section-builder` skill's `references/merge.md` says, with the merge policy `person` from settings; when it merges, the run becomes `merged`. Check: `one-merge-step.sh`, extended for the run's pull request.

#### When it is not the normal case
- A piece whose dependency was kicked back is `withdrawn`, returned to `state:ready` by the gate, and stays out of the integration branch. Check: `integration-rehearsal.sh`.
- Another tool's worktree, or the main folder on another branch: the run still works from the main folder's `.agents/worktrees/` and never switches the main folder, as today. Check: `kit-owns-worktrees-rehearsal.sh`.

### Part c: bisect, kickback, limits and resuming

#### Works
- When the run's pull request check goes red on the integration branch, the run runs the failing check twice on that commit; where it passes once, the check is unreliable, a `type:chore` piece is filed for it, and no piece is kicked back. Otherwise it bisects the integration branch's piece merges with `git bisect run` on the failing check, reverts the first breaking piece's merge with `git revert -m 1` (never a force push), kicks that piece back to `shaping:research` with the failing check in its Kickback section, withdraws any integrated piece that depends on it the same way, and pushes. Check: `integration-rehearsal.sh` with three pieces where the second breaks a check only once combined, and a flaky control.
- A kickback in a run never stops the run: the gate writes `kicked back` and `state:shaping` together, and the run carries on with the pieces that do not depend on it. Check: `run-record-rehearsal.sh`.
- The run pauses, starting nothing new while running builders finish, when its budget is spent, when the pull request's CI has failed `ci_rounds` times, when builders report three refused commands in a row in their results, or when slice 7's `environment_failed` route asks; the pause is written with its reason, and the person is told in one line. Check: `run-record-rehearsal.sh`, one case per reason.
- A new session resumes from `run.json`, never from memory: `/implement` typed alone, `/what-now` and `/maintain` name a run that is `running` or `paused` and offer to continue it, a piece shown `building` continues from its last commit after `recovery.py baseline` and `eligible` (overnight batch branch, brought onto main by slice 7) check the base it continues on, and the run continues in the same turn while an eligible step is left. Check: `run-record-rehearsal.sh` kills the run mid-piece and resumes it; `failure-recovery.sh`.
- The person can abandon a run with `gate.py run abandon <run name>`: the run becomes `abandoned`, every branch is kept, and the gate returns each piece not yet merged to `state:ready` as `withdrawn`, through the transitions slice 2 added for this. Pausing and continuing are `gate.py run pause <run name>` and `gate.py run resume <run name>`. Check: `run-record-rehearsal.sh`.
- When a run closes, merged or abandoned, `gate.py run close <run name>` writes one `run-summary` block into the run's pull request body: each piece with its final status and loop module, kickbacks by shaping sub-state, attempts used, CI rounds, budget used, and whether the merge was the person's or automatic. A run of one writes the same block on its own pull request. The block is written once and never edited after. Check: `run-record-rehearsal.sh` reads the block from the stand-in pull request after a merged run of three and after an abandoned run, and validates it against a stored schema.

#### When it is not the normal case
- The failing check does not fail on this computer (it fails only on GitHub's runner): no bisect, the run pauses with `environment failed` and the job's link, and nothing is kicked back. Check: `integration-rehearsal.sh`.
- Two runs at once in one project: the second does not start while another run is `running`, and names it. Check: `run-record-rehearsal.sh`.
- A run state file from AI Build Kit (`state.json`): does not arise in an AI Loop Kit project, because no project founded with AI Build Kit is moved (decision 63); `/implement` reads only `run.json`.

### Documents, every part
- The implement skill's SKILL.md and `references/running-longer.md`, rewritten around the run record, waves and the integration branch; the sections on stacks and parts, `at_once` and merge pre-approval go. Check: `run-controller.sh`.
- section-builder's SKILL.md step 1 (a piece in a run starts from the integration branch's head in its worktree) and `references/merge.md` (the run's pull request). Check: `run-controller.sh`; `validate-kit.sh`'s step 1 wording check, updated.
- The what-now skill (offers to resume and no longer offers `/queue`). Check: `run-controller.sh`.
- WORKFLOW.md section 1, "Commands" (no `/queue`) and section 10, renamed "Runs: /implement", with the run statuses, the one pull request and what a kickback does. Check: `run-controller.sh`.
- `README.md`'s command list and `docs/COMPATIBILITY.md`'s "Harness map" (eight commands). Check: `validate-kit.sh` command count; `run-controller.sh` reads both.
- Root `AGENTS.md`: the new rehearsals named, `queue-groups.sh` and `the-runner.sh` gone or renamed. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Runs", the run rows of "What a machine enforces" and the `/queue` sentence of "Commands". The note needs four additions: that abandoning a run returns pieces not yet merged to `state:ready`, through the two transitions slice 2 adds to the table; that a combined failure kicks the breaker back to `research`; that a failing check is run twice before bisecting, so an unreliable check becomes a chore piece; and that a closed run leaves a `run-summary` block on its pull request, which slice 17 counts.

## Not in this piece
- How many builders the computer can carry, heavy pieces, heartbeats: slice 10: Crews and computer resources.
- Automatic merge of the run's pull request and the smoke test on its preview: slice 13: Merge policy.
- The preview address the `in preview` status shows: slice 14: /deploy replacing /ship.
- Pushes limited to the run's own branches by a scoped token: slice 15: Safety boundary for runs.
- The loop board and notifications: slice 16: Boards and notifications.
- Lessons promoted at run close: slice 17: /maintain absorbs /sync.

## Decided
- Every build is a run, a run of one opens its own pull request, and a run of several opens one from its integration branch. (Decision 2.)
- A run asks nothing; the count, budgets and merge policy come from `.agents/loop-settings.json`. Today's merge and parallel questions go. (Decision 3.)
- `at_once` defaults to 1 until slice 10 measures the computer; the design's run crew default of 3 arrives with that measurement.
- Pieces join one at a time on the combined result, no agent resolves a conflict, and a red integration branch is bisected and only the breaker kicked back. (Decision 30.)
- A piece's status lives in the run record, written with the labels in one gate step. (Decisions 9 and 10.)
- No run on a red `main`; the kit files a bug piece instead. (Decision 38.)
- `/queue` is removed here, as its plan is now the run's own. (Decision 21.)
- Defaults: a run budget of 480 minutes and three CI rounds, to be measured by slice 20's real runs. (Design note, "Settled when built".)
- A merge to integrate always uses a merge commit and never a rebase, and a broken piece is taken out with a revert, so nothing needs a force push.

## Data
New `.agents/runs/<run name>/run.json` and `progress.md` (git-ignored, main folder), written by the gate only, replacing `state.json`. New keys in `.agents/loop-settings.json`. New `run/<run name>` branches on GitHub, kept after a run ends until `/maintain`'s stale-branch step lists them. Bug and chore pieces filed by the run. A `run-summary` block in each closed run's pull request body, written once by the gate.

## Leaves the tool
The integration branch and each piece's branch are pushed to the project's GitHub repository, one pull request per run is opened, and the run files bug and chore issues there. All are the project's own repository, under today's first-upload rule.

## Must still hold
- The first upload of a project's code waits for a yes: `first-upload-asks.sh`.
- No push to `main` and no force push: `push-to-main-rules.sh`.
- A merge waits for a yes that names it, until slice 13: `one-merge-step.sh`, `merge-ask-rule.sh`.
- Only the `Closes` line closes a piece: `closing-words.sh`.
- No pull request merges on a check that ran against an older `main`: `recheck-before-merge.sh`, `recheck-before-merge-rehearsal.sh`.
- The changelog files fold at merge without conflict: `fold-at-merge.sh`, `fold-at-merge-rehearsal.sh`, `changelog-files.sh`.
- The kit owns each worktree, never removes one with unsaved work, and never switches the main folder: `kit-owns-worktrees.sh`, `kit-owns-worktrees-rehearsal.sh`, `worktree-links.sh`.
- A run stops at a sensitive area with no acceptance and never accepts for the person: `acceptance-is-earned.sh`.
- No issue numbers in tracked files; rehearsals named in AGENTS.md: `validate-kit.sh`.

## Relies on
- `.agents/skills/implement/SKILL.md`, `references/running-longer.md`, `scripts/worktree.sh`, `.agents/skills/section-builder/scripts/bring-up-to-date.sh`, `references/merge.md`, `.agents/skills/queue/`, `.agents/tests/replay/fake-github`: on main today.
- Same-turn continuation from the overnight batch branch's `references/running-longer.md` (`gwpicard/v1-overnight-integration-20261001` in the old repository, gwpicard/ai-build-kit, which stays), brought over in this slice.
- The gate script and transitions: slice 2. `Depends on:` and `Boundary:` fields and the lint: slice 3. The area map: slice 5. The gate's check run: slice 6. Builder statuses, kickback, `recovery.py` and `.agents/loop-settings.json`: slice 7. The automatic review before `integrated`: slice 8.

## Reach and risk
Boundary: the implement skill (SKILL.md, running-longer reference, the new planner script), section-builder (step 1, merge reference, `bring-up-to-date.sh`), the gate script's run actions, the what-now skill, the queue skill (removed), WORKFLOW.md, README.md, COMPATIBILITY.md.
Reaches: merging and the fold, guarded by `fold-at-merge-rehearsal.sh`, `recheck-before-merge-rehearsal.sh`, `one-merge-step.sh`; worktrees, guarded by `kit-owns-worktrees-rehearsal.sh`; the plan printout, guarded by `plan-printout.sh`; installation routes, guarded by `claude-plugin.sh` and `agent-plugin.sh`; replay scenarios 52, 53, 55 and 57, guarded by `replay-state.sh` and `gated-turns.sh`, which slice 20 rewrites.
If it breaks: a run stalls or opens a pull request whose combined code is red, and the person sees it on the pull request's check. Undone by reverting the slice's pull request; run branches and records are kept.
Depends on: 2, 3, 5, 6, 7, 8.
Loop module: build, because each promise is a run outcome a throwaway repository with stub builders can show.
Crew: default for the module.

## Under the hood
- Rewrite `running-longer.md` around `run.json`, waves and integration; keep its worktree sections and `worktree.sh`.
- Add `implement/scripts/plan-run.py`; grow `implement/scripts/run.py` into the run controller, which starts builders, integrates and bisects; add `--base <branch>` to `bring-up-to-date.sh`; add the gate's `run` subcommand (`start`, `pause`, `resume`, `abandon`, `close`) and `integrate`. Bisecting stays in the run controller, which calls `gate.py move` for the kickback.
- Remove `.agents/skills/queue/`, update `validate-kit.sh`'s command list and rebuild adapters.
- Reused from the overnight batch branch: same-turn continuation, and `recovery.py baseline` and `eligible` (brought over by slice 7).
- Expected to change: `the-runner.sh` (replaced by `run-controller.sh`), `parallel-run.sh` (the question goes), `queue-groups.sh` (removed), `state-moves.sh`, `recheck-before-merge.sh` (the sweep goes), `one-merge-step.sh` (pre-approval goes), `first-upload-asks.sh`, `kit-owns-worktrees.sh`, `checks-first.sh` and `loop-first-ground.sh` (they name `/queue`), `plan-printout.sh`, `replay-state.sh` (scenario 57), `claude-plugin.sh` and `agent-plugin.sh` (command count).
- SOURCES.md: credit Gas Town and merge queues for integrating one at a time, and cc-sdd for boundary and dependency fields, as `agentic-loop-research.md` records.
- Kit rules: five questions in the pull request; adapters rebuilt; `validate-kit.sh`; the Humanizer before saving prose; no issue numbers.

## Evidence
Script rehearsals in throwaway repositories with a bare remote, stub builders and the stand-in GitHub (`run-record-rehearsal.sh`, `plan-run-rehearsal.sh`, `integration-rehearsal.sh`), a rule-shape rehearsal for the prose (`run-controller.sh`). The real run of several pieces belongs to slice 20.

## Size
Three parts, two sittings each: Part a (record, run of one, plan, green `main`, `/queue` removed); Part b (waves and the integration branch); Part c (bisect, kickback, limits, resuming and abandoning).

## Consistency notes
- Names: the run controller is `implement/scripts/run.py` (the design note's "run script"), the run record is `.agents/runs/<run name>/run.json`, and the settings are the keys `at_once`, `run_budget_minutes`, `ci_rounds` and `merge` (`"person"` by default) in `.agents/loop-settings.json`. Every later slice uses these names.
- The gate subcommands this slice adds are `gate.py run` with `start`, `pause`, `resume`, `abandon` and `close`, and `gate.py integrate`. The board buttons in slice 16 copy the `run` commands exactly.
- The transitions back to `state:ready`, for a withdrawn piece and an abandoned run, are in slice 2's table, so this slice only calls them.
- The run closes with a `run-summary` block on its pull request. Slice 17 counts clean runs, merged runs and the kit measures from those blocks and from nothing else.
- No run state from AI Build Kit is read (decision 63).
- This slice removes the question before a run, `merge_preapproved` and the at-once question from `running-longer.md`. The dead "Pre-approval for a run" section of `merge.md` goes in slice 13: Merge policy, and the computer-sized builder count arrives in slice 10: Crews and computer resources.
