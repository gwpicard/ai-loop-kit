---
name: shape
description: The command for turning an idea into a ready piece before anything is built. Typed with words after it, it takes the request in plain language, works out what kind of work it is, and takes the piece through the shaping sub-states, raw, research, clarify, prototype, spec and check, until the ready gate passes it. A bug with a clear reproduction takes the bug route, straight from raw to spec. Asked only to note an idea, it files the piece and stops. Typed alone it shapes the next piece still waiting. It records and stops; it never builds, though it offers to hand a ready piece to implement.
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
A piece already in a sub-state stays in it when the person says "later", with what was agreed so far written on it,
and nothing more is asked in that session.

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
- Once its contract is written, the piece moves to `shaping:check`, `python3 .agents/tools/gate.py move <number> check`, and the readiness check runs.
  "Spec: writing the contract" below says what the contract holds.
  On Ready the piece moves to `state:ready`, `python3 .agents/tools/gate.py move <number> ready`.
  On Not ready it moves to the sub-state that closes its gaps, as "The readiness check" below says.
- A piece in `state:ready` that nobody has claimed and somebody wants another
  look at moves back with `clarify`, or with `research`, `prototype` or `spec`
  where that is the question.

Where the gate refuses a move, tell the person its line in plain words and stop that move.
Never write the label another way, as the `setup-ai-build-kit` skill's
`references/blocked-commands.md` says. Where GitHub cannot be reached, the gate changes nothing, so say so and leave the
piece as it is.

## Spec: writing the contract

`shaping:spec` has no open question, so write the whole contract alone, with
nobody asked anything: the loop module and its bar, the reach fields, `## Not in this piece`,
and every other field the `setup-ai-build-kit` skill's
`references/pieces.md` describes.

For a build or fix piece, write the acceptance checks as real tests, one for
each line of `## Done when` a machine can judge, and point a `Check:` line at
each. Commit them on a branch named `spec/<number>-<short name>`, cut from `origin/main`,
holding test files only, and push it. `Acceptance branch:` under `## Loop` names it.
Where the project can run them, run each check on `origin/main` before the
push: it has to fail on its assertion. A goal or gauntlet piece gets no acceptance branch here, since its
bar is the one clarify agreed under `## Loop`.

An acceptance check that passes on `origin/main` when written means the line it guards is already true.
Write that finding as the one question under `## Open question` and move the piece to `shaping:clarify`.
In the same way, a question found while writing sends the piece back to the sub-state it needs, with the
question written under `## Open question`. The gate moves a piece out of spec to research, clarify or prototype only with a new question:
one whose fingerprint differs from the section the gate found when the piece
entered spec. A question already asked and answered, still written on the piece, is refused,
so a piece cannot go round on the same question.

Once `## Loop` and `## Reach` are written, move the piece to `shaping:check`.
The gate refuses that move until the two sections have changed since the piece entered spec.

### A spec branch that already exists

When spec runs on a piece that already has a spec branch, after a kickback or after a check was found passing on `origin/main`, cut a new acceptance branch from `origin/main`.
Name it `spec/<number>-<short name>-<n>`, where `<n>` is the next unused number from 2, and hold test files only on it.
Carry the checks that are still valid onto it, and name it on the `Acceptance branch:` line.
Never delete the earlier branch: name it on a `Kept branch:` line under `## Kickback`, never as `Acceptance branch:`,
even when it holds commits the person wants kept.

When neither applies and `Acceptance branch:` is not yet written, as after a spec run stopped half-way with its branch pushed, reuse that branch and cut no new one.

### A project with no code online yet

A spec branch follows section-builder's "The first upload": the first push of a spec branch on a project whose code is not online asks first, as a piece's first push does.
Where `origin/main` does not exist, ask the first-upload question before cutting anything.
After a yes, cut the spec branch from the local `main`, push it, and create `main` on GitHub at the commit it was cut from,
as that section says, then fetch, so the branch stands on `origin/main`.
After a no, push nothing: the piece stays in `shaping:spec` with the reason written on it.
Until then the ready-gate lint refuses a build or fix piece, naming "answer the first-upload question in `/shape`".

Where AGENTS.md's stack section records `Test command: none for <language>`, write the acceptance checks as test files for the runner
the Test runner table in the `setup-ai-build-kit` skill's
`references/check-floor.md` names for that language, and name it under `## Loop` as `Test runner: <runner>`, the field the lint reads.
Nothing can run them yet, and the lint passes them on its route for a project
with no code. The build that adds the runner records the test command in the stack section.

## The readiness check

`shaping:check` runs the ready-gate lint, then the fresh checker, then `gate.py move <number> ready`,
and says the result in one line.

In `shaping:check`, first run the ready-gate lint, `python3 .agents/tools/ready-lint.py <number>`, so the checker never reads a
piece the lint would refuse. It checks what a machine can: every section is
there, the bar fits the loop module, each acceptance check fails on today's
code on its assertion, and the reach is whole. Say the lint's result in one
line, such as "The ready-gate lint found two gaps: the reach names no test for
billing, and the check for refunds passes today." Where the lint says GitHub or
its checkout could not be reached, say so and leave the piece where it is. The
move to `state:ready` runs the lint again, so a piece changed after it passed
is caught there.

On a lint refusal the fresh checker does not run. Write the lint's gaps as the piece's `## Readiness` section,
replacing any earlier one: a first line `<date>, ready-gate lint: Not ready`,
then one `- BLOCKING lint: <gap>` line for each gap the lint printed. The gate's move out of `shaping:check` reads that section as it reads the fresh checker's.

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
Notes stay on the piece for the builder. Say the result in one line, such as "A session that did not
shape this piece checked it: ready, with two notes for the builder."

### Where a gap sends the piece

When the lint refuses the piece or the fresh checker writes Not ready, write each blocking gap on the piece and move it through the gate to the sub-state that closes the gap:

- `shaping:clarify` for a gap a person must settle, with the gap as its `## Open question`,
  including a Relies on line whose code does not exist or does not return what the piece needs;
- `shaping:research` for a fact from outside the project;
- `shaping:prototype` for a gap on item 13, a flow the person has not seen;
- `shaping:spec` for a lint refusal, or a gap in the contract's own wording.

Where gaps need different sub-states, the piece goes to the first of clarify, prototype, research and spec, and the other gaps stay written on it.
Say in one line where the piece went and why, such as "The check found the
refund rule undecided, so this piece is back in clarify with that question."
No `needs-` label is written. The gate moves a piece out of `shaping:check` to another sub-state only once `## Readiness` has changed since the piece entered check,
so the result is written before the move. After a gap is closed, run the check
again in a new subagent.

## When a piece is waiting on a question

A piece in `shaping:clarify`, `shaping:prototype` or `shaping:research` has a
question to settle before its code could be written. Settling that question is
the work of this command. An open issue with no `state:` label was opened by
hand or from the form and never taken in: take it in first, as "Typed alone,
or given a piece" below says, and shape it.

There is no fixed order between research, clarify and prototype. A piece sits
in the sub-state of its next open question, and a sub-state with nothing to do
is skipped. Each has its own section below.

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

The gate reads the same from its answer marker. When a piece enters research,
clarify or prototype, the gate writes a hidden marker on it holding a
fingerprint of `## Research` or `## Decided`, and it refuses to move the piece
on until that section differs. A refusal there means the record was never
written: write it, then run the move again.

### Research: what is true

`shaping:research` answers what is true and never decides. It runs one of two
steps and records what it finds under `## Research` on the piece, with a source
for each claim. A question about one external fact, such as what a provider's API
supports, runs the source check in
the `change-triage` skill's `references/source-check.md`. A question about
whether something already exists that could do the work runs
the `change-triage` skill's `references/existing-work.md`. Say which step you
ran and why, in one line, because a question can plausibly match either.

On a project with code, research also works out what the piece reaches, so the
questions the person is asked later rest on the code rather than a guess. Run
`git fetch origin`, then run the reach check in the `section-builder` skill's `references/reach-check.md` on `origin/main`.
Unless this folder is on `main` at the same commit as `origin/main`, with
nothing unsaved, read each file as `git show origin/main:<path>` gives it, so
the result describes the code the piece will be built on.

Then add one query of saved history for files that change together:
run the `section-builder` skill's `scripts/co-change.sh` from the project
folder, with the files the reach check found. Map each hit to a named area of the project, taken from the
masterplan and the sensitive-area map where one exists, never a bare file
path. Say which reach-check engine you used, including the fallback that reads
imports and callers directly when no engine is there.

Write what research found under `## Research`, one list item for each claim, each naming its source: a web address, or
`source:` and what was read, such as `source: reach check on origin/main at
<commit>`. End with one line that is not a list item, `Recommendation:`, then
what research would choose and why. The recommendation is advice for whoever
decides, and research itself decides nothing.

Before it starts, write one line on the piece: "Needs your decision: yes" or
"Needs your decision: no", saying whether its result will need the person to
choose. With no, and a result that settles every question, move the piece to
`shaping:spec` and on through the readiness check, with nobody there.
With no, and a result that leaves a question open, the piece stays in `shaping:research` with the gap written on it.

A finding that needs a choice moves the piece to `shaping:clarify` with the choice as its question, whatever the line said:
write the choice under `## Open question`, with the recommendation as the
labelled guess. With yes, write what it found, then move the piece to `shaping:clarify` in
one step, so it waits for the person rather than for a guess:
`python3 .agents/tools/gate.py move <number> clarify`.

### Clarify: what the person wants

`shaping:clarify` answers what the person wants, through the clarify skill, one question at a time, in the question box its
"How to ask" describes. Each answer is written into `## Decided` before the gate moves the piece.
Write what comes out into the shape the `setup-ai-build-kit` skill's
`references/pieces.md` describes, and keep the person's
original words underneath, because their words are what a refinement can be
checked against and what to return to when it reads wrong.

Where the reach touches a sensitive area, stored data or anything that leaves
the tool, clarify asks the pre-mortem once, and a goal or gauntlet piece agrees its bar here, both as the clarify skill's
"When a piece touches states, data or the outside" says.

A piece another account opened holds a colleague's words, not the person's.
Read its author first, as the `setup-ai-build-kit` skill's
`references/pieces.md` describes under "Speaking for the person". Keep their
words whole under "Original report", and name the author in your reply, so
the person knows whose request is being reshaped. Ask before saving a changed
title or scope, and show the new wording when you ask. A body that only adds
the shaped sections above, with the original kept whole, is not a change of
scope. Post nothing to that author until the person has said yes to the words.

#### The risk notice and its acceptance

Where the piece's boundary or reach touches a sensitive area named in the masterplan's build path with no recorded acceptance,
give the risk notice here, in `shaping:clarify`, so a run never meets a
sensitive area nobody accepted. Give it once, in full, as the `setup-ai-build-kit` skill's `references/fit-check.md` says,
and follow that file on what counts as carrying on: silence does not count, nor a form or menu answer with no option selected,
and the `Accepted:` line quotes the person exactly.

When the person carries on, write the `Accepted:` line with their words and the date,
and correct every masterplan sentence it makes untrue, in the same save.
Write the acceptance's summary into `## Decided` too, since the gate moves a
piece out of clarify only once that section has changed. Read the `Accepted:` line back before the piece moves on.

The `Accepted:` line and the sentences it corrects are saved on a records pull request of their own, never on a piece's branch.
Ask for its merge with a yes that names it, as the `section-builder` skill's `references/merge.md` says.
Where the masterplan's `Goes live:` line says every merge goes live, the ask for that merge says it is a build on the host,
and that a first such merge runs `/ship`'s first-launch checks, as `/ship` says for its own records pull request.

The piece leaves `shaping:clarify` only once that pull request has merged.
Until then it stays there, with "acceptance saved, waiting for its merge"
written on it. The ready-gate lint reads the masterplan from `origin/main`, so
an acceptance that has not merged cannot carry the piece past the gate either.

On a project whose code is not yet online, pushing that pull request is the project's first upload, which waits for the yes section-builder's "The first upload" describes.
After a no, push nothing. The piece stays in `shaping:clarify` with
"acceptance recorded here, waiting for the first upload" written on it.

### Prototype: what the person has to see

`shaping:prototype` settles the piece with something to look at. Where the
person already has a mock, a sketch, or anything else that shows it, follow
the `clarify` skill's `references/existing-artifact.md` and build toward
that, rather than building a throwaway to rediscover a decision they have
already made. Otherwise run the decision prototype in
the `clarify` skill's `references/decision-prototype.md`. Either way, the decision goes into `## Decided` in words,
and the prototype is deleted or kept apart, never merged.

### Who has to be there

Two of those three need the person in the room. An interview needs somebody to
interview, and a prototype exists so somebody can react to it. Research does
not: the agent settles it alone.

Never answer a person-present question yourself. With nobody there, leave each such piece in its sub-state with the question and its labelled guess written under `## Open question`,
and say which pieces are waiting on them. A guess
written onto a piece and moved to `state:ready` is worse than an open question, because
the label that said it was open has gone and `/implement` builds on the guess.

The interview may show that the real block is a different one. Write what it
settled under `## Decided` and the new question under `## Open question`, and
move the piece from `shaping:clarify` to `shaping:prototype` or
`shaping:research` through the gate. Follow the new sub-state rather than
shaping past it. A piece whose question is settled carries `state:ready` and no
`shaping:` label, and the gate never lets the two sit together.

## A piece that came back from a build

A piece arriving in shaping with a `## Kickback` section came back from a build. Read that section first:
what happened, what was tried, and what decision is needed. Then read the
piece's comments: answers the person already left there are read before any question is asked again.
A complete answer is reconciled into `## Decided` and the fields it changes,
with the original words kept. An incomplete, unrelated or empty answer leaves the question open,
and silence or a label never supplies a decision or an acceptance.

Keep the piece's branch, and never delete it. Settle the question in the sub-state the kickback named,
rewrite the contract in `shaping:spec`, remove the old `## Readiness` result,
and run the check again. Spec cuts a new acceptance branch and names the old
one on a `Kept branch:` line, as "A spec branch that already exists" says.

## Typed alone, or given a piece

Typed alone, first take in any open issue that carries no `state:` label, such
as one opened by hand or from the form: take it in with `python3 .agents/tools/gate.py capture <number>`, and never open a second issue for it.
Then give it exactly one `type:` label before its first move, `gh issue edit <number> --add-label type:<feature|bug|chore>`,
as change-triage says under "Taking a piece in".

Then take the next piece still in shaping, in this order: a piece with a `## Kickback` section first, then a piece waiting in `shaping:check`, then `shaping:research`, which needs nobody, then `shaping:clarify` and `shaping:prototype` when the person is there, then `shaping:spec`, then the oldest `shaping:raw`.
Within one place in that order, take the oldest piece first. Pieces already
part-shaped finish before new notes start.

A piece with a `## Kickback` section is taken in as "A piece that came back
from a build" says. A piece in `shaping:check` is waiting for its readiness check: its shaping finished and the check never ran,
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
