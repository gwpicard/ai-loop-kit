---
name: run
description: Build ready pieces with the selected Claude Code or Codex backend and report gate-checked pull requests. Use when the person wants ready pieces built.
---
# Run

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

## Now
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" status 2>&1 | head -20`

## Steps
1. Show ready pieces and explain that each gets up to three attempts. If none are ready, suggest `/ai-loop-kit:shape` and stop.
2. Start `python3 "<KIT>/scripts/run.py"` in the background, writing KIT in full. Optional piece numbers select pieces. `Agent:` in AGENTS.md selects the backend; `--agent codex` or `--agent claude` overrides it.
3. Report attended output and `.loop/logs/` failures until "Run finished." Report every pull request link and hand-back reason. The person reviews and merges.
4. After merges, run `python3 "<KIT>/scripts/gate.py" sync`.

If interrupted, orphaned, locked, dirty, stopped, conflicting or returned for environment trouble, load [run-recovery](../run-recovery/SKILL.md).
If the person rejects a pull request, load [reject-handling](../reject-handling/SKILL.md).
If the person will be absent, read [walk-away guidance](references/walk-away.md) before adding `--walk-away`.

The run enforces `Waiting limit:` (default 3) before each piece. Attempts stop after `Idle limit:` minutes without output (default 10), returning `builder-failed`.

Stop with `gate.py stop`; inspect hand-backs with `gate.py report`; drop with `gate.py move <n> dropped --reason "<why>"`.

## Rules
Never build here, merge, change state labels by hand, reset, rewrite or force-push piece branches. Every move back needs `--type` and `--reason`.
The run refuses branches whose pushed commits are missing locally.

For goal pieces, report main and attempt measurements and every fresh `.loop/hypothesis`. For gauntlet pieces, report three blind verdicts and critic order. The gate puts this evidence in the pull request.
