# Contributing

AI Loop Kit is built with itself, so the way to change it is the way the kit
asks its users to work.

## Changes go through shaped issues

A change to `kit/` starts as an issue. Describe the evidence first: a failure
in a real run, friction in real use, or a gap between what the kit does and the
walk-away goal. Shape the issue with acceptance criteria and dependencies (the
shape skill does this), and let the loop build it. Hand edits to `kit/` are the
exception, for a loop that cannot start. Read `docs/DESIGN.md` before you
propose a change, and `AGENTS.md` for the standing rules.

A change that makes code, text or a check redundant removes it in the same
pull request. The kit should stay small enough to read in one sitting.

## Run the checks

From the repository root:

    tests/run-all.sh

This runs the kit's tests in parallel (`python3 kit/tests/run.py`, about 80
seconds) and then the house rules (`sh tests/house-rules.sh`). Both must pass.
The tests use a fake `gh` and a fake `claude`, so they need no network and no
account.

## House rules

- Write British spelling, with no em or en dashes and paragraphs under about
  100 words. Claim only what the code or a test shows.
- Never put an issue or pull request number in a tracked file.
- Never add a model co-author line or a session link to a commit or pull
  request. In a fresh clone, run `git config core.hooksPath .githooks` once;
  the hook strips them.
- Never push to `main` and never force-push. Open a pull request with base
  `main`.
- Never put a secret in a tracked file.
- Write public text (pull request descriptions, documentation, release notes)
  in line with the guides in `.agents/maintainer-skills/`.

`tests/house-rules.sh` checks the mechanical ones over every tracked file.

## Reporting a vulnerability

See `SECURITY.md`.
