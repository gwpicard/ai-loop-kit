# Prompt for a local Claude Code session

Run this from a clone of gwpicard/ai-build-kit, signed in with `gh`. Paste everything below the line.

---

You are carrying out an agreed plan to (A) return gwpicard/ai-build-kit to a fixes-only 0.19 line and release v0.19.3, and (B) start AI Loop Kit v1 in a new private repository, gwpicard/ai-loop-kit. Every decision is already made. Your job is to execute, check, and stop for my yes at each step that changes something online.

## Read first, in full
1. `git fetch origin && git checkout handoff/ai-loop-kit-v1`, then read in `handoff/`: `README.md`, `decision-record.md` (63 decisions; 56 to 63 cover this move), `move-plan.md`, `backlog-plan.md`, `epic.md`, `OPEN-DECISIONS.md`, and skim `slice-01.md` to `slice-23.md`.
2. `docs/design/agentic-loop.md` and `docs/design/agentic-loop-research.md` (on this branch and on `design/agentic-loop`).
3. `AGENTS.md` and `docs/MAINTAINING.md` (house rules, release process, the pre-release run, attribution rules, blocked commands in `.agents/guard/blocked-commands.md`).
Then run `git config core.hooksPath .githooks`.

## Rules for the whole session
- Ask me before every step that changes something online (push to main, create repo, labels, issues, transfers, closes, comments, release). Before each, say in two lines what will change and whether it can be undone. Batch related operations into one yes where the plan groups them.
- Never force push, never rewrite history, never use the commands in `.agents/guard/blocked-commands.md`. If a command is refused, stop and tell me.
- No attribution lines in commits, PRs or issues: no co-author trailer naming a model, no session link, no "Generated with" footer.
- Tracked files in either repository contain no issue or PR numbers (the validator fails on them). Issue bodies may contain them.
- Use subagents for independent work: one per repository part, one per group of slice issues, one for the backlog operations. Give each a self-contained brief and have it report back; you keep the coordination and every online write.
- Report in plain British English, short.

## Part A: AI Build Kit back to the 0.19 line (gwpicard/ai-build-kit)

A1. Build the revert PR.
- Branch `release/back-to-0.19` from `origin/main`.
- The last commit before the redesign is `80bb670` (v0.19.2 plus the six fixes). Restore its tree in one commit without rewriting history: `git read-tree --reset -u 80bb670`, check `git status`, commit with a message that says main returns to the 0.19 line and the loop-first redesign moves to AI Loop Kit.
- Port the Codex GitHub access fix (commit `e76c655`) by hand: `git cherry-pick -n e76c655` conflicts in four files (the founded AGENTS.md template, `plan-refresh.sh`, `plan-printout.sh`, root `AGENTS.md`). Resolve each so only the Codex fix's own lines are added onto the 0.19 versions, keep the AGENTS.md template within its ceiling, commit.
- Check: `git diff 80bb670 --stat` shows only the Codex fix's files; `.agents/tools/build-adapters.sh` leaves nothing to commit; `.agents/tools/validate-kit.sh` passes; `.agents/tests/run-all.sh` passes, including `codex-github-auth.sh`.
- Open the PR to `main` (never `stable`) with the `bug` and `release-patch` labels and an `area:` label. Stop for my review and merge.

A2. Release v0.19.3 after I merge A1.
- The fixes touch founding, so `docs/MAINTAINING.md` requires "Trying unreleased work as a person would". Give me the steps; I run it or tell you to skip it, and the reason is recorded.
- Then follow "When a release is cut" in `docs/MAINTAINING.md`: stamp PR, Release Drafter notes rewritten as a patch release listing the fixes, prepare, publish (my yes), verify, `stable` moves. Delete the old v0.20.0 draft (my yes).

## Part B: AI Loop Kit (gwpicard/ai-loop-kit), can run in parallel with Part A

B1. Create the repository: `gh repo create gwpicard/ai-loop-kit --private` with no README, licence or template (my yes).

B2. First commit, a clean snapshot.
- In a new folder outside this clone: `git init`, then copy the tree of `origin/main` as it is NOW (commit `e76c655`, with the loop-first redesign), for example with `git archive e76c655 | tar -x -C <folder>`.
- Add `docs/design/agentic-loop.md` and `docs/design/agentic-loop-research.md` from `origin/design/agentic-loop`. Do not add the `handoff/` folder.
- Make every workflow gate that checks the repository name (grep `.github/workflows` for `gwpicard/ai-build-kit`) accept `gwpicard/ai-loop-kit`, so the hosted checks run rather than skip. Change no other name; slice 22 does that.
- Commit as me, with no attribution lines. Run `git config core.hooksPath .githooks`, the validator and `run-all.sh` in that folder; fix only what the name change breaks.
- Add the remote and push `main` (my yes).

B3. Settings (my yes): `gh label clone gwpicard/ai-build-kit --repo gwpicard/ai-loop-kit`, plus an `after-1.0` label; delete branches on merge; `main` as default branch. No `stable` until the v1.0 release.

B4. Issues (my yes): create the epic from `handoff/epic.md` and the 23 slices from `handoff/slice-NN.md`, in build order, with today's labels as each slice states. Link each slice as a sub-issue of the epic and add its blocked-by links from the epic's table. Use one subagent per group of about six slices to prepare the bodies; you create them. Then read every issue back and check the links. The slices' open defaults are listed in `handoff/OPEN-DECISIONS.md`; do not decide them, list them in the epic as open decisions.

## Part C: the old backlog (after B3), following `handoff/backlog-plan.md`
- First a trial transfer of one issue named in the plan: `gh issue transfer <number> gwpicard/ai-loop-kit` (my yes), and show me what survived (labels, comments, sub-issue links).
- Then, on my yes, the remaining transfers, the comments, the closes with their reasons, and the comments on issues kept for the 0.19 line, in the order the plan gives.
- Close PR 346 with a pointer to the new repository's first commit, and close the overnight batch PR and its drafts with the reuse list from the plan. Delete no branch.

## When you finish each part
Say what was done, what was checked, and what is still open, in a few lines. End with the next step that needs my yes.
