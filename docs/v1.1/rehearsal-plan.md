# v1.1 rehearsal plan, low Claude use (replaces Step 2 of your brief)

The maintainer is low on Claude credit. Codex drives everything. Claude is used only where the kit itself must run Claude, always on Sonnet, with at most 2 attempts per piece. Target: about 20 short Sonnet sessions in total. Copy this file to docs/v1.1/rehearsal-plan.md and commit it.

Setup for all parts: create /tmp/loop-sonnet (not tracked) containing `#!/bin/sh` and `exec claude --model sonnet "$@"`, make it executable, and export LOOP_CLAUDE=/tmp/loop-sonnet for every run.py and gate.py call. Start any interactive test session with `claude --model sonnet --plugin-dir <this worktree>/kit`. All work in ~/PROJECTS/loop-test-install.

## Part A: no Claude at all (Codex runs the scripts directly), about 30 minutes
A1 Setup again on a configured project: run `python3 <kit>/scripts/gate.py doctor` with a proposed Quality line, the P4 way (the proposed loop section applied to a fresh copy of main). PASS: doctor passes with no manual edits, or names exactly what is missing.
A2 Real mutation testing: on a branch with a changed in-process function, run the Quality commands (mutmut 3.8 or later in the repo's .venv, and crap.py) through the gate's Quality path. PASS: true results, a survivor fails, a killed set passes, no source paths fails.
A3 Goal piece, written by Codex: capture an issue with gate.py capture (Intent, Out of scope, Contract, Judge with Kind: goal, Measure, Target, Keep), for example "counting a 50 MB file takes under N ms" where main is clearly slower. Run gate.py check and move it to ready. PASS: ready refuses while Measure meets the target on main, accepts when main misses it, and records main's value.
A4 Gauntlet piece, written by Codex: Kind: gauntlet, Capture (for example tally --report output on a sample text written to .loop/capture/), Reference (a hand-written report file that is clearly better), Criteria (clarity, ordering, completeness). gate.py check and move ready. The ready check runs critics on main versus the reference: this costs 3 Sonnet sessions. PASS: main does not win, ready is accepted.

## Part B: one short Claude session, about 20 minutes
B1 Researcher: in one interactive Sonnet test session, run /ai-loop-kit:shape for one small piece that needs an outside fact (for example "tally --top respects the Unicode word boundary rules of a named standard"). Answer as the person, take the recommendations, approve. PASS: the researcher writes Research lines with URLs and read dates, the judge writer writes the judge, and the gate moves it to ready. Then close the session.

## Part C: one walk-away run, about 60 to 90 minutes, no interaction
C1 Sandbox proof: `gate.py doctor --walk-away` (one Sonnet probe). PASS: the probe shows a forbidden write, a read of ~/.ssh and an outside network call all fail. If the probe cannot prove it, STOP part C, record FAIL with the probe output, and do not run walk-away: that is the most important result of the whole rehearsal.
C2 Walk-away: `LOOP_CLAUDE=/tmp/loop-sonnet python3 <kit>/scripts/run.py --walk-away --attempts 2` over the three ready pieces (B1, A3, A4). Do not touch it until it ends. PASS: each piece reaches approval or goes back with a typed reason; .loop/summary.md and the run-log issue comment exist; the person is mentioned only for a blocker; nothing was merged; the run logs show every session ran with the sandbox settings; the goal pull request shows main's value and the new value and each hypothesis; the gauntlet pull request shows three blind verdicts with the order each critic saw.

## Not in this round (say so in the results)
Node (covered in v1), kill during review (an open GitHub issue), a second walk-away night.

## Rules
As in your brief. On a kit failure: ledger row, test, fix on kit/v1.1, rerun only that part, once. Time box: part A by 16:30, part B by 17:00, part C by 18:30. Write docs/v1.1/rehearsal-results.md with PASS, FAIL or NOT RUN per item and the number of Claude sessions used. Then both suites, push, CI, PR body section, stop.
