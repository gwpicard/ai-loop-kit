# Case: normal

Scenario evals need the real model, so `tests/run-all.sh` does not run them. Run this
case by hand after a change to the skill or the model. Judge it from the session log and
the final state of the fixture project.

## Setup

An empty throwaway project: a Git repository with a stand-in `origin`, one commit, no
code, no `.claude/` folder and no `AGENTS.md`. The stand-in `gh` is on the path. There is
no GitHub App. The kit is installed as a plugin, outside the project. The person types:

> /setup

The person answers each question by accepting the recommended answer.

## Expect

1. The skill runs the tooling check first, and carries on only when it passes.
2. It runs the setup script with `--dry-run`, shows the person the list of files it will
   write, then runs it for real.
3. It writes the foundation files and overwrites nothing: `AGENTS.md`, `CLAUDE.md`,
   `docs/overview.md`, `docs/README.md`, `docs/area-map`, `CHANGELOG.md`,
   `.github/workflows/checks.yml`, `.gitignore`, the policy file, the settings, the
   hooks and the pre-push hook.
4. It gives the gate's label names, and, after the first piece is captured, the reply gives the `next:` line for the person
   to create the labels. The gate cannot create them before the App exists.
5. It captures the first piece locally, as a quick-path piece that scaffolds the project
   and its test runner. It does not move the piece to ready.
6. It never calls `gh`, and never shows the App manifest link. The closing message says
   the App comes in the second half of `/setup`, and that an unattended run waits for it.
7. It asks each question once, with a recommended answer, and a skipped answer becomes an
   open question in the project, never a stop.

## Fail if

- a file that was there before is changed;
- the skill calls `gh`, creates a label, opens an issue or shows the App link;
- the closing message does not name the second half of `/setup`;
- the first piece is moved to ready.
