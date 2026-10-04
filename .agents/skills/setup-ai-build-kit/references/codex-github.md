# GitHub access in Codex

Use this only when a kit operation needs GitHub and Codex cannot reach it or
authenticate. First report the failing command and exit status, with credentials
masked. Keep the last plan until a refresh succeeds.

## Reach GitHub

Run `curl -I --connect-timeout 10 https://api.github.com` in Codex's command tool.
A successful response proves connectivity, not sign-in. On a DNS or connection
failure, request the client's authorised network access. If that needs a settings
change, identify the active Codex home, profile, project settings and managed
policy first. Back up the file and get the person's authorisation before editing.
Keep filesystem sandboxing and the approval reviewer. Never bypass a managed
restriction or combine the two permission systems below.

For a configuration using the standard sandbox settings, the root key and table
are:

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

For a configuration using `default_permissions`, a named workspace profile can
provide the same access:

```toml
default_permissions = "workspace-network"

[permissions.workspace-network]
extends = ":workspace"

[permissions.workspace-network.network]
enabled = true
```

These are examples, not files to append. Update the active settings without
creating duplicate keys, and preserve any existing profile restrictions. Start
a new session and verify its actual profile, since a client can override the
default. See [Codex configuration](https://developers.openai.com/codex/config-reference/).

## Use the current GitHub login

Compare `gh auth status --hostname github.com` in Codex and the person's terminal.
Never use `--show-token`. Report `GH_TOKEN` and `GITHUB_TOKEN` presence only; an
invalid environment credential overrides a valid stored one. Compare the `gh`
executable, user and effective configuration directory, including `HOME`,
`GH_CONFIG_DIR` and `XDG_CONFIG_HOME`. Do not re-authenticate a working host login
merely because Codex cannot read it.

If those match and the terminal can use the stored login while Codex cannot,
offer the [session launcher](../scripts/codex-with-github.py). The person runs
it with python3 from an ordinary terminal in their project. Give them a command
with the launcher's actual absolute installed path. A terminal in an editor is
fine too; no editor or Orca integration is required. Pass Codex arguments after
the script path when needed.

The launcher uses an existing `GH_TOKEN` or `GITHUB_TOKEN` if present. Otherwise
it captures the current GitHub CLI login in memory and supplies `GH_TOKEN` only
to the new Codex process. It never writes a credential to a file or changes
GitHub's storage. It disables shell snapshots and uses a dedicated process to
keep the credential out of snapshots and a shared daemon. It preserves the
configured permissions and approval reviewer. The old session gains no access.

Offer this only for access the person authorised. The agent does not run it or
read a stored credential itself without that authorisation. Do not put tokens
in settings, project files, shell startup files, prompts or logs. Do not enable
HTTP debug logging or dump the environment in the resulting session.

Codex must inherit the credential. Check presence in its command tool, never its
value. The default shell environment policy passes it through. If a custom policy
filters it, inspect `shell_environment_policy.inherit`, `ignore_default_excludes`
and `filters` or the legacy `exclude` and `include_only` settings. Preserve the
policy and ask the person to allow this credential for the session rather than
turning all filtering off. Include rules cannot restore an earlier exclusion.
See [Codex environment filtering](https://developers.openai.com/codex/config-reference/)
and [GitHub's credential precedence](https://cli.github.com/manual/gh_help_environment).

## Verify in the new command tool

Run `gh api user --jq .login` and `gh repo view --json nameWithOwner` from the
project. The first confirms the account, the second the repository. Refresh the
plan only after they succeed. A read does not prove write permissions; a refused
operation still needs its own repository permission. Do not create a test issue.
A connector's separate authorisation failure is not repaired by this launcher.
