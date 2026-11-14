# AI Loop Kit lite: design

Draft, 13 November 2026. For the maintainer's review before anything is built.

## What changed in the second build (14 November 2026)

The first build merged issues; this one makes each merge more reliable and
reviews the whole batch before you see it.

- Tests are proven to fail at the base commit before the builder starts.
- Stop hooks keep a builder from ending while the Test or Check command
  fails, and a test writer from ending without a test.
- Optional `Check command` (guardrails, run after the Test command) and
  `Smoke command` (the real artefact, run by the pass only).
- After each merge: a `## Built` note on the issue and the pull request, and
  the reviewer's follow-ups as `inbox` issues.
- `PLAN.md` gains `## Lessons`, `## Standing approvals` and `## Surfaces`;
  issues may carry a `## Failing test`.
- The drain runs the end-of-loop pass (smoke, drift, red team with failing
  tests, rubric, lessons) after new merges, puts its report in the pull
  request body, and the board shows the last pass. Details are in the
  README. The text below is the first design, kept for its reasoning;
  where it names shell scripts, the code is Python.

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
3. Progress is visible on GitHub. The loop notifies you only when it parks
   an issue or finishes.

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

| Marcdown did | Lite keeps it as |
| --- | --- |
| A plan file with binding decisions | `PLAN.md` in the repository, read by every agent |
| Issues with acceptance criteria, `Depends on`, milestones | The same, from a template |
| A coordinator session dispatching builders and reviewers | The same, restarted per issue by a supervisor (see "Stateless") |
| Sonnet builder, then Sonnet reviewer in its own worktree | The same; every agent works in its own worktree |
| Fix list back to the same builder, at most three rounds | The same |
| "Closest approach, record under Deviations, continue" | The same, bounded by a stops list |
| `needs-user` label with a one-line reply | The same, for anything on the stops list |
| An oracle built early (`MarcdownRender`) | A shaping question: "how will an agent see this is right?" |

## Marcdown's weak spots, and the guard for each

| Weak spot (evidence from the run) | Guard | Kind |
| --- | --- | --- |
| The coordinator merged to `main` itself | Hook refuses any push to, or merge into, `main` or the default branch | Code (`guard.py`, reused) |
| About 20 of 41 fixes merged with no re-check; coordinator edits merged untested | Merging happens only through `merge.sh`, which runs the Test command on the exact commit and merges with `--match-head-commit`. The hook refuses `gh pr merge` from any other command | Code |
| A builder can weaken the tests that judge it | Hook refuses builder edits to existing test files. New tests are allowed. Changing an existing test needs a line in the issue saying so | Code |
| Agents shared one checkout and switched each other's branches | Every builder and reviewer gets its own worktree, created by the supervisor | Code |
| Reviews lived only in agent hand-backs | `merge.sh` refuses unless the review verdict is posted on the pull request | Code |
| The only park happened by accident (a classifier refusal) | A written stops list: money, credentials, permissions, settings, irreversible data, going public, new dependencies. Anything on it parks as `needs-user` | Words, checked by the reviewer |
| Stray worktrees and test processes left running | The supervisor removes its worktrees and kills its process group after each issue | Code |
| One long session holding everything (440k tokens) | One coordinator session per issue; state lives in GitHub | Design |
| Deletes and secrets | Hook refuses recursive deletes, force pushes and secret shapes in a diff | Code (`guard.py`, reused) |

## The factory

### States, as labels on issues

| Label | Meaning | Who sets it |
| --- | --- | --- |
| `inbox` | An idea or report, not shaped yet. Anyone may open one | GitHub, by default, on a new issue |
| `shaping` | Being shaped | The shape skill |
| `ready` | Shaped and approved: in the queue | The shape skill, after your yes |
| `building` | Claimed by the loop | `loop.sh` |
| `needs-user` | Parked on a decision only you can make, with a one-line reply | The coordinator |
| closed | Merged into the loop branch | `merge.sh` |

A milestone groups issues into a batch or a theme and gives a progress bar.
The loop builds only `ready` issues whose `ready` label was added by a
collaborator (checked in the issue's timeline), so a stranger's issue in a
public repository never reaches an unattended builder.

### The board: one pinned issue

`loop.sh` keeps one pinned issue, "Factory", and rewrites its body after
every step. It shows:

- what is building now, and since when;
- what needs you, each with its question and the reply to type;
- the queue in build order, with what each waits on;
- what is waiting to be shaped (`inbox` and `shaping`);
- what landed since your last merge into `main`, and the open final pull
  request;
- the last event and the time of the next check.

It is a dashboard with no server: it lives on GitHub, works from your
phone, and cannot drift from the truth because `loop.sh` writes it from the
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
  loop branch into `main`, posts a summary on the board, notifies you, and
  keeps waiting.
- After you merge that pull request, it merges `main` into the loop branch
  and carries on.
- It ends after 12 hours with nothing to build, or when you create a stop
  file, and says why. Starting it again is one command.

## Stateless

Nothing the loop needs lives in a session or on disk outside the
repository. Any run can stop at any moment and the next one carries on.

- **State is GitHub.** An issue is open (to do), labelled `building` (claimed),
  labelled `needs-user` (parked), or closed (merged into the loop branch).
  The milestone shows progress. `Depends on` lines give the order.
- **Decisions are `PLAN.md`.** Deviations are appended there by the
  builder's pull request, so they merge with the code.
- **The supervisor is a short shell script, `loop.sh`.** It repeats:
  1. Pick the next `ready` issue whose dependencies are closed.
  2. Label it `building` and create a worktree for it.
  3. Start one coordinator session (`claude -p`) for that issue only. The
     session builds, reviews, fixes and calls `merge.sh`, then exits.
  4. If the session crashes or times out, remove the `building` label and
     try the issue once more; a second failure parks it with the reason.
  5. Remove the worktree and any process left behind. Go to 1.
  6. Rewrite the board. When nothing is `ready` or `building`, do the
     drain steps above and wait.
- **One loop per repository**, enforced by a lock file holding the pid; a
  stale lock with a dead pid is taken over.
- **GitHub errors** are retried with a short back-off by `loop.sh` and
  `merge.sh`. A rate limit waits for its reset.

A fresh session per issue means no context growth and no compaction, and a
restart loses nothing.

## The files

| File | What it is | Size target |
| --- | --- | --- |
| `skills/shape/SKILL.md` | Turns an idea into `PLAN.md` plus issues; asks one batch of questions; lists the person-only prerequisites; one approval | 1 page |
| `skills/loop/SKILL.md` | The coordinator's instructions for one issue: build, review, fix rounds, deviations, stops list, `merge.sh` | 1 page |
| `templates/PLAN.md`, `templates/issue.md` | The plan and issue shapes | Short |
| `loop.sh` | The supervisor | About 150 lines |
| `merge.sh` | Test on the exact commit, check the posted review, merge into the loop branch | About 60 lines |
| `hooks/guard.py` | Reused from the current kit, trimmed to the rules above plus the test lock | About 250 lines |
| `briefs/simplify.md` | The code-simplification reviewer | 1 page |

Target: under 500 lines of code and a test suite under one minute.

## Settings, in `AGENTS.md`

`Test command`, `Loop branch`, `Milestone`, and optionally `Builder model`
and `Reviewer model` (default Sonnet). Nothing else.

## Simplification as a step

- **Per pull request.** After the review approves, a simplify pass reviews
  only the changed code, using the code-simplification skill: behaviour
  unchanged, tests unchanged, its own commit, and the Test command passes
  again before `merge.sh`.
- **Per release.** One pass whose only job is deletion: list what no run used
  since the last release, and remove it unless the maintainer says why it
  stays.

## Building the kit with itself, quickly

The lite kit is small, so its suite runs in seconds. Builders run the tests
for the files they touched; `merge.sh` runs the full suite once per issue,
and the final pull request runs it once more. No judge writing, no proof
runs, no ready step.

## What is dropped from the current kit, and what carries over

Dropped: the gate's state machine and typed reasons, judges written and
frozen before the build, the ready check and its suite runs, the dashboard,
the run page, previews (Measure, Critics, mutation, researcher), the size
inventory, 16 settings, about 45 concepts.

Carried over as ideas, not code: the fix round, retries for transient
failures, the standing loop, deviations, the stops list, the oracle
question, one final pull request into `main` merged by the person,
`guard.py`.

The test lock replaces most of what frozen judges gave: the builder cannot
weaken a test that already exists, and the reviewer checks that new tests
cover the acceptance criteria.

## Decided on 13 November 2026

- **The loop is continuous** (late on 13 November, replacing "finish when
  the milestone is empty"): it waits for new `ready` issues and ends after
  12 idle hours or a stop file.
- **Unattended sessions run in Claude Code's auto mode, guarded by hooks.**
  No builder sandbox.
- **The test lock's escape hatch:** an existing test may change or be
  deleted only when the issue names its path.
- **A release needs a smoke run** in an empty repository: one small issue
  built end to end.

## Gaps found by the issue review, now part of the design

Each comes from a failure recorded in an issue.

- **Merges.** The review verdict names the exact head commit it reviewed;
  `merge.sh` refuses when the head differs, so a fix commit cannot merge
  without review. The hook refuses every other merge route: `gh pr merge`,
  merge calls through `gh api`, `git merge` into the loop branch, and
  pushes to a branch after its review.
- **Stops in code, not only words.** `merge.sh` parks an issue whose diff
  touches a protected path, a workflow file, a lockfile or manifest, or a
  settings file, unless the issue names that path.
- **Setup.** One setup pull request before the first run writes the loop
  branch, the milestone and the settings, warns about an absolute
  `core.hooksPath`, and runs the Test command on a fresh worktree under
  auto mode.
- **Never silent.** `loop.sh` runs unbuffered, prints a line before every
  long step, and gives a reason on every exit, including "nothing to build".
- **Session isolation.** Sessions start with project-only settings and a
  strict MCP configuration, so they do not inherit the person's plugins and
  MCP servers (docla's sessions carried 41, including mail and chat).
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
- **Only milestone issues are built.** In a public repository, issue text is
  data, and a stranger's issue must never reach an unattended builder.
- **A minimal event log** (one line per step) feeds the release's deletion
  pass.

## Checking the work: three independent layers

Recommended on the evidence. Each layer catches failures the others miss.

1. **Acceptance tests first, by a separate session.** Before the builder
   starts, a fresh test-writer session writes one test per acceptance
   criterion from the issue alone, commits them to the issue branch, and
   shows that each fails on the base with an assertion. Only those tests
   run, so this takes minutes (pieces 550 to 553 took 3 to 5 minutes for the
   same step). Criteria that already hold get no test, so there is no
   "already true" marking to get wrong; that marking caused five of today's
   ten hand fixes. Why: in docla and doclo, builders edited tests and turned
   off a lint rule to pass, and marcdown's tests were written by the same
   agent that wrote the code.
2. **The test lock.** The builder cannot edit those tests or any existing
   test, except a path the issue names.
3. **A reviewer after the build, in a fresh session.** It reads the issue,
   the diff and `PLAN.md`; runs the Test command and the oracle (renders,
   measurements); checks each criterion with evidence; may add a test that
   reproduces a finding; and gives a verdict naming the head commit. Why:
   the contract review caught real defects that frozen tests missed
   (graphwright, docla, the 10 November batch), and marcdown's reviewers
   returned changes on 10 of the first 16 issues, caught from renders and
   reading.

Then fix rounds, at most three, each re-reviewed. A test the writer got
wrong is not a dead end: the reviewer can flag it and the coordinator parks
the issue with the reason, as a `needs-user` question.

## Open questions

1. Notifications when you are away from the machine: GitHub does not notify
   you of your own login's activity. Options: a separate bot account, an
   email, or a phone push.

## How we decide

1. Build lite by hand in its own folder, marcdown style.
2. Build one docla batch with it.
3. Compare with docla's kit history: hours unattended, times you stepped
   in, defects found after merge.
4. If lite wins, it becomes the kit, and the current code goes to the
   archive.
