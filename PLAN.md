# Plan

Every agent reads this file before it starts. The person adds to it while
shaping. Where an issue and this file differ, this file wins. `AGENTS.md`
holds the house rules; where the two differ, `AGENTS.md` wins.

## Decisions

- 16 Nov 2026: a passing suite is not proof that the product works for a
  person. Tests for behaviour a person triggers go through the entry point
  the person uses. Reason: in one project, about 33 defects a person found
  by hand sat under a green suite of about 2,200 tests, because the tests
  called internal code in place of the keys and menus a person uses.
- 16 Nov 2026: hands-on checks never park the loop. The final pull request
  lists them as unticked boxes, which the person ticks before merging it.
  Reason: walking away stays the goal, and the person's check happens once,
  at the end of a batch.
- 16 Nov 2026: the final pull request body follows the Summary, Evidence and
  Merge danger format of the AI Hero `/pr` skill, written by one read-only
  session per batch. It never blocks the drain. Reason: the person wants to
  understand a batch, its evidence and its risk before opening the diff.
- 16 Nov 2026: rubric findings are validated in the existing confirm
  session, so the pass stays at nine sessions at most. Reason: an unchecked
  rubric finding forces the person to triage it; a validator confirmed 22
  of 23 high and medium findings in one project.
- 16 Nov 2026: whether the Test and Check commands cover every target and
  source folder is asked at shaping and checked by the drift review, with no
  new setup code. Reason: keep the kit small; the drift review already reads
  every batch.
- 16 Nov 2026: progress is read on GitHub's milestones page; the board keeps
  only what is building, what needs the person and a progress line per
  milestone. No notifications for now. Reason: the person followed a
  milestones page through a whole walk-away run, while the dashboard of
  version 1 died unseen and the board's long lists were not what the person
  followed.
- 16 Nov 2026: the kit refuses to run when the running version is older than
  the version the clone was set up with, and tells the person to restart
  Claude Code. Reason: a session keeps the plugin version it started with,
  and in one project an upgraded project started the old kit's loop an hour
  after the update.
- 16 Nov 2026: issues left with the labels of kit 1.x are not migrated or
  reported by the kit. Reason: the one active project that had them was
  converted by hand.
- 16 Nov 2026: every role (builder, test writer, reviewer, pass) can run on
  Claude or Codex, chosen per role in the `## Loop` section of `AGENTS.md`
  and shown to the person before each start. Reason: building on Claude
  alone uses up the person's Claude usage, and a review by a different
  model is a more independent check.
- 16 Nov 2026: a Codex session gets the same guard and stop check as a
  Claude session, and the guard refuses what it cannot parse; otherwise the
  kit refuses to run Codex for that role. On a usage limit a session waits
  and resumes, with no fallback agent. Reason: the safety rules must not
  depend on which agent runs.

## Product rules

- British spelling, no em or en dashes, paragraphs under about 100 words.
- No issue or pull request number in a tracked file.
- The kit uses the Python standard library only.
- Keep the kit small enough to read in one sitting. Prefer a precise
  instruction in a brief over new code; when a change makes code, text or a
  check redundant, the same change removes it.
- A change to a brief keeps the reply block formats (VERDICT, TESTS,
  FINDINGS, PARK) unless the issue says otherwise.

## Stops

An agent that needs one of these ends its reply with
`PARK: <question> | <recommended answer>` and stops work on the issue:

- spending money or changing billing
- credentials, secrets or access rights
- permissions, repository or service settings
- irreversible data changes
- anything that makes the project public
- a new dependency, or a change to a protected path
- any decision only the person can make

## Lessons

One line per trap that a later session would hit too. Sessions append here.
Keep the section under 30 lines: merge lines or drop the oldest when full.
- `kit/tests/test_entry_point.py` imports `flow` without `helpers`; locked, so `kit/tests/run.py` puts `kit/scripts` on the child's path.

## Standing approvals

A confirmed defect with a failing test, found by the end-of-loop pass, may be queued as ready without the person's yes. Everything else goes to the inbox.

## Surfaces

- The loop supervisor: claims, retries, parks and the drain in `kit/scripts/loop.py`
- The merge checks in `kit/scripts/merge.py`
- The guard hook, `kit/hooks/guard.py`
- The parsing of session replies: the VERDICT, TESTS, FINDINGS and PARK blocks in `kit/scripts/flow.py` and `kit/scripts/pass_.py`

## Deviations

Builders append here when they take the closest approach to a decision the
plan did not make: the issue, what they chose, and why.
- Issue 564: the person approved editing one existing test in `kit/tests/test_pass.py` (the Three rubric finding now has a `file:line` and a scripted confirm reply), because the criterion requires it.
- Issue 564: when the confirm reply is unreadable or the open-issue list is truncated, only rubric findings are filed; drift, held, guardrails, lessons, simplify and red-team candidates stay unqueued as before.
