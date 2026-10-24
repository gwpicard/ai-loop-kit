# Walk-away runs

Add `--walk-away` only when the person will be absent and `gate.py doctor --walk-away` passes. Doctor owns the prerequisite checks; Prepare runs outside the agent sandbox.

Claude requires Code 2.1.285 or later, its live sandbox probe, a wired guard, green Prepare and Test on fresh main, 10 GB free, room in the approval queue, confirmed sandbox domains and no exposed child tokens.

Claude uses the built-in shell sandbox, a strict network allowlist and no MCP servers. Read, Edit, Write and hooks are outside that sandbox; permission rules and the file-tool hook limit access. A permitted domain can still carry data out.

Codex requires its live home-write, SSH-read and network probe, green Prepare and Test on fresh main, 10 GB free and room in the approval queue. Its workspace-write sandbox permits writes only in the build folder and disables network access. Codex has no Claude guard hook or Edit denies: the gate checks settings, protected paths and secrets.

The run writes `.loop/heartbeat` every minute and `.loop/summary.md` when finished. It posts the summary to the `AI Loop Kit run log` issue, mentioning the person only when a piece needs them or waits on another. The run never merges into `main`; with `Base merges: run` it merges gated pieces into the base branch.
