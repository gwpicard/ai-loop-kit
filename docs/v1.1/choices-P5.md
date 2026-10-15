# P5 choices: non-interactive agent backend

Checked 15 October 2026 against the installed `codex-cli 0.162.1`.

## Backend selection

- `Agent: claude` is the default. `Agent: codex` selects Codex for builders,
  standards reviewers, contract reviewers and critics.
- The ready record stores the selected backend. `run.py --agent codex` and
  `run.py --agent claude` override it for one run without changing that record.
- The interactive skills stay in Claude Code. `LOOP_CLAUDE` remains available
  for tests; `LOOP_CODEX` names a fake Codex executable in tests.
- Codex can save Claude credit. Its workspace-write sandbox applies to the
  agent process, unlike Claude Code's Bash-only sandbox.

## Codex invocation

The installed `codex exec --help` lists `--json`, `--sandbox`, `--ask-for-approval`,
`--cd`, `--ignore-user-config` and `--ephemeral`. The backend starts:

```text
codex exec --json --sandbox workspace-write --ask-for-approval never
  --cd <build-folder> --ignore-user-config --ephemeral
  --config sandbox_workspace_write.network_access=false
  --config sandbox_workspace_write.writable_roots=[]
  --config sandbox_workspace_write.exclude_slash_tmp=true
  --config sandbox_workspace_write.exclude_tmpdir_env_var=true <brief>
```

The `--cd` folder is the build folder. No `--add-dir` is passed. User and
project Codex configuration is ignored, so an additional writable root or
network setting cannot loosen the session. Network access and writable roots
are also set explicitly. The Codex process environment removes `GH_TOKEN` and
`GITHUB_TOKEN`.

Codex JSONL `item.completed` events carry assistant text in an
`agent_message` item. The session logger writes that text and counts every
event as idle activity. Review and critic verdict parsing receives the final
agent message, where it reads the existing tagged `<verdict>` JSON block.

## Walk-away check

Prepare stays outside the sandbox and still runs by `run.py`. A Codex pre-run
session attempts to create `~/sandbox-probe`, list `~/.ssh`, and reach
`https://example.com`. All three commands must fail. The run refuses to start
if a command succeeds, an expected status is missing, Codex exits with an
error, or the probe file appears.

Codex has no Claude guard hook or Claude Edit deny rules. The gate remains the
check for the frozen judge, loop settings, protected paths and secrets. The
probe also means a Codex installation that can read `~/.ssh` cannot run
unattended, even if its write and network checks pass.

## Alternatives considered

- Keep Claude Code as the only backend. This avoids another session launcher,
  but does not offer the requested Codex sandbox or save Claude credit.
- Use Codex's personal configuration. This could add writable roots or enable
  network access, so the launcher ignores it and sets the sandbox options on
  each session.
- Use Claude's guard hook and Edit denies as the boundary for Codex. Those
  controls are Claude-only; the Codex sandbox and the gate provide the
  backend's boundary instead.
