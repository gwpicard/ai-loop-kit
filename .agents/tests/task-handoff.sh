#!/usr/bin/env sh
# task-handoff.sh: guard the boundary between the session that runs the build
# loop and the fresh builder it starts for each attempt.
#
# Every attempt of the build loop is a fresh builder given a bounded brief and
# the note of the attempt before, never the conversation that came before it.
# Where the coding agent cannot start one, the run stops where it can resume and
# says so. Subprocess stubs check the written routing and the saved records;
# they cannot measure whether a model lost its context.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"
HANDOFF="$ROOT/.agents/skills/section-builder/references/task-handoff.md"
rs_init "Task handoff checks"
rs_rule "every attempt of the build loop uses it" 'use this reference for every attempt of the build loop'
rs_rule "the attempt carries the previous note and nothing of its conversation" 'the previous attempt.s note and nothing of its conversation'
rs_rule "the brief names the result file the run script reads" 'the result file the start request names'
rs_rule "no fresh builder means a resumable stop with the sentence" 'open a new session and paste `/implement` to resume this run'
rs_rule "fresh means no inherited conversation" 'start a new builder without inherited conversation or a prior task.s agent id'
rs_rule "only exposed writable tools qualify" 'confirm the exposed delegation tool can start fresh and permits edits and project commands'
rs_rule "supported reset is evidenced" 'a reset/resume route qualifies only when its exposed contract supports autonomous fresh re-entry from saved records'
rs_rule "unsupported stops resumably" 'leave waiting pieces waiting, record the limit and stop at a resumable boundary'
rs_rule "no false forgetting" 'compaction and an instruction to forget do not establish a fresh context'
rs_rule "current requirements" 'read the current issue body and latest comments before preparing the brief'
rs_rule "exact checked base" 'identify the branch and exact checked baseline commit'
rs_rule "bounded sources" 'pass relevant record pointers and saved artifact paths, never earlier transcripts'
rs_rule "one writer" 'only the coordinator writes authoritative run state, progress and the live page'
rs_rule "bounded authority" 'builders never claim, push, review, open pull requests or merge'
rs_rule "saved lookup" 'later builders read earlier artifacts from those saved sources'
rs_rule "bounded return" 'return a bounded result with commit ids, check commands and exits, flags, unseen cases and evidence or failure paths'
rs_rule "stale result rejected" 'the result echoes it and the coordinator rejects a result from another handoff'
rs_rule "resource ownership" 'record the browser identity, serving computer, owner, server working directory and port'
rs_rule "explicit transfer" 'a transfer requires the previous owner.s release and the new owner.s acknowledgement'
rs_rule "locality still applies" 'ownership never proves browser locality'
rs_rule "interrupted writer" 'a missing report counts as a failed attempt only after the builder is known to have ended'
rs_rule "resume recovery" 'resume through the existing checked-baseline recovery rules before another builder starts'
rs_guard "$HANDOFF" "task-handoff.md"
rs_require_load_bearing "section-builder loads handoff" "$ROOT/.agents/skills/section-builder/SKILL.md" 'load `references/task-handoff\.md`'
rs_require_load_bearing "compatibility points to installed evidence" "$ROOT/docs/COMPATIBILITY.md" '## task context capabilities'
rs_require_load_bearing "handoff loads installed evidence" "$HANDOFF" 'load \[task context capabilities\]\(task-context-capabilities\.md\)'
rs_require_load_bearing "compatibility links to owning reference" "$ROOT/docs/COMPATIBILITY.md" 'section-builder/references/task-context-capabilities\.md'
COMPAT="$ROOT/.agents/skills/section-builder/references/task-context-capabilities.md"
rs_require_load_bearing "Claude non-fork route" "$COMPAT" 'non-fork general-purpose subagents'
rs_require_load_bearing "Codex fresh-input condition" "$COMPAT" 'separate threads alone do not prove fresh input'
rs_require_load_bearing "Cursor clean input" "$COMPAT" 'start without prior conversation history'
rs_require_load_bearing "Gemini writable generalist" "$COMPAT" 'the generalist.*runs action-oriented work in an isolated conversation'
rs_require_load_bearing "unknown clients unavailable" "$COMPAT" 'no fresh-builder or autonomous reset route is established here'
rs_require_load_bearing "no universal reset" "$COMPAT" 'no universal reset operation is established by the sources above'
rs_require_load_bearing "grades unchanged by docs" "$COMPAT" 'not a measured kit run or a higher grade'
rs_done
python3 "$ROOT/.agents/tests/fixtures/task-handoff-stubs.py" "$HANDOFF"
