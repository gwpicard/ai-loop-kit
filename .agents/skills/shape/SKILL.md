---
name: shape
description: The command for turning an idea into a ready piece before anything is built. Typed with words after it, it takes the request in plain language, works out what kind of work it is, shapes it into a piece, and settles any open question. Asked only to note an idea, it files the piece and stops. Typed alone it shapes the next piece still waiting on one. It records and stops; it never builds, though it offers to hand a ready piece to implement.
---

# Shape

This command shapes work; it does not build it. It takes an idea in plain
language, works out what kind of work it is, writes it into a piece somebody
could build, and settles anything the piece is still waiting on. When a piece
is ready it offers to hand it to `/implement`, but building is always a
separate, deliberate step.

Read masterplan.md first, build-path section first, then the project's pieces,
the same way `/implement` does. Refresh the printout and read that.
The `setup-ai-build-kit` skill's `references/pieces.md` describes how the pieces are kept.

Whenever shaping touches a decision, re-read any "rests on" clause in the
piece's `## Decided` or the masterplan, following pieces.md's decision rules.
Check what it names before relying on it, including when the piece is already
ready. When its support has gone, say in one line: "The rule that a job closes
once rested on a test that no longer exists." Name the actual rule in plain
words, then settle any question this opens through the usual shaping route.

## Typed with words

Typed as `/shape <number> check readiness`, this is not a request. Skip
change-triage and run the readiness check on that piece, as the readiness check
section below says.

Otherwise run change-triage on the request and follow its route: shape it into a ready
piece now, run clarify first, run a decision prototype, run a source check,
update the masterplan first, or stop and rerun the fit check. Say which route
you chose and why, in one line. A request that becomes a piece is taken in as
`shaping:raw` and triaged at once, as change-triage's "Triage in raw" says.

Where GitHub cannot be reached when a request would become a piece, nothing is filed. Say so in one line, and
repeat the person's words back to them in full, so nothing they said is lost
and they can give it again once GitHub answers.

Clear, piece-sized work becomes a ready piece straight away: write it into the
shape the `setup-ai-build-kit` skill's `references/pieces.md` describes, take its subjects
from change-triage rather than choosing them yourself, and move it to `state:ready`
through the gate once the readiness check below finds no blocking gap. That is
a new issue, taken in through the gate by change-triage so the check has a
piece to read, and it starts unassigned: a person is assigned only when
`/implement` picks the piece up to build it, never when `/shape` creates it.
Then make the build offer below.

Shape the piece in its two layers, as pieces.md describes. The header stays
short and plain, so it never reads as simpler than the work is. The agent layer
is complete: consider every field, and where one does not apply, say why in one
line. Every choice a person would notice by trying the tool is decided in
`## Decided`, with its reason, rather than left for the build. Scale the piece to
its change: a colour change answers most fields in one line. The build context
that only affects how the code gets written goes in the collapsed
`Under the hood` section, so the person never has to read it and `/implement`
still has it. Route context that reaches past this piece by
how far it reaches: a whole-product decision to the masterplan, a whole-codebase
convention to AGENTS.md's stack section, lasting technical design to its concept
file listed in `docs/README.md`. A piece must be small enough for a fresh
session to hold whole; where it is not, cut it down. Any groundwork the piece
needs is itself a vertical slice, ordered ahead of the piece that needs it, never
a separate "database" or "API" layer.

On every piece you shape or refine, write `## Masterplan change` on the
surface before marking it ready, following pieces.md. Say what the masterplan
gains, changes or loses when it lands. Write "nothing" only when the masterplan
already says every line of `## Done when`; pieces.md has the test, and a new
rule the person could check is a change even when it narrows an existing
promise. Read it back in the reply that reports the piece: "When this lands, the
masterplan gains a weekly summary email." Use the actual change in that line;
for "nothing", say the masterplan already covers it. Do not apply a future change while shaping.

When writing the `Under the hood` notes for a project with code, load
the `section-builder` skill's `references/reach-check.md` and run its reach
check. Use the live result to name the code seams and existing covering tests,
instead of researching them again from nothing. Keep the result on the piece as
build context only; never create a separate index or record for it.

Where the request is bigger than a piece, it goes into the masterplan first and
is cut into pieces on the plan, order confirmed with the user. Parts of one
outcome become sub-issues of a parent piece, each a vertical slice; separate
outcomes that must come in order become separate pieces linked by blocked-by. The
test is the outcome: one shared `## So that` means parts of a whole, and the
parent is done when its parts are. Where it would change what kind of project
this is, stop and rerun the fit check before shaping anything.

## Shaping now, or filing for later

Typed with words, this command shapes now. The person already chose to shape
when they typed it, so offering them the choice again asks the same question
twice. Where the route is a question rather than a ready piece, start the step
the route names. A source check or a search for existing work simply starts.
An interview or a prototype takes a sitting, so say so in one line and start:
"This needs a short interview, which takes a sitting. Say 'later' at any point
and I'll file it."

The person can say "later" at any point in a step. File the piece then, with
anything the step has already agreed written onto it, and stop.

Filing is also something the person can ask for outright, in words such as
"note this for later" or "just file this idea", or by typing `/shape later` or
`/shape idea` with the idea. That is capture, and change-triage handles it: file
it without starting any step, through the gate as a piece in `shaping:raw`, in their own words,
with nothing settled. It is not a separate command. The idea is shaped the next
time somebody runs `/shape` on it.

Filing part-way through a step writes the piece in full: the person's own words,
the question it still waits on in plain language, and the sub-state that names
who can settle it. It is the same piece a session settling the question now would
have started from, so a fresh session picks it up with nothing lost. Then stop.
Do not begin the step, or carry on with one already started, and do not raise
the question again in the same session.

A piece filed part-way stays in shaping: it carries the sub-state that names its question and no `state:ready` label,
which is what keeps it out of `/implement` until its question is answered. Deferring the question never lets the piece be built with the question
still open.

## Moving a piece's state

Only the gate script moves a piece. It takes the old state off in the same step as it puts the new one
on, so a piece never shows in two columns of the board, and it refuses a move
whose condition does not hold. Until `/shape` gives each sub-state steps of its
own, these are the moves it makes:

- A piece with an open question moves from `shaping:raw` once the question is written under `## Open question`:
  to `shaping:clarify` for a decision only the person makes, `python3 .agents/tools/gate.py move <number> clarify`;
  to `shaping:research` for a fact from outside, `python3 .agents/tools/gate.py move <number> research`;
  or to `shaping:prototype` for a flow the person has not seen, `python3 .agents/tools/gate.py move <number> prototype`.
- A piece with no open question moves from `shaping:raw` to `shaping:spec`, `python3 .agents/tools/gate.py move <number> spec`.
  A bug that took change-triage's fast path arrives in `shaping:spec` this way, already carrying `loop:fix`.
  Write its contract and run the readiness check in the same session, and offer `/implement <number>` as soon as it is ready.
- In `shaping:spec`, replace a guessed `Loop module:` line, the one triage marked
  `(guess, ...)`, with the module the contract is written for. Give the piece
  that module's label where it has none, `gh issue edit <number> --add-label loop:<module>`.
  The `loop:` label is not a state, so `gh` writes it directly.
- A settled question is written under `## Decided` for clarify and prototype, or under `## Research` with a source for each claim for research, and the piece moves to `shaping:spec`
  with the same command.
- Research whose result needs the person moves to `shaping:clarify` once what it
  found is written under `## Research`.
- Before a written contract moves on, the ready-gate lint runs on it, as "The readiness check" below says.
- Once its contract is written, the piece moves to `shaping:check`, `python3 .agents/tools/gate.py move <number> check`, and the readiness check runs.
  On Ready the piece moves to `state:ready`, `python3 .agents/tools/gate.py move <number> ready`.
  On Not ready it moves to the sub-state its first BLOCKING line needs: `spec`,
  `clarify`, `research` or `prototype`.
- A piece in `state:ready` that nobody has claimed and somebody wants another
  look at moves back with `clarify`, or with `research`, `prototype` or `spec`
  where that is the question.

Where the gate refuses a move, tell the person its line in plain words and stop that move.
Never write the label another way, as the `setup-ai-build-kit` skill's
`references/blocked-commands.md` says. Where GitHub cannot be reached, the gate changes nothing, so say so and leave the
piece as it is.

## The readiness check

Before the piece moves to `shaping:check`, run the ready-gate lint,
`python3 .agents/tools/ready-lint.py <number>`, so the checker never reads a
piece the lint would refuse. It checks what a machine can: every section is
there, the bar fits the loop module, each acceptance check fails on today's
code on its assertion, and the reach is whole. Say the lint's result in one
line, such as "The ready-gate lint found two gaps: the reach names no test for
billing, and the check for refunds passes today." Close each gap on the piece
and run the lint again. A gap only the person can close is written as the one
question under `## Open question`, and the piece moves to `shaping:clarify`.
Where the lint says GitHub or its checkout could not be reached, say so and
leave the piece where it is. The move to `state:ready` runs the lint again, so
a piece changed after it passed is caught there.

Before a piece moves to `state:ready`, a session that did not shape it checks it
against the fixed list in the `shape` skill's `references/readiness-check.md`.
The session that shaped a piece has the same blind spots when it judges the
piece, so it would miss the same gaps twice. Start a subagent that carries none
of this conversation, where the coding agent has one, and give it the piece's
number and that file. A fork of this session does not count.

Where the coding agent cannot start a subagent, say in one line that the check
needs a new session, and give the exact line to paste there:
"This piece needs a check by a session that did not shape it. In a new session,
paste: /shape <number> check readiness". Leave the piece in `shaping:check`
meanwhile.
Typed that way, in a session that did not shape the piece, run the check
yourself.

The check writes a `## Readiness` section on the piece: the date, "checked by a
session that did not shape it", Ready or Not ready, and its notes. Read that
section back and let it decide the move. With no blocking gap, move the piece to `state:ready` through the gate.
A blocking gap sends it back through the gate to the sub-state its first BLOCKING line needs, with the gap written on it.
Notes stay on the piece for the builder. Say the result in one line, such as "A session that did not
shape this piece checked it: ready, with two notes for the builder." After a gap
is closed, run the check again in a new subagent.

## When a piece is waiting on a question

A piece in `shaping:clarify`, `shaping:prototype` or `shaping:research` has a
question to settle before its code could be written. Settling that question is
the work of this command. An open issue with no `state:` label was opened by
hand or from the form and never taken in: take it in first, as "Typed alone,
or given a piece" below says, and shape it.

Run the step the sub-state names, write what settled it into the piece's
`## Decided` section, or under `## Research` for research, and only then take the label off,
moving the piece to `shaping:spec` through the gate. The record
goes first because the label is the only thing saying the question was ever open:
once it is gone, a piece settled properly and a piece nobody looked at read
exactly alike.

Read the piece back before the label comes off, and let what you read decide
whether it does. `## Decided` has to hold what settled the question, and
`## Done when` has to be there at all. Where either is missing, the writing did
not happen however well the conversation went: write it, read it again, and only
then relabel.

This is a check, not a reminder. Doing the steps in the right order is what a
run believes it did; reading the piece back is what tells it whether it did. It
is the one part of settling a question nobody in the conversation can see, which
is why a piece has reached `state:ready` with no `## Done when` in it and nobody
noticed until the files were read.

- `shaping:clarify` runs clarify. Write what comes out into the shape
  the `setup-ai-build-kit` skill's `references/pieces.md` describes, and keep the person's
  original words underneath, because their words are what a refinement can be
  checked against and what to return to when it reads wrong.

  A piece another account opened holds a colleague's words, not the person's.
  Read its author first, as the `setup-ai-build-kit` skill's
  `references/pieces.md` describes under "Speaking for the person". Keep their
  words whole under "Original report", and name the author in your reply, so
  the person knows whose request is being reshaped. Ask before saving a changed
  title or scope, and show the new wording when you ask. A body that only adds
  the shaped sections above, with the original kept whole, is not a change of
  scope. Post nothing to that author until the person has said yes to the words.
- `shaping:prototype` settles the piece with something to look at. Where the
  person already has a mock, a sketch, or anything else that shows it, follow
  the `clarify` skill's `references/existing-artifact.md` and build toward
  that, rather than building a throwaway to rediscover a decision they have
  already made. Otherwise run the decision prototype in
  the `clarify` skill's `references/decision-prototype.md`. Either way, the
  decision goes back onto the piece in words.
- `shaping:research` runs one of two steps and records what it finds under
  `## Research` on the piece, with a source for each claim. A question about one external fact, such as what a provider's API
  supports, runs the source check in
  the `change-triage` skill's `references/source-check.md`. A question about
  whether something already exists that could do the work runs
  the `change-triage` skill's `references/existing-work.md`. Say which step you
  ran and why, in one line, because a question can plausibly match either.
  Before it starts, write one line on the piece: "Needs your decision: yes" or
  "Needs your decision: no", saying whether its result will need the person to
  choose. With no, and a result that settles every question, move the piece to
  `shaping:spec` and on through the readiness check, with nobody there.
  With no, and a result that leaves a question open, the piece stays in `shaping:research` with the gap written on it.
  With yes, write what it found, then move the piece to `shaping:clarify` in
  one step, so it waits for the person rather than for a guess:
  `python3 .agents/tools/gate.py move <number> clarify`.

Two of those three need the person in the room. An interview needs somebody to
interview, and a prototype exists so somebody can react to it. Research does
not: the agent settles it alone.

Never answer a person-present question yourself. With nobody there, say which
pieces are waiting on them and leave those pieces where they are. A guess
written onto a piece and moved to `state:ready` is worse than an open question, because
the label that said it was open has gone and `/implement` builds on the guess.

The interview may show that the real block is a different one. Write what it
settled under `## Decided` and the new question under `## Open question`, and
move the piece from `shaping:clarify` to `shaping:prototype` or
`shaping:research` through the gate. Follow the new sub-state rather than
shaping past it. A piece whose question is settled carries `state:ready` and no
`shaping:` label, and the gate never lets the two sit together.

## Typed alone, or given a piece

Typed alone, first take in any open issue that carries no `state:` label, such
as one opened by hand or from the form: take it in with `python3 .agents/tools/gate.py capture <number>`, and never open a second issue for it.
Then give it exactly one `type:` label before its first move, `gh issue edit <number> --add-label type:<feature|bug|chore>`,
as change-triage says under "Taking a piece in".

Then take the next piece still in shaping, in this order: a piece with a `## Kickback` section first, then a piece waiting in `shaping:check`, then `shaping:research`, which needs nobody, then `shaping:clarify` and `shaping:prototype` when the person is there, then `shaping:spec`, then the oldest `shaping:raw`.
Within one place in that order, take the oldest piece first. Pieces already
part-shaped finish before new notes start.

A piece with a `## Kickback` section came back from a build: read what happened
first, and settle the decision it asks for. A piece in `shaping:check` is waiting for its readiness check: its shaping finished and the check never ran,
so run the check on it rather than shaping it again. A piece in `shaping:raw` is triaged first, as change-triage's "Triage in raw" says, and then
follows the sub-state that triage gives it. When nothing is waiting and every
piece is already ready, say so and point the person at `/implement` to build the
next one. The command does not run out of things to do quietly; it says the
plan is shaped.

Given an issue number, settle that piece rather than the next in that order, so
somebody with one piece in mind is not made to work through the list. Given it
as `/shape <number> check readiness`, run the readiness check on that piece and
nothing else. Where that
piece is already ready, say so and make the build offer instead.

Where the person says they are not staying, take the pieces the agent can settle
alone, which is every piece in `shaping:research`. Then name the ones that
need them and why, in one short list, so they know what is waiting for their
return. Settle none of those in their absence.

## The build offer

When a piece is ready, offer to build it: name the piece, and point at
`/implement` in a fresh session as the way to build it, or "not now" to leave it
as a ready piece for later. A fresh session is the offer for every piece, not
only when a founding or long session ends, so a heavy planning context does not
carry into the build. The offer is genuinely optional, and declining leaves a
shaped, recorded piece that any `/implement` session picks up.

Shape itself never builds. Where the person asks to build here and now anyway,
that is `/implement` running on the piece just shaped, not this command writing
code, and a fresh session stays the better path whenever the planning context
has grown heavy.

## Record only durable information

Follow change-triage's rule: add a changelog line only when work actually lands,
the masterplan changes, the build path changes, a risk notice is accepted, or an
idea is closed as not planned or rejected for a durable reason. Shaping a piece is not itself a
changelog entry; the piece is the record.

## Done when

The request has exactly one route, the piece is written into its proper shape
with every field considered and moved to `state:ready` only after a session that did
not shape it wrote a `## Readiness` section naming no blocking gap, or left in shaping
with the question it still waits on, or in `shaping:raw` when the person only asked to
note it, every move went through the gate, a routed question was
started unless the person asked to file it, the person's original words are kept
underneath a refinement, and nothing was built except
through an accepted build offer.
