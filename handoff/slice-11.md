# Slice 11: A piece whose done is a number gets built in a measure, change, keep or discard loop until it hits its target

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 3: Contract v2 and the ready-gate lint; slice 6: Frozen-bar enforcement; slice 7: Build and fix loop modules; slice 9: Run controller; slice 10: Crews and computer resources.

## So that
A person who can say "done is this number reaching that target" gets the piece built by a loop the builder cannot fool, and sees either the target met or the best honest result with its numbers.

## Done when
### Works
- A `loop:goal` piece is built in rounds: the run controller measures the starting value with the contract's metric command, the builder makes one change, the script measures again, and the script alone keeps the change when the number moved towards the target and every guard check is green, or discards it. Check: new `.agents/tests/goal-loop-rehearsal.sh` runs the shipped `implement/scripts/goal.py` in a throwaway repository whose metric command prints a number read from a file, with a stand-in builder that makes a better change, a worse change and a better change that breaks a guard check, and reads keep, discard, discard.
- The metric command's last line of output is the value, read as a number; output with no number on its last line, or a non-zero exit, counts as a failed measurement and the change is discarded. Check: `goal-loop-rehearsal.sh` with a metric that prints prose and one that exits 2.
- A discarded change never reaches the piece's branch: each round is built on its own attempt branch cut from the last kept commit, and keeping is a fast-forward of the piece branch done by the script; the builder never moves the piece branch. Check: `goal-loop-rehearsal.sh` reads `git log` of the piece branch after a discard and finds only kept commits, and finds no `reset --hard` in the stand-in Git log.
- The loop ends when the target is reached with every guard check green and the held-out check passing, and the piece goes on to the automatic review. Check: `goal-loop-rehearsal.sh` reaches the target on the third round and reads the run record's piece status `checking`.
- The held-out check runs only on the final kept result, in a separate worktree, and the builder's brief and worktree never contain it. Check: `goal-loop-rehearsal.sh` lists the builder's worktree and brief and finds no held-out path, and reads the held-out run in the gate's own worktree.
- A target reached with the held-out check failing is not a pass: the piece goes to `review:person` with both numbers. Check: `goal-loop-rehearsal.sh` with a held-out check that fails on the final result.
- A goal that spends its budget (attempts, time or tokens, whichever first) without reaching the target goes to `in-review` as `review:person`, carrying its best kept result that passed the guard checks, the starting value, the best value and the target. Check: `goal-loop-rehearsal.sh` with a stand-in builder that never reaches the target, reading the gate's labels in the stand-in GitHub log and the numbers in the pull request body it wrote.
- A goal whose best kept result is no better than the starting value opens no pull request: the piece is kicked back to `shaping:clarify` with the numbers, because the target or the approach needs a decision. Check: `goal-loop-rehearsal.sh` with a stand-in builder whose every change is discarded.
- The metric command, the files it reads and the guard checks are part of the frozen bar: a builder change to any of them is refused by the build gate and the round is discarded. Check: `goal-loop-rehearsal.sh` with a stand-in builder that edits the metric script, reading the gate's refusal; `frozen-bar-rehearsal.sh` from slice 6 extended with a goal contract.
- With a crew of 2 or 3 written in the contract, the run builds a race: each builder works in its own worktree from the same kept commit, the script measures each, keeps the best that passed the guard checks and discards the rest; the race width never passes 3 or the computer's builder count. Check: `goal-loop-rehearsal.sh` races two stand-in builders and reads which commit was kept; `resources-rehearsal.sh` from slice 10 with a goal race on a computer suggesting one builder, reading a race of one.
- The ready-gate lint accepts an optional `Keep when better by:` line on a `loop:goal` contract, a field this slice owns and adds to slice 3's list, refuses it on any other loop module, and the piece contract template in the `setup-ai-build-kit` skill's `references/pieces.md` describes it. Check: slice 3's lint rehearsal extended with both cases; `piece-contract.sh` reads the field rule.
- The run record holds, for a goal piece, the starting value, the current value, the best kept value, the target and one line per round (kept or discarded and why), for the loop board to show. Check: `goal-loop-rehearsal.sh` reads those fields.
- `running-longer.md` has a "Goal loop" section with these rules, and its old "Goal modes" section, which treated a coding agent's own `/goal` as a run, is replaced by one sentence: a native goal mode's judge never decides when a goal piece is done; the metric does. Check: new `.agents/tests/goal-loop.sh` (rule-shape) reads each rule back and proves it load-bearing; `run-controller.sh` (slice 9) changes its goal-mode assertions to the new sentence.
- The `section-builder` skill says how a builder works inside one goal round: one change per round, the attempt note the script built, nothing outside the piece's boundary. Check: `goal-loop.sh`.
- WORKFLOW.md replaces its paragraph on goal or long-run modes with one on the goal loop module: when shaping picks it, what the person sees when the target is met and when it is not. Check: `goal-loop.sh` reads it and refuses the old "Same run, same rules: take the condition from a done line".
- docs/COMPATIBILITY.md's "Long runs" row and README.md's account of how a project flows name the goal loop as the kit's own and say it does not depend on a native goal mode. Check: `goal-loop.sh` reads both.
- docs/SOURCES.md credits karpathy/autoresearch for the keep or discard loop with a fixed scorer and Claude Code's goal documentation for what a transcript-only judge cannot prove. Check: `goal-loop.sh` reads both credits; `validate-kit.sh` resolves the links.
- The root AGENTS.md describes both new checks. Check: `validate-kit.sh`.

### When it is not the normal case
- The metric command fails on the starting commit: environment failed, never a kickback; the run retries once and then pauses, as slice 7's status route says. Check: `goal-loop-rehearsal.sh` with a metric that fails before any change.
- The metric is noisy, so the same commit measures differently: the contract's `Keep when better by:` line sets the smallest change that counts, and a change inside that margin is discarded. Without the line, any improvement counts. Check: `goal-loop-rehearsal.sh` with a metric that adds a small random amount and a margin larger than it.
- A guard check is flaky (passes and fails on the same commit): the round is discarded, the run notes the check, and the run files one `type:chore` raw piece for it rather than sending the goal piece back. Check: `goal-loop-rehearsal.sh` with a guard check that alternates, reading one raw piece in the stand-in GitHub log.
- The builder decides the approach needs a different bar (for example a checks-based build): it switches loop module and logs it only when the new bar comes from the spec with no new decision; otherwise the piece is kicked back. Check: `goal-loop.sh` reads the switch rule from `running-longer.md`.
- The computer is under pressure during a race: slice 10's back-off stops the newest racer with no commit, and the race carries on narrower. Check: `resources-rehearsal.sh`.

## Masterplan change
Design note: "Loop modules" (the goal row and the paragraph on a goal that spends its budget) and the goal line of "Crews" in docs/design/agentic-loop.md. The note does not say what happens when the best result is no better than the start; this slice adds one sentence there: no gain is a kickback to `clarify`, not a review.

## Not in this piece
- The goal bar fields in the contract and the lint that checks them: slice 3: Contract v2 and the ready-gate lint.
- The contract hash and the build gate's diff guard: slice 6: Frozen-bar enforcement; this slice only adds the metric files to what that guard protects.
- The loop board's current and best values: slice 16: Boards and notifications.
- A recorded real goal run: slice 20: Replay harness rewrite and real runs.
- Shaping a goal piece in `/shape` (asking for the metric, the target and the held-out check): slice 4: Shaping sub-states in /shape.

## Decided
- The script, never the builder, measures and decides keep or discard, because a metric loop is safe only with a scorer the agent cannot reach (decisions 12 and 28; research "Loops and goals").
- Discard by never moving the piece branch rather than by resetting it, because `git reset --hard` is a refused command and the attempt branch keeps the evidence of what was tried.
- A missed target goes to `review:person` with the best result (decision 15); no gain at all is a kickback, because handing the person a pull request with nothing in it wastes a review.
- The held-out check is kept out of the builder's worktree and brief and runs once at the end. It is hidden, not secret: the sandbox in slice 15 decides whether a builder can read it at all.
- A noisy metric is handled by a margin written in shaping, not by the script averaging runs, because the margin is a decision about the bar and the bar is fixed in shaping.
- A native goal mode never ends a goal piece, because its judge reads only the transcript (research "Loops and goals").

## Data
- New run record fields for goal pieces (starting, current, best and target values; one line per round) in the run folder slice 9 writes, which git ignores.
- Attempt branches named `<piece branch>-goal-<round>` on this computer only; the script removes them when the piece leaves `building`, keeping the kept commits on the piece branch.
- The held-out check's location and hash in the contract, written in shaping; no new tracked file in the project beyond the piece's own checks.

## Leaves the tool
Nothing new leaves the tool, because measurements and attempt branches stay on the computer; only the piece branch with kept commits is pushed, through the run's existing save route, and the pull request body carries the numbers.

## Must still hold
- A builder never edits, skips or deletes an acceptance or guard check. Check: slice 6's frozen-bar rehearsal.
- Refused commands stay refused. Check: `push-to-main-rules.sh`, `refused-commands.sh`.
- One writer per piece. Check: `crews.sh` from slice 10.
- A sensitive area with no acceptance never reaches a run. Check: `run-controller.sh`, `acceptance-is-earned.sh`.
- No issue numbers and no attribution lines in tracked files. Check: `validate-kit.sh`.

## Relies on
- The goal bar fields and `Crew:`: slice 3. The build gate and contract hash: slice 6. Builder statuses, attempt notes and limits: slice 7. The run record and run controller: slice 9. The crew starter and resources: slice 10.
- `implement/scripts/worktree.sh` and `implement/references/running-longer.md`: on main today.

## Reach and risk
Boundary: the `implement` skill (its run references and a new goal script), the `section-builder` skill's account of one round, WORKFLOW.md, README.md, docs/COMPATIBILITY.md, docs/SOURCES.md, the root AGENTS.md checks list.
Reaches: runs (`run-controller.sh`, `parallel-run.sh`), worktrees (`kit-owns-worktrees-rehearsal.sh`), the frozen bar (slice 6's rehearsal), resources (`resources-rehearsal.sh`).
If it breaks: a goal piece is marked done on a number it never reached, or loops past its budget; the person sees it on the loop board or in review. Undone by reverting the slice's pull request; nothing on `main` changes until a goal piece's pull request merges.
Depends on: 3, 6, 7, 9, 10.
Loop module: build, because each rule is a decision the goal script makes that a throwaway repository can judge.
Crew: default.

## Under the hood
Add `implement/scripts/goal.py` (measure, attempt branch, keep or discard, race, held-out run, budget), called by slice 9's run controller for `loop:goal` pieces. Add the "Goal loop" section to `running-longer.md` and replace "Goal modes". Add the goal metric files to slice 6's protected set. Add `goal-loop.sh` (rule-shape) and `goal-loop-rehearsal.sh` (throwaway repository, stand-in builder, stand-in GitHub). Change `run-controller.sh`'s two goal-mode assertions. The overnight batch's `goal-routing.md` fixture is not reused, because it tested a native goal entering a run, which this slice removes. A canonical skill changes: five questions answered in the pull request, SOURCES.md credits, adapters rebuilt, validator run, humanizer on the prose, no issue numbers.

## Evidence
A rule-shape check with each rule proved load-bearing, and a script rehearsal in a throwaway repository with a stand-in builder and metric. The real goal run is slice 20's.

## Size
Two sittings: the goal script and its rehearsal, then the prose, the documents and the rule-shape check.

## Consistency notes
- `Keep when better by:` is this slice's field. It extends slice 3's contract v2 and lint, and slice 3 names it as this slice's; no other slice defines it.
- The goal loop is driven by the run controller, `implement/scripts/run.py` (slice 9), which calls `goal.py`; "the run controller" replaces the drafts' "run script" throughout.
- The goal piece's numbers live in the run record, `.agents/runs/<run name>/run.json`, for the loop board in slice 16.
