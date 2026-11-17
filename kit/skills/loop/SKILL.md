---
name: loop
description: Start, stop and watch the AI Loop Kit factory that builds ready issues unattended. Use when the person says run the loop, start building, stop the loop, show the board, or answers a parked issue.
---

# Run the loop

The loop builds issues labelled `ready`, reviews them and merges them into
the loop branch. This skill only starts, stops and reads it. Never build,
review or merge by hand, and never push to the default branch.

`<plugin>` is this skill's plugin folder, two levels up.

## First, check the kit version

Run `<plugin>/bin/loop check-version` from the project root. If it exits
non-zero, report its two lines and stop.

## Set up, once per project

Run `python3 <plugin>/scripts/setup.py` from the project root. If it prints
`refused:`, do the `next:` step. If it adds `.lite/` to `.gitignore`, tell
the person to commit that line. If the preflight fails, report it and stop.
Setup also reports the optional `Test files command`, `Prepare command`,
`Check command` and `Smoke command` that are set, `Parallel` (builds at once, default 1)
and `Defect rounds` (default 2). If the Test command is slow
(minutes), suggest a `Test files command` (targeted runs) and a `Prepare
command` (install steps), which keep it to two full runs per issue. If the
project has many independent issues and a machine with spare CPU and memory,
suggest `Parallel: 3`; the loop then runs builds as separate processes, queues
their merges, and says on the board and in `.lite/loop.out` when it waits for
headroom. If no
`Smoke command` is set, mention that the end-of-loop pass can run a smoke
check only when one is in `AGENTS.md`.

## Confirm the agents, before every start

Read `Builder:`, `Test writer:`, `Reviewer:` and `Pass:` from the `## Loop`
section of `AGENTS.md` (each `<agent> <model>`, default `claude sonnet`; an
older `Builder model` or `Reviewer model` line sets two of them). Show the
four to the person and ask once whether to change any. Write a change to
`AGENTS.md` before the start. Only `claude` is accepted for now.

## Start and stop

Start: `mkdir -p .lite && nohup <plugin>/bin/loop run > .lite/loop.out 2>&1 &`
from the project root. A second start is refused while a loop is alive. `tail .lite/loop.out`
shows its steps.
Stop: `<plugin>/bin/loop stop`; the loop ends after its current step.

## Read the board

The board is the pinned `Factory` issue: what is building, what needs the
person (parked issues, unbuilt dependencies, the open pull request into the
default branch, a conflict, the defect rounds limit notice), and one progress
line for each open milestone with its closed and total counts and a link.
GitHub's milestones page shows the same progress in full. Find it with
`gh issue list --search "Factory in:title"`, read it with `gh issue view`,
and summarise it.

## Answer a parked issue

A parked issue carries `needs-user` and a comment headed `Needs you`. The
person answers by replying on that issue. If the person answers here, post
their words on it with `gh issue comment`. The loop reads the reply,
queues the issue again and passes the reply to the next build.

## After a drain

When merges are new and the Test and Check commands pass on the loop
branch, the loop runs the end-of-loop pass and puts its report in the pull
request body. Read it with `gh pr view`. Its simplify and reconcile session
files one `inbox` issue of behaviour-preserving changes. Findings are `inbox` issues, except a
confirmed defect, which is `ready` only if `PLAN.md` says so positively under
`## Standing approvals`. Do not queue anything yourself: the shape skill does that, with
the person's yes. Follow-ups from reviewers also arrive as `inbox` issues.
