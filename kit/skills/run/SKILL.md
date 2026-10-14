---
name: run
description: Builds the ready pieces. Each attempt is a fresh Claude session; the gate runs the judge; a pass opens a pull request for the person. Use when pieces are ready and the person wants them built.
---
# Run

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

## Now
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" status 2>&1 | head -20`

## Steps
1. Say which pieces are ready, and that each gets up to three attempts.
   Done when: the person has seen the list. If nothing is ready, suggest `/ai-loop-kit:shape` and stop.
   Before each piece, the run checks how many pull requests wait in approval. At `Waiting limit:` (default 3), it starts no new piece and prints one `next:` step.
   Builder and reviewer attempts stop after ten minutes without output by default; `Idle limit:` in the loop section changes the minutes. An idle attempt returns as `builder-failed`. A dirty build folder returns as `environment` with a `next:` step; the run never resets or cleans it. A stop request returns the piece with type `stopped` and keeps the last real failure reason when one exists.
2. Start the run in the background: `python3 "<KIT>/scripts/run.py"` (or with piece numbers to build only those). Write the KIT path out in full.
   Done when: the run has started.
3. While it runs, report each line it prints: claims, attempts, passes, failures. The attempt logs are in `.loop/logs/`.
   Done when: the run prints "Run finished."
4. Report the result: each pull request link for the person to read and merge, and each piece sent back to shaping with its reason.
   Done when: the person has every link and reason.
5. After the person merges, run `python3 "<KIT>/scripts/gate.py" sync` to move merged pieces to done.
6. If the person rejects a pull request, move the piece back in their words: `python3 "<KIT>/scripts/gate.py" move <n> shaping --type person-rejected --reason "<their words>"`. Leave the pull request open; the next build pushes to the same branch and updates it. If the spec or the judge must change, use `/ai-loop-kit:shape`. Then the piece goes through ready again, and the next build gets the reason.
   Done when: the piece is in shaping with the person's reason on the issue.
7. If a pull request conflicts with main after another merge, move the piece back with `gate.py move <n> shaping --type conflict --reason "conflicts with main"`, then run `gate.py move <n> ready` (the spec and the judge are unchanged) and run it again. The run merges main and the builder resolves the conflicts; the keep check proves both changes still work. Never resolve the conflicts yourself.
   Done when: the piece is in ready, or the run has started.
8. To stop a live run, use `python3 "<KIT>/scripts/gate.py" stop`. To see hand-backs by type, use `python3 "<KIT>/scripts/gate.py" report`. To drop a piece, use `python3 "<KIT>/scripts/gate.py" move <n> dropped --reason "<why>"`.

## Rules
- Never build a piece yourself in this session. The run builds; the gate judges.
- Never merge a pull request. The person merges.
- Never move a state label by hand.
- Never reset, rewrite or force-push a piece branch. The run refuses a branch whose pushed commits are missing locally.
- Every move back needs both `--type` and `--reason`. Use `person-rejected` for a rejected pull request, `conflict` when a conflict cannot be handed to the builder, and the type reported by the run for other hand-backs.
