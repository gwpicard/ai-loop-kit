# Task context capabilities

For multi-piece runs, select the route from the current client's exposed tools,
permissions and version. These primary sources were checked on 2 October 2026;
they establish documented capability, not a measured kit run or a higher grade.
Installation through either plugin or shared skills does not provide a missing
harness tool.

| Harness route | Documented capability and runtime selection |
|---|---|
| Claude Code, shared skills or Claude plugin | [Non-fork general-purpose subagents](https://code.claude.com/docs/en/sub-agents) start with a fresh prompt. Select fresh-builder when the exposed tool permits build work; forks and resumed prior-task agents retain history. |
| Codex app, CLI or IDE, including an Agent Plugins client | [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) delegate through separate threads. Select fresh-builder only when the exposed tool explicitly allows no inherited conversation and permits edits and commands. Separate threads alone do not prove fresh input. |
| Cursor editor, CLI or cloud | [Subagents](https://cursor.com/docs/subagents) start without prior conversation history. Select fresh-builder when a writable task agent is exposed and permitted; a browser or search helper alone is insufficient. |
| Gemini CLI | [The generalist](https://geminicli.com/docs/core/subagents/) runs action-oriented work in an isolated conversation. Select fresh-builder when that tool is exposed with build permissions. A read-only investigator alone is insufficient. |
| GitHub Copilot and other clients | No fresh-builder or autonomous reset route is established here. Select unavailable unless the actual exposed contract supplies that evidence. |

On any route lacking fresh builders, select supported reset/resume only with
evidence that the client can autonomously re-enter from durable records in a
fresh context. No universal reset operation is established by the sources above.
Otherwise select unavailable and pause the run with saved progress and a
new-session `/implement` instruction. Compaction does not prove context eviction.
Existing unfinished runs can re-enter from their saved records; no automatic
migration or larger parallel group is required.

The [task handoff](task-handoff.md)
holds the brief, return and resource rules. One piece at a time remains the
default. Only the existing Claude Code policy offers parallel groups, and
independent review remains required where the build path calls for it. Offline
handoff stubs check written routing and durable records; they do not prove model
context eviction, client permissions or live browser continuity.
