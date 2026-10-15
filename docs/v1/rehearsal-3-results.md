# Round 3 field rehearsal results

Date: 15 October 2026

| # | Repository | Result | Evidence |
| --- | --- | --- | --- |
| 1 | loop-test-install | PASS | The ready record froze `Idle limit: 2`. Attempt 2 ran for 278.742 seconds, passed the judge and was not stopped for idleness. The run log shows that Quality failed on attempt 1 and passed after attempt 2. The builder changed files and added tests during attempt 2. No separate file-activity reset event was logged, so the reset is inferred from the run lasting past the idle limit without output until the end. |
| 2 | loop-test-install | PASS, with a scope choice | The kit's mutmut and CRAP commands ran against real coverage and mutmut. Four surviving mutants were reported after attempt 1. Attempt 2 changed the affected code, added tests, killed the survivors and passed both Quality checks. The work began as a feature piece, not a separately shaped fix piece. |
| 3 | loop-test-node | FAIL | Three runs passed and opened pull requests. I failed to catch a live reviewer process, so I did not send SIGTERM to `run.py` during review or prove recovery after a kill. The reviewer processes exited with their runs. I did not merge test-repository pull requests or raise the waiting limit to make another run possible. |
| 4 | loop-test-install | PASS | Doctor passed on fresh main and reported that mutation testing could not be exercised there. The explicit idle override was removed from `setup/idle-limit`; the branch and main now resolve to the ten-minute default. The setup branch is clean. |

## Review findings fixed

- Item 1: shared process, cache and idle state now live in `kit/scripts/procs.py`. A subprocess test sends SIGTERM during a fake review and checks that no child remains.
- Item 2: the output pump waits three seconds after the parent exits, then stops a child that keeps the pipe open.
- Item 3: the fresh-main Quality check runs the frozen Test command first. Its cache key includes the Quality command and main commit.
- Item 6: idle activity checks run every two seconds, skip generated build folders and log `result` errors.
- Item 7: commands use the frozen protected paths, and the test checks the specific refusal.
- Item 8: hostile-builder tests cover Quality deletion, test renames, `conftest.py` and standards-file edits.
- Items 4 and 5 were left untouched under the maintainer amendment. They are assigned to the separate branch.

## Choices I made

- I used the setup branch to freeze the two-minute idle limit, then removed the explicit line so the default is restored. The empty setup pull request remains open because it now changes no files; I did not merge or close it.
- The report judge first disagreed with its own tie rule and an existing test. I kept the existing behaviour, corrected the Contract and judge to use one alphabetical tie rule, and continued on the same piece branch.
- I counted the real mutation run as the Quality scenario because the failed check found survivors in changed functions, and the later attempt fixed them. No separate mutation-only piece was shaped.
- I marked the node kill scenario as failed because the reviewer window closed before the run process was signalled. The process cleanup regression test for review finding 1 passed in the kit checks.

The review findings file and this brief are committed with the rehearsal results. No test-repository pull request was merged.
