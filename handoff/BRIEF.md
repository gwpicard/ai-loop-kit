# Brief for drafting v1 slice issues

Read first, in full:
- /home/user/ai-build-kit/docs/design/agentic-loop.md (the agreed v1 design; branch design/agentic-loop, already checked out)
- /home/user/ai-build-kit/docs/design/agentic-loop-research.md
- /tmp/claude-0/-home-user-ai-build-kit/30be0cd6-ee74-59b5-bb9f-17d0f8021556/scratchpad/v1-decision-record.md (55 numbered decisions)
- /tmp/claude-0/-home-user-ai-build-kit/30be0cd6-ee74-59b5-bb9f-17d0f8021556/scratchpad/v1-slices/TEMPLATE.md (the shape every slice must follow)
- /home/user/ai-build-kit/AGENTS.md and docs/MAINTAINING.md (house rules; the rule-shape check family; what a canonical skill change requires)

Then read the current kit code that each of your slices touches (skills in .agents/skills/, tests in .agents/tests/, tools in .agents/tools/, templates in .agents/skills/setup-ai-build-kit/templates/), so each slice names exactly what changes, what is reused and which existing rehearsals it will change. Mechanisms built on the unmerged branch origin/gwpicard/v1-overnight-integration-20261001 may be reused (read with `git show origin/gwpicard/v1-overnight-integration-20261001:<path>`): implement/scripts/recovery.py, section-builder/references/task-handoff.md and task-context-capabilities.md, the local-browser walk-through rule, the force-push deny rules, the clarify question box, same-turn continuation.

The 23 slices, in build order (each blocked by the slices it needs):
1. Principle, audience and the loop kit in PHILOSOPHY.md, the README and WORKFLOW.md
2. Label model and gate script (states, sub-labels, transitions, hook and deny rules, labels created at founding)
3. Contract v2 and the ready-gate lint (reach fields, crew, the bar for each loop module, checks fail on their assertion, refused phrases, brief rules, length limit per type)
4. Shaping sub-states in /shape (triage in raw via change-triage, research, clarify, prototype, pre-mortem, spec, check; bug fast path; kickback intake; removing /fix)
5. Area map for the whole project, kept by the project check
6. Frozen-bar enforcement (contract hash, wider diff guard, evidence record, Stop hook)
7. Build and fix loop modules (builder statuses incl. environment failed, script-built attempt notes, limits, self-repair within spec, fix discipline)
8. Automatic reviewer (contract plus diff only, two verdicts, gap sorting, capped rounds, logged rulings, calibration data)
9. Run controller (run record, run of one, waves from Depends on and Boundary, integration branch one piece at a time, bisect, kickback, run statuses, green main before a run)
10. Crews and computer resources
11. Goal loop module
12. Gauntlet loop module
13. Merge policy (earned automatic merge, GitHub protection check, preview smoke test, health check and rollback, irreversible data change with backup)
14. /deploy replacing /ship (pipeline setup, previews with their own data, app per worktree, releases for not-hosted projects, recipes updated and real runs)
15. Safety boundary for runs (sandbox and allowlist, scoped push token held by the gate script, untrusted text as data, dependency check, secret scan, brief states allowed actions)
16. Boards and notifications (status JSON, local HTML, live Claude artifact, four notifications, /what-now)
17. /maintain absorbs /sync (lessons, kit metrics, drift reads after N runs, offer of automatic merge, guide removal tests, reviewer calibration, moving founded projects to v1 labels and records)
18. Compact masterplan and behaviour deltas
19. Codex parity (same scripts as hooks and rules)
20. Replay harness rewrite and real runs (one per loop module, one /deploy per recipe)
21. Documentation sweep (one story across WORKFLOW.md, README.md, COMPATIBILITY.md, MAINTAINING.md, root AGENTS.md maintainer checks, SOURCES.md credits, foundation templates, CONTRIBUTING.md, issue templates; old loop-first design notes marked as replaced)
22. Rename to AI Loop Kit
23. Release v1.0

Rules for your drafts:
- Follow TEMPLATE.md exactly, one file per slice: /tmp/claude-0/-home-user-ai-build-kit/30be0cd6-ee74-59b5-bb9f-17d0f8021556/scratchpad/v1-slices/slice-<NN>.md (two digits).
- Every Done when line is checkable, false on today's main and true after the slice; name the check (an existing or new rehearsal file in .agents/tests/, a script run, a replay scenario, or a guided check).
- Be specific to this repository: name skills, references, scripts and rehearsals. No hand-waving, no "consider", "TBD", "if needed", "for now", "may" in a list.
- If a slice is too big for one or two sittings, split it into parts inside the same file (Part a, Part b), each with its own Done when.
- British spelling, no em dashes, no issue or PR numbers anywhere in the text (refer to other slices by "slice N: title" and to old issues by their title). Plain words.
- Do not change any repository file. Do not create GitHub issues.
- Finish with a short report: the files written, any slice where you found a conflict with the design note or a decision, and any decision the maintainer still has to make.

- Every slice's Done when includes the documents its own change touches (the house rule that a change is told in WORKFLOW.md, the skill and the words on screen), named one by one with the check that holds each. Slice 21 then makes the whole set tell one story.
