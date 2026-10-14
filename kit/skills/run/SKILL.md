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
2. Start the run in the background: `python3 "<KIT>/scripts/run.py"` (or with piece numbers to build only those). Write the KIT path out in full.
   Done when: the run has started.
3. While it runs, report each line it prints: claims, attempts, passes, failures. The attempt logs are in `.loop/logs/`.
   Done when: the run prints "Run finished."
4. Report the result: each pull request link for the person to read and merge, and each piece sent back to shaping with its reason.
   Done when: the person has every link and reason.
5. After the person merges, run `python3 "<KIT>/scripts/gate.py" sync` to move merged pieces to done.
6. If the person rejects a pull request, move the piece back in their words: `python3 "<KIT>/scripts/gate.py" move <n> shaping --reason "<their words>"`. Leave the pull request open; the next build pushes to the same branch and updates it. If the spec or the judge must change, use `/ai-loop-kit:shape`. Then the piece goes through ready again, and the next build gets the reason.
   Done when: the piece is in shaping with the person's reason on the issue.

## Rules
- Never build a piece yourself in this session. The run builds; the gate judges.
- Never merge a pull request. The person merges.
- Never move a state label by hand.
- Never reset, rewrite or force-push a piece branch. The run refuses a branch whose pushed commits are missing locally.
