# Open decisions settled by the maintainer, 4 October 2026

How to cite: "settled decision N" means item N in this file. A bare "decision N" means item N in the epic's decision record (the 63 design decisions of 2 October 2026). The two lists share numbers.

1. Which kit builds the slices: a coordinator session following this repository's AGENTS.md and MAINTAINING.md, with the kit's run discipline (claim, worktree per slice, checks first, fresh reviewer, PR to main, state file). No plugin install, because the plugin's /implement expects a founded project and this repository must never be founded.
   Merges: pre-approved. The coordinator merges a slice when CI is green, run-all.sh and validate-kit.sh pass, and a fresh reviewer finds nothing worth stopping for. Anything else waits for the maintainer.
   Protection: local deny rules only (.claude/settings.local.json) while the repository is private.
2. Migration tooling: removed in slice 21, with the AGENTS.md entries that describe it.
3. Backlog plan lines: dropped. backlog-plan.md is not on disk or in either repository.
4. Kit's own labels: move after v1.0 (default).
5. Gate files: founding copies every script the gate or the printout calls into .agents/tools/ beside gate.py, each held by check-floor-rehearsal.sh.
6. Piece folders: /maintain names the .agents/pieces/<number>/ folders of pieces closed over a month ago and gives the delete command (slice 17).
7. Old helper refresh: only the step for projects founded before the helper goes; refreshing copied scripts after an update stays.
8. CHANGED from the draft and from decision 63: when AI Loop Kit finds AI Build Kit in a project, founding lists Build Kit's own machinery (skills, generated adapters, plugin entry, .ai-build-kit-* record files, its hook and plan helper), removes it on one yes, then founds AI Loop Kit fresh. The project's masterplan, CHANGELOG, code and issues stay untouched. Nothing is removed without the yes. Reaches slices 17, 22, 23 and the epic's decision 63.
9. Contract length limits: 80 chore / 120 bug / 250 feature (default).
10. Ready-gate check time limit: 10 minutes (default).
11. Co-change look-back: last 200 commits (default).
12. Attempts and budget: 3 attempts, 120 minutes per piece (default).
13. At the limit: kickback to shaping:research, or to spec when a check cannot be met as written (default).
14. Review: 2 rounds, then review:person (default).
15. Run limits: at_once 1, 480-minute run budget, 3 CI rounds (default).
16. Computer sizing: 2.5 GiB per builder, 4 GiB reserve, pressure and critical thresholds as drafted (default).
17. Goal with no gain: kickback to shaping:clarify, no pull request; the design note gains the sentence (default).
18. Gauntlet: every critic prefers the work in both orders; another model family only with the person's recorded agreement (default).
19. A recipe whose rollback the kit cannot run never earns automatic merge (default).
20. Founding offers a ruleset on main once, created only on a yes naming it (default).
21. Real runs use the Supabase free plan with no branching: previews share one preview database, no "Previews keep their own data:" line, automatic merge stays off on both recipes at 1.0.
22. No sandbox: the run starts, says so every run, automatic merge stays off (default).
23. A dependency first released under 30 days ago is refused (default).
24. Board run buttons copy "/implement pause|continue|stop <run name>"; /implement calls the gate.
25. Health counts: 5 clean runs, drift every 5 runs, 7 days, 3 months (default).
26. The repository goes public at slice 23, on the maintainer's yes, just before the v1.0.0 draft is published (default).

# Settled on 4 October 2026, from the first readiness pass

27. Starting a crew member (slices 7, 9, 10): on Claude Code a crew member is a subagent. run.py decides each crew and writes a start request into the run record; the coordinating session starts each member with its subagent tool and writes back its id. run.py never starts a model session itself.
28. at_once (slice 10): founding writes "at_once": "auto", the computer's suggestion, up to six. A number is the person's own count. Decision 15's 1 applies only when the settings file is missing and no memory reading exists.
29. Outside critic (slice 12): Codex only at 1.0, checked with `codex --version` and `codex login status`, and only with the person's recorded agreement. The lint refuses any other command.
30. Throwaway environment (slices 14, 15): slice 14's local app step writes a git-ignored .env.local with throwaway values into each worktree; slice 15 relies on it by name. Builders never see a real key.
31. Saving an acceptance (slice 4): /shape saves the Accepted: line, and every masterplan sentence it makes untrue, on a records pull request of its own, merged on a yes naming it. The piece leaves shaping:clarify only once that pull request has merged.
32. Asking to review (slice 16): `/shape <number> review` records the request as a hidden marker on the issue; the gate routes the piece to review:person. The board marks a ready piece "would benefit from your review" when it reaches code no existing test covers.
33. Files AI Build Kit founded (slices 18, 22): on the same yes that removes AI Build Kit's machinery, AGENTS.md, CLAUDE.md, GEMINI.md, the copilot instructions and the piece form are removed and written again by AI Loop Kit. The old masterplan is read as input to the founding interview, then replaced in the founding save (it stays in git history). checks.yml and .claude/settings.json are kept.
34. Replay passes (slices 20, 23): the coordinator may start the v1 baseline pass and the guide-removal replays itself, on the maintainer's model account, when their slice reaches that point.
35. Label colours (slice 2): the checker's proposed colours are accepted.
36. Guided checks (all slices): a guided check holds a merge only when a later slice relies on what it proves. Otherwise the coordinator merges on green, adds the check to the "Waiting on you" queue on the dashboard, and keeps building. Every queued check is done by the maintainer before slice 20's real runs. Real accounts, money, repository settings, going public and the release still stop the run.

# Settled on 4 October 2026, from the second readiness pass

37. A project with no code yet (slices 3, 4): spec asks the first-upload question before cutting a branch, and writes the acceptance checks as test files for the test runner check-floor.md names for the language. The build that adds that runner records the test command in AGENTS.md. The lint accepts this case.
38. Network allowlist (slice 15): founding offers once to set `sandbox.network.strictAllowlist` in the person's `~/.claude/settings.json`, says it applies to every project on the computer and how to undo it, and writes it only on a yes. Until it is set, the Sandbox line says the fence is not held and automatic merge stays off.
39. Env files (slice 15): founded settings refuse reads of every git-ignored env file except `.agents/app/.env.local`, for every session in the project. The person starts the app in their own terminal or through /deploy's host tools.
40. Tools outside the sandbox (slice 15): `gh` and each recipe's command-line tools run outside the sandbox. Every write a builder could make in the person's name (comment, review, new issue, API write) goes behind an ask rule. Label writes stay denied; merge stays behind its ask rule.
41. Guides and sensors (slice 17): at 1.0 the guides are the agent-brief lint rules, the automatic review and the crew checks. Everything else is a sensor and is never switched off.
42. Clean runs (slice 17): automatic merge is offered when the 5 most recent counted runs are all clean; a run that is not clean starts the count again.
43. AI Build Kit (slices 22, 23 and the epic): AI Build Kit is a separate product the maintainer keeps maintaining under its own philosophy. It is not retired, archived or given an end date. AI Loop Kit is the product built around looping. No document or release note promises a support window for AI Build Kit; they say the two are separate products. Decision 8 still holds: a project uses one kit, so founding AI Loop Kit removes AI Build Kit's own files from that project on a yes.

# Settled on 4 October 2026, from the final readiness pass

44. Test runner for TypeScript and JavaScript (slices 3, 4): Vitest. check-floor.md names Vitest for both, and spec writes acceptance checks for it when a project records no test command yet.
45. Kept settings (slices 6, 22): when founding keeps an existing `.claude/settings.json` (settled decision 33), it still adds the kit's deny rules to it, by key, leaving the person's own entries alone. Slice 22 owns this.
46. Kept settings, hooks (slices 2, 7, 22): founding also adds the kit's hooks (slice 2's state guard, slice 7's Stop and SubagentStop hooks) to a kept `.claude/settings.json`, by key, leaving the person's own hooks alone. Slice 22 owns this, beside settled decision 45.
47. Sandbox exceptions (slice 15): `gate.py evidence` runs only commands named in the contract or in AGENTS.md's stack section; `worktree.sh app start` runs only the recipe's own `## Local app` start command; `codex` is excluded only in the outside critic's exact call, never as `codex *`. WORKFLOW.md and the design note say plainly that code under test still runs outside the fence, and sandboxing it is work after 1.0.
48. Skip ahead past a person's step (coordinator, all slices): when a part needs the maintainer's real accounts (for example slice 14 Part d), the coordinator merges every part an agent can do, marks that part "waiting on you" on the dashboard, and carries on with later slices whose fresh readiness check confirms they need only what is on main. A slice that truly needs the waiting part waits. Slice 20's real runs and slice 23's release still stop the run.

# Settled on 5 October 2026, by the maintainer

49. A new open question (slices 2, 4): the gate tells a new question from an old one with the answer marker. On entry to `shaping:spec` it fingerprints the `## Open question` section. It moves the piece from spec back to `shaping:research`, `shaping:clarify` or `shaping:prototype` only when that section holds one question and its fingerprint differs from the one taken on entry. A question already asked and answered, still written on the piece, is refused, so a piece cannot go round on the same question.

50. Questions only the maintainer can answer (coordinator, all slices, from 5 October 2026): when a readiness re-check finds a BLOCKING gap that needs the maintainer's answer, the coordinator does not stop. It takes the checker's labelled best guess, writes it into the slice's issue under `## Decided` as "Decided overnight on the checker's guess, for the maintainer to review: <answer>", comments on the issue, adds a queued check "review overnight decision: <one line>" to the slice's `ask` on the dashboard, and carries on. Where the checker gave no guess, the coordinator picks the option that changes least and is easiest to undo, and says so. Real accounts, money, repository settings, going public, slice 20's real runs and slice 23's release still stop the run, as do a review finding after two rounds, three failed attempts and a refused command.

# Settled on 5 October 2026, by the maintainer, after the night's stop

51. Pre-approval unblocks everything else (coordinator, all slices; widens settled decision 50). The maintainer pre-approves the run. So the coordinator does not stop to ask about anything except the stops listed below, wherever the question comes from: a readiness check, a builder (a Done when line wrong, a check that cannot pass as written) or a reviewer (the slice's text at fault rather than the code). It takes one of two routes and documents it:
   - Decide: take the answer that keeps every settled decision and is easiest to undo or change (a checker's or builder's labelled guess first). Save the old issue body in `bodies/`, edit the issue, write the answer under `## Decided` as "Decided during the run, for the maintainer to review: <answer>", comment on the issue, add "Queued: review run decision: <one line>" to the slice's `ask`, and log it in `state.json` and the dashboard's events.
   - Park: where no answer is safe to take, set that piece aside with the reason written on its issue and the dashboard, and carry on with any work that does not depend on it.
   Still stopping the whole run: a fatal error the run cannot recover from, anything touching money, real accounts or credentials, a repository or account setting, data that cannot be restored, going public or a release (slice 20's real runs, slice 23), three failed attempts on one part, a refused command, and any answer that would need a settled decision changed. A code defect a review still finds after two rounds parks that part. Why: on the night of 4 to 5 October the run stood still from about 03:30 to 07:40 on a builder's request to amend slice 4 part c's Done when line, because decision 50 named readiness questions only.

52. The fast flow: build parts back to back, prove each slice downstream (coordinator, from slice 6 part b onwards, 5 October 2026). The maintainer is hardening the skills before the final release and accepts fixing things downstream. So:
   - A branch `v1-integration`, cut once from `origin/main`, is where parts land. Every part's worktree is cut from `origin/v1-integration`.
   - A part lands when its builder's quick checks pass. The coordinator squashes it into one commit on `v1-integration` ("<human line> (slice N part x)", no closing word), pushes, records the commit in `state.json` and the step log, and starts the next part at once. A part gets no pull request, no per-part review and no wait for GitHub's checks.
   - When a slice's last part has landed, the coordinator cuts `slice-<NN>-to-main` from that commit and opens one pull request to `main`, with the release label, the type label and `Closes #<issue>`. CI runs on it and one fresh review reads the whole slice diff, while the next slice is already building.
   - That pull request merges with `gh pr merge --merge` (never squash, so `main` keeps `v1-integration`'s history and later slice pull requests do not conflict) when the merge conditions of the coordinator's step 6 hold. A CI failure or review finding becomes a fix part on `v1-integration`, built like any part and logged as a fix for that slice; the slice's branch is moved to the new commit and the pull request re-checked. Settled decisions 50 and 51 apply to everything here.
   - The builder adds a fresh `ruff check` and `mypy` on every Python file it changed, the cheapest of the checks that most often failed in CI.
   - The maintainer may install and try the skills from `v1-integration` at any time. It may be broken between a part landing and its slice's checks finishing.
   Why: a part took about 60 minutes, of which about half was review, CI and second rounds for small mechanical errors. Building back to back cuts a part to about 30 minutes.

53. Local checks now, GitHub at the end (coordinator and chat assistant, from 5 October 2026, about 13:00). The repository is private and GitHub Actions minutes are limited. The maintainer switched off the "source checks" and "maintainer branch check" workflows on GitHub (the chat assistant ran `gh workflow disable` on their yes). "release label" and "pull request base" stay on; they take seconds.
   - For each slice's pull request to `main`, the coordinator runs `.agents/tools/build-adapters.sh --check`, `.agents/tools/validate-kit.sh` and `.agents/tests/run-all.sh` on this computer, in a worktree of `slice-<NN>-to-main`, in the background while the next slice builds. It saves the output to `.agents/tmp/v1-factory/reports/slice-<NN>-local-checks.log` and names the result and the log in the pull request. A failure becomes a fix part, as in decision 52. Run one local suite at a time, never two at once, to spare memory.
   - Merge condition 1 becomes: that local run is green on the pull request's latest commit, and GitHub's "release label" and "pull request base" checks pass.
   - The chat assistant switches both workflows back on (`gh workflow enable`) once slice 21 has merged, with the maintainer told. From slice 22 the merge conditions are GitHub's again. If the coordinator reaches slice 22 and either workflow is still off, that is a setting and the run stops for the maintainer.
   Why: about 230 minutes of Actions time were used on 4 and 5 October, about 96 of them by the branch check repeating the validator on every push.

54. Build the core now, the rest later (coordinator, from 5 October 2026, about 13:40). The maintainer wants to use and harden the skills sooner than 16 to 20 hours. The run builds slices 6 to 10 (frozen bar, build and fix loops, automatic reviewer, run controller, crews and computer resources), then one short docs piece, the "Core docs pass" issue in gwpicard/ai-loop-kit, built and merged like a one-part slice. Then it stops with run status `done`, logs it, sends a notification, and the dashboard says the core is built.
   - Slices 11 to 23 are the backlog. Each issue has a comment saying so; nothing in them is changed or dropped. The coordinator does not claim, check or build them. The maintainer picks them up later, one at a time, as fixes and features after using the core.
   - Settled decision 53's switch back to GitHub's checks "once slice 21 has merged" no longer has a trigger. Both workflows stay off until the maintainer decides; the chat assistant's hourly job for it is cancelled.
