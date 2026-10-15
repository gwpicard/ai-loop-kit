# v1 rehearsal round 2 findings (15 October 2026)

Branch kit at the hardening commit. Passed: bar-wrong on attempt 1 (thin), a reviewer fix kept in the pull request (node), every cheating builder form refused (guard and gate). Not reached: a build longer than 10 minutes (the longest piece took 6 minutes over three attempts). Failed or partial: Quality with real mutmut, kill during review, setup on a configured project.

Fix each on kit/v1: a docs/LEDGER.md row (seen in: v1 rehearsal round 2), a test, then the fix.

A. `kit/quality/mutmut-changed.py` fails against real mutmut 3.8:
- the filter names are wrong: mutmut names module functions `module.x_func__mutmut_N` and methods `module.xǁClassǁmethod__mutmut_N`;
- test files in the diff are taken as changed functions, so the filter matches nothing and mutmut aborts; only files under mutmut's source paths count;
- results parsing replaces dots with underscores, and plain `mutmut results` lists only mutants that were not killed, so a run with every mutant killed still fails; use `mutmut results --all true`, fail on any `survived`, and fail when no mutant for the changed functions was tested.
The rehearsal agent's working patch is in this folder as `rehearsal-2-mutmut.diff`; check it, do not copy it blindly. Add a test that runs real mutmut on a tiny fixture when mutmut is installed, and a test with recorded real mutmut output for CI. Doctor's dry-run passed only because main has no changed functions: make doctor say plainly that the mutation check could not be exercised on main, rather than "ok".

B. A run killed during review leaves `review/*` worktrees and branches. At run start, remove every review worktree and `review/*` branch the kit made (by `git worktree remove` and `git branch -D` on names it recognises), and report what it removed.

C. Doctor's Quality dry-run runs without the Test command's output, so a CRAP line that reads `.coverage` fails on a fresh main. Setup must write a self-contained CRAP command (`python -m coverage run -m pytest && python -m coverage json && crap.py ...`) or doctor must run the Test command first. Pick one and say which in docs/V1.md.

D. Smaller:
- Without `LOOP_BUILDER`, the guard lets `eval "git push --force"` and `xargs rm -r` through. docs/V1.md says force pushes and recursive deletes are refused everywhere: refuse them in every session.
- The hostile-builder test in tests/test_scenarios.py is weak: its fake judge fails anyway, and the assertion matches text in a comment. Make the fake builder pass the judge and cheat, and assert on the refusal reason. Make the refusal for an edited `AGENTS.md` say "the loop settings changed", not "judge files differ".
- `run` right after `gate.py move <n> ready` twice printed "Nothing is ready" (GitHub label lag). Retry the ready list a few times over about 20 seconds before saying nothing is ready.
- Old in-project `.loop/worktrees/` folders still break plain lint in the Node repo; doctor should name them and say the person may remove them.

E. Scenario 1 is still unproven: add an automated test where a fake builder streams events for longer than the idle limit and passes, and keep the field scenario for round 3.
