# Pieces

A piece is one small, visible, end-to-end change, sized for a single sitting and
small enough for a fresh session to hold the whole of it. It lives as a GitHub
issue.

The project's issues are the only record of what is left to build. Keeping the
pieces there needs a GitHub repository and the GitHub command line tool signed
in, which the kit sets up when a project is founded; `capability-check.md`
records it in the capability profile.

Issues are the agent's memory rather than the person's reading material. They
can carry as much context as a piece deserves, because nobody reads them all at
once. What the person reads is `/what-now`, and a local printout of the open
issues that never becomes a source of truth.

## What an issue carries

The title says what the person will be able to do, in their words. Not a task
for the agent.

A piece has two layers. The header is short and in plain words, for the person.
The agent layer below it is complete, for the builder and for the readiness
check.

```md
## So that
<one outcome for the person, in one line>

## Done when
### Works
- <a rule somebody can check>. Check: <what proves it>
### When it is not the normal case
- <a case this change can show>: <what happens>. Check: <what proves it>
- <a case>: does not arise, because <why>

## Masterplan change
<what the masterplan gains, changes or loses when this lands, or "nothing">

## Not in this piece
<the nearest things this is not, so scope does not creep in later, and any
part of So that which Done when leaves out, with the piece that follows it up>

## Waiting on you
<only when the work cannot go further until the person does something the agent
cannot: where to go, what to do there, and what to bring back>

## Decided
<every choice a person would notice by trying the tool, with its reason>

## Data
<each stored record written or changed, or why none is>

## Leaves the tool
<what goes where, or why nothing does>

## Must still hold
<each rule, limit or time target the change touches, with its number>

## Relies on
<each existing thing used and not built here, confirmed>

## Loop
Loop module: <fix | build | goal | gauntlet>
<the bar that module needs, one line for each field it names>

## Reach
Boundary: <area>, <area>
Reaches: <area>: guarded by <existing tests, by name> | <area>: no test covers it, guarded by <acceptance check>
If it breaks: <who notices what, and how it is undone>
Depends on: <#number>, <#number> | nothing
Reach derived at: <commit>

Crew: <step> <width>, because <reason>

## Needs from the computer
Heavy: <yes | no>
Dev server: <yes | no>
Browser: <yes | no>
Expected duration: <minutes>
Cannot share: <a resource, or nothing>

<details><summary>Under the hood</summary>

<the build approach, and the existing tests this piece may change, with the
reason: the technical context a builder needs and the person never has to open>

</details>

## Evidence
<automated behaviour check | guided manual check | source-backed fact |
operational rehearsal, summarising the checks on the Done when lines>

## Readiness
<written only by the readiness check>
```

The header is `So that`, `Done when`, `Masterplan change`, `Not in this piece`
and `Waiting on you`. Everything from `## Decided` down is the agent layer.

A piece opened with the GitHub form shows every field as a `###` heading, so
Done when and "When it is not the normal case" sit side by side, and the loop
module, its bar, the reach and the crew each sit under a heading of their own.
`/shape` rewrites it to the layout above when it shapes the piece.

## Field rules

One bar applies to every piece, in proportion to the piece. Every field is
considered. A field in the agent layer that does not apply says why in one line,
such as "Data: none; this piece stores nothing." A colour change answers most
fields that way and runs only the checks its change needs. The standards always
apply.

`## So that` states one outcome for the person.

`## Done when` keeps that heading, because the printout and `/implement` read
it, and holds two groups as `###` subheadings. `### Works` holds checkable
rules, each naming its check. A rule given by examples names the class and its
edge members. `### When it is not the normal case` holds one line for each
state the change can show, such as empty, failing, slow or left part-way, each
with its check, or "does not arise, because" and the reason. If a line cannot
be answered yes or no by trying the tool, it belongs in `## So that`.

`## Masterplan change` is always on the surface, in plain words. Name the
section and what it gains, changes or loses when this piece lands. Most pieces
say "nothing", because the masterplan already describes the promised result.
Test that before writing it. Read each line of `## Done when` against the
masterplan alone, and write "nothing" only when the masterplan already says it.
A rule the person could check the tool against, such as an order, a limit, a
default or a message, is a change even when it narrows a promise the masterplan
already makes. A piece that puts an existing list in alphabetical order gains
that rule in `What correct looks like`.
This is the piece's delta, meaning its change to the present record. Writing
it does not apply it early. The save and recovery rules live in
[masterplan-changes.md](masterplan-changes.md).

`## Not in this piece` is required on every piece. It names the nearest things
this piece is not, so scope does not creep in later. Where Done when does not
deliver all of So that, it also names the gap and the piece that follows it up.

`## Decided`: every choice a person would notice is decided here, with its
reason, so nothing a person would notice is left for the build to choose. A
piece where no such choice exists says so in one line.

`## Data` covers each stored record the piece writes or changes: where it
lives, who else writes it and how the writes merge, the order on first open,
limits and what goes at the limit, backup and restore, and delete and undo.

`## Leaves the tool` covers what goes where, whether the recipient is new,
which keys, the gate that decides who can reach it, and whether the build
path's personal-data line changes.

`## Must still hold` names each rule, limit or time target the change touches,
with its number and where it is measured, and which rule wins where two apply.

`## Relies on` names each existing thing the piece uses, confirmed to exist and
to give the data needed, by reading or trying it.

`## Loop` holds `Loop module: fix | build | goal | gauntlet` and the bar that
module needs, one line for each field:

- For `build`: `Acceptance branch:`, the branch that holds the acceptance
  checks, and a `Check:` on every Works line, written
  `Check: <path of one test file on the acceptance branch>`. A project with no
  code yet carries the branch too, cut after the person's yes to the first
  upload.
- For `fix`: `Acceptance branch:`; `Reproduction:`, naming one test file on
  that branch that fails today, in the same form as `Check:`; and
  `Must not change:`.
- For `build` or `fix` where AGENTS.md's stack section records
  `Test command: none for <language>`: `Test runner:`, naming the runner
  [check-floor.md](check-floor.md) names for that language. The checks are
  written for it.
- For `goal`: `Metric:`, `Measured by:` (a command), `Target:`, `Budget:`,
  `Guard checks:` and `Held-out check:`. The held-out check is written as a
  command, then `on held-out/<number>-<short name> at <commit>`, the branch
  and commit the spec step writes.
- For `gauntlet`: `Reference:`, a link that can be fetched, with the person's
  approval and its date; `Compared by:`; `Budget:`; and `Guard checks:`.

A line the module does not need is left out, never written as "none", because
the module says which lines a piece needs.

`## Reach` holds five lines, and replaces the one-line `Touches:` an older
piece may carry:

- `Boundary:` names the areas the piece may change, as
  `Boundary: <area>, <area>`, each named by the skill, record or document name,
  never a file path, because paths go stale.
- `Reaches:` names the areas it affects without changing them, each with the
  existing tests that guard it by name, or "no test covers it" and the
  acceptance check that guards it.
- `If it breaks:` says who notices what, and how it is undone: a rollback, or
  not reversible because of data.
- `Depends on:` gives `#<number>` for each piece it needs, separated by commas,
  or `nothing`. The numbers match the piece's blocked-by links.
- `Reach derived at:` names the commit the reach was worked out on.

The ready-gate lint reads area names from a piece in one fixed way.
`Boundary:` is a comma-separated list of area names on one line. Each entry
under `Reaches:` begins with an area name followed by a colon, and the tests or
"no test covers it" follow the colon. A name is matched whole, ignoring case
and surrounding spaces, against the names `area-map.py areas` prints, so an
area name holds no comma and no colon. The areas are the ones in the Areas section
of `docs/working-rules.md`. The lint refuses a piece that names an area the
map does not hold, and one whose boundary or reach holds an area with a
`sensitive:` line whose caution is neither done nor accepted.

The person reads the reach as one sentence, such as "This changes sign-in. It
also reaches billing, which 14 checks guard. If it breaks, people cannot sign
in, and a rollback undoes it."

`Crew:` is written only where the crew differs from the loop module's default,
as `Crew: <step> <width>, because <reason>`, with no heading of its own. The
step is one of `research` (readers, cap 5), `prototype` (variants, cap 3),
`fix` (reading probes, cap 3), `goal` (race entries, each in its own worktree,
cap 3) and `gauntlet` (critics, cap 3). The width counts that step's members
and never the builder. A `Crew:` line naming the build or readiness check step,
naming the run, or asking for more than one builder is a crew with two
writers, and is refused.

`## Needs from the computer` holds `Heavy:`, `Dev server:`, `Browser:`,
`Expected duration:` and `Cannot share:`. They say whether the piece runs
something heavy, such as a container, a model download or an index build,
whether it needs a dev server or a browser, how long it should take, and any
resource it cannot share with another piece.

`Under the hood` holds the build approach, and the existing tests this piece
may change, with the reason.

`Under the hood` also holds a `Changes the bar:` line for each guarded change
the piece needs, one path to a line, written as `Changes the bar: <path>,
because <reason>` with the whole path. A guarded change is one the bar guard,
the `section-builder` skill's `scripts/bar-guard.sh`, lists: a lint or type
suppression, a skip or focus marker in a test, a line added to or taken out of
a test, lint, type-check or coverage tool's settings, an updated snapshot, or a change to a
workflow, a hook, the gate's scripts or the Claude Code settings.

A guarded change counts as named only on a `Changes the bar:` line under `Under the hood`,
and the gate refuses to send a piece to review with one the piece did not name.
A named one still goes to the person's review. The ready-gate lint lets a path
stand on that line. Write it while the piece is shaped: once the piece is ready
its contract is fixed, and a change to it during the build sends the piece back
to spec.

`## Evidence` names the kind of proof, summarising the checks on the Done when
lines.

`## Readiness` is written by the readiness check and read by every later step.
The check and the section are described in the `shape` skill's
`references/readiness-check.md`.

## The brief rules

The contract is a brief for a builder who works alone and never sees the
shaping conversation. Three rules keep it usable that way:

- Behaviour rather than steps. The piece says what the tool does once it
  lands, and leaves the order of the work to the builder.
- Interfaces rather than file paths or line numbers. The piece names a route,
  a command, a screen or a record. A path belongs only in `## Relies on` and in
  the lines that name a check or a test, because those name the evidence.
  `Under the hood` is the one further place, and only for a test file. The
  test guard in the `section-builder` skill's `scripts/test-guard.sh` lets an
  existing test change only when `Under the hood` names it by its whole path.
  A line number there is still refused, and so is any other path, except on a
  `Changes the bar:` line.
- Each acceptance criterion checkable on its own. Every Works line names its
  own check, and no line passes only because another one does.

## Rules that are not fields

- No open choice a person would notice. The refused phrases, and the rule that
  a vague count or size needs a number, are item 10 of the list in
  the `shape` skill's `references/readiness-check.md`.
- Lists are complete: a list of examples does not stand in for the whole.
- Each Done when line is false on today's code and true after, through this
  piece alone.
- Split, never shrink. No stub, placeholder or "for now" stands in for a line.
- A missed number is a fail, stated at the top of the pull request.
- Report a wrong test or an impossible line. Never work round it.

## Decisions and what they rest on

A decision in `## Decided`, or a key term or decided line in the masterplan,
may carry an optional one-line "rests on" clause in plain words. This applies
on every build path. Name what supports it: a test, a piece, a source, or a
person's answer with its date. For example: "A returned item can be booked
again; rests on the returning-early check." Leave the clause out when there
is no evidence to name. Never invent support to fill the line.

Before relying on a clause, read the thing it names against the current
branch or source. A missing or contradicted source no longer supports the
decision. An unreachable source is unconfirmed, rather than gone. Say which
in one plain line, without asking the person to read code or understand a
test name. Keep the decision visible until it is settled through the command's
usual route; a missing source is not permission to reverse the decision.

## Waiting on the person

`## Waiting on you` is left out unless a step belongs to the person, and for a
stronger reason than any other field: it is
the one thing on a piece that only the person can clear. It appears when the
work stops until they sign up for something, hand over a key, or move some data
themselves. Write it as something they could follow without help, and never ask
for something the agent could go and do instead. It never carries the secret it
asks for: say where the key goes, and the key itself stays out of every tracked
file, as it always does.

A piece with a `## Waiting on you` step sits in `shaping:clarify` until the step is done, so no run takes it.
Two other pieces come back from a build to shaping, and each says why in a
`## Kickback` section rather than here. A piece stopped at a sensitive-area caution is kicked back to `shaping:clarify` with a `## Kickback` section naming the caution,
and stays there until the acceptance is recorded. A piece that failed three attempts is kicked back to `shaping:spec` or `shaping:research`,
by what the attempts showed.

One line looks alike and means something else. A piece carrying a
`Waiting on you: try it` line is built as usual. The line sits on its own rather
than as a section, and asks for the person's own try before the piece is saved:
once it is built, section-builder gives them an address and up to three things
to try, and waits. A `check-myself|yes` line in `.ai-build-kit-maintenance`
asks the same for every piece.

## The two layers of a piece

The header stays in plain words and short, and it stays honest about anything
that affects the product, so a simple read is never a false one. The agent layer
is complete. A fact belongs on the piece when it would change what a person sees
or does, what is stored, or what leaves the tool: put it in `## Decided`, `## Data`
or `## Leaves the tool`, in words the person would use. A fact belongs under the
hood when it only affects how the code gets written.

`Under the hood` is a collapsed section for that build context: the approach and
the tests the piece may change. The person never has to open it, and
`section-builder` always reads it before building. This is the same principle
the issue already follows, that an issue is the agent's memory and carries as
much context as a piece deserves.

Context that reaches past one piece does not live here. A decision that affects
the whole product goes in the masterplan, in plain words. A technical convention
that affects the whole codebase goes in AGENTS.md's stack section, as one short
rule. Lasting technical design goes in its own `docs/<concept>.md`, one concept
to a file, listed in `docs/README.md`, as the `section-builder` skill's
`SKILL.md` routes it. The piece
holds only what is particular to it.

## Labels

A piece carries every subject label that fits it, from the same small vocabulary
the consequence classification uses. Most pieces have one:

| Label | What the piece is about |
|---|---|
| `visual` | the interface, what people see and click |
| `how it works` | the rules and logic |
| `data` | information the tool stores |
| `accounts and permissions` | who can get in and what they can see |
| `finance` | charging, refunds, pricing, invoices |
| `external service` | somebody else's system that this piece needs |
| `background automation` | something that runs on its own, with nobody watching |

A subject label is not a description of the piece. Each one decides evidence and
a save route, so `section-builder` reads the labels rather than re-deriving them.
Where a piece carries more than one, its evidence is everything those subjects
demand between them, and its save route is the strictest of the ones present.

Ticking every subject that fits, rather than the closest single one, stops the
kit dropping a true fact about a piece: a checkout is `finance` and
`external service`, and picking one would lose the evidence the other requires.

### States

Every open piece is in exactly one of four states, and one label says which.
The four, in the order a piece moves through them:

- `state:shaping`, not ready to build yet;
- `state:ready`, shaped and checked, and waiting to be built;
- `state:building`, while somebody or a run is building it;
- `state:in-review`, built with every check green, and waiting for its review.

Exactly one `state:` label sits on an open piece, never two. Two state labels
on one piece is a mistake, and the printout names it under Needs attention
rather than guessing which one is true.

A closed issue is done, or was dropped, and carries no state label.
`gate.py tidy` takes the labels off a piece once it closes.

An open issue with no state label has not been taken in yet. Anybody can open
one by hand or with the form, and nobody has to label it. The printout names it
under Needs attention as having no state, and `/shape` takes it in with
`gate.py capture <number>` rather than opening a second issue.

A parent, an issue with open parts, carries no state of its own: its parts
carry the states. The gate refuses to capture or move a parent, and the
printout lists it under Made of parts.

Held up by another piece is never a state or a label. It is a blocked-by link
(see Status, owner, and order), so a ready piece waiting on another stays
`state:ready`, and the printout shows it as held up.

### Shaping sub-states

A piece in `state:shaping` carries one shaping sub-label, which says where its
shaping stands:

- `shaping:raw`, captured in the person's words and not looked at yet;
- `shaping:research`, waiting on something from outside the project: a fact to confirm, or existing work that might already do the job;
- `shaping:clarify`, waiting on a decision only the person makes;
- `shaping:prototype`, waiting on a decision the person has to see first;
- `shaping:spec`, with no question left, while its contract is written;
- `shaping:check`, waiting on the readiness check.

Exactly one `shaping:` label sits beside `state:shaping`, never two, and never
beside another state.

Three of them say the piece is waiting on a question, and each says who can
answer it:

- `shaping:clarify`, when talking it through will settle it. The person has to
  be there: an interview the agent answers itself is a guess with a record
  attached.
- `shaping:prototype`, when only something to look at will settle it, whether a
  throwaway build or a mock the person already has. The person has to be there,
  because reacting to the thing is the whole point.
- `shaping:research`, when it needs something from outside the project. The
  agent settles this one alone, with nobody present.

So the label already says whether the person is needed, and the list shows it at
a glance. No further label carries that.

They cost different amounts to settle, which is why `/shape` names the cost in
one line before it starts a sitting, so the person can say "later" and file the
piece instead. Research is minutes, and nobody has to be there for it.
Clarify and prototype are a sitting: an interview runs until the questions run
out, and a prototype has to be built before anybody can react to it. Keep the
estimate that coarse. A real estimate per piece would be a guess dressed as a
number.

A question goes under `## Open question` on the piece, one question to a piece,
before the piece moves to the sub-state that answers it. Settling it writes
what settled it onto the piece before the label comes off: the fact and where
it was found under `## Research`, or under `## Decided` the decision the
prototype produced or what the interview agreed. Without that the label is the
only sign the question was ever asked, and taking it off leaves a piece that
looks the same whether the work happened or not. The gate holds this: it will
not move a piece out of research, clarify or prototype until the section that
records the answer has changed since the piece arrived there.

A piece with no question left moves to `shaping:spec`, and to `shaping:check`
once its contract is written. The readiness check runs there. Only a
`## Readiness` section saying Ready with no blocking line lets the gate move it
to `state:ready`, so every ready piece carries a section that, written by a
session that did not shape it, names no blocking gap. Not ready sends it back to the sub-state that closes its
gaps, as the `shape` skill's `references/readiness-check.md` says. A piece never reaches `state:ready` with a question open.

### Review sub-labels

A piece in `state:in-review` carries exactly one review sub-label: `review:auto`
while it waits on the automatic review, or `review:person` while it waits on
the person's. Until the automatic review exists, every piece reaching review
gets `review:person`, so nothing waits on a reviewer that is not there. Neither
sits beside another state.

### Type and loop

Every piece carries exactly one `type:` label, given when it is captured and
before its first move:

- `type:feature`, something new the tool does;
- `type:bug`, the tool does not do what the masterplan promised;
- `type:chore`, upkeep nobody would notice in the tool.

A repair is a `type:bug` piece, and the printout marks it in whichever column it
sits. A `loop:` label, one of `loop:fix`, `loop:build`, `loop:goal` and
`loop:gauntlet`, names the loop that builds the piece.

### Only the gate moves a piece

Only the gate script, `.agents/tools/gate.py`, changes a state, a sub-state or a
review label. It reads the piece, checks the condition for the move, writes the
new labels and takes the old ones off in one call, and refuses when the
condition fails. A refusal says what failed and gives the next command to run.
The `type:`, `loop:` and subject labels are not states, so a command adds them
with `gh issue edit`.

`gate.py report` names every open piece whose labels are out of order, and
changes nothing. A person can still change a label on GitHub. The person
outranks the gate, so the report names what it finds and never puts it back.

`/queue` reads `state:ready` to answer a different question: not which piece is
next, but which of them can be taken on at the same time. A piece can be shaped
and still be held up, so `state:ready` alone does not mean startable. What
`/queue` offers is the ready pieces the printout has already put under
`To build`, and a piece with an open blocker is never there. That is what makes
the group safe to take on at once: no two pieces in it are waiting on each
other. The printout also compares their `Boundary:` lines and prints the pieces
in groups, two pieces naming the same area never in one, and `/queue` reads the
groups rather than working them out again. The pieces of one group can be built
at the same time in any order, and each still merges one at a time, brought up
to date with `main` and checked again first. Shape still decides too, so a
piece somebody labelled `state:ready` without giving it a `## Done when` is a
note, and `/queue` does not offer it either.

Those 26 are the only labels the kit owns: the four states, the six shaping
sub-states, the two review sub-labels, the three types, the four loops and the
seven subjects. `gate.py labels` creates them. Any other label on an issue
belongs to somebody else, so the kit reads past it and never removes it. That
includes the labels of AI Build Kit's model: `idea`, `shaping`, `ready`,
`building`, `to check`, `parked`, `blocked`, `broken` and its three `needs-`
labels. `gate.py report` names each as a label the kit does not use and leaves
it alone, and nothing moves a project's issues off them.

The nine labels GitHub puts on a new repository are the one exception, and only
at founding. `bug`, `documentation`, `duplicate`, `enhancement`, `good first
issue`, `help wanted`, `invalid`, `question` and `wontfix` were nobody's
decision: they were there before anybody arrived. `/setup-ai-build-kit` deletes them and says
which ones went. After founding they are somebody's to keep, so the ordinary
rule applies again and the kit leaves them alone.

Founding creates the kit's labels with `gate.py labels` before the first issue,
so a piece can carry its state from the day it is opened. Where the person's
account cannot create one, because they are a collaborator without write access,
the gate names each label it could not create and creates the rest, and the work
carries on. A piece that cannot be labelled is still a piece.

## Status, owner, and order

Closed already means done, so no label repeats it. An open piece carries one of
the four states above, with its sub-label where the state has one, and nothing
else says where it stands.

The assignee is who is building it. This works the same whether one person or
five are on the project, so nothing changes on the day a second person arrives.

Dependencies use GitHub's own blocked-by relationship, not a line of prose. A
piece that needs another names it there, and the agent reads it rather than
parsing a body.

A piece with parts uses GitHub's own sub-issue relationship. The two
relationships answer different questions, and the answer decides which to use. A
sub-issue is a part of the same outcome: it shares the parent's `## So that`, and
the parent is not done until its parts are. A blocked-by piece is a different
outcome that must land first. Same outcome means a sub-issue; a different outcome
that has to come first means blocked-by. A piece too big to hold whole in a fresh
session is split into sub-issues, each a vertical slice of its own.

When a build uncovers work and files a new piece, write "Found while building
<piece title>" on the new piece's surface, with the title linked to the piece
that surfaced it. The originating piece's record names and links to the new
piece too, so either one leads to the other.

Parts of the same outcome stay sub-issues. A find with a different outcome gets
the found-while-building link; it gains a blocked-by relationship only if one
piece really must land before the other. Finding work does not add it to the
piece being built.

`/implement` takes the lowest-numbered `state:ready` issue whose blockers are all closed
and whose subjects the current build path all permit. A parent with open children
is a container rather than a buildable slice: `/implement` builds the children,
and the parent closes when they all close. This is what keeps the two ways of
being not-ready apart. A blocker is a different piece that must land first; an
open child is a part of this piece still to build. Issue numbers give a stable
creation order and the two relationships give the structure, so nothing extra is
maintained by hand.

## An issue somebody typed by hand

Anybody can open an issue, from a phone, in half a sentence. That is a request
rather than a piece, and it cannot be built or proved as it stands.

Shape is what decides, not who wrote it or whether anyone remembered to mark it.
An issue with no `## Done when` has not been sized. Where it carries no state
label, `/shape` takes it in with `gate.py capture <number>`, which gives it
`state:shaping` and `shaping:raw` and keeps its title and body, so somebody
reading the list on GitHub can tell which entries are still notes.

Shaping it decides whether a question is open. If one is, write it under
`## Open question` and move the piece to the sub-state that says who can answer
it (see Labels above). Say which you moved it to and why, because a label change
nobody explained reads as the agent losing track.

Refining one produces the shape above. Keep what the person originally typed
underneath, under "Original report", rather than replacing it, because their words are what a refinement
can be checked against and what to return to when it reads wrong.

## When somebody acts on GitHub

The issues are shared, so people assign, close, label and edit them by hand.
Three rules settle nearly every case.

A person's action wins. The agent never undoes something somebody did on
purpose. It can say what it found, and then it works with what is there.

Absence is not a decision. A piece carrying no subject label is unclassified
rather than assumed to be `how it works`. Several subject labels are not excess,
because a piece is allowed to be about more than one thing.

The agent says what it found. It does not quietly reshape a project back into
the form it expected.

| What the person does | What the kit does |
|---|---|
| Assigns themselves | Treats the piece as theirs, and `/implement` will not hand it to anyone else. Assignment says whose it is; `state:building` says work is under way now |
| Assigns somebody else | `/implement` skips it and says who has it, rather than quietly taking it |
| Adds or changes a state label | Leaves it. `gate.py report` names anything out of order, and nothing is put back |
| Closes an issue by hand | It stays closed. `/sync` may say that no changelog line matches it, counting an entry waiting in `changes/` as a line, and ask whether it was done or dropped |
| Reopens a closed issue | Treats it as work again. With no state left, `/shape` takes it in with `gate.py capture <number>` |
| Edits the body so `## Done when` is gone | Treats it as a request rather than a piece, and refines it before building |
| Adds labels of their own | Leaves them alone |
| Puts two subject labels on one piece | Takes both, and satisfies what each one demands |
| Leaves the subject off | change-triage classifies it when the piece is refined |
| Uses milestones or a project board | Ignores both, and neither reads nor writes them |
| Deletes an issue | Lets it go. If a branch still refers to it, `/sync` says so |
| Fills the issue form in properly | Nothing special. It is a piece, and it gets built |

## Speaking for the person

Whatever the agent posts under the person's account, somebody else reads as the
person speaking. So anything another person will read that way waits for a yes
that covers those exact words. Show the words first, then ask. This covers:

- a comment or a reply on an issue or a pull request;
- a review of a pull request;
- a mention of someone by their GitHub name, because GitHub tells them;
- a message in any other channel the agent can reach.

The same yes is needed before changing the title, the `## So that`, the
`## Done when` or the scope of an issue or a pull request that another account
opened. Adding the shaped sections above the original, kept whole, is not such
a change. Read the author with `gh issue view <number> --json author`, or
`gh pr view <number> --json author` for a pull request, and compare it with
`gh api user --jq .login`. When the author cannot be read, for example because
GitHub cannot be reached, treat it as another person's and ask.

Some writing is the kit's bookkeeping. These say nothing in the person's voice,
so they need no yes, on anyone's issue:

- the labels the gate writes, and the `type:` label a piece gets when it is taken in;
- the claim comment a run writes;
- the one comment naming the conflicting files when a merge from `main`
  conflicts;
- the title and body of a pull request the kit opens for a piece;
- a `Closes #<number>` line;
- the question a run or `/shape` writes on a piece it sends back to shaping;
- the readiness check's gaps and its `## Readiness` section;
- the shaped sections added above a kept original;
- the person's own words added as a comment when they asked for exactly that,
  such as capture adding them to a matching issue, whoever opened it.

When the person says "tell them" something, that is the yes for those words.
Write what they said, show it, and post them with no second question. Where you
add or change words, ask about the new version.

When the person says no, post nothing. Give them the words, so they can post
them themselves if they want to.

A run with nobody watching posts nothing in the person's voice, and it changes
no title or scope on an issue or a pull request another account opened. Its
bookkeeping still goes on. What it would have said goes into its report for the
person to read.

## The local printout

`plan.local.md` is a printout of the open issues and nothing else. It is
gitignored, so it is one person's view of a shared record and can never collide
with anyone else's.

Information flows one way: issues are the record, and the printout is made from
them, never read back. A change to a piece goes to the issue, and the printout is
made again with `sh .agents/tools/plan-refresh.sh`, so if it looks stale,
refresh it. Run the refresh when reading or changing the plan rather than on
every session start, so a session that never touches the plan stays light.

Founding copies that helper into the project from this skill's
`templates/foundation/plan-refresh.sh`, whichever route installed the kit, and
`/maintain` adds it to a project founded before it shipped. Where a project
still has no copy, run the same file from the installed setup-ai-build-kit
skill, from the project's root folder, and say in one line that the next
`/maintain` adds it to the project. Never sort the pieces by reading the issues
by hand instead. The printout is what keeps a piece with an open blocker out of
`To build`, and a hand reading once named a blocked piece as the next one to
build.

The printout reads the states as the columns of a board. It prints, in this
order: Needs attention, then one column for each shaping sub-state, then ready,
building, and in review split into waiting for you and automatic, and last Made
of parts. Within ready, the pieces free to start are headed `To build`,
followed by `Go together`, and the ones waiting on another piece are headed
`Held up`, each naming the piece holding it.

Needs attention lists the findings `gate.py report` would print: a piece with no
state, two states, a sub-label beside the wrong state or missing, a parent
carrying a state, and a label from AI Build Kit's model. The printout takes them
from the gate script beside it rather than working them out again, and such a
piece prints once, there. It also lists a `state:ready`, `state:building` or
`state:in-review` piece that skipped a step. With no `## Done when` it says the
piece was never shaped. For a piece being built or reviewed, with a Done when
but no `## Readiness` section it says the piece had no Readiness check. Where
both are missing, only the first is said. A piece being built or reviewed stays
in its own column as well, because somebody really is building or reviewing it, while a ready one stays
out of `To build`. A parent gets neither note. A parent with open parts carries
no state of its own and prints under Made of parts. A `type:bug` piece carries
a `(bug)` mark in whichever column it sits. A closed issue never prints.

`Go together` puts the pieces under `To build` in groups by their `Boundary:`
lines. A piece with no `Boundary:` line, such as an older piece that carries
only `Touches:`, goes alone. A held-up piece is marked `(in the plan)` when
every open blocker in its chain is ready to build too. A ready piece carries the marks a run's verdict
needs, read from its body: `(needs you)` for a `## Waiting on you` step other
than `try it`, `(not ready)` and `(not yet checked)` from its `## Readiness`
section, `(try it)` for a `Waiting on you: try it` line, and on a held-up piece
`(waits for ...)` when it stacks on one a run cannot take.

When a command names what can be built next, it names a piece under `To build`
marked `(ready)` in a printout it has just refreshed, and nothing else. Where
that group holds no such piece, say that nothing is ready to build now and what
the rest are waiting on, and name no piece as next.

When a refresh fails, follow [required tools](required-tools.md),
"When GitHub access fails", before concluding GitHub is unavailable. That
route requests access through the client when permission is the missing part.

It carries the time it was written, which is what makes it safe when GitHub is
unreachable. A refresh that cannot reach GitHub leaves the last printout as it
was and says when that one was written. The agent can say "here is your list as of 18:40, and I cannot
reach GitHub to confirm it is current" rather than leaving somebody with
nothing. Work that would change the plan waits until GitHub is back, because
the agent will not update issues it cannot see. The piece already in hand
carries on.

One call to GitHub covers the whole backlog. The issue list carries a
dependency summary, so whether a piece is held up by another is known without
asking about each one. Only the pieces that are actually blocked need a second
call, to name what is holding them.

## Ideas left out

An idea deliberately left out is closed as not planned with
`gate.py drop <number> --reason "<why>"`, which writes the reason as a comment
and takes its state labels off. Closed, so it never reads as work waiting to be
done.

Before accepting a request as new, search closed issues too. The reason exists
so the same idea does not come back around and get built by accident.
