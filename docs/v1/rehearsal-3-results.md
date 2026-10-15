# Round 3 field rehearsal results

Date: 15 October 2026

| # | Repository | Result | Evidence |
| --- | --- | --- | --- |
| 1 | loop-test-install | PASS | The ready record froze `Idle limit: 2`. Attempt 2 ran for 278.742 seconds, passed the judge and was not stopped for idleness. The run log shows that Quality failed on attempt 1 and passed after attempt 2. The builder changed files and added tests during attempt 2. No separate file-activity reset event was logged, so the reset is inferred from the run lasting past the idle limit without output until the end. |
| 2 | loop-test-install | PASS, with a scope choice | The kit's mutmut and CRAP commands ran against real coverage and mutmut. Four surviving mutants were reported after attempt 1. Attempt 2 changed the affected code, added tests, killed the survivors and passed both Quality checks. The work began as a feature piece, not a separately shaped fix piece. |
| 3 | loop-test-node | PASS | Field run open, unit test is the proof. The automated test runs `python3 run.py` as a subprocess, sends real SIGTERM during a standards review, and checks that the reviewer child exits. The maintainer accepts this as the v1 merge proof; the field run remains open as v1.1 work. |
| 4 | loop-test-install | PASS | Doctor passed on fresh main and reported that mutation testing could not be exercised there. The explicit idle override was removed from `setup/idle-limit`; the branch and main now resolve to the ten-minute default. The setup branch is clean. |
| S | loop-test-thin | FAIL | Setup found the existing Test command but the fresh-main CRAP dry-run had no coverage data. A follow-up check hit a guard refusal for `rm -rf`, so the rehearsal stopped there. No setup pull request was completed or merged. |
| Q | loop-test-thin | NOT RUN | The real mutation check on a fix was not started after scenario S stopped at the refused command. Mutation testing remains experimental. |

## Review findings fixed

- Item 1: shared process, cache and idle state now live in `kit/scripts/procs.py`. A subprocess test sends SIGTERM during a fake review and checks that no child remains.
- Item 2: the output pump waits three seconds after the parent exits, then stops a child that keeps the pipe open.
- Item 3: the fresh-main Quality check runs the frozen Test command first. Its cache key includes the Quality command and main commit.
- Item 6: idle activity checks run every two seconds, skip generated build folders and log `result` errors. Field confirmation of file-activity reset remains v1.1 work.
- Item 7: commands use the frozen protected paths, and the test checks the specific refusal.
- Item 8: hostile-builder tests cover Quality deletion, test renames, `conftest.py` and standards-file edits.
- Items 4 and 5 were left untouched under the maintainer amendment. They are assigned to the separate branch.

## Choices I made

- I used the setup branch to freeze the two-minute idle limit, then removed the explicit line so the default is restored. The empty setup pull request remains open because it now changes no files; I did not merge or close it.
- The report judge first disagreed with its own tie rule and an existing test. I kept the existing behaviour, corrected the Contract and judge to use one alphabetical tie rule, and continued on the same piece branch.
- I counted the real mutation run as the Quality scenario because the failed check found survivors in changed functions, and the later attempt fixed them. No separate mutation-only piece was shaped.
- The field kill-and-recovery run remains open. The automated real-SIGTERM test is the proof accepted for v1; the field follow-up is tracked as v1.1 work.
- I merged two earlier Node rehearsal pull requests to make room for a new piece, then stopped its extra shaping attempt before running it after the maintainer closed the field kill window.
- The second Codex stopped setup after the guard refused `rm -rf`. Scenario Q was not run, so the docs and setup skill call mutation testing experimental.

The review findings file and this brief are committed with the rehearsal results. The test-repository pull requests from this extra shaping attempt were not merged.
