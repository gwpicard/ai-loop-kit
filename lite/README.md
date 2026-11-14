# AI Loop Kit lite

A continuous factory for building software with Claude Code while you are
away. You shape and approve work with Claude. A loop on your computer builds
each approved issue, has a second session review it and merges it into a
loop branch. You merge that branch into your default branch yourself.

The loop never asks for input. It parks an issue only for a decision that
`PLAN.md` reserves for a person, and carries on.

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

`Check command` is the project's guardrails (lint baseline, size budgets,
architecture tests). It runs after every Test command run for an issue, and
a failure counts like a test failure. `Smoke command` uses the real built
artefact, such as the CLI on real input; only the end-of-loop pass runs it.
Setup reports both; neither is required.

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
from the project root. `<plugin>/bin/loop stop` stops it; so does the idle limit.

The pinned `Factory` issue is the board: what is building, what needs you,
the queue, what has landed, the open pull request and the last pass. To
answer a parked issue, reply on it; the loop queues it again and gives your
reply to the next build.

## What each issue gets

- **Tests first.** A test writer commits tests from the acceptance criteria
  before any code. They must fail at the base commit; if they pass, the
  writer is asked once to fix them, then the issue is parked.
- **Stop hooks.** The builder cannot end a session while the Test or Check
  command fails (three blocks at most); the test writer cannot end one
  without a new test file (two at most).
- **Build note.** After the merge, the issue and the pull request get a
  `## Built` note: what changed and why, deviations, the merge and files.
- **Follow-ups.** Worthwhile non-blocking work the reviewer names becomes
  an `inbox` issue, once, linked to its source.
- **Lessons and failing tests.** Sessions append traps to `## Lessons`. A
  `## Failing test` section is committed as given by the test writer.

## The end-of-loop pass

When the drain finds merges it has not examined and the Test and Check
commands pass on the loop branch, it runs one pass before it opens or
refreshes the pull request. Each session is fresh, reads the loop branch in
a temporary worktree and is told not to edit tracked files; the guard hook
blocks this best-effort.

- Smoke: the `Smoke command`, if set.
- Drift: the batch diff against `PLAN.md` (decisions, budgets, duplication).
- Red team: one session per bullet under `## Surfaces` in `PLAN.md` (four at
  most). A finding counts only with a test file under `.lite/pass/` at the
  path where it belongs (such as `.lite/pass/tests/test_x.py`). The pass
  copies it there and it must fail the Test command; a second session
  must confirm it.
- Rubric: readability, error handling, weak tests, fixed sleeps, dead code.
- Lessons and proposed guardrails.

A confirmed defect becomes an issue with a `## Failing test` section. It is
labelled `ready` only if a paragraph under `## Standing approvals` in
`PLAN.md` says positively that a confirmed defect may be queued as ready,
with no negation such as not, never, no or unless; anything unclear fails
closed to `inbox`. Every other finding, proposed guardrail and lesson goes
into one `inbox` issue per pass, a checkbox each. Lessons reach `PLAN.md`
through an issue, never a direct commit. The report goes into the pull
request body. A pass that fails is noted there and never blocks it. The board
shows a `Last pass` section; `.lite/pass.json` remembers it. After a pass
without errors nothing reruns until new merges arrive; after one with errors
the next drain tries again.

## What the loop may leave behind

After each session the loop kills what is left in the session's process
group and logs it; a process that detaches itself from its parent can
survive. If Docker answers, the containers, networks and volumes a session
made are removed and listed in the build note; images stay as cache. At exit
the loop prunes worktrees, deletes logs older than 14 days and prints the
worktrees and issue branches left. Outside services are on the stops list.

## What is guaranteed by code

- Issue branches merge into the loop branch only through `merge.py`. It
  merges the exact commit the reviewer approved, after the Test command
  passes on that commit.
- It refuses a diff that touches a protected path, a workflow, a lockfile or
  package manifest, a settings file, or an existing test, unless the issue
  lists it in its `## Paths the builder may change` section; a path named
  elsewhere grants nothing. The test writer's tests are locked the same way.
- The guard hook refuses pushes to the default branch, force pushes,
  recursive deletes and secrets in writes, in the loop's own sessions
  (through `--settings`) and wherever the plugin is enabled.
- An issue is built only if a collaborator with write access added `ready`.
- The loop never merges into the default branch; it only opens a pull
  request. Branch protection is what stops any other path.

## What is guaranteed by instruction to the model

The briefs tell sessions never to ask, to record deviations and to park on
the stops list, and the reviewer to check every criterion with evidence.
Code does not enforce these.

## What is not guaranteed

- Pass sessions are told not to edit tracked files; the guard blocks it
  best-effort, on the text of commands, as it does everything else.
- The reviewer and the pass can miss a defect, and a red-team test proves
  only what it exercises.
- Behaviour that only a person can see, such as how an interaction feels,
  is unchecked unless the issue gives an agent a way to check it.
- Notifications are not built; watch the board. Branch protection is your
  job: setup recommends it, never sets it.
