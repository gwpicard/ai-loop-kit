# Lessons from the first build

What the first build (5 to 13 October 2026) taught us about Claude Code,
GitHub and our own process. The parts bin in Part 3 points at the first
kit's code, which now lives under `legacy/kit-v1/` (read `kit/` in those
paths as `legacy/kit-v1/`).

## How to read this file

- Part 1 holds facts about the platform. Each has the fact, how it bit us and what to do.
- Part 2 holds lessons about design and process, with evidence.
- Part 3 is the parts bin. Each part has a path, its job, its size, why it is worth
  reusing and what to strip.
- Line counts are from main on 13 October 2026. They will drift.

---

# Part 1. Facts about the platform

## 1.1 Claude Code

### 1.1.1 The Bash tool sets git config in the environment

- Fact: Claude Code's Bash tool sets `GIT_CONFIG_COUNT=2`, with the keys
  `credential.interactive` and `credential.guiPrompt`. We first blamed Orca. A
  check on 12 October showed Claude Code does it in every session.
- How it bit us: our guard asked for confirmation on every git command, even
  `git tag` and `git remote -v`, because it refused any `GIT_CONFIG` override. An
  unattended run would stop at its first git command. The same variables made a
  rehearsal fixture ask until a fixture was changed.
- What to do: do not refuse the presence of `GIT_CONFIG_COUNT`. Read the key and
  value pairs. Ask only for risky keys: `core.hooksPath`, `core.sshCommand`,
  `alias.*`, `credential.helper`. Pass the two harmless credential keys.
  Test the guard in a real Claude Code session, not only in a stand-in.

### 1.1.2 A `!` command counts as an agent session

- Fact: a command the person types with the `!` prefix runs in Claude Code's own
  environment. It looks the same as an agent's tool call.
- How it bit us: the gate refused `gate.py sync` with "only the person runs it".
  The person ran it with `!` and was refused. Other kit messages had told the
  person to use `!`.
- What to do: every message that names a person-only command must say "in a
  separate terminal, not with `!`". Better, avoid person-only commands in v1. The
  thin kit should use the person's own `gh` sign-in and need no such door.

### 1.1.3 The auto mode safety check refuses things, and an agent cannot widen its own rights

- Fact: Claude Code's auto mode classifier refused all of these during the build:
  an edit to the coordinator's own brief ("Instruction Poisoning"); accepting a
  failed validator as a known false positive (a "check bypass"); switching off a
  queued workflow; pushing a merged branch; starting Codex with network on
  ("Create Unsafe Agents"); an empty first commit pushed to a test repository's
  main; adding allow rules to `.claude/settings.local.json`, even after the
  person said yes in the chat; `gh repo edit`; deleting worktrees and branches.
- Also: on 12 October the classifier had several no-verdict outages. A job that
  needs a verdict waits or fails.
- How it bit us: the first overnight run stopped for about four hours. The brief
  widening that would have fixed it was refused. Later refusals parked work at
  every stage that touched settings, pushes or deletes.
- What to do:
  - Treat a refusal as a stop. Report it. Do not reach the result another way.
  - The person sets autonomy and permissions before the run, in a file agents
    cannot edit. Never plan for an agent to loosen its own rules mid-run.
  - Keep the list of things only the person does short, and print the exact
    command for each.
  - Do not build a design that needs the classifier to say yes.

### 1.1.4 Headless sessions need `dontAsk` and a deny list, not a prompt

- Fact: in `claude -p` with `dontAsk`, anything not pre-approved is refused and
  the session cannot ask a question. Interactive auto mode instead falls back to
  prompting after a run of blocks (3 in a row, 20 in total, per the research).
- How it bit us: a coordinator held in a terminal session asked a question and
  waited. A scripted run with `claude -p` cannot do that.
- What to do: the run loop is a plain script. Each builder and reviewer is a fresh
  `claude -p` session with `dontAsk`, a settings file passed by `--settings`, and
  no `--resume`, no `--continue`. The brief goes in by file.

### 1.1.5 The hook runs twice when the plugin and `--settings` both load it

- Fact: when a session loads a plugin and `--settings` that both define the same
  hook, the hook fires twice for one tool call.
- How it bit us: the command log wrote double lines. We added a claim file per call
  ID in `claims/` to dedupe.
- What to do: wire each hook in one place only. If you cannot, dedupe on call ID.

### 1.1.6 The founded sandbox blocks the kit's own setup steps

- Fact: once a project's `.claude/settings.json` turns the sandbox on with a
  network allowlist (only the package registries), setup cannot reach github.com.
  It also cannot write `.agents/pieces/`, which the sandbox protects from the
  agent.
- How it bit us: preflight, founding, first-piece and capture all failed in the
  session that founded the project. Every step became "run this yourself". The
  skill turned into a list of commands for the person. A read-only origin check
  said "origin main could not be verified; the cause is unknown", so a sandbox
  block looked like a missing branch.
- What to do:
  - Run all network steps of setup before any sandbox settings take effect, or as
    one person command.
  - Name a sandbox block plainly when it is the cause.
  - Do not write sandbox settings in the same run that still needs the network.
  - If excluded commands are used, exclude only commands that run nothing from
    the project. A gate that runs project tests outside the sandbox is a hole;
    the maintainer parked a design for that reason.
  - Excluded-command patterns end in a space and star, so a bare subcommand may
    not match. Test the bare form.

### 1.1.7 Kit settings do not reach a project founded earlier

- Fact: founding never overwrites. Nothing updated the kit-owned part of an
  existing project's `.claude/settings.json`.
- How it bit us: a fix that added `excludedCommands` never reached the test
  project. The guard refused `cd ... && python3 .../setup.py`, and the sandbox
  blocked the bare call. A user who upgrades the kit would hit the same wall.
  Re-founding with a new kit also failed with an opaque message about a pinned
  workflow marker.
- What to do: keep kit-owned settings in the plugin, not copied into the project.
  If you must copy, store a version marker and offer an update with the person's
  yes. Make every error name the file and the change.

### 1.1.8 A development copy cannot be tested without a release

- Fact: `claude --plugin-dir <path>` loads a kit with no release version. Our
  version check refused it, even with a full commit SHA.
- How it bit us: nobody could try the skills before a release, and every fix
  needed a new release to test.
- What to do: the thin kit has no version gate. A plugin loaded from a folder
  just works. Add versions only when something is published.

### 1.1.9 Skill live lines need the plugin root variable

- Fact: a skill's inline command (the `!` line that runs when the skill loads)
  must use `"${CLAUDE_PLUGIN_ROOT}/..."`. A relative `kit/scripts/...` path
  fails in a founded project, which has no `kit/` folder.
- How it bit us: the shape skill failed to load on first use.
- What to do: every path in a skill uses the plugin root variable. Add a check
  that fails on a bare `kit/` path in `skills/`. Also check that "Held by:"
  pointers use the full path (a short path failed three skill checks).

### 1.1.10 Founding must not write before the person agrees

- Fact: a `.agents` folder appeared in an empty project before setup ran. A
  session-start hook was the likely cause.
- What to do: hooks that run at session start must be read-only, and must print
  nothing in a project that does not use the kit.

### 1.1.11 Weekly usage is a run limit

- Fact: the first build paused at 90% of weekly usage on 7 October. Background
  sessions spend quota in proportion to how many run. In `-p` mode a usage limit
  makes the agent fail, not pause.
- What to do: the run reads usage if it can, has a "waiting for the limit to
  reset" state, and keeps the number of parallel sessions low. Use cheap models for
  mechanical steps (sonnet for builders and reviewers, haiku for mechanical steps,
  opus only as a second try, as the memory file records).

### 1.1.12 Trust dialog and first-run prompts

- Fact: a fresh project folder opens with Claude Code's trust dialog. A stray
  Enter in a setup question accepted a default ("Private, free plan") that the
  person never saw.
- What to do: show each question before it takes an answer. Do not offer a
  default that a single Enter can take for money, access or visibility questions.
  Read the repository's visibility with `gh` instead of asking (the skill
  recommended Public for a private repository).

## 1.2 GitHub

### 1.2.1 Actions on a private repository use paid minutes

- Fact: hosted checks on a private repository use paid minutes. When recent
  payments fail or the spending limit is hit, the job does not start. The message
  is "The job was not started because recent account payments have failed or your
  spending limit needs to be increased." It fails in about one second.
- How it bit us: on 4 and 5 October, Actions used about 230 minutes across 164
  runs; about 96 of them came from one branch check repeating a validator on every
  push. We switched workflows off. In the field test the founded check failed for
  billing, not for code. The test repository had to go public to run it.
- What to do:
  - Default to local checks. Make the hosted check one cheap workflow.
  - Tell the person at setup that a private repository uses minutes.
  - Make the check say "billing" when billing is the cause.
  - Queued runs may sit for hours with no runner. Do not wait on them.

### 1.2.2 A free private repository has no server-side rules

- Fact: rulesets, required checks, merge queues and push protection are missing on
  a free private repository. Repository settings need the person (`gh repo edit` is
  denied to agents).
- How it bit us: the "two independent layers" rule had no GitHub layer to lean on.
- What to do: the local layer must hold alone (git hooks, deny rules, a guard).
  Say so plainly in setup. Offer a ruleset only on a plan that has one.

### 1.2.3 An empty repository has no main branch

- Fact: a new repository with no commits has no `main`. A pull request needs a
  base, so a foundation pull request cannot open.
- How it bit us: founding finished and then could not reach a first piece. The
  only way on was a first commit pushed to main, which our rules forbid for agents.
  Five manual steps stood between founding and the first shaping.
- What to do: at the start of setup, check whether origin has a main commit. If
  not, print the one command the person runs (an empty first commit and push), or
  ask them to create the repository with a README. Ask this before the questions.

### 1.2.4 App token versus person token

- Fact: a fine-grained personal access token acts as the person who made it.
  Every label, comment and merge made with it shows the person as the actor. An
  App has its own identity, and a short-lived installation token.
- How it bit us: the gate's trust ("this label was set by the gate, not the
  person") cannot hold on one account. The App route also needs an RS256 JWT, which
  the standard library cannot sign (we shelled out to `openssl`). Before the App
  exists, the gate could not read blocked-by links, so no piece could reach ready,
  although setup promised "you can shape and run locally now".
- What to do: for the thin kit, do not rely on actor identity. State labels are
  guarded by the gate's own checks and a hook, not by who wrote them. Do not need
  blocked-by reads from the API; keep dependencies in the spec text. Defer the App
  entirely. If it returns, make the pre-App path a full path.

### 1.2.5 A closing word closes an issue even in a sentence that denies it

- Fact: "Closes" before a number closes the issue, even in "this does not close".
- What to do: only `Closes <ref>` lines in the pull request body. Neutralise every
  other reference from agent or issue text. `closing.py` does this (see Part 3).

### 1.2.6 `gh pr merge` needs a default repository, and GraphQL fails sometimes

- Fact: a literal `gh pr merge` failed with a missing-default-repository refusal
  until `GH_REPO` was set for the child process. GitHub's GraphQL API returned a 504
  in the middle of publishing, leaving an edited issue with no pull request.
- What to do: pass the repository explicitly to every `gh` call. Make publishing
  resumable: record each step so a retry continues, not repeats. Merge with
  `--match-head-commit` so a branch that moved is refused.

### 1.2.7 Network outages and DNS failures happen in agent sandboxes

- Fact: a whole night passed with no internet and Orca unresponsive (5 to 6
  October). Codex's own environment failed DNS while an Orca terminal worked.
- What to do: every GitHub step is retryable and idempotent. The run saves state
  before and after each step. Write a "network down" wait, not a crash.

## 1.3 macOS

- The machine crashed twice from memory pressure with too many agents at once.
  Budget about 2.5 GiB per builder and keep a reserve. The thin kit should cap
  parallel builders low (three was the working number) and run one full suite at
  a time unless disk and memory are checked first.
- The disk filled on 9 October at 02:34. About 28 GB of retained scratch folders
  sat in the temp folder. Every build stopped. Set a free-space floor (15 GB was
  used) and clean scratch by default. Do not retain scratch "as evidence".
- The Mac must stay awake. A run started under `caffeinate -dis -w <pid>` kept
  going; a restored session without it did not. Check power and sleep before the
  person walks away.
- A scheduled job inside a chat session dies when the session or app ends. Use
  `launchd` for any watch that must survive.
- System Python on this Mac is 3.9. The kit assumed 3.10 (it avoids `tomllib` and
  uses newer annotation forms). Focused tests failed under 3.9. Pin the Python
  the kit needs and say so in setup; check the version first.
- A missing `pytest` in the check environment made rehearsals skip and print
  "passed". Treat a skip as a failure unless the skip is allowed by name.
- A Perl locale fault printed noise in setup rehearsals until `LC_ALL=C`.
- `ruff` and `mypy` caught annotation faults late. Run them on every changed
  Python file in the builder's own quick check.

## 1.4 Orca

- Orca restarted four times in two days (6 October: about 01:00, 13:00, 18:00,
  23:45). Each restart killed the background agents of the coordinator and the
  watchdog job. Work lost: any agent that had not committed. Rule: every worker
  commits early and writes its own state to a file; a restart is a normal event.
- The coordinator's terminal input box cannot be read from outside. A line
  typed there reaches only that session. Use a mailbox file the coordinator reads
  at each step.
- Idle terminals pile up (Codex opened 15 to 20 shells an hour). A no-model loop
  closing idle terminals every ten minutes kept the machine alive. Better: do not
  spawn a shell per step.
- Two coordinators at once is a real risk after a restore. Check for a live
  process before starting a new one, and close the old terminal.
- A log timestamp ran ahead of the clock by hours in one night. Take times from
  the system clock in code, not from the model.

## 1.5 Python, uv and packages

- Supply chain settings that worked: `uv.toml` with `exclude-newer = "30 days"`
  and `no-build = true`; `.npmrc` with `ignore-scripts=true`, `min-release-age=30`
  (npm 11.10 or later, days) and `minimum-release-age=43200` (pnpm 10.16 or later,
  minutes). An older uv takes only a date for `exclude-newer` and fails with a parse
  error on a relative value. Check versions before writing these.
- `uv`, `gitleaks` and a package-age check were absent on the check machine. The
  built-in scanner ran. Make every optional tool optional and say when it is missing.
- A bare pytest start crashed with SIGSEGV in one retained environment while the
  full-check environment passed. Pin one check environment.

## 1.6 Codex

- Codex could be driven as a second coordinator and builder, but its own
  environment failed DNS, and a direct review launch failed with a
  managed-preferences sync fault. A normal Orca terminal worked. Keep Claude Code as
  the only agent for the thin kit.
- A cross-model review study (one study, two models, 116 tasks) found a worse pass
  rate for Codex reviewing Claude's code. Treat an outside critic as advisory.

---

# Part 2. Lessons about design and process

## 2.1 Why the build was slow

Evidence in brackets.

1. Full suite cost grew with the kit. A full suite ran 49 rehearsals and 1,744
   units on 8 October, then 54 rehearsals and 2,023 units on 13 October. One
   run took about 15 hours overnight (partly network resets and load), and about
   50 minutes in a clean run. Reruns after every fix, refresh and review dominated.
   Lesson: a check that takes an hour is checked once a day, not once a change.
   Keep the full suite under 10 minutes by design, or split it.
2. Review rounds had no stopping rule that worked. Each piece took two fresh
   reviews, then a third "authorised" one, then park. Reviews kept finding novel
   blockers on large pieces (CR-03, CR-06, CR-07, CR-09, CR-22 and Q4 all parked at
   the cap). The pieces were too big. A review finds what a reviewer can hold in
   its head. Lesson: slice small. A piece a reviewer can read in one sitting clears
   in one or two rounds.
3. Factory overhead swamped product work. The folder holds hundreds of one-off
   scripts (`codex3-<piece>-<step>.sh`, `-v2`, `-v3`) for publish, refresh, hosted
   poll, merge and main-after checks. Most existed to prove the process. Lesson: the
   run is a script in the kit with one path. Do not build per-piece process scripts.
4. Evidence bureaucracy: every step recorded hash proofs of "449 source files
   unchanged" and "process group gone". Safe, slow, and unread. Lesson: record what
   a person will read (judge result, diff, decisions made alone). Drop the rest.
5. Top-down design. A 63-decision design, 23 slices, 27 core pieces, 58 follow-ups,
   22 repair findings and a 42-node dependency plan were written before one real
   project ran the loop. The first field test (11 to 12 October) found the core
   did not work: setup could not run inside its own sandbox, shaping could not reach
   ready before the App, the generated first piece could never pass on main, skill
   paths broke. Lesson: run one real project end to end first, with the thinnest
   path, then add.
6. Speed-ups gave up checks that later mattered (see the deferred list): no
   readiness agent per piece, short briefs, parallel builds, no GitHub checks. The
   risks named there (a piece correct by its brief but missing a house rule; two
   pieces with different assumptions about a shared interface) are exactly what
   the field test found.
7. Every fix touched shared files. Pieces queued behind each other for settings
   templates, `setup.py` and `read_record.py`, and the `1,864`-line guard. Waiting
   on "gate ownership release" is a sign of a god file. Lesson: small modules with
   one owner each.
8. Fixtures broke production changes. Many red full suites were fixture setup
   errors, not product faults (107 setup errors in one run). The rule that a fixture
   fault does not count as an attempt was added late. Lesson: tests that need a
   rehearsal of the whole kit break on every change. Prefer small unit tests plus
   one end-to-end check.
9. Cleanup traps blocked verification. Existing tests ran recursive deletes in
   their cleanup, which the guard refuses. Verification ran in retained copies with
   those traps disabled. Lesson: tests clean up in a way the guard allows.
10. The coordinator model forgot. A model in a terminal holds the loop and its
    context fills. Handover by hand was needed. Lesson: the loop is a plain script
    that starts each step in a fresh session and writes each step's start and end
    to a record itself.

## 2.2 What made the kit fragile

1. Prose rules that scripts should hold. The skills audit found far-too-long
   skills (three over 500 lines: 894, 746 and 694), reference chains three deep, and
   exact algorithms written as prose (a first-upload flow with exit codes, a claim
   race, the next release number, every queue verdict). Each should be a script with
   a test.
2. A guard that parses shell. The guard grew to 1,864 lines trying to read every
   spelling of a push, a delete, a label edit and a merge. It still asked on
   forms it could not read, and it asked on every git command under the harness
   variables. Deny rules plus a short hook and a sandbox are enough. Hold the hard
   rules (push to main, recursive delete, hand-written state labels, secrets) in
   two layers, and stop there.
3. One account for agent and person. The gate cannot tell an agent from the person
   when both use the person's `gh` sign-in. Designs built on that distinction
   (person-only sync, "actor" checks) failed in real use.
4. Rules that contradict each other. Setup promised local shaping before the App;
   the gate refused ready without it. The setup skill told the person to pass flags
   that the script rejected. A piece's source field named the foundation pull request
   and not the piece. A need told the agent to "ask the gate to run the judge" with
   no command that does it. Lesson: a test that runs each skill's stated commands.
5. State outside the project. Held-out cases, keys and heads live in a data folder
   outside the project. They broke when the data folder moved or a sandbox blocked
   it. Use it only where it earns its keep.
6. "Park" meant three things. The red team found the anti-circle rule deadlocked
   three of fourteen moves, and that taking a piece out of a combined branch had no
   working mechanism without a rewrite. The 14-move table is more than a thin kit
   needs.
7. Opaque errors. "Prepare the existing workflow's development marker and matching
   SHA" and "cause is unknown" cost hours. Every refusal needs a `next:` line with
   the file and the command.
8. Unsaved state leaks. The founding kept answers "for the next run" and then asked
   again. A run that says it saved something must save it, and a test must check.

## 2.3 What worked

1. Shaping questions were good. In the habits test, shape planned three small
   pieces, each depending on piece 1, and asked five sharp questions (data file
   place, duplicate names, unknown habits, the streak rule, empty list). Each had a
   reason and a recommendation, and the answers went into the spec under Decisions
   with one assumption marked. Keep: "settle the biggest need first, recommend an
   answer, write it into the spec".
2. Checks first. Writing the test, seeing it fail for the right reason (an
   assertion that names a spec ID), then building. Failing-first caught real faults
   (46 expected failures in one piece, 27 failing assertions with the old guard).
3. Frozen bar. Judge files committed first, alone; a byte comparison of the bar
   after the build catches edited tests, the way Claude models mostly cheat.
4. Fresh session per attempt with a short attempt log. Long sessions with failed
   approaches get worse.
5. Fixed hand-back outcomes for builders: done, bar-is-wrong, needs-the-person,
   blocked-by-environment, gave-up. They let the run continue where a free-text
   report would have stopped it.
6. Decide or park. After the first night's stall, a single rule worked: take the
   answer that keeps every settled decision and is easiest to undo, write it
   under `## Decided`, flag it for the morning. Stop only for money, accounts,
   settings, going public, a release, irreversible data loss, three failed
   attempts, or a refused command.
7. Real-project tests found real problems in a day. The field loop (test, note,
   fix, retest) in a scratch project found more than weeks of rehearsals.
8. Local checks only. Switching hosted checks off saved money and time. The
   merge condition became "local run green on the latest commit".
9. Small merges. Pieces that changed few files merged first time.
10. Two-layer rules. Settings deny rules plus a hook caught the same refusals;
    when one layer missed a spelling, the other caught it.
11. The board and the dependency graph the run redrew from the plan, and the log
    of each step. The maintainer liked them. Keep a small version.
12. A dated, itemised field-notes file with kinds (blocker, wrong, friction) and a
    rule that core findings (loop stops, kit says something false, breaks a
    decided principle) are fixed one at a time, most blocking first.

## 2.4 Walk-away lessons (the first night)

On the night of 4 to 5 October the run stood still for about four hours on a
question an agent could have answered.

Causes, in short:
1. Stop rules were a list of exceptions, and the list missed the case that came.
2. The assistant promised more than the rule delivered.
3. The watchdog obeyed the letter of its rule and had no way to wake the person.
4. There was no safe way to reach a running coordinator.
5. Changing the rule mid-run was refused by the safety check.
6. A strict chain of slices meant one stop stopped everything.
7. The watchdog was a job inside a chat session on a Mac that might sleep.

Fixes to keep:
- One rule to decide alone, not a list.
- A decisions record the person reads in the morning, with a one-command undo.
- Autonomy policy set by the person before the run, in a file agents cannot edit.
- A mailbox file read at each step.
- A watchdog outside any chat session (`launchd`), driven by a heartbeat, with a
  notification when it gives up.
- A real stop notifies the person and lets the run take work that does not depend
  on it.
- A pre-walk-away check: power, sleep, memory, disk, planned stops.

For the thin kit: do this later. Walk-away is a second step. First make the
attended loop work.

## 2.5 Research results worth keeping

From the ten-point research drafts (agentic loops, gates, spec-driven, records,
skills, red team):

1. Give the builder a sanctioned "the bar is wrong" outcome. Research on
   impossible tasks showed an explicit flag cut cheating sharply.
2. Byte comparison of tests catches edits, not special-casing. Hold a hidden case
   only if the cost is small; otherwise rely on a fresh reviewer.
3. "Clearly stuck" by idle time misfires both ways. Use repeated action and result
   patterns, a hard timeout on every test and judge run, and let the gate decide.
4. A usage limit is the likeliest overnight stall.
5. After a join, rerun the earlier pieces' judges, not only the project check.
   About 28% of agent pull requests conflict.
6. A review finding counts only as a failing check or a new shaping item. A
   reviewer asked for gaps always finds some.
7. Model-written context files can lower success. Keep the standing instruction
   file short (150 lines at most), one home for each fact.
8. The run's one pull request must stay reviewable. Verification, not generation,
   is the bottleneck.
9. A fine-grained token acts as the person. Do not build trust on it.
10. A free private repository has no server-side layer.

## 2.6 Rules of thumb for the restart

1. Thin first: setup, shape, run, one gate, one guard. Prove one real project.
2. Every step that takes more than ten minutes is a script with a log and a
   resume point.
3. A skill holds judgement. A script holds an algorithm. A hook or deny rule holds
   a hard stop. Never prose for an algorithm.
4. One home for each fact. One owner for each file.
5. Every refusal has a `next:` line.
6. Test each skill's commands in a real session, in a founded project, with the
   sandbox on.
7. Keep the slice small enough for one review.
8. Cap parallel work by memory and disk. Check before, not after the crash.
9. Name the lessons issue in the next build. Put lessons into checks, not into
   notes.

---

# Part 3. Parts bin

Paths are under `/Users/guillaumepicard/PROJECTS/ai-loop-kit/kit/`. "Strip" says what to
remove when copying so the thin kit does not inherit the old design.

## 3.1 Spec and gate core

### 3.1.1 Spec parser

- Path: `scripts/loop/spec.py` (758 lines), format in `spec-format.md` (229 lines).
- Job: the one parser for the spec block between `<!-- spec:start version=1 -->`
  and `<!-- spec:end -->`. Returns a `Spec` with the same keys every time.
  Handles fenced code, unknown versions, lists, judge lines, coverage tables.
  Includes `add_list_item`, `remove_list_item`, `set_judge_line`, `split_after_block`.
- Why reuse: a single reader stops drift. The marker rules and edge cases are
  already tested (fenced markers, second block, missing end).
- Strip: held-out, route-open and measurement judge fields; reference-judge
  fields; the sensitive-area `Accepted:` rules; coverage fields if you drop
  spec IDs. Cut the field list to Goal, Done when, Edge cases, Must stay the same,
  Judge, Touches, Decisions, Open questions.

### 3.1.2 Fingerprint

- Path: `scripts/loop/fingerprint.py` (158 lines).
- Job: a hash of the normalised spec block plus the commit that last touched the
  judge files. Stored at ready; a different value later means the spec or judge
  moved, so old evidence is stale.
- Why reuse: it is small, pure and tested. The normalisation rules (collapse
  blanks except inside quotes, leave out gate-written lines) took several rounds.
- Strip: the held-out fingerprint link; the CLI wrapper if not needed.

### 3.1.3 States and moves table

- Path: `scripts/loop/states.py` (163 lines).
- Job: states and numbered moves as data, with a refusal for any other pair.
- Why reuse: a table as data is easy to test. The label helpers (`label`,
  `state_of_label`) are useful.
- Strip: shrink to the states the thin kit needs (shaping, ready, building,
  review, done, plus parked). Drop the 14-move table, the anti-circle rule and
  repeat counters; the red team showed they deadlock.

### 3.1.4 Ready gate

- Path: `scripts/loop/gates/ready.py` (734 lines).
- Job: lint, the needs list, judge files committed alone as the first commit, the
  judge run on main must fail on an assertion that names a spec ID, then fingerprint.
- Why reuse: the order of checks and the "fails for the right reason" test are
  the heart of the loop. The doc string is a good spec.
- Strip: two fresh test lists, held-out store, area map, sensitive-area and
  must-look reasons, blocked-by reads, measurement and reference judges, the pre-App
  queue. Keep: lint, judge commit first and alone, judge fails on main with an ID,
  fingerprint.

### 3.1.5 Needs list

- Path: `scripts/loop/needs.py` (259 lines).
- Job: works out what a piece still needs from its spec, so shaping always has a
  "biggest need first".
- Why reuse: this drives the good shaping behaviour.
- Strip: needs that depend on the App, held-out cases, or areas.

### 3.1.6 Lint

- Path: `scripts/loop/lint.py` (389 lines), `scripts/spec.py` (250 lines, CLI).
- Job: machine checks on a spec: length limits by type, required fields, quick-path
  rules.
- Strip: area checks and anything tied to the policy keys you drop.

### 3.1.7 Closing words

- Path: `scripts/loop/closing.py` (131 lines), `scripts/closing-words.py` (88).
- Job: scans a pull request body, title, commits and changelog for closing words;
  `neutralise` breaks references in agent text.
- Why reuse: the GitHub behaviour is easy to get wrong and this is tested.
- Strip: the changelog scan if the thin kit has no changelog entry rule.

## 3.2 The run

### 3.2.1 Judge runner

- Path: `scripts/loop/judge.py` (579 lines).
- Job: runs a judge command in a temporary checkout of a ref under a hard time
  limit. Reads the runner's report (JSON or XML) and returns `passed`, `failed`,
  `failed_no_id` (assertion failed but names no spec ID), `errored` or `timeout`.
  Detects pytest, vitest and others. `run_limited` kills the process group.
- Why reuse: telling an assertion failure from an error is the core of
  failing-first. The time limit and process-group kill fixed real hangs.
- Strip: `evidence_entry` chain coupling, the CLI, any held-out injection.

### 3.2.2 Session launcher

- Path: `scripts/loop/sessions.py` (591 lines).
- Job: starts a non-interactive `claude -p` with an exact short command line: brief
  by file, `--settings`, `dontAsk`, no `--bare`, `--resume` or `--continue`. Scrubs
  GitHub credentials from the environment. Wraps outside text in marked data
  blocks (`data_block`, `parse_blocks`, `check_template`). Reads the hand-off file
  (`validate_handoff`, `read_handoff`). Renders settings for the attempt with deny
  rules for the bar.
- Why reuse: the command line, env scrub and data-block approach are lessons in
  code. The hand-off outcomes are right.
- Strip: crew and trim wiring; cost-cap options not needed; the policy coupling.
  Keep `build_command`, `scrub_env`, `data_block`, `render`, hand-off read and
  `start`.

### 3.2.3 Frozen bar check

- Path: `scripts/loop/bar.py` (377 lines).
- Job: lists every change a build made to the bar (judge files, existing tests,
  fixtures, snapshots, tool settings, guard files) in seven kinds, by comparing
  head to base byte for byte. Also `paths` for deny rules.
- Why reuse: this is the main anti-cheating check and it is cheap.
- Strip: reference-judge and held-out kinds; coverage tool checks if the thin kit
  does not use them.

### 3.2.4 Attempt log

- Path: `scripts/loop/attempt_log.py` (119 lines).
- Job: one entry per judged attempt; `render` produces the short log the next
  builder reads.
- Why reuse: fresh session per attempt needs this.
- Strip: the keyed evidence chain dependency. Write plain JSON lines in the piece
  folder.

### 3.2.5 Attempt gate

- Path: `scripts/loop/gates/attempt.py` (818 lines).
- Job: judges one attempt: bar changes, touches, judge result.
- Why reuse: the order of checks is sound.
- Strip: held-out runs, hypothesis list, trim, new-test lint coupling, possible
  gaming log if you keep it simple. Likely a rewrite at 150 to 250 lines; use as a
  reference.

### 3.2.6 Evidence record (reference only)

- Path: `scripts/loop/evidence.py` (333 lines).
- Job: HMAC hash chain of what the gate saw, with a key outside the project.
- Why reuse: probably do not. It is a good design for tamper evidence, but the
  thin kit does not need it. Keep as a reference if tamper evidence returns.

### 3.2.7 Worktree script

- Path: `scripts/worktree.sh` (740 lines).
- Job: opens a worktree per piece under `.agents/worktrees/`, writes a `.env` of
  throwaway values from `.env.example`, never links real env files, finds a free
  port, lists leftovers, refuses to remove a worktree with unsaved work.
- Why reuse: "never remove a worktree holding unsaved work" and "throwaway env
  only" are lessons. Disk-full and old-git exit codes are handled.
- Strip: the link-list file, `candidates`, the app start command, and `tidy` if
  you use a simpler cleanup. Cut to open, unsaved, remove, port.

### 3.2.8 Trim pass (optional)

- Path: `scripts/loop/trim.py` (479 lines), `briefs/trim.md` (73), `scripts/trim-check.py` (149).
- Job: a fresh session may only remove code the piece added; the check refuses any
  test touch and any added line.
- Why reuse: only if you want it. A cheap quality step.
- Strip: everything on first copy. Defer.

### 3.2.9 Policy file

- Path: `scripts/loop/policy.py` (199 lines), `templates/policy.json` (22).
- Job: validated JSON policy (attempt limit 3, review rounds 2, question cap 5,
  length limits, test command and timeout, memory and disk floors).
- Why reuse: the defaults are the settled ones, and a JSON policy with named
  errors is a good pattern. No pre-approval key by design.
- Strip: billing, research age, builder cap if unused. Keep limits and floors.

### 3.2.10 Paths

- Path: `scripts/loop/paths.py` (178 lines).
- Job: every shared path defined once; run-name check; project key.
- Strip: App key and held-out paths.

## 3.3 Safety

### 3.3.1 Secret scan

- Path: `scripts/secret-scan.py` (395 lines).
- Job: reads only added lines of a staged change or a commit range. Known key
  shapes, high-entropy strings, commit messages, lockfile handling, optional
  `gitleaks`. `--staged` and `--range`. Read-only.
- Why reuse: standalone, tested, no kit coupling beyond the CLI helper.
- Strip: the `# contract: agent` header if the thin kit has none; the shared CLI
  `setup` and `handle` glue.

### 3.3.2 Command guard (reduce)

- Path: `hooks/guard.py` (1,864 lines), `hooks/hooks.json` (37).
- Job: PreToolUse hook. Refuse (exit 2), ask, or pass. Refuses push to main,
  force push, recursive delete, hand-written state labels, merges by agents, reads
  of env files and keys, writes to guards.
- Why reuse: the exit-code protocol, the three outcomes, the "a fault asks, bad
  input refuses" fail-safe, the shell splitting (`split_commands`, `unwrap`,
  `substitutions`) and the push, rm and label checks are the useful parts.
- Strip: nearly everything else. Copy `Decision`, `refuse`, `ask`, `normalise`,
  `split_commands`, `unwrap`, `check_push`, `check_rm`, `check_find`, label checks
  and the main loop. Drop: installed-door checks, gate and sync rules, merge door,
  pre-approved run, MCP checks, GraphQL payload handling. Fix the `GIT_CONFIG`
  rule (Part 1.1.1) before using it. Target 300 to 400 lines.

### 3.3.3 Command log

- Path: `hooks/command-log.py` (224 lines).
- Job: one JSON line per call (pass, ask, refuse, ran, failed) with a retry
  count, scrubbed of secrets. Never stops a call.
- Why reuse: it made refusals investigable and fed the lessons list.
- Strip: the run-name coupling if you keep one log.

### 3.3.4 Blocked commands list

- Path: `templates/blocked-commands.md` (349 lines).
- Job: the human-readable list, with the rule "if refused, report and stop; never
  reach the same result another way".
- Why reuse: the opening paragraph is the best statement of the rule. The list of
  commands is the mirror for deny rules.
- Strip: the long spellings sections can shrink to the deny rules in the settings
  template.

### 3.3.5 Settings templates

- Path: `templates/claude-settings.json` (135), `templates/builder-settings.json`
  (176), `templates/reviewer-settings.json` (105), `templates/merge-ask-rules.json` (69).
- Job: deny rules for push to main (many spellings), force push, recursive delete,
  `git clean -f`, state labels; builder and reviewer variants.
- Why reuse: the spellings list is the useful part (`git push * main`, `*:main`,
  `*refs/heads/main`, `+main`).
- Strip: the founded sandbox and network allowlist sections until a plan for
  Part 1.1.6 exists. Do not copy into projects; ship from the plugin.

### 3.3.6 Dependency check

- Path: `scripts/dependency-check.py` (562 lines).
- Job: for each new package in a lockfile change (npm, pnpm, uv), asks the registry
  for release date and licence, refuses too new (under 30 days) or unlicensed.
- Why reuse: standalone and tested with a fake registry. A real supply chain guard.
- Strip: defer. Add when a project adds dependencies.

### 3.3.7 Supply chain files

- Path: `templates/uv.toml` (11), `templates/npmrc` (12).
- Job: 30-day minimum release age, no install scripts.
- Why reuse: free protection. Keep the comments on versions.

## 3.4 Skills, briefs and templates

### 3.4.1 Builder brief

- Path: `briefs/builder.md` (88 lines).
- Job: the brief for a fresh builder. Data-block warning, frozen spec, attempt
  log, never-do list, "you cannot ask questions", five hand-back outcomes.
- Why reuse: it is already short, and the hand-back protocol is right.
- Strip: hypothesis and held-out text. Keep the never-do list, trimmed.

### 3.4.2 Reviewer brief

- Path: `briefs/reviewer.md` (112 lines).
- Job: fresh reviewer sees the specs and the diff only; round count; data blocks.
- Strip: combined-branch wording if one piece per pull request.

### 3.4.3 Test list brief

- Path: `briefs/test-list.md` (41 lines); `scripts/loop/testlists.py` (167), `scripts/test-lists.py` (104).
- Job: a fresh session lists the tests it would write; lists must cover the same
  spec IDs.
- Why reuse: cheap check that the spec is clear. Defer until needed.

### 3.4.4 Shape skill

- Path: `skills/shape/SKILL.md` (58 lines) plus `references/questions.md`,
  `references/quick-path.md`, `scripts/find-duplicates.py`.
- Job: capture, duplicate search, choose a path, settle the biggest need, write the
  answer in the spec, lint, ask the gate for ready. Stops, Steps with "Done when:"
  lines, Gotchas, When to read more.
- Why reuse: the structure (Now, Stops with "Held by:", Steps each with "Done
  when:", Gotchas) is the skill template from the research. The questions
  reference holds the good shaping behaviour.
- Strip: held-out and sensitive-area steps, App queue notes. Fix the relative path.

### 3.4.5 Run and setup skills

- Path: `skills/run/SKILL.md` (51), `skills/setup/SKILL.md` (58).
- Job: short skills that call scripts.
- Strip: rewrite setup. It must work inside the settings it writes (Part 1.1.6).

### 3.4.6 Templates

- Path: `templates/AGENTS.md` (51), `templates/CLAUDE.md` (1), `templates/overview.md`
  (29), `templates/piece-issue.yml` (52), `templates/first-piece.md` (26),
  `templates/CHANGELOG.md` (15), `templates/gitignore` (30), `templates/checks.yml` (38).
- Job: the founded project's standing file (under 150 lines, one home per fact,
  "Rules and the reason for each"), an issue form, a first piece, a hosted check.
- Why reuse: the AGENTS.md template is a good short model. Note the first piece
  needs a README to pass its own check (a field-test fault).
- Strip: area map, policy and sandbox references. `checks.yml` needs the billing
  note in Part 1.2.1.

### 3.4.7 Glossary

- Path: `glossary.md` (43 lines).
- Job: the plain words the kit uses. Reuse it as the base for a `CONTEXT.md`.

### 3.4.8 Skill checker

- Path: `scripts/check-skills.py` (727 lines).
- Job: checks skills against size limits, "Held by:" pointers, path rules.
- Why reuse: catches the relative-path fault (Part 1.1.9) and the short Held-by
  path. Strip down to size, paths and pointers.

### 3.4.9 Session start

- Path: `scripts/session-start.sh` (92 lines).
- Job: prints a short report of the loop's state at session open; exits 0 on every
  route; prints nothing in a project without the kit.
- Strip: the check-main call. Keep the fail-safe shape.

### 3.4.10 Other scripts

| Path | Lines | Job | Verdict |
| --- | --- | --- | --- |
| `scripts/co-change.sh` | 68 | files that change together, to fill `Touches:` | copy |
| `scripts/handoff.py` | 158 | write the hand-off file builders end with | copy with sessions.py |
| `scripts/run.py` | 321 | run entry point | rewrite |
| `scripts/gate.py` | 338 | gate CLI | rewrite, smaller |
| `scripts/loop/run/engine.py` and siblings | many | the run engine | reference only |
| `scripts/loop/moves.py` | 1,311 | applies the table | rewrite |
| `scripts/loop/github.py` | 880 | App, JWT, push | do not copy; use `gh` |
| `scripts/loop/pulls.py` | 132 | pull request create, merge with `--match-head-commit`, never `--admin` or `--auto` | copy the merge rule |
| `scripts/bring-up-to-date.sh` | 173 | bring a branch up to main | maybe |
| `scripts/records-check.py`, `area-map.py` | 79, 82 | records and area checks | defer |
| `scripts/document-bloat.py`, `document-claims.py` | 145, 235 | doc size and claim checks | defer |
| `scripts/pre-run-check.py` | 979 | power, memory, disk before a run | copy the checks only |
| `scripts/check-tooling.sh`, `check-recipes.sh` | 384, 191 | tool and recipe checks | defer |
| `recipes/` (Vercel, Coolify, Supabase parts) | various | deployment recipes | defer |
| `scripts/setup.py`, `loop/versions.py` | 959, 565 | founding, versions | rewrite; no version gate |

## 3.5 Tests and house rules

- `tests/house-rules.sh` (214 lines): checks every tracked file for issue and pull
  request numbers, model attribution, em dashes and other house rules. Copy.
- `tests/lint.sh` (297): ruff and mypy over Python. Copy.
- `tests/run-all.sh` (136): runs every check, one by name. Copy; fix the rule that
  prints "passed" for skipped rehearsals.
- `tests/fake-github.sh`, `tests/fake-host.sh`, stand-in registry: stand-ins for
  GitHub, the host and a package registry. Borrow the stand-ins, not the 54
  rehearsals.
- `.githooks/commit-msg`: strips model attribution. Copy as is.

## 3.6 Copy order for the thin kit

1. `spec.py`, `fingerprint.py`, `closing.py`, `secret-scan.py`, `judge.py`.
2. `sessions.py` (reduced), `bar.py`, `attempt_log.py`, `handoff.py`.
3. `guard.py` (cut to about 400 lines), `command-log.py`, settings templates.
4. Builder and reviewer briefs, shape skill, AGENTS.md template.
5. `worktree.sh` (cut), `policy.py`, `pre-run-check.py` checks.
6. House-rule tests and lint.

Leave behind: the App, JWT, sync, held-out store, evidence chain, 14-move table,
combined-branch integration, watch and mailbox, versions, recipes, crews.

## 3.7 Facts to check before copying

- Python version: the old code targets 3.10 and fails on system 3.9.
- Every path in a skill uses the plugin root variable.
- The guard is tested in a real Claude Code session with the `GIT_CONFIG` variables
  set.
- No code path calls `rm -r`; tests clean up in a way the guard allows.
- Skipped tests are failures unless allowed by name.
