# AI Loop Kit

A continuous factory for building software with Claude Code while you are
away. You shape work with Claude and approve it once. A loop on your own
computer then builds each approved issue, has a second Claude session review
it and merges it into a loop branch. You merge that branch into your default
branch yourself.

The loop never asks for input. It parks an issue only for a decision that the
project's `PLAN.md` reserves for a person, and it carries on with the rest.

Version 2.0.1. The design and its reasons are in [docs/DESIGN.md](docs/DESIGN.md).
The full settings reference is in [kit/README.md](kit/README.md).

## Install

You need `git`, `gh` signed in to GitHub, Claude Code and `python3`
(the kit's tests run on 3.13 in CI). In Claude Code:

    /plugin marketplace add gwpicard/ai-loop-kit
    /plugin install ai-loop-kit@ai-loop-kit

## Set up a project

Put this in the project's `AGENTS.md`:

    ## Loop
    Test command: <the command that runs your tests>

Then ask Claude to set up the loop. The setup skill proposes these lines from
your project if they are missing, and asks you to confirm. Setup creates the
labels, the loop branch (`loop/main` by default), a pinned `Factory` issue
that serves as the board, and a `.loop/` line in `.gitignore` for you to
commit. It runs your Test command on a fresh copy of the loop branch. Running
it again is safe. Optional keys, such as `Parallel`, `Protected paths` and
`Check command`, are listed in the reference.

## Shape

Use the shape skill in any session, at any time. It turns inbox issues or an
idea into issues with acceptance criteria and dependencies, asks one batch of
questions, records decisions in `PLAN.md` and clears the prerequisites only a
person can clear. On your single yes it labels the issues `ready`. You can
shape while the loop runs; new issues join the queue.

## Run

Ask Claude to start the loop, or from the project root:

    mkdir -p .loop && nohup <plugin>/bin/loop run > .loop/loop.out 2>&1 &

`<plugin>/bin/loop stop` stops it, and it stops by itself after 12 idle
hours. For each ready issue the loop writes failing tests first in one
session, has a builder make them pass in another, has a reviewer check every
acceptance criterion in a third, and merges through `merge.py` only after the
full Test command passes on the exact commit. With `Parallel: N` it builds up
to N issues at once.

When the queue drains, an end-of-loop pass reads the whole batch (drift from
the plan, red-team tests, readability, lessons, simplification) and the loop
opens one pull request into your default branch.

## The board

The pinned `Factory` issue on GitHub shows what is building, what needs you,
the queue, what has landed, the open pull request and the last pass. To answer
a parked issue, reply on it; the loop queues it again and gives your reply to
the next build.

## What is guaranteed

By code, in `merge.py`, the authoritative line:

- The loop merges issues only through `merge.py`; in the loop's sessions the hook refuses `gh` and `git merge`; branch protection on the default branch stops other routes. `merge.py` merges the reviewed
  commit, or a conflict-free merge of it, after a full test run on that exact
  commit.
- A diff that touches a protected path, a workflow, a lockfile, a settings
  file or an existing test is refused, unless the issue names that path.
- The loop never merges into the default branch. It opens a pull request.
- Only issues that a collaborator with write access labelled `ready` are built.

By the guard hook, an early warning that matches the text of a command and can
be routed around:

- Everywhere: pushes to the default branch, force pushes and recursive
  deletes are refused.
- In the loop's sessions: `gh`, `git push`, `git merge`, branch switches and
  writes to the test writer's tests are also refused.
- Secrets are checked in content a session writes, not in diffs.

## What is not guaranteed

- The briefs tell sessions never to ask and to record deviations. Code does
  not enforce that.
- The reviewer and the end-of-loop pass can miss a defect.
- Behaviour that only a person can see is unchecked unless the issue gives an
  agent a way to check it.
- Notifications are not built: watch the board.
- Branch protection on your default branch is your job. Setup only recommends
  it.

## Moving from version 1

See the 2.0.0 entry in [CHANGELOG.md](CHANGELOG.md).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). The
kit is released under the licence in [LICENSE](LICENSE).
