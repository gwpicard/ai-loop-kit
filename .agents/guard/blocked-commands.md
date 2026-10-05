# Blocked commands

Never run these. Each one can destroy work, or cross a boundary this project
has agreed to keep, in a way the people on this project cannot see coming or
recover from alone.

This file is the portable instruction, and the source of truth. It holds in
any harness, including one with no mechanical enforcement at all: a missing
deny list reduces automation, it does not remove the rule. Where a tool
supports a command deny list, this list is also mirrored there as stronger,
mechanical enforcement:

- Claude Code: `.claude/settings.json` → `permissions.deny` (shipped, mirrors this list).
- Codex: set `approval_policy`/sandbox in `~/.codex/config.toml` so shell writes need approval.
- Cursor: add the same patterns under Cursor's command allow/deny settings.

When you change this file, update `.claude/settings.json` to match. Two
entries below are left out of the mechanical deny on purpose: `git checkout .`
/ `git restore .` are allowed inside the fix loop's announced reset step, and database
drops are too varied to pattern-match, so they remain instruction-only along
with the standing-restriction entries below, none of which reduce to a single
shell pattern.

When the coding agent refuses a command, or this list forbids it, stop. Then
tell the person in one line which command was refused and what it was for,
and let them decide. Never reach the same result another way: another
spelling, another tool such as `find -delete` or a script, or the same work
split into steps.

## Commands

- git reset --hard (throws away unsaved work)
- git checkout . and git restore . (the same thing wearing different clothes; allowed only inside fix's reset step, announced out loud first)
- git push --force (rewrites shared history under teammates' feet)
- git clean -fd (deletes files git never saved)
- a recursive delete in any spelling, such as rm -rf, rm -r or rm --recursive (deletes anything, recursively, with no undo)
- git reflog expire (throws away the history Git uses to recover lost work)
- git gc with --prune (the same, for work nothing points at any more)
- any command that drops or empties a database table

## Standing restrictions

These hold regardless of build path, and regardless of whether a mechanical
guard can express them:

- no production database migration without a backup and a rehearsal on a copy;
- no production deletion or bulk update without the human's explicit approval, named to the specific action;
- no printing, committing, or otherwise outputting a secret, anywhere;
- no disabling authentication or an access control to make a test or a check pass;
- no bypassing a red project check to ship or merge anyway;
- no force-merging or auto-merging over a review the build path requires;
- no activating a flagged capability before its recorded condition is met or the person has accepted the risk on the record;
- no withdrawing, softening, or redefining a risk notice already given, and no treating your own work as the independent review a build path names.

Commit before anything sweeping. If one of these ever looks necessary,
stop, say why, and let the human decide with the reason in front of them.
