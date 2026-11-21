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
- Unknown `.loop/` names are not legacy markers: projects and test fixtures keep their own files there. Refuse only the explicit kit 1.x names or `.lite/`.
- A reload test that replaces builds with fake workers cannot prove retention reaches sessions, hooks and merge checks. Exercise a real build after damaging each settings file, both serially and in a worker.
- JSON accepts whole numbers such as 3.0; normalise count settings to integers before passing Max rounds to range.
- `kit/tests/test_entry_point.py` imports `flow` without `helpers`; locked, so `kit/tests/run.py` puts `kit/scripts` on the child's path.
- Flow fixtures run real session cleanup, which needs `ps`; a sandbox that denies it produces an environment error before the behaviour assertions.
- The test runner drops inherited `LOOP_PROJECT` before starting test processes, so disk checks and events use each fixture. Unsetting it only in a manual command leaves the Stop hook exposed to the same failure.
- Reviewer prompts include the whole brief; keep the literal revert result prefix out of its explanatory prose so a skipped check has no result line.
- Protected paths this issue may change do not unlock existing tests for the test writer; add new tests and leave any conflicting old assertion for the builder.
- Session tests use `ps` to reap child processes; the macOS sandbox may refuse it, so these checks need an approved run outside that sandbox.
- A session environment assertion can pass before a guard fix; invoke the configured hook with the spawned session's environment and prove the test fails on the loop branch.
- The test-lock hook refuses edits to existing tests even when the issue allows them; write judging tests in a new file when instructed to continue.
- The full checks need `ps`; a sandbox that refuses process inspection breaks session and pause tests and can leave their loop processes running. Run with process inspection available and check for surviving test processes.
- A fake GitHub command reading `--body-file -` must read stdin as bytes to preserve CRLF issue bodies.
- The builder guard matches command names inside read-only search patterns; use direct file reads for those names, as the person authorised.
- When hiding Codex, preserve the test runner's sysctl stub; replacing it with the host command can make setup preflight wait on real memory pressure.
- Released kit 2.2.0 leaves `.lite/` behind, sometimes with colliding files; preserve the whole residual folder outside the project after migration rather than deleting it.

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

- Standing-instruction budget: count the root files before migrations, so
  normal setup and dry-run report the same input. Missing files count as zero.
  The check only reads the files; existing settings migrations remain separate.
  Use whitespace-separated words and exclude only a standalone `@AGENTS.md`
  line in `CLAUDE.md`, as the locked acceptance tests require.
  All 16 setup tests and house rules pass. Leave the full suite to merge,
  as the repository's fast-path rule requires.

- Standing-instruction budget tests: add a separate module because existing
  tests stay locked. Invoke setup from the project root with settings already
  in JSON, so settings migration cannot obscure whether the check edits the
  instructions. Treat whitespace-separated tokens as words, exclude only a
  standalone import line, and check both sides of the 1,500-word boundary.
  Vary whitespace and import position; nested instruction files do not count.
  All three tests fail by assertion on the missing warning; below-budget
  silence and preservation of both instruction files already pass.

- Legacy refusal correction: the person's latest instruction supersedes the
  earlier decision to refuse unknown `.loop/` names. Recognise only the
  former kit 1.x names and `.lite/`, removing the current-runtime allowlist.
  Retain those names solely as refusal markers, without restoring their
  migrations. Command regressions cover setup preserving unknown files and
  folders, and `loop run` reaching settings validation with those files intact.
  All 120 targeted tests pass with process inspection available. Keep the
  full Test command reserved for merge, as the earlier builder notes require.

- Legacy migration merge failure: the log retains only the final failure
  line, so the exact failing assertion is unknown. Reproduced a setup
  timeout through the command with the missing-Codex fixture: it discarded
  the runner's memory-pressure stub when rebuilding PATH. Preserve the
  selected sysctl command while keeping Codex hidden. Add a setup-command
  regression that records the stub being read. Run the affected fixture,
  setup and loop tests; the full suite remains reserved for merge.

- Legacy upgrade review: retain the required `.lite/` refusal and explain
  that, after kit 2.2.0 setup succeeds and its loop is stopped, the person
  moves the whole residual folder to an unused backup path outside the
  project before updating. Test the released migration from the local
  `v2.2.0` tag, including colliding logs, then run current setup after that
  move and check the backup. Check legacy layouts at the `loop run` entry
  point before settings, Codex checks or version recording. Cover both
  legacy layouts with settings still in `AGENTS.md` and no `loop.json`.

- Legacy migration removal: recognise current runtime names and session or
  history prefixes instead of retaining the kit 1.x file list. Unknown names
  directly under `.loop/` also require the intermediate upgrade; archived
  files under `.loop/v1/` and `.lite` copies of current files left by the
  intermediate migration remain valid. Keep `tidy`'s return shape for its
  existing callers and check it before `loop run` reads settings, so it
  refuses before reporting missing settings or a missing branch. Remove obsolete move tests and
  retain coverage of the 2.2.0 and 3.0.0 migrations. The full Test command is
  reserved for merge by the builder guard; run targeted checks here.
  Stop the broader Codex fixture check when it waits on host memory pressure;
  leave that unrelated fixture unchanged and run the migration checks separately.

- Legacy migration tests: add a separate acceptance module because existing
  tests stay locked for the test writer. Exercise setup and `loop run` as
  commands, with empty and populated `.lite/` folders and varied kit 1.x
  markers. Require the intermediate-upgrade advice before the ordinary
  missing-loop-branch advice. Existing tests cover the retained migrations;
  the builder must remove the obsolete move assertions and the old file list.

- Protected paths heading: update the loop's park-reply writer as well as
  the named consumers, so an approval uses the section merge reads. Rename
  only heading lines in setup and save each original body before editing,
  retaining line endings and a separate backup for each attempt. Refuse a
  possibly truncated open-issue list before editing any body. Update the
  authorised existing test fixtures to use the new heading; leave the test
  writer's locked acceptance module unchanged. Use targeted checks here;
  the builder guard reserves the full Test command for merge.

- Protected paths heading tests: add a new test module because existing tests
  stay locked. Exercise setup through its command with a fake GitHub that
  records edited bodies, including section order and line-ending variants.
  Check the saved originals and undo commands without prescribing backup
  filenames. Existing park messages name no section, so that criterion
  already holds on this branch and needs no failing test.

- Squash settings: use the build's validated settings snapshot for both
  trailer options. Remove existing copies of the project's sign-off before
  appending it once at the end, keeping other contributors' sign-offs.
  Compare sign-offs case-insensitively and ignore surrounding whitespace,
  so differences in the trailer label's capitalisation do not leave
  duplicates. Both settings default to false and remain excluded from local
  overrides.
- Squash settings validation: add a separate test module for invalid boolean
  values and both options enabled together, leaving the locked tests intact.
  Run the relevant test modules and house rules in the builder; the full
  Test command is reserved for merge by the builder guard.

- Squash settings tests: add a new module beside the squash-message tests,
  reusing their fake GitHub merge fixture because existing tests stay locked.
  Check both boolean values through `merge.merge` and its recorded `--body`,
  with varied trailer order and project git identities. Local-file validation
  already refuses both keys; the existing JSON test checks every key added to
  the defaults and requires the file and key in the diagnostic. Default
  attribution removal already passes.

- Settings in JSON, resumed validation: retain the implementation approved by the latest review, with no further runtime changes. All 478 tests in the 31 changed test modules, including the locked acceptance tests and build-retention regressions, pass with process inspection available. House rules pass too.

- Settings in JSON, merge resolution: keep both the settings decisions and the incoming Spotlight README notes. Their additions to Deviations are independent; the README paragraph and its tests remain intact.

- Settings in JSON: retain legacy parsing only for setup migration and fixture conversion. Existing alias assertions now check role values, and the old unknown-key warning assertion now requires refusal, because the new criteria supersede those behaviours. Migration fixtures stay in AGENTS.md to exercise the real setup command.
- Settings in JSON, Stop hook fix: isolate inherited LOOP_PROJECT in the test runner rather than changing runtime disk checks or requiring callers to unset it. A regression invokes the runner with an enclosing project and checks both the disk tests and the absence of events outside their fixtures.
- Settings in JSON, build retention: scope a validated snapshot to each build, carry it into workers and agent hooks through the subprocess environment, and use it for sessions and merge checks. The supervisor alone reloads files between cycles. The drain and end-of-loop pass use their supplied snapshot too. Test subprocesses discard inherited snapshots so they retain fixture isolation.
- Settings in JSON, runner regression: invoke only the two disk checks that reproduce project leakage, through a test module that selects them. Running every common test inside this regression also ran an unrelated short GitHub timeout check, which failed under concurrent suite load.
- Settings in JSON: require finite, non-negative numbers, with positive whole numbers for Parallel and Max rounds. Normalise those counts to integers, including JSON values written with a decimal point. Reload failures keep the whole previous configuration and report each unchanged error once; recovery clears the warning. When concurrency falls to one, existing worker builds finish before an in-process build starts.

- Spotlight README: the locked tests and house rules passed. After a merge
  refusal reported only "Some checks failed", reran the full Test command
  with `LOOP_PROJECT` unset and approved execution outside the sandbox, as
  the Lessons require. All 837 tests and house rules passed; the merge
  failure did not reproduce, so no code or locked tests changed.

- Spotlight README tests: check the paragraph's required terms and its position
  beside the load and memory explanation, allowing line wrapping and Markdown
  code spans. The issue's reading oracle still judges whether the prose explains
  the relationships clearly. The existing house-rules check covers the final
  criterion; it needs no new test.

- Revert check: run the Test files command once per builder test file in one scratch worktree per review, so a failing file cannot hide a passing one. Report command or preparation errors as unverified rather than as proof. The person authorised the two existing command-count assertions to include the revert runs; all their other checks stay intact.
- Revert check brief: keep the locked brief tests' references to tests that cannot fail and FOLLOW-UPS, but limit that exception to tests guarding existing behaviour explained in DEVIATIONS, as the new criterion requires.

- Revert check tests: exercise complete issue builds with fake agents and a real targeted test command. The builder records a Stop hook pass so each review must still run its own revert check. Cover added, modified and removed non-test files, changed existing tests and all three skip conditions.

- Full Test command restriction: retain the shared session environment code, which already passes both test commands to every role. Replace the environment-only test with a check that invokes the configured guard using the spawned session's environment, with and without a Test files command. It fails on the loop branch for test-writer and pass refusals and passes with the fix.
- Full Test command restriction: put acceptance tests in a new file because the test lock refuses edits to existing tests. The builder must update the old guard assertion that permits the full command for test-writer and pass sessions. Session environment propagation and the test-writer brief already meet their criteria; the brief test fails on the red-team instructions.
- Settings in JSON: judging tests live in a new file because the test-lock hook refused an existing test edit and the follow-up instructed the writer to continue with new tests. Fixture conversion stays with the builder. Live reload uses the run command handler with fake workers and bounded waits; setup and the legacy refusal use subprocess commands.

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
- Issue 753: the locked test looks for "conflicts in" in builder prompts, which also matched a sentence of `kit/briefs/builder.md`; the brief now says "conflicts at the named paths".
