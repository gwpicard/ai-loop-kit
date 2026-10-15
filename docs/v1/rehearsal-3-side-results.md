# Round 3 side results

| Scenario | Result | Evidence |
| --- | --- | --- |
| S: setup again | FAIL | Setup doctor reported that the CRAP dry-run failed on fresh `main` because its old Test command produced no coverage data. The follow-up fresh-clone check hit the kit guard's refusal of `rm -rf`; this was recorded and the rehearsal continued. The setup changes remain on unmerged branch `setup/quality` (commit `cae8ce7`). I skipped S and moved to Q when `gh pr list` returned HTTP 401, as the task allowed. No setup PR was completed or merged. |
| Q: real mutation testing | FAIL | Piece 15, “Reject blank habit name in done and remove”, passed its judge and all 33 tests on the second run. The final diff was limited to `habits/cli.py` and `tests/judge/test_blank_name.py`; `cmd_add`, `cmd_list` and `cmd_count` match `main`. PR 16 was open, mergeable and clean. The quality scripts did not produce valid passing results: see below. The requested merge command was refused by the kit guard (“agents do not merge. the person merges the pull request”), so PR 16 remains open. |

## Q quality evidence

- On the piece branch, `kit/quality/mutmut-changed.py origin/main` printed `no changed Python functions found` and exited 0. This was a vacuous result because the branch had no `pyproject.toml` source paths.
- With the setup branch's `pyproject.toml` copied into a scratch worktree, the script exited 1: mutmut 3.3.1 did not recognise `source_paths` and reported `FileNotFoundError: Could not figure out where the code to mutate is.`
- With `paths_to_mutate = ["habits/"]` added in the scratch copy, mutmut generated mutants but then exited 1 with `AttributeError: 'NoneType' object has no attribute 'max_stack_depth'`. The CLI tests run `python -m habits` in subprocesses, so no mutant was scored.
- `coverage run -m pytest` passed all 33 tests but recorded 0% coverage for `habits/cli.py`, because the subprocess tests did not report coverage. `crap.py --coverage coverage.json --base origin/main` exited 0 with “changed functions are at or below 30”. The score came from complexity alone: `cmd_done` 30, `cmd_remove` 20, `reject_blank` 6. The CRAP result is not meaningful with 0% coverage.
- The first review added a `cmd_add` refactor despite the contract marking `add` out of scope. Contract review flagged it, but the run still opened PR 16. I returned the piece with `person-rejected`; the second run removed the refactor, and the final contract review found no scope issue.

Suggested `docs/LEDGER.md` rows, each marked v1.1:

| v1.1 | Doctor CRAP dry-run on fresh main | The proposed coverage-based command fails when the Test command on fresh `main` produces no coverage file. | Doctor reports plainly that the coverage check could not be exercised, and the proposed dry-run succeeds on fresh `main` without manual edits. |
| v1.1 | Mutmut configuration and subprocess tests | The setup config uses `source_paths`, which mutmut 3.3.1 did not recognise; after switching to `paths_to_mutate`, mutmut generated mutants but crashed before scoring them because the CLI tests run in subprocesses. | Use a supported mutmut setting and exercise changed code through a runner that can score these subprocess tests. |
| v1.1 | Coverage across CLI subprocesses | Coverage reports 0% for `habits/cli.py`, yet CRAP exits 0 at its threshold based on complexity alone. | Collect coverage from the CLI subprocesses before treating a CRAP result as evidence. |
| v1.1 | Contract review findings at submit | The first run opened a PR after contract review flagged an out-of-scope change to `cmd_add`. | A contract review finding about scope returns the piece for correction before a PR is opened. |
