# AI Loop Kit: design

Version 3.0.0. This describes what the kit in `kit/` does, how it works and
why. Command details and settings are in `kit/README.md`; history lives in
the git tags and `CHANGELOG.md`.

## The goal

A continuous factory for building software while you are away. You shape
work into GitHub issues and approve it once. The loop builds, tests,
reviews and merges each approved issue into a loop branch. You review the
batch and merge its final pull request into the project's default branch.
Shaping can continue in another session while the loop runs.

Every session works towards a goal without asking you questions or waiting
for an answer. A failed test, review finding or transient error is work to
resolve. Sessions decide from the issue and standing rules, take the closest
approach that keeps those rules, and record deviations for your review.

The exception is a decision reserved for you: a product choice about
behaviour, appearance or what ships, money, credentials, access, settings,
irreversible data, going public, a new dependency or a protected path
without approval. The issue parks with a question and a recommended
answer; the loop continues with other eligible work. Shaping should clear
these prerequisites before approval, so walking away remains practical.

## The contract and settings

Each issue follows `kit/templates/issue.md`: a goal, acceptance criteria,
an oracle an agent can use to judge the result, dependencies and binding
decisions. Optional hands-on checks become unticked boxes in the final
pull request. They do not block the loop; you perform them before merging.
Enforceable rules belong in checks. Standing guidance that every agent
needs belongs in `AGENTS.md`.

The kit does not use `PLAN.md` as a runtime contract. Decisions belong in
issues; standing instructions belong in `AGENTS.md`. Setup preserves the
contents of an existing plan in an inbox issue for you to place, leaving the
file unchanged. Setup warns when the root standing instructions exceed
1,500 words, excluding the standalone import of `AGENTS.md` in `CLAUDE.md`.

The committed `loop.json` holds validated settings. Only `Test command` is
required. `Loop branch` defaults to `loop/main`; `Max rounds` to three;
`Session minutes` to 45. `Builder`, `Test writer`, `Reviewer` and `Pass`
select an agent and model per role, each defaulting to Claude Sonnet.
Each role can use Claude or Codex. The loop skill shows these choices before
each start.

The git-ignored `loop.local.json` may override only `Parallel` and
`Idle hours`, whose defaults are one build and 12 hours. The supervisor
reloads both settings files at each cycle. If either cannot be read or
validated, it retains the previous valid settings and logs the error,
without repeating an unchanged error. Each build keeps its validated
settings snapshot, so a later edit does not change its checks mid-build.

The issue section `## Protected paths this issue may change` grants
permission for named protected files, manifests, lockfiles, settings and
existing tests. Every other file is available to the builder. Both settings
files are protected by default. Setup renames the former permissions
heading in open issues and records backups and undo instructions.

## The queue and progress

GitHub holds the durable work state. Issues move through these labels:

| State | Meaning |
| --- | --- |
| inbox | An idea or report awaiting shaping |
| shaping | Decisions and acceptance criteria are being agreed |
| ready | Shaped and approved for the loop |
| building | Claimed by a build |
| needs-user | Parked on a decision reserved for you |
| closed | Merged into the loop branch |

The loop accepts only collaborators' ready labels, checked against the issue
timeline. Issue text is data, not authority. Dependencies determine which
issues can start. A collaborator's reply requeues a parked issue. A clear yes
without doubt words grants test paths named in a permission question ending
with `?`, subject to the stops list, whatever the verb. If a question about
changing tests names none, the `Recommended:` line must name exactly one;
the grant comment identifies its source. For test changes, agreement granting
nothing prompts a comment asking the collaborator to name paths.

One pinned Factory issue shows builds, stages, parked questions, blocked
dependencies, the final pull request, next poll and milestone progress.
The supervisor rewrites it from GitHub state; no dashboard server or
notifications are built.

The status command reports local activity, timings and recent events without
an agent session. Its open parks section reads current parked questions
from GitHub, regardless of the event window. The report command summarises merged
issues using git refs, local events and read-only GitHub calls for build
notes. The final pull request includes that report.

## One issue through the loop

`kit/scripts/loop.py` selects an eligible issue, claims it and creates an
isolated worktree. `kit/scripts/flow.py` coordinates fresh test-writer,
builder and reviewer sessions, with fixes returned to the builder. Each
issue ends merged or parked with a reason. Fresh sessions limit accumulated
context; build notes preserve what a restarted builder needs.

The test writer starts from the issue's acceptance criteria and writes
tests through the entry point a person or caller actually uses. The loop
proves they fail on the base before building. A meaningful assertion failure,
or a missing module or symbol that the issue introduces, counts; a broken
test command does not. Criteria already satisfied need no new test.

The builder implements the smallest change and commits it. The guard locks
the test writer's tests and existing tests. A permitted existing test path
can be changed, but a builder cannot silently weaken the tests judging its
work. New builder tests remain editable. The lock covers test modules,
including `conftest.py`; test support files stay editable and appear in the
report's risk flags.

A fresh reviewer reads the issue, standing rules, diff and latest test
result. It checks the acceptance criteria and follows the real entry point,
using renders or measurements where appropriate. A review verdict names
the exact head commit. Fixes receive another review, within the configured
round limit. Verified reviewer follow-ups may become inbox issues.

Before each review, the revert check examines builder-added or changed
test files outside the locked set when a Test files command is configured
and non-test files also changed. In a scratch checkout, it restores the
non-test files to the branch base and runs each selected test file. The
reviewer receives the files that pass without the implementation and any
unverified results. Such a passing test requires changes unless the recorded
deviations explain that it guards existing behaviour. This checks whether
the builder's tests actually depend on the change they claim to prove.

`kit/scripts/merge.py` checks the diff permissions, test lock and posted
review before merging. It tests the exact commit and requires the reviewed
head when merging the pull request. A conflict-free catch-up with the loop
branch is tested too; conflicts return to the builder. The merge lock
serialises this step across parallel builds. After a successful merge, the
loop posts the build note and closes the issue.

## Testing without repeated full runs

`Test files command` selects test files through its placeholder. Without
it, the Test command stands in. `Prepare command` runs once per worktree
and fresh checkout before testing. `Check command` supplies additional
guardrails; `Smoke command` exercises the real artefact during the batch
pass.

With a Test files command set, the guard refuses the full Test command in
all four roles: builder, reviewer, test writer and pass. The full suite is
reserved for merge and drain.
At merge, targeted tests and the Check command
run unless a full suite is due. `Full suite every` defaults to four merges;
setting it to one runs the full suite at every merge. Without a Test files
command containing `{files}`, every merge runs the full suite. A merge also
runs the full suite if the issue has no posted list of locked test modules.

Targeted selection also includes tests that import changed Python modules,
including test support files, and importers of any selected test module.
It parses imports without running project code. Other languages and invalid
Python use mentions of the changed file's base name without its extension.
When the selection exceeds 40 modules, the merge runs the full suite.
Session checks retain all locked and changed test modules, then add importing
tests in selection order until the cap is reached. Locked and changed tests
may exceed the cap. The merge log and build
note list extra modules and why each was selected.

Merge events record whether the full suite ran. The merge gate reads that
history after a restart and resets the count after a successful full merge
run or drain. When a merge Test command fails, the gate reruns the named
failing modules present on the loop branch head with the Test files command.
Without selectable modules or a Test files command, it runs the full Test
command there instead.

Failures isolated to the issue return to the builder with diagnostics, any
hung-test stack and, when modules can be selected, a targeted rerun command.
Shared failures are listed separately; if no new failure can be isolated,
the issue parks. Two merge test fix rounds are available apart from the review limit.
The drain always runs the full suite before the pass and final pull request.
A regression outside the targeted tests may reach the loop branch before
the next full run finds it.

The fails-first step runs the locked tests. `loop check` and the builder's
Stop hook run tests selected from locked files and changes since the session's
start commit, then the Check command. Failures block completion. A clean pass records the
commit and selection inputs in the build's temporary folder. Stop reuses it
at the same HEAD with a clean tree and matching inputs, and records it for
the session.

Flow reuses that record at the same HEAD or runs targeted checks in a fresh
checkout. Reviewers read Stop's result, running checks only to verify findings.
The pass validates candidate failing tests with targeted checks and the Check command.

`loop check`, the builder's Stop hook and flow's tests step limit the Test
files command to one third of `Session minutes`, with a ten-minute minimum.
A timeout warns that the command may be running more than the named files.
These checks reuse the timeout at that worktree and HEAD without running
commands; flow reports it in events, logs and review. Merge keeps its existing test policy.

## Boundaries and recovery

`kit/hooks/guard.py` refuses recognised recursive deletes, force pushes,
pushes to protected branch names and secret shapes in written content.
Loop sessions also cannot push, merge, switch branches or use GitHub's CLI.
Reviewers write scratch files only in the system temporary folder; pass
sessions write only in their runtime folder. These command checks are early warnings,
not a sandbox: merge-time diff checks and branch protection provide further
boundaries.

For git and GitHub CLI restrictions, the guard ignores ordinary quoted text
and heredoc bodies unless the command invokes `sh`, `bash`, `zsh`, `dash`,
`eval` or `xargs`. It also reads code passed to `python`, `python3`, `node`
and the shells by `-c`, `-e`, a heredoc or a here-string, including behind
`env` or `uv run`.
A builder's first write to an unapproved stop path is refused;
`setup.py` is a manifest only at the root or beside `pyproject.toml` or `setup.cfg`.

`kit/scripts/session.py` isolates sessions from personal plugins and MCP
servers. Codex receives the same guard and Stop checks as Claude, and its
guard refuses inputs it cannot parse. Setup and loop startup verify the
Codex hooks feature and required flags for configured Codex roles; missing
support prevents a run. Usage limits wait for reset without switching agent.

GitHub transient errors retry with back-off; rate limits wait for reset.
A crashed or timed-out build gets one retry, then parks. Permission refusals
park immediately with the refused path. Each build cleans up its worktree
and processes. An unregistered folder at the worktree path is renamed aside
rather than deleted.

`Parallel` controls concurrent builds. The first build can start regardless
of machine load; additional builds wait for CPU and, on macOS, memory
headroom. Memory waits apply only at critical pressure, and a lone build
never waits for memory.
Low disk space delays work rather than consuming a crash attempt. Each
build has its own temporary folder for sessions and test commands.

One lock permits one supervisor per repository. Runtime locks, logs,
events, session records and worker results live under `.loop/`. Events
record stages, durations, agents, models, refusals and exit reasons. Workers
report progress to the supervisor and have a time cap; a worker that dies
without a result follows the crash retry rule.

The pause command freezes the loop and its processes without discarding
work; resume continues them. Paused time does not consume the kit's build,
session or test timeouts. Stop prevents new builds and lets running builds
finish their issue. `loop stop --now` ends build process trees and returns
their issues to `ready` without consuming an attempt or counting a crash.
The loop reports why it exits.

## The batch and the person's review

When the queue drains, the loop runs the full suite on the loop branch and
opens or refreshes one final pull request into the default branch. When all
ready issues depend, directly or through other ready issues, on parked work,
it waits until 60 minutes after the latest park on those dependencies before
draining, including the cycle that collects a parked build's result. After
new merges, `kit/scripts/pass_.py` runs the batch pass: smoke, drift,
red-team checks with failing tests, rubric, lessons, and simplify and
reconcile. The pass reports findings rather than editing product code.
Confirmed defects become inbox issues with reproducing tests. One open
simplification issue collects later findings.

The final pull request records evidence, risk, deviations needing
confirmation and hands-on checks. You decide whether to merge it. The loop
then brings the default branch back into the loop branch and continues.
With no eligible work, it polls every two minutes until the idle limit or
a stop request. A batch ending is not a reason to end the factory.

## Setup and maintenance

`kit/skills/setup/SKILL.md` gathers settings;
`kit/scripts/setup.py` creates missing labels, the loop branch and the
Factory issue, ignores runtime files and runs preflight on a fresh checkout.
Setup previews migrations with its dry-run flag and records changes with
undo instructions. It refuses unsupported legacy layouts with upgrade
advice rather than guessing how to move their contents. It also refuses an
older running kit than the version recorded for the project.

`kit/skills/shape/SKILL.md` handles shaping and approval;
`kit/skills/loop/SKILL.md` starts and watches the loop. Role instructions
live in `kit/briefs/`. The Python implementation uses only the standard
library. Keep it small enough to read in one sitting: a rule in a brief is
preferable to code when judgement is sufficient, and redundant code and
guidance leave with the change that makes them redundant.

`python3 kit/tests/run.py` runs the kit tests, with file arguments selecting
modules. `sh tests/house-rules.sh` checks repository conventions;
`tests/run-all.sh` runs both. A release also needs an end-to-end smoke run
in an empty repository, building one small issue through the loop.
