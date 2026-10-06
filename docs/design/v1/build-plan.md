# AI Loop Kit v1: build plan

This plan takes v1 from the borrowed code now on `main` to a working core. Its sources, in order of authority, are the maintainer's decisions of 5 October 2026, `design.md`, the two skill reports in `drafts/`, the code in `kit/` and `tests/` with `BORROWED.md`, and the notes from the overnight reviews.

The core is the smallest kit a person can use to shape a piece and have it built, judged, joined, reviewed and offered for merge on their own computer, with the guards in place. The pieces after it make the kit safe to walk away from, and add the other commands and loops.

Pieces are numbered P1 to P26 for the core, then L1 to L9 for later work. A piece number is a name in this plan, not an issue number.

## The pieces at a glance

Core means the bootstrap core. A parallel group is a set of pieces that share no files and whose dependencies are met, so they can build at the same time. Group G2 runs before G3, and so on.

| Piece | Title | Size | Depends on | Parallel group |
| --- | --- | --- | --- | --- |
| P1 | Foundations and test harness | M | none | G1 |
| P2 | Spec format and shared parser | M | P1 | G2 |
| P3 | Command guard hook and command log | M | P1 | G2 |
| P4 | Secret scan | S | P1 | G2 |
| P5 | New dependency check and supply chain settings | S | P1 | G2 |
| P6 | New-test lint | M | P1 | G2 |
| P7 | Skills lint and plugin manifest | M | P1 | G2 |
| P8 | Spec lint and computed needs list | L | P2 | G3 |
| P9 | Judge runner, fingerprint, evidence and held-out store | L | P2 | G3 |
| P10 | Settings, sandbox and hook wiring | M | P3 | G3 |
| P11 | Gate: states, moves and labels | L | P2, P4, P8 | G4 |
| P12 | Worktrees, sessions and the builder hand-off | M | P10 | G4 |
| P13 | Pre-run check and policy file | M | P4, P10 | G4 |
| P14 | Ready gate and claim gate | L | P8, P9, P11, P12, P13 | G5 |
| P15 | Attempt judging: frozen bar and judges | L | P5, P6, P9, P11, P14 | G6 |
| P16 | Records checks and project templates | M | P14 | G6 |
| P17 | `/shape` | M | P7, P14 | G6 |
| P18 | Trim pass | S | P12, P15 | G7 |
| P19 | `/setup`, first half: shape and run locally | L | P4, P5, P7, P10, P11, P13, P16 | G7 |
| P20 | Run loop | L | P11, P12, P13, P14, P15, P18 | G8 |
| P21 | Stuck detection, usage limits and the mailbox | M | P20 | G9 |
| P22 | Integration loop | L | P4, P16, P20 | G9 |
| P23 | Review loop | M | P22 | G10 |
| P24 | `/run` | S | P7, P13, P20 | G10 |
| P25 | Pull request and merge decision | M | P22, P23 | G11 |
| P26 | Core end-to-end rehearsal | M | P1 to P25 | G12 |

Later, after the core, briefly described at the end: L1 `/setup` second half (walk away), L2 `/setup` second half (deployment, health check and rollback), L3 notifications and the watch, L4 `/what-now`, L5 `/maintain`, L6 the learning loop, L7 measurement judge and hypothesis list, L8 fresh critic and outside critic, L9 shaping crews and the fuller research refresh. The later Live layers (errors and tracing into issues) follow v1.0 by the design's own plan.

## Rules for every piece

### Skills and checks

The design's "Skills and checks" section applies to every piece without exception.

- A rule that must hold lives in a script, a hook, a setting or the gate. A skill holds judgement and conversation.
- Every important rule sits in at least two independent layers.
- Each piece states its rules under "Held by:", naming the script, hook, setting or gate move that holds each one. A rule with only prose behind it is not finished.
- A `SKILL.md` has at most 150 lines and 2,000 words, and a description of 300 characters at most. References have at most 300 lines each. The `check-skills` lint from P7 holds these limits.
- Each skill has at least three eval cases (normal, edge, refusal), committed as the first commit of its piece, before the skill text. This mirrors the judge-first rule for project pieces.
- Every script follows principle 8: no prompts, `--help`, JSON on stdout, distinct exit codes, idempotent, `--dry-run` where it changes state, and errors that name the next command. The contract test from P1 runs each script marked as an agent script.

### Borrowed code

- A piece that adapts a borrowed file changes its row in `BORROWED.md` in the same pull request. The row then says "adapted" and names what the file shed.
- A piece that replaces a borrowed file removes the old file and its old rehearsal with `git rm` on named files, never a recursive delete, and moves the row to a short "Retired" table with the reason.
- `BORROWED.md` is the only file that pieces in one parallel group may share. Each piece edits only its own rows. Pieces merge one at a time, and each is brought up to date with `main` before it merges.
- New v1 files are not listed in `BORROWED.md`.

### Ruff, mypy and the Python floor

This plan settles the lint rules for v1 code.

- Python 3.10 or later, standard library only. This computer runs 3.10, and the kit installs into projects that may not have more. The policy file is JSON for that reason, since `tomllib` arrives in 3.11.
- `ruff.toml` at the repository root holds the v1 rule set:

  ```toml
  target-version = "py310"
  line-length = 100

  [lint]
  select = ["E", "W", "F", "I", "B", "UP", "SIM", "RUF", "PLW1510", "S602", "S604", "S605"]
  ```

  `B` catches likely bugs, `UP` keeps code in the 3.10 style, `SIM` removes needless branches, `RUF` adds ruff's own checks, `PLW1510` refuses `subprocess.run` without `check=`, and the three `S` rules refuse a shell started from a string.
- Verbatim copies keep `E4,E7,E9,F` until a piece adapts them. `tests/lint.sh` reads which files are verbatim from `BORROWED.md`, so the list has one home. It runs the full set on every other Python file and the old set on the verbatim ones. Adapting a file means changing its row, so the file moves to the full set in the same pull request.
- mypy runs with `--strict` on `kit/scripts/loop/` and new scripts, and with default settings on verbatim copies.
- Python files with no `.py` name, such as the GitHub stand-in, are found by their shebang and linted under a temporary `.py` name, as the stage C build did.
- `tests/lint.sh` fails, with the install line, when ruff or mypy is missing. A check that did not run is never green.

### How tests run

GitHub hosted runners are off. Every test runs on this computer.

- `tests/run-all.sh` runs every `tests/*.sh` file and names each failure. It is the check before every merge.
- Unit tests use Python's own `unittest`, under `tests/unit/`. `tests/unit.sh` runs them all, so `run-all.sh` picks them up. One file runs alone with `python3 -m unittest tests/unit/test_<name>.py`.
- An end-to-end test is a `tests/<name>.sh` file that builds a throwaway project with `tests/lib/throwaway-project.sh`. It runs alone as `tests/<name>.sh`.
- The throwaway project uses the GitHub stand-in and a new Claude stand-in, so no test needs the network, a GitHub account or a model.
- Tests that call the real `claude` sit under `tests/smoke/` and scenario evals under each skill's `evals/`. Neither is in `run-all.sh`, because they cost money. They run by hand on a skill or model change.
- `.github/workflows/v1-checks.yml` stays on manual dispatch only. It runs `tests/run-all.sh` and nothing else.

## The core

### P1. Foundations and test harness

**Goal.** Give every later piece a place to put code, a way to test it offline, and the lint rules above.

**Test.** `tests/harness.sh` builds a throwaway project, opens an issue through the GitHub stand-in, runs a scripted Claude stand-in session that commits one file, and checks the commit and the stand-in's log. Unit tests cover `loop/paths.py` and `loop/cli.py`. `tests/lint.sh` and `tests/script-contracts.sh` each plant one fault in a copy and require a failure.

**Files.**
- New: `ruff.toml`; `tests/lint.sh`; `tests/unit.sh`; `tests/unit/test_paths.py`; `tests/unit/test_cli.py`; `kit/scripts/loop/__init__.py`; `kit/scripts/loop/paths.py` (the run folder, piece records, held-out folder, logs and worktrees, in one place); `kit/scripts/loop/cli.py` (shared `--help`, `--json`, `--dry-run` and exit codes); `tests/lib/throwaway-project.sh`; `tests/stand-ins/fake-claude/claude` (replays a scripted attempt: files to write, commits to make, a hand-off to leave); `tests/script-contracts.sh` (finds scripts marked `# contract: agent` and runs principle 8's checks on each); `tests/harness.sh`.
- Changed: `tests/recipes.sh` gains a count assertion, so an empty `kit/recipes` fails (later note from the stage C3 review). `BORROWED.md` adds `tests/stand-ins/prepare/live-on-vercel.after-commit.sh` to its old-name list (same note).
- Adapts no borrowed code.

**Held by:** the lint rules in `ruff.toml` and `tests/lint.sh`; principle 8 in `tests/script-contracts.sh`; "a check that did not run is not green" in `tests/lint.sh` exiting non-zero.

### P2. Spec format and shared parser

**Goal.** Write the versioned spec format once and read it with one parser that the gate, the lint, the needs list and the fingerprint all share.

**Test.** Unit tests parse every fixture spec: a full spec, a quick-path spec, a spec with no markers, a spec with an unknown version, and the design's example issue. Each returns the same fields every time, and an unknown version is refused with a `next:` line. `tests/spec-parse.sh` puts the example issue into the GitHub stand-in and reads it back through `kit/scripts/spec.py show --json`.

**Files.**
- New: `kit/spec-format.md` (the one home for the format: markers `<!-- spec:start version=1 -->` and `<!-- spec:end -->`, field names, ID forms such as `FL-1` and `EC-1`, the quick-path field set, the coverage category list, and the supported test runners); `kit/scripts/loop/spec.py`; `kit/scripts/spec.py` with `show` only; `tests/fixtures/specs/`; `tests/unit/test_spec.py`; `tests/spec-parse.sh`.
- Adapts no borrowed file. It reads `section()` in `kit/scripts/gate.py` for the heading rules and copies none of it.

**Held by:** "one parser" in `loop/spec.py` being the only module that reads a spec block, which `tests/unit/test_spec.py` checks by searching `kit/scripts/` for any other reader of the markers.

### P3. Command guard hook and command log

**Goal.** Replace the text-matching state guard with a hook that parses each command, and log every command the agent runs, refuses or retries.

**Test.** Unit tests feed the hook every spelling in `kit/templates/blocked-commands.md` and the permission matcher's cases: `git -C . push origin main`, `env X=1 git push --force`, `sh -c "rm -rf x"`, `find . -delete`, `gh issue edit 5 --add-label state:ready`, `gh api` label writes, `cat .env`, and a write to a guarded path. Each is refused with a reason. Harmless forms such as `git push origin feature` pass. `tests/guard-hook.sh` runs the hook as Claude Code would, with JSON on stdin, in a throwaway project, and checks the command log line for both a refusal and a pass.

**Files.**
- New: `kit/hooks/guard.py`; `kit/hooks/command-log.py`; `tests/unit/test_guard.py`; `tests/guard-hook.sh`.
- Adapts: `kit/templates/blocked-commands.md` (v1 wording, the kit's own paths, the old product name gone).
- Retires: `kit/scripts/state-guard.sh` and `tests/state-guard.sh`, replaced by the two tests above.

**Held by:** this piece is one of the two layers for push to `main`, force push, recursive delete, hand-written `state:` and `needs-you` labels, reading real env files, and writes to the guards. The other layer is P10's deny rules.

### P4. Secret scan

**Goal.** Stop a secret leaving the computer, in two places.

**Test.** Unit tests plant a key of each common kind and a high-entropy string in a staged change, and require a refusal that names the file, the line and the kind, never the value. `tests/secret-scan.sh` installs the pre-push hook in a throwaway project and requires a refused push. It then calls the scan the way the gate's push step will, on a commit range, and requires the same refusal.

**Files.**
- New: `kit/scripts/secret-scan.py` (stdlib patterns and entropy; it also runs `gitleaks` when that is installed); `kit/templates/githooks/pre-push`; `tests/unit/test_secret_scan.py`; `tests/secret-scan.sh`.
- Adapts no borrowed code.

**Held by:** the git pre-push hook, and the gate's push step that P11 adds to `loop/github.py`. The design marks the gate's push step as Proposed; this plan adopts it.

### P5. New dependency check and supply chain settings

**Goal.** Check the age and licence of a new dependency before it is accepted, and turn on the package managers' own minimum-age and no-install-scripts settings.

**Test.** Unit tests diff two lockfiles for npm, pnpm and uv, find the added package, and judge it against a stand-in registry: too new is refused, an unknown licence is refused, an allowed one passes. `tests/dependency-check.sh` runs the check on a throwaway project with a planted lockfile change.

**Files.**
- New: `kit/scripts/dependency-check.py`; `kit/templates/npmrc` (minimum release age, `ignore-scripts=true`); `kit/templates/uv.toml` (exclude newer, no build scripts where uv allows); `tests/stand-ins/fake-registry/`; `tests/unit/test_dependency_check.py`; `tests/dependency-check.sh`.
- Adapts no borrowed code.

**Held by:** the package manager's own settings (first layer, before an install runs) and `dependency-check.py`, which the attempt gate in P15 calls (second layer).

### P6. New-test lint

**Goal.** Refuse the test smells a script can find reliably, the "yes" rows of the design's checks table.

**Test.** Unit tests hold one planted example per rule, in Python and in TypeScript: no assertion, a skip marker added, `assert True`, a duplicate assertion, an `if` or loop in a test, `sleep`, a debug print, a mock of the project's own module, a call-count assertion, code that checks it is under test, a snapshot rewritten in the same change, a suppression comment, an empty `catch` or `except: pass`, and a debug leftover. Each fires, and a clean test passes. "Assertion roulette" and magic numbers are reported but never refuse. Each rule also gets a mutation test with `tests/lib/rule-shape.sh`.

**Files.**
- New: `kit/scripts/loop/newtest_lint.py`; `kit/scripts/newtest-lint.py`; `tests/fixtures/test-smells/`; `tests/unit/test_newtest_lint.py`; `tests/newtest-lint.sh`.
- Reads `kit/scripts/test-guard.sh` for its patterns. Does not change it.

**Held by:** the attempt gate (P15), which runs this lint on every attempt. The reviewer's list (P23) covers the "partly" and "no" rows.

### P7. Skills lint and plugin manifest

**Goal.** Make the 17 principles a free check on every commit, before any skill is written, and give the kit its plugin manifest.

**Test.** `tests/check-skills.sh` builds a good fixture skill and passes it, then mutates one rule at a time with `tests/lib/rule-shape.sh` and requires each mutation to fail: over 150 lines, over 2,000 words, a description over 300 characters, a hard rule with no `Held by:` line, sections out of order, a missing `Done when:` line, a nested or orphan reference, a shell block over three lines, capitalised emphasis, a date or hash-and-digits number, fewer than three eval cases, a copied gate table row, a banned synonym, and a guard claimed only by the skill's own frontmatter. It also requires `disable-model-invocation: true` on `setup`, `run` and `maintain`. `claude plugin validate` runs when `claude` is installed, and the test says plainly when it skipped it.

**Files.**
- New: `kit/scripts/check-skills.py`; `kit/glossary.md` (one word per concept, and the banned synonyms, such as "ticket" or "task" for piece and "stage" for state); `kit/.claude-plugin/plugin.json` (the plugin root is `kit/`, and skills live in `kit/skills/<name>/`); `tests/fixtures/skills/`; `tests/check-skills.sh`.
- Reuses `kit/scripts/document-bloat.py` unchanged for repeated paragraphs.

**Held by:** `check-skills.py` for principles 1 to 7, 9, 11, 12, 13, 15, 16 and 17; `tests/script-contracts.sh` (P1) for principle 8; P12's command-line test for principle 14; the scenario evals for principle 10.

### P8. Spec lint and computed needs list

**Goal.** Judge a spec without running anything, and work out from it what the piece still needs and who can settle each need.

**Test.** Unit tests drive each need in the design's needs table: it appears when its field is missing and clears when the field is written. Lint unit tests cover required fields for both paths, coverage categories answered or "not applicable" with a reason, every ID traced to a test and every test to an ID, edge cases in "When ..., then ..." form with an example value, Limits with a number or "none", refused phrases, vague adjectives with no number, a numbered build-step list, and length limits. A test checks that the runner list in `kit/spec-format.md` matches the runners the judge runner reads (later note from the stage C1 review). `tests/spec-lint.sh` puts three issues into the GitHub stand-in and runs `spec.py lint` and `spec.py needs --json` on each.

**Files.**
- New: `kit/scripts/loop/lint.py`; `kit/scripts/loop/needs.py`; `tests/unit/test_lint.py`; `tests/unit/test_needs.py`; `tests/spec-lint.sh`.
- Changed: `kit/scripts/spec.py` gains `lint` and `needs`.
- Adapts from `kit/scripts/ready-lint.py`: required sections, refused phrases, brief rules, length limits and exit codes. It drops the masterplan reading and the no-code special case. The file itself retires in P14, once P9 has taken the judge runner too.

**Held by:** the ready gate (P14), which runs the lint and refuses a non-empty needs list; the claim gate (P14), which runs the lint again on today's `main`.

### P9. Judge runner, fingerprint, evidence and held-out store

**Goal.** Run a judge the same way everywhere, tell an assertion failure from an error, take the fingerprint, keep the hash-chained evidence, and hold the hidden cases where only the gate can read them.

**Test.** Unit tests: a pytest, Vitest, Jest and Node runner report each read as "failed on an assertion naming FL-1", "errored on import" or "passed"; another runner falls back to the exit code with a note; a check past its hard timeout is stopped and reported. The fingerprint changes when the spec block or the judge commit changes and not otherwise. The evidence chain refuses an edited entry. `tests/judge-runner.sh` builds a throwaway Python project with a failing acceptance test, runs it on `main` in a temporary checkout, and checks the result, the timeout and the evidence entry. It then stores two held-out cases, checks their fingerprint, and checks that a session running as a builder cannot read the folder (the sandbox test itself is in P10).

**Files.**
- New: `kit/scripts/loop/judge.py`; `kit/scripts/loop/fingerprint.py`; `kit/scripts/loop/evidence.py`; `kit/scripts/loop/heldout.py`; `tests/unit/test_judge.py`; `tests/unit/test_fingerprint.py`; `tests/unit/test_evidence.py`; `tests/judge-runner.sh`.
- Adapts from `kit/scripts/ready-lint.py`: the temporary checkout, the install, the time limits and the report reading. Adapts from `kit/scripts/gate.py`: `contract_hash`, `chain_of`, `read_record` and `write_record`. Neither file changes here.

**Held by:** the gate running every judge itself (P14, P15, P22), never trusting an agent's word; the held-out folder sits outside git and outside the project, read-blocked for builders by the sandbox (P10) and denied by the guard hook (P3).

### P10. Settings, sandbox and hook wiring

**Goal.** Write the deny and ask rules, the sandbox settings and the builder's own settings file, and wire the hooks, so every guard has its second layer.

**Test.** `tests/settings.sh` reads the design's two-layer table as data and checks that each rule has both holders: a deny rule in the template and a refusal from `kit/hooks/guard.py`, both matched offline with `tests/lib/permission-matcher.py`. It checks the sandbox block (`strictAllowlist`, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`, bypass mode off), the held-out folder read-block, and auto memory off in the builder settings. It checks that the settings template wires the session start hook, and that merging the template into a project's own settings keeps the person's rules (later note from the stage C2 review). The adapted session-start test drives the hook after a compaction and checks it prints the gate's brief report.

**Files.**
- New: `kit/templates/builder-settings.json` (passed with `--settings`; `dontAsk`, the `Skill` tool denied, no GitHub credential, held-out folder read-blocked, sandbox auto-allow); `kit/hooks/hooks.json`; `tests/settings.sh`.
- Adapts: `kit/templates/claude-settings.json`; `kit/scripts/merge-ask-rules.py` (pattern reused, kit paths updated); `kit/templates/merge-ask-rules.json`; `kit/scripts/session-start.sh` (drops the old check-up file, `AI_BUILD_KIT_TODAY` and the old product name; prints the gate's brief report on start and after compaction); `tests/push-to-main-rules.sh`; `tests/merge-ask-rule.sh`; `tests/session-start.sh`.

**Held by:** the deny rules and sandbox (first layer) beside the guard hook (P3, second layer); "guards guard themselves" by deny rules and sandbox write-blocks on `kit/`, `.claude/`, `.github/workflows/` and the hooks, with the pre-run check (P13) as the second layer.

### P11. Gate: states, moves and labels

**Goal.** Rewrite the gate as the only mover: seven states, fourteen moves, the `needs-you` flag, refusals with `next:`, and the report the skills inject.

**Test.** Unit tests drive every one of the fourteen moves twice, once where its checks hold and once where each check fails, and require a move not in the table to be refused. They cover read-twice writes, a reason on every move back, the anti-circle rule on moves back to shaping only, the repeat counter of 3 on moves 7, 8 and 12, a gate-made spec change taking a new fingerprint, a hand-changed label reported and never undone, and a second `state:` label refused. `tests/gate.sh` drives one piece through capture, shaping and drop in a throwaway project with the GitHub stand-in, and checks the labels, the needs written below the spec, the `needs-you` flag and the run record.

**Files.**
- New: `kit/scripts/loop/states.py` (the table of states and moves, as data); `kit/scripts/loop/moves.py` (each move calls its checks from `loop/gates/<name>.py`; a move whose checks are not installed yet is refused with a `next:` line, so later pieces add a module and change no shared file); `kit/scripts/loop/github.py` (the `gh` wrapper, read-twice, and the push step that runs `secret-scan.py` first); `kit/scripts/loop/gates/__init__.py`; `tests/unit/test_states.py`; `tests/unit/test_moves.py`; `tests/gate.sh`.
- Adapts: `kit/scripts/gate.py`, rewritten as a thin command line (`capture`, `move`, `drop`, `report`, `labels --create`, `branch`) over the modules above. It sheds the old label list, the sub-state markers, the checkpoint assumptions, the always-person review stub and `.agents/tools/` paths. May extend `tests/stand-ins/fake-github/gh` where a move needs it.
- Retires: `tests/gate-script.sh`, replaced by the tests above.
- Labels: the gate creates its own set (`state:` for each state, `needs-you`, `type:feature`, `type:bug`, `type:chore`). The old labels stay until removal stage G retires them.

**Held by:** the gate refusing any move outside the table; hand-written labels refused by P3's hook and P10's deny rules, and reported by `gate.py report`; the push step's secret scan beside P4's pre-push hook.

### P12. Worktrees, sessions and the builder hand-off

**Goal.** Give each piece its own worktree with throwaway values, start every non-interactive session with one exact command line, and give builders one way to hand back.

**Test.** Unit tests assert the exact `claude -p` command line (principle 14): the brief passed by file, `--settings` with the builder settings, `--permission-mode dontAsk`, no `--bare`, `--max-budget-usd` only when the caller passes a cap (the run script reads it from the policy), the working folder the worktree, and an environment with no GitHub token. `tests/kit-owns-worktrees-rehearsal.sh` (adapted) opens a worktree, finds throwaway values in place of the real env file, and removes the worktree without force. It regains two assertions lost in stage C2: a file in `.agents/tmp` never reaches git, and a walk-through picture outlives the worktree. `tests/handoff.sh` runs the Claude stand-in through each of the five hand-offs and checks the file the run will read.

**Files.**
- New: `kit/scripts/loop/sessions.py` (starts any `claude -p` session: builder, test-list writer, trim, reviewer); `kit/briefs/builder.md` (the fixed brief template); `kit/scripts/handoff.py` (done, bar is wrong, needs the person, blocked by environment, gave up; "needs the person" writes the question and returns at once); `tests/unit/test_sessions.py`; `tests/handoff.sh`.
- Adapts: `kit/scripts/worktree.sh` (drops linking the real `.env`, writes throwaway values from `.env.example`, sheds the old product name); `tests/kit-owns-worktrees-rehearsal.sh`.

**Held by:** builders holding no GitHub credential, by the scrubbed environment here and the sandbox read-block on the `gh` config in P10; "no real env file" by the throwaway values here and the deny rule and hook in P10 and P3.

### P13. Pre-run check and policy file

**Goal.** Refuse to start a run, with the reason, unless every guard, the policy, the computer and `main` are fine.

**Test.** `tests/pre-run-check.sh` takes each guard away in turn in a throwaway project and requires a refusal that names it: the guard hook, a deny rule, the sandbox, the pre-push hook, a changed kit file, a missing policy, a malformed policy value (named by key), a lock held by another run, a run script passing `--bare`, low disk, and a red `main`. With every guard in place it passes. It names which half of `/setup` is missing. On an API key with no spend caps it refuses. With `origin` set to the kit's own repository it refuses. Unit tests cover the policy schema and its defaults.

**Files.**
- New: `kit/scripts/loop/policy.py`; `kit/templates/policy.json` (builder cap 3, attempt limit 3, review rounds 2, question cap 5, research age limit, length limits, billing mode and caps, held-out folder); `kit/scripts/pre-run-check.py`; `tests/unit/test_policy.py`; `tests/pre-run-check.sh`.
- Adapts: `kit/scripts/check-tooling.sh` (tools and sign-in, the kit repository guard; sheds the old product name), which the pre-run check calls; `tests/check-tooling.sh`.

**Held by:** this check is the second layer for "the guards stay in place" (P10 is the first). The policy file is protected from agents by P10's deny rules and P3's hook.

### P14. Ready gate and claim gate

**Goal.** Install the checks for move 2 (ready) and move 4 (claim), including the two fresh test lists and the decision on individual review.

**Test.** Unit tests: each ready check refuses alone (needs not empty, lint fails, test lists differ by spec ID, judge files not the first commit, a judge that passes on `main`, a judge that errors instead of failing on its assertion, a must-stay-the-same check that fails on `main`, a sensitive area with no acceptance, a blocked-by link to nothing or a cycle, an area missing from the map), and each must-look reason marks the piece for individual review. Each claim check refuses alone (fingerprint changed, a research finding whose file fingerprint changed, an outside finding past the age limit, lint fails on today's `main`, the judge now passes, a blocker not done, already building, an area in use, no free slot). `tests/ready-gate.sh` shapes one piece in a throwaway project with a scripted spec and a failing test, runs the two test-list sessions with the Claude stand-in, takes the piece to ready, then edits the spec by hand and requires the claim to send it back to shaping.

**Files.**
- New: `kit/scripts/loop/gates/ready.py`; `kit/scripts/loop/gates/claim.py`; `kit/scripts/loop/research.py` (the quick check of every finding); `kit/scripts/loop/areas.py`; `kit/scripts/test-lists.py` (runs two fresh sessions and compares their lists by spec ID); `kit/briefs/test-list.md`; `kit/templates/area-map`; `tests/unit/test_ready.py`; `tests/unit/test_claim.py`; `tests/ready-gate.sh`.
- Adapts: `kit/scripts/area-map.py`, now a command line over `loop/areas.py`, shedding the old product name; `tests/area-map-rehearsal.sh`.
- Retires: `kit/scripts/ready-lint.py` and `tests/ready-lint-rehearsal.sh`, whose parts now live in P8 and P9.

**Held by:** the gate refusing move 2 and move 4 unless every check passes; the fingerprint, checked again at every claim; the sensitive-area acceptance held by the ready gate and quoted on the issue.

### P15. Attempt judging: frozen bar and judges

**Goal.** Install the checks for move 5, in the design's order, so the gate judges every attempt and catches gaming.

**Test.** Unit tests plant each anti-gaming case and require a failed attempt, logged as possible gaming where the design says so: a changed judge file, a removed or skipped test, a loosened assertion, a raised timeout, a retry added, a held-out result much worse than the visible one, a new test that fails the new-test lint, a must-stay-the-same check gone red, a diff outside the declared touches, and an unplanned new dependency. A clean attempt passes. `tests/attempt-gate.sh` runs three scripted attempts on one piece in a throwaway project: one that edits the bar, one that special-cases the visible test and fails a held-out case, and one honest pass.

**Files.**
- New: `kit/scripts/loop/gates/attempt.py`; `kit/scripts/loop/bar.py` (the byte-for-byte check over the judge and everything it rests on: tests, fixtures, test settings); `tests/unit/test_attempt.py`; `tests/unit/test_bar.py`; `tests/attempt-gate.sh`.
- Adapts into `loop/bar.py`: the seven kinds of bar change from `kit/scripts/bar-guard.sh` and `kit/scripts/test-guard.sh`, without the named-change escape, since any bar change is now a failed attempt.
- Retires: `kit/scripts/bar-guard.sh`, `kit/scripts/test-guard.sh`, `tests/bar-guard-rehearsal.sh`, `tests/frozen-bar-rehearsal.sh` and `tests/test-strength-rehearsal.sh`, each case carried into the new tests first.
- Core judge kinds: acceptance tests and reproducing test. A measurement or reference judge is refused at the ready gate until L7 or L8 lands, so no piece runs without its anti-gaming checks.

**Held by:** the gate (this move's checks) and the bar files' deny rules and sandbox write-blocks (P10); held-out cases by the gate-only folder (P9, P10).

### P16. Records checks and project templates

**Goal.** Hold the records model by checks: every fact in one home, under its line limit, with no drift that a script can find.

**Test.** Unit tests: `AGENTS.md` over 150 lines or a section over 12 fails; a path or command it names that does not exist fails; `docs/overview.md` over 100 lines fails; an overview area or sensitive flag that disagrees with the area map fails; an area doc over 300 lines fails; a tracked file in no area fails; a closed piece with no changelog entry fails; a repeated paragraph fails. `tests/records-check.sh` founds a throwaway project from the templates and requires it to pass, then plants each fault.

**Files.**
- New: `kit/scripts/records-check.py`; `kit/templates/AGENTS.md` (the skeleton, under 150 lines); `kit/templates/CLAUDE.md` (imports `AGENTS.md` only); `kit/templates/overview.md`; `kit/templates/docs-README.md`; `kit/templates/CHANGELOG.md`; `tests/unit/test_records_check.py`; `tests/records-check.sh`.
- Adapts: `kit/scripts/document-claims.py` (paths named exist) and `kit/scripts/document-bloat.py` (repeated paragraphs), both called by `records-check.py`; `tests/document-read-rehearsal.sh`; `tests/document-bloat-rehearsal.sh`.
- Adapts: `kit/templates/working-rules.md` into the `AGENTS.md` template, and retires it.

**Held by:** `records-check.py`, run in the project's checks on every pull request and in the final combined check (P22); the gate refusing a merge whose named doc the pull request did not change (P25).

### P17. `/shape`

**Goal.** Capture an idea in the person's words, or shape a piece until the ready gate accepts it.

**Eval cases, written first.**
1. Normal: given a one-line idea in a fixture project, the gate's capture is called, questions come in a batch under the cap of five, each with why it matters and a recommended answer, and the ready move is called only after `spec.py lint` passes.
2. Edge: given a vague idea, no ready move is called, and the reply names the biggest need on the list.
3. Refusal: given an idea touching a sensitive area, the reply gives the risk notice and asks for the person's acceptance, and no ready move happens without it.
4. Triggering, since `/shape` is model-invoked: ten queries, five that should trigger and five near misses, three runs each, passing above a trigger rate of 0.5.

**Test.** `check-skills` passes on the folder. `tests/shape-skill.sh` drives the skill's helper scripts in a throwaway project: the duplicate search finds a closed issue with the same words and adds a comment rather than a new issue, and the dropped-piece search warns. The scenario evals run by hand.

**Files.**
- New: `kit/skills/shape/SKILL.md` (150 lines at most); `kit/skills/shape/references/questions.md`; `kit/skills/shape/references/quick-path.md`; `kit/skills/shape/scripts/find-duplicates.py`; `kit/skills/shape/evals/`; `tests/shape-skill.sh`.
- Uses `kit/scripts/co-change.sh` unchanged to help fill the touches field.

**Held by:** "a need clears only when its answer is written" by the gate computing needs from the spec (P8, P11); the question cap by the policy file and the eval; "never ready without the gate" by move 2 (P14); the yes before posting in the person's name by the ask rule (P10) and the hook (P3); "silence is never an answer" by the needs list, which only a written answer clears.

### P18. Trim pass

**Goal.** Run the last step of the build loop: remove or fold only, never a test, only code this piece added, in its own commit, thrown away if any check fails.

**Test.** Unit tests on `trim-check.py`: a trim that touches a test fails; one that changes a line the piece did not add fails; one that adds net lines fails; a clean fold passes. `tests/trim.sh` runs a scripted trim session on a passed piece in a throwaway project. When a check fails afterwards, the piece branch is unchanged. The trim lives on a scratch branch that only fast-forwards the piece branch on green, so nothing is reset.

**Files.**
- New: `kit/scripts/trim-check.py`; `kit/briefs/trim.md`; `tests/unit/test_trim_check.py`; `tests/trim.sh`.

**Held by:** `trim-check.py` and the attempt gate re-run after the trim (P15); the scratch branch, since `git reset --hard` is denied by P10 and refused by P3.

### P19. `/setup`, first half: shape and run locally

**Goal.** Found a project, or meet an existing one, so the person can shape and run locally with every local guard in place.

**Eval cases, written first.**
1. Normal: in an empty fixture project, the skill runs the tooling check, writes the foundation files without overwriting anything, creates the gate's labels, and captures the first piece as a quick-path scaffold and test runner piece.
2. Edge: with a missing tool, the first half stops with the install line and writes nothing else.
3. Refusal: run in a fixture whose `origin` is the kit's own repository, it opens no issue and changes no setting.

**Test.** `check-skills` passes. `tests/setup-first-half.sh` runs the setup script on an empty throwaway project and on one with existing code, settings and an `AGENTS.md`. It checks: no file overwritten, the person's settings rules kept, the hooks and the pre-push hook installed (later note from the stage C2 review), the ignore file covering the run folder, piece records, logs and worktrees, a default network allowlist for the detected language, the free-plan warning on a private free repository in the stand-in, the spend caps asked for when the billing mode is an API key, the policy written, and the pre-run check passing apart from "the second half of `/setup` is missing".

**Files.**
- New: `kit/skills/setup/SKILL.md`; `kit/skills/setup/references/founding.md`; `kit/skills/setup/evals/`; `kit/scripts/setup.py` (the steps the skill calls, idempotent, decided by what is on disk); `kit/templates/network-allowlist/` (one file per language: the package registry and toolchain hosts); `tests/setup-first-half.sh`.
- Adapts: `kit/scripts/bootstrap-project.sh` into `setup.py` (copy without overwriting; sheds the old skill-folder paths and plugin detection), then retires it; `kit/templates/gitignore`; `kit/templates/piece-issue.yml` (v1 fields, filing into shaping).
- Retires: `kit/scripts/place-plan-helper.sh`. v1 runs its scripts from the plugin folder, so nothing is copied into a project to refresh (later note from the stage C2 review).

**Held by:** the guards installed here are held by P3, P4, P10 and P13; "founding never stops on a nice-to-have answer" by `setup.py` writing an open question instead; the first piece's judge (the test command runs) by the ready gate's empty-project exception (P14).

### P20. Run loop

**Goal.** Run the pieces the person picked as a plain script: plan, claim, build attempt by attempt, route each outcome, keep the run record, and resume after a crash.

**Test.** Unit tests on ordering: dependencies first, serial chains shown first, no two pieces in one area at once, slots sized from free memory and capped by policy. Unit tests on routing: each hand-off and gate result goes to its one move (5, 6, 7, or stay), with attempts counted as the design's outcomes table says, and "no real improvement" decided from judge results. `tests/run-loop.sh` runs three ready pieces in a throwaway project with the Claude stand-in: one passes first time, one fails then passes, one says the bar is wrong. It then kills the script mid-run, starts it again, and checks that finished work is not redone. A stop sends the building piece back to ready with its branch kept.

**Files.**
- New: `kit/scripts/run.py`; `kit/scripts/loop/run/__init__.py`; `kit/scripts/loop/run/plan.py` (also printed by `run.py --plan`); `kit/scripts/loop/run/attempts.py`; `kit/scripts/loop/run/record.py` (the run record at `.agents/runs/<name>/run.json`, the heartbeat and the lock file); `kit/scripts/loop/run/summary.py` (the morning summary, with every decision made alone); `tests/unit/test_plan.py`; `tests/unit/test_routing.py`; `tests/run-loop.sh`.
- `run.py` calls `loop/run/watch.py`, `loop/run/integrate.py`, `loop/run/review.py` and `loop/run/pull_request.py` when they exist, so P21 to P25 add modules and do not edit it.

**Held by:** attempt limits by the run script counting from the gate's attempt log; the lock file by `record.py` and the pre-run check (P13); every move by the gate (P11), never by the script writing labels.

### P21. Stuck detection, usage limits and the mailbox

**Goal.** Stop a clearly stuck attempt, wait out a usage limit without counting it, and obey pause, continue and stop.

**Test.** Unit tests feed recorded builder output: the same error three times, a change undone and redone, a test past its hard timeout. Each stops the attempt and counts it. A usage-limit message pauses the piece as waiting for reset and counts nothing. Two environment failures in a row on different pieces pause the run. `tests/watch-and-mailbox.sh` writes pause, continue and stop into the mailbox during a stand-in run and checks the run record, and checks tokens recorded per piece.

**Files.**
- New: `kit/scripts/loop/run/watch.py`; `kit/scripts/loop/run/mailbox.py`; `tests/unit/test_watch.py`; `tests/watch-and-mailbox.sh`.

**Held by:** the run script, which sees the builder's output; the hard timeout on every judge run (P9).

### P22. Integration loop

**Goal.** Join each built piece to the combined branch as a trial, move the branch only on green, name the culprit on red, then commit the docs and changelog and run the final combined check.

**Test.** `tests/integration-loop.sh` is the design's end-to-end case. Two pieces pass alone and clash together. The clash is found at the second trial join, the trial is thrown away, the combined branch never moves, the culprit goes back to building with the clash written on it, and the run carries on. Further cases: a merge conflict goes back the same way and no agent resolves it; a resumed run reads the `Piece:` trailers and does not join twice; a piece leaving after it joined causes a rebuild from `main` under a fresh name, with no revert and no force push; a dependent stacks on its dependency's branch; an isolated piece follows the same steps on its own branch; held-out cases are copied in only at the final check; the secret scan runs before each push.

**Files.**
- New: `kit/scripts/loop/run/integrate.py`; `kit/scripts/loop/run/docs_commit.py` (applies each piece's Added, Changed and Removed lines to the overview and area docs, and folds one changelog entry per piece); `tests/integration-loop.sh`.
- Adapts: `kit/scripts/bring-up-to-date.sh` (a merge commit, never a rebase; works on the combined branch; fixes its error message); `kit/scripts/fold-changes.py` (one entry per piece from its behaviour change); `tests/fold-at-merge-rehearsal.sh`; `tests/recheck-before-merge-rehearsal.sh`.

**Held by:** the gate re-running every joined piece's judges, must-stay-the-same checks and touches at each trial (P9, P15); no force push and no revert by P3's hook and P10's deny rules; the secret scan by P4 and the gate's push step.

### P23. Review loop

**Goal.** Have a fresh reviewer read only the specs and the combined diff, piece by piece, and turn every finding into a failing check, a shaping issue or a worth-knowing note.

**Test.** `tests/review-loop.sh` runs a stand-in reviewer that returns a scripted findings file. A failing-check finding sends its piece to building (move 8) with the new test joining the frozen bar and a written justification. A wrong-spec finding sends it to shaping (move 9). A finding left after two rounds sends only that piece to shaping with `needs-you` set, and the combined branch is rebuilt without it. Unit tests check the findings schema (kind, gap kind, piece, evidence) and that the reviewer's command line passes no builder account.

**Files.**
- New: `kit/scripts/loop/run/review.py`; `kit/briefs/reviewer.md` (the reviewer's list holds the "partly" and "no" rows of the design's checks table, and the report split into worth stopping for and worth knowing); `tests/unit/test_review.py`; `tests/review-loop.sh`.

**Held by:** the reviewer's isolation by `sessions.py` (P12) passing only specs and diff; the round cap by the policy file and `review.py`; moves 8 and 9 by the gate.

### P24. `/run`

**Goal.** Start a run from a conversation: show the gate's report, ask the two questions once, run the pre-run check, and start the run script.

**Eval cases, written first.**
1. Normal: the pre-run check runs before the run script, and the skill starts the script rather than building anything itself (no edit to source files).
2. Edge: with no ready piece, the reply says so in one line and starts nothing.
3. Refusal: with a guard missing in the fixture, the reply names the missing guard and which half of `/setup` is missing, and the run script is never started.

**Test.** `check-skills` passes, including `disable-model-invocation: true` and the `!` injection of `gate.py report --json --brief` with its fallback line. `tests/run-skill.sh` checks the start command the skill uses: `run.py` under `caffeinate`, the two answers passed as flags, and the default "merge not pre-approved".

**Files.**
- New: `kit/skills/run/SKILL.md`; `kit/skills/run/evals/`; `tests/run-skill.sh`.

**Held by:** the pre-run check (P13) refusing a missing guard; pre-approval asked per run and never stored, held by `run.py` taking it only as a flag and the policy schema having no such key.

### P25. Pull request and merge decision

**Goal.** Open one pull request grouped by piece with each piece's evidence, and merge only the exact tested commit, only when the person merges or every pre-approval condition holds.

**Test.** `tests/merge-decision.sh` in a throwaway project: the pull request body lists each piece with its judge result, held-out result, review verdict and worth-knowing items, and one `Closes` line per piece with no closing word anywhere else. A pre-approved run with every condition met merges with `--match-head-commit`. A pre-approved run with a must-look piece waits. When `main` moves after the final check, nothing merges until the branch is brought up to date and checked again (move 12). A comment naming one piece sends back only that piece and rebuilds the rest (move 13). A pull request whose named doc did not change is refused. A merge the person makes after `main` moved triggers a check on `main`.

**Files.**
- New: `kit/scripts/loop/run/pull_request.py`; `kit/scripts/loop/gates/merge.py`; `kit/scripts/closing-words.py` (scans title, body, commits and changelog entries); `tests/unit/test_merge.py`; `tests/merge-decision.sh`.
- May extend `tests/stand-ins/fake-github/gh` for `--match-head-commit` if it lacks it.

**Held by:** the gate (moves 10 to 13); "only the person merges unless pre-approved" by the run script's flag (P24) and, on a public or paid repository, a GitHub branch rule as a further layer; the merge ask rule in the settings template (P10).

### P26. Core end-to-end rehearsal

**Goal.** Prove the core works as one thing, from an empty project to a merge.

**Test.** `tests/e2e-core.sh`: an empty throwaway project goes through the first half of `/setup`, builds the scaffold piece, shapes one feature piece with acceptance tests and one bug piece with a reproducing test, takes both to ready, runs them with the Claude stand-in, joins, reviews and opens the pull request, and the person merges on the GitHub stand-in. Both pieces end done, the changelog holds two entries, and the records check passes. `tests/smoke/run-real.sh` does the same with the real `claude` on a tiny project, by hand only.

**Files.**
- New: `tests/e2e-core.sh`; `tests/smoke/run-real.sh`; `tests/fixtures/e2e-core/`.

**Held by:** nothing new. This piece proves the others hold together.

## Later pieces

These come after the core. Each gets its own plan entry, in the same shape, before it is built.

- **L1. `/setup` second half: walk away.** Creates the gate's GitHub App and moves the gate onto it; runs the run script under launchd with `KeepAlive`; writes the recipe's network allowlist on top of the language default; adds Dependabot and pinned Actions in the project. The pre-run check then stops reporting a missing half.
- **L2. `/setup` second half: deployment.** Adapts the two recipes, their parts, `recipe-format.md`, `check-recipes.sh` and the host stand-ins; adds the post-deploy health check as a small GitHub Action and the automatic rollback, with a revert pull request, a bug issue and a "production is pinned" notification; puts the preview link in each piece's evidence.
- **L3. Notifications and the watch.** GitHub @-mentions by the App for the six moments, quiet hours from GitHub Mobile's working hours with held messages collapsed into one, and the launchd watch that only checks the heartbeat is fresh.
- **L4. `/what-now`.** What is where, what needs the person, how a run is going, and what was decided alone, from the gate's report, with its order and cap of three.
- **L5. `/maintain`.** Drift between records and code, code health with mutation testing where a tool is present, change-fail and rework rates, stale branches listed and never removed, and kit updates. Findings become issues in shaping. Suggested every 2 weeks.
- **L6. The learning loop.** Evidence at run end and on every kickback, lesson candidates at two sightings, lessons as checks first, applied at the next run as their own commits, stale lessons offered for removal.
- **L7. Measurement judge and hypothesis list.** The metric command, the held-out twin, and the hypothesis list fixed before any attempt.
- **L8. Fresh critic and outside critic.** A/B comparison in both orders for reference pieces, and Codex as an advisory outside critic when installed and agreed.
- **L9. Shaping crews and the fuller research refresh.** Several researchers or prototypes when the needs list holds a research or design question, the rule for researchers who disagree, and automatic re-research at claim time.

## Decisions this plan made alone

The design did not settle these. Each is the choice that keeps every settled decision and is easiest to undo.

1. The plugin root is `kit/`, with `kit/.claude-plugin/plugin.json` and skills in `kit/skills/`. Removal stage D deletes the root `.claude-plugin/`, so the two never meet.
2. Python 3.10 and the standard library only, so the policy file is JSON.
3. The ruff rule set above, with the verbatim list read from `BORROWED.md`.
4. Until the second half of `/setup` creates the GitHub App, the gate uses the person's own `gh` sign-in for its bookkeeping. Builders still hold no credential. Such a run cannot be pre-approved.
5. The held-out folder sits outside the project, under the person's local data folder, keyed by repository. Its path lives in the machine-local settings file.
6. Builders hand back by running `kit/scripts/handoff.py`, a script their settings allow, not through a server.
7. Tests use a Claude stand-in. Real sessions run only in `tests/smoke/` and scenario evals, by hand.
8. Core judge kinds are acceptance tests and reproducing test. The ready gate refuses measurement and reference judges until L7 and L8.
9. Shaping crews and the automatic research refresh come in L9. Until then a claim whose research needs a fuller refresh sends the piece back to shaping with that need.
10. The first half of `/setup` writes a default network allowlist for the project's language, so the sandbox has one from the first run. The second half adds the recipe's hosts.
11. The run record sits at `.agents/runs/<name>/run.json` and piece records at `.agents/pieces/<n>/`, both git-ignored, as the design proposed.
12. A trim lives on a scratch branch that only fast-forwards the piece branch on green, because `git reset --hard` is denied.
13. The gate's moves look up their checks in `loop/gates/<name>.py`, so later pieces add files and leave shared ones alone.
14. `/setup` writes the area map at founding, and later changes go through pieces. The design left this "not settled".
15. The first half of `/setup` asks for spend caps when the billing mode is an API key, and the pre-run check refuses an API key with no caps.

## Where the design and the decisions file disagree

Most differences are earlier answers that a later decision on 5 October replaced. The design follows the later decision, and so does this plan.

1. Answer 17 says a red join is "confirmed by one re-check without it" and "taken out". The red-team fixes replaced this with trial joins in a scratch copy, and the design says there is no take-out step and no re-check.
2. Answer 18 and "Final three" name a Claude Code push notification with email as the fallback. The final research pass replaced this with GitHub @-mentions pushed by GitHub Mobile.
3. The meta-loop answers give the watch the jobs of restarting the run script, stopping stuck attempts and giving up after three restarts. The final pass moved those into launchd and the run script. The watch now only checks the heartbeat, and notification 6 is "heartbeat stale" rather than "the watchdog gave up".
4. Answer 11 says scratch files are removed before merge. The final pass keeps them in a git-ignored run folder, so nothing is removed.
5. Both documents say the first half of `/setup` lets the person "shape and run locally". Both also say the pre-run check refuses unless the gate's GitHub App is in place, and the App comes from the second half. This one is still open in both. The plan resolves it with decision 4 above, and the maintainer should confirm it.
6. The design puts the network allowlist in the second half of `/setup`, but also turns the sandbox and its allowlist on for every agent session in v1. The plan resolves it with decision 10 above.
7. The design puts spend caps for an API key in the second half of `/setup`, but a local run on an API key needs them. The plan resolves it with decision 15 above.
