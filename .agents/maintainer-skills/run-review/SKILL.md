---
name: run-review
description: Read what a loop run left behind in a project that uses the kit (the runtime folder, the parks on its issues and the Claude Code transcripts) and find where the kit cost the person time. Records the evidence in docs/OPEN.md and drafts inbox issues for this repository. For the maintainer, after a run or on a schedule. Never queues, labels, answers or edits anything in the project it reads, and never starts or stops its loop. Load it by its path when you want it.
---

# Run review

The end-of-loop pass learns about the project it built. It sees only the
issues merged since the last pass: per issue, the build note, fix rounds,
parks and deviations. It does not read `loop.out` or the person's sessions,
and it files what it finds in the project it built, not in this repository.
Field reviews of real runs were done by hand for that reason. This skill
writes that review down so it is done the same way each time, after a run or
on a schedule.

It answers one question: where did the kit force the person to step in, wait,
ask a question or remember a step during this run, and does `docs/OPEN.md` or
an open issue already record it?

## Scope

Name the project folder, and a start time when the review should cover only
part of the run. Without a start time, cover everything since the last
`run-review` entry for that project in `docs/OPEN.md`, or the last seven days
when there is no entry or no `docs/OPEN.md`. The project may be this repository or any other project
set up for the kit.

If GitHub cannot be reached for the project, say so and stop. A review that
counts no parks because the issue list failed to load reports a clean run that
did not happen.

## Read

Read every source before judging any of them. One problem usually shows in
several places, and a single source alone misjudges its cause.

1. **The runtime folder.** In the project's `.loop/`: `loop.out` for what the
   supervisor did and every "problem, will check again", crash and deferral
   line; `events.jsonl` for the steps; `logs/` for each session's final
   result, where `PARK:` and `DEVIATIONS:` say what a session could not do.
   Older files may sit in `.loop/v1/`.
2. **The issues.** Every issue the run touched, with its comments:
   `gh issue list --state all --limit 200 --search "updated:>=<start date>"`
   (if the list reaches the limit, say so), then
   `gh issue view <n> --json title,labels,body,comments`. Read each
   `## Needs you` comment, the reply under it, and what happened next: queued
   again, parked again, merged.
3. **The person's sessions.** Claude Code keeps one transcript per session as
   JSONL under `~/.claude/projects/`, in a folder named after the session's
   working directory with each `/` replaced by `-`. Read the project's own
   folder and every folder whose name contains the project's folder name
   (worktrees). From the person's messages, collect each time they asked for
   status, asked whether something was running, asked how to do something,
   restarted or stopped the loop, or did a step by hand. From tool results,
   collect each refusal (a hook, the settings, or the auto-mode classifier)
   and each error the agent had to diagnose.
4. **What the kit already knows.** `docs/OPEN.md`, and the open issues in this
   repository: `gh issue list --repo <this repository> --state open`.

Never copy a secret, a token or a private file's contents into a finding.
Quote the person only as far as the evidence needs, a short phrase at most.

## Judge

Sort every finding into one of three kinds.

- **Kit friction.** The kit made the person act where the walk-away goal says
  it should not: a park a reply could not settle, a question asked twice, a
  failure nothing reported, a step the person had to remember, or a behaviour
  the person or their agent had to learn by reading the kit's code.
- **Kit defect.** The kit did something wrong: a crash, a wrong message, a
  check that passed what it should have refused, or refused what it should
  have passed.
- **Not the kit.** The project's own code, the machine, or the person's
  choice. Name it and leave it; it does not go into the kit's backlog.

For each kit finding, count how often it happened in this run, and check it
against `docs/OPEN.md` and the open issues. A finding already recorded gets
this run's count and instances as further evidence. A new one needs at least one concrete instance:
a log line, a comment, or a message, with its time.

Look for the pattern as well as the instances. Several findings with one cause
make one issue, not several. Name the cause in a sentence the maintainer could
check.

## Report

Write one entry in `docs/OPEN.md`, headed with the date, the project and the
words `run-review`, so the next review knows where to start. List each kit
finding with its count, its evidence and, where one exists, the open issue it
adds to.

Then draft one inbox issue for each new kit finding, in the shape of
`kit/templates/issue.md`: the evidence, what the person needs instead, and
acceptance tests that reproduce the failure. Draft them in the session
scratchpad, show the maintainer the titles and a line each, and file them with
the `inbox` label only on the maintainer's yes. For a finding that adds to an
open issue, propose a comment with the new evidence instead.

All issue text passes `.agents/maintainer-skills/writing-review/SKILL.md`
before it is filed.

This review never applies `ready`, never answers a park, never edits an issue
in the project it reads, and never starts or stops a loop. Where it finds
something the person must act on now, such as a parked issue or a dead loop,
it says so at the top of its reply and leaves it there.

## Say

```
<project>, <start> to <end>: <n> kit findings (<n> new, <n> known), <n> not the kit

ACT NOW
  what needs the person today, if anything

NEW
  <title of the drafted issue>
        <count> times. The cause, in a line.

KNOWN, MORE EVIDENCE
  <open issue>  <count> more times this run

NOT THE KIT
  <one line each>
```

## Done when

`docs/OPEN.md` has a dated entry for the project and the period, every kit
finding in it carries its evidence and count, each new finding has a drafted
issue waiting for the maintainer's yes, and the review has changed nothing in
the reviewed project.
