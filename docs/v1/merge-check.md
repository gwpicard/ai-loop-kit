# Merge check before v1 merges (read at ed83858)

Do these in the wrap-up (finish plan M7), each small. Most are docs.

1. Bug: kit/skills/shape/SKILL.md tells the agent `gate.py move <n> shaping --reason "<why>"`, but the gate needs `--type` for that move. Add `--type spec-unclear` (or `bar-wrong`) and check every other move command in the skills, README and briefs against gate.py's required flags. Add a test that runs every `gate.py ...` command line found in kit/skills/*/SKILL.md through the argument parser.
2. Version: kit/.claude-plugin/plugin.json to `1.0.0`; CHANGELOG.md `## 1.0.0` with today's date, what v1 holds, and an upgrade note (0.10 specs need `## Intent` with a non-empty `Out of scope:`; `## Done when` still reads as Contract); README status line no longer "in progress".
3. CRAP docs: docs/V1.md, docs/DESIGN.md and kit/briefs/builder.md say a changed function must not score worse than main. The code only checks the limit of 30. Make the text match the code.
4. Doc drift in docs/V1.md: list all eight typed reasons (add `stopped` and `judge-gap`); the guard refuses unreadable forms in build sessions (it does not "ask"); the size budget line should state the real size and the target; drop is allowed from building too. Update the gate.py docstring with spec, report and stop. README and AGENTS.md say the tests take "seconds": say "about two to four minutes".
5. kit/skills/setup/SKILL.md: add `Standards:`, `Idle limit:` and `Waiting limit:` to the AGENTS.md template.
6. `run.py --verdict-kind judge-writer --verdict-file <missing>` ends in a traceback; give the `next:` line instead.
7. Confirm the double import of run.py is gone after procs.py (the check read an older commit): a test that runs `python3 run.py` as a subprocess already exists; make sure it covers the review path.
8. Plan files: delete docs/V1-PLAN.md and docs/V1-HARDENING.md and docs/v1/amendment-*.md in a last commit (they say "delete when v1 merges" and are instructions to a build agent; the findings and results files stay). Fix the references to them in docs/DESIGN.md, docs/LEDGER.md and README "Where things live" to point at docs/v1/ and git history. Add a row to tests/field/RESULTS.md for each round (1, 2, 3) with the result.
