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
- 17 Nov 2026: the steps for trying the product live in a `## Try it`
  section of `PLAN.md`, written at shaping. The final pull request shows
  them, with the loop branch and its head commit, at the top of its
  hands-on checks. Reason: a hands-on check needs a build the person can
  run, and nothing told them how to get one. The steps are prose for a
  person, so they belong in the plan, not in a setting.
- 17 Nov 2026: `loop pause` freezes the running loop and everything it
  started, and `loop resume` continues it where it was. The pause kills
  nothing. Paused time does not count against the build cap, the session
  limit or a Test command timeout. A paused loop stays paused until the
  person resumes or stops it. Timers outside the kit, such as Claude Code's
  own hook timeout or a request in flight, may fail once on resume; that
  counts as a build crash. No variant kills builds to free memory at once.
  Reason: the Mac slowed or ran short of memory during runs, `loop stop`
  waits for running builds to finish, and killing a build discards the
  uncommitted work in its worktree.
- 19 Nov 2026: a review returns CHANGES only for a blocking finding: an
  acceptance criterion not met, a project rule broken, data or user work
  lost, or existing behaviour broken. Every other verified finding,
  including a builder's extra test that cannot fail, is a follow-up that
  becomes an `inbox` issue when the issue merges. From the second round,
  the reviewer blocks only on an earlier finding that is still unfixed or
  on something the fix broke. There is no setting for a stricter review.
  Reason: on ai-docs-kit, review rounds chased one new edge case after
  another until issues parked with every criterion met, and the person
  stepped in four or five times a night. The locked tests are already
  shown to fail before the code exists.
- 19 Nov 2026: when the only conflict between an issue branch and the loop
  branch is in `PLAN.md`, and both sides only added lines, the loop keeps
  both sides, the loop branch's lines first, and goes on without a builder
  round or a park. Any other conflict goes to the builder as before.
  Reason: on ai-docs-kit, issues parked on `PLAN.md` conflicts that were
  resolved each time by keeping both sides, and a shaping session's
  `PLAN.md` pull request met a builder's lines at the end of the same
  section.

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

- Issue 575: the issue names `.loop/logs/preflight.log`, but the kit keeps its logs and ignores only `.lite/`. The tests expect `.lite/logs/preflight.log`, beside the session logs.
- Issue 575: setup's preflight now also runs the Check command (the criterion says each Prepare, Test and Check command that ran is logged).
- Issue 575: `copy_repo` in `kit/tests/helpers.py` gives a second repository in the same folder its own subfolder, because a locked test builds two repositories in one folder.
- Issue 564: the person approved editing one existing test in `kit/tests/test_pass.py` (the Three rubric finding now has a `file:line` and a scripted confirm reply), because the criterion requires it.
- Issue 564: when the confirm reply is unreadable or the open-issue list is truncated, only rubric findings are filed; drift, held, guardrails, lessons, simplify and red-team candidates stay unqueued as before.
- Issue 562: step 5 of the shape skill is the oracle question again (prerequisites moved to step 6), because the locked test finds that step by the number 5 and a merged step 1 had moved it to 6.
- Issue 580: the issue says `LOOP_*`, but the kit's variables are `LITE_*`; the tests check every `LITE_*` variable `session.run` sets. The sandbox criterion (commit in the worktree, write under `.loop/`) needs the real Codex and has no test; the builder records the sandbox options under this heading.
- Issue 580: sandbox options for a Codex builder: `-s workspace-write` on a new session, plus `-c sandbox_mode="workspace-write"` on resume (`exec resume` has no `-s`), and `-c sandbox_workspace_write.writable_roots=[<git common dir>]` on both, because `--add-dir` is also missing from `exec resume` and a worktree's commits write into the main checkout's `.git`. `.loop/` and `.lite/` sit inside the worktree, so they need no extra option. Not run against the real Codex.
- Issue 581: a Codex session gets the guard as a PreToolUse hook (matcher `Bash|apply_patch`) and the stop check as a Stop hook, both passed as `-c hooks=...` on every start and resume, with `LITE_AGENT=codex` set so `guard.py` refuses what it cannot parse. The kit passes `--dangerously-bypass-hook-trust` because Codex otherwise asks for persisted trust of the hooks, which an unattended run cannot give; the only hooks it runs are the two the kit writes itself from its own folder. Not run against the real Codex: the tests use the fake `codex`.
- Issue 582: the Codex usage-limit text is not known and was not run against the real Codex. The wait reuses `LIMIT` (`usage limit|limit reached`) on Codex's error events and output, and `_wait_seconds` (a `|<epoch>` reset, else 30 minutes). The builder could not record real Codex text; the first real limit shows whether the pattern matches.
- Issue 582: the start check reads `codex --version`, `codex features list` (a `hooks` line) and `--help` of `exec` and `exec resume` for the flags `-s -m -c --json -o --dangerously-bypass-hook-trust`; `-s` is not required on `exec resume`, which has none.
- Issue 714: `kit/tests/test_loop_failed_crash_comment_polling.py` is outside the allowed paths, but the test writer added it in an earlier commit and it is locked, so it stays. It reruns the base tests with short sleeps injected before each `subprocess.run`, as a Linux regression check.
- Issue 714: mutation check run in an uncommitted scratch copy under `.loop/scratch714` (the crash comment's `try`/`except` removed, the call kept): `test_loop_ends_and_issue_is_not_stranded` fails with "the loop waits for a build that is not running". The scratch folder stays untracked because recursive deletes are forbidden; the person may remove it.
- Issue 725: the fake in `fake_codex_check.py` is left as it was, because the locked comma-flag test rewrites its `print("  " + flag)` line to print the comma form itself. That test's no-refusal check now looks for `codex` in the output, since the run goes on to refuse for the loop branch missing on origin.
- Issue 719: the `refused:` lines of `loop pause` and `loop resume` have no `next:` line, because the locked tests require exactly one line.
