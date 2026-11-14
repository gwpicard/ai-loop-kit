# AI Loop Kit lite

A continuous factory for building software with Claude Code while you are
away. You shape and approve work with Claude. A loop on your computer builds
each approved issue, has a second session review it and merges it into a
loop branch. You merge that branch into your default branch yourself.

The loop never asks you for input. It parks an issue only for a decision
that `PLAN.md` reserves for a person, and carries on.

## Install

You need `git`, `gh` signed in to GitHub, Claude Code and `python3` (3.9 or
later). Add this repository as a plugin marketplace in Claude Code, then
install the `ai-loop-lite` plugin from it:

    /plugin marketplace add gwpicard/ai-loop-kit
    /plugin install ai-loop-lite@ai-loop-kit

Below, `<plugin>` is the installed plugin folder (holding `bin/`).

## Set up a project

Put this in the project's `AGENTS.md`:

    ## Loop
    Test command: <the command that runs your tests>

Optional keys in the same section: `Loop branch` (default `loop/main`),
`Builder model` and `Reviewer model` (default `sonnet`), `Protected paths`,
`Idle hours` (default 12) and `Max rounds` (default 3), `Check command` and
`Smoke command`.

`Check command` is the project's guardrails: a lint baseline, size budgets,
architecture tests. It runs after the Test command everywhere the Test
command runs for an issue (the builder's Stop hook, the merge, the drain),
and a failure counts like a test failure. `Smoke command` uses the real
built artefact, such as launching the app on a temporary file or running
the CLI on real input. Only the end-of-loop pass runs it. Setup reports
both; neither is required.

Ask Claude to set up the loop, or run `python3 <plugin>/scripts/setup.py` from
the project root. It creates the labels, the loop branch, a pinned `Factory`
issue, a `.lite/` line in `.gitignore` (commit it yourself) and runs your
Test command on a fresh copy of the loop branch. Running it again changes
nothing that exists.

## Shape

Use the shape skill in any session, at any time. It turns inbox issues or an
idea into issues with acceptance criteria and dependencies, asks one batch
of questions, records decisions in `PLAN.md` and clears person-only
prerequisites first. On your single yes it labels the issues `ready`.

## Run

Use the loop skill, or run
`mkdir -p .lite && nohup <plugin>/bin/loop run > .lite/loop.out 2>&1 &`
from the project root. Stop it with `<plugin>/bin/loop stop`; it also ends
after the idle limit.

## What each issue gets

- **Tests first.** A test writer commits tests from the acceptance criteria
  before any code. The loop runs them at the base commit in a temporary
  worktree; they must fail there. If they pass, the writer is asked once to
  fix them, and the issue is parked if they still pass.
- **Stop hooks.** The builder cannot end its session while the Test or Check
  command fails (three blocks at most). The test writer cannot end it
  without committing a new test file (two blocks at most).
- **Build note.** After the merge, the issue and the pull request get a
  `## Built` comment: what changed and why, deviations, what was not
  exercised, the merged commit and changed files.
- **Follow-ups.** Worthwhile non-blocking work the reviewer names becomes
  an `inbox` issue, once, linked to its source.
- **Lessons.** Sessions append traps to `## Lessons` in `PLAN.md`.
- **Failing test.** An issue may carry a `## Failing test` section; the test
  writer commits it as given, then adds its own.

## The end-of-loop pass

When the drain finds merges it has not yet examined, and the Test and Check
commands pass on the loop branch, it runs one pass before it opens or
refreshes the pull request into the default branch. Each session is fresh,
reads the loop branch in a temporary worktree and is told not to edit
tracked files; the guard hook blocks this on a best-effort basis.

- Smoke: the `Smoke command`, if set.
- Drift: the batch diff against `PLAN.md`, for decisions, budgets,
  duplication and accuracy of docs.
- Red team: one session per bullet under `## Surfaces` in `PLAN.md` (four at
  most). A finding counts only with a test file under `.lite/pass/` that
  fails the Test command; a second session must confirm it.
- Rubric: readability, error handling, tests that restate constants, fixed
  sleeps, dead code.
- Lessons and proposed guardrails.

A confirmed defect becomes an issue with a `## Failing test` section. It is
labelled `ready` only if a paragraph under `## Standing approvals` in
`PLAN.md` says positively that a confirmed defect may be queued as ready, and
contains no negation such as not, never, no or unless. Anything unclear fails
closed to `inbox`, as does every other finding. The template's default
sentence is accepted. Lessons reach `PLAN.md` through an
issue, never a direct commit. The report goes into the pull request body.
A pass that fails is noted in the report and never blocks the pull request.
The board shows a `Last pass` section; `.lite/pass.json` remembers the last pass.
After a pass that finished without errors, nothing reruns until new merges
arrive. After a pass with errors, the next drain tries again.

## The board and replying

The pinned `Factory` issue shows what is building, what needs you, the
queue, what waits to be shaped, what has landed, the open pull request and
the last pass.
To answer a parked issue, reply on it. The loop reads your reply, queues the
issue again and gives the reply to the next build.

## What is guaranteed by code

- Issue branches merge into the loop branch only through `merge.py`. It
  merges the exact commit the reviewer approved, after the Test command
  passes on that commit.
- It refuses a diff that touches a protected path, a workflow, a lockfile or
  package manifest, a settings file, or an existing test, unless the issue
  lists that path in its `## Paths the builder may change` section. A path
  named elsewhere in the issue grants nothing. The tests the test writer
  added are locked the same way.
- The guard hook refuses pushes to the default branch, force pushes,
  recursive deletes and secrets in writes. It applies to the loop's own
  sessions (through `--settings`) and to any session where the plugin is
  enabled.
- An issue is built only if a collaborator with write access added `ready`.
- The loop never merges into the default branch; it only opens a pull
  request. Branch protection is what stops any other path.

## What is guaranteed by instruction to the model

The briefs tell sessions never to ask, to record deviations and to park on
the stops list. The reviewer is told to check every acceptance criterion
with evidence. Code does not enforce these.

## What is not guaranteed

- Pass sessions are told not to edit tracked files; the guard blocks it
  only on a best-effort basis.
- The reviewer and the pass can miss a defect, and a red-team test proves
  only what it exercises.
- The guard works on the text of commands and is best effort.
- Behaviour that only a person can see, such as how an interaction feels,
  is unchecked unless the issue gives an agent a way to check it.
- Notifications are not built. Watch the board.
- Branch protection on the default branch is your job. Setup recommends it
  and never changes repository settings.
