# AI Loop Kit v1: build plan

This plan takes v1 from the borrowed code now on `main` to a working core. Its sources, in order of authority, are the maintainer's decisions of 5 October 2026, `design.md`, the two skill reports in `drafts/`, the code in `kit/` and `tests/` with `BORROWED.md`, and the notes from the overnight reviews.

"Core" in this plan means the bootstrap core: the smallest kit a person can use to shape a piece and have it built, judged, joined, reviewed and offered for merge on their own computer, with the guards in place. The later pieces L1 to L10 are all part of v1.0. The core comes first only because the rest builds on it.

Pieces are numbered P1 to P27 for the core, then L1 to L10. A piece number is a name in this plan, not an issue number.

## The pieces at a glance

A parallel group is a set of pieces that share no files and whose dependencies are met, so they can build at the same time. Group G2 runs before G3, and so on.

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
| P11 | Gate: states, moves, labels and the App credential | L | P2, P4, P8, P9 | G4 |
| P12 | Worktrees, sessions and the builder hand-off | M | P10 | G4 |
| P13 | Pre-run check and policy file | M | P4, P10 | G4 |
| P14 | Ready gate and test lists | L | P8, P9, P11, P12 | G5 |
| P15 | Claim gate and research check | M | P13, P14 | G6 |
| P16 | Attempt judging: frozen bar and judges | L | P5, P6, P9, P11, P14 | G6 |
| P17 | Records checks and project templates | M | P14 | G6 |
| P18 | `/shape` | M | P7, P14 | G6 |
| P19 | Trim pass | S | P12, P16 | G7 |
| P20 | `/setup`, first half: shape and run locally | L | P4, P5, P7, P10, P11, P13, P17 | G7 |
| P21 | Run loop | L | P11, P12, P13, P15, P16, P19 | G8 |
| P22 | Stuck detection, usage limits, the mailbox and answers | M | P21 | G9 |
| P23 | Integration loop | L | P4, P17, P21 | G9 |
| P24 | Review loop | M | P23 | G10 |
| P25 | `/run` | S | P7, P13, P21 | G10 |
| P26 | Pull request and merge decision | M | P23, P24 | G11 |
| P27 | Core end-to-end rehearsal | M | P1 to P26 | G12 |

Later, all part of v1.0, briefly described at the end: L1 `/setup` second half (walk away: launchd, the watch, the recipe allowlist), L2 `/setup` second half (deployment, health check and rollback), L3 notifications, L4 `/what-now`, L5 `/maintain`, L6 the learning loop, L7 measurement judge and hypothesis list, L8 fresh critic and outside critic, L9 shaping crews and the fuller research refresh, L10 well-defined checks for the trim pass. The later Live layers (errors and tracing into issues) follow v1.0 by the design's own plan.

## Rules for every piece

### Skills and checks

The design's "Skills and checks" section applies to every piece without exception.

- A rule that must hold lives in a script, a hook, a setting or the gate. A skill holds judgement and conversation.
- Every important rule sits in at least two independent layers.
- Each piece states its rules under "Held by:", naming the script, hook, setting or gate move that holds each one. A rule with only prose behind it is not finished.
- A `SKILL.md` has at most 150 lines and 2,000 words, and a description of 300 characters at most. References have at most 300 lines each. The `check-skills` lint from P7 holds these limits.
- Each skill has at least three eval cases (normal, edge, refusal), committed as the first commit of its piece, before the skill text. This mirrors the judge-first rule for project pieces.
- Every script follows principle 8: no prompts, `--help`, JSON on stdout, distinct exit codes, idempotent, `--dry-run` where it changes state, and errors that name the next command. The contract test from P1 runs each script marked as an agent script.
- Text from issues, comments and the web reaches a session only inside a marked data block in its brief. P12 builds and tests this for every brief.

### What the core refuses until a later piece lands

The ready gate (P14) refuses a piece that needs something the core does not hold yet, with a `next:` line naming the later piece. So no piece runs without its checks.

- A measurement judge, or a spec marked "route open": refused until L7 brings the hypothesis list and the held-out twin.
- A reference judge: refused until L8.
- A needs list holding a research or design question that calls for a crew: the agent settles it alone in `/shape` until L9.

### Borrowed code

- A piece that adapts a borrowed file changes its row in `BORROWED.md` in the same pull request. The row then says "adapted" and names what the file shed.
- A piece that only reads a borrowed file leaves its row alone. For example, P8 and P9 read `ready-lint.py`, and only P14, which retires it, changes its row.
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
- Borrowed files that no v1 piece has adapted yet keep `E4,E7,E9,F` and default mypy. That covers every row whose "Verbatim or edit" cell starts with "verbatim" or "edited". `tests/lint.sh` reads this list from `BORROWED.md`, so the list has one home. It runs the full set on every other Python file. A piece that adapts a file changes its row to "adapted", so the file moves to the full set in the same pull request.
- mypy runs with `--strict` on `kit/scripts/loop/` and new scripts, and with default settings on borrowed files not yet adapted.
- Python files with no `.py` name, such as the GitHub stand-in, are found by their shebang and linted under a temporary `.py` name, as the stage C build did.
- `tests/lint.sh` fails, with the install line, when ruff or mypy is missing. A check that did not run is never green.

### How tests run

GitHub hosted runners are off. Every test runs on this computer.

- `tests/run-all.sh` runs every `tests/*.sh` file and names each failure. It is the check before every merge.
- Unit tests use Python's own `unittest`, under `tests/unit/`. `tests/unit.sh` runs them all, so `run-all.sh` picks them up. One file runs alone with `python3 -m unittest tests/unit/test_<name>.py`.
- An end-to-end test is a `tests/<name>.sh` file that builds a throwaway project with `tests/lib/throwaway-project.sh`. It runs alone as `tests/<name>.sh`.
- The throwaway project uses the GitHub stand-in, a stand-in App credential and a Claude stand-in, so no test needs the network, a GitHub account, the real App or a model.
- Tests that call the real `claude` sit under `tests/smoke/` and scenario evals under each skill's `evals/`. Neither is in `run-all.sh`, because they cost money. They run by hand on a skill or model change. The stand-in does not enforce the sandbox, so every sandbox claim also gets a smoke case.
- A test that skips a step prints a visible "skipped" line and never counts the skip as a pass.
- `.github/workflows/v1-checks.yml` stays on manual dispatch only. It runs `tests/run-all.sh` and nothing else.

## The core

### P1. Foundations and test harness

**Goal.** Give every later piece a place to put code, a way to test it offline, every shared path, and the lint rules above.

**Test.** `tests/harness.sh` builds a throwaway project, opens an issue through the GitHub stand-in, runs a scripted Claude stand-in session that commits one file, and checks the commit and the stand-in's log. Unit tests cover `loop/paths.py` and `loop/cli.py`. `tests/lint.sh` and `tests/script-contracts.sh` each plant one fault in a copy and require a failure.

**Files.**
- New: `ruff.toml`; `tests/lint.sh`; `tests/unit.sh`; `tests/unit/test_paths.py`; `tests/unit/test_cli.py`; `kit/scripts/loop/__init__.py`; `kit/scripts/loop/paths.py`; `kit/scripts/loop/cli.py` (shared `--help`, `--json`, `--dry-run` and exit codes); `tests/lib/throwaway-project.sh`; `tests/stand-ins/fake-claude/claude` (replays a scripted attempt: files to write, commits to make, a hand-off to leave); `tests/stand-ins/fake-app/` (a stand-in App credential; the stand-in key is made at test time with `openssl genrsa` in the throwaway folder, and no private key is committed; P11 makes the GitHub stand-in check it); `tests/script-contracts.sh` (finds scripts marked `# contract: agent` and runs principle 8's checks on each); `tests/harness.sh`.
- `loop/paths.py` defines every shared path once, so no later piece edits it: the run folder and run record (`.agents/runs/<name>/run.json`), the lock file, the heartbeat, the mailbox, the piece records (`.agents/pieces/<n>/`), the command log, the worktrees folder, the policy file (`.agents/loop/policy.json`), the machine-local settings file (`.agents/loop/local.json`, git-ignored), the held-out folder outside the project, the App key file (outside the project, beside the held-out folder under the person's local data folder), and the installed kit folder (the plugin cache in a founded project, `kit/` in this repository).
- P1 provides the mutation helper only as it is. P6 and P7 write their mutations in their own test files, and neither changes `tests/lib/rule-shape.sh`.
- Changed: `tests/recipes.sh` gains a count assertion, so an empty `kit/recipes` fails (later note from the stage C3 review). `BORROWED.md` adds `tests/stand-ins/prepare/live-on-vercel.after-commit.sh` to its old-name list (same note).

**Held by:** the lint rules in `ruff.toml` and `tests/lint.sh`; principle 8 in `tests/script-contracts.sh`; "a check that did not run is not green" in `tests/lint.sh` exiting non-zero.

### P2. Spec format and shared parser

**Goal.** Write the versioned spec format once and read it with one parser that the gate, the lint, the needs list and the fingerprint all share.

**Test.** Unit tests parse every fixture spec: a full spec, a quick-path spec, a spec marked "route open", a spec with no markers, a spec with an unknown version, and the design's example issue. Each returns the same fields every time, and an unknown version is refused with a `next:` line. `tests/spec-parse.sh` puts the example issue into the GitHub stand-in and reads it back through `kit/scripts/spec.py show --json`.

**Files.**
- New: `kit/spec-format.md` (the one home for the format: markers `<!-- spec:start version=1 -->` and `<!-- spec:end -->`, field names, ID forms such as `FL-1` and `EC-1`, the quick-path field set, the coverage category list, the "route open" mark, the Changes field's way to name a new area, and the supported test runners); `kit/scripts/loop/spec.py`; `kit/scripts/spec.py` with `show` only; `tests/fixtures/specs/`; `tests/unit/test_spec.py`; `tests/spec-parse.sh`.
- Reads `section()` in `kit/scripts/gate.py` for the heading rules and copies none of it.

**Held by:** "one parser" in `loop/spec.py` being the only module that reads a spec block, which `tests/unit/test_spec.py` checks by searching `kit/scripts/` for any other reader of the markers.

### P3. Command guard hook and command log

**Goal.** Replace the text-matching state guard with a hook that parses each command, and log every command the agent runs, refuses or retries.

**Test.** Unit tests feed the hook every spelling in `kit/templates/blocked-commands.md` and the permission matcher's cases: `git -C . push origin main`, `env X=1 git push --force`, `sh -c "rm -rf x"`, `find . -delete`, `git reset --hard`, `gh issue edit 5 --add-label state:ready`, `gh api` label writes, `cat .env` in the main folder, and a write to a guarded path. Each is refused with a reason. `gh issue comment` and `gh pr comment` return "ask", not a pass. Harmless forms such as `git push origin feature` pass. Reading a worktree's throwaway `.env`, whose first line is the kit's throwaway marker, passes. A `.env` in the main folder is refused even when it starts with the marker. Reading the App key file, the held-out folder or the `gh` config, `gh auth token`, and `security find-generic-password` or `find-internet-password` are each refused. `tests/guard-hook.sh` runs the hook as Claude Code would, with JSON on stdin, in a throwaway project, and checks the command log line for a refusal, an ask and a pass.

**Files.**
- New: `kit/hooks/guard.py`; `kit/hooks/command-log.py`; `tests/unit/test_guard.py`; `tests/guard-hook.sh`.
- Adapts: `kit/templates/blocked-commands.md` (the kit's own paths, the old product name gone).
- P3 keeps every section heading and command list in `blocked-commands.md` that `tests/push-to-main-rules.sh` and `tests/merge-ask-rule.sh` read, so both stay green. It changes paths, the old product name and the hook name only. P10 changes the wording those two tests read, in the same pull request as the tests.
- The throwaway marker string lives in `kit/hooks/guard.py`. P12's `worktree.sh` writes the same string.
- Retires: `kit/scripts/state-guard.sh` and `tests/state-guard.sh`, replaced by the two tests above.

**Held by:** this piece is one of the two layers for push to `main`, force push, recursive delete, `git reset --hard`, hand-written `state:` and `needs-you` labels, reading real env files, writes to the guards, and posting in the person's name. The other layer is P10's deny and ask rules.

### P4. Secret scan

**Goal.** Stop a secret leaving the computer, in two places.

**Test.** Unit tests plant a key of each common kind and a high-entropy string in a staged change, and require a refusal that names the file, the line and the kind, never the value. `tests/secret-scan.sh` installs the pre-push hook in a throwaway project and requires a refused push. It then calls the scan the way the gate's push step will, on a commit range, and requires the same refusal.

**Files.**
- New: `kit/scripts/secret-scan.py` (stdlib patterns and entropy; it also runs `gitleaks` when that is installed, and says so when it is not); `kit/templates/githooks/pre-push`; `tests/unit/test_secret_scan.py`; `tests/secret-scan.sh`.

**Held by:** the git pre-push hook, and the gate's push step that P11 adds to `loop/github.py`. The design marks the gate's push step as Proposed; this plan adopts it.

### P5. New dependency check and supply chain settings

**Goal.** Check the age and licence of a new dependency before it is accepted, and turn on the package managers' own minimum-age and no-install-scripts settings.

**Test.** Unit tests diff two lockfiles for npm, pnpm and uv, find the added package, and judge it against a stand-in registry: too new is refused, an unknown licence is refused, an allowed one passes. `tests/dependency-check.sh` runs the check on a throwaway project with a planted lockfile change. The minimum-age setting differs by manager and version, so the test checks each template against the manager version on this computer and prints a visible "skipped" line when that version has no such setting.

**Files.**
- New: `kit/scripts/dependency-check.py`; `kit/templates/npmrc` (minimum release age, `ignore-scripts=true`); `kit/templates/uv.toml` (exclude newer, no build scripts where uv allows); `tests/stand-ins/fake-registry/`; `tests/unit/test_dependency_check.py`; `tests/dependency-check.sh`.

**Held by:** the package manager's own settings (first layer, before an install runs) and `dependency-check.py`, which the attempt gate in P16 calls (second layer).

### P6. New-test lint

**Goal.** Refuse the test smells a script can find reliably, the "yes" rows of the design's checks table that concern tests.

**Test.** Unit tests hold one planted example per rule, in Python and in TypeScript: no assertion, a skip marker added, `assert True`, a duplicate assertion, an `if` or loop in a test, `sleep`, a debug print, a mock of the project's own module, a call-count assertion, code that checks it is under test, a snapshot rewritten in the same change, a suppression comment, an empty `catch` or `except: pass`, and a debug leftover. Each fires, and a clean test passes. "Assertion roulette" and magic numbers are reported but never refuse. Each rule also gets a mutation test with `tests/lib/rule-shape.sh`.

**Files.**
- New: `kit/scripts/loop/newtest_lint.py`; `kit/scripts/newtest-lint.py`; `tests/fixtures/test-smells/`; `tests/unit/test_newtest_lint.py`; `tests/newtest-lint.sh`.
- Reads `kit/scripts/test-guard.sh` for its patterns. Does not change it.

**Held by:** the attempt gate (P16), which runs this lint on every attempt. The reviewer's list (P24) covers the "partly" and "no" rows.

### P7. Skills lint and plugin manifest

**Goal.** Make the 17 principles a free check on every commit, before any skill is written, and give the kit its plugin manifest.

**Test.** `tests/check-skills.sh` builds a good fixture skill and passes it, then mutates one rule at a time with `tests/lib/rule-shape.sh` and requires each mutation to fail. Every lint rule has its mutation:
- over 150 lines, over 2,000 words, a description over 300 characters (principle 3);
- a hard rule with no `Held by:` line (1); a copied gate table row, label name or exit code (2), read from a small list in `check-skills.py` that P11 points at `loop/states.py`;
- sections out of order (4);
- `disable-model-invocation: true` missing on `setup`, `run` or `maintain`, and a model-invoked description with no "Use when" clause (5);
- a nested or orphan reference, a link line with no condition word, a reference over 100 lines with no contents list (6);
- a shell block over three lines, a pipe into a state change (7);
- capitalised emphasis (9), and a warning for a "do not" with no positive instruction beside it;
- no `## Gotchas` section (10);
- a repeated paragraph or a banned synonym (11);
- a step with no `Done when:` line (12);
- `/what-now` or `/run` not starting with an `!` line that runs `gate.py report --json --brief` and a fallback line (13); P7 checks the shape only, and P10 owns the fallback wording;
- fewer than three eval cases (15);
- a date, version, model name or hash-and-digits number (16);
- a guard claimed only by the skill's own frontmatter (17).

`claude plugin validate` runs when `claude` is installed. When it is not, the test prints a visible "skipped" line and does not count it as a pass.

**Files.**
- New: `kit/scripts/check-skills.py`; `kit/glossary.md` (one word per concept, and the banned synonyms, such as "ticket" or "task" for piece and "stage" for state); `kit/.claude-plugin/plugin.json` (the plugin root is `kit/`, and skills live in `kit/skills/<name>/`); `tests/fixtures/skills/`; `tests/check-skills.sh`.
- Calls `kit/scripts/document-bloat.py` unchanged for repeated paragraphs.

**Held by:** `check-skills.py` for principles 1 to 7, 9, 11, 12, 13, 15, 16 and 17, and for the `## Gotchas` part of 10; `tests/script-contracts.sh` (P1) for principle 8; P12's command-line test for principle 14; the scenario evals for the rest of principle 10.

### P8. Spec lint and computed needs list

**Goal.** Judge a spec without running anything, and work out from it what the piece still needs and who can settle each need.

**Test.** Unit tests drive each need in the design's needs table: it appears when its field is missing and clears when the field is written. Lint unit tests cover required fields for both paths, coverage categories answered or "not applicable" with a reason, every ID traced to a test and every test to an ID, edge cases in "When ..., then ..." form with an example value, Limits with a number or "none", refused phrases, vague adjectives with no number, a numbered build-step list, and length limits. `tests/spec-lint.sh` puts three issues into the GitHub stand-in and runs `spec.py lint` and `spec.py needs --json` on each.

**Files.**
- New: `kit/scripts/loop/lint.py`; `kit/scripts/loop/needs.py`; `tests/unit/test_lint.py`; `tests/unit/test_needs.py`; `tests/spec-lint.sh`.
- Changed: `kit/scripts/spec.py` gains `lint` and `needs`.
- Reads `kit/scripts/ready-lint.py` for required sections, refused phrases, brief rules, length limits and exit codes, and drops the masterplan reading and the no-code special case. It does not change the file or its row.

**Held by:** the ready gate (P14), which runs the lint and refuses a non-empty needs list; the claim gate (P15), which runs the lint again on today's `main`.

### P9. Judge runner, fingerprint, evidence and held-out store

**Goal.** Run a judge the same way everywhere, tell an assertion failure from an error, take the fingerprint, keep the hash-chained evidence, and hold the hidden cases where only the gate can read them.

**Test.** Unit tests read recorded pytest, Vitest, Jest and Node runner reports from `tests/fixtures/runner-reports/`, so the tools need not be installed. Each reads as "failed on an assertion naming FL-1", "errored on import" or "passed". Another runner falls back to the exit code with a note. A check past its hard timeout is stopped and reported. A test checks that the runner list in `kit/spec-format.md` matches the runners `judge.py` reads (later note from the stage C1 review). The fingerprint changes when the spec block or the judge commit changes and not otherwise. The evidence chain refuses an edited entry. `tests/judge-runner.sh` builds a throwaway Python project with a failing acceptance test, runs it on `main` in a temporary checkout, and checks the result, the timeout and the evidence entry. It then stores two held-out cases through `heldout.py`, checks that nothing landed in git, and checks their fingerprint.

**Files.**
- New: `kit/scripts/loop/judge.py`; `kit/scripts/loop/fingerprint.py`; `kit/scripts/loop/evidence.py` (the piece record in `.agents/pieces/<n>/`, written only by the gate); `kit/scripts/loop/heldout.py`; `tests/fixtures/runner-reports/`; `tests/unit/test_judge.py`; `tests/unit/test_fingerprint.py`; `tests/unit/test_evidence.py`; `tests/judge-runner.sh`.
- Reads `kit/scripts/ready-lint.py` (the temporary checkout, the install, the time limits and the report reading) and `kit/scripts/gate.py` (`contract_hash`, `chain_of`, `read_record`, `write_record`). Changes neither file nor its row.

**Held by:** the gate running every judge itself (P14, P15, P16, P23), never trusting an agent's word; the held-out folder sits outside git and outside the project, read-blocked for builders by the sandbox (P10, tested in P12) and denied by the guard hook (P3).

### P10. Settings, sandbox and hook wiring

**Goal.** Write the deny and ask rules, the sandbox settings and the builder's own settings file, and wire the hooks, so every guard has its second layer.

**Test.** `tests/settings.sh` reads the two-layer table from `tests/fixtures/two-layer-rules.json` and checks that each rule has both holders: a deny or ask rule in the template and a refusal or ask from `kit/hooks/guard.py`, both matched offline with `tests/lib/permission-matcher.py`. It checks:
- the sandbox block (`strictAllowlist`, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`, bypass mode off);
- write-blocks on the installed kit folder, `.claude/`, `.github/workflows/`, the hooks and the policy file;
- the held-out folder read-blocked for builders;
- builders may write only their own hand-off file in the run folder, and nothing else under `.agents/runs/` or `.agents/pieces/`;
- the `gh` config and the keychain read-blocked for builders;
- the App key file and the machine-local settings file read-blocked for builders;
- auto memory off in the builder settings;
- the builder settings wire the hooks themselves, since builders get them through `--settings` and not through the plugin's `hooks.json`;
- the settings template wires the session start hook, and merging the template into a project's own settings keeps the person's rules (later note from the stage C2 review).

The adapted session-start test drives the hook after a compaction. The hook calls `gate.py report --json --brief`, and prints the template's fallback line when that fails. This test checks the fallback line; P11 checks the real report. `tests/smoke/sandbox.sh` shows with the real `claude` that a write-block and a read-block hold.

**Files.**
- New: `kit/templates/builder-settings.json` (passed with `--settings`; `dontAsk`, the `Skill` tool denied, no GitHub credential, sandbox auto-allow, hooks wired); `kit/hooks/hooks.json`; `tests/fixtures/two-layer-rules.json`; `tests/settings.sh`; `tests/smoke/sandbox.sh`.
- Adapts: `kit/templates/claude-settings.json`; `kit/scripts/merge-ask-rules.py` (pattern reused, kit paths updated); `kit/templates/merge-ask-rules.json`; `kit/scripts/session-start.sh` (drops the old check-up file, `AI_BUILD_KIT_TODAY` and the old product name); `tests/push-to-main-rules.sh`; `tests/merge-ask-rule.sh`; `tests/session-start.sh`.

**Held by:** the deny and ask rules and the sandbox (first layer) beside the guard hook (P3, second layer); "guards guard themselves" by deny rules and sandbox write-blocks, with the pre-run check (P13) as the second layer.

### P11. Gate: states, moves, labels and the App credential

**Goal.** Rewrite the gate as the only mover: seven states, fourteen moves, the `needs-you` flag, refusals with `next:`, the report the skills inject, and every GitHub call made as the gate's GitHub App when it exists. Before the App exists (it comes in the second half of `/setup`), a move that must act on GitHub (labels, comments, issues) never uses the person's sign-in. The gate makes every state move in the local piece record (`.agents/pieces/<n>/`), which is the truth for state until the App exists. It queues the label, comment and issue writes it cannot make in that record, and prints one `next:` line naming `gate.py sync`. The person may run `gate.py sync` with their own sign-in. That is the person acting, not the agent. Pieces that need a GitHub result to go on wait.

**Test.** P11 tests the table and the shared rules with stub check modules. Each later piece tests its own checks. Unit tests drive every one of the fourteen moves with a passing stub and a refusing stub, and require a move not in the table to be refused. They cover read-twice writes, a reason on every move back, the anti-circle rule on moves back to shaping only, the repeat counter of 3 on moves 7, 8 and 12, a gate-made spec change taking a new fingerprint, `gate.py answer` writing a late answer under Decisions and taking a new fingerprint, a second `state:` label refused, and a hand-changed label found by comparing it with the gate's own piece record (never by actor), reported and never undone. A unit test shows every GitHub call goes through `credential()`. With no App credential, each move that needs GitHub (a label, a comment, an issue) changes nothing on GitHub, never reads the person's `gh` sign-in or keychain, stops with a `next:` line naming the exact command for the person to run, and leaves the piece waiting. Every move still works in the piece record with no App, the queue fills, and the agent cannot run `gate.py sync` (the guard hook refuses it from an agent session). With the stand-in App credential the same moves go through as the App. `tests/gate.sh` drives one piece through capture, shaping and drop in a throwaway project with the GitHub stand-in and the stand-in App credential, and checks the labels, the needs written below the spec, the `needs-you` flag and the piece record. It also checks that the session start hook (P10) now prints the real brief report.

**Files.**
- New: `kit/scripts/loop/states.py` (the table of states and moves, as data); `kit/scripts/loop/moves.py` (each move calls its checks from `loop/gates/<name>.py`; a move whose checks are not installed yet is refused with a `next:` line, so later pieces add a module and change no shared file); `kit/scripts/loop/github.py` (the `gh` wrapper, read-twice, one `credential()` function that reads the App's key path from the machine-local settings file and makes a short-lived App token; `credential()` signs the JWT by calling `openssl dgst -sha256 -sign <key>`, because the standard library has no RSA signing, and keeps the token in memory only; and the push step that runs `secret-scan.py` first); `kit/scripts/loop/gates/__init__.py`; `tests/unit/test_states.py`; `tests/unit/test_moves.py`; `tests/unit/test_github.py`; `tests/gate.sh`.
- Adapts: `kit/scripts/gate.py`, rewritten as a thin command line (`capture`, `move`, `drop`, `answer`, `comment`, `report`, `labels --create`, `branch`; `comment` posts as the App) over the modules above. It sheds the old label list, the sub-state markers, the checkpoint assumptions, the always-person review stub and the `.agents/tools/` paths. May extend `tests/stand-ins/fake-github/gh` where a move or the App token needs it.
- Retires: `tests/gate-script.sh`, replaced by the tests above, and `tests/frozen-bar-rehearsal.sh` and `tests/test-strength-rehearsal.sh`, since they drive the old gate's evidence commands. P16 carries their cases forward.
- The gate alone writes `.agents/pieces/<n>/`. The run script (P21) alone writes `run.json`.
- Labels: the gate creates its own set (`state:` for each state, `needs-you`, `type:feature`, `type:bug`, `type:chore`). The old labels stay until removal stage G retires them.

**Held by:** the gate refusing any move outside the table; hand-written labels refused by P3's hook and P10's deny rules, and reported by `gate.py report`; the kit acting on GitHub only as the App by `credential()`, and before the App exists not acting on GitHub at all but waiting for the person, and builders holding no credential (P10, P12); the App key read-blocked for builders by the sandbox (P10) and refused by the hook (P3); the push step's secret scan beside P4's pre-push hook.

### P12. Worktrees, sessions and the builder hand-off

**Goal.** Give each piece its own worktree with throwaway values, start every non-interactive session with one exact command line, and give builders one way to hand back.

**Test.** Unit tests assert the exact `claude -p` command line (principle 14): the brief passed by file, `--settings` with the builder settings, `--permission-mode dontAsk`, no `--bare`, `--max-budget-usd` only when the caller passes a cap, the working folder the worktree, and an environment with no GitHub token. A unit test checks that issue, comment and web text in every brief sits inside a marked data block. A stand-in builder session started by `sessions.py` gets settings that read-block the held-out folder; the real-sandbox version is in `tests/smoke/`. `tests/kit-owns-worktrees-rehearsal.sh` (adapted) opens a worktree, finds throwaway values with the kit's marker line in place of the real env file, and removes the worktree without force. It regains two assertions lost in stage C2: a file in `.agents/tmp` never reaches git, and a walk-through picture outlives the worktree. `tests/handoff.sh` runs the Claude stand-in through each of the five hand-offs and checks the file the run will read, including the decisions the builder made alone, carried on "done".

**Files.**
- New: `kit/scripts/loop/sessions.py` (starts any `claude -p` session: builder, test-list writer, trim, reviewer); `kit/briefs/builder.md` (the fixed brief template; it reads the gate-kept attempt log that P16 writes); `kit/scripts/handoff.py` (done, with any decisions made alone; bar is wrong; needs the person, which writes the question and returns at once; blocked by environment; gave up); `tests/unit/test_sessions.py`; `tests/handoff.sh`; `tests/smoke/held-out-blocked.sh`.
- Adapts: `kit/scripts/worktree.sh` (drops linking the real `.env`, writes throwaway values from `.env.example` under the marker line, sheds the old product name); `tests/kit-owns-worktrees-rehearsal.sh`.

**Held by:** builders holding no GitHub credential, by the scrubbed environment here and the sandbox read-blocks on the `gh` config and the keychain in P10; "no real env file" by the throwaway values here and the deny rule and hook in P10 and P3; "outside text is data" by the data blocks here and the test that checks them.

### P13. Pre-run check and policy file

**Goal.** Refuse to start a run, with the reason, unless every guard, the policy, the computer and `main` are fine.

**Test.** `tests/pre-run-check.sh` takes each guard away in turn in a throwaway project and requires a refusal that names it: the guard hook, a deny rule, the sandbox, the pre-push hook, a changed file in the installed kit folder, a missing policy, a malformed policy value (named by key), a lock held by another run, the computer on battery, sleep not held off, too little free memory, low disk, and a red `main`. Each computer reading comes from a stand-in for `pmset`, `vm_stat` and `df`. With the stand-in App credential and every other guard in place it passes. It names which half of `/setup` is missing. The App is the one guard that only unattended runs and pre-approved merges need. With no App credential, an attended local run passes. An unattended run and a pre-approved merge (`--merge-pre-approved`) are each refused, and the refusal names the second half of `/setup`, where the App is created. The check tells an attended run from an unattended one by the flag that `run.py` passes it (P21). On an API key with no spend caps it refuses. With `origin` set to the kit's own repository it refuses. With every first-half guard and no App credential, and no second half, an attended run passes. It prints one notice, "the second half of `/setup` is missing: the run stops if this computer sleeps or this session closes, and GitHub steps wait for you", and exits 0. A missing guard is always a refusal, and the refusal names the half of `/setup` that installs that guard. An App key file inside the project, or readable by other users, is refused. "Main is green" means the policy's test command passes on a clean checkout of `main`, since GitHub Actions stay off and the App needs no check permissions. "A changed file in the installed kit folder" compares with the plugin's own version record in a founded project, and with `git status` on `kit/` in this repository. Unit tests cover the policy schema and its defaults. The `--bare` check is P21's, since it needs the run script.

**Files.**
- New: `kit/scripts/loop/policy.py`; `kit/templates/policy.json` (builder cap 3, attempt limit 3, review rounds 2, question cap 5, research age limit, length limits, pull request size limit, billing mode and caps); `kit/scripts/pre-run-check.py`; `tests/stand-ins/fake-computer/`; `tests/unit/test_policy.py`; `tests/pre-run-check.sh`.
- Adapts: `kit/scripts/check-tooling.sh` (tools and sign-in, the kit repository guard, and `openssl` now required; sheds the old product name), which the pre-run check calls; `tests/check-tooling.sh`.

**Held by:** this check is the second layer for "the guards stay in place" (P10 is the first). The policy file is protected from agents by P10's deny rules and P3's hook. The policy has no pre-approval key, so pre-approval can never become a standing setting.

### P14. Ready gate and test lists

**Goal.** Install the checks for move 2, including the two fresh test lists, the held-out check and the decision on individual review.

**Test.** Unit tests: each ready check refuses alone:
- needs not empty, or lint fails;
- the two test lists differ by spec ID;
- judge files not the first commit on the piece branch;
- a judge that passes on `main`, or errors instead of failing on its assertion;
- a must-stay-the-same check that fails on `main`;
- held-out cases missing from the store, or their fingerprint missing from the spec or different from the store;
- a sensitive area with no acceptance;
- a blocked-by link to nothing, or a cycle;
- an area missing from the map;
- a measurement judge, a reference judge, or a "route open" mark, each with a `next:` line naming L7 or L8.

The must-look reasons are exactly five, and only the gate writes them: a sensitive area (the spec's Sensitive areas), an irreversible data change (a `Not reversible:` mark in Changes to current behaviour), a new dependency (a `New dependency:` mark), a security change (a `Security:` mark), and the person's own mark, a `must-look` line the person writes in the spec's Decisions. Each one marks the piece for individual review. The gate passes the reasons to the move as a `must_look` field on the passing result, and `loop/moves.py` records them on the move into ready. A must-stay-the-same check is a `Check:` line in the spec's Must stay the same field. In a project with no test runner, a quick-path scaffold piece passes when its judge is that the test command runs, and any other piece is refused. `tests/ready-gate.sh` shapes one piece in a throwaway project with a scripted spec, a failing test and two held-out cases, runs the two test-list sessions with the Claude stand-in, and takes the piece to ready.

**Files.**
- New: `kit/scripts/loop/gates/ready.py`; `kit/scripts/loop/areas.py`; `kit/scripts/loop/testlists.py` (plans and runs the two sessions through `loop/sessions.py`); `kit/scripts/test-lists.py` (the command line over it: runs two fresh sessions and compares their lists by spec ID); `kit/briefs/test-list.md` (issue text only inside a marked data block); `kit/templates/area-map`; `tests/unit/test_ready.py`; `tests/unit/test_areas.py`; `tests/unit/test_testlists.py`; `tests/ready-gate.sh`.
- The area map is the file `docs/area-map` in the project, in the style of a CODEOWNERS file: one `<pattern> <area>` line each, the last match wins, and no prose. `kit/scripts/loop/paths.py` gains one `area_map` property that returns it, and it stays the one home of shared paths. `kit/templates/area-map` is the template. `loop/areas.py` reads the file.
- Changed: `loop/moves.py` records the `must_look` reasons and any extra record entries that a passing result carries. `loop/spec.py` reads the `Check:` lines of Must stay the same and the three marks of Changes to current behaviour, and writes the `Fails today:` line. `kit/spec-format.md` says so. `kit/templates/working-rules.md` points at `docs/area-map`.
- Adapts: `kit/scripts/area-map.py`, now a command line over `loop/areas.py`, shedding the old product name and the `## Areas` section of `docs/working-rules.md`; `tests/area-map-rehearsal.sh`. Both rows in `BORROWED.md` become "adapted".
- Retires, with `git rm` on the named files: `kit/scripts/ready-lint.py` and `tests/ready-lint-rehearsal.sh`, whose parts now live in P8 and P9. Their rows move to the Retired table. Two callers lose only the lines that place it: `kit/scripts/bootstrap-project.sh` and `kit/scripts/place-plan-helper.sh`. Their rows in `BORROWED.md` say what changed. The docstrings of `kit/scripts/loop/lint.py` and `kit/scripts/loop/github.py` stop naming the retired file.

**Held by:** the gate refusing move 2 unless every check passes; the sensitive-area acceptance held by the ready gate and quoted on the issue; the held-out cases by the gate-only store (P9) and this check.

### P15. Claim gate and research check

**Goal.** Install the checks for move 4: nothing changed since ready, and every research finding still holds.

**Test.** Unit tests: each claim check refuses alone: fingerprint changed by an edit the gate did not make; a research finding whose file fingerprint changed; an outside finding past the age limit or on a changed version; lint fails on today's `main`; the judge now passes on `main`; a must-stay-the-same check now fails on `main`; a relied-on file changed since ready; a blocker not done and not built earlier in this run; already building; an area in use by a running piece; no free slot. A finding that needs a fuller refresh sends the piece back to shaping with that need, by move 3 (decision 9, until L9). `tests/claim-gate.sh` takes a ready piece in a throwaway project, edits its spec by hand, and requires the claim to send it back to shaping with the reason.

**Files.**
- New: `kit/scripts/loop/gates/claim.py`; `kit/scripts/loop/research.py` (the quick check of every finding); `tests/unit/test_claim.py`; `tests/claim-gate.sh`.
- Changed: `loop/spec.py` gains `parse_finding`, which reads one research finding (source, date, what it rests on). `kit/spec-format.md` writes the finding shape in its Research section. The ready gate records a `relied-on` entry, the files that `Relies on:` names with their fingerprints, because it recorded nothing the claim could read. `loop/moves.py` makes move 3 itself when a claim refusal carries `send_back`, so the reason, the anti-circle rule and the open question are the gate's own. No lint rule is added: the needs list already holds a finding that lacks a source, a date or a basis. The slot count is `builder_cap` in the policy file, which exists already.
- Settled alone: a fault of the spec or the code under it (fingerprint, lint, a research finding, a relied-on file, a judge that no longer fails) sends the piece back. A fault of the moment (a blocker, a piece already building, an area in use, no free slot, a must-stay-the-same check red on `main`) leaves it ready. The run lists the pieces it built earlier with `--option built_earlier=<issue numbers>`.

**Held by:** the gate refusing move 4 unless every check passes; the fingerprint, checked again at every claim and at every attempt (P16).

### P16. Attempt judging: frozen bar and judges

**Goal.** Install the checks for move 5, in the design's order, so the gate judges every attempt and catches gaming, and give the frozen bar its first layer in each attempt's settings.

**Test.** Unit tests plant each anti-gaming case and require a failed attempt, logged as possible gaming where the design says so: a changed judge file, a removed or skipped test, a loosened assertion, a raised timeout, a retry added, a held-out result much worse than the visible one, a new test that fails the new-test lint, a must-stay-the-same check gone red, a diff outside the declared touches, an unplanned new dependency, and a fingerprint changed since the claim. The touches check reads the area map from the piece's base commit, never from the builder's tree. The attempt's settings deny a write to each bar file. A clean attempt passes. A fault of the gate's own (a git error, a missing record, an unreadable file, an empty or changed held-out store, a judge that cannot run) is a refusal with a `next:` line that counts no attempt, and a test plants each one. `tests/attempt-gate.sh` runs three scripted attempts on one piece in a throwaway project: one that edits the bar, one that special-cases the visible test and fails a held-out case, and one honest pass. It checks the attempt log after each.

**Files.**
- New: `kit/scripts/loop/gates/attempt.py`; `kit/scripts/loop/bar.py` (the byte-for-byte check over the judge and everything it rests on: tests, fixtures, test settings); `kit/scripts/loop/attempt_log.py` (the gate-kept attempt log: each attempt's result and findings, which the next builder's brief reads); `tests/unit/test_attempt.py`; `tests/unit/test_bar.py`; `tests/attempt-gate.sh`.
- Changes `kit/scripts/loop/sessions.py` (P12) so each attempt gets its own settings file: the builder template plus deny rules and sandbox write-blocks on every path `bar.py` lists for that piece. `tests/unit/test_sessions.py` gains the cases.
- Changes `kit/scripts/loop/moves.py` and the note in `kit/scripts/loop/gates/__init__.py`: a refusal of move 5 that carries an `attempt` entry makes the gate write it to the piece record and keep the piece in building; one that also carries `send_back` makes the gate send the piece to shaping by move 6, through the same code as the claim's send back. `tests/unit/test_moves.py` gains the cases.
- Adapts into `loop/bar.py`: the seven kinds of bar change from `kit/scripts/bar-guard.sh` and `kit/scripts/test-guard.sh`, without the named-change escape, since any bar change is now a failed attempt.
- Retires, with `git rm` on the named files: `kit/scripts/bar-guard.sh`, `kit/scripts/test-guard.sh` and `tests/bar-guard-rehearsal.sh`. Their rows move to the Retired table in `BORROWED.md`. Each case of the retired rehearsals, including `tests/frozen-bar-rehearsal.sh` and `tests/test-strength-rehearsal.sh` retired by P11, is read from git history and carried into the new tests. The cases of `tests/test-strength-rehearsal.sh` drive mutation testing, which waits for L5.
- Core judge kinds: acceptance tests and reproducing test. Mutation testing at the gate (Proposed) is deferred to L5.

**Held by:** the frozen bar by two layers: the per-attempt deny rules and sandbox write-blocks (first) and the gate's byte-for-byte check (second); held-out cases by the gate-only folder (P9, P10); touches by the area map read from the base commit; the dependency check by the package manager's own settings (P5, first) and `dependency-check.py` run by the attempt gate (second); the fingerprint by the claim gate (P15) and the attempt gate (second).

**Settled alone (6 October 2026).**
- The gate checks in the design's order: the fingerprint, then the bar. A changed fingerprint or bar stops the checks there, since a judge run against a changed bar means nothing. A changed fingerprint is a failed attempt, not logged as gaming. Then it reports every fault of the visible judge, the held-out cases, the new-test lint, the must-stay-the-same checks, the touches and the dependencies together.
- The bar is read between the base commit (the parent of the judge commit, or the commit the fingerprint names for a scaffold piece) and the head of the piece branch. The gate judges commits only. A tracked change nobody committed in the piece's worktree is a refusal, so a pass is never given for work the gate did not see.
- The first layer lists exact files: the judge files, and each test, fixture, snapshot, tool-settings file and guarded file the base holds. A new file is not on it, so a builder may add tests. `pyproject.toml`, `setup.cfg` and `tox.ini` are not on it, since a builder may add a dependency there. The gate's check reads only their tool sections.
- A held-out case is a test file with a line `held-out-path: <relative path>` in its first five lines. The gate lays each case over the head of the branch, runs the judge's command with the judge files swapped for the case, and runs the cases only when the visible judge passed. The Command must name its judge files. A result is "much worse" when half or more of the hidden cases fail while the visible judge passes: that is logged as possible gaming. Fewer failures still fail the attempt. The log says how many hidden cases failed and never names or shows one.
- The attempt log is `attempt` entries in the keyed piece record, not a second file, so it is as hard to forge as the rest. Attempts count from the last move out of shaping, like the repeat counter. The attempt that uses the last of `attempt_limit` carries the send back, with every attempt's findings as the reason.
- `dependency-check.py` exit 3 (a new package is refused) is a failed attempt. Exit 4 and any answer the gate cannot read are refusals that count no attempt. A new package with no `New dependency:` mark in the spec is an unplanned dependency, a failed attempt.

### P17. Records checks and project templates

**Goal.** Hold the records model by checks: every fact in one home, under its line limit, with no drift that a script can find.

**Test.** Unit tests: `AGENTS.md` over 150 lines or a section over 12 fails; `CLAUDE.md` that holds more than the import fails; a path or command that `AGENTS.md` or the overview names and that does not exist fails; `docs/overview.md` over 100 lines fails; an overview area that the area map lacks, an area of the map that the overview lacks, or a sensitive flag that is not `yes` or `no`, or a sensitive area with no boundary, fails; an area doc over 300 lines or missing fails; a tracked file in no area fails; a closed piece (named by `--closing`) with no changelog entry fails; a repeated paragraph fails. The sensitive flag lives in the overview's area table, and the area map holds no prose, so the two agree on area names only. `tests/records-check.sh` founds a throwaway project from the templates and requires it to pass, then plants each fault in a clone and requires that fault's rule alone. It also runs the run lines of the shipped `checks.yml`. `tests/check-skills.sh` stays green after the `document-bloat.py` change.

**Files.**
- New: `kit/scripts/records-check.py`, a thin command line over `kit/scripts/loop/records.py`; `kit/templates/AGENTS.md` (the skeleton, under 150 lines); `kit/templates/CLAUDE.md` (imports `AGENTS.md` only); `kit/templates/overview.md`; `kit/templates/docs-README.md`; `kit/templates/CHANGELOG.md`; `tests/unit/test_records_check.py`; `tests/records-check.sh`.
- Adapts: `kit/scripts/document-claims.py` (it now reads `AGENTS.md` and the overview too) and `kit/scripts/document-bloat.py` (it reads `AGENTS.md`, and `--repeated` prints only the repeats), both called by `records-check.py`; `tests/document-read-rehearsal.sh`; `tests/document-bloat-rehearsal.sh`; `kit/templates/checks.yml`, now the project's own check file. It fetches the kit at the version `{{KIT_REF}}` names, runs `records-check.py`, and runs the policy's `test_command`, without the old product name. `tests/area-map-rehearsal.sh` loses its case for the old `checks.yml` step, which `tests/records-check.sh` now covers.
- Adapts `kit/templates/working-rules.md` into the `AGENTS.md` template, and retires it with `git rm`. `bootstrap-project.sh` still reads the old template until P19 and P20 replace it.

**Held by:** `records-check.py`, run by the project's `checks.yml`, by the pre-run check's "main is green" (through the policy's `test_command`), and in the final combined check (P23, which passes `--closing` for each piece the merge closes); the gate refusing a merge whose named doc the pull request did not change (P26).

### P18. `/shape`

**Goal.** Capture an idea in the person's words, or shape a piece until the ready gate accepts it.

**Eval cases, written first.**
1. Normal: given a one-line idea in a fixture project, the gate's capture is called, questions come in a batch under the cap of five, each with why it matters and a recommended answer, held-out cases are written through `heldout.py` and only their fingerprint goes in the spec, and the ready move is called only after `spec.py lint` passes.
2. Edge: given a vague idea, no ready move is called, and the reply names the biggest need on the list.
3. Refusal: given an idea touching a sensitive area, the reply gives the risk notice and asks for the person's acceptance, and no ready move happens without it.
4. Triggering, since `/shape` is model-invoked: ten queries, five that should trigger and five near misses, three runs each, passing above a trigger rate of 0.5.

**Test.** `check-skills` passes on the folder. `tests/shape-skill.sh` drives the skill's helper scripts in a throwaway project: the duplicate search finds a closed issue with the same words and asks the gate to add the new words as a kit comment, signed by the App (with no App, the comment waits for the person with a `next:` line), rather than open a new issue; the dropped-piece search warns; held-out cases land in the store and never in git or the issue.

**Files.**
- New: `kit/skills/shape/SKILL.md` (150 lines at most); `kit/skills/shape/references/questions.md`; `kit/skills/shape/references/quick-path.md`; `kit/skills/shape/scripts/find-duplicates.py`; `kit/skills/shape/evals/`; `tests/shape-skill.sh`.
- Uses `kit/scripts/co-change.sh` unchanged to help fill the touches field.
- `find-duplicates.py` has two commands. `search` reads open and closed issues only through `loop.github`, as the App, and also reads the gate's own record, so a dropped piece warns even with no App. With no App it reads nothing on GitHub and says so with a `next:` line. `comment <n>` calls `gate.py comment`, so the App signs it, or the gate queues it for `gate.py sync`. The gate refuses a comment on an issue it never captured, with a `next:` line, because capturing an old issue would put a state label on it.
- The cap of five comes from `question_cap` in the policy file.
- `kit/skills/shape/evals/` holds one file for each case: `normal.md`, `edge.md`, `refusal.md` and `triggering.md`. They need the real model, so `run-all.sh` does not run them.

**Held by:** "a need clears only when its answer is written" by the gate computing needs from the spec (P8, P11); the question cap by the policy file and the eval; "never ready without the gate" by move 2 (P14); the held-out cases by the gate-only store (P9) and the ready check (P14); the yes before posting in the person's name by the ask rule (P10) and the hook (P3), while kit bookkeeping goes through the gate as the App; "silence is never an answer" by the needs list, which only a written answer clears.

### P19. Trim pass

**Goal.** Run the last step of the build loop: remove or fold only, never a test, only code this piece added, in its own commit, thrown away if a check fails.

**Test.** Unit tests on `trim-check.py`: a trim that touches a test fails; one that changes a line the piece did not add fails; one that adds net lines fails; a clean fold passes. `tests/trim.sh` runs a scripted trim session on a passed piece in a throwaway project. The trim lives on a scratch branch. The gate re-runs the attempt checks straight after the trim. On green the piece branch fast-forwards to it. On red the scratch branch is left, the piece branch is unchanged, and the piece goes on untrimmed, with no attempt counted. The test also checks that unused-code and duplicated-code reports reach the trim session when the project has such tools.

**Files.**
- New: `kit/scripts/trim-check.py`; `kit/scripts/loop/trim.py` (the trim rules and the whole pass); `kit/briefs/trim.md`; `tests/unit/test_trim_check.py`; `tests/trim.sh`.
- Edited: `kit/scripts/loop/gates/attempt.py` gains `rerun`, the attempt checks on another branch's head with no attempt counted; `tests/unit/test_attempt.py` tests it.

**How it runs.** The pass uses P12's session code, so the trim brief holds the spec, the diff and the reports of the project's own tools (vulture, knip, jscpd, only if installed or set up, never installed by the kit) in data blocks, and the session settings deny a write to every test and bar file. A trim must be one commit that adds no file, touches no bar file, changes only lines the piece added (read against the piece's base commit) and adds no net lines. A git error or an unreadable file is a refusal that keeps the piece untrimmed.

**Held by:** `trim-check.py` and the attempt gate re-run straight after the trim (P16); the scratch branch, since `git reset --hard` is denied by P10 and refused by P3. Once the piece branch has moved on, a later failure (a trial join, review) cannot throw the trim away, because reset and revert are both forbidden. It goes back through the normal routes.

### P20. `/setup`, first half: shape and run locally

**Goal.** Found a project, or meet an existing one, so the person can shape and run locally with every local guard in place. The gate's GitHub App is not made here. The maintainer decided on 6 October 2026 that it is created and installed in the second half of `/setup` (L1). Until then, any step that needs the agent to act on GitHub waits for the person, and unattended runs are not allowed.

**Eval cases, written first.**
1. Normal: in an empty fixture project, the skill runs the tooling check, writes the foundation files without overwriting anything, writes the gate's label list and the `next:` line for the person to create the labels (the gate cannot do it before the App exists), and captures the first piece locally as a quick-path scaffold and test runner piece.
2. Edge: with a missing tool, the first half stops with the install line and writes nothing else.
3. Refusal: run in a fixture whose `origin` is the kit's own repository, it opens no issue, asks for no App and changes no setting.

**Test.** `check-skills` passes. `tests/setup-first-half.sh` runs the setup script on an empty throwaway project and on one with existing code, settings and an `AGENTS.md`. It checks:
- no file overwritten, and the person's settings rules kept;
- `AGENTS.md`, `CLAUDE.md`, `docs/overview.md`, `docs/README.md`, the area map, `CHANGELOG.md` and `checks.yml` written from the templates;
- the hooks and the pre-push hook installed (later note from the stage C2 review);
- the ignore file covering the run folder, piece records, logs, worktrees and the machine-local settings;
- a default network allowlist for the detected language, with no `github.com` or `api.github.com` in it;
- no App step: the skill never shows the App manifest link, writes no key file and stores no App key path, and its closing message says the App comes in the second half of `/setup`;
- a GitHub step with no App (creating labels, opening an issue) changes nothing on GitHub, never uses the person's `gh` sign-in, and ends with a `next:` line naming the exact command for the person to run;
- with no `origin`, a stop with a `next:` line (the fixture has a stand-in `origin`);
- spend caps asked for when the billing mode is an API key;
- the free-plan warning on a private free repository (`setup.py` takes the plan and the visibility as flags the skill asks for, since it never reads GitHub before the App exists, so the GitHub stand-in needs no plan field);
- the policy written;
- the pre-run check passing for an attended run with no App, with the notice that the second half of `/setup` is missing, and refusing an unattended run and a pre-approved merge.

**Files.**
- New: `kit/skills/setup/SKILL.md`; `kit/skills/setup/references/founding.md`; `kit/skills/setup/evals/`; `kit/scripts/setup.py` (the steps the skill calls: `found`, `first-piece` and `github labels|issue`; idempotent, decided by what is on disk); `kit/templates/network-allowlist/` (one `<language>.txt` file per language: the package registry and toolchain hosts; `found` copies the detected language's hosts to `.agents/loop/network-allowlist.json`, which the run reads when it renders the builders' settings); `tests/setup-first-half.sh`.
- Adapts: `kit/scripts/bootstrap-project.sh` into `setup.py` (copy without overwriting; sheds the old skill-folder paths and plugin detection), then retires it with `git rm`. `setup.py` renders `{{KIT_DIR}}` (the installed kit folder, taken from the script's own place) and `{{KIT_REF}}` through the render function of `merge-settings.py`, and merges the settings with that script's handler. It writes the plugin's version record with `write_record()` when the kit is a plugin install and has none. The skill finds the scripts with `${CLAUDE_PLUGIN_ROOT}`, which Claude Code substitutes in a skill's text, because a founded project has no `kit/` folder; `kit/templates/gitignore`; `kit/templates/piece-issue.yml` (v1 fields, filing into shaping).
- Retires: `kit/scripts/place-plan-helper.sh`. v1 runs its scripts from the plugin folder, so nothing is copied into a project to refresh (later note from the stage C2 review).

**Held by:** the guards installed here are held by P3, P4, P10 and P13; GitHub steps before the App by `credential()` (P11), which stops with a `next:` line and never uses the person's sign-in; unattended runs by the pre-run check (P13); "founding never stops on a nice-to-have answer" by `setup.py` writing an open question instead; the first piece's judge by the ready gate's empty-project exception (P14).

### P21. Run loop

**Goal.** Run the pieces the person picked as a plain script: plan, claim, build attempt by attempt, route each outcome, keep the run record, and resume after a crash.

**Test.** Unit tests on ordering: dependencies first, serial chains shown first, no two pieces in one area at once, slots sized from free memory and capped by policy. Unit tests on routing: each hand-off and gate result goes to its one move (5, 6, 7, or stay), with attempts counted as the design's outcomes table says, and "no real improvement" decided from judge results. A unit test refuses a run whose session command line carries `--bare`, through a check `run.py` adds to `pre-run-check.py`. `tests/run-loop.sh` runs five ready pieces in a throwaway project with the Claude stand-in: one passes first time, one fails then passes, one says the bar is wrong, one needs the person, and one is blocked by its environment. It then kills the script mid-run, starts it again, and checks that finished work is not redone. Before the App, the run is attended and every piece that needs a GitHub action parks as waiting for the person, with the `next:` line in the run record, while pieces that need none carry on. `--unattended` with no App is refused by the pre-run check. A stop signal sends the building piece back to ready with its branch kept. Reaching a spend cap, per piece or per run, parks the run until the person answers.

**Files.**
- New: `kit/scripts/run.py` (flags `--pieces`, `--merge-pre-approved`, `--plan`, and `--unattended`, which the second half's launchd job sets and which the pre-run check refuses without the App); `kit/scripts/loop/run/__init__.py`; `kit/scripts/loop/run/plan.py`; `kit/scripts/loop/run/attempts.py`; `kit/scripts/loop/run/record.py` (the run record, the heartbeat, the lock file and the spend per piece and per run); `kit/scripts/loop/run/summary.py` (the morning summary, with every decision made alone, the builders' included); `tests/unit/test_plan.py`; `tests/unit/test_routing.py`; `tests/run-loop.sh`.
- Also new: `kit/scripts/loop/run/gateway.py` (the calls to `gate.py`, `trim-check.py` and `worktree.sh`; every reply keeps the exit code, so silence is never a pass) and `kit/scripts/loop/run/engine.py` (the loop); `tests/unit/test_record.py`, `tests/unit/test_summary.py` and `tests/unit/test_pre_run.py`.
- Changes `kit/scripts/pre-run-check.py` (P13): the `--bare` check (the command line `run.py` passes as `--session-command`, the one `loop.sessions.build_command` makes, and the `CLAUDE_CODE_SIMPLE` switch, which is `--bare` in the environment), and one rule for an empty project. With no `test_command` in the policy, `--pieces` naming only the quick-path scaffold piece passes with a notice that `main` was not tested. Any other run, a missing piece or a red `main` is still refused. `tests/pre-run-check.sh` covers both.
- Changes `tests/stand-ins/fake-claude/claude`: `--version`, one script for each piece folder (`FAKE_CLAUDE_DIR`), a `sequence` of sessions, `sleep`, `cost_usd` and `exit_code`. Old scripts work as before.
- Rules the run keeps, settled while building it:
  - Slots are `1 + (free memory - min_free_memory_mb) / 1024 MB`, at least 1 and at most `builder_cap`; unknown free memory gives 1. They are sized once, when the run starts.
  - A piece that has an issue, with no App, waits for the person: the run does not ask the claim gate, and the run record holds the `next:` line (`gate.py sync`). A piece with no issue goes on, and its queued GitHub steps are named in the run record.
  - A claim refusal that keeps the piece ready (no slot, an area in use, a blocker) waits and is tried again when another piece finishes. A piece still refused when nothing runs any more ends the run as `waiting`, with the reason. A refusal that sent the piece back (move 3) ends as `sent-back`.
  - A gave-up attempt, and a session that left no hand-off after a clean exit, go to the gate for move 5, so the gate's attempt log is the only count. A session that failed and left no hand-off goes back to ready by move 7 and counts nothing.
  - "No real improvement" is two failed attempts in a row that name no fewer failing spec IDs and no fewer other faults. An attempt logged as possible gaming is never an improvement.
  - Either spend cap parks the run, not only the piece: no new session starts, the sessions in flight end their attempt, the run record says `parked`, and the `next:` line names the policy keys. Started again with the same name, the run goes on from its record, and parks again until a cap is raised. Each session gets `--max-budget-usd` set to what is left under the smaller cap.
  - A stop signal ends the sessions of this run, sends each building piece back to ready by move 7 with its branch and worktree kept, and exits 3.
  - A dependent piece is claimed with `built_earlier` naming the issues of the pieces built in this run. Stacking its branch on the branch of its dependency is the integration loop's (P23); this piece cuts every branch from `main`.
- `run.py` calls `loop/run/watch.py`, `loop/run/inbox.py`, `loop/run/integrate.py`, `loop/run/review.py` and `loop/run/pull_request.py` when they exist, so P22 to P26 add modules and do not edit it. `run.py` handles a stop signal; P22 handles the mailbox. A module defines `run_hook(context, event, **data)`, and the engine calls it for the events `start`, `tick`, `session-ended`, `piece-built`, `built-all` and `run-end` (`loop/run/__init__.py` lists what the context holds). A hook that raises is written to the run record as a problem, and the run then ends with exit code 1.

**Held by:** attempt limits by the run script counting from the gate's attempt log (P16); the lock file by `record.py` and the pre-run check (P13); `--bare` by the pre-run check and P12's command-line test; spend caps by `--max-budget-usd` on each session and the run total in `record.py`; every move by the gate (P11), never by the script writing labels.

### P22. Stuck detection, usage limits, the mailbox and answers

**Goal.** Stop a clearly stuck attempt, wait out a usage limit without counting it, obey pause, continue and stop, pick up the person's answers from GitHub comments, and handle the run-level real stops.

**Test.** Unit tests feed recorded builder output: the same error three times, a change undone and redone, a test past its hard timeout. Each stops the attempt and counts it. A usage-limit message pauses the piece as waiting for reset and counts nothing. Run-level stops: two environment failures in a row on different pieces, the same refused command in two pieces, and the same failure across several pieces. Each notifies once (a log line and the run record until L3) and the run carries on with independent work. `tests/watch-and-mailbox.sh` writes pause, continue and stop into the mailbox during a stand-in run and checks the run record and the tokens recorded per piece. `tests/answers.sh` posts an answer as a comment in the GitHub stand-in (this path needs the stand-in App credential; with no App, `inbox.py` reads nothing from GitHub and the person's answers come through the mailbox and `gate.py answer`, and a unit test checks this), on a parked piece and on a pull request made directly in the stand-in (the run's own pull request comes in P26): during the run it resumes the parked piece; after the run it goes in through `gate.py answer`, the piece goes to ready by move 7, and the person is told in a comment.

**Files.**
- New: `kit/scripts/loop/run/watch.py`; `kit/scripts/loop/run/mailbox.py`; `kit/scripts/loop/run/inbox.py` (reads new comments on parked pieces and on the run's pull request, as data); `tests/unit/test_watch.py`; `tests/unit/test_inbox.py`; `tests/watch-and-mailbox.sh`; `tests/answers.sh`.

**Held by:** the run script, which sees the builder's output; the hard timeout on every judge run (P9); answers written into the spec only by the gate (`gate.py answer`, P11), which re-fingerprints.

### P23. Integration loop

**Goal.** Join each built piece to the combined branch as a trial, move the branch only on green, name the culprit on red, then commit the docs and changelog and run the final combined check.

**Test.** `tests/integration-loop.sh` is the design's end-to-end case. Two pieces pass alone and clash together. The clash is found at the second trial join, the trial is thrown away, the combined branch never moves, the culprit goes back to building with the clash written on it, and the run carries on. Further cases:
- a merge conflict goes back the same way and no agent resolves it;
- a planted flaky test: on a red trial the gate runs the same commit once more, a different result marks the check flaky, a worth-knowing item and never a pass;
- a resumed run reads the `Piece:` trailers and does not join twice;
- a piece leaving after it joined causes a rebuild from `main` under a fresh name, with no revert and no force push;
- a dependent stacks on its dependency's branch, and an isolated piece follows the same steps on its own branch;
- a piece that names a new area in its Changes field gets that area added to the map and the overview in the docs commit;
- held-out cases are copied in only at the final check;
- the secret scan runs before each push.

**Files.**
- New: `kit/scripts/loop/run/integrate.py`; `kit/scripts/loop/run/docs_commit.py` (applies each piece's Added, Changed and Removed lines and any new area to the overview, area map and area docs, and folds one changelog entry per piece); `tests/integration-loop.sh`.
- Adapts: `kit/scripts/bring-up-to-date.sh` (a merge commit, never a rebase; works on the combined branch; fixes its error message); `kit/scripts/fold-changes.py` (one entry per piece from its behaviour change); `tests/fold-at-merge-rehearsal.sh`; `tests/recheck-before-merge-rehearsal.sh`.

**Held by:** the gate re-running every joined piece's judges, must-stay-the-same checks and touches at each trial (P9, P16); flakiness judged by the gate re-running the same commit; no force push and no revert by P3's hook and P10's deny rules; the secret scan by P4 and the gate's push step.

### P24. Review loop

**Goal.** Have a fresh reviewer read only the specs and the combined diff, piece by piece, and turn every finding into a failing check, a shaping issue or a worth-knowing note.

**Test.** `tests/review-loop.sh` runs a stand-in reviewer that returns a scripted findings file. A failing-check finding sends its piece to building (move 8) with the new test joining the frozen bar and a written justification. A wrong-spec finding sends it to shaping (move 9). A finding left after two rounds sends only that piece to shaping with `needs-you` set, and the combined branch is rebuilt without it. The fingerprint of each piece is checked again before review. Unit tests check the findings schema (kind, gap kind, piece, evidence) and that the reviewer's command line passes no builder account.

**Files.**
- New: `kit/scripts/loop/run/review.py`; `kit/briefs/reviewer.md` (the reviewer's list holds the "partly" and "no" rows of the design's checks table, and the report split into worth stopping for and worth knowing); `tests/unit/test_review.py`; `tests/review-loop.sh`.

**Held by:** the reviewer's isolation by `sessions.py` (P12) passing only specs and diff; the round cap by the policy file and `review.py`; moves 8 and 9 by the gate.

### P25. `/run`

**Goal.** Start a run from a conversation: show the gate's report, ask the two questions once, run the pre-run check, and start the run script.

**Eval cases, written first.**
1. Normal: the pre-run check runs before the run script, and the skill starts the script rather than building anything itself (no edit to source files).
2. Edge: with no ready piece, the reply says so in one line and starts nothing.
3. Refusal: with a guard missing in the fixture, the reply names the missing guard and which half of `/setup` is missing, and the run script is never started.

**Test.** `check-skills` passes, including `disable-model-invocation: true` and the `!` injection of `gate.py report --json --brief` with its fallback line. `tests/run-skill.sh` checks the start command the skill uses: `run.py` under `caffeinate`, the two answers passed as `--pieces` and `--merge-pre-approved`, and "not pre-approved" by default.

The skill names the kit's scripts as `"${CLAUDE_PLUGIN_ROOT}/scripts/..."`, quoted, as the setup skill does. It runs the pre-run check and `run.py` each under `caffeinate -i`, because the check refuses a computer that nothing holds awake, and `run.py` runs the check before it starts its own `caffeinate`. The skill also asks for a last yes before it starts the run, chooses the run name (`--run`) and starts the script in the background, because the script prints only when the run ends. The frontmatter holds `disallowed-tools: Edit Write NotebookEdit`, so the skill cannot edit a source file. `tests/run-skill.sh` also checks that `--unattended` is absent from the start command by default, and drives the scripts in a founded throwaway project: a missing guard, no ready piece, a policy key for pre-approval, and an unattended or pre-approved run with no App.

**Files.**
- New: `kit/skills/run/SKILL.md`; `kit/skills/run/evals/`; `tests/run-skill.sh`.

**Held by:** the pre-run check (P13) refusing a missing guard; pre-approval asked per run and never stored, held by `run.py` taking it only as a flag and the policy schema having no such key.

### P26. Pull request and merge decision

**Goal.** Open one pull request grouped by piece with each piece's evidence, and merge only the exact tested commit, only when the person merges or every pre-approval condition holds.

**Test.** `tests/merge-decision.sh` in a throwaway project:
- the pull request body lists each piece with its judge result, held-out result, review verdict and worth-knowing items, and one `Closes` line per piece with no closing word anywhere else;
- a pull request past the policy's size limit is split, and each part holds whole pieces;
- an isolated piece gets its own pull request, and a dependent on it is based on its branch;
- a pre-approved run with every condition met merges with `--match-head-commit`, and a pre-approved run with a must-look piece waits;
- when `main` moves after the final check, nothing merges until the branch is brought up to date and checked again (move 12);
- a comment naming one piece sends back only that piece and rebuilds the rest (move 13);
- a pull request whose named doc did not change is refused;
- a merge the person makes after `main` moved is found by `gate.py check-main`, which the next pre-run check and the session start hook run when no run is going.

With no App credential, nothing is pushed or opened on GitHub: the run stops at the pull request step with a `next:` line naming the exact push and pull request commands for the person, and the pieces wait. A pre-approved merge with no App is refused before the run starts (P13).

**Files.**
- Changes `kit/scripts/gate.py` to add `check-main`.
- New: `kit/scripts/loop/run/pull_request.py`; `kit/scripts/loop/gates/merge.py`; `kit/scripts/closing-words.py` (scans title, body, commits and changelog entries); `tests/unit/test_merge.py`; `tests/merge-decision.sh`.
- May extend `tests/stand-ins/fake-github/gh` for `--match-head-commit` if it lacks it.

**Held by:** the gate (moves 10 to 13); "only the person merges unless pre-approved" by the run script's flag (P21) and, on a public or paid repository, a GitHub branch rule as a further layer; the merge ask rule in the settings template (P10).

### P27. Core end-to-end rehearsal

**Goal.** Prove the core works as one thing, from an empty project to a merge.

**Test.** `tests/e2e-core.sh`: an empty throwaway project goes through the first half of `/setup`, builds the scaffold piece, shapes one feature piece with acceptance tests and one bug piece with a reproducing test, and takes both to ready. It runs twice, once for each case.
- Before the App: the run is attended. The GitHub steps (labels, comments, the pull request) wait for the person, each with its `next:` line. The test runs those commands by hand against the GitHub stand-in, as the person would. An unattended run and a pre-approved merge are each refused, naming the second half of `/setup`.
- With the stand-in App credential, as the second half would leave it: the run is unattended, runs both pieces with the Claude stand-in, joins, reviews and opens the pull request as the App, and the person merges on the GitHub stand-in.

In both cases both pieces end done, the changelog holds two entries, and the records check passes. `tests/smoke/run-real.sh` does the same with the real `claude` and a real test App on a tiny project, by hand only. It covers the App path.

**Files.**
- New: `tests/e2e-core.sh`; `tests/smoke/run-real.sh`; `tests/fixtures/e2e-core/`.

**Held by:** nothing new. This piece proves the others hold together.

## Later pieces

These come after the core and are part of v1.0. Each gets its own plan entry, in the same shape, before it is built.

- **L1. `/setup` second half: walk away.** Creates and installs the gate's GitHub App (the maintainer's decision of 6 October 2026): guides the person through the manifest link and permissions, writes the key file to the App key path with mode 600, never inside the project, stores its path in the machine-local settings only, creates the gate's labels, and posts the comments that were waiting. The App manifest, `kit/templates/github-app.json` (this repository only, issues, pull requests and contents, no administration and no workflows), and `references/github-app.md` move here from P20. Tests: the stand-in App credential is accepted, the key file mode and place are checked, and the pre-run check then allows an unattended run. The first step of L1 syncs the queue as the App. From then on the gate writes labels directly. A label that differs from the piece record after the sync is reported and never silently overwritten. Tests: a queue filled before the App syncs as the stand-in App and leaves no entry; a label that differs from the record is reported and kept. It also runs the run script under launchd with `KeepAlive`; adds the watch, a launchd job that only checks the heartbeat is fresh; writes the recipe's network allowlist on top of the language default; adds Dependabot and pinned Actions in the project. The pre-run check then stops reporting a missing half.
- **L2. `/setup` second half: deployment.** Adapts the two recipes, their parts, `recipe-format.md`, `check-recipes.sh` and the host stand-ins; adds the post-deploy health check as a small GitHub Action and the automatic rollback, with a revert pull request, a bug issue and a "production is pinned" notification; puts the preview link in each piece's evidence.
- **L3. Notifications.** GitHub @-mentions by the App for the six moments, once each, and quiet hours from GitHub Mobile's working hours with held messages collapsed into one.
- **L4. `/what-now` and the run's board.** What is where, what needs the person, how a run is going, and what was decided alone, from the gate's report, with its order and cap of three. L4 also owns the run's board, since no core piece has one (P21 keeps only the run record and the morning summary). The board turns the build plan into a live dependency graph, from the pieces' dependencies and states in the run record and the gate's report, and redraws it whenever the plan changes. This is the maintainer's v1 requirement of 6 October 2026. Tests: a plan that gains or loses a piece, or changes a dependency, redraws the graph with no stale node, and each piece shows its state and any waiting `next:` line.
- **L5. `/maintain`.** Drift between records and code, code health with mutation testing where a tool is present (the gate's mutation check comes here too), change-fail and rework rates, stale branches listed and never removed, and kit updates. Findings become issues in shaping. Suggested every 2 weeks.
- **L6. The learning loop.** Evidence at run end and on every kickback, lesson candidates at two sightings, lessons as checks first, applied at the next run as their own commits, stale lessons offered for removal.
- **L7. Measurement judge and hypothesis list.** The metric command, the held-out twin, and the hypothesis list fixed before any attempt, for metric pieces and pieces marked "route open". The ready gate then stops refusing them.
- **L8. Fresh critic and outside critic.** A/B comparison in both orders for reference pieces, and Codex as an advisory outside critic when installed and agreed.
- **L9. Shaping crews and the fuller research refresh.** Several researchers or prototypes when the needs list holds a research or design question, the rule for researchers who disagree, and automatic re-research at claim time. This removes decision 9's interim rule.
- **L10. Well-defined checks for the trim pass**, researched from Matt Pocock's list (for example tautological tests).

### Proposed items not placed in the core

These are Proposed in the design. They are not in any core piece and wait for a later plan entry: back-off under memory pressure; one port and seeded data per builder; the walk-through with sample data; branch removal on merge and worktree removal after close; a parent issue closing with its last part; "the gate changes nothing when GitHub cannot be reached"; the overview line a risk acceptance makes untrue; `.claude/rules/<area>.md` path checks; and the first upload of a project not yet on GitHub.

## Decisions the maintainer made (decided)

**The GitHub App is created in the second half of `/setup`. Decided 6 October 2026.** The App is created and installed in the second half ("make it safe to walk away"), as the design says, and not in the first. Until then a project shapes and runs locally. Any step that needs the agent to act on GitHub waits for the person, and unattended runs are not allowed.

What follows from it:
- P20 drops the App step and its test lines. The App step moves to L1.
- The gate's credential function (P11) uses the App when it exists. Before then, a move that must act on GitHub (labels, comments, issues) never uses the person's own sign-in. It stops with a `next:` line naming the exact command for the person to run, and the piece waits. The stand-in App credential stays, for tests of the App path.
- The pre-run check (P13) allows an attended local run without the App. It refuses an unattended run, and a pre-approved merge, without the App, and names the second half of `/setup`.
- P21, P22 and P26 respect "waits for the person" for GitHub actions before the App. P27 tests both cases.
- The person's own `gh` sign-in is not used as a stand-in. That keeps four Decided rules whole: the pre-run check's App guard, the yes before posting in the person's name, the gate told apart from the person by identity, and the four pre-approval conditions. It also keeps the person's full token out of the run's process tree.

**The run's board shows a live dependency graph. Decided 6 October 2026.** The run turns the build plan into a live dependency graph on its board and redraws it whenever the plan changes. This is a v1 requirement. L4 owns it, because no core piece has a board.

## Decisions this plan made alone

The design did not settle these. Each is the choice that keeps every settled decision and is easiest to undo.

1. The plugin root is `kit/`, with `kit/.claude-plugin/plugin.json` and skills in `kit/skills/`. Removal stage D deletes the root `.claude-plugin/`, so the two never meet. In a founded project the kit runs from the plugin cache, and the write-blocks and the pre-run check name that path.
2. Python 3.10 and the standard library only, so the policy file is JSON.
3. The ruff rule set above. Borrowed files not yet adapted keep the old set, and the list is read from `BORROWED.md`.
4. Withdrawn. See the decision for the maintainer above.
5. The held-out folder sits outside the project, under the person's local data folder, keyed by repository. Its path lives in the machine-local settings file.
6. Builders hand back by running `kit/scripts/handoff.py`, a script their settings allow, not through a server. The sandbox lets it write its one file in the run folder and blocks every other write there and in the piece records.
7. Tests use a Claude stand-in and a stand-in App credential. Real sessions run only in `tests/smoke/` and scenario evals, by hand.
8. Core judge kinds are acceptance tests and reproducing test. The ready gate refuses measurement and reference judges and the "route open" mark until L7 and L8.
9. Until L9, a claim whose research needs a fuller refresh sends the piece back to shaping with that need. This is stricter than the Decided rule, which re-researches in place, and L9 removes it.
10. The first half of `/setup` writes a default network allowlist for the project's language, so the sandbox has one from the first run. It leaves out `github.com` and `api.github.com`. The second half adds the recipe's hosts.
11. The run record sits at `.agents/runs/<name>/run.json` and piece records at `.agents/pieces/<n>/`, both git-ignored, as the design proposed.
12. A trim lives on a scratch branch that only fast-forwards the piece branch when the gate's re-run straight after the trim is green. If that re-run fails, the trim is thrown away and the piece goes on untrimmed, with no attempt counted. A later failure cannot throw the trim away, since reset and revert are forbidden.
13. The gate's moves look up their checks in `loop/gates/<name>.py`, so later pieces add files and leave shared ones alone.
14. `/setup` writes the area map at founding. Later changes go through pieces: a piece names a new area in its Changes field, and the docs commit applies it. The touches check reads the area map from the piece's base commit, never from the builder's tree. The design left the writer "not settled".
15. The first half of `/setup` asks for spend caps when the billing mode is an API key, and the pre-run check refuses an API key with no caps.
16. A builder's `.env` holds throwaway values under a marker line. The guard hook lets a session read a `.env` with that marker and refuses the main folder's real one.
17. The person marks a piece for individual review with a `must-look` line in the spec's Decisions.
18. A merge the person makes after `main` moved is checked by `gate.py check-main`, run by the next pre-run check and the session start hook when no run is going.
19. Before the App exists, a GitHub step stops with a `next:` line and the piece waits. The plan did not settle where the waiting piece's state lives. Before the App, the gate makes every move in the local piece record, which is the truth for state, and queues the GitHub writes it cannot make. It prints one `next:` line naming `gate.py sync`, which only the person runs, and the guard hook refuses it from an agent session. L1's first step syncs the queue as the App, and a label that then differs from the record is reported, never overwritten. The run record and the gate's report show the waiting pieces. The pre-run check tells an attended run from an unattended one by a flag `run.py` passes.
20. The live dependency graph sits in L4, the `/what-now` piece, because no core piece has a board. The plan says on purpose that the graph arrives in v1.0 through L4 and not in the core. It reads the run record and the gate's report, so P21 needs no change to feed it.

## Where the design and the decisions file disagree

Most differences are earlier answers that a later decision on 5 October replaced. The design follows the later decision, and so does this plan.

1. Answer 17 says a red join is "confirmed by one re-check without it" and "taken out". The red-team fixes replaced this with trial joins in a scratch copy, and the design says there is no take-out step and no re-check.
2. Answer 18 and "Final three" name a Claude Code push notification with email as the fallback. The final research pass replaced this with GitHub @-mentions pushed by GitHub Mobile.
3. The meta-loop answers give the watch the jobs of restarting the run script, stopping stuck attempts and giving up after three restarts. The final pass moved those into launchd and the run script. The watch now only checks the heartbeat, and notification 6 is "heartbeat stale" rather than "the watchdog gave up".
4. Answer 11 says scratch files are removed before merge. The final pass keeps them in a git-ignored run folder, so nothing is removed.
5. Both documents say the first half of `/setup` lets the person "shape and run locally", and both say the pre-run check refuses unless the gate's GitHub App is in place, and the App comes from the second half. The plan first moved the App to the first half. The maintainer decided on 6 October 2026 that the App stays in the second half. Before it, a project shapes and runs locally, GitHub steps wait for the person, and unattended runs and pre-approved merges are refused. The plan follows the design again.
6. The design puts the network allowlist in the second half of `/setup`, but also turns the sandbox and its allowlist on for every agent session in v1. The plan resolves it with decision 10 above.
7. The design puts spend caps for an API key in the second half of `/setup`, but a local run on an API key needs them. The plan resolves it with decision 15 above.
