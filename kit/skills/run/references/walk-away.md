# Walk-away runs

A run walks away when `gate.py doctor --walk-away` passes. Doctor owns the checks; Prepare runs outside the agent sandbox.

Claude requires Code 2.1.285 or later, its live sandbox probe, a wired guard, green Prepare and Test on fresh main, 10 GB free, room in the approval queue, confirmed sandbox domains and no exposed child tokens.

Claude uses the built-in shell sandbox, a strict network allowlist and no MCP servers. Read, Edit, Write and hooks are outside that sandbox; permission rules and the file-tool hook limit access. A permitted domain can still carry data out.

The Codex backend is a preview and requires its live home-write, SSH-read and network probe, green Prepare and Test on fresh main, the Test command passing inside its builder sandbox, 10 GB free and room in the approval queue. Its workspace-write sandbox permits writes only in the build folder and disables network access. Codex has no Claude guard hook or Edit denies: the gate checks settings, protected paths and secrets.

The run writes `.loop/heartbeat` every minute and `.loop/summary.md` when finished. It posts the summary to the `AI Loop Kit run log` issue, mentioning the person only when a piece needs them or waits on another. The run never merges into `main`. With `Base merges: run`, it merges gated pieces into a base branch other than main, except pieces with contract findings or changes to `.github/`, `.githooks/` or `AGENTS.md`; the approval queue then does not apply.
