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
