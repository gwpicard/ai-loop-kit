# Loop-first redesign

The design for turning the kit into a system that works through a backlog one
piece at a time, or several in a chain, with nobody watching. It records the
decisions the maintainer made on 29 and 30 September 2026, the evidence behind
them, and the slices that build it. Each slice is a sub-issue of the epic that
points here. Read this file before building any of them. The second round's
decisions, from slice 13 on, are in
[loop-first-round-2.md](loop-first-round-2.md).

## Why

A real project built with the kit ran for six weeks: 451 commits, 119 merged
pull requests and 168 issues. Its owner is the maintainer, and the way they
worked is the way the kit is meant to be used. The kit did not describe that
way of working, so the agent improvised it each time, and the kit's rules did
not travel with the improvisation.

What went wrong, in order of weight:

- **Batch runs were hand-built four times.** Each one kept its rules and state in
  temporary files and memory notes. The gate that decides which pieces a run may
  take was skipped twice, once on a piece that touched personal data.
- **A merge put the tool live.** The host deploys every merge to `main`, so the
  first launch happened as a merge inside a loop, and `/ship` never ran it.
  Three merges went ahead on a yes that did not name them.
- **"Try it yourself" was skipped** in almost every build. "Where can I see
  this?" came up about twelve times. The person then handed the check to the
  agent and invented test profiles to make that work.
- **Parallel work collided.** Worktrees and sessions stepped on each other, a
  missing claim let two runs start the same piece, and nearly every batch merge
  hit a changelog conflict.
- **The records grew past their limits.** The project's `AGENTS.md` reached
  1,019 lines against a ceiling of 200.
- **Pieces were detailed but missed categories.** Of the review findings, about
  38 were states nobody named (empty, failure, leaving part-way, a tap while an
  answer arrives), about 14 were data and sync rules, about 11 were things
  leaving the device, and 11 were rules or numbers the change broke. The loop
  pull requests also carried 85 choices the builder made alone and marked "to
  confirm".

What held: `/shape`, the clarify interview, prototypes, parts and blocked-by
links, the risk notice, `/fix` finding the cause first, and plain hand-over
reports. Rules held when a command was actually typed or a machine enforced
them. Prose the agent had to remember while improvising did not.

## The principle

Model the loop the person already runs, and move every rule to the place where
its action happens, so that every route carries it. The piece becomes a
contract a machine can build against. `/queue` plans. `/implement` runs.

## Decisions

| Topic | Decision |
|---|---|
| Audience | Technical builders who direct agents. The workflow never depends on reading code, and it assumes git, branches and pull requests are familiar. |
| Records | Every record is written for agents first, with a short human header. Only public documents meant for people, such as the README, stay human-first. `AGENTS.md` becomes an index of rules and pointers with a line ceiling checked when work is saved. |
| States | Each open piece is in exactly one state: idea, shaping, ready, building, to check, or parked. A closed issue is done; an idea deliberately left out stays closed and labelled parked. The states can be read as the columns of a board. A `needs-` reason is a note inside shaping, and "held up by another piece" is a link, never a state. |
| Capture | An idea can be captured in plain words or with `/shape`. It is always filed as an issue. An issue opened by hand with no state counts as an idea. `/shape` always tries to reach ready. |
| Research | A research piece declares, before it starts, whether its result will need the person's decision. |
| The bar | One bar for every piece, applied in proportion to it. Every field is considered, and a field that does not apply says why in one line. Checks scale with the change, so a colour change does not run the whole suite. The standards always apply. |
| Readiness check | Before a piece turns ready, a fresh session that did not shape it checks it against a fixed list. A miss sends it back to shaping. The list is fixed because an open "find the gaps" review always finds some. |
| Checks first | Each check a machine can run exists and fails on today's code before the code is written, in its own commit. An existing test changes only when the piece names it. Checks only a person can make are exempt. |
| Walk-through | The agent may drive the tool with sample data and record what it saw, standing in for the person's try before saving. The piece still goes to to check and closes when it merges. The person opts in when they want to try a piece themselves. |
| Open choice in a run | Split by how hard it is to undo. A choice about data shape, sync, or what leaves the device stops that piece and sends it back to shaping. A choice that is easy to undo takes the most reversible option and is flagged in the pull request. Either way the run moves on to the next unblocked piece. |
| Pull requests | One pull request per piece. The parts of one parent share a pull request. |
| Chains | A piece that depends on one built but not yet merged stacks on it in dependency order, so the stack merges cleanly in order. |
| Worktrees | The kit owns them: one per piece, named after it, removed when its pull request closes, leftovers removed by `/maintain`. A worktree links to the main `.env` rather than copying it. |
| Progress | A run keeps a state file. A live page is published from it wherever the coding agent can publish one, and the state file alone serves elsewhere. |
| Agent merge | An agent merges only when the person pre-approved it before the run. |
| Launch | Merges reach a preview. `/ship` promotes to live, with its checks. |
| Changelog | One file per piece, folded into `CHANGELOG.md` by `/sync` or `/ship`. Round 2 moves the fold to the merge. |
| Portability | Claude Code first. Other coding agents get the one-at-a-time core, and the compatibility page says so. |
| Size | The kit grows, and PHILOSOPHY says why: the growth replaces improvisation that already happened, with its safety built in. |

## The piece contract

A piece keeps a short human header and a complete agent layer. The readiness
check reads the whole piece.

**Human header**

- **So that**: one outcome for the person.
- **Done when**, in two groups. *Works*: checkable rules, each naming its check.
  *When it is not the normal case*: one line for each state that can arise, each
  with its check, or "does not arise, because".
- **Masterplan change**: what the masterplan gains, changes or loses.
- **Not in this piece**: required when Done when does not cover all of So that.
- **Waiting on you**: only when a step belongs to the person.

**Agent layer**

- **Decided**: every choice a person would notice by trying the tool, with its
  reason.
- **Data**: for each stored record written or changed, where it lives, who else
  writes it and how the writes merge, the order on first open, limits and what
  goes at the limit, backup and restore, delete and undo.
- **Leaves the tool**: what goes where, whether the recipient is new, keys, the
  gate, and whether the build path's personal-data line changes.
- **Must still hold**: each rule, limit or time target the change touches, with
  its number and where it is measured, and which rule wins where two apply.
- **Relies on**: each existing thing the piece uses, confirmed to exist and to
  give the data needed.
- **Touches**: one line naming the areas changed, by skill, record or document
  name, never a file path, because paths go stale.
- **Under the hood**: the build approach, and the existing tests this piece may
  change, with the reason.
- **Evidence**: the kind of proof, summarising the checks on the Done when lines.

**Rules that are not fields**

- No open choice a person would notice. Phrases such as "decide during build",
  "consider", "or accept the limit", "TBD", "if needed", and "e.g." inside a
  list are refused. A vague word needs a number.
- Lists are complete, never examples.
- Each Done when line is false on today's code and true after, through this
  piece alone.
- Split, never shrink. No stub, placeholder or "for now" stands in for a line.
- A missed number is a fail, stated at the top of the pull request.
- Report a wrong test or an impossible line. Never work round it.

**Rejected**: traceability ids, separate spec, plan and task documents, a
separate assumptions field, and mandatory given-when-then syntax. Independent
reviews of spec-heavy tools found long review times with bugs still getting
through, and the tools' own makers have scaled back. The failures above came
from missing categories, not missing length.

## The run

`/queue` reads the ready pieces and prints the plan: the order from blocked-by
links, which pieces can go together because they share no area, and what a run
can do with each. Its last line is the command that runs the plan.

`/implement` builds one piece, or runs the plan. For each piece in a run:

1. Claim it (`building`), before any work.
2. Open its worktree from the right base: `main`, or the branch of the piece it
   stacks on.
3. Start ritual: read the run state, start the tool, run a smoke check, and
   confirm the piece's Relies on lines still hold.
4. Write the machine checks first and show that they fail.
5. Build, verify, and walk through with sample data.
6. Independent review.
7. Open its pull request, write its changelog file, and move it to to check.
8. Update the run state and the live page.

A piece that fails three times is parked with the reason, and the run moves on.
A sensitive area without a recorded acceptance is never taken. The run ends
with one report: each piece, its pull request, its state, the choices flagged
for confirmation, and the merge order. The person answers with the pull
requests to merge, unless they pre-approved merging.

## Slices

Built in this order. Each is its own pull request, stacked on the one before. The epic's sub-issues carry the full contract for each.

1. **Philosophy and audience.** PHILOSOPHY, README, WORKFLOW's opening and
   COMPATIBILITY say who the kit is for, that records are agent-first, that the
   kit owns worktrees, that Claude Code comes first, and why the kit grows.
2. **Piece states.** One exclusive state label per piece, read by the plan
   printout as a board, with capture in plain words or through `/shape`.
3. **Commands read the states.** `/implement`, `/queue`, `/what-now`, `/sync`
   and change-triage use the states, and `/maintain` migrates an older project.
4. **The piece contract and the readiness check.** The template, pieces.md, and
   `/shape` with the fixed list run by a fresh session.
5. **Checks first and the walk-through.** section-builder writes machine checks
   first, protects existing tests, and closes on a walk-through unless the person
   opts in.
6. **Changelog files.** One file per piece, folded by `/sync` and `/ship`.
7. **Agent-first records.** The founded `AGENTS.md` becomes an index with a
   ceiling checked on save, and section-builder routes each fact to one home.
8. **Merge and promote.** One merge step for every route, with the named yes and
   pre-approved agent merge, and `/ship` promoting from preview to live.
9. **The runner.** `/implement` runs the plan with claims, stacking, the state
   file, the live page, the open-choice rule and the end-of-run report.
10. **The runner's rehearsal.** A replay case drives a run over three fixture
    pieces and the harness grades the end state.
11. **Worktrees.** The kit's worktree life cycle, the linked `.env`, and
    `/maintain` removing leftovers.
12. **`/queue` plans.** The printed plan with order, groups and the command that
    runs it.

## What stays

`/shape` and clarify, the risk notice and its acceptance, a person deciding what
reaches live, `/fix` finding the cause before changing code, sensitive areas
stopping unattended work, and the rule that the workflow never depends on
reading code.
