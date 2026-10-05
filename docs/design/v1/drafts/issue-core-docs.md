Labels: documentation, area:docs. Release label for the pull request: release-minor. Parent: the "AI Loop Kit v1" epic. Blocked by: slice 10 (Crews and computer resources). Settled decision 54 in the build's notes makes this the last piece of the v1 core build. Slices 11 to 23 move to the backlog.

## So that
Someone who installs the kit from `v1-integration` or `main` after the core build reads an honest account. The documents say what v1 does today (slices 1 to 10) and name what is planned without claiming it works.

## Done when

### Works
- WORKFLOW.md and the README each carry one short section, "What v1 has today", listing the parts that slices 1 to 10 built in plain words: the gate and state labels, contract v2 and the ready gate, shaping sub-states, the area map, the fixed bar, the build and fix loops, the automatic review, the run controller, and crews and computer resources. The same section names the planned parts in one list headed "Planned, not built yet": the goal and gauntlet loop modules, the merge policy, `/deploy`, the safety boundary for runs, boards and notifications, `/maintain` absorbing `/sync`, the compact masterplan, Codex parity, the replay harness rewrite and the name AI Loop Kit. Check: a new rule-shape rehearsal `.agents/tests/core-scope.sh` holds both lists in both files, each item proved load-bearing.
- No sentence in WORKFLOW.md, the README or a skill tells a person to use a planned part as if it worked today. That means no instruction to type `/deploy`, and no claim that runs merge by themselves, that boards exist, or that Codex is held by the same gates. A mention inside the "Planned, not built yet" list is fine. Check: `.agents/tests/core-scope.sh`, which fails on a copy of WORKFLOW.md with "type `/deploy`" outside that list.
- Commands that slices 1 to 10 did not replace (`/ship`, `/sync`, `/maintain`, `/what-now`, `/queue` where it still exists) are described as they work today, not as v1 will change them. Check: `.agents/tests/core-scope.sh` reads WORKFLOW.md's command table against the skill folders in `.agents/skills/`.
- Root `AGENTS.md`'s maintainer-checks list has an entry for `core-scope.sh`. Check: `validate-kit.sh`.

### When it is not the normal case
- A document already describes a planned part as working, written by an earlier slice. Reword that sentence to say it is planned, and change nothing else. Check: `.agents/tests/core-scope.sh`.

## Not in this piece
- The full documentation sweep (slice 21), the rename (slice 22) and the release (slice 23).

## Size
One part, one sitting.

## Under the hood
Write `core-scope.sh` first with every rule above and see it fail. Then edit WORKFLOW.md, the README and any skill sentence the check finds. Load the humanizer before writing prose, and follow MAINTAINING.md's house rules. Use no issue numbers in tracked files.
