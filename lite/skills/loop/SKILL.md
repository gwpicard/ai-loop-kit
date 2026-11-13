---
name: loop
description: Start, stop and watch the AI Loop Lite factory that builds ready issues unattended. Use when the person says run the loop, start building, stop the loop, show the board, or answers a parked issue.
---

# Run the loop
The loop builds issues labelled `ready`, reviews them and merges them into
the loop branch. This skill only starts, stops and reads it. Never build,
review or merge by hand, and never push to the default branch.

`<plugin>` is this skill's plugin folder, two levels up.

## Set up, once per project

Run `python3 <plugin>/scripts/setup.py` from the project root. If it prints
`refused:`, do the `next:` step. If it adds `.lite/` to `.gitignore`, tell
the person to commit that line. If the preflight fails, report it and stop.

## Start and stop

Start: `mkdir -p .lite && nohup <plugin>/bin/loop run > .lite/loop.out 2>&1 &`
from the project root. A second start is refused while a loop is alive. `tail .lite/loop.out`
shows its steps.
Stop: `<plugin>/bin/loop stop`; the loop ends after its current step.

## Read the board

The board is the pinned `Factory` issue: what is building, what needs the
person, the queue, what waits to be shaped, what landed, and the open pull
request into the default branch. Find it with
`gh issue list --search "Factory in:title"`, read it with `gh issue view`,
and summarise it.

## Answer a parked issue

A parked issue carries `needs-user` and a comment headed `Needs you`. The
person answers by replying on that issue. If the person answers here, post
their words on it with `gh issue comment`. The loop reads the reply,
queues the issue again and passes the reply to the next build.
