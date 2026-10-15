# Sandbox for walk-away runs: research and choice (15 October 2026)

Choice: Claude Code's built-in sandbox, passed per session with `claude -p --settings '<json>'`. Docker waits until a run shows a gap the built-in sandbox cannot close. Source: https://code.claude.com/docs/en/sandboxing and https://code.claude.com/docs/en/settings-reference (check exact key names against the installed Claude Code version before relying on them).

## What it is
- It wraps Bash commands and their children: Seatbelt on macOS, bubblewrap and socat on Linux. It is off by default.
- It does not cover Read, Edit, Write or WebFetch (those follow permission rules), hooks, or MCP servers. Subagents use the parent's sandbox.
- Default: writes allowed to the working directory and a temp folder; reads allowed almost everywhere, including `~/.ssh`; network only through a proxy with an empty allowlist.
- Writes to `.claude` settings, `.gitconfig`, shell startup files and `~/.claude` are always denied.
- In `-p` mode, if the sandbox is unavailable the session runs unsandboxed, unless `sandbox.failIfUnavailable` is true.
- Claude can retry a failed command unsandboxed (`dangerouslyDisableSandbox`); `"allowUnsandboxedCommands": false` passed in `--settings` forbids that, and makes repository settings that loosen the sandbox ignored (Claude Code 2.1.285 or later).

## Settings the kit passes for a walk-away session (starting point; verify each key)
```json
{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,
  "filesystem":{"allowWrite":["<build folder>","~/.npm","~/.cache/pip"],
    "denyRead":["~/"],"allowRead":["<build folder>","<package caches>"]},
  "credentials":{"files":[{"path":"~/.ssh","mode":"deny"},{"path":"~/.config/gh","mode":"deny"},{"path":"~/Library/Keychains","mode":"deny"}],
    "envVars":[{"name":"GITHUB_TOKEN","mode":"deny"},{"name":"GH_TOKEN","mode":"deny"},{"name":"NPM_TOKEN","mode":"deny"}]},
  "network":{"strictAllowlist":true,"allowedDomains":["registry.npmjs.org","pypi.org","files.pythonhosted.org"]}},
 "permissions":{"blockReadsOutsideWorkingDirectories":true,
  "deny":["Read(~/.ssh/**)","Read(~/.config/gh/**)","Read(~/Library/Keychains/**)","Bash(git push *)","Bash(gh *)"]}}
```
- The array form of `credentials` comes from the sandboxing page; the settings reference shows an object form. Test which one the installed version accepts.
- Use absolute paths for the build folder in `--settings`.
- Load no MCP servers in builder sessions. Keep the kit's guard hook: it runs outside the sandbox and still guards Edit and Write.
- The allowed domains are per project: setup should propose them from the Prepare command (npm, pip, uv) and the person confirms.

## What it does not protect (say so in the docs)
Edit and Write are limited only by permission rules; hooks and MCP servers run unsandboxed; an allowed domain can carry data out; the Claude process holds its own login.

## Pre-run check (refuse walk-away if any fails)
1. Claude Code version at least 2.1.285.
2. The session settings carry `enabled`, `failIfUnavailable: true` and `allowUnsandboxedCommands: false`; no loaded settings file has `excludedCommands`; no MCP config is loaded.
3. Linux: `bwrap` and `socat` on PATH, and AppArmor allows unprivileged user namespaces; not inside a container that needs a weaker nested sandbox.
4. The permission mode is not bypass.
5. Active probe: a short `claude -p` with the same settings is asked to run `touch ~/sandbox-probe`, read a file under `~/.ssh`, and `curl --noproxy '*' https://example.com`. Pass only if all three fail and no probe file exists. Also confirm reads of `~/.config/gh` and the keychain folder fail.
6. `GH_TOKEN`, `GITHUB_TOKEN` and `NPM_TOKEN` are absent from the child environment.
7. The login stays valid for the length of the run.

## Later
The sandbox runtime (`npx @anthropic-ai/sandbox-runtime claude`) wraps the whole Claude process without Docker, but is a beta. Docker per attempt (sandcastle shape) gives the strongest boundary, at the cost of Docker Desktop on macOS.
