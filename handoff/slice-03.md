# Slice 3: A piece cannot turn ready until a machine has checked its contract and its bar

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script.

## So that
A person can leave a ready piece to be built with nobody there, knowing a script has already confirmed that its contract is complete, its bar fits its loop module, its acceptance checks fail on today's code for the right reason, and it says what it is allowed to change and what it reaches.

## Done when

Two parts, each its own pull request: part a writes contract v2 into the records and the form; part b builds the lint and puts it on the gate.

### Part a: contract v2

#### Works
- `references/pieces.md` (setup-ai-build-kit skill) adds four parts to the agent layer and names each one's rule:
  - `## Loop`, holding `Loop module: fix | build | goal | gauntlet` and the bar that module needs: for build, `Acceptance branch:` and the `Check:` on every Works line; for fix, `Reproduction:` naming the check that fails today and `Must not change:`; for goal, `Metric:`, `Measured by:` (a command), `Target:`, `Budget:`, `Guard checks:` and `Held-out check:`; for gauntlet, `Reference:` (a link that can be fetched, with the person's approval and its date), `Compared by:`, `Budget:` and `Guard checks:`.
  - `## Reach`, holding `Boundary:`, `Reaches:` (each area with the existing tests that guard it by name, or "no test covers it" and the acceptance check that guards it), `If it breaks:`, `Depends on:` and `Reach derived at:` (a commit). It replaces the one-line `Touches:`.
  - `Crew:`, written only where the crew differs from the loop module's default, as `Crew: <step> <width>, because <reason>`.
  - `## Needs from the computer`, holding `Heavy:`, `Dev server:`, `Browser:`, `Expected duration:` and `Cannot share:`.
  It also makes `## Not in this piece` required on every piece, and states the brief rules: behaviour rather than steps, interfaces rather than file paths or line numbers, and each acceptance criterion checkable on its own. Check: `.agents/tests/piece-contract.sh`, extended with a rule for each field and each brief rule, each proved load-bearing by `rs_guard`.
- `templates/foundation/piece-issue.yml` carries the new fields in the same order as `pieces.md`, with `Loop module` as a dropdown of the four modules, and drops the `Touches` field. Check: `piece-contract.sh`, the form's field order assertion updated.
- The printout `templates/foundation/plan-refresh.sh` builds `Go together` from `Boundary:` in place of `Touches:`, and no longer reads `Touches:`. Check: `.agents/tests/plan-printout.sh` and `.agents/tests/queue-groups.sh`, fixtures moved to `Boundary:`, and a fixture carrying only `Touches:` printed as having no boundary.
- `shape/references/readiness-check.md` changes three items and keeps the rest of the fixed list word for word: item 9 reads the `## Reach` fields in place of `Touches`; item 10 (refused phrases) moves to the lint and the item says "the lint has already refused these"; a new item asks the checker to match each acceptance check to the criterion it claims to test, and a check that tests something else is a BLOCKING gap. Check: `piece-contract.sh`, its stored copy of the list updated to the new wording and still compared word for word.
- WORKFLOW.md section 2's paragraph "A piece is written in two layers" names the loop module, the bar, the reach line the person reads ("This changes sign-in. It also reaches billing, which 14 checks guard. If it breaks, people cannot sign in, and a rollback undoes it.") and that the lint checks the rest. Check: `piece-contract.sh`, a rule on WORKFLOW.md for the loop module and the reach sentence.
- PHILOSOPHY.md's worked example "A piece written in two layers, added" names the loop module and the reach line among what the agent layer carries, keeping all five answers. Check: `.agents/tests/loop-first-ground.sh`, its `check_five` call on that example passes, and a new rule on "loop module" in it.
#### When it is not the normal case
- A piece with `Touches:` and no `## Loop`: the lint refuses it and names the missing parts, and `/shape` writes them, because AI Loop Kit carries no piece shaped under AI Build Kit's contract (decision 63). Check: `ready-lint-rehearsal.sh`, a fixture with `Touches:` only.
- A field that does not apply, such as `Must not change:` on a build piece: the field is absent, never written with "none", because the lint reads the module to know which fields it needs. Check: `ready-lint-rehearsal.sh` in part b.

### Part b: the ready-gate lint

#### Works
- `.agents/skills/shape/scripts/ready-lint.py <number>` reads the issue through the GitHub command-line tool and the project's checkout, prints one line ("Ready-gate lint: no gaps on <title>.") and exits 0 when every rule below holds, and otherwise lists each gap with the next action and exits 1. Check: new `.agents/tests/ready-lint-rehearsal.sh`, run in throwaway repositories against the stand-in GitHub `.agents/tests/replay/fake-github/gh`, with one fixture piece for each rule that passes and one that fails it.
- Required sections: the header, the agent layer, `## Loop`, `## Reach` and `## Not in this piece` are present and non-empty. Check: `ready-lint-rehearsal.sh`.
- The bar fits the module: exactly one `loop:` label, matching `Loop module:`; every field that module needs is present; a goal's and a gauntlet's `Budget:` carry a number and a unit (attempts, minutes or tokens); a gauntlet's `Reference:` is a link and names the date the person approved it. Check: `ready-lint-rehearsal.sh`, one fixture per module.
- Reach fields: all five present; every test a `Reaches:` line names exists on `origin/main`; every "no test covers it" line names an acceptance check from the piece; `Reach derived at:` is a commit `origin/main` contains; the pieces under `Depends on:` match the issue's blocked-by links and form no cycle. Check: `ready-lint-rehearsal.sh`, including a three-piece cycle through the stand-in's blocked-by links.
- Sensitive areas: an area the masterplan's build-path section names as sensitive that appears under `Boundary:` or `Reaches:` has an `Accepted:` line or a caution marked done in that section. Check: `ready-lint-rehearsal.sh`, with a Build with care masterplan fixture.
- Crew: absent, or a known step from the design note's crew table with a width within its cap and a reason after "because"; a crew with two writers is refused. Check: `ready-lint-rehearsal.sh`.
- Refused phrases: every phrase item 10 of today's readiness check refuses, moved into the lint word for word as one list, plus a count or size word with no number, is refused anywhere outside `Original report`, `## Kickback` history and code spans. Check: `ready-lint-rehearsal.sh`, one fixture per phrase, read from the same list the lint uses.
- Brief rules: no line number anywhere (`line 12`, `file.py:12`); no file path outside `Reaches:`, `Check:`, `Reproduction:`, `Measured by:`, `Guard checks:` and `Held-out check:`; no numbered list of build steps; every Works line names its own `Check:`. Check: `ready-lint-rehearsal.sh`.
- Length limit per type, counting the body's lines without `## Readiness`, `## Kickback` history and `Original report`: `type:chore` 80 lines, `type:bug` 120, `type:feature` 250. Check: `ready-lint-rehearsal.sh`, a fixture one line over each limit and one at it.
- Checks fail on their assertion: for a build or fix piece, the lint checks out the `Acceptance branch:` (or the branch holding `Reproduction:`) in a temporary folder, refuses it when it changes anything other than test files against `origin/main`, runs each named check with the project's test command from AGENTS.md's stack section, and requires each to fail with an assertion failure. For pytest, Vitest, Jest and Node's own test runner it reads the runner's JUnit or JSON report and refuses a failure that is a collection error, a failed import, a missing module, a syntax error or a name that does not exist, naming the check and the error. Check: `ready-lint-rehearsal.sh`, a pytest project and a Node test-runner project, each with one check failing on its assertion (passes), one failing on a missing import (refused), one passing on main (refused) and a spec branch that also changes source code (refused).
- The gate uses it: `gate.py move <n> state:ready` from `shaping:check` refuses unless the lint exits 0, the `## Readiness` section says Ready, and a `loop:` label is set; the refusal prints the lint's gaps. Check: `.agents/tests/gate-script.sh`, the `shaping:check` row extended.
- `/shape` runs the lint before starting the fresh checker, so the checker never reads a piece the lint would refuse, and reports the lint's result in one line. Check: `piece-contract.sh`, a rule in `shape/SKILL.md`, proved load-bearing.
- AGENTS.md (root) describes `ready-lint-rehearsal.sh` in the maintainer checks list and the changed `piece-contract.sh` entry. Check: guided check: the maintainer reads both entries against the rehearsals' rule lists; `validate-kit.sh` passes.
#### When it is not the normal case
- The project's test runner is not one of the four the lint can read: the lint counts a non-zero exit as failing, writes a NOTE that it could not tell an assertion from an error, and the fresh checker reads the check's output for that item. Check: `ready-lint-rehearsal.sh`, a project with a runner named only by a shell command.
- The project has no code yet (founding, first pieces): checks that need the checkout or `origin/main` say "no code yet" and pass, and the acceptance branch rule applies from the first piece that has code to fail against. Check: `ready-lint-rehearsal.sh`, an empty repository fixture.
- GitHub cannot be reached: the lint exits 2, changes nothing and says so in one line; the gate treats exit 2 as a refusal. Check: `ready-lint-rehearsal.sh`.
- A check hangs: each run has a ten-minute limit, after which the lint stops it and refuses the piece naming the check. Check: `ready-lint-rehearsal.sh`, with a check that sleeps past a lowered limit.
- The temporary checkout cannot be made (disk full): the lint says so, exits 2 and leaves nothing behind. Check: `ready-lint-rehearsal.sh`.

## Masterplan change
Design note: realises "The piece contract", the contract fields of "Reach and risk", "Loop modules" (the bar column), the `Crew:` field rules of "Crews", the piece's numbers in "Computer resources", the "fail on their assertion" paragraph of "The frozen bar", and the row "The ready gate" of "What a machine enforces" in `docs/design/agentic-loop.md`. The note leaves the length limit per type to the piece that builds it; this slice settles it at 80, 120 and 250 lines, and the note's "Settled when built" list gains those three numbers.

## Not in this piece
- Writing the acceptance checks on a spec branch, and choosing the loop module in shaping: slice 4: shaping sub-states in /shape.
- Checking every `Boundary:` area against a whole-project area map, and working the reach out again on today's `main`: slice 5: area map for the whole project.
- The contract hash recorded at ready and the diff guard during the build: slice 6: frozen-bar enforcement.
- Starting the crew a piece names, and reading `## Needs from the computer` to size a run: slice 10: crews and computer resources.
- The `## Learned` section a piece gains after its build, and the lint's rule that it is never required at ready and never counted in the length limit: slice 17: /maintain absorbs /sync.
- The optional `Keep when better by:` line on a goal piece: slice 11: Goal loop module, which extends this slice's field list and lint.
- The `Smoke:` line that names the paths a preview smoke test requests: slice 13: Merge policy, which extends this slice's field list and lint.
- The saved copy of a gauntlet's reference and its hash: slice 12: Gauntlet loop module, which extends the gauntlet bar and the lint.
- Checking that every area under `Boundary:` and `Reaches:` exists in the area map, and reading sensitive areas through the map: slice 5: Area map for the whole project, which extends this lint.
- Renaming `## Masterplan change` to `## Behaviour change` with its entry format: slice 18: Compact masterplan and behaviour deltas.

## Decided
- The lint is a script and the fresh checker stays a session, because a machine can count fields and run checks, and only a reader can tell whether a check tests the criterion it claims (decisions 6 and 46).
- The refused phrases move from the checker's list into the lint, because a phrase match is a machine's job and the checker's list stays fixed.
- Length limits are 80 lines for a chore, 120 for a bug and 250 for a feature, because a bug carries a reproduction in place of most of a feature's agent layer and a chore changes no behaviour a person sees. They are starting defaults, and the real runs in slice 20: replay harness rewrite and real runs measure them (design note, "Settled when built").
- File paths are allowed only in the fields that name a check or a test, because those name interfaces of the bar, and anywhere else a path is a step the builder should choose.
- An acceptance branch carries test files only, so the bar is the only thing shaping commits.
- The lint reads failure kinds for pytest, Vitest, Jest and Node's own test runner, the runners `check-floor.md` already names; any other runner falls back to the exit code with a note, so a project on another runner is never stopped.
- A ten-minute limit for each check run at the gate, because a check that runs longer at the gate runs as long in every attempt of the loop.
- `Touches:` is dropped rather than read beside `Boundary:`, because AI Loop Kit is for new projects and has no older pieces to honour (decision 63).

## Data
- The issue body gains the four new parts. Only `/shape` and a person write them; the lint only reads.
- The lint writes nothing to the project. Its temporary checkout lives in a folder `mktemp -d` makes, and is removed with `git worktree remove` when the lint ends, never by a recursive delete.
- No move for projects founded with AI Build Kit (decision 63). A piece without the new parts is refused by the lint until `/shape` writes them.

## Leaves the tool
Nothing new leaves the tool. The lint reads issues and links from GitHub through the command-line tool already signed in, and writes nothing there; the gate's label move is slice 2's.

## Must still hold
- The fixed readiness list, compared word for word with a stored copy (`piece-contract.sh`).
- The readiness check runs in a session that did not shape the piece (`piece-contract.sh`).
- Checks written first fail on today's code (`checks-first.sh`), and universal test-first stays rejected (`loop-first-ground.sh`).
- The printout's grouping guarantee for `/queue` (`plan-printout.sh`, `queue-groups.sh`).
- A recursive delete is never used to clear a folder (`refused-commands.sh`).
- No issue numbers in tracked files (`validate-kit.sh`).

## Relies on
- `gate.py`, its `shaping:check` row and `gate-script.sh`, produced by slice 2: label model and gate script.
- `references/pieces.md`, `templates/foundation/piece-issue.yml`, `templates/foundation/plan-refresh.sh`, `references/check-floor.md` (setup-ai-build-kit skill), `shape/references/readiness-check.md` and `shape/SKILL.md`, on main today.
- The stand-in GitHub's blocked-by links (`.agents/tests/replay/fake-github/gh`), on main today.
- pytest and Node, used by `check-floor-rehearsal.sh` on the hosted check today.

## Reach and risk
Boundary: the shape skill (SKILL.md, readiness-check.md, a new lint script), the setup-ai-build-kit skill's pieces.md, piece form and printout, the gate script's ready condition, WORKFLOW.md section 2, PHILOSOPHY.md's two-layer example, root AGENTS.md's maintainer checks.
Reaches: the readiness check and founding's use of it (`piece-contract.sh`, `starter-rehearsal.sh`); `/queue`'s groups (`queue-groups.sh`, `plan-printout.sh`); checks written first in section-builder (`checks-first.sh`); the run's claim of an unchecked piece (`the-runner.sh`).
If it breaks: no piece can turn ready, or a weak piece turns ready. The person sees the first at once as a refusal in `/shape`; the second shows as a kickback during a build. Reverting part b takes the lint off the gate and leaves the contract fields in place.
Depends on: 2.
Loop module: build, because every rule is a script behaviour a rehearsal can pass or fail.
Crew: default for the module.

## Under the hood
Part a is prose and form changes; write the new `piece-contract.sh` rules first and see them fail. Part b writes `ready-lint-rehearsal.sh` first, with fixture issues in the stand-in GitHub's state file and throwaway repositories holding a pytest project and a Node test-runner project, then `ready-lint.py`. The lint keeps one table of required fields per module, one table of the crew shapes and caps copied from the design note, and one table of how each runner reports a failure kind. The gate calls the lint as a subprocess and passes its output through.

Nothing is reused from the overnight batch branch.

Existing rehearsals expected to change: `piece-contract.sh` (fields, form, readiness list stored copy), `plan-printout.sh` and `queue-groups.sh` (`Boundary:` in place of `Touches:`), `piece-contract.sh` (the rule that a piece shaped before the readiness check stays ready goes), `gate-script.sh` (ready condition), `loop-first-ground.sh` (two-layer example). New: `ready-lint-rehearsal.sh`.

The kit's own rules: answer the five questions in PHILOSOPHY.md in each pull request (fits under /shape; the person sees one line saying the lint passed or the gaps it found; "a machine checks the piece before a person or agent judges it"; when it goes wrong they answer the gap in /shape; they never need to learn the rules the lint holds); credit the brief rules (mattpocock/skills) and the requirement-scenario idea (OpenSpec) in `docs/SOURCES.md`; regenerate adapters if the shape skill's description changes; run `validate-kit.sh`; humanizer on prose; no issue numbers.

## Evidence
A script run in throwaway repositories against the stand-in GitHub (`ready-lint-rehearsal.sh`), covering every lint rule in both directions and two real test runners; rule-shape rehearsals with load-bearing checks for the prose (`piece-contract.sh`); the gate's ready row (`gate-script.sh`).

## Size
Two sittings: part a (contract v2 in the records and form), part b (the lint and the gate).

## Consistency notes
- The ready-gate lint is this slice's, and its rule that every area under `Boundary:` and `Reaches:` exists in the map belongs to slice 5: Area map for the whole project, which builds the map. Until slice 5 lands, this slice's sensitive-area rule reads the masterplan's build-path section; slice 5 replaces that reading with `area-map.py`.
- One owner for each contract field. This slice owns every field listed under part a. Later slices extend the list and the lint, each owning its own field: `Keep when better by:` (slice 11: Goal loop module), the gauntlet's saved reference copy and hash (slice 12: Gauntlet loop module), `Smoke:` (slice 13: Merge policy), `## Learned` (slice 17: /maintain absorbs /sync), and `## Behaviour change` in place of `## Masterplan change` (slice 18: Compact masterplan and behaviour deltas).
- AI Loop Kit carries no piece shaped under AI Build Kit's contract (decision 63), so `Touches:` is dropped rather than read on older pieces, and the old "shaped before the readiness check" rule goes.
