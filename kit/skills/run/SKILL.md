---
name: run
description: Build ready pieces with the selected Claude Code or Codex backend and report gate-checked pull requests. Use when the person wants ready pieces built.
---
# Run

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

## Now
!`"${CLAUDE_PLUGIN_ROOT}/bin/kit-python" "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" status 2>&1 | head -20`

## Steps
1. Show ready pieces; each gets three attempts by default. If none are ready, suggest `/ai-loop-kit:shape` and stop.
2. Start `"<KIT>/bin/kit-python" "<KIT>/scripts/run.py" --detach`, writing KIT in full; it outlives this session. Optional piece numbers select pieces. `Agent:` in AGENTS.md selects the backend; `--agent codex` or `--agent claude` overrides it. It walks away when the unattended checks pass, else runs attended and names the failed check; `--attended` forces that.
3. Print the full path to `.loop/dashboard.html`, the run page. Read the printed log until "Run finished." Report every pull request link, hand-back reason and held piece with its `next:` step. The person reviews and merges, unless `Base merges: run` merged it into the base.
4. After merges, run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" sync`.

If interrupted, orphaned, locked, dirty, stopped, conflicting or returned for environment trouble, load [run-recovery](../run-recovery/SKILL.md).
If the person rejects a pull request, load [reject-handling](../reject-handling/SKILL.md).
If the person will be absent, read [walk-away guidance](references/walk-away.md); `--walk-away` refuses attended runs.

The run enforces `Waiting limit:` (default 3) before each piece and ends an attempt after `Idle limit:` minutes without output (default 10) as `builder-failed`.

Stop with `gate.py stop`; inspect hand-backs with `gate.py report`; drop with `gate.py move <n> dropped --reason "<why>"`.

## Rules
Never build here, merge, change state labels by hand, reset, rewrite or force-push piece branches. Every move back needs `--type` and `--reason`.

For goal pieces, report main and attempt measurements and every fresh `.loop/hypothesis`. For gauntlet pieces, report three blind verdicts and critic order. The gate puts it in the pull request.

`Test command:` always runs; `Keep:` adds checks. The pull request reports regression results from the final commit.
