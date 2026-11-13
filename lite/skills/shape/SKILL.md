---
name: shape
description: Turn inbox issues or a new idea into shaped, approved issues for the AI Loop Lite factory. Use when the person wants to plan work, shape issues, clear the inbox or queue work for the loop. Never builds code.
---

# Shape work for the loop

This is the person's part. Run it in a session with the person, at any time,
including while the loop runs. It writes plans and issues. It never builds
code and never merges.

## Steps

1. Read `PLAN.md` (start from `<plugin>/templates/PLAN.md` if the project
   has none) and the code the work touches. Read open `inbox` issues, or
   take the person's idea.
2. Ask ONE batch of questions, all at once, and wait for the answers. Ask
   only what the plan and the code cannot answer.
3. Add each decision to `PLAN.md`, with the date and the reason. It is a
   living file: every builder reads all of it.
4. List the prerequisites only a person can clear (accounts, keys, money,
   settings, access, a decision on going public). Put them first and get
   them cleared before any label goes on. Name each one as plainly as
   a task.
5. Ask the oracle question for each piece: how will an agent see that this
   is right (a command, a render, a measurement)? If nothing can, the first
   issue builds that check.
6. Split the work into issues an agent can finish in about an hour. Each
   follows `<plugin>/templates/issue.md`: a goal, three to six acceptance
   criteria, how an agent checks it, a `## Paths the builder may change`
   section (normally `none`), `Depends on: #a, #b`, and a milestone.
7. Create each issue with `gh issue create --label shaping --milestone
   <name>`, dependencies first. Then write `Depends on: #n` with the real
   numbers into the dependants. Show every issue in full. Ask for one yes for the whole batch.
8. On the yes, label each issue `ready` with `gh issue edit <n>
   --add-label ready`. The loop builds an issue only when the person's own
   login added that label, which holds when this runs in the person's
   session. Remove `shaping` and `inbox` from it.
9. Close a raw `inbox` issue with a comment linking to the issues that
   replace it.

## Rules

- Label nothing `ready` without the person's yes in this session.
- Mark an issue `shaping` while it is drafted, so the board shows it.
- Never write a path in `## Paths the builder may change` unless the
  builder may change it: it lifts the merge checks for that path.
- An issue that needs a decision from the person on the stops list in
  `PLAN.md` is not ready: ask for the decision now.
