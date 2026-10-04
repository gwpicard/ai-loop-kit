# Slice 10: A run starts the agents the piece declares, and sizes itself to the computer so it never freezes it

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 3: Contract v2 and the ready-gate lint; slice 7: Build and fix loop modules; slice 8: Automatic reviewer; slice 9: Run controller.

## So that
A person who starts a run of several pieces gets small, fixed crews per piece and a builder count chosen from the computer's own memory and cores, so the run finishes without anyone having to watch the machine.

## Done when

This slice splits into two parts. Each part merges on its own pull request.

### Part a: crews

#### Works
- The `implement` skill ships four role definitions, builder, critic, reader and checker, each with its own list of allowed tools, and only the builder's list holds a tool that writes files or runs a shell command that changes the worktree. Check: new `.agents/tests/crews.sh` reads the four files and fails when a write or edit tool appears in the critic, reader or checker list, and on a copy where the builder list loses its write tools.
- Founding and the run place the four role definitions into the project's `.claude/agents/` when they are missing or older, and change nothing on a second run. Check: new `.agents/tests/crews-rehearsal.sh` runs the placement step on each of the six layouts `plan-helper-routes.sh` builds (whole copy, shared installer for several agents and for Claude Code alone, Claude Code plugin, Agent Plugins folder) and reads the four files back, then runs it again and finds no change.
- The run controller starts every crew member itself, from the shape table: research readers 1 for a fact and 2 to 4 for a comparison (cap 5), prototype variants 1 (cap 3), readiness checker 1 (cap 1), fix probes 1 per ranked cause (cap 3) then one builder then a critic, build one builder then one critic, goal 1 (cap 3), gauntlet critics 1 (cap 3). A crew wider than its cap is refused with one line naming the step and the cap. Check: `crews-rehearsal.sh` drives the crew starter with a stand-in agent command and counts the members started for each step, and feeds it a contract asking for four fix probes and reads the refusal.
- A crew member receives only its declared inputs: the critic gets the contract file and the diff file and nothing else, the checker gets the contract alone, and no member gets a builder's transcript or attempt notes. Check: `crews-rehearsal.sh` reads the argument list and the working folder the stand-in agent command was given for each role and fails on any extra path.
- A verdict comes back in one fixed JSON shape the gate script reads, and a verdict that does not parse counts as no verdict and is never read as a pass. Check: `crews-rehearsal.sh` feeds the reader one good verdict, one with a missing field and one with trailing prose, and reads pass, no verdict and no verdict.
- A comparison between two results runs in both orders, and a split verdict is not a win. Check: `crews-rehearsal.sh` drives the comparison helper with a stand-in critic that always prefers the first result and reads "split, no win".
- A finding counts only when it names a failing check or a reproduction the run can re-run. Check: `crews-rehearsal.sh` feeds a critic verdict with one finding tied to a check name and one with prose only, and reads one counted finding.
- No agent starts a writer: the builder role definition has no tool that starts an agent, and the run controller refuses a second builder for a piece that already has one alive. Check: `crews.sh` for the role list; `crews-rehearsal.sh` asks the starter for a second builder on one piece and reads the refusal.
- `running-longer.md`, the `implement` SKILL.md and the `section-builder` skill's `references/task-handoff.md` (brought onto main by slice 7) say who starts each member, what each receives, the verdict shape and that one piece has one writer. Check: `crews.sh` reads each rule back from those three files and proves each load-bearing with `lib/rule-shape.sh`.
- WORKFLOW.md section 10 explains crews in plain words: one writer per piece, a reviewer that sees only the contract and the change, and that every helper costs roughly a full context. Check: `crews.sh` reads those three sentences from WORKFLOW.md and proves each load-bearing.
- docs/COMPATIBILITY.md says role definitions with tool lists are a Claude Code feature and that other coding agents run the same roles in one session, one after another. Check: `crews.sh` reads the line, and `compatibility-grades.sh` still passes.
- The root AGENTS.md names both new rehearsals. Check: `validate-kit.sh` ("AGENTS.md names every maintainer check").

#### When it is not the normal case
- The coding agent has no role definitions (any agent but Claude Code): the run uses the same four roles in one session, one after another, and says so once in its opening line. Check: `crews.sh` reads the fallback rule from `running-longer.md`.
- A crew member ends without a verdict: it counts against the piece's budget and as no verdict; the gate never reads silence as a pass. Check: `crews-rehearsal.sh` with a stand-in that exits without output.
- A contract changes the crew without a reason: does not arise at run time, because the slice 3 lint refuses it at the ready gate; the starter still refuses an unknown shape. Check: `crews-rehearsal.sh` feeds an unknown shape.

### Part b: computer resources

#### Works
- Before a run starts, the run controller measures free memory and processor cores and suggests a builder count: memory left after the reserve, divided by the memory each builder needs, never more than half the cores and never more than four. Check: new `.agents/tests/resources-rehearsal.sh` runs the shipped `implement/scripts/resources.py suggest` against stand-in readings (memory file and core count passed in) for 8, 16 and 32 GiB with 4, 8 and 16 cores, and reads the expected counts.
- The person raises the count above the suggestion only after one warning line, and never above six. Check: `resources-rehearsal.sh` asks for 5 and reads the warning, asks for 9 and reads 6 with one line saying so.
- A piece whose contract says `Heavy: yes` runs alone: no other builder is alive while it builds. Check: `resources-rehearsal.sh` plans a wave holding one heavy piece and reads it in a wave of its own.
- Before each new builder starts, the run checks memory pressure and swap. Under pressure it starts no new builder, stops dev servers nobody is using and lowers the count for the rest of the run. Under critical pressure it also stops the newest builder with no commit yet, keeps its worktree and counts no attempt. Starts resume at the lower count after ten minutes of normal pressure. Check: `resources-rehearsal.sh` feeds a sequence of stand-in readings and reads each decision and each change written to a stand-in run record with its reason.
- When a usage limit is reached, the run starts nothing new and records the time the allowance resets. Check: `resources-rehearsal.sh` feeds the stand-in builder's usage-limit output and reads the paused run record with the reset time.
- The run's opening line says that a run of N builders spends the allowance N times faster. Check: `resources.sh` (new, rule-shape) reads the sentence from `running-longer.md`.
- A builder's heartbeat is a change in its worktree. After 30 minutes with none the run asks it for its state; after 45 it stops the builder, keeps the work and counts an attempt. A piece is stopped at its wall-clock cap, two hours unless the contract says otherwise. Check: `resources-rehearsal.sh` ages the worktree's files with `touch -d` and drives the heartbeat check at 29, 31 and 46 minutes and at 121 minutes for the cap.
- Worktrees share one package store, the coordinator holds the one browser, a dev server runs only during a walk-through, and each builder runs at most two test workers. Check: `resources-rehearsal.sh` reads the environment the starter gives a builder (the package store variable and the test worker limit for Vitest, Jest, Node's runner and pytest) and finds no browser in the builder's resources; `kit-owns-worktrees-rehearsal.sh` holds that `worktree.sh` stops a dev server when the walk-through ends.
- The caps, reserve, thresholds, timeouts and model for each role are read from the project settings, then from the per-computer file `.agents/loop-settings.local.json`, which git ignores, then from the defaults in `resources.py`. Check: `resources-rehearsal.sh` sets each layer in turn and reads which value wins.
- The run record holds the current count, each change with its reason, the peak memory measured and each builder's last heartbeat, and nothing else is written to the issue. Check: `resources-rehearsal.sh` reads those four fields from the stand-in run record and finds no `gh` call in the stand-in GitHub log.
- `running-longer.md` says the builder count is the computer's suggestion, and that `at_once` in `.agents/loop-settings.json`, which slice 9 left as a fixed number with no question, now raises or lowers that suggestion within the hard cap. Check: `parallel-run.sh`, as slice 9 left it, extended to hold the new rule and to fail on a copy where `at_once` overrides the suggestion past six.
- WORKFLOW.md section 10 and section 5's paragraph on the plan say the run sizes itself to the computer, names the hard cap of six and the heavy rule, and no longer says the run asks. Check: `resources.sh` reads the new sentences and refuses the old "in Claude Code it asks before it starts".
- docs/COMPATIBILITY.md says memory pressure is read on Linux and macOS, and what happens elsewhere. Check: `resources.sh` reads the line.
- The root AGENTS.md describes `resources.sh` and `resources-rehearsal.sh`, and its paragraph on `parallel-run.sh` matches the rewritten check. Check: `validate-kit.sh`.

#### When it is not the normal case
- The computer gives no memory reading (an unknown system, or a reading that fails): the run suggests one builder, says why in one line, and carries on. Check: `resources-rehearsal.sh` with a missing memory file.
- Swap is already in use before the run starts: the suggestion counts swap use as pressure and starts at one builder lower. Check: `resources-rehearsal.sh`.
- A builder stopped under critical pressure had uncommitted work: the work stays in its worktree, the piece goes back to `queued` with no attempt counted, and `worktree.sh tidy` never removes that worktree. Check: `resources-rehearsal.sh` and `kit-owns-worktrees-rehearsal.sh`.
- The person asks for more than six: six, said once. Check: as above.
- The usage-limit message changes wording in a coding agent release: the stand-in output is a fixture file, and the rehearsal fails on the old fixture only when the matcher in `resources.py` is changed; the real wording is checked in slice 20: Replay harness rewrite and real runs. Check: `resources-rehearsal.sh` names its fixture.

## Masterplan change
Design note: "Crews" and "Computer resources" in docs/design/agentic-loop.md. The note leaves the reserve, the memory per builder, the thresholds and the timeouts to this piece; the defaults this slice writes (below) go into the note's "Settled when built" list as the starting values.

## Not in this piece
- The `Crew:` field, its default per loop module and the lint that checks shape, caps and reason: slice 3: Contract v2 and the ready-gate lint.
- Waves planned from `Depends on:` and `Boundary:`, the run record itself and the run statuses: slice 9: Run controller.
- The goal race in separate worktrees and the gauntlet's blind critics: slice 11: Goal loop module and slice 12: Gauntlet loop module, which use this slice's starter and comparison helper.
- The loop board's view of the count and heartbeats: slice 16: Boards and notifications.
- Measured memory per builder from real runs: slice 20: Replay harness rewrite and real runs.
- The same roles as Codex agents: slice 19: Codex parity.

## Decided
- Role definitions ship inside the `implement` skill and are placed into `.claude/agents/` by a script, because the shared installer and both plugins carry skills and nothing else, which is the same reason the plan helper ships inside a skill (decision 44).
- The default memory per builder is 2.5 GiB and the reserve is 4 GiB, until real runs measure it; the design leaves both to this piece. With those, a 15 GiB computer gets four builders at most only when nearly idle, and the run that froze such a computer with ten would have started at most four.
- Pressure thresholds: pressure when available memory falls under the reserve or swap grows by more than 512 MiB since the run began; critical under half the reserve. These are defaults in `resources.py`, overridden by settings (decision 45).
- On macOS the pressure reading comes from the `memory_pressure` command and `sysctl vm.swapusage`; on Linux from `/proc/meminfo` and `/proc/pressure/memory` where it exists. Another system gets the one-builder fallback.
- A run asks nothing (decision 3); slice 9 already removed the at-once question, and `at_once` in the settings is the person's standing cap on the computer's suggestion.
- A comparison runs in both orders and a split is no win, and a finding counts only when reproduced or tied to a failing check (decision 44).
- The heartbeat is a file change in the worktree, read from the newest modification time under the worktree with dependency and build folders left out, because Claude Code's own stall timeout misses a builder that reads without writing (decision 45, research "Crews and resources").

## Data
- Four role definition files in the project's `.claude/agents/`, written by the placement script and by nothing else; a definition the person edited (it no longer carries the kit's generated marker) is left alone and named.
- Per-computer settings in `.agents/loop-settings.local.json`, git-ignored, beside `.agents/loop-settings.json` (slice 7); it holds only numbers and model names, never a key.
- New run record fields (current count, count changes with reasons, peak memory, last heartbeat per builder) in the run record slice 9 writes, under the main folder's `.agents/runs/`, which git ignores.
- A project missing a role definition gets it from the placement step on the next run. No project founded with AI Build Kit is moved (decision 63).

## Leaves the tool
Nothing new leaves the tool, because the memory readings, heartbeats and settings stay on the computer and in the git-ignored run folder. Each crew member is a coding agent session and sends its inputs to the model's service, as every session already does; the critic now sends less than today's reviewer, since it receives only the contract and the diff.

## Must still hold
- The coordinating session alone claims, writes the run state, opens pull requests and merges; a builder never pushes. Check: `parallel-run.sh` (rewritten, keeps these rules) and `run-controller.sh`.
- Each piece in its own worktree under `.agents/worktrees/`, the main folder never switched, and `.env` linked never copied for work outside a run; from slice 15 on, a run's worktree carries no production secrets and gets no `.env` link at all. Check: `kit-owns-worktrees.sh`, `kit-owns-worktrees-rehearsal.sh`.
- The walk-through never takes another worker's browser. Check: `walk-through-eyes.sh`.
- The checks leave `.agents/worktrees/` out. Check: `check-floor.sh`.
- No issue numbers and no attribution lines in tracked files. Check: `validate-kit.sh`.
- The canonical skill inventory and generated adapters. Check: `validate-kit.sh`, `build-adapters.sh`.

## Relies on
- `implement/references/running-longer.md`, `implement/scripts/worktree.sh` (its `port` and `tidy` commands), `section-builder/SKILL.md` step 6: on main today.
- `section-builder/references/task-handoff.md` and `task-context-capabilities.md`, and the resource ownership rules in them: brought onto main from the overnight batch branch by slice 7; this slice adds the resource rules it needs.
- The `Crew:` field and the lint: slice 3. The builder statuses and the attempt notes the run controller builds: slice 7. The automatic reviewer that becomes the build critic: slice 8. The run record, the run controller and waves: slice 9.
- `.agents/tests/lib/rule-shape.sh` and the six layouts in `plan-helper-routes.sh`: on main today.

## Reach and risk
Boundary: the `implement` skill and its references and scripts, the `section-builder` skill's handoff references, the `setup-ai-build-kit` skill's placement step, WORKFLOW.md section 10 and the plan paragraph in section 5, docs/COMPATIBILITY.md, the root AGENTS.md checks list.
Reaches: worktrees and dev servers (`kit-owns-worktrees.sh`, `kit-owns-worktrees-rehearsal.sh`), the walk-through (`walk-through-eyes.sh`), the run (`run-controller.sh`, `parallel-run.sh`), plugin and installer layouts (`plan-helper-routes.sh`, `claude-plugin.sh`, `agent-plugin.sh`), the check floor (`check-floor.sh`).
If it breaks: a run starts too many builders and the computer slows or freezes; the person notices a stuck machine and stops the run from the loop board or by closing the session. Undone by reverting the slice's pull request; the run record keeps the work.
Depends on: 3, 7, 8, 9.
Loop module: build, because every rule here is a script's decision that a rehearsal can judge from stand-in readings.
Crew: default.

## Under the hood
Add `implement/scripts/resources.py` with `suggest`, `before-start`, `heartbeat` and `usage-limit` commands, reading stand-in paths from environment variables so the rehearsal never depends on the computer it runs on. Add the four role files under `implement/templates/agents/` and a placement step in `setup-ai-build-kit/scripts/bootstrap-project.sh`, reused by the run before it starts. Extend slice 9's run controller with a crew starter and a both-orders comparison helper. Extend `task-handoff.md` and `task-context-capabilities.md`, which slice 7 brought onto main, with the resource rules this slice needs; their resource ownership rules supply "one browser held by the coordinator". Extend `parallel-run.sh`, which slice 9 rewrote when the question went, and extend `kit-owns-worktrees-rehearsal.sh` (dev server stopped after the walk-through, worktree kept after a pressure stop). The test worker limit uses the runner settings `check-floor.md` already names. A canonical skill changes, so the pull request answers PHILOSOPHY's five questions; SOURCES.md credits MAST, the Google research on independent agents and Anthropic's multi-agent research post for small crews; adapters are rebuilt, the validator runs, prose goes through the humanizer, and no issue number appears.

## Evidence
Rule-shape checks (`crews.sh`, `resources.sh`, the rewritten `parallel-run.sh`) with every rule proved load-bearing; script rehearsals (`crews-rehearsal.sh`, `resources-rehearsal.sh`) run with stand-in readings and a stand-in agent command in throwaway folders. The memory each builder needs stays an estimate; slice 20 records the measured value.

## Size
Two sittings, as Part a (crews) and Part b (computer resources), each its own pull request; Part b does not need Part a.

## Consistency notes
- The run controller is `implement/scripts/run.py` from slice 9; "the run controller" here means that script, which starts every crew member. The settings are `.agents/loop-settings.json` (slice 7), with the per-computer layer `.agents/loop-settings.local.json` added here.
- `task-handoff.md` and `task-context-capabilities.md` are brought onto main once, by slice 7. This slice extends them and brings nothing over again.
- The at-once question goes in slice 9; this slice turns `at_once` into the person's cap on the computer's suggestion.
- The `.env` link: a run's worktree carries no production secrets from slice 15 on, so this slice's "Must still hold" keeps the link only for work outside a run.
