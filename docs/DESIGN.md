# AI Loop Kit: design

Version 2.0.0. This is the one description of what the kit is, how it works
and why. It describes the kit in `kit/`.

## The goal

A continuous factory. The loop keeps building whatever is approved. You
shape and approve work whenever you like, in another session, and it joins
the queue. You can see on GitHub what is waiting to be shaped, what is
queued, what is building, what needs you and what is done. The loop never
asks you for input or waits to be asked for status. It stops only for a
decision that a written rule says only you can make.

Three rules follow:

1. Everything you must do happens in shaping: decisions, approvals, and the
   prerequisites only a person can clear. Shaping can happen at any time,
   while the loop runs.
2. The loop never stops for a cause it can handle: a GitHub error, a review
   finding, a failed test, a crashed session, the end of a batch.
3. Progress is visible on GitHub. The board shows when the loop parks an
   issue or finishes. Notifications are not built.

## Default posture: a goal, not a conversation

Every session the loop starts behaves as if it had been given a goal: keep
going until the work is done, without the person. Every brief starts with
this and every guard exists to make it safe.

- **Never ask.** No session asks the person anything or waits for an answer.
  A question becomes a decision: take the choice `PLAN.md` implies, or the
  closest approach that keeps its rules, record it under Deviations, and
  continue.
- **Never stop early.** A failed test, a review finding, a crash or a GitHub
  error is work to do, not a reason to end. The coordinator retries, fixes
  and re-reviews until the issue merges or its rounds run out.
- **Finish.** An issue ends merged, or parked with a reason. The loop ends
  only when nothing is left to build, after the idle limit, or on a stop file.
- **The one exception is the stops list.** An issue that needs a decision
  only the person can make (money, credentials, permissions, settings,
  irreversible data, going public, a protected path) is parked as
  `needs-user` with a one-line reply, and the loop carries on with
  everything else.

The rest of this design supports that posture: shaping removes the reasons
to ask, the guards make autonomy safe, the board removes the need to ask for
status, and continuous shaping keeps the queue full.

## The pattern

This is the marcdown run, written down, with guards where marcdown was weak.

| Marcdown did | The kit keeps it as |
| --- | --- |
| A plan file with binding decisions | `PLAN.md` in the repository, read by every agent |
| Issues with acceptance criteria and `Depends on` | The same, from a template |
| A coordinator session dispatching builders and reviewers | The same, restarted per issue by a supervisor (see "Stateless") |
| Sonnet builder, then Sonnet reviewer in its own worktree | The same; every agent works in its own worktree |
| Fix list back to the same builder, at most three rounds | The same |
| "Closest approach, record under Deviations, continue" | The same, bounded by a stops list |
| `needs-user` label with a one-line reply | The same, for anything on the stops list |
| An oracle built early (`MarcdownRender`) | A shaping question: "how will an agent see this is right?" |

## Marcdown's weak spots, and the guard for each

| Weak spot (evidence from the run) | Guard | Kind |
| --- | --- | --- |
| The coordinator merged to `main` itself | The hook refuses a push to `main`, `master` or the default branch in every session, and `git merge`, `gh` and branch switches in the loop's sessions; branch protection is the line that holds | Code (`guard.py`) |
| About 20 of 41 fixes merged with no re-check; coordinator edits merged untested | Merging happens only through `merge.py`, which runs the Test command on the exact commit and merges with `--match-head-commit`. The hook refuses `gh` in the loop's sessions | Code |
| A builder can weaken the tests that judge it | The hook refuses writes to existing test files in the loop's sessions, and `merge.py` refuses a diff that changes one unless the issue names its path. New tests are allowed | Code |
| Agents shared one checkout and switched each other's branches | Every builder and reviewer gets its own worktree, created by the supervisor | Code |
| Reviews lived only in agent hand-backs | `merge.py` refuses unless the review verdict is posted on the pull request | Code |
| The only park happened by accident (a classifier refusal) | A written stops list: money, credentials, permissions, settings, irreversible data, going public, new dependencies. Anything on it parks as `needs-user` | Words, checked by the reviewer |
| Stray worktrees and test processes left running | The supervisor removes its worktrees and kills its process group after each issue | Code |
| One long session holding everything (440k tokens) | Fresh sessions per issue; state lives in GitHub | Design |
| Deletes and secrets | The hook refuses recursive deletes and force pushes in every session, and secret shapes in content a session writes (not in diffs) | Code (`guard.py`) |

## The factory

### States, as labels on issues

| Label | Meaning | Who sets it |
| --- | --- | --- |
| `inbox` | An idea or report, not shaped yet. Anyone may open one | GitHub, by default, on a new issue |
| `shaping` | Being shaped | The shape skill |
| `ready` | Shaped and approved: in the queue | The shape skill, after your yes |
| `building` | Claimed by the loop | `loop.py` |
| `needs-user` | Parked on a decision only you can make, with a one-line reply | The coordinator |
| closed | Merged into the loop branch | `merge.py` |

The loop builds only `ready` issues whose `ready` label was added by a
collaborator (checked in the issue's timeline), so a stranger's issue in a
public repository never reaches an unattended builder.

### The board: one pinned issue

`loop.py` keeps one pinned issue, "Factory", and rewrites its body after
every step. It shows:

- what is building now, and since when;
- what needs you, each with its question and the reply to type;
- the queue in build order, with what each waits on;
- what is waiting to be shaped (`inbox` and `shaping`);
- what landed since your last merge into `main`, and the open final pull
  request;
- the last event and the time of the next check.

It is a dashboard with no server: it lives on GitHub, works from your
phone, and cannot drift from the truth because `loop.py` writes it from the
labels. To answer a question, reply on the parked issue; the next poll
reads a reply from a collaborator, removes `needs-user` and requeues the
issue. A real dashboard can replace the pinned issue later, reading the
same labels.

### Shaping while it runs

You run the shape skill in any session, at any time. It turns `inbox`
issues or a new idea into shaped issues, adds decisions to `PLAN.md`, asks
you one batch of questions, and labels the issues `ready` on your yes. The
loop picks them up at its next poll. `PLAN.md` is a living file: every
batch adds its decisions, and every builder reads all of them.

### The loop never finishes on its own work

- It polls GitHub every two minutes while nothing is ready.
- When the queue drains (nothing `ready` or `building`), it runs the full
  suite on the loop branch, opens or refreshes one pull request from the
  loop branch into `main`, posts a summary on the board and keeps
  waiting.
- After you merge that pull request, it merges `main` into the loop branch
  and carries on.
- It ends after 12 hours with nothing to build, or when you create a stop
  file, and says why. Starting it again is one command.

## Stateless

Nothing the loop needs lives in a session or on disk outside the
repository. Any run can stop at any moment and the next one carries on.

- **State is GitHub.** An issue is open (to do), labelled `building` (claimed),
  labelled `needs-user` (parked), or closed (merged into the loop branch).
  `Depends on` lines give the order.
- **Decisions are `PLAN.md`.** Deviations are appended there by the
  builder's pull request, so they merge with the code.
- **The supervisor is `scripts/loop.py`.** It repeats:
  1. Pick the next `ready` issue whose dependencies are closed.
  2. Label it `building` and create a worktree for it.
  3. Run that issue's own fresh sessions (`claude -p`): a test writer, a
     builder and a reviewer, with fix rounds, then `merge.py`.
  4. If the session crashes or times out, remove the `building` label and
     try the issue once more; a second failure parks it with the reason.
  5. Remove the worktree and any process left behind. Go to 1.
  6. Rewrite the board. When nothing is `ready` or `building`, do the
     drain steps above and wait.
- **One loop per repository**, enforced by a lock file holding the pid; a
  stale lock with a dead pid is taken over.
- **GitHub errors** are retried with a short back-off by `loop.py` and
  `merge.py`. A rate limit waits for its reset.

A fresh session per issue means no context growth and no compaction, and a
restart loses nothing.

## The files

| File | What it is |
| --- | --- |
| `kit/skills/shape/SKILL.md` | Turns an idea into `PLAN.md` plus issues; asks one batch of questions; lists the person-only prerequisites; one approval |
| `kit/skills/loop/SKILL.md` | Starts and watches the loop |
| `kit/templates/PLAN.md`, `kit/templates/issue.md` | The plan and issue shapes |
| `kit/briefs/` | The instructions for the test writer, the builder, the reviewer and the end-of-loop passes |
| `kit/scripts/loop.py` | The supervisor: picks issues, starts builds, rewrites the board |
| `kit/scripts/flow.py`, `session.py`, `worker.py` | One issue from tests to review; one Claude session; one parallel build |
| `kit/scripts/merge.py` | Tests the exact commit, checks the posted review, merges into the loop branch |
| `kit/scripts/pass_.py` | The end-of-loop pass |
| `kit/scripts/setup.py` | Labels, loop branch, board issue, first test run |
| `kit/hooks/guard.py`, `kit/hooks/stop.py` | The refusals and the Stop hook |

The tests are in `kit/tests/`; `python3 kit/tests/run.py` runs them in
parallel in about 100 seconds.

## Settings, in `AGENTS.md`

`Test command` is the only required key. The others are listed in the README.

## Simplification as a step

- **Per batch.** There is no per-issue simplify pass. The end-of-loop pass runs one "simplify and reconcile" session over the
  batch's changed code and build notes and files one inbox issue; nothing is
  edited by the pass.
- **Per release.** One pass whose only job is deletion: list what no run used
  since the last release, and remove it unless the maintainer says why it
  stays.

## Standing decisions

- **The loop is continuous.** It waits for new `ready` issues and ends after
  12 idle hours or a stop file.
- **Unattended sessions run in Claude Code's auto mode, guarded by hooks.**
  No builder sandbox.
- **The test lock's escape hatch:** an existing test may change or be
  deleted only when the issue names its path.
- **A release needs a smoke run** in an empty repository: one small issue
  built end to end.

## Failures the design answers

Each comes from a failure seen in a real run.

- **Merges.** The review verdict names the exact head commit it reviewed;
  `merge.py` refuses when the head differs, so a fix commit cannot merge
  without review. `merge.py` is the authoritative line: it merges the
  reviewed commit, or a conflict-free merge of it with the current loop
  branch, after a full test run on that exact commit.
- **Early warnings in the guard.** In the loop's own sessions the guard hook
  also refuses `gh`, `git push`, `git merge`, branch switches and checkouts.
  It matches the text of the command, so it can be routed around. It is an
  early warning, and `merge.py` and branch protection are the lines that hold.
- **Stops in code, not only words.** `merge.py` parks an issue whose diff
  touches a protected path, a workflow file, a lockfile or manifest, or a
  settings file or an existing test, unless the issue names that path.
- **Setup.** `scripts/setup.py` creates the missing labels, the loop branch
  (from the default branch), a pinned `Factory` issue and a `.lite/` line in
  `.gitignore`. It runs the Test command, after the Prepare command, on a fresh
  checkout of the loop branch as a preflight, and reports the optional
  settings that are set. Running it again adds only what is missing. It opens
  no pull request and does not check `core.hooksPath`.
- **Never silent.** `loop.py` runs unbuffered, prints a line before every
  long step, and gives a reason on every exit, including "nothing to build".
- **Session isolation.** Sessions start with project-only settings and a
  strict MCP configuration, so they do not inherit the person's plugins and
  MCP servers (one project's sessions carried 41).
- **Limits.** A Claude usage limit or a GitHub rate limit waits for its
  reset; it is neither a failure nor a park.
- **Safe to repeat.** Every step can run twice after a crash: create a
  pull request only if none exists, and clear `building` before a retry.
- **Permission refusals** park the issue with the refused path named; they
  are not retried.
- **Held dependants.** A park notice and the finish summary name the issues
  that wait on the parked one.
- **Review verdict format.** The verdict is a delimited block; prose around
  it is kept, not refused.
- **Reviewers get paths, not pasted content,** so a large project cannot
  overflow their input.
- **Only issues a collaborator labelled `ready` are built.** In a public
  repository, issue text is data, and a stranger's issue must never reach an
  unattended builder.
- **A minimal event log** (one line per step) feeds the release's deletion
  pass.

## Checking the work: three independent layers

Recommended on the evidence. Each layer catches failures the others miss.

1. **Acceptance tests first, by a separate session.** Before the builder
   starts, a fresh test-writer session writes one test per acceptance
   criterion from the issue alone, commits them to the issue branch, and
   shows that each fails on the base with an assertion. Only those tests
   run, so this takes minutes.

   Criteria that already hold get no test, so there is no "already true"
   marking to get wrong. Why: in two earlier projects, builders edited tests
   and turned off a lint rule to pass, and marcdown's tests were written by
   the same agent that wrote the code.
2. **The test lock.** The builder cannot edit those tests or any existing
   test, except a path the issue names.
3. **A reviewer after the build, in a fresh session.** It reads the issue,
   the diff and `PLAN.md`; is given the latest full test result and runs only
   targeted tests and the oracle (renders, measurements); checks each criterion with evidence; may add a test that
   reproduces a finding; and gives a verdict naming the head commit. Why:
   the contract review caught real defects that frozen tests missed
   (graphwright, docla, the 10 November batch), and marcdown's reviewers
   returned changes on 10 of the first 16 issues, caught from renders and
   reading.

Then fix rounds, at most three, each re-reviewed. A test the writer got
wrong is not a dead end: the reviewer can flag it and the coordinator parks
the issue with the reason, as a `needs-user` question.

## From version 1

Version 1 of the kit (tag `v1.7.0`, kept in history) moved each piece through
a state machine written in code, and wrote and froze judges at shaping time.
Version 2 replaces it with the design above. What was dropped, and why:

- **The state machine and typed reasons.** A gate decided when a piece was
  ready, with a reason for each refusal. Each field failure added a state,
  a reason or a setting, and each rule needed more rules at its edges. Version
  2 keeps the states as labels on GitHub issues and leaves proportionate
  judgement to the sessions.
- **Judges written and frozen at shaping.** Writing and proving a judge,
  then the ready check, ran the full suite about three times per piece. In
  one batch, judge-writing pieces without a blocker took 61 to 105 minutes
  before any build, and five of ten judges needed a hand fix. Version 2 writes
  the tests in the run, from the acceptance criteria, in a separate session,
  and locks them against the builder.
- **The dashboard server.** The board is one pinned GitHub issue, which needs
  no server and works from a phone.
- **Size.** Version 1 measured 9,144 lines of kit Python in 44 scripts, 124
  test files and a 20-minute suite; the sum of its concepts and settings was
  the cost of every change. Version 2 is about 2,100 lines of Python in 10
  scripts and hooks, with a suite of about 100 seconds.

Evidence. The marcdown run, with no kit code, took 32 minutes of shaping and
merged 41 pieces in 11 hours. The docla trial of version 2 merged all 8 of its
first batch, about 50 minutes per issue before the fast path and 19 to 25
minutes after it, with 23 merges unattended and 20 of 24 approved in the first
review round. The docla history on version 1 counted 56 runs, 55 attended,
29 that merged nothing, and 94 backward moves against 53 merges. These are not
a controlled comparison: the projects and the periods differ.

Carried over as ideas, not code: the fix round, retries for transient
failures, the standing loop, deviations, the stops list, the oracle question,
one final pull request into the default branch merged by the person, and the
guard hook.

## Details of the loop

### The fast path

A Test command that takes minutes must not run on every step. Per issue it
runs in full twice: once in the Stop hook when the builder finishes, and once
in `merge.py` on the exact commit it merges. Everything between is targeted.

- `Test files command` runs only some test files (`{files}` stands for their
  paths; the Test command stands in when it is absent). `Prepare command`
  runs once per worktree and per fresh checkout, before any test run.
- The fails-first step runs only the locked files with the Test files command
  and requires a failure by assertion, not a syntax error in the test.
- The builder runs the Test files command while it works. The Stop hook runs
  the full Test and Check commands once when it finishes, and records the
  commit and the output tails in `.lite/passed-<session>`. The flow reuses that
  pass when it is for the head commit, and otherwise runs the full commands in
  a fresh checkout.
- There is no per-issue simplify step. The reviewer gets the latest test
  result in its prompt and runs only targeted checks.
- A folder that is not a registered worktree is renamed aside, never deleted.
  A Stop hook command lives in its own process group, listed in
  `LITE_GROUPS`, so the loop kills it with the session.

### Parallel builds

`Parallel: N` (default 1) sets how many builds run at once.

- With 1, the loop builds in its own process. With more, each build is
  `scripts/worker.py`, a separate process that runs the same crash, retry and
  park logic for one issue and leaves its result in
  `.lite/builds/<issue>.result`. The supervisor, one loop under one lock,
  polls the processes. A process that ends with no result died: the issue is
  queued once more, then parked.
- Claim: the `building` label goes on before the process starts. A new build
  starts while fewer than N run, an eligible issue exists and the machine has
  headroom (load average below the CPU count; on macOS, free plus inactive
  memory above 1.5 GB). The first build always starts. Each deferral is
  logged once per reason.
- Merge queue: `.lite/merge.lock` (an advisory file lock, freed when its
  holder dies) is held while the loop branch is merged into the issue branch
  and `merge.merge` runs. A clean catch-up is pushed and the verdict's HEAD
  follows it. Conflicts leave the merge open and return the issue to its
  builder for a fix round.
- If the merge is refused and the loop branch moved, the lock is released,
  the catch-up runs once more, and the merge is retried.
- The board reads each running build's step from `.lite/builds/<issue>.step`.
- Supervision: workers run in their own session and the pid goes to
  `.lite/builds/<issue>.pid`. A worker running longer than 3 times
  `Session minutes` plus 30 minutes is killed with its group and counts as a
  death. If a recorded pid is still alive at start, the loop refuses rather
  than claim those issues again.
- When the loop exits with builds left, it ends them; that skips their
  worktree cleanup, which the next start's worktree pruning covers.
- Stop: no new build starts and running builds finish their issue. Worktree,
  process group and Docker cleanup stay with each build.

### Checks on each merge, and the pass

- The test writer's tests are proven to fail at the base commit before the
  builder starts.
- Stop hooks keep a builder from ending while the Test or Check command
  fails, and a test writer from ending without a test.
- `Check command` (guardrails, run after every Test command run) and
  `Smoke command` (the real artefact, run by the pass only) are optional.
- After each merge the issue and the pull request get a `## Built` note, and
  the reviewer's follow-ups become `inbox` issues.
- `PLAN.md` has `## Lessons`, `## Standing approvals` and `## Surfaces`;
  issues may carry a `## Failing test`.
- After new merges the drain runs the end-of-loop pass (smoke, drift, red
  team with failing tests, rubric, lessons, simplify and reconcile), puts its
  report in the pull request body, and the board shows the last pass.
  The README describes it in detail.

### Limits on defect rounds and paths

- `Defect rounds` (default 2) caps the passes that queue confirmed defects as
  `ready` between merges of issues the person queued. Past it, defects go to
  `inbox` with their failing tests. The count is in `.lite/pass.json`; an
  unreadable file counts as the limit reached and a missing one as zero.
- A red-team test must also pass the Check command with the file in place.
  The test writer may format a given failing test (layout only) so the locked
  file never fails the Check command. The fails-first run after that commit
  still requires a failure by assertion, or the writer is resumed once and the
  issue then parks.
- One `Simplify and reconcile` issue is open at a time; later passes comment
  on it.
- A collaborator's clear "yes" to a park that names one test path adds that
  path to the issue's `## Paths the builder may change`. Nothing else grants a
  path.
- The reviewer may write scratch files in the system temp folder only.
