---
name: implement
description: The everyday command for building a piece that has already been shaped and marked ready. Typed alone it takes the next ready piece from the plan. Given an issue number, or a request that matches a ready piece, it builds that one. A request that is not yet a ready piece goes to shape first; implement builds, it does not shape. Given several issue numbers, or "queue", it runs them as a plan with nobody watching. Do not use for repairs of promised behaviour; that is fix.
---

# Implement

Use the current session for related, well-bounded work while the context
remains clear. Start fresh after a long, confused, interrupted, or unrelated
session, and whenever an independent review is required. The documents are
the source of truth either way. Read masterplan.md first, build-path section
first, then the project's pieces.

This command builds; it does not shape. It takes a piece that `/shape` has
already shaped and marked ready, and carries it to a confirmed, saved change.
Shaping, sizing, and settling a question all happen in `/shape`, so this command
never has to guess what a piece means. A request that is not yet a ready piece
belongs to `/shape` first.

`sh .agents/tools/plan-refresh.sh` prints the open issues into `plan.local.md`.
Refresh first, then read that, and never sort the pieces by hand in its place.
The `setup-ai-build-kit` skill's `references/pieces.md` describes how the
pieces are kept, and what to run in a project that has no copy of the helper.

When GitHub cannot be reached, say so, say when the printout was last written,
and work from it. The piece already in hand carries on. Anything that would
change what is on the plan waits, because an issue that cannot be updated is
not a record of anything, and that includes starting a new piece, since
starting one moves its state.

## Typed alone

Take the lowest-numbered ready piece that nothing open is holding up and whose
class the current build path allows. A ready piece is one `/shape` has finished
shaping: it carries the `state:ready` label, has a `## Done when` line, and waits on no
open question. The issue list says which are held up, so this needs no digging.

A piece with open parts is a container, not a slice to build directly. Skip it
and take one of its parts, the same way you would take any other ready piece; the
parent closes on its own when its parts all close. The issue list carries the
sub-issue count, so a parent is known without digging, the way a blocker is.

Before handing an eligible piece to section-builder, confirm it's genuinely
unblocked, confirm the current build path allows it, and identify its
evidence and save route from the piece and the build path. Read the piece's
subject labels rather than reclassifying it; the classification was settled in
`/shape` and section-builder reads it rather than re-deriving it.

Claim the piece before any work, through the gate, which moves it from
`state:ready` to `state:building` and assigns it in one call:
`python3 .agents/tools/gate.py move <number> building --assignee @me`.
section-builder's step 1 makes that move, so two sessions never start the same
piece. Where GitHub cannot be reached the claim cannot be made, so say so and do
not start the piece: a piece nobody could claim may be claimed by somebody else.
Where the gate refuses a move, tell the person its line in plain words and stop that move.
Never write the label another way, as the `setup-ai-build-kit` skill's
`references/blocked-commands.md` says.

A piece kicked back to shaping is not buildable as it stands, and it never
carries `state:ready`, so nothing here takes it. One kicked back at a sensitive-area caution sits in `shaping:clarify` with a `## Kickback` section naming the caution, and stays there until the person carries on after the risk notice and the acceptance is recorded;
`/shape` then moves it on. One kicked back after three failed attempts sits in `shaping:spec` or `shaping:research` for `/shape` to look at again,
as `references/running-longer.md` says. A label from an older project, such as
`blocked`, is named by `gate.py report` and left alone.

## When a piece waits on the person

A piece carrying a `## Waiting on you` section cannot be built until that step is
done. Such a piece sits in `shaping:clarify`, as the
`setup-ai-build-kit` skill's `references/pieces.md` says, so it never reaches
`To build`. Given it by number, do not attempt it, and do not pass it over in
silence. Say what the step is, in the words the piece uses, and that building
carries on once it is done.

The `Waiting on you: try it` line is different: it asks for the person's own try
once the piece is built, so build the piece, and section-builder waits for them
before saving.

In an unattended run, name the step, leave the piece where it is, and take the
next ready piece, so the run keeps working and the step is waiting when the
person comes back.

Where the step turns out to be something you can do yourself, do it and carry on
rather than asking. A piece should never hold work up for something the agent
could have gone and done.

## When the next piece is not ready

A piece still in `state:shaping` has a question to settle, or a contract to
write, before its code is written. An issue with no `## Done when` was typed by
hand and never sized. An open issue with no state label has not been taken in yet, however full its body,
because nobody captured it through the gate. None of them is ready, and building
one only guesses the answer.

This command does not settle the question. Settling it is planning, and planning
is what `/shape` is for. Say in one sentence what the piece is waiting on, and
point the person at `/shape` to shape it. Then take the next ready piece instead,
so a session that asked to build still builds something. Where nothing else is
ready, say so plainly rather than shaping the waiting piece here.

## Given a specific piece or a request

Typed alone, take the next ready piece as above.

Given an issue number, build that piece if it is ready, and send it to `/shape`
if it is not, saying in one line why it is not ready. Given several, run them
as a plan, as the section below says.

Given a request in plain words, check whether it already matches a ready piece.
Where it does, build that piece. Where it does not, this is new or unshaped
work: point the person at `/shape`, which shapes a request into a piece. This
command never shapes a typed request itself, and it never builds past an open
question.

## When the pieces contradict each other

The blocked-by link is the truth, so read the link. A ready piece whose blockers
have all closed is buildable. A kickback is not about another piece: it names a
stop written on the piece, so it never lifts because a blocker closed.

A piece carrying two states is not built. The printout lists it under Needs
attention; say so, and leave the repair to `/sync`.

When nothing is ready, because everything open is held up, still waiting on a
question, or two pieces hold each other up, say so plainly and name what is
waiting on what. Standing there with nothing to say is the one unhelpful answer.
Two pieces blocking each other is a planning mistake rather than a state to wait
out, so offer to break it in `/shape`.

A piece assigned to somebody else is theirs. Skip it and say who has it. Where
that person is no longer around, offer to take it over and let the person
decide, because reassigning somebody's work is their call.

Two people building the same piece is what claiming a piece exists to prevent,
so say it the moment you see it rather than at the end.

## Naming the next piece

When the report at the end of a build names what can be built next, read it off
the printout section-builder has just refreshed. Name only a piece under
`To build` marked `(ready)`, and never the piece just built. Where that group
holds no such piece, say that nothing is ready to build now, say what the rest
are waiting on, and name no piece as next. Never work the next piece out from
the issue list or its blocked-by links by hand: the printout already keeps a
piece with an open blocker out of `To build`, and a hand reading does not.

## Merging

A built piece's pull request merges only as the `section-builder` skill's
`references/merge.md` says: on a yes that names it, or under the person's
pre-approval of a run, for a piece that meets all six of its conditions.

## Given several pieces, or queue

Given several issue numbers, or `queue`, this command runs them as a plan with
nobody watching. `auto` is another name for `queue`. Load
`references/running-longer.md` before the run starts and follow it. The shape,
so the person knows what they are agreeing to: the plan is said once, with each
piece and whether the run may take it, and the person approves it once and says
whether pieces that pass may be merged. Each piece is then claimed, built,
walked through and reviewed, and opens its own pull request, with the parts of
one parent sharing one. A piece that depends on another built in the run stacks
on its branch.

On Claude Code, each piece in a run is built in its own worktree under
`.agents/worktrees/`, named after the piece, while the main folder stays on its
branch. Where the plan holds a group of pieces that can go together, the run
asks once whether to build a group's pieces at the same time, warns that this
uses more memory, and builds one at a time unless the person gives a number.
The kit clears a worktree away once its pull request has closed and nothing in
it is unsaved. Outside a run, a single piece is built in the main
folder, as always, unless the person asks for a worktree: then open one the
way `references/running-longer.md` says.

Whether the run may take a piece is decided for each piece. A piece is taken
only when it is ready, carries a Ready readiness result, is
self-sufficient enough to build without a person present, waits on no step of
the person's other than their try, and lies outside every sensitive area that has no recorded
acceptance. A piece that fails three attempts is kicked back to shaping, a hard open choice,
seen at the plan or met while building, sends a piece back to shaping, and the
run moves on. Every move the run makes goes through the gate. It ends with one
report: each piece, its pull request and its state, the choices flagged for the
person, what went back to shaping and why, and the merge order.

The run keeps its state in the main folder's `.agents/runs/`, the first
worktree git lists, even when this session sits in another tool's worktree,
so a session that dies loses nothing. Where an unfinished run's state file is in `.agents/runs/`, offer to
resume it before taking anything new, whether this command was typed alone or
with `queue`.

## Done when

The route was followed, the records are true, the piece moved through the gate from `state:ready` to `state:building` before any work and on to its next state when the pass ended, and the piece is confirmed and saved through the required route, kicked back to shaping at a recorded condition, or the user knows exactly where things stopped and why.
