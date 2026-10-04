---
name: queue
description: The plan a run would follow, for somebody taking on more than one piece. Trigger when someone asks what can be built in parallel, what order the rest comes in, what a run would do, or wants to see everything that is ready rather than the next thing. Prints the order, the groups that can go together, what a run can do with each piece, what stacks on what, and the command that runs it. Never builds, shapes, or changes anything.
---

# Queue

`/what-now` is for somebody who is lost, so it names one next step and at most
three things. This is for somebody who has decided to take several pieces on at
once and needs to see the whole set. Typing it is the person saying so. It
shows what a run would do, and `/implement` does it.

## Read

Refresh the printout with `sh .agents/tools/plan-refresh.sh` and read
`plan.local.md`. That is the only source for the pieces. Where the project has no copy of the
helper, the `setup-ai-build-kit` skill's `references/pieces.md` says what to
run instead; never sort the pieces by hand. If GitHub cannot be reached, work from
the printout as it stands and say when it was written, because an old list a
person can see beats no list at all.

The printout has already done the sorting. A piece under `To build` marked
`(ready)` is shaped and free to start. A piece under `Held up` names the piece
holding it up, and marks it `(in the plan)` when every open blocker in its
chain is in the plan. `Go together` holds the pieces under `To build` in
groups, and two pieces in one group name no area in common on their `Boundary:`
lines. Each ready piece carries the marks read from its own body: `(needs you)`,
`(not ready)`, `(not yet checked)`, `(try it)`, and on a held-up piece
`(waits for ...)`. Nothing else needs working out, and a piece with an open
blocker is never under `To build`, so a ready piece cannot be waiting on another
ready piece. Never open the pieces themselves with `gh issue view`.

Beside the printout, read the masterplan's build-path section, for the
sensitive areas and the `Accepted:` lines, which no piece carries, and the
project's `.ai-build-kit-maintenance` for a `check-myself|yes` line.

Where the printout has pieces under `To build` but no `Go together` section,
the project's helper is older than the plan. Say so, say that the next
`/maintain` refreshes it, and print no groups and no command, since the marks
a verdict needs are missing too.

## Say

Five parts, in this order: the order, the groups, what a run can do with each
piece, the stack, and the command. Piece names, never issue numbers, in every
part but the command, which needs the numbers. The person cannot follow a
number, and the printout carries the name of the blocking piece already.

**The order.** The plan is every piece under `To build` marked `(ready)`, and
every piece under `Held up` marked `(in the plan)`, one whose open blockers are
all in the plan, all the way down its chain: the pieces `/implement queue`
would take. Say the count first, in one line, then the
pieces in the order a run builds them, each after every piece it depends on,
and by number where the blocked-by links leave a choice. The pieces under
`To build` are free of each other: they have no dependency between them, which
is what makes them safe to take on at once.

Among the pieces under `Held up`, one whose blocker is outside the plan waits
its turn. Give it one line after the order, saying which piece releases it: "deposits cannot
start until card payments is built". Where a chain runs deeper than one, the
order falls out of the chain itself, so put the piece that unlocks the most
first and let the rest follow it.

**The groups.** Read the `Go together` groups as the printout wrote them, and
never group the pieces yourself. The pieces of one group can be built at the
same time in any order, because no two pieces in it change the same area. Two
pieces that each pass alone can still fail together, so each still merges one
at a time, brought up to date with `main` and checked again first.
`/implement queue` builds one piece at a time by default, whatever the groups
say. On Claude Code it asks before the run starts whether to build a group's
pieces at the same time, and warns that this uses more memory. Say each group in one line of piece names. Where a piece's line says its Boundary is
unknown, say that its `Boundary:` line is missing, so it goes alone until `/shape`
writes one. A piece under `Held up` is in no group, since it is not free to
start.

**What a run can do with each.** One line for every piece in the plan, with the
first of these that holds. The printout's marks settle all but the first:

- Needs you: it lies in a sensitive area the build-path section names, and no
  `Accepted:` line covers it. A run never takes it, and never accepts on the
  person's behalf. A piece the printout marks `(needs you)` has a `Waiting on
  you` step other than `try it`, and needs the person too: name the step as
  their own to do, and never ask for a key, a password, or a token in a message.
- Waits for the piece it stacks on: the printout marks it `(waits for ...)`, or
  it stacks on a piece that needs you through a sensitive area. Give the base's
  name and its reason, as the mark does: "calendar invites waits for calendar
  sync, which is not ready". A run cannot take it until its base can be taken.
- Not ready: its `## Readiness` section says Not ready, which the printout marks
  `(not ready)`. A run leaves it, and `/shape` is where it goes back.
- Not yet checked: it has no `## Readiness` section, which the printout marks
  `(not yet checked)`. It was shaped before the check existed. A run checks it
  before claiming it, and it goes back to shaping if the check finds a gap.
- Taken, then waits for your try: the printout marks it `(try it)` for a
  `Waiting on you: try it` line, or the project carries a `check-myself|yes`
  line. The piece is still taken by a run and stops at `to check` for the
  person's try, and it is never merged under pre-approval. A `Waiting on you:
  try it` line alone does not keep a piece out of the groups.
- A run can take it: none of the above holds, so the Readiness section's first
  line says Ready. On Explore privately, say the run's own condition beside it:
  a run takes the piece only as disposable work whose Done when lines a machine
  can check.

**The stack.** A piece that depends on another piece in the plan stacks on it:
a run builds it on that piece's branch, and its pull request merges after that
one. Say each in one line: "deposits stacks on card payments, and merges after
it". Where nothing stacks, say nothing about it.

**The command.** The last line is the exact command that runs the plan, and
nothing follows it. It is `/implement queue` when a run can take every piece
in the plan, counting a piece not yet checked and a piece that waits for the
person's try. Otherwise it is `/implement` followed by the numbers of the
pieces a run can take, in the order above, such as `/implement 4 7 9`. The
numbers include a piece not yet checked and a piece that waits for the
person's try, just as `queue` would take them. A piece that needs you, is not
ready, or waits for the piece it stacks on is never among them.

Where a piece is waiting on a question rather than on another piece, say which
of the three it needs and leave it out of the plan. It is not ready and it is
not blocked by work; it is waiting on somebody.

A piece under `Building` or under either `In review` column is in neither group, nor anywhere in the
plan. The first is already claimed, and the second is built and waiting for a
review: the person's under "In review, waiting for you". Say how many wait for
the person, in one line, when any do.

A piece that has been sized but never moved to `state:ready` sits under a `Shaping:` column, not under
`To build`, so `/implement` will not take it either. Name it with those, and say
`/shape` is what moves it to ready. It matters most when that piece is the one
holding another up. A held-up piece's blocker may sit under a `Shaping:` column, so name it there,
because otherwise the person is told to wait for something they never see.

Where nothing is ready, say so plainly, say what would make something ready,
usually `/shape`, and print no command. Where a run can take none of the pieces
in the plan, leave the command off too, and say what would change each
verdict. Where
nothing is blocked, say nothing about it rather than printing an empty group.

Do not rank the pieces beyond the order the links give, and do not choose for
the person. This command only ever reports: it never labels, claims or starts a
piece, and running the plan is the person's choice.

## Done when

The person can see the plan a run would follow: the order, which pieces can go
together, what a run can do with each, what stacks on what, and the command
that runs it. Nothing has been changed.
