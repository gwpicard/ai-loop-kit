---
name: shape
description: Turn inbox issues or a new idea into shaped, approved issues for the AI Loop Kit factory. Use when the person wants to plan work, shape issues, clear the inbox or queue work for the loop. Never builds code.
---

# Shape work for the loop

This is the person's part. Run it in a session with the person, at any time,
including while the loop runs. It shapes issues. It never builds
code and never merges.

## Steps

1. Run `<plugin>/bin/loop check-version` from the project root first. If it
   exits non-zero, report its two lines and stop.
2. Read `AGENTS.md` and the code the work touches. Read open `inbox` issues, or
   take the person's idea.
3. Ask ONE batch of questions, all at once, and wait for the answers. Ask
   only what the standing rules and the code cannot answer.
4. Put decisions in the issue that needs them, with their reasons. Use a
   check for a rule that can be enforced. Use `AGENTS.md` only when every
   agent needs the rule and no check can enforce it, `README.md` for context,
   and a `docs/` file only when it earns its place. Ask which parts of the
   project the red team should attack and record them in the `Red-team
   surfaces` list in `loop.json`.
5. Ask the oracle question for each piece: how will an agent see that this
   is right (a command, a render, a measurement)? If nothing can, the first
   issue builds that check. For each piece a person triggers, also ask which
   entry point they use (the keys, the menu item, the command, the route), and
   name it in the criterion.
   For each piece a person sees or touches, also ask for its hands-on
   steps: what they would do in the real product and the result to expect.
   They go in the issue's `## Hands-on check` section, including the steps
   to run the product from the loop branch and the result to expect.
   Keep general instructions for running the product in `README.md`.
6. List the prerequisites only a person can clear (accounts, keys, money,
   settings, access, a decision on going public). Put them first and get
   them cleared before any label goes on. Name each one as plainly as
   a task.
7. Split the work into issues an agent can finish in about an hour. Each
   follows `<plugin>/templates/issue.md`: a goal, three to six acceptance
   criteria, how an agent checks it, a `## Protected paths this issue may change`
   section (normally `none`), `Depends on: #a, #b`, and a milestone. A path
   named anywhere else in the issue body grants nothing.
   Add `Kind: build` for implementation, or `Kind: parallel` for work that
   cannot conflict with builds, such as documentation or research. The loop
   runs at most one parallel issue beside the builds, without taking a
   `Parallel` slot. Both kinds wait for dependencies, and additional workers
   wait for load and memory headroom. A missing or unknown kind means `build`.
8. Create each issue with `gh issue create --label shaping --milestone
   <name>`, dependencies first. Then write `Depends on: #n` with the real
   numbers into the dependants. Show every issue in full. Ask for one yes
   for the whole batch.
9. On the yes, label each issue `ready` with `gh issue edit <n>
   --add-label ready`. The loop builds an issue only when the person's own
   login added that label, which holds when this runs in the person's
   session. Remove `shaping` and `inbox` from it.
10. Close a raw `inbox` issue with a comment linking to the issues that
   replace it.

## Inbox issues from the loop

Reviewer follow-ups and end-of-loop pass findings, including confirmed
defects, arrive as `inbox` issues.
Shape them like any other. The pass's single `Pass findings` issue lists one
checkbox per finding: shape the worthwhile ones, then close it. An issue with a `## Failing test` section keeps
it: the test writer commits that test as given. Ask whether the project
needs a `Check command` (guardrails) or a `Smoke command` (the real
artefact) in `loop.json`, and add the answer there. If the Test command takes
minutes, also ask for a `Test files command` (runs given files, `{files}`
stands for the paths) and a `Prepare command` (installs a fresh checkout).

Once per project, ask whether the Test and Check commands build every target
and type-check every source folder. Record any gap in the issue that fixes
the command, and make that the first issue.

## Rules

- Label nothing `ready` without the person's yes in this session.
- Mark an issue `shaping` while it is drafted, so the board shows it.
- Never write a path in `## Protected paths this issue may change` unless the
  builder may change it: it lifts the merge checks for that path.
- An issue that needs a decision from the person on the kit's stops list in
  `<plugin>/briefs/preamble.md` or in `AGENTS.md` is not ready: ask for the decision now.
