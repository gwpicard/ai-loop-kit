# AI Loop Kit lite

A continuous factory for building software with Claude Code while you are
away. You shape and approve work in a session with Claude. A loop on your
own computer then builds each approved issue, has it reviewed by a second
session and merges it into a loop branch. You merge that branch into your
default branch yourself, in one pull request.

The loop never asks you for input. It stops on an issue only for a decision
that `PLAN.md` says only a person can make, and carries on with the rest.

## Install

You need `git`, `gh` signed in to GitHub, Claude Code and `python3` (3.9 or
later). Add this repository as a plugin marketplace in Claude Code, then
install the `ai-loop-lite` plugin from it.

## Set up a project

Put this in the project's `AGENTS.md`:

    ## Loop
    Test command: <the command that runs your tests>

Optional keys in the same section: `Loop branch` (default `loop/main`),
`Builder model` and `Reviewer model` (default `sonnet`), `Protected paths`,
`Idle hours` (default 12) and `Max rounds` (default 3).

Ask Claude to set up the loop, or run `python3 scripts/setup.py` from the
project root. It creates the labels, the loop branch, a pinned `Factory`
issue, a `.lite/` line in `.gitignore` (commit it yourself) and runs your
Test command on a fresh copy of the loop branch. Running it again changes
nothing that exists.

## Shape

Use the shape skill in any session, at any time. It turns inbox issues or an
idea into issues with acceptance criteria and dependencies, asks one batch
of questions, records decisions in `PLAN.md` and clears person-only
prerequisites first. On your single yes it labels the issues `ready`.

## Run

Use the loop skill, or run `nohup bin/loop run > .lite/loop.out 2>&1 &`.
Stop it with `bin/loop stop`. It ends by itself after the idle limit.

## The board and replying

The pinned `Factory` issue shows what is building, what needs you, the
queue, what waits to be shaped, what has landed and the open pull request.
To answer a parked issue, reply on it. The loop reads your reply, queues the
issue again and gives the reply to the next build.

## What is guaranteed by code

- Merging happens only in `merge.py`. It merges the exact commit the
  reviewer approved, after the Test command passes on that commit.
- It refuses a diff that touches a protected path, a workflow, a lockfile or
  package manifest, a settings file, or an existing test, unless the issue
  names that path. The tests the test writer added are locked the same way.
- The guard hook refuses pushes to the default branch, force pushes and
  recursive deletes for every session in the project, and secrets in writes.
- An issue is built only if a collaborator with write access added `ready`.
- Nothing is merged into the default branch. Only you do that.

## What is guaranteed by instruction to the model

The briefs tell sessions never to ask, to record deviations and to park on
the stops list. The reviewer is told to check every acceptance criterion
with evidence. Code does not enforce these.

## What is not guaranteed

- The reviewer can miss a defect.
- The guard works on the text of commands and is best effort.
- Behaviour that only a person can see, such as how an interaction feels,
  is unchecked unless the issue gives an agent a way to check it.
- Notifications are not built yet. Watch the board.
- Branch protection on the default branch is your job. Setup recommends it
  and never changes repository settings.
