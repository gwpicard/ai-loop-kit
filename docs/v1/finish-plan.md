# v1 finish plan (one hour, strict). Start 13:25, merge decision 14:20.

The maintainer pre-approved merging the v1 pull request (PR v1, kit/v1 into main) at 14:20 if the merge criteria below hold. Claude (the lead session) makes that merge; no Codex merges anything in ai-loop-kit.

## Merge criteria (all must hold)
M1. The three must-fix items of docs/v1/review-2-findings.md are fixed, each with a test (done in 3a26e13; keep them green).
M2. Kill during review recovers the piece and leaves no reviewer process, review worktree or review/* branch. Maintainer decision (15 October, 13:26): the automated test that sends a real SIGTERM to a real `python3 run.py` during a review counts as proof for the merge. The field run is open: a docs/LEDGER.md row marked v1.1 and a GitHub issue track it.
M3. Field: long build with `Idle limit: 2` in loop-test-install: an attempt that streams activity for more than 2 minutes is not killed, and the piece passes.
M4. kit/v1-guard-mutmut is merged into kit/v1.
M5. tests/run-all.sh and tests/house-rules.sh pass; all four CI jobs pass on the final commit.
M6. docs/v1/rehearsal-3-results.md exists with a PASS, FAIL or NOT RUN row for every round 3 scenario, and every open problem is a docs/LEDGER.md row marked "v1.1".
M7. Docs are true: docs/V1.md and docs/DESIGN.md describe the final behaviour; mutation testing is marked "experimental" in docs/V1.md, docs/DESIGN.md and the setup skill unless scenario Q passes on the branch kit.

## Not blocking (record, do not chase)
- Q: real mutmut and CRAP on a fix (second Codex, loop-test-thin).
- S: setup again on a configured project (second Codex, loop-test-thin).
- Review-2 items 6 to 8 not finished: ledger rows marked v1.1.

## Time boxes
- Main Codex: merge kit/v1-guard-mutmut now (resolve conflicts in tests/test_loop.py and tests/test_quality.py by keeping both sides' tests). M3 by 13:45, M2 by 14:00 (15 minutes each at most). Only fix what blocks M2 or M3. 14:00 to 14:10: results file, ledger rows, docs (M6, M7). 14:10: final suites, push, CI watch. Stop when CI is green and print the final commit.
- Second Codex: S then Q in loop-test-thin, finish by 14:00, write its results into .agents/tmp/v1-factory/round3-side-results.md (scenario, PASS/FAIL/NOT RUN, evidence, ledger row). It does not edit the kit; main Codex copies its rows into the results file.
- Any scenario not finished by its box is NOT RUN, with the reason.

## Rules for both
Merging pull requests is allowed only in gwpicard/loop-test-install, loop-test-node and loop-test-thin, after reading the file list (`gh pr merge --repo gwpicard/loop-test-<name> <n> --merge`). Never merge, push to main of, or change gwpicard/ai-loop-kit except commits on kit/v1 (main Codex only). No force-push, no recursive delete in any spelling, never edit any .claude/settings*.json. Close your rehearsal terminals when done. Do not ask questions; note choices in the results file. Check disk (`df -h /System/Volumes/Data`) and stop below 5 GB.
