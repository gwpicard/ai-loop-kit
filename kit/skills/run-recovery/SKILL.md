---
name: run-recovery
description: Diagnose interrupted runs, orphan processes, run locks, dirty folders, conflicts and environment hand-backs from recorded evidence.
user-invocable: false
---
# Run recovery

Read the run output, its `next:` step and `.loop/logs/`. Preserve unsaved work. Never reset, clean, rewrite or force-push a piece branch.

Run `"<KIT>/bin/kit-python" "<KIT>/scripts/run.py"` again after an interruption. It checks the run lock, refuses live runs or orphan builders and reviewers, takes over dead locks, cleans abandoned reviews and returns interrupted building pieces as `environment`. Follow a refusal's `next:` step; never remove the lock to bypass it.

A dirty folder returns as `environment`; preserve it and follow `next:`. For other environment hand-backs, address the recorded cause before reshaping. A stop uses `gate.py stop`, returns `stopped` and preserves the last real failure.

For a pull request conflicting with the base branch, with the spec and judge unchanged, run `"<KIT>/bin/kit-python" "<KIT>/scripts/run.py" --retry-conflict <n>` in the background. The runner moves it through shaping with type `conflict` and through ready before retrying. Its builder resolves conflicts and Keep checks both changes. Never resolve conflicts here.

A result that says `Not merged` leaves the piece in approval: read the reason, then merge it on GitHub or reshape it. If GitHub merged it but the piece is still in approval, run `gate.py sync`.
