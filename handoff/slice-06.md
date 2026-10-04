# Slice 6: The bar a piece is built against cannot be changed by the builder, and "done" needs fresh proof

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 5: Area map for the whole project, kept by the project check.

## So that
A green result on a piece means the checks agreed before the build passed on the code as it now stands, because the builder could neither weaken them nor claim a pass it did not show.

## Done when

### Part a: the contract hash and the wider diff guard

#### Works
- When the gate script moves a piece to `state:ready`, it posts one bookkeeping comment on the issue, `<!-- loop:contract sha256=<hash> commit=<spec commit> -->`, where the hash covers the contract body with the sections the system writes later left out (`## Kickback`, `## Readiness`, `## Learned`) and the comment markers themselves. Check: new `.agents/tests/frozen-bar-rehearsal.sh` drives the gate against the replay harness's stand-in GitHub (`replay/fake-github`) and reads the comment.
- `gate.py check-contract <number>` recomputes the hash; a piece in `state:building` whose contract changed is moved by the gate to `shaping:spec` with a `## Kickback` section saying "The contract changed while it was being built", and its branch is kept. section-builder runs it at the start of every attempt and the gate runs it again before `state:in-review`. Check: `frozen-bar-rehearsal.sh` edits the stand-in issue body mid-build and reads the kickback; a control edit to the `## Kickback` section alone passes.
- A new section-builder script, `scripts/bar-guard.sh <base> <piece-file> <spec-commit>`, lists every change since the base in seven kinds, one line each with its kind: an acceptance check (any file the spec commit added) edited or deleted; an existing test edited, deleted or moved (today's `test-guard.sh` rule); a skip or focus marker added to a test (`.skip(`, `xit(`, `it.only(`, `@pytest.mark.skip`, `t.Skip(`, `@unittest.skip`); a lint or type suppression added (`eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `# type: ignore`, `# noqa`, `# pylint: disable`, `//nolint`); a change to a test, lint, type-check or coverage tool's settings file (`jest.config.*`, `vitest.config.*`, `eslint.config.*`, `.eslintrc*`, `tsconfig*.json`, `.coveragerc`, `setup.cfg`, `pyproject.toml`, `ruff.toml`, `mypy.ini`); an updated snapshot (`__snapshots__/`, `*.snap`); and a change to the project check, any CI workflow, the hooks or the deny rules (`.github/workflows/`, `.agents/hooks/`, `.githooks/`, `.husky/`, `.claude/settings.json`). It exits 0 when nothing is listed, 1 when something is, 2 when it cannot run. Check: new `.agents/tests/bar-guard-rehearsal.sh` makes one change of each kind in a throwaway repository and reads the kind named, with a clean control.
- A listed change the contract does not name is refused: the gate will not move the piece to `state:in-review`, and its refusal names each file and says to put it back. A listed change the contract names, in the same place `test-guard.sh` reads today, passes the guard and forces `review:person`, with the reason recorded. Check: `frozen-bar-rehearsal.sh`, one refused and one named case.
- The gate reads `area-map.py which` (slice 5) on every changed path; a path outside the areas the piece's `Boundary:` names forces `review:person` with the path and its area as the reason, and never refuses. Check: `frozen-bar-rehearsal.sh`.

#### When it is not the normal case
- GitHub cannot be reached when the hash is posted or read: the gate refuses the transition and says GitHub could not be reached, never treating a missing hash as unchanged. Check: `frozen-bar-rehearsal.sh` with the stand-in switched off.
- A contract with no hash comment (made ready before this slice): `check-contract` records the hash now and says so in one line, so older ready pieces stay buildable. Check: `frozen-bar-rehearsal.sh`.
- A suppression, skip marker or settings change that only removes text (a suppression taken out): not listed. Check: `bar-guard-rehearsal.sh` control.
- A file renamed away from a test path: listed under its old path with its new path on standard error, as `test-guard.sh` does today. Check: `bar-guard-rehearsal.sh`.

### Part b: the evidence record and the Stop hook

#### Works
- `gate.py evidence <number> -- <command>` runs the command itself in the piece's worktree and appends one line to `.agents/pieces/<number>/evidence.jsonl` in the main folder: the command, its exit code, the commit, whether the tree was clean, the time and the phase (`before` or `after`). Only the gate writes the file. Check: `frozen-bar-rehearsal.sh` reads the record.
- Before moving a piece to `state:in-review`, the gate itself runs, on the current commit with a clean tree: every acceptance check, every guard check named under `Reaches:`, and the project check's commands from AGENTS.md's stack section; for `loop:build` and `loop:fix` it also runs each acceptance check at the spec commit and requires it to fail. Any check missing, failing, or run on another commit or a dirty tree is a refusal naming the check and the next action. The builder's own statement counts for nothing. Check: `frozen-bar-rehearsal.sh`: a builder claiming done with one check red is refused; a passing piece moves.
- The founded `claude-settings.json` gains `Stop` and `SubagentStop` hooks that run `gate.py stop-check`. In a worktree whose branch belongs to a piece in `state:building`, it reads the builder's result file; where the status is `done` and a check fails, it exits 2 with one line naming the failing check, so the builder carries on; where the status is any other, or `stop_hook_active` is set and the attempt's limit is reached, it lets the session stop. Anywhere else it prints nothing and exits 0. Check: new `.agents/tests/stop-hook.sh` feeds `stop-check` the hook's JSON input in throwaway worktrees for each case.
- The gate and the hook stop the agent writing `.agents/pieces/` directly: the deny rules refuse `Write` and `Edit` on that folder, and the gate rejects a record whose lines it did not write (each line carries a hash chained to the previous one). Check: `push-to-main-rules.sh`'s shared matcher (`lib/permission-matcher.py`) fed the new rules; `frozen-bar-rehearsal.sh` hand-edits a line and reads the refusal.

#### When it is not the normal case
- An acceptance check that fails at the spec commit on an error rather than its assertion (a failed import, a missing file): the gate refuses `before` evidence and names it, matching the ready-gate rule from slice 3. Check: `frozen-bar-rehearsal.sh` with a check that fails on import.
- A check that passes only on a retry: recorded as a failure, never as a pass. Check: `frozen-bar-rehearsal.sh` with a check that fails then passes.
- The hook runs in this repository: it does nothing, since this repository's `.claude/settings.json` carries no Stop hook. Check: `session-start.sh` extended to assert the maintainer settings carry neither hook.
- A coding agent with no Stop hook: the gate's own run of the checks before `state:in-review` still holds the rule; COMPATIBILITY.md says the hook is Claude Code's and Codex follows in slice 19. Check: `compatibility-grades.sh` rule for the sentence.

### Part c: the checks are tested once the build is green

#### Works
- After every acceptance check passes, where a local runner exists for the project's language, the build breaks the code this piece changed on purpose, following `references/test-strength.md`, without offering first and on every build path; an acceptance check that fails on none of the breakages of the code it claims to cover forces `review:person`, naming the check. Check: `test-strength.sh` rewritten for the new rule; `test-strength-rehearsal.sh` extended with an acceptance check that misses a boundary error and reads the forcing reason.
- Where no runner exists, the piece's "what I could not check" says the checks were not tested by breaking the code, and nothing is forced. Check: `test-strength-rehearsal.sh` with no runner.

### Documents, every part
- section-builder's SKILL.md step 4 (acceptance checks come from the spec and are never written by the builder) and step 8 (`bar-guard.sh` and the gate's evidence replace the builder running `test-guard.sh` itself). Check: `checks-first.sh`, updated.
- WORKFLOW.md section 6, "Evidence": the bar is fixed at ready, what the guard refuses, what forces your review, and that "done" is the gate running the checks. Check: `frozen-bar.sh`, a new rule-shape rehearsal.
- The founded `blocked-commands.md`: a command the deny rules refuse on `.agents/pieces/` is told to the person, never worked round. Check: `refused-commands.sh`.
- `docs/COMPATIBILITY.md`, "Optional harness features": the Stop hook. Check: `frozen-bar.sh`.
- Root `AGENTS.md` names each new rehearsal. Check: `validate-kit.sh`.

## Masterplan change
Design note: "The frozen bar", and the rows "The frozen bar" and "Fresh evidence" in "What a machine enforces". The note needs two sentences: that the contract hash leaves out the sections the system writes during a build, and that test-strength runs without an offer once the build is green.

## Not in this piece
- Acceptance checks failing on their assertion at the ready gate, and the checker matching checks to criteria: slice 3: Contract v2 and the ready-gate lint.
- The builder's statuses and the attempt note built from the evidence record: slice 7: Build and fix loop modules.
- The automatic review and how `review:auto` or `review:person` is finally chosen: slice 8: Automatic reviewer.
- The secret scan in the gate: slice 15: Safety boundary for runs.
- The same checks as Codex hooks: slice 19: Codex parity.

## Decided
- The hash is posted on the issue as a bookkeeping comment rather than kept on this computer, so a run on another computer reads the same bar. Bookkeeping on the project's own issue needs no yes (`speaks-for-the-person.sh`). (Decision 28.)
- The gate runs the checks itself rather than trusting the record, so a forged line proves nothing; the record is the output the boards and slice 7's attempt note read. (Decisions 28 and 46.)
- A listed change the contract does not name is put back, as `test-guard.sh` does today; one the contract names goes to the person. That keeps today's naming rule and adds the person where the design says "forced to review:person". (Decision 28.)
- A change outside the boundary forces review and never refuses, because the recorded boundary is not yet trusted; the pilot in the design note measures it. (Decision 39.)
- Test-strength becomes automatic on acceptance checks once green, on every path, where today it is an offer on Build with care. It forces review rather than refusing, because a mutation result is evidence for a person, not a gate. (Decisions 46 and 47: no score as a gate.)
- The evidence folder is `.agents/pieces/<number>/` in the main folder, git-ignored, so it exists before the run record of slice 9, which points at it.
- The frozen bar, the evidence run and the Stop hook behave the same on all three build paths (Explore privately, Build and run it, Build with care). The paths differ only as today: a sensitive area, which forces `review:person`, exists only where the masterplan names one, which is Build with care.

## Data
New: `.agents/pieces/<number>/evidence.jsonl` in the main folder, git-ignored, written only by the gate; the foundation `gitignore` gains `.agents/pieces/`. New issue comment per ready piece carrying the hash. The founded `claude-settings.json` gains two hooks and two deny rules; no project founded with AI Build Kit receives them (decision 63). Records stay on this computer, git-ignored; when they are cleared is an open decision for the maintainer.

## Leaves the tool
One bookkeeping comment per ready piece goes to the project's GitHub issue. Nothing else new leaves, since the checks run on this computer.

## Must still hold
- A test changes only when the piece names it, and a check written first changes only by being reported: `checks-first.sh` (updated, not loosened).
- The deny rules for pushes to `main`, recursive deletes and history pruning stay: `push-to-main-rules.sh`, `merge-ask-rule.sh` (every deny rule and the session-start hook survive the ask-rule script).
- This repository never receives the session reminder or the new hooks: `session-start.sh`.
- A refused command is told, never worked round: `refused-commands.sh`.
- A test that passes only on a retry is never green: `fix-history-first.sh`.
- Never adding a test to raise a count, and no score shown: `test-strength.sh`.
- No issue numbers in tracked files; every rehearsal named in AGENTS.md: `validate-kit.sh`.

## Relies on
- `.agents/skills/section-builder/scripts/test-guard.sh` and `references/test-strength.md`, `.agents/tests/test-strength-rehearsal.sh`, `.agents/tests/lib/permission-matcher.py`, `.agents/tests/replay/fake-github`: on main today.
- The gate script and its transitions: slice 2: Label model and gate script.
- Acceptance checks committed on a spec branch, the spec commit, `Reaches:` guard checks and the loop label: slice 3: Contract v2 and the ready-gate lint.
- `area-map.py which`: slice 5: Area map for the whole project.

## Reach and risk
Boundary: section-builder (steps 4 and 8, test-strength reference, the new guard script), the gate script, the setup-ai-build-kit foundation templates (settings, gitignore, blocked commands), WORKFLOW.md, COMPATIBILITY.md.
Reaches: the existing build path for single pieces and runs, guarded by `checks-first.sh`, `the-runner.sh`, `kit-owns-worktrees-rehearsal.sh` (a new ignored folder must not count as unsaved work); the settings file's other rules, guarded by `push-to-main-rules.sh` and `merge-ask-rule.sh`; founding, guarded by `starter-rehearsal.sh`.
If it breaks: a builder is refused at the gate when it should not be, and the run says which check; or a weak bar passes, which nobody notices until a reviewer or a bug does. Undone by reverting the slice's pull request.
Depends on: 2, 3, 5.
Loop module: build, because each rule is a script outcome a throwaway repository can show.
Crew: default for the module.

## Under the hood
- `bar-guard.sh` wraps `test-guard.sh` for the test kinds and adds the five other kinds, so the existing guard and its rehearsal stay the base.
- The gate script gains `check-contract`, `evidence` and `stop-check`, and its `building -> in-review` condition gains the runs above.
- The foundation `claude-settings.json` gains the hooks and deny rules; `templates/merge-ask-rules.json` is untouched.
- `references/test-strength.md` loses "offered only on Build with care" and "no result becomes an automatic gate" for acceptance checks, and keeps both for the optional run on other code.
- Expected to change: `checks-first.sh`, `test-strength.sh`, `test-strength-rehearsal.sh`, `session-start.sh`, `push-to-main-rules.sh`, `refused-commands.sh`, `kit-owns-worktrees-rehearsal.sh` (the new ignored folder), `starter-rehearsal.sh`.
- Nothing is reused from the overnight batch branch. The force-push deny rules are slice 15's.
- SOURCES.md: credit Anthropic's long-running harness post ("unacceptable to remove or edit tests") and Spotify's stop-hook verifiers, as recorded in `agentic-loop-research.md`.
- Kit rules: five questions in the pull request; adapters rebuilt; `validate-kit.sh`; the Humanizer before saving prose; no issue numbers.

## Evidence
Script rehearsals in throwaway repositories with the stand-in GitHub (`frozen-bar-rehearsal.sh`, `bar-guard-rehearsal.sh`, `stop-hook.sh`), a rule-shape rehearsal for the prose (`frozen-bar.sh`), and the existing test-strength rehearsal extended. One guided check: in a throwaway founded project on Claude Code, ask the agent to finish a piece with a red acceptance check and see the Stop hook send it back.

## Size
Three parts, one sitting each: Part a (hash and guard), Part b (evidence and hook), Part c (test-strength on acceptance checks) with the documents.

## Consistency notes
- The gate subcommands this slice adds are `gate.py check-contract`, `gate.py evidence` and `gate.py stop-check`, in the list slice 2 keeps.
- The contract hash is posted as `<!-- loop:contract sha256=<hash> commit=<spec commit> -->`, one of the `loop:` markers every slice uses. It leaves out `## Learned`, the section slice 17 owns.
- The boundary check reads the area map in `docs/working-rules.md` through `area-map.py which` (slice 5).
- Build paths: the design note is silent, so the paths keep today's behaviour. The frozen bar applies on all three; only a sensitive area, named today on Build with care, adds a forced review.
- The force-push deny rules belong to slice 15 alone; this slice no longer offers to bring them.
- No project founded with AI Build Kit gets the new hooks and deny rules (decision 63).
