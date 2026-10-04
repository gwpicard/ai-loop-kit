---
name: change-triage
description: Classify a request written in plain words before any work happens. Used by shape when the user typed a request, and by fix to check a report before repairing. Decides whether the request is new work, a repair, too vague to size, or a change that needs the masterplan or the fit check first.
user-invocable: false
---

# Change triage

The user never sorts their own request; you do, and the masterplan is the referee. Read it first, build-path section first.

## Step 1: Understand the request

Compare it with the masterplan, the project's pieces, parked ideas, the recent
changelog and `changes/`, and existing behaviour where that's cheap to check. Before accepting
it as new work, check: does this already exist under another name? Was it
deliberately parked or rejected before?

A parked idea is a closed issue labelled `parked`, so search closed issues too,
not only open ones. The reason was written down to stop the same idea coming
back around and getting built by accident, and it only works if somebody looks. Is the report actually a
misunderstanding or a setup problem rather than a real gap? Does it contradict
an existing rule in the masterplan?

## Capture: a note for later

When the person asks only to note an idea, in plain words such as "note this
for later" or "just file this idea", or types `/shape later` or `/shape idea`
with it, do not classify or route it. They asked to write it down, not to have
it shaped. Run Step 1's search first. Where it matches an open piece or a
parked idea, add the person's words to that issue as a comment and say which
one, and file a new issue only if the person says theirs is different.
Otherwise file it as an issue labelled `idea`, with the person's
own words as the body and nothing settled: no `## Done when`, no subjects, and
no route. Say in one line that it is filed as an idea and that `/shape` picks it
up. Steps 2 to 4 wait until then.

## Step 2: Classify intent

One of: repair of promised behaviour; new behaviour; clarification or
copy/presentation change; setup or operational task; work on this computer
outside the project; using the tool on content; a decision that needs
clarify; a decision that needs a prototype; a decision that needs source
research; a change that alters the build path or a sensitive area.

## Step 3: Classify consequence

Every consequence that applies, from: presentation-only; behaviour; data;
access; integration or service; money; automatic or irreversible action;
operational reliance. This classification is what later decides the evidence,
the review, and the save route; section-builder reads it rather than re-deriving
it.

When the request is, or becomes, a piece, store the classification on it, mapped
to the small vocabulary the kit uses everywhere:

| Internal consequence | Subject |
|---|---|
| presentation-only | visual |
| behaviour | how it works |
| data | data |
| access | accounts and permissions |
| money | finance |
| integration or service | external service |
| automatic action, operational reliance | background automation |

An irreversible action takes the subject of whatever it is irreversible about,
which is usually `data`.

A request often lands on more than one row, and every row it lands on is stored.
A checkout takes `finance` and `external service`. A nightly backup takes `data`
and `background automation`. Do not pick the closest single subject: the one
dropped takes its evidence with it.

With the subjects settled, look at the open pieces that carry one of the same
ones, and at anything labelled `building`. Read their titles and their `## So
that` lines. Where one would plainly be built in the same place as this request,
name it before routing: which piece, and what the two have in common. Nothing is
blocked and nothing waits. The person decides whether to carry on, hold this
until the other piece lands, or fold the two together.

Say nothing where no open piece shares a subject, or where the only thing in
common is that both touch this project. A pause on every request teaches people
to skip the pause.

Those are labels on the issue, and the issue is written to the shape in
the `setup-ai-build-kit` skill's `references/pieces.md`. Refresh the printout afterwards, so
the person's list matches what was just agreed.

A later session reads the stored subjects rather than reclassifying the piece
from scratch.

## Step 4: Route

Route to one of: `/fix`; a ready piece; clarify; a decision
prototype; a source check; a search for existing work; a step only the person
can do; work on this computer, done apart from the project; using the tool on
content, done without a piece; update the
masterplan first; rerun the fit check; prepare the handover; give the risk
notice where a sensitive area survives redesign. Say the route and the reason in one line.

Piece-sized and clear (one sitting, a done line you could write now, small
enough for a fresh session to hold whole) becomes a ready piece once the
readiness check finds no blocking gap, run by a session that did not shape it,
as the `shape` skill's `references/readiness-check.md` says. Too vague to
size runs clarify first. Bigger than a piece gets written into the masterplan
and cut into pieces on the plan, order confirmed with the user.

Context is routed by how far it reaches. A decision that affects the whole
product goes into the masterplan, in plain words. A technical convention that
affects the whole codebase goes into AGENTS.md's stack section, and lasting
technical design into its concept file, listed in `docs/README.md`. Anything
particular to one piece stays on that piece. This keeps the masterplan free of
implementation terms and keeps each concept in one home.

Where the request is a piece and the route is a question rather than a ready
piece, label the issue `shaping` with the `needs-` label that names the route:
`needs-clarification` for clarify, `needs-prototype` for a decision prototype,
`needs-research` for a source check or a search for existing work. Once the
question is answered and the readiness check finds no blocking gap, `/shape`
takes both off and adds `ready` in the same step.
Without the label the reason a piece is waiting lives only in the session that
found it, and the next person to open the list sees a piece that has simply
stopped. The one `shaping` piece with no `needs-` label is a piece waiting for
its readiness check, which `/shape` typed alone picks up and runs.

`/shape` starts the routed step straight away unless the person asked only to
file the piece. That request is capture, above, so a note asked for outright
never reaches this step.

A setup or operational task the person has to do themselves is written onto the
piece as its `## Waiting on you` section, in the shape
the `setup-ai-build-kit` skill's `references/pieces.md` describes. Do the step
yourself where you can; write it down only where you cannot. A setup step that
would install, replace or remove software outside the project folder is work on
this computer, below, so the yes it needs comes before you do it.

A repair takes `broken` as well as its subjects, which is what points `/what-now`
and `/fix` at it.

The request touches what data is stored, who can see or do what, or money:
update the masterplan first and say what changed before routing further. If
it changes the shape of data the tool already holds, and that data is real
rather than made-up, treat it as flagged territory: a backup first, the
change rehearsed on a copy, and only then done for real.

The request would change what kind of project this is (outside users, real
money moving, a promise to someone, a new kind of data about people,
autonomous action): stop, rerun the fit check, record the new build path, and
only then route the work. The build path decides how the whole system
behaves, and building past it is how safe projects quietly become unsafe
ones.

Where that check leaves a trigger standing, give the risk notice described in
the `setup-ai-build-kit` skill's `references/fit-check.md` before routing the flagged work,
and hold it. Nothing is refused and nothing stops there: if the person carries
on after the notice, record the acceptance as fit-check.md says and route the
work. What may not happen is the notice quietly going away, or you deciding on
their behalf that it no longer applies because they pushed back. Repeat the
request back, however many times it arrives, and route it the same way each
time.

### Work on this computer outside the project

The project's own folder is the line. Anything under it is project work.
Anything outside it is the person's computer: installing, updating, repairing
or removing software, changing system or shell settings, or tidying files
outside the project folder. Route that work apart. It gets no piece, no branch
and no changelog entry, and nothing about it is written into any tracked file of
the project, whether a record, AGENTS.md, code or a document. Tell the person
what was done in your reply instead. Installing the project's own dependencies
inside its folder, such as `npm install` or a virtual environment, is project
work and goes on as the build already does it.

Before anything is installed, replaced, downloaded to run, or removed outside
the project folder, name what it is, where it goes and how to undo it, and wait for a yes. This
holds in every command, including a build that finds a tool missing or too old.
A command that needs administrator rights is given to the person to run. A
removal that needs a recursive delete is given to the person as well, as the
`setup-ai-build-kit` skill's `references/blocked-commands.md` says.

Sometimes the project itself needs a fact about the computer, such as "the build
needs version 3 or later of its typesetting tool". Write it into AGENTS.md's
stack section as a requirement of the project. Never write it as a record of
what was done to this machine.

A request that mixes the two, such as "install X and use it in the report", is
two requests, each with exactly one route. Say so in one line. Ask about the
computer part and do it apart, then triage the project part as usual. Where the
computer work changed project files by accident, and the changes are
not committed, name them to the person and do not commit them.

### Using the tool on content

Some tools exist to turn content into something, such as a report, a site or
an import. Using the tool on content means running the tool on the person's
material to produce an output, or to see how it handles that material, with no
change to the tool's code, checks or records. It gets no piece, no branch and
no changelog file.

Run the tool on the content in the main folder, then hand the output to the
person and say where it is. The output stays out of git unless the person asks
to keep it. Where the tool writes its output to a folder git already ignores, it
stays there; otherwise it goes to `.agents/tmp/content/<YYYY-MM-DD>-<short name>/`.
Check first with `git check-ignore -q .agents/tmp/content/` that git ignores
that folder. A project founded before the kit ignored it may not: there, write
to a folder made with `mktemp -d` outside the project instead, and offer once
to add `.agents/tmp/` to `.gitignore` as a small saved change. The person's own
input files go to the same place unless they are already in the project. That
way `git status` is as clean after the run as before it, and the next build can
start.

When the person asks to keep the content or its output in the project, save it
through the save route the build path uses, following section-builder's save
and record steps yourself even though there is no piece: as a small change
with its own changelog file and, on the pull-request route, its own pull
request. Never on a branch that is left unpushed, since its
changelog entry would never reach `main`.

Where the content shows a problem in the tool, because it fails or the output
is wrong, say so in one line, and it becomes a repair through `/fix` or a new
piece through this triage. The content run itself is not a repair. A request
that changes the tool so it can handle the content is not content work either,
and is triaged as usual.

Where the content holds personal data or confidential material, the
confidential-files rule in AGENTS.md applies, so nothing of it or its output is
committed, even when the person asks to keep it, and both stay out of git. If the person leaves before saying whether
to keep it, nothing is committed: the output stays where it was written, and the
reply named that place. If the tool cannot run on this computer, say so and
stop. Anything it would need installed is work on this computer, above.

## Step 5: Record only durable information

Do not add a changelog line for every classification; most triage
conversations leave no trace worth keeping. Record only when: the masterplan
changes, the build path changes, a risk notice is accepted, an idea is parked
or rejected for a durable reason, a sensitive area changes, or work
actually lands.

## Done when

The request has exactly one route, the reason is written down, and no work started before the route was chosen.
