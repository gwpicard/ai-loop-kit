---
name: run
description: Builds the ready pieces with the selected Claude Code or Codex backend; the gate runs the judge; a pass opens a pull request for the person. Use when pieces are ready and the person wants them built.
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
2. Start the run in the background: `python3 "<KIT>/scripts/run.py"` (or with piece numbers to build only those). It uses `Agent:` from the loop section of `AGENTS.md`; add `--agent codex` or `--agent claude` to override it for this run. Add `--walk-away` only when the person will be absent and `gate.py doctor --walk-away` passes. Claude walk-away checks require Claude Code 2.1.285 or later, its live sandbox probe, a wired guard, a green Prepare and Test on fresh main, at least 10 GB free, an approval queue below its limit, confirmed sandbox domains and no exposed child tokens. Codex walk-away checks require its live home-write, SSH-read and network probe to pass, a green Prepare and Test on fresh main, at least 10 GB free and an approval queue below its limit. Prepare runs outside the agent sandbox. Write the KIT path out in full.
   Done when: the run has started.
3. For an attended run, report each line it prints: claims, attempts, passes and failures. The attempt logs are in `.loop/logs/`. A walk-away run writes `.loop/heartbeat` every minute and `.loop/summary.md` when it ends. It also posts the summary to the `AI Loop Kit run log` issue, mentioning the person only when a piece needs them.
   Done when: the run prints "Run finished."
4. Report the result: each pull request link for the person to read and merge, and each piece sent back to shaping with its reason.
   Done when: the person has every link and reason.
5. After the person merges, run `python3 "<KIT>/scripts/gate.py" sync` to move merged pieces to done.
6. If the person rejects a pull request, ask: was something missing from the contract? If yes, use `/ai-loop-kit:shape` to add an exit check or a `(stays)` item, then move the piece to shaping with `--type judge-gap` and take it through ready again. If the rejection is a matter of taste, move it back in the person's words with `--type person-rejected`; leave the pull request open so the next build retries with that reason. Use `python3 "<KIT>/scripts/gate.py" move <n> shaping --type judge-gap --reason "<what was missing>"` or `python3 "<KIT>/scripts/gate.py" move <n> shaping --type person-rejected --reason "<their words>"`.
   Done when: the piece is in shaping with the person's reason on the issue.
7. If a pull request conflicts with main after another merge, move the piece back with `gate.py move <n> shaping --type conflict --reason "conflicts with main"`, then run `gate.py move <n> ready` (the spec and the judge are unchanged) and run it again. The run merges main and the builder resolves the conflicts; the keep check proves both changes still work. Never resolve the conflicts yourself.
   Done when: the piece is in ready, or the run has started.
8. To stop a live run, use `python3 "<KIT>/scripts/gate.py" stop`. To see hand-backs by type, use `python3 "<KIT>/scripts/gate.py" report`. To drop a piece, use `python3 "<KIT>/scripts/gate.py" move <n> dropped --reason "<why>"`.

## Rules
- Never build a piece yourself in this session. The run builds; the gate judges.
- For a goal piece, each attempt needs a fresh hypothesis in `.loop/hypothesis`; report the main and attempt measurements and every hypothesis tried. For a gauntlet piece, report the three blind verdicts and the order each critic saw. The gate includes this evidence in the pull request.
- Never merge a pull request. The person merges.
- Never move a state label by hand.
- Never reset, rewrite or force-push a piece branch. The run refuses a branch whose pushed commits are missing locally.
- Every move back needs both `--type` and `--reason`. Use `person-rejected` for a rejected pull request, `conflict` when a conflict cannot be handed to the builder, and the type reported by the run for other hand-backs.
- A Claude walk-away session uses Claude Code's built-in shell sandbox with a strict network allowlist and no MCP servers. Read, Edit, Write and hooks are outside that sandbox; permission rules and the walk-away file-tool hook limit their access. A permitted network domain can still carry data out. A Codex walk-away session uses workspace-write with the build folder as its only writable root and network disabled. Its active probe must block a home write, an SSH read and an outside network request. Codex has no Claude guard hook or Edit denies, so the gate checks settings, protected paths and secrets. The run never merges a pull request.
