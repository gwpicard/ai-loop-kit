---
name: loop
description: Start, stop and watch the AI Loop Kit factory that builds ready issues unattended. Use when the person says run the loop, start building, stop the loop, show the board, or answers a parked issue.
---

# Run the loop

The loop builds issues labelled `ready`, reviews them and merges them into
the loop branch. This skill only starts, stops and reads it. Never build,
review or merge by hand, and never push to the default branch.

`<plugin>` is this skill's plugin folder, two levels up.

## Set up first

If the project has no `## Loop` section in `AGENTS.md`, or the loop refuses
because the project is not set up, use the setup skill first.

## Start and stop

Start: `mkdir -p .loop && nohup <plugin>/bin/loop run > .loop/loop.out 2>&1 &`
from the project root. A second start is refused while a loop is alive. `tail .loop/loop.out`
shows its steps.
Stop: `<plugin>/bin/loop stop`; the loop ends after its current step.

## Read the board

The board is the pinned `Factory` issue: what is building, what needs the
person, the queue, what waits to be shaped, what landed, and the open pull
request into the default branch, and the last end-of-loop pass (time,
confirmed defects, inbox issues created, link to the pull request). Find it with
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
