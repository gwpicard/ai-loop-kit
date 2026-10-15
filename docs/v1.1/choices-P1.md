# P1 choices and local checks

Date: 15 October 2026

P1 uses Claude Code's built-in Bash sandbox for walk-away sessions. The run
script still owns GitHub calls and pull request creation. The person merges.

## Claude Code on this Mac

`claude --version` reports `2.1.289 (Claude Code)`. The plan requires 2.1.285
or later.

I ran `claude -p --settings` with the proposed sandbox settings and the
`--strict-mcp-config` flag. Claude Code reached session initialisation without
a settings parse error. The real boundary probe did not reach Bash: Claude
Code reported `Not logged in · Please run /login`. Its startup hook also could
not create a session directory under `~/.claude` in this restricted workspace.
The active sandbox result is therefore unverified. `gate.py doctor
--walk-away` and `run.py --walk-away` refuse to start until that probe passes.

The P1 settings keys were passed to the installed version as JSON. The session
accepted the settings object before authentication failed:

| Key | Choice | Local evidence |
| --- | --- | --- |
| `sandbox.enabled` | `true` | Accepted during session initialisation. Active enforcement is unverified. |
| `sandbox.failIfUnavailable` | `true` | Accepted during session initialisation. |
| `sandbox.allowUnsandboxedCommands` | `false` | Accepted during session initialisation. |
| `sandbox.filesystem.allowWrite` | Build worktree, system temp, npm and pip caches | Accepted during session initialisation. |
| `sandbox.filesystem.allowRead` | Build worktree, system temp, npm and pip caches | Accepted during session initialisation. |
| `sandbox.filesystem.denyRead` | SSH, GitHub CLI config and macOS keychains | Accepted during session initialisation. |
| `sandbox.credentials.files` | Object form with `path` and `mode: deny` | The object-form settings reached initialisation. |
| `sandbox.credentials.envVars` | Object form with `name` and `mode: deny` | The object-form settings reached initialisation. |
| `sandbox.network.strictAllowlist` | `true` | Accepted during session initialisation. |
| `sandbox.network.allowedDomains` | Project-confirmed package registries | Accepted during session initialisation. |
| `permissions.blockReadsOutsideWorkingDirectories` | `true` | Accepted during session initialisation. |
| `permissions.deny` | Secret `Read` patterns, `git push`, and `gh` | Accepted during session initialisation. |
| `hooks.PreToolUse[].matcher` | `Bash|Edit|Write|MultiEdit|NotebookEdit` | Session hook wiring is included in the settings object; the live hook did not run because authentication failed first. |
| `hooks.PreToolUse[].hooks[].type` | `command` | Same limitation: accepted by the settings object, but hook execution was not verified. |
| `hooks.PreToolUse[].hooks[].command` | Existing guard and the walk-away file boundary | Same limitation: hook execution was not verified. |
| `--strict-mcp-config` and empty `mcpServers` | Use for every unattended Claude session | The empty MCP object was accepted. No MCP servers appeared in the session initialisation event. |

The CLI help on 2.1.289 lists `--settings <file-or-json>`, `--strict-mcp-config`
and `--mcp-config`. The session also uses `-p`, `--output-format
stream-json`, `--verbose`, `--permission-mode acceptEdits` and `--tools`; these
are command-line options, not settings keys. The active probe uses Bash only.

I also tried both the array and object forms of `sandbox.credentials`. Both
passed argument parsing in 2.1.289, but the object form matches the current
Claude Code documentation and is used by the kit. Neither form had a live
credential-read test on this Mac.

## Boundaries

The shell sandbox does not cover Claude's Read, Edit, Write, web tools, hooks
or MCP servers. Walk-away sessions load no MCP servers, use permission denies
for secret reads, and add a PreToolUse hook that limits direct file-tool writes
to the active build folder. The existing guard hook still checks commands and
protected paths. Package registry domains must be recorded in the project's
`Sandbox domains:` setting before a walk-away run. A permitted domain can still
carry data out, and Claude Code itself retains its own sign-in.

The run writes `.loop/heartbeat` and `.loop/summary.md`, keeps macOS awake with
`caffeinate`, and leaves each pull request for the person to merge.

## Sources

- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Claude Code settings reference](https://code.claude.com/docs/en/settings-reference)
