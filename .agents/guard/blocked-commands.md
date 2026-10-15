# Blocked commands

This file records the rules for commands and changes that can lose work or
cross a boundary. Read it before changing the kit or running a command that
could cause lasting harm.

`kit/hooks/guard.py` is the command hook. It refuses the forms it recognises.
It checks words and common shell wrappers, not every possible shell program.
The hook is a guard, not a sandbox. Do not try another spelling, tool or
sequence to get the same blocked result.

## Commands the hook refuses

- Recursive deletion through `rm`, `find`, `xargs rm`, or recognised Python
  or Node commands that call recursive removal.
- `git clean`, forced pushes, and pushes to `main` or `master`.
- `eval` in a builder session, and `eval` that wraps another refused command.
- `gh pr merge` and attempts to change a `state:` label by hand.
- A command in a builder session that the hook cannot read safely.

In a builder session (`LOOP_BUILDER=1`), the hook also refuses every push,
every `gh` command, Perl or Ruby code passed with `-e`, and writes to
`.claude/`, `.githooks/` or a protected path. It refuses file-tool edits to
those paths as well. The gate checks state changes; only the gate may move a
piece between states.

## Other protections

Claude Code's `.claude/settings.json` has a separate command deny list. It
also denies commands that the hook does not cover, including `git reset
--hard`, some secret and credential access, release and repository changes,
and some commit options. It does not mirror every rule in this file. Do not
edit that settings file as part of this list's maintenance.

The hook and settings file do not cover every restriction below. These remain
rules for every build path:

- Do not drop or empty a database table.
- Do not run a production database migration without a backup and a rehearsal
  on a copy.
- Do not delete production data or make a bulk update without the person's
  explicit approval for that action.
- Do not print, commit or otherwise expose a secret.
- Do not disable authentication or access control to pass a check.
- Do not bypass a failed project check to ship or merge.
- Do not force-merge or auto-merge over a required review.
- Do not activate a flagged capability before its recorded condition is met
  or the person accepts the risk on the record.
- Do not withdraw, soften or redefine a risk notice already given. Do not
  treat your own work as an independent review.

If a command is refused, stop. Report the command and what it was meant to
do, then let the person decide. Never use another spelling, tool or sequence
to reach the same result. If a restricted action seems necessary, explain
why and wait for the person's decision.
