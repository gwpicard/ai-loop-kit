# v1 rehearsal findings (15 Oct 2026, overnight)

Passed: guard (4 hostile forms refused), conftest change refused, killed run recovered, gate.py stop, node feature piece, install feature and fix pieces (after repairs). Fix each finding below on kit/v1: first a docs/LEDGER.md row (seen in: the v1 rehearsals), then a test that shows the failure, then the fix.

1. Setup never offers the standards file or protected paths unless asked (all three repos). kit/skills/setup/SKILL.md has no standards step. Add a setup step that offers both, with a recommended default, on the person's yes.

2. mutmut leaves an untracked `mutants/` folder in the build folder; pytest then fails with "import file mismatch", and the builder cannot remove it. The run must own tool output: exclude and clean known tool output folders (mutants/, .stryker-tmp/, coverage files) between attempts without a recursive delete by the agent (use the run's own safe removal of paths it recorded, or run Quality in a separate fresh copy). Setup should also set pytest testpaths when it adds mutmut.

3. A Quality command that can never pass was accepted (mutmut found no test for any mutant, because tests run the CLI through a subprocess). Setup and `gate.py doctor` must dry-run each Quality command on a fresh copy of main and refuse to write one that fails. A Quality failure must be given back with a reason that names the failing check, typed `environment` when it fails on main too, never "the judge still fails".

4. CRAP plus the "no unnamed test file" rule trapped the builder. The builder brief must state the CRAP rule plainly (keep new branches in new small functions; changed functions must not score worse than on main) and that a refused compound shell command should be retried as simple commands or done with the Edit tool. Also: the builder's own new tests outside the judge were removed because the Contract did not name the file; allow NEW test files the builder adds (the rule is about changing EXISTING tests), and say so in the brief.

5. The builder cannot report bar-wrong: run.py reads `.loop/outcome` but kit/briefs/builder.md never mentions it. Add the instruction to the brief, and a test that a contradictory judge ends as bar-wrong on attempt 1, not builder-failed after 3.

6. `gate.py stop` records the give-back with type bar-wrong. Use a distinct type `stopped` (add to the type list and to report), and never overwrite an earlier, real failure reason.

7. Killing run.py leaves the `claude -p` builder running (orphaned, ppid 1). Start builders and reviewers in the run's own process group or a new session the run tracks, kill them on SIGTERM and SIGINT, and at run start refuse or clean up when an orphan builder from the lock's run is still alive.

8. Minor:
 - The gate's "wrong reason" filter matched "No such file or directory" inside an assertion message. Judge the error type, not the message text.
 - Judge writer reused an ID name (test_D5_...) that clashed with a new D5 in an edited file. The judge-writer brief: when editing a judge file, keep IDs unique and rename stale tests.
 - Setup wrote mutmut keys deprecated in mutmut 3.8 (paths_to_mutate, tests_dir). Use the current keys.
 - Old in-project `.loop/worktrees/` folders break plain `npm test` in the main folder; doctor should warn and say how to remove them (by the person).
 - The standards reviewer never committed a fix in any rehearsal. Check the reviewer can commit small fixes in practice (it said "the brief forbids changing tests", which is right, but non-test fixes should be possible). Add a test with a fake reviewer that commits a non-test fix and the gate keeps it.

When all are done: run tests/run-all.sh and tests/house-rules.sh until both pass, push kit/v1, add a "Rehearsal findings fixed" list to the draft PR body, and stop. Do not merge.
