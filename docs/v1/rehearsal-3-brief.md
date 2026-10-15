# Round 3 field rehearsal, run by Codex

You run this yourself. First make sure kit/v1 is pushed and all four CI jobs pass (gh pr checks 184 --watch); fix CI first if not.

Drive real Claude Code test sessions through the `orca` CLI (run `orca skills get orca-cli` once for the guide):
- `orca terminal create --worktree path:<repo> --title rehearsal3 --command "claude --plugin-dir /Users/guillaumepicard/orca/workspaces/ai-loop-kit/v1-build/kit" --json`
- `orca terminal wait --terminal <h> --for tui-idle --timeout-ms <ms> --json` and check result.wait.satisfied
- `orca terminal send --terminal <h> --text "<text>" --enter --json` (a numbered choice: the number alone, no --enter)
- `orca terminal read --terminal <h> --json` (result.terminal.tail)
Close your rehearsal terminals at the end.

Act as the person: take the kit's recommended options and approve reasonable specs. Merging pull requests in the three test repositories is allowed: `gh pr merge --repo gwpicard/loop-test-<name> <n> --merge`, after reading the file list; never merge one that adds generated files.

Scenarios (only what failed or was not reached in round 2; see docs/v1/rehearsal-2-findings.md):
1. Long build (loop-test-install): shape one piece big enough that a build attempt runs past 10 minutes (for example a report with several output formats, sorting, filtering and a summary section). Record each attempt's time from .loop/logs. Pass: no idle kill on an attempt that streams activity, and the piece passes.
2. Real mutation testing (loop-test-install): run setup again so the Quality lines match this kit; shape a fix to an existing function. Pass: the branch's own mutmut-changed.py and crap.py run against real mutmut and coverage with true results, and a surviving mutant, if any, is fixed on a later attempt.
3. Kill during review (loop-test-node): start a run; when the reviewer `claude -p` appears (ps), kill only the run.py process id. Start the run again. Pass: the piece is recovered, and no reviewer process, review worktree or review/* branch remains, including the stale review/*-14-1-* ones from round 1.
4. Setup again (loop-test-install): pass when doctor's Quality dry-run passes on a fresh main without manual edits, and says plainly when the mutation check could not be exercised.

Rules: never merge, push to main of, or change gwpicard/ai-loop-kit except commits on kit/v1; never create repositories; never force-push; no recursive delete in any spelling; never edit any .claude/settings*.json; check `df -h /System/Volumes/Data` before each scenario and stop below 5 GB free.

When a scenario fails: add a docs/LEDGER.md row, a test, then the fix on kit/v1, and run that scenario again once. Then write docs/v1/rehearsal-3-results.md (a PASS or FAIL table with evidence, plus findings), run both suites, push, wait for all four CI jobs, update the PR body, and stop. Do not ask questions; note choices in the results file.
