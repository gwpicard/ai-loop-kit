# Blocked commands

This file records the rules for commands and changes that can lose work or
cross a boundary. Read it before changing the kit or running a command that
could cause lasting harm.

`kit/hooks/guard.py` is the command hook. It matches regular expressions on
the raw command, so it refuses the forms it recognises, not every possible
shell program. It is an early warning, not a sandbox, and it allows a call it
cannot parse. The lines that hold are the diff check in `kit/scripts/merge.py`
and branch protection on the default branch. Do not try another spelling,
tool or sequence to get the same blocked result.

## What the hook refuses in every session

These apply wherever the plugin is enabled, in Bash commands.

- A recursive delete: `rm` with a recursive flag, `find` with `-delete`, or
  `rmtree`.
- A `git push` that forces (`-f`, `--force`, `--mirror`, `--all`, or a
  refspec starting with `+`).
- A `git push` that names `main`, `master` or the default branch. The
  environment variable `LITE_DEFAULT_BRANCH` names the default branch.
- A secret shape in content that a session writes with the Edit, Write,
  MultiEdit or NotebookEdit tools (a private key header, a GitHub token, an
  AWS key id, an Anthropic key or a Slack token). The hook checks written
  content, not diffs or shell commands.

A bare `git push` from `main` is not caught, because the hook does not ask
git which branch is checked out.

## What it also refuses in the loop's own sessions

The loop sets `LITE_ROLE` for the sessions it starts. When it is set, the
hook also refuses:

- `git push`, `merge`, `checkout`, `switch`, `restore`, `apply` and
  `branch -f`.
- Any `gh` command.
- A write, by a file tool or by a shell redirection or `tee`, to a path in
  `LITE_LOCKED` (the test writer's locked tests), or to a tracked test file.
  This is the test lock. The issue may name a path it allows, and the check in
  `merge.py` honours that; the hook does not.
- Any write inside the project by the reviewer role. It may write scratch
  files in the system temp folder.
- Any write by the pass role outside `.lite/pass/`.

Issue branches reach the loop branch only through `merge.py`. It merges the
reviewed commit, or a conflict-free merge of it with the current loop branch,
after a full test run on that exact commit, and refuses a diff that touches a
protected path, a workflow, a lockfile or manifest, a settings file or an
existing test, unless the issue names that path.

## Other protections

Claude Code's `.claude/settings.json` has a separate command deny list. It
also denies commands that the hook does not cover, including `git reset
--hard`, some secret and credential access, release and repository changes,
and some commit options. It does not mirror every rule in this file. Do not
edit that settings file as part of this list's maintenance.

A refusal from the settings does not say which rule matched. When one part
of a chained command matches, Claude Code refuses the whole chain. Find the
denied part in the deny list before you report a block. Run the other parts
separately, and stop on the denied part.

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
