# Plan: AI Loop Kit in a new repository, AI Build Kit kept stable

Decisions 56 to 62 in the decision record. Every step marked (yes) changes something online and waits for the maintainer's yes at that step.

## Part A. The old repository, gwpicard/ai-build-kit

A1. Return main to the 0.19 line (one PR to main, never a force push).
- Branch from main. Revert, in one PR, every commit after the six fixes: the loop-first design note, slices 1 to 12, round 2, the integration merge and the later fix, keeping the six fixes (replay ungraded, changelog pointer, free-plan note, kit repository refused at founding, older records upkeep, replay records).
- Port the Codex GitHub access fix by hand onto that tree. Four files conflict today: the founded AGENTS.md template, plan-refresh.sh, plan-printout.sh and the root AGENTS.md.
- Check: the tree matches the fixes-only commit except for the Codex fix; validate-kit.sh and run-all.sh pass; the Codex rehearsal passes.
- The maintainer merges the PR. (yes)

A2. Release v0.19.3 through the normal process.
- The six fixes touch founding, so MAINTAINING.md requires the pre-release run as a person before the release. (the maintainer runs it, or decides to skip it with the reason recorded)
- Stamp, Release Drafter notes rewritten as a patch release, prepare, publish, verify, stable moves. (yes at publish)
- The old v0.20.0 draft is deleted. (yes)

A3. Close what moved or was replaced. (yes, from the approved backlog list)
- PR 346 closes with a pointer to the new repository's first commit.
- The overnight batch PR and its draft PRs close; their branches stay, because v1 slices read mechanisms from them.
- Issues the new model replaces close as not planned, each with its reason.
- Issues that fold into a v1 slice or wait for after 1.0 are transferred to the new repository (A3 runs after B1).
- Bugs that still apply to AI Build Kit stay open for the 0.19 line.

A4. Maintenance mode until v1.0: fixes only, as v0.19.x. At the v1.0 release the README points to AI Loop Kit; a later release offers founded projects the move; the repository is archived once that move has run for real.

## Part B. The new repository, gwpicard/ai-loop-kit

B1. Create the repository, private, with no template, README or licence added by GitHub. (yes)

B2. First commit: a clean snapshot.
- The tree of the old main as it stands before A1 (the loop-first redesign included), plus docs/design/agentic-loop.md and docs/design/agentic-loop-research.md from the design branch.
- In the same commit, the workflow gates that check the repository name accept gwpicard/ai-loop-kit, so the hosted checks run rather than skip. The kit's other names (plugin, marketplace, founding command, record files) stay as they are until slice 22.
- Authored by the maintainer, with no attribution lines. The validator and the rehearsals pass on it before the push.
- Push to main. (yes)

B3. Repository settings. (yes for each)
- Labels: today's label set, so the slices can be built by today's /implement.
- Delete branches on merge; main as the default branch. stable is created at the v1.0 release, not before.
- A private free repository has no branch protection, so main is held by the kit's guards until v1.0 makes it public.

B4. Issues. (yes)
- The epic "AI Loop Kit v1" and the 23 slice issues, linked as sub-issues and by blocked-by in build order.
- The transferred issues from A3 are folded into their slices or labelled as after 1.0.

B5. The build starts at slice 1.

## Order

B1, B2, B3, B4 can run today. A1 and A2 run in parallel with the v1 work. A3 runs once B1 exists, after the backlog list is approved. Nothing in Part A depends on the v1 slices.

## What changes in the slices

- Slice 22 is no longer a GitHub rename. It becomes "Moving from AI Build Kit to AI Loop Kit": the new plugin and marketplace names, the founding command and record file names, and the move for founded projects through the new kit's /maintain.
- Slices that read mechanisms from the overnight batch read them from the old repository's branch, which stays.
- The rename finding about workflow gates is handled once, in B2.
