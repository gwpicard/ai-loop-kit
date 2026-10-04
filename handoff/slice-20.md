# Slice 20: The maintainer can replay the v1 kit end to end and show a recorded real run for every loop module and every recipe

Labels (today's set): enhancement, area:tests, ready-able once shaped. Release label for the PR: release-patch, because the harness and its records stay in this repository and only the recipes' `## Proven` sections ship.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 4: Shaping sub-states in /shape; slice 7: Build and fix loop modules; slice 8: Automatic reviewer; slice 9: Run controller; slice 11: Goal loop module; slice 12: Gauntlet loop module; slice 13: Merge policy; slice 14: /deploy replacing /ship; slice 15: Safety boundary for runs; slice 16: Boards and notifications; slice 17: /maintain absorbs /sync; slice 18: Compact masterplan and behaviour deltas.

## So that
Before v1 is released, the maintainer can see measured evidence that the new model holds: a replay rate for each v1 behaviour on a fixture that speaks the v1 labels, and one recorded real run for each loop module and each recipe.

## Done when

### Works

Part a: the harness speaks v1
- The fixture's `issues.json` carries only v1 labels: every open issue has exactly one `state:` label, a `state:shaping` issue has exactly one `shaping:` sub-label, and every issue past `shaping:raw` has a `type:` label; no `idea`, `parked`, `building`, `to check`, `ready` or `needs-` label remains. Check: `.agents/tests/replay-state.sh` gains an assertion that reads the fixture and fails on a copy carrying one old label.
- The GitHub stand-in answers what v1 calls: blocked-by links through the issue dependencies endpoint, sub-issue links, `gh pr merge --auto`, a read of branch protection and rulesets that answers "protected" or "not protected" from the state file, and `gh release create`. Each unmodelled call is still refused. Check: `.agents/tests/fake-github.sh`, one case per call and one refusal case.
- The host stand-in builds a preview for each pushed branch with its own throwaway database, answers a health check at the live address, and records a rollback after a failed health check. Check: `.agents/tests/fake-host.sh`.
- `state-check.sh` grades the v1 world: one state and one sub-label per open issue; every label change in the GitHub log came from the gate script's own log line; a kicked-back piece carries a `## Kickback` section and keeps its branch on the remote; the run record lists every piece with a status from the six piece statuses and one of the six run statuses; nothing under the run record's folder is committed. Each assertion fails on a hand-built wrong end. Check: `.agents/tests/replay-state.sh`, one wrong end per assertion.
- `scenarios.md` describes only v1 behaviour: no scenario expects `/fix`, `/queue`, `/sync` or `/ship`, or a `parked` or `needs-` label, and each retired scenario is listed by number and title under a "Retired at v1" heading with the reason. Check: `.agents/tests/replay/check-parser.sh` fails on a scenario naming a removed command or an old label, and `.agents/tests/empty-fields.sh` still passes.

Part b: one replayed scenario for each v1 behaviour
- A wired case exists, with its contract in `scenarios.md`, for each of: a `loop:fix` piece whose fix fails three times and goes back to `shaping:research` (scenario 8 rewritten); a `loop:build` run of one that ends `state:in-review` with fresh evidence; a `loop:goal` piece that misses its target and ends `review:person` with its best result; a `loop:gauntlet` piece judged by a blind critic in both orders; a run of three pieces that integrates two and kicks back one (scenario 57 rewritten); a piece the ready gate refuses; a builder status of environment failed that pauses the run and kicks nothing back; and `/deploy` on each recipe (scenario 54 rewritten for the Vercel recipe, a new case for the Coolify recipe with the companion's checks read back). Check: `.agents/tests/replay/check-parser.sh` reads every new contract, and `.agents/tests/gated-turns.sh` runs each new preparation script on a throwaway project and refuses a folder that is not a fresh replay project.
- The rollup reports, for each model, whether a scenario held on every one of its runs, beside the rate. Check: `.agents/tests/held-definition.sh` drives `rollup.sh` with hand-built graded runs, one set that held every time and one that held four times in five.
- `baseline.md` opens with a v1 baseline: every wired case run five times on the same kit commit, driven and graded by named models, with the date; the pre-v1 tables sit under a "Before v1" heading as history. Check: `.agents/tests/compatibility-grades.sh` still finds Claude Code named in `baseline.md`, and a guided check: the maintainer reads the v1 table and finds every wired case in it.

Part c: recorded real runs
- `.agents/tests/real-runs.md` records one real run for each loop module (fix, build, goal, gauntlet) on a throwaway project with a real GitHub repository, each with the date, the kit commit, the coding agent and model, the piece's contract, the run record's final statuses, the attempts used and what the person saw on the boards. Check: new `.agents/tests/real-runs.sh`, which fails while any loop module has no dated entry, on a date in the future, and on an entry missing a field.
- Each recipe's `## Proven` section records a real `/deploy`: pipeline set up, a preview built from a branch with its own seeded database, the health check answered, a rollback run and checked. The line that previews keep off live data is stated as proven or not proven, by name. Check: `.agents/tests/recipe-nextjs-supabase-on-vercel.sh` and `.agents/tests/recipe-nextjs-supabase-on-coolify.sh` require the dated `/deploy` real run that slice 14 Part d records, and either a `Previews keep their own data:` line with its date or a sentence saying the run did not prove it.

Documents this slice touches
- `.agents/tests/replay/README.md` describes the v1 fixture, the new cases and the per-model "held on every run" line. Check: `.agents/tests/held-definition.sh` reads the README for the per-model line.
- `docs/MAINTAINING.md`, sections "Scenario review" and "Maintainer validation", name the v1 scenarios and `real-runs.md`. Check: new rule in `.agents/tests/real-runs.sh` reading MAINTAINING.md.
- Root `AGENTS.md` maintainer-checks entries for `replay-state.sh`, `gated-turns.sh`, `fake-github.sh`, `fake-host.sh` and `held-definition.sh` describe the v1 assertions, and a new entry describes `real-runs.sh`. Check: guided check against the files' own header comments; slice 21 then makes the list tell one story.

### When it is not the normal case
- A real run fails partway, for example the coding agent stops or the host refuses a deploy: the run is recorded as it happened, with what failed, and does not count towards its loop module until a later run completes. Check: `.agents/tests/real-runs.sh` refuses an entry marked failed as the module's only run.
- A preview on a recipe shares a database with another preview or with production in the real run: the recipe carries no `Previews keep their own data:` line, and automatic merge stays off for that recipe as slice 13: Merge policy defines. Check: the recipe rehearsal fails on a recipe carrying the line while its run notes say shared.
- The real GitHub command answers inside a replay: the run is written as not graded, as today. Check: `.agents/tests/replay-provider.sh`, unchanged.
- A model upgrade lands between Part b and the v1 baseline: the baseline is taken again on one model pair; two pairs are never mixed in one table. Check: guided check of `baseline.md`'s header.

## Masterplan change
Design note: "Learning and code health" (the replay harness reports, for each model, whether a scenario passes on every one of several clean runs) and "1.0" (real runs recorded, one for each loop module, and one `/deploy` for each recipe). No change to the note.

## Not in this piece
- The behaviour each scenario measures: built in slices 4, 7 to 9 and 11 to 18; this slice measures it.
- A Codex replay pass and the Codex grade: slice 19: Codex parity keeps Codex at expected to work until a recorded run, and that run is not a 1.0 condition.
- The pre-release run as a person: slice 23: Release v1.0.
- Rewriting WORKFLOW.md, the README and COMPATIBILITY.md around the new evidence: slice 21: Documentation sweep.

## Decided
- The harness is rewritten in place, not replaced: `run.sh`, `turn-gate.sh`, `provider.sh`, the grader and the isolation stay, because they work and their rules are already guarded (decision 24 reuses what works).
- Each loop module gets one replayed case and one real run, and each recipe one real `/deploy` (decision 26).
- The rollup's "held on every run, per model" line sits beside the rate rather than replacing it, since the rate is what finds an unreliable case (design note, "Learning and code health").
- Real runs are recorded in `.agents/tests/real-runs.md`, apart from `baseline.md`, because a real run is a single dated account and the baseline is a rate.
- Retired scenarios keep their numbers; a new scenario takes the next free number, so old results stay comparable by number.
- A failed health check in a replay is answered by the host stand-in, never by a real host.

## Data
- `.agents/tests/replay/fixture/issues.json` moves to v1 labels; the replay copies it into each throwaway project, nothing else writes it.
- `.agents/tests/replay/fake-github/` and `fake-host/` state files gain blocked-by links, protection, previews with their own databases and health answers; they live beside each throwaway project, as today.
- New `.agents/tests/real-runs.md`, written by the maintainer only, never shipped (absent from `release-manifest.txt`).
- Recipe `## Proven` sections carry slice 14's `/deploy` run and, where proven, the `Previews keep their own data:` line; they ship.
- No founded project's data changes.

## Leaves the tool
The replay never leaves the computer: its remote is a bare repository next door and its GitHub is a stand-in, as today. The real runs in Part c create a throwaway GitHub repository, a host project and a database on the maintainer's own accounts; each is torn down afterwards and the teardown is recorded in `real-runs.md`. Model calls go to the coding agent's own service, as today.

## Must still hold
- The replay never writes inside this repository and never reaches a signed-in GitHub account. Check: `.agents/tests/replay-provider.sh`.
- A gated turn can cost a filler but never holds a line back for good. Check: `.agents/tests/gated-turns.sh`.
- `scenarios.md` keeps exactly two words for an empty field. Check: `.agents/tests/empty-fields.sh` and `check-parser.sh`.
- The validator's quiet-onboarding and interview-shape needles in `scenarios.md` (scenarios 25 and 26). Check: `.agents/tools/validate-kit.sh`.
- No issue numbers and no attribution lines in any tracked file, the real-run record included. Check: `.agents/tools/validate-kit.sh`.
- No product named outside a recipe and the README. Check: `.agents/tests/hosting-request.sh`.

## Relies on
- `.agents/tests/replay/` as it stands on `main`: `run.sh`, `state-check.sh`, `turn-gate.sh`, `rollup.sh`, `fake-github/gh`, `fake-host/`, `prepare/`, `cases/` (confirmed present).
- The gate script, labels and run record from slice 2: Label model and gate script and slice 9: Run controller.
- The loop modules from slices 7, 11 and 12, the reviewer from slice 8, `/deploy` and the preview fields from slice 14, the boards from slice 16.

## Reach and risk
Boundary: the replay harness, the scenario contract, the recipe proven sections, the maintainer notes on validation.
Reaches: the validator's scenario needles (`validate-kit.sh`); the recipe format (`recipes.sh`, `check-recipes.sh`); the compatibility grades (`compatibility-grades.sh`); the held definition (`held-definition.sh`).
If it breaks: the maintainer sees a replay that cannot grade, or a rehearsal that fails in `run-all.sh`; the slice's pull request is reverted and the harness returns to the pre-v1 cases, which grade a kit that no longer exists, so the release waits.
Depends on: 4, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18.
Loop module: build, because every Part a and Part b line is a rehearsal that fails today and passes after; Part c is evidence the maintainer gathers.
Crew: default for build. Part c is listed under "Waiting on you" in the piece, because a real run needs the maintainer's accounts and the person present at a deploy.

## Under the hood
Part a rewrites `fixture/issues.json` (the three waiting pieces become `shaping:research`, `shaping:clarify` and `shaping:prototype`; the open building piece becomes `state:building`; the two parked ideas become closed not planned), extends `fake-github/gh` and `fake-host/_common.sh`, and replaces the per-scenario assertions in `state-check.sh` that test `/ship`, `parked` and the first upload's old route with v1 invariants read from the run record and the gate log. `prepare/` scripts for scenarios 52, 53, 54 and 57 are rewritten for v1; `one-recipe-menu.sh` and `long-instructions.sh` stay. Part b adds cases under `cases/` and contracts in `scenarios.md`, then runs the suite and writes the v1 baseline. Part c is run by the maintainer with the recorded steps.

Existing rehearsals expected to change: `replay-state.sh`, `gated-turns.sh`, `fake-github.sh`, `fake-host.sh`, `held-definition.sh`, `check-parser.sh`, `compatibility-grades.sh`, both recipe rehearsals. Reused from `main`: the whole isolation layer and the grader. Nothing is taken from the overnight batch branch.

Kit rules: no canonical skill changes here, so the five questions do not apply; the validator and `run-all.sh` pass; the humanizer and house rules apply to every prose file touched; no issue numbers; `docs/SOURCES.md` credits pass^k reporting to its source if it came from outside work (the research note's "Verification and code health" section names it).

## Evidence
Rehearsals with hand-built end states for every new assertion, each proved to fail on a wrong end; a whole replay pass recorded in `baseline.md`; dated real runs in `real-runs.md` and in each recipe's `## Proven` section.

## Size
Three sittings, split as above: Part a (one sitting), Part b (one sitting plus the replay pass, about two hours of model time), Part c (one sitting of the maintainer's time per real run, six runs in all).

## Consistency notes
- The recipe line is `Previews keep their own data:`, defined by slice 13 and written by slice 14's real runs; the draft's "Preview data:" wording now uses that name.
- The `/deploy` real run for each recipe is slice 14 Part d's; this slice counts it and does not run it again (slice 14, Decided).
- The run record is `.agents/runs/<run name>/run.json` and the gate script is `gate.py`, whose own log line `state-check.sh` reads.
- The rehearsal that replaced `the-runner.sh` is slice 9's `run-controller.sh`.
