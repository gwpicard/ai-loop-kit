# Code review of the hardening and round 2 fixes (15 October 2026)

A read-only review of commits de942ce, 11dffbf and fea3104. Suite: 149 tests, 1:34 in a clean worktree. Each item: ledger row, test, fix.

Must fix before v1 merges:
1. run.py is loaded twice in a real run. review.py (`from run import ...`), pr.py (`import run`) and loopkit.py (`from run import track_process`) import `run`, but `python3 run.py` runs as `__main__`, so a second copy loads. Process groups registered by reviewers, judges, Prepare and Quality go to the other copy: the SIGTERM handler and the lock never see them. The main-ref cache and `AttemptIdle` are split too. Move process tracking, the cache and `AttemptIdle` into a small module that is never `__main__` (for example `kit/scripts/procs.py`), and add a test that starts a real `python3 run.py` subprocess, sends SIGTERM during a fake review, and checks no child is left.
2. `_pump_session` can hang for ever: when claude exits but a background child keeps the pipe open, EOF never comes and the timers stop. After the process ends, wait about 3 seconds, then kill the group and stop reading.
3. `quality_fails_on_main` (gate.py) does not pass the Test command, so a CRAP line that needs coverage fails on main and a fixable failure is called `environment` and never retried. Pass the frozen Test command. Key the `.loop/main-quality-*.json` cache on a hash of the command and the main commit, so it is never stale or shared between commands.

Should fix:
4. mutmut: treat every status other than `killed` (no tests, timeout, suspicious) as a failure; anchor name matching on `__mutmut_` so `x_foo` does not match `x_foobar`; only select changed files under mutmut's source paths; skip nested functions mutmut does not create; when a changed function has zero mutants, report it as "nothing to mutate" and pass, not fail.
5. Guard is too broad outside build sessions: `eval "$(pyenv init -)"` and `xargs ... rm` without `-r` are refused. Check the string inside eval instead of refusing all eval; refuse `xargs rm` only with -r, -R or -f. Also catch `git push origin` and `git push -u origin` while on main, and respect `git -C` when reading the current branch.
6. Idle: a long silent tool call (a 15-minute test run) only counts as activity through file times, and the folder walk runs about 10 times a second without skipping build folders. Poll every 2 seconds, skip `dist/`, `build/`, `__pycache__`, and log `result` events with an error so a rate limit or auth failure is visible.
7. H1 test is weak (asserts only that output is non-empty); `command_env` still reads protected paths from the build folder's AGENTS.md. Use the frozen value and assert on the refusal reason.
8. H9 hostile-builder test covers one cheat only; add the rest the plan named (Quality deletion, rename, conftest.py, standards file). The kill-during-review test should use a real signal (see 1).
