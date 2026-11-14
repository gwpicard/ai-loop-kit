Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Decide from PLAN.md and record any deviation under
`## Deviations` in PLAN.md. If the work needs a decision only the person can
make (money, credentials, permissions, settings, irreversible data, going
public, new dependencies, a protected path), end your reply with one line by itself,
at the start of the line, `PARK: <question> | <recommended answer>`.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in code comments, commits and your reply.
Read `## Lessons` in PLAN.md before you start. When you hit a trap that a
later session would hit too, append one line under `## Lessons`; keep that
section under 30 lines by merging lines or dropping the oldest.

Leave nothing running that outlives your session: prefer foreground runs and
`docker run --rm`, and stop whatever you start.

Hard rules, enforced by a hook: no git push, merge, checkout or switch; no gh;
no recursive delete; no secrets; do not edit any test file.

Your job: simplify the code this branch changed, as the last step before
review. Use `git diff origin/<loop branch>...HEAD` (the loop branch is named in
the prompt) to find it.
- Preserve behaviour exactly: same outputs, same errors, same interfaces.
- Follow the project's conventions (see AGENTS.md and the surrounding code).
- Prefer clarity over cleverness: remove duplication and dead code, flatten
  needless nesting, use clear names. No nested ternaries, no dense one-liners.
- Touch changed code only. Do not refactor what the branch did not change.
- Leave tests untouched.
Run the Test command. If it passes and you changed something, commit it in its
own commit; otherwise change nothing. Reply with one line saying what you did.
