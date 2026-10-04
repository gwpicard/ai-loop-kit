# Open decisions for AI Loop Kit v1

Every decision the slice drafts leave to the maintainer, gathered from slices 1 to 23 and the epic, with duplicates merged. Each gives the slice it affects, what the drafts do if nobody decides, and a one-line recommendation. Numbers settled when built are listed because the design note leaves them open; each draft's default is a starting value that slice 20's real runs measure.

## How the work is done

1. **Which kit builds the slices.** Slices: all, and the epic. Default: none chosen; decision 55 only says the slices use today's labels so today's `/implement queue` can build them. Recommendation: build with AI Build Kit 0.19.3 installed at user level through the Claude plugin, and treat the adapters generated inside gwpicard/ai-loop-kit as the work under test, because a session in the kit's own repository otherwise picks up half-built skills.

2. **The old repository's migration tooling in the new repository.** Slice 22. Default: `docs/MIGRATION.md`, `docs/MIGRATION-READINESS.md`, `.agents/migration/`, `preflight-cutover.sh` and `rehearse-merged-tree.sh` stay as they are. Recommendation: remove them in slice 21 with a line in the changelog, since they served the old repository's history rewrite and the old repository keeps them.

3. **The backlog plan's slice text changes.** Slices 5, 14, 16, 19 and 20. Default: not applied; `backlog-plan.md` lists Done when lines for the bugs kept for the 0.19 line that also exist in the snapshot. Recommendation: add those lines, each naming the old issue by title, once the backlog list is approved.

4. **When the kit's own issues move to the v1 labels.** Slice 2 and slice 23. Default: gwpicard/ai-loop-kit keeps today's labels until the release (decision 55), and no slice moves them after. Recommendation: run `gate.py labels` and relabel the open issues as the first piece after v1.0, on a yes.

## The gate and the files it reaches

5. **How a copied `gate.py` reaches scripts that stay inside the skills.** Slices 2, 3, 6, 15 and 16. Default: the drafts keep `ready-lint.py`, `bar-guard.sh`, `dependency-check.py`, `secret-scan.sh`, `board.py` and `notify.sh` inside their skills, and say nothing on how the copied gate or printout finds them on each installation route. Recommendation: have the placement step copy every script the gate or the printout calls into `.agents/tools/` beside `gate.py`, each held by `check-floor-rehearsal.sh`.

6. **When the per-piece records are cleared.** Slice 6, with slice 17 as the natural owner. Default: `.agents/pieces/<number>/` (evidence, attempt notes, review rulings) is never cleared. Recommendation: `/maintain` names the folders of pieces closed more than a month and gives the person the command, as it does for other folders.

7. **What "old helper refresh" removes.** Slice 17. Default: the step that adds the printout helper to a project founded before it shipped goes; refreshing the copied scripts after an update stays. Recommendation: keep that reading, since an AI Loop Kit project needs the current `gate.py` after every update.

8. **The one-line refusal for a project founded with AI Build Kit.** Slices 17 and 22. Default: `/maintain` and founding find `.ai-build-kit-maintenance` with no `.ai-loop-kit-maintenance`, change nothing and say the project stays on AI Build Kit. Recommendation: keep it, because it stops a founding over an old project and is not a bridge.

## Shaping and the contract

9. **Contract length limits.** Slice 3. Default: 80 lines for a chore, 120 for a bug, 250 for a feature. Recommendation: keep and let slice 20 measure.

10. **Time limit for each check run at the ready gate.** Slice 3. Default: ten minutes. Recommendation: keep.

11. **How far back the co-change query looks.** Slice 4. Default: the last 200 commits. Recommendation: keep.

## Loops and runs

12. **Attempts and piece budget.** Slice 7. Default: three attempts and 120 minutes per piece. Recommendation: keep.

13. **Where a build loop goes at its limit.** Slice 7. Default: kickback to `shaping:research`, or to `spec` when an attempt note shows a check that cannot be met as written. Recommendation: keep.

14. **Review rounds and what happens at the cap.** Slice 8. Default: two rounds; a piece still holding gaps goes to the person as `review:person`, not back to shaping. Recommendation: keep.

15. **Run limits.** Slice 9. Default: `at_once` 1, a run budget of 480 minutes, three CI rounds. Recommendation: keep, with slice 10's computer suggestion replacing the fixed `at_once`.

16. **Computer resource numbers.** Slice 10. Default: 2.5 GiB per builder, a 4 GiB reserve, pressure when available memory falls under the reserve or swap grows by 512 MiB, critical under half the reserve. Recommendation: keep until slice 20 records measured values.

17. **A goal with no gain.** Slice 11. Default: a goal whose best result is no better than the start is kicked back to `clarify` and opens no pull request. Recommendation: keep, and add the sentence to the design note as the slice says.

18. **The gauntlet's panel and outside critics.** Slice 12. Default: the work wins only when every critic prefers it in both orders, and a critic from another model family is used only when shaping recorded the person's agreement. Recommendation: keep both.

## Merging, deployment and safety

19. **A recipe whose rollback the kit cannot run.** Slice 13. Default: such a recipe never earns automatic merge (the Coolify recipe today). Recommendation: keep.

20. **The founding offer of a ruleset on `main`.** Slice 13. Default: where GitHub can protect `main`, founding offers once to create a ruleset requiring the project check and a pull request, only on a yes naming it. Recommendation: keep.

21. **A database plan with branching for the real runs.** Slices 14 and 20. Default: if the maintainer's database plan has no branching, previews share one preview database, no `Previews keep their own data:` line is written, and automatic merge stays off on both recipes at 1.0. Recommendation: decide before slice 14 Part d whether to use a plan with branching for the real runs, since without it no project can earn automatic merge at 1.0.

22. **A computer with no sandbox.** Slice 15. Default: the run still starts, says so every run, and automatic merge stays off. Recommendation: keep.

23. **Age of a new dependency.** Slice 15. Default: a dependency whose first release is under 30 days old is refused. Recommendation: keep.

## Boards and maintenance

24. **What the board's run buttons copy.** Slice 16. Default: the gate's own commands, such as `python3 .agents/tools/gate.py run pause <run name>`. Recommendation: copy `/implement` with the word pause, continue or stop and the run name instead, so the person pastes a command they already know, with `/implement` calling the gate.

25. **Counts for the health visit.** Slice 17. Default: 5 clean runs before the offer of automatic merge, drift reads every 5 merged runs, 7 days for a revert or bug to count against a run, three months before a lesson is reviewed. Recommendation: keep.

## Release

26. **When the repository becomes public.** Slice 23. Default: just before the v1.0.0 draft is published, on the maintainer's yes (decision 59). Recommendation: keep, and run the route checks only after it, since an installer cannot read a private repository.

Count: 26 open decisions.
