# AI Loop Kit: reference

The full reference for the plugin in this folder. The root `README.md` is the
short guide and `docs/DESIGN.md` explains why the kit works this way.

A continuous factory for building software with Claude Code while you are
away. You shape and approve work with Claude. A loop on your computer builds
each approved issue, has a second session review it and merges it into a
loop branch. You merge that branch into your default branch yourself.

The loop never asks for input. It parks an issue for a product choice or a
decision reserved for a person by the kit's stops or `AGENTS.md`.

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

## Upgrading

Every release that changes what a project holds ships its migration in setup.
Run `python3 <plugin>/scripts/setup.py --dry-run` to preview every change without
writing files or GitHub data, or running preflight. Without the flag, setup
prints each change before applying it and logs the time, kit version and undo
instructions in `.loop/migrations.log`. Migrations are safe to run twice and
delete nothing.

## Set up a project

Turn off "Automatically delete head branches" in the repository's Settings,
General, Pull Requests. Otherwise, merging the loop's final pull request
deletes the loop branch.

Commit `loop.json` at the project root:

    {"Test command": "<the command that runs your tests>"}

Optional keys in the same JSON object: `Loop branch` (default `loop/main`),
`Builder`, `Test writer`, `Reviewer` and `Pass` (each `<agent> <model>`,
default `claude sonnet`; the agent is `claude` or `codex`), `Protected paths`,
`Idle hours` (default 12) and `Max rounds` (default 3), `Session minutes`
(default 45, the wall-clock limit of one Claude session; raise it when one
Test command run is slow), `Test minutes` (default 30, the Test command time
limit), `Test files command`, `Prepare command`,
`Check command`, `Smoke command`, `Full suite every` (default 4) and
`Parallel` (default 1).
`Protected paths`, `Codex writable roots` and `Red-team surfaces` are lists of strings.
Numeric settings take JSON numbers; `Full suite every` and `Test minutes`
take integers of at least one. `Codex network` takes a JSON boolean and defaults to false.
Other settings take strings. Unknown keys and values of the wrong type are
refused. Set `"Codex network": true` to enable network access in Codex
sessions when the `Prepare command` fetches packages.
`Codex writable roots` lists
further folders that a Codex session may write to, in addition to the
worktree, the git folder and the temp and cache folders; a leading `~` is
expanded and a folder that does not exist is left out. Use it for a build
tool's cache, such as `~/Library/Caches/org.swift.swiftpm` for SwiftPM.

`Red-team surfaces` names the parts of the project the end-of-loop pass
attacks, such as a command, an input format or a screen. The pass uses at
most four surfaces. With an empty list, it proposes surfaces in an inbox issue.

The optional, git-ignored `loop.local.json` accepts only `Parallel` and
`Idle hours`, which override `loop.json`. The running loop reloads both files
at the start of every cycle. If either cannot be read or validated, it keeps
the previous settings and logs the error without repeating an unchanged
error. Both settings files are protected paths by default; changing them in
a piece requires naming the file under `## Protected paths this issue may change`.

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

In a build tree, `<plugin>/bin/loop check` selects the issue's locked tests
and test files changed since the session's start commit, plus tests that
import changed modules, then runs the Check command. It prints one pass line,
or the failing command and at most 60 lines of its output. Without a Test
files command it runs the Test command. With
a Test files command and no selected files, it skips tests and still runs
the Check command.

Python selection parses imports, including relative and `from` imports.
It also follows imports of test support files and selected test modules.
For other languages or invalid
Python, it selects tests mentioning the changed file's base name without its
extension. When the selection exceeds 40 modules, session checks retain all
locked and changed test modules, then add importing tests in selection order
until the cap is reached. Locked and changed tests may exceed the cap. The
merge runs the full Test command when its selection exceeds the cap.

After `loop check` passes with a clean tree, the Stop hook reuses its result
at the same commit with matching selection inputs and settings. A new commit
or uncommitted changes require another run.

`Check command` is the project's guardrails (lint baseline, size budgets,
architecture tests). It runs after every Test command run, and a failure
counts like a test failure. `Smoke command` uses the real built artefact,
such as the CLI on real input; only the end-of-loop pass runs it. Setup
reports those that are set; none is required.

`Parallel: N` lets the loop run up to N builds at once. The default, 1,
builds one issue at a time. Each build is a separate process in its own
worktree, so a crash or a hang in one cannot stop the loop or the others.

The loop starts agent sessions at background priority so they favour
efficiency cores on macOS and keep the machine responsive. Every Claude and
Codex session, including the pass and summary, starts with `taskpolicy -b`
on macOS when available. Otherwise, the session process uses `os.nice(10)`.
Commands started by a session inherit its priority. The supervisor stays at
normal priority, so the Test, Check, Prepare and Smoke commands it schedules
run at normal priority. The full suite at merge and drain runs at normal
priority to avoid the slowdown from using efficiency cores alone.

`Test minutes` in `loop.json` sets the Test command time limit at merge,
drain and targeted checks. It defaults to 30 minutes and takes a whole number
of at least one. At merge and drain, a timeout refusal reports the limit,
elapsed time excluding pauses and up to 60 lines from the end of its output.
Prepare, Check and Smoke commands keep their 30-minute limits.

The loop starts a build only for a `ready`, trusted issue whose dependencies
are closed, labels it `building` first, and starts another only while the
machine has headroom: load average below the CPU count and, on macOS, memory
pressure below critical (level 4). It says why when it waits. With more than
one build running, sessions and test commands wait at critical pressure for
at most 10 minutes, then start anyway and log a line. A build running alone
never waits for memory. Memory waits happen before the merge lock is taken
and do not count against the build cap; each records a `memory-wait` event
with its level and seconds waited.

On a Mac, Spotlight indexes every new worktree, log and test repository the
loop creates, competing with builds for the processor. Add the folder that
holds your projects and `.loop-worktrees` (by default the parent folder of
the project) to System Settings, Spotlight, Search Privacy. Build temporary
files live in `loop-tmp/loop-build-*`. The `loop-tmp` folder sits beside the
project and `.loop-worktrees`, on the same volume. Without this exclusion,
you may see `mds_stores` and `mds` near the top of Activity Monitor and a high
load average, which also holds back a second build.

The loop passes each build's temporary folder as `TMPDIR`, `TMP`, `TEMP` and
`LOOP_TMPDIR` to sessions and the Test, Check, Prepare and Smoke commands,
then removes it after the build. The visible `loop-tmp` folder keeps the kit
from adding hidden components to temporary paths; keep the project's parent
path free of hidden components too. Build worktrees stay in `.loop-worktrees`.

Before a build or a test command starts, the loop checks free space on the
project volume and in the temp folder. With less than 2 GB free, it prints a
line, records a `disk-wait` event and checks again every minute. A failure
reporting "No space left on device" waits without using a crash attempt.

Merges into the loop branch queue behind one lock (`.loop/merge.lock`): an
issue catches up with the loop branch, then merges, and a branch that
conflicts goes back to its builder. The board lists every running build with
its step and elapsed minutes in that step, or says when the drain or pass is
running. A stop request starts no new build and lets running builds finish
their issue. `loop stop --now` ends running builds, their agent sessions and
test commands at once and returns their issues to `ready`, without counting
a crash or using an attempt. Each build process writes its log to
`.loop/logs/build-<issue>.log`. Lines in these logs and `loop.out` start with a
local timestamp (`YYYY-MM-DD HH:MM:SS`).

`.loop/events.jsonl` records step starts and ends, durations in whole seconds,
session agents and models, merges, parks, crashes, drains, passes and stop or
exit reasons. Refusals carry stable rule ids, such as `test-lock`. Every record
names the running kit version and the project folder’s base name.
Step starts and ends, merges and parks also record `load` (the one-minute load
average) and `pressure` (the macOS memory-pressure level, or null elsewhere
or when the reading fails).

`<plugin>/bin/loop status` reads `.loop/` and checks local pids. It shows
current activity, merges, parks, crashes, rule counts, stage times, agents and
models from the last 12 hours, without a session. Its `Open parks` section
reads every open `needs-user` issue and its latest park question from GitHub,
regardless of the time window. If GitHub cannot be read, it reports that the
section is unavailable. `--json` prints only the local throughput report.
`--since` accepts
`YYYY-MM-DD HH:MM`, `HH:MM` (today), or a duration such as `4h` or `90m`.
Stage totals and medians use steps completed in the window; a merged issue's
total minutes and review rounds use its full recorded history.

`<plugin>/bin/loop report` summarises issues merged on the loop branch since
`origin/<default>`, using local git refs, `.loop/` events and one read-only
GitHub call per issue for its build note. It lists changed folders, test
counts, risk flags (including every test support file changed), reasons,
deviations and build timings without a session or GitHub writes. The drain
includes the same text under `What changed` near
the top of the final pull request body.

When a park's permission question ends with `?` and names test paths, a
collaborator can reply "yes", whatever verb the question uses. The loop adds
each path the stops list permits to the issue's
`## Protected paths this issue may change` and requeues it.
Paths named only in the recommendation and protected paths are never granted
by a reply. A reply that does not clearly agree or contains a doubt word,
or the loop's own comment, grants nothing. The reviewer may
write scratch files in the system temp folder, never inside the project.

## The fast path

With a Test files command set, `Full suite every` sets the merge interval
for the full Test command: four by default, or one to run it at every merge.
Other merges run the Test files command on the locked tests and test modules
changed against the loop branch, plus the importers and base-name matches
described above, then the Check command. When the selection exceeds 40 modules,
the merge runs the full Test command.

The merge's log line and build note list extra modules with the import or
base-name mention that selected each one. Each run uses
`merge.py`'s fresh checkout of the reviewed commit. Path checks and the test
lock run first, so a refusal costs no test run.

The merge count comes from `.loop/events.jsonl`, where each merge records
`full_suite`, and survives restarts. A successful full merge run or drain
resets it. If a due full Test command fails, the gate runs it once on the
loop branch head. If that also fails, the issue parks with an explanation
that the failure was already on the loop branch; otherwise it returns to
the builder. Without a Test files command containing `{files}`, every merge
runs the full suite. A merge also runs the full suite when the issue has no
posted list of locked test modules, since changed files alone may omit tests
that cover the issue.
The drain always runs the full suite before the pass and final pull request.
A regression outside the targeted tests may be found only at the next full run.

The tests are proven to fail with the Test files command, by assertion, on
the locked files only. The builder runs the Test files command while it works.
The Stop hook runs the same selection as `loop check`, then the Check
command. It records which tests ran. After the
builder or a fix pass, the loop reuses that result if it was for the head
commit, and otherwise runs the same targeted set in a fresh checkout. Without
a Test files command, these steps use the full Test command.

The reviewer is given that result and runs only targeted checks. With a Test
files command set, the guard refuses the full Test command in builder,
test-writer, reviewer and pass sessions. There is no per-issue simplify step:
the end-of-loop pass simplifies the whole batch once.

## Set up with the script

Ask Claude to set up the loop (the setup skill writes `loop.json`
with you), or run `python3 <plugin>/scripts/setup.py` from the project root.
Setup refuses legacy kit 1.x and `.lite/` layouts with upgrade advice.
Otherwise it creates the labels, the loop branch, a pinned `Factory` issue,
a `.loop/` line in `.gitignore` (commit it
yourself) and runs your Test command on a fresh copy of the loop branch.
Setup also migrates an existing `## Loop` section from `AGENTS.md` into
`loop.json`, removes the section and ignores `loop.local.json`. It records
each change and its undo in `.loop/migrations.log`; `--dry-run` previews
the changes without applying them. Running it again is safe.

Setup warns when the root standing instructions exceed 1,500 words,
excluding the standalone import of `AGENTS.md` in `CLAUDE.md`.

Setup also renames the protected-paths section in open issues. It saves each
original body under `.loop/migrations/` and records the rename and an undo
command in `.loop/migrations.log`. A dry run lists the issues without editing
them.

When the project has a `PLAN.md`, setup files one inbox issue titled
"Find a home for the contents of PLAN.md". It preserves each non-empty
section and proposes where it belongs, leaves the file unchanged and
records the issue in `.loop/migrations.log`. A dry run prints the issue
without filing it. The kit uses the issue and `AGENTS.md` for instructions;
it does not read the old plan outside this migration.

## Shape

Use the shape skill in any session, at any time. It turns inbox issues or an
idea into issues with acceptance criteria and dependencies, asks one batch
of questions, records decisions in the issues and clears person-only
prerequisites first. On your single yes it labels the issues `ready`.

## Run

Use the loop skill, or run from the project root
`mkdir -p .loop && nohup <plugin>/bin/loop run > .loop/loop.out 2>&1 &`.
`<plugin>/bin/loop stop` starts nothing new and ends after running builds
finish their issue. Use `<plugin>/bin/loop stop --now` to end them at once
and return their issues to `ready`. The idle limit also stops the loop.

When every `ready` issue waits, directly or through other ready issues, on an
open `needs-user` dependency and no build is running, the loop keeps reading
replies before draining. It waits
until 60 minutes after the latest park comment on those dependencies, then
runs the usual drain. This wait applies in the cycle that collects the parked
build's result. With nothing `ready` or parked, it drains as usual.

The pinned `Factory` issue is the board, in three sections: `Building now`;
`Needs you`, with parked issues, unbuilt dependencies, the open pull request
into the default branch and a conflict; and `Progress`, one line for each
open milestone that has an open `ready`, `building` or `needs-user` issue, with its closed and
total issue counts and a link to its milestone page. Read the full
progress on GitHub's milestones page. To answer a parked issue, reply on it;
the loop queues it again and gives your reply to the next build.
The next check includes its date. When ready issues are waiting and nothing
is building, `Why idle` names parked dependencies and the minutes until the
drain, or a load or memory deferral.

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
- **Restart history.** A restarted builder reads earlier review rounds and
  build notes from `.loop/history-<issue>.md` in the project folder, outside
  the worktree. The file is removed after the merge. Prompts carry only
  replies to the last park; reviewers get only BUILT and DEVIATIONS from
  the builder's report.
- **Merge conflicts.** A reused issue branch that conflicts with the loop
  branch is left mid-merge; the builder resolves it first, else the issue parks.
- **Follow-ups.** At most two verified non-blocking findings become `inbox`
  issues per issue. Unverified findings and titles under four words are dropped.
- **Lessons and failing tests.** Sessions append traps to `## Lessons`. A
  `## Failing test` section is committed as given by the test writer.

## The end-of-loop pass

When the drain finds merges it has not examined and the Test and Check
commands pass on the loop branch, it runs one pass before it opens or
refreshes the pull request. Each session is fresh, reads the loop branch in
a temporary worktree and is told not to edit tracked files; the guard hook
blocks this best-effort.

- Smoke: the `Smoke command`, if set.
- Drift: the batch diff against `AGENTS.md` (rules, budgets, duplication).
- Red team: one session per entry in `Red-team surfaces` in `loop.json` (four at
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
never queued. Every other finding and guardrail goes into one `inbox`
issue, a checkbox each; an open `Pass findings` issue gets only what it lacks,
as a comment. Each lesson becomes a separate inbox issue naming the check or
`AGENTS.md` line that would prevent it. No lesson is appended to a project file.

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
  package manifest, a settings file, or an existing test module, unless the issue
  lists it in its `## Protected paths this issue may change` section; a path named
  elsewhere grants nothing. The guard refuses a builder's write or edit to
  a path on the stops list at once, unless the issue lists it, and tells the
  builder to park if the change is needed. `setup.py` is a manifest only at
  the repository root or beside `pyproject.toml` or `setup.cfg`.

  The test writer's tests are locked the same way.
  The test lock covers test modules, recognised by their names, including
  `conftest.py`. Other files under test folders, such as helpers, runners,
  fakes and fixtures, are test support files. They are not locked or passed
  to the Test files command; changes to them appear in the report's risk flags.
- An issue is built only if a collaborator with write access added `ready`.
- The loop never merges into the default branch; it only opens a pull
  request. Branch protection is what stops any other path.

The guard hook is an early warning that matches the text of a command, so it
can be routed around. It is registered for the loop's own sessions (through
`--settings`) and wherever the plugin is enabled.
For `gh` and the loop's git restrictions, it ignores quoted text and heredoc
bodies. If the command invokes `sh`, `bash`, `zsh`, `dash`, `eval` or `xargs`,
directly or through `env`, it checks the whole command, including quoted and
piped input.

- Everywhere: it refuses pushes to the default branch, force pushes and
  recursive deletes.
- In the loop's sessions only: it also refuses `gh`, `git push`, `git merge`,
  branch switches and checkouts, and writes to the test writer's locked
  test modules or to existing test modules. For builders, an existing test is one at
  `LOOP_START`, the loop branch baseline at the start of the build, or at the
  merge base with the loop branch when `LOOP_START` is absent. Builders may
  edit tests they added on their issue branch; the writer's tests stay locked.
- Secrets are checked in content a session writes with its file tools, not in
  diffs or shell commands.

## What is guaranteed by instruction to the model

The shared preamble tells sessions never to ask and to park on the stops
list. Role briefs require recorded deviations and a review of every criterion
with evidence. Code does not enforce these.

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
