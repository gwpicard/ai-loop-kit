# AI Loop Kit

Build software with Claude Code in small steps. A script checks each step before you review the change.

Version 1.2.0 is released. It works best with Python and Node projects.

![How AI Loop Kit works](docs/images/how-it-works.svg)

## What it does

1. Shape an idea into a **piece**: a GitHub issue with the task, its limits and a contract. The contract lists the results the change must meet.
2. You approve the task and its contract before work starts.
3. Run the piece. The selected agent gets up to three fresh tries to build it.
4. The **gate**, a script that controls the steps, runs a **judge** (tests for the contract) and your **keep check** (the project's full test command). Two fresh reviewers check the code and the contract. The gate runs the checks again.
5. If the checks pass, the gate opens a pull request. You read it and merge it.

## Who it is for

AI Loop Kit is for a developer who uses Claude Code with a GitHub project and wants to review small pull requests.

Use it in a repository where only collaborators shape pieces. The gate accepts records only from owners, members and collaborators.

## Install

In Claude Code, run:

```text
/plugin marketplace add gwpicard/ai-loop-kit
/plugin install ai-loop-kit@ai-loop-kit
/ai-loop-kit:setup
```

### What you need

- `git` and `gh` signed in to GitHub
- Python 3.9 or later
- A GitHub repository with one commit on `main`, and permission to push to it
- A Claude Code sign-in

## Your first 15 minutes

1. Run `/ai-loop-kit:setup` in your project.
2. Ask Claude to shape one small idea with `/ai-loop-kit:shape <idea>`.
3. Run `/ai-loop-kit:run` to build every ready piece in turn.
4. Read each pull request and merge it if it meets the contract.

For example, ask for `tally --top 2 words.txt` to print `b 3` and then `a 2`. The pull request shows the changed files, test results, risks and why the builder made the change. The contract can also say that output without `--top` must stay the same.

## Commands

- `/ai-loop-kit:setup` asks how to prepare and test a fresh copy of the project, and which files agents must not change. It writes the loop settings on a branch and opens a pull request for you to merge. Run it once per project, then again when you want to change settings.
- `/ai-loop-kit:shape <idea>` asks questions, splits the work when needed, writes the task and contract for you to approve, gets a test written for it, then makes the piece ready.
- `/ai-loop-kit:run` builds every ready piece in turn, with up to three tries and two reviews per piece. It opens a pull request for each piece and pauses when three pull requests wait for you.

### Things you can ask Claude during a run

- “Stop the run after the current try.”
- “Show the report of why pieces came back.”
- “Reject this pull request with this reason: …”
- “Drop this piece.”

To build with nobody watching, ask Claude: "Start a walk-away run." It first proves the sandbox works, then builds every ready piece and leaves a summary for the morning. Walk-away is a preview.

## Previews in 1.1

These are new in 1.1. They pass the automated tests but have not yet been tested on a real project.

- **Walk-away runs:** build every ready piece while you are away. A run refuses to start unless a probe proves the sandbox blocks writes outside the build folder, reads of your secrets and outside network calls.
- **Researcher:** looks up outside facts while shaping, and records each source with the date it was read.
- **Goal pieces:** the test is a measurement, such as speed, that must reach a target.
- **Gauntlet archive:** the failed critic preview and its tests are kept on `preview/gauntlet`. The shipped kit refuses gauntlet specs.
- **Codex backend:** with `Agent: codex` in the loop settings, Codex does the building, reviewing and judging instead of Claude.

## What you approve

You approve the task, including its intent, what is out of scope and its contract. You also approve the merge. A script runs the checks between those decisions.

## Words you will see

- **Piece:** a GitHub issue that describes one change.
- **Gate:** the script that checks work and moves a piece through its steps.
- **Judge:** tests that check whether the contract's results hold.
- **Contract:** the numbered results that a change must meet.
- **Keep check:** the project's full test command, which must still pass.
- **Prepare command:** the command that makes a fresh project copy ready for checks or a build.
- **Guard:** a hook that blocks some forbidden commands. It is not a sandbox.

## Limits

The fail-on-main check recognises failing assertions in pytest and unittest output, and TAP-style `not ok` lines. CI tests on Linux and macOS with Python 3.9 and 3.12. Attended runs have no sandbox, so stay nearby while they run. The guard blocks some commands but does not isolate the builder.

Claude walk-away runs need Claude Code 2.1.285 or later. A walk-away run keeps a Mac awake with `caffeinate`. Walk-away is a preview. Weak tests can let weak code pass, so read the task and pull request. Mutation testing is experimental and needs mutmut 3.8 or later with tests that call changed code in-process. Docker and team use have not been tested.

## More to read

- [How it works, and why](docs/DESIGN.md)
- [Upgrade from 1.0 or 1.1 to 1.2](docs/UPGRADE-1.2.md)
- [Changelog](CHANGELOG.md)
- [MIT licence](LICENSE)
