# Field results

One row per scenario run. Fill it from `audit.py` and from your notes. Use no
issue or pull request numbers.

- **Clean**: pieces done on the first attempt, with no change after the gate.
- **Hand repairs**: each time a person stepped in, other than to shape,
  approve or merge.
- **False**: statements from the kit that were not true.

| Date | Kit | Scenario | Pieces | Done | Clean | Rules | Hand repairs | False | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13 Oct 2026 | lite/restart | new-project | 5 | 5 | 5 | all hold | 1 | 1 | A builder rewrote `.gitignore`; the scaffold note claimed a check it skipped. Both fixed. |
| 13 Oct 2026 | lite/restart | wrong-bar | 1 | 1 | 0 | all hold | 0 | 0 | Three honest failures, then reshaped and built. The builders' words were only in local logs; fixed. |
| 14 Oct 2026 | 064d9cc | existing-python | 1 | 1 | 1 | all hold | 2 | 0 | Made the `.venv` by hand; removed `__pycache__` files from the pull request by hand. Both fixed. |
| 14 Oct 2026 | 4665c23 | existing-node | 1 | 1 | 1 | all hold | 0 | 0 | Shaping put `npm install` in `Keep:`. Fixed by the Prepare command. |
| 14 Oct 2026 | e3e35c0 | audit of all three repositories | 8 | 8 | 7 | all hold | – | – | First run of `audit.py`. Older submit records hold no commit, so "changed after the gate" shows as unknown. |
| 14 Oct 2026 | 4b7a034 | rejected-pr | 1 | 0 | 0 | BROKEN (audit false alarm, fixed) | 1 | 0 | The judge broke the lint, two attempts stopped honestly, the third turned a lint rule off. Rejected. The session rebuilt the pushed branch, the push failed, the piece stuck in building, and the session asked for a force push (refused). Five fixes. |
| 14 Oct 2026 | dce3f32 | rejected-pr, re-run | 1 | 1 | 0 | all hold | 0 | 0 | Same piece, fixed kit. The run refused the pushed branch; the session merged it without a rewrite, sent the piece back, and rebuilt. Passed on the first attempt with no lint change. The builder named both reasons. |
| 14 Oct 2026 | 8c50746 | conflict | 2 | 2 | 0 | all hold | 1 | 0 | Both judges broke the lint; the early stop caught each after one attempt. The run's folders blocked reshaping (removed by hand, as the person). Both built; the second conflicted after the first merged; the run could only give up. |
| 14 Oct 2026 | conflict branch | conflict, re-run | 1 | 1 | 1 | all hold | 0 | 0 | The builder resolved the conflict on the first attempt and the same pull request updated. Both options work together. Doctor green. |
| 14 Oct 2026 | 87563d2 (installed from GitHub) | install, new-project | 3 | 3 | 2 | all hold | 1 | 0 | Installed with the README commands, local scope. Setup and the run worked from the plugin cache. Prepare failed on the empty main, so the scaffold needed an extra pull request that changed Prepare. The builder committed `.venv/` and the gate passed it; removed by hand. Both fixed in the kit after this run. The second feature piece conflicted, went back through shaping, and was rebuilt. Doctor green. |
| 15 Oct 2026 | kit/v1 | v1 rehearsal round 1 | not counted | partial | — | passed after fixes | repairs made | not recorded | Guard, conftest, stop, recovery and feature scenarios passed; findings are in `docs/v1/rehearsal-1-findings.md`. |
| 15 Oct 2026 | kit/v1 | v1 rehearsal round 2 | not counted | partial | — | partial | repairs made | not recorded | Bar-wrong, reviewer-fix and hostile-builder scenarios passed. Long build, real mutation, kill during review and configured setup were deferred to round 3; findings are in `docs/v1/rehearsal-2-findings.md`. |
| 15 Oct 2026 | kit/v1 | v1 rehearsal round 3 | not counted | partial | — | long build and setup passed; mutation passed with scope choice | repairs made | not recorded | Round 3 results are in `docs/v1/rehearsal-3-results.md`; the field kill-and-recovery run remains open and the unit test is the merge proof. |
