# One task in a fresh builder

Use this reference for every attempt of the build loop, as the
[build loop](build-loop.md) runs it, and for each piece a multi-piece run hands
to a builder. The coordinator is the session that ran the run script: it keeps
the agreed plan and resource ownership, and the builder carries one attempt's
build detail. Each attempt carries the previous attempt's note and nothing of
its conversation.
Load [task context capabilities](task-context-capabilities.md) for the owned
capability evidence and route conditions.

## Select the route

Confirm the exposed delegation tool can start fresh and permits edits and
project commands. Start a new builder without inherited conversation or a prior
task's agent id. A read-only investigator is insufficient. Use the installed
tool's actual schema and permissions; do not copy another harness's tool syntax.
Record the route, tool/version where available, evidence and any limit in the
ignored run folder. Recheck availability on resume. A changed route never
increases `at_once` or grants new approval.

A reset/resume route qualifies only when its exposed contract supports autonomous
fresh re-entry from saved records. Record the supported operation and its evidence
before using it. A human typing a client command does not establish autonomous
support. Compaction and an instruction to forget do not establish a fresh context.
When neither route is supported, leave waiting pieces waiting, record the limit
and stop at a resumable boundary. Say: "This coding agent cannot start the next
piece fresh by itself. Open a new session and paste `/implement` to resume this
run." Record the run folder with that instruction so a later session can find it.
This pause leaves the run unfinished; it does not invoke ordinary end-of-run
skipping. Finish preservation and baseline verification first where owed.

## Prepare the brief

The coordinator makes the existing claim and prepares the branch or worktree.
Read the current issue body and latest comments before preparing the brief.
Identify the branch and exact checked baseline commit, including the successful
parts of a shared parent. Pass relevant record pointers and saved artifact paths,
never earlier transcripts. Include the accepted task requirements or their saved
snapshot, blockers, scope, build path, evidence and save route, attempts already
used and the coordinator's identity and run folder. No secret values belong here.

In the build loop the run script, the `implement` skill's `scripts/run.py`,
writes the brief and the start request, and the builder writes its status to
the result file the start request names.

Use these fields as the brief's checklist. Values below are disposable examples;
absolute directories and refs must describe the actual task. `requirements` holds
the current requirements snapshot; `records` names only relevant sources. The
coordinator saves the brief privately before dispatch so interruption loses none
of it. Give each dispatch a new `handoff` identity; the result echoes it and the
coordinator rejects a result from another handoff. A missing field is completed
before a builder starts.

```json
{
  "task": "notes-list",
  "handoff": "notes-list-attempt-1",
  "requirements": "task/requirements.md",
  "baseline": {"branch": "notes-list", "commit": "checked-ref", "directory": "task"},
  "records": ["AGENTS.md", "masterplan.md", "docs/notes.md"],
  "artifacts": ["earlier/result.md"],
  "run": {"directory": "run", "coordinator": "coordinator", "attempts": 0},
  "authorisation": {"scope": ["task"], "steps": "start, checks, build, walk-through, local commit"},
  "resources": {
    "browser": {"identity": "local-browser", "computer": "serving-computer", "owner": "coordinator"},
    "server": {"owner": "coordinator", "directory": "task", "port": 4012}
  },
  "result": "task/result.json",
  "loop": {"module": "build", "attempt": 1, "attempts_allowed": 3, "budget_minutes": 120,
           "budget": "Only time counts against the budget; usage is not counted."}
}
```

Only the coordinator writes authoritative run state, progress and the live page.
Builders never claim, push, review, open pull requests or merge. They load the
project's standing instructions and this skill, check their assigned directory,
branch and baseline against the brief, and perform only the assigned build steps.
A mismatch stops edits and returns evidence. Later builders read earlier artifacts
from those saved sources. Missing or changed prerequisites return to the
coordinator rather than being filled from memory.

## Keep shared resources owned

Record the browser identity, serving computer, owner, server working directory
and port. For each resource say retained by the coordinator, assigned exclusively
to this builder, or unavailable. A transfer requires the previous owner's release
and the new owner's acknowledgement, saved by the coordinator before use. An
unacknowledged transfer permits no browser action or server restart. Another
builder's active resource stays theirs; report the unavailable observation.

Ownership never proves browser locality. Apply section-builder's walk-through
rules again, using exposed browser evidence that identifies the serving computer.
A coordinator may keep the browser and perform the required observations on the
builder's saved commit while the builder reports what it could not see. Confirm
the server process, directory, port and served version before reusing it; do not
start a competing server, stop another owner's process or attach to an unrelated
page. At completion record retained resources or an acknowledged return. Resource
ownership does not change the existing server lifetime rules.

## Return and recover

Return a bounded result with commit ids, check commands and exits, flags, unseen
cases and evidence or failure paths. Save longer output and the requirements
used in the ignored task folder, and return pointers. Do not return the whole
transcript. The coordinator reads back the saved result and Git state before
updating progress or starting independent review. A builder never earns merge
consent or satisfies a review of its own work.

A missing report counts as a failed attempt only after the builder is known to
have ended. Contact loss alone does not release its checkout or resources. Keep
attempt counts and unfinished work. Resume through the existing checked-baseline
recovery rules before another builder starts, as the `implement` skill's
`references/running-longer.md` says. On re-entry verify branch, result and resource
ownership from saved sources; an old agent id or stale checked result proves
nothing. Resolve any still-active builder before assigning another writer.
