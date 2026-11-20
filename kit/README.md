# AI Loop Kit: reference

The full reference for the plugin in this folder. The root `README.md` is the
short guide and `docs/DESIGN.md` explains why the kit works this way.

A continuous factory for building software with Claude Code while you are
away. You shape and approve work with Claude. A loop on your computer builds
each approved issue, has a second session review it and merges it into a
loop branch. You merge that branch into your default branch yourself.

The loop never asks for input. It parks an issue only for a decision that
`PLAN.md` reserves for a person.

## Install

You need `git`, `gh` signed in to GitHub, Claude Code and `python3`
(the kit's tests run on 3.13 in CI). Add this repository as a plugin
marketplace in Claude Code, then install the `ai-loop-kit` plugin from it:

    /plugin marketplace add gwpicard/ai-loop-kit
    /plugin install ai-loop-kit@ai-loop-kit

After an update of the plugin, restart Claude Code: a session keeps the
version it started with. The kit refuses to run when the running version is
older than the one the project was set up with (recorded in
`.loop/kit-version`), and says so.

`<plugin>` below is the installed plugin folder (holding `bin/`).

## Set up a project

Put this in the project's `AGENTS.md`:

    ## Loop
    Test command: <the command that runs your tests>

Optional keys in the same section: `Loop branch` (default `loop/main`),
`Builder`, `Test writer`, `Reviewer` and `Pass` (each `<agent> <model>`,
default `claude sonnet`; the agent is `claude` or `codex`), `Protected paths`,
`Idle hours` (default 12) and `Max rounds` (default 3), `Session minutes`
(default 45, the wall-clock limit of one Claude session; raise it when one
Test command run is slow), `Test files command`, `Prepare command`,
`Check command`, `Smoke command` and `Parallel` (default 1).
`Codex writable roots` lists further folders, comma-separated
like `Protected paths`, that a Codex session may write to, in addition to the
worktree, the git folder and the temp and cache folders; a leading `~` is
expanded and a folder that does not exist is left out. Use it for a build
tool's cache, such as `~/Library/Caches/org.swift.swiftpm` for SwiftPM. The
older `Builder model: <m>` line still sets the builder and test writer to
`claude <m>`, and `Reviewer model: <m>` the reviewer and the pass, unless the new line for that role is set.

Codex is an agent for any role, such as `Builder: codex gpt-6`. A Codex session
runs under the same rules as a Claude one: the guard and the stop check are
passed to it as hooks, and the guard refuses a command it cannot parse. Setup
and the loop's start check the installed Codex for each role set to `codex`:
the `codex` command, its hooks feature and the flags the kit passes. When one
is missing they refuse and name it, and nothing runs Codex without the guard.
On a Codex usage limit the session waits for the reset time in the reply (30
minutes without one) and resumes; there is no fallback agent.

`Test files command` is the fast path: it runs only some test files, with
`{files}` replaced by their paths (for example `pytest {files}`). Without it,
the Test command stands in. `Prepare command` installs what a fresh checkout
needs (for example `npm ci`); the loop runs it once in each worktree and in
every fresh checkout, before any test run, so the Test command need not
embed it.

`Check command` is the project's guardrails (lint baseline, size budgets,
architecture tests). It runs after every Test command run, and a failure
counts like a test failure. `Smoke command` uses the real built artefact,
such as the CLI on real input; only the end-of-loop pass runs it. Setup
reports those that are set; none is required.

`Parallel: N` lets the loop run up to N builds at once. The default, 1,
builds one issue at a time inside the loop process. With more, each build is a
separate process in its own worktree, so a crash or a hang in one cannot stop
the loop or the others.

The loop starts a build only for a `ready`, trusted issue whose dependencies
are closed, labels it `building` first, and starts another only while the
machine has headroom: load average below the CPU count and, on macOS, normal
memory pressure. It says why when it waits. Every session and test command
also waits, on macOS, while memory pressure is above normal.

Before a build or a test command starts, the loop checks free space on the
project volume and in the temp folder. With less than 2 GB free, it prints a
line, records a `disk-wait` event and checks again every minute. A failure
reporting "No space left on device" waits without using a crash attempt.

Merges into the loop branch queue behind one lock (`.loop/merge.lock`): an
issue catches up with the loop branch, then merges, and a branch that
conflicts goes back to its builder. The board lists every running build with
its step and elapsed minutes in that step, or says when the drain or pass is
running. A stop request starts no new build and lets running builds finish
their issue. Each build process writes its log to
`.loop/logs/build-<issue>.log`. Lines in these logs and `loop.out` start with a
local timestamp (`YYYY-MM-DD HH:MM:SS`).

`.loop/events.jsonl` records step starts and ends, durations in whole seconds,
session agents and models, merges, parks, crashes, drains, passes and stop or
exit reasons. Refusals carry stable rule ids, such as `test-lock`. Every record
names the running kit version and the project folder’s base name.

`<plugin>/bin/loop status` reads only `.loop/` and checks local pids. It shows
current activity, merges, parks, crashes, rule counts, stage times, agents and
models from the last 12 hours, without GitHub or a session. `--since` accepts
`YYYY-MM-DD HH:MM`, `HH:MM` (today), or a duration such as `4h` or `90m`.
Stage totals and medians use steps completed in the window; a merged issue's
total minutes and review rounds use its full recorded history.

A park that names exactly one test path and asks whether to change it needs
only a reply of "yes" from a collaborator: the loop adds that path to the
issue's `## Paths the builder may change` and requeues it. A reply that does
not clearly agree, or the loop's own comment, grants nothing. The reviewer may
write scratch files in the system temp folder, never inside the project.

## The fast path

With a Test files command set, the full suite runs once per issue, at merge,
in `merge.py`'s fresh checkout of the reviewed commit. Path checks and the
test lock run first, so a refusal costs no test run.

The tests are proven to fail with the Test files command, by assertion, on
the locked files only. The builder runs the Test files command while it works.
The Stop hook runs the locked tests and the test files changed since the
issue started, then the Check command. It records which tests ran. After the
builder or a fix pass, the loop reuses that result if it was for the head
commit, and otherwise runs the same targeted set in a fresh checkout. Without
a Test files command, these steps use the full Test command.

The reviewer is given that result and runs only targeted checks. With a Test
files command set, the guard refuses the full Test command in builder and
reviewer sessions. There is no per-issue simplify step: the end-of-loop pass
simplifies the whole batch once.

## Set up with the script

Ask Claude to set up the loop (the setup skill writes the `## Loop` section
with you), or run `python3 <plugin>/scripts/setup.py` from the project root.
It first moves the runtime files of kit 1.x (into `.loop/v1/`) and of kit
2.0.0 (the `.lite/` folder) into `.loop/`, then creates the labels, the loop
branch, a pinned `Factory` issue, a `.loop/` line in `.gitignore` (commit it
yourself) and runs your Test command on a fresh copy of the loop branch.
Running it again is safe.

## Shape

Use the shape skill in any session, at any time. It turns inbox issues or an
idea into issues with acceptance criteria and dependencies, asks one batch
of questions, records decisions in `PLAN.md` and clears person-only
prerequisites first. On your single yes it labels the issues `ready`.

## Run

Use the loop skill, or run from the project root
`mkdir -p .loop && nohup <plugin>/bin/loop run > .loop/loop.out 2>&1 &`.
`<plugin>/bin/loop stop` stops it; so does the idle limit.

The pinned `Factory` issue is the board, in three sections: `Building now`;
`Needs you`, with parked issues, unbuilt dependencies, the open pull request
into the default branch and a conflict; and `Progress`, one line for each
open milestone that has an open `ready`, `building` or `needs-user` issue, with its closed and
total issue counts and a link to its milestone page. Read the full
progress on GitHub's milestones page. To answer a parked issue, reply on it;
the loop queues it again and gives your reply to the next build.
The next check includes its date. When ready issues are waiting and nothing
is building, `Why idle` names parked dependencies or a load or memory deferral.

## What each issue gets

- **Tests first.** A test writer commits tests from the acceptance criteria
  before any code. They must fail by assertion at the base commit, run with the
  Test files command on the locked files only; if they pass or fail on a
  syntax error, the writer is asked once to fix them, then the issue is parked.
- **Stop hooks.** The builder cannot end a session while the Test or Check
  command fails (three blocks at most); the test writer cannot end one
  without a new test file (two at most).
- **Build note.** After the merge, the issue and the pull request get a
  `## Built` note: what changed and why, deviations, the merge and files.
- **Merge conflicts.** A reused issue branch that conflicts with the loop
  branch is left mid-merge; the builder resolves it first, else the issue parks.
- **Follow-ups.** Non-blocking work the reviewer names becomes an `inbox` issue.
- **Lessons and failing tests.** Sessions append traps to `## Lessons`. A
  `## Failing test` section is committed as given by the test writer.

## The end-of-loop pass

When the drain finds merges it has not examined and the Test and Check
commands pass on the loop branch, it runs one pass before it opens or
refreshes the pull request. Each session is fresh, reads the loop branch in
a temporary worktree and is told not to edit tracked files; the guard hook
blocks this best-effort.

- Smoke: the `Smoke command`, if set.
- Drift: the batch diff against `PLAN.md` (decisions, budgets, duplication).
- Red team: one session per bullet under `## Surfaces` in `PLAN.md` (four at
  most). A finding counts only with a test file under `.loop/pass/` at the
  path where it belongs (such as `.loop/pass/tests/test_x.py`). The pass
  copies it there. After Prepare, it must fail the Test files command on that
  file (or the Test command when none is set) and pass the `Check command`
  (lint, format) with the file in place; a second session must confirm it.
- Rubric: readability, error handling, weak tests, fixed sleeps, dead code.
- Lessons and proposed guardrails.
- Simplify and reconcile: one session reads the batch's changed code and its
  build notes (deviations, workarounds, follow-ups, "not exercised") and
  files one `inbox` issue, `Simplify and reconcile, <date>, <sha>`, with
  concrete, behaviour-preserving changes. Nothing is edited by the pass. While
  one such issue is open, later passes add to it as a comment, as for
  `Pass findings`.

A confirmed defect becomes an `inbox` issue with a `## Failing test`
section. Shape and approve it like any other issue.

A finding that touches an open `inbox` or `needs-user` decision is held,
never queued. Every other finding, guardrail and lesson goes into one `inbox`
issue, a checkbox each; an open `Pass findings` issue gets only what it lacks,
as a comment. Lessons reach `PLAN.md` through an issue, never a direct commit.

The report goes into the pull request body. A pass that fails is noted there
and never blocks it. `.loop/pass.json` remembers it. After a pass without errors nothing reruns
until new merges arrive; after one with errors the next drain tries again.

## What the loop may leave behind

After each session the loop kills what is left in its process group and
logs it; a process that detaches itself can survive. If Docker answers, a new
container is removed only when its compose working directory or a bind mount
lies in the session's worktree. Everything else new (containers, networks,
volumes, images) is listed in the log and the build note, never removed.

At the end of each build, its sessions' `.loop/passed-<session>` and
`.loop/stop-<session>` files are removed. Each build has its own folder under
the system temp folder: its sessions and test commands receive that path as
`TMPDIR`, `TMP` and `TEMP`, and Codex can write there. The loop removes that
folder with the build's worktree, after checking it is the folder it created.
At exit the loop prunes worktrees, deletes logs older than 14 days and prints
the worktrees and issue branches left. Outside services are on the stops list.

## What is guaranteed by code

`merge.py` is the authoritative line.

- The loop merges issues only through `merge.py`; in the loop's sessions the hook refuses `gh` and `git merge`; branch protection on the default branch stops other routes. `merge.py`
  merges the reviewed commit, or a conflict-free merge of it with the current
  loop branch, tested in full on that exact commit (Prepare, Test, Check on a
  fresh checkout). Conflicts go back to the builder and a fresh review.
- It refuses a diff that touches a protected path, a workflow, a lockfile or
  package manifest, a settings file, or an existing test, unless the issue
  lists it in its `## Paths the builder may change` section; a path named
  elsewhere grants nothing. The test writer's tests are locked the same way.
- An issue is built only if a collaborator with write access added `ready`.
- The loop never merges into the default branch; it only opens a pull
  request. Branch protection is what stops any other path.

The guard hook is an early warning that matches the text of a command, so it
can be routed around. It is registered for the loop's own sessions (through
`--settings`) and wherever the plugin is enabled.

- Everywhere: it refuses pushes to the default branch, force pushes and
  recursive deletes.
- In the loop's sessions only: it also refuses `gh`, `git push`, `git merge`,
  branch switches and checkouts, and writes to the test writer's locked
  tests or to existing test files. For builders, an existing test is one at
  `LOOP_START`, the loop branch baseline at the start of the build, or at the
  merge base with the loop branch when `LOOP_START` is absent. Builders may
  edit tests they added on their issue branch; the writer's tests stay locked.
- Secrets are checked in content a session writes with its file tools, not in
  diffs or shell commands.

## What is guaranteed by instruction to the model

The briefs tell sessions never to ask, to record deviations and to park on
the stops list, and the reviewer to check every criterion with evidence.
Code does not enforce these.

## What is not guaranteed

- Pass sessions are told not to edit tracked files; the guard blocks it
  best-effort, on the text of commands, as it does everything else.
- The reviewer and the pass can miss a defect, and a red-team test proves
  only what it exercises.
- Behaviour that only a person can see, such as how an interaction feels,
  is unchecked unless the issue gives an agent a way to check it.
- Notifications are not built; watch the board and the milestones page. Branch protection is your
  job: setup recommends it only.

## Tests

Run `python3 kit/tests/run.py` from the repository root: it runs each test module in its own process, in parallel, and exits non-zero on any failure.

Pass test file paths or module names to run only those modules, for example
`python3 kit/tests/run.py kit/tests/test_flow.py` or
`python3 kit/tests/run.py kit.tests.test_flow`. `-h` or `--help` prints the usage;
an argument that names no test module exits non-zero.
