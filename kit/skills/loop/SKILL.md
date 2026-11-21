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

If the project has no `loop.json`, or the loop refuses
because the project is not set up, use the setup skill first.

## Confirm the agents, before every start

Read the `Builder`, `Test writer`, `Reviewer` and `Pass` keys from
`loop.json` (each `<agent> <model>`, default `claude sonnet`). Show the
four to the person and ask once whether to change any. Write a change to
`loop.json` before the start. Display them as `Builder:`, `Test writer:`,
`Reviewer:` and `Pass:`. The agent is `claude` or `codex`; Codex is a
preview.

For machine-specific concurrency or idle limits, edit `Parallel` or
`Idle hours` in the git-ignored `loop.local.json`. The loop reloads both
settings files at the start of each cycle, so no restart is needed.

## Start and stop

Start: `mkdir -p .loop && nohup <plugin>/bin/loop run > .loop/loop.out 2>&1 &`
from the project root. A second start is refused while a loop is alive. `tail .loop/loop.out`
shows its steps.
Stop: `<plugin>/bin/loop stop`; the loop ends after its current step.
Pause: `<plugin>/bin/loop pause` freezes the loop and every process it
started, with nothing killed, for when the Mac is slow. Processor use stops at
once; memory is not freed at once. `<plugin>/bin/loop resume` continues every
build where it was. A session step may fail once on resume, because a timer or
request outside the kit ran out meanwhile; that counts as a build crash. The
board shows `Paused since` while the loop is paused, and `loop stop` on a
paused loop resumes it first.

## Read the board

Run `<plugin>/bin/loop status` first for "what happened" questions.
Use `--since <time>` to change its 12-hour window.

The board is the pinned `Factory` issue: what is building, what needs the
person (parked issues, unbuilt dependencies, the open pull request into the
default branch and a conflict), and one progress line for each open milestone with its closed and total counts and a link.
GitHub's milestones page shows the same progress in full. Find it with
`gh issue list --search "Factory in:title"`, read it with `gh issue view`,
and summarise it.

## Answer a parked issue

A parked issue carries `needs-user` and a comment headed `Needs you`. The
person answers by replying on that issue. If the person answers here, post
their words on it with `gh issue comment`. The loop reads the reply,
queues the issue again and passes the reply to the next build.

## After a drain

Run `<plugin>/bin/loop report` for a compact view of what changed and why
before merging the loop branch. It reads local git refs and events, plus
each issue's build note through a read-only GitHub call, without a session
or GitHub writes. The same text appears under `What changed` in the final
pull request body.

When merges are new and the Test and Check commands pass on the loop
branch, the loop runs the end-of-loop pass and puts its report in the pull
request body. Read it with `gh pr view`. Its simplify and reconcile session
files one `inbox` issue of behaviour-preserving changes. All findings,
including confirmed defects with their failing tests, arrive as `inbox`
issues. Shape them like any other issue. Do not queue anything yourself:
the shape skill does that, with the person's yes. Follow-ups from reviewers
also arrive as `inbox` issues.
