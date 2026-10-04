---
name: section-builder
description: Build one piece from the plan to a confirmed, saved change. Used by implement for every piece and by fix once the cause is known. Refuses to start on top of uncommitted work. One piece per pass, always.
user-invocable: false
---

# Section builder

You build one piece, directed by someone who will judge it by behaviour. Follow the order.

## 1. Safe start

Read the piece in full, including its `Under the hood` notes, the masterplan's
build-path section, and any whole-product decision in the masterplan or
whole-codebase convention in AGENTS.md's stack section that the piece points to.
Read too each concept file the piece touches, from the list in
`docs/README.md`, since that is where the design it builds on is written.
The under-the-hood notes carry the build context so this does not have to be
worked out from nothing. Check git status; if uncommitted
work is lying around, stop and say so: it gets finished or cleared first
(what-now owns that conversation). Never build on top of half-done work.
Bring the shared `main` branch up to date and start the piece from it, on every
save route including the checkpoint route, so no piece begins from a stale copy.
Two starts differ, as the `implement` skill's `references/running-longer.md`
says. On Claude Code, a piece in a run starts in its own worktree under
`.agents/worktrees/`, with its dependencies installed there before its start
ritual, and the main folder is never switched to the piece's branch.
A piece in a run that stacks on another piece built in that run and not yet
merged starts from that piece's branch, in a worktree of its own on Claude
Code, and a later part of a parent continues on the branch, and in the
worktree, its first part cut. Where `main` cannot be reached, start from the
local copy and note that in one plain line.

Choose the save route before changing anything:

1. **Checkpoint route.** Private or disposable exploration, with no shared or
   live reliance and no change to data, access, integrations, money,
   autonomy, or operations.
2. **Pull-request route.** Shared or live use, a behavioural change, data or
   permissions, an external integration or service, an operational change, or
   any change the build path requires it for.
3. **Flagged route.** The work touches a named sensitive area whose caution
   is neither done nor accepted. Before building inside the area, give the
   risk notice once, in full, as
   the `setup-ai-build-kit` skill's `references/fit-check.md` describes. If
   the person carries on after it, write the `Accepted:` line with their
   words and the date, read it back, and build and save the piece on the
   pull-request route. Do this in the reply that answers them, and do not
   ask a further question before the build. A lock whose only purpose is to
   wait for this caution opens with the acceptance, unless the person asks
   to keep it. If they do not carry on, build only up to the recorded
   condition. In an unattended run nobody is there to carry on, so never
   write an acceptance on the person's behalf: stop at the condition.
   Stopping there, safely prepared and correctly recorded as parked, is one
   of section-builder's two successful outcomes; see step 8.

Pull-request and flagged routes work on a short-lived branch cut from the
up-to-date `main`, or from the branch a piece in a run stacks on. The checkpoint route may commit on the current branch once
its state is confirmed clean, but it too starts the piece from the up-to-date
`main` rather than continuing an older branch, so each piece is independent.

A route the project cannot perform right now does not stop the work. Where the
pull-request route is the right one and GitHub cannot be reached, so there is no
way to open a pull request, build the piece and save it on its own branch. Note
the step that did not happen in one plain line where the piece lives, the way you
would note any other fact.

That line is a note, not a warning. A step that cannot be performed because a
service is temporarily unreachable is missing, not dangerous, so it earns no risk
notice, no acceptance, and no recorded exception. Treating it as a hazard tells
the person their working project is broken, which is both untrue and the fastest
way to make them distrust the record they are relying on. Open the pull request
once GitHub is reachable again.

**The first upload.** Founding told the person nothing would be uploaded, so
the first push of the project's code waits for their yes. Before any push,
check where `origin` points. Where it is the kit's own repository,
`gwpicard/ai-build-kit`, push nothing: say plainly that the project still
points at the kit's repository, and ask for their own. Never push a project
there.

Then run `git ls-remote --exit-code --heads origin` and read its exit code.
Exit 2 means the repository has no branch: nothing from this project is
online yet, and this push is the first upload. Any exit other than 0 or 2
means the listing could not be read, because there is no `origin`, GitHub
cannot be reached, or the tool is not signed in. That is the route the
project cannot perform right now, with its one-line note, and never an empty
repository. Exit 0 means it has branches. Run `git fetch origin`: the code is
already online only when a remote branch shares history with the local
`main`, so that `git merge-base` finds a commit they share. Then push without
asking. That is how you know the question was answered: it is asked once for
each project, and no record is kept. A remote with nothing on it has no
`main` to bring up to date, and that needs no note.

Where the repository has branches but none shares history with `main`, push
nothing. It may hold a first commit GitHub made itself, or other work. Name
`owner/name`, say it holds something else, and ask the person what to do.

Build and check the piece first. Only the push waits. In the reply that
reports the piece, ask for a yes that names the upload: the repository as
`owner/name`, and whether it is public or private, read with
`gh repo view --json visibility`. Where you cannot read that, say so rather
than guess. Close to: "This is the first time your project's code goes
online. It goes to owner/name, which is private. Shall I upload it?"

On a yes, push the piece's branch, then create `main` on GitHub at the commit
the branch was cut from, `git merge-base main <piece branch>`, with
`gh api repos/<owner>/<name>/git/refs -f ref=refs/heads/main -f sha=<commit>`.
Make it the default branch with `gh repo edit --default-branch main`, open
the pull request, and tell the person in one clause that GitHub now starts
from their project's main copy. This is the one time `main` is written other
than by a merge. It holds only what the person already has, so it changes
nothing anybody relies on. On a no, keep the piece on its own branch on this
computer. That is the route the project cannot perform right now, with its
one-line note, and the next piece that pushes asks again. In an unattended
run nobody is there to say yes, so never upload on the person's behalf: keep
the work local and note it on the piece.

Claim the piece before changing anything. Label the piece `building` and assign
it to whoever is building it, in one step,
`gh issue edit <number> --add-label building --remove-label ready --add-assignee <login>`,
creating the label first if the project lacks it. Whatever state it carried comes off in that step, such as `parked` for a piece
whose condition is now met. That is what stops two people starting the same
piece, and it costs one call. Where GitHub cannot be reached, the claim fails:
say so, and do not start the piece. A piece already claimed carries on if
GitHub drops out later, as the route note above says.

## 2. Agree the visible result

Say back what the user will be able to do or see when this piece is done,
what's outside it, and how it will be checked. Get an explicit yes only when
something is still ambiguous; an already-approved, precisely written plan
piece does not need the ceremony repeated.

## 3. Choose evidence

Pick the smallest evidence that would actually be credible. Use every subject
the piece stores as an input to that choice and to the save route, from its
labels; do not silently downgrade
any of them. A piece carrying two subjects needs what both demand, and its save
route is the stricter of the two.

Where a machine can check the piece, that check is run and must pass before the
piece is called done. The softer proofs below are for the claims a machine
cannot judge, not a way around one it could. A screen that looks right is never
a substitute for a check that was available and skipped.

An automated behaviour test is required for: business rules, calculations,
permissions, data transformations, integrations, scheduled or background
behaviour, bugs, previously broken behaviour, and any acceptance criteria a
machine can judge.

A guided manual check is acceptable for: copy, layout, colour, exploratory
interaction, subjective usability, and disposable prototype work.

An operational rehearsal is required for: backups, restores, migrations,
rollback, alerts, deployment, and failure recovery. Under `data`, that turns on
what the change does to records that already exist. Adding a new field takes a
test; changing or moving records people already have takes a rehearsal on a copy.

Source evidence is required when correctness depends on an external fact;
run change-triage's source check first.

Run the checks the change needs: the ones its Done when lines name, and the
existing tests the reach check in step 7 finds. The whole suite is not the
default. A colour change runs the checks a colour change needs, and the project
check on the pull request runs the rest.

On Build with care, where a runner exists for the project's language, offer
the optional check in `references/test-strength.md`: break only the changed
code on purpose to see whether its tests notice. Run it after the ordinary
tests pass, if the person wants it. Use that reference's one-line report and
sort the misses on the piece. This offer adds no gate to saving the work.

## 4. Write the checks first

Before any code, write each check a machine can run that the Done when lines
name, under both `### Works` and `### When it is not the normal case`. Then run
each one on today's code and record that it fails: the Done when line, the
check, and the failure it showed. Commit the checks on their own, before the
code, in a commit that holds nothing else, so the saved history shows each check
failing before the change that makes it pass. Where the project's pre-commit
hook refuses a commit whose checks fail, commit the checks together with the
first code commit instead, and put the failing run's output in the hand-over. A
committed check changes only by being reported: the guard in step 8 lists it if
it changes. Checks only a person can make are exempt, such as whether a layout
reads well: name them, and leave them to the walk-through in step 6.

A check that passes on today's code proves nothing about this piece. Where it
passes because the check is wrong, fix the check. Where it passes because the
behaviour already exists, the Done when line is wrong: say so in the hand-over
and do not build that line.

Write each new check in a new test file where the project's layout allows, so
that writing checks changes no existing test. Where the layout allows no new
file, such as a single test file or tests kept inside the code, add the check to
the existing file and name that file in the hand-over as one the piece's `Under
the hood` must name. Never put a new check back to get past the guard. An
existing test may change only when the piece's `Under the hood` names it and
gives the reason. Step 8 runs the guard that holds this before anything is
saved.

A test that has to change for the piece to pass, when the piece does not name
it, means the test or the piece is wrong. So does a Done when line that cannot
be met as written. Report a wrong test or an impossible Done when line in the
hand-over, and never work round it: never weaken, skip or delete a test to get
past it, and never meet a different line in its place.

For adopted behaviour or a refactor, establish the current passing baseline
before changing it. For visual work, capture or describe the current state and
say what visible difference to expect. Do not write a meaningless automated test
merely to have one.

Load `references/reach-check.md` and use its current engine to take a small
structure baseline before code changes. Record only the relationships needed
for comparison: imports between the parts being changed, and any declared
sensitive-area boundary. Where no engine is present, read those imports
directly. Do not save the baseline as a project file or turn it into a score.

Where installing the project's dependencies, running the checks or running the
project's own commands first shows a tool missing from this computer, or too
old, stop that step. Name the tool, where it would go and how to undo it, and
wait for a yes, as the `change-triage` skill says under "Work on this computer
outside the project". In a run with nobody watching, park the piece instead, as
the `implement` skill's `references/running-longer.md` says. Write any version
the project needs into AGENTS.md's stack section as a requirement.

## 5. Build one vertical slice

Implement only the agreed behaviour, end to end and visible, in the smallest
reasonable change. Run focused checks as you go. Avoid speculative
abstraction; prefer managed services and the project's existing conventions.
Stop and say so if the change is expanding past what was agreed.

A piece whose build fails three attempts stops there: move it from `building`
to `parked` in one step, `gh issue edit <number> --add-label parked --remove-label building`,
with one line on what kept failing, and route it as `/fix`'s escalation says.
Never let a fourth attempt run on the same guess.

A build may reach a service the tool uses, for example to read its keys or set
it up. Use only what a tool offers through its own commands, and the keys the
tool already sends to the browser. Never read a stored login, token or
password out of the keychain, a credential store, or another tool's own files,
such as its settings or sign-in file, and never call a service's management API
with one. When you cannot read or change something that way, say so truthfully
and ask the person, naming the page where it lives. Once you have said you
cannot read something, never read it another way. A key the person gave this
project, kept where the masterplan records it, belongs to the project.

A command that changes a live service's settings or data, other than saving
code through the save route, waits for a yes that names the change and says
whether it can be undone, or that you do not know. Name every setting or
record the command will change, not only the one you meant to change, taken
from the command's own preview where it has one. Pushing a whole local
settings file changes everything in it that differs from the live project.
Applying migrations to the live project needs the yes too, and so does
changing its sign-in settings. Ask before you run it, never after. In an
unattended run nobody is there to say yes, so leave it unrun and say so on the
piece. A secret key is never written to a shared temporary folder such as
`/tmp`. Write what the build needs straight into the git-ignored file that
uses it. A secret key read through a tool's own commands is piped straight
into that file and never shown.

When the piece carries `visual`, or the change touches a screen file whatever
subject the piece carries, load and follow `screen-check`. A screen file is one
that renders a page, view, component, template, style, or native interface.
Apply it before the screen's guided manual check, so the person judges the first
result rather than describing a redo. When this build came from `/fix`, use the
same boundary: a fault on a screen gets the rules and any other fault does not.

When filing a new piece for work this build uncovers, follow the rule for work
found during a build in the `setup-ai-build-kit` skill's `references/pieces.md`.
Put the originating title on the new piece's surface and name the new piece
on the originating record. Say one line such as "Found while building the
invoice list." Keep the current build within its agreed scope.

A test that passes only on a retry is a fault in the test, never a passing
result. Report it as unreliable evidence and repair or replace it before the
piece can be saved.

Groundwork that makes the change easier is allowed only when it is itself a
vertical slice, or an expand-then-contract sequence that keeps the checks green
throughout, and it is ordered ahead as its own piece. It is never a horizontal
"refactor the data layer first" step, because that is the speculative
abstraction the paragraph above rules out and the layer split `/setup-ai-build-kit` forbids.

Internal engineering judgement, about interfaces, locality, or what makes a
boundary testable, can guide the work, but none of that vocabulary belongs in
what the user sees.

## 6. Hand over the behaviour

Before handing over, run the type check and linter that AGENTS.md's stack
section names, alongside the tests. A failure is a gap like any other: describe
it as expected versus actual and fix it at the root. Where the stack section
records none for the language, there is nothing to run.

Once those pass, on Build and run it and Build with care, load
`references/trim.md` and run its single pass. It takes out what this change
added that the behaviour does not need, and it only removes or folds, so the
walk-through, or the person's try when they opt in, sees the piece as it will be
saved. Give its one line at hand-over, or
nothing when it found nothing.

Then walk through the piece. Drive the tool yourself with the project's sample
data, the way the person would use it, and record what you saw: each action,
what the screen or output showed, and whether it matches the Done when line. The
masterplan's "How it stays running" says what sample data the project keeps.
Where it keeps none, make up the smallest case the piece needs and say so. At
each step, look at what the person would see, as "How the walk-through looks"
below says, and keep every screenshot and render in the main folder's
`.agents/tmp/walkthrough/<issue number>/`, which git ignores. For a piece with
no face, such as a scheduled job or an email, trigger it against a made-up case
and record what it produced.

The walk-through stands in for the person's try before saving. It does not close
the piece: on the pull-request route the piece still moves to `to check` and
closes when its pull request merges, so the person can still try it before they
merge. The person's decision is the merge: the walk-through is the check before
saving unless the person opted in or the walk-through could not see. Its report
never calls a screen accessible, compliant or good; `screen-check` says what it
may claim.

Where the coding agent cannot drive a browser or take screenshots, record what
it could check, such as the text a request to the page returned, and name what
it could not see. On the pull-request route, a piece that changes what somebody
sees then goes to `to check` for the person rather than closing, and the pull
request says what the walk-through could not see. On the checkpoint route, where
the walk-through could not see what somebody would see, there is no pull request
to wait in, so take the opt-in path below: give the person an address and things
to try, and save nothing until they reply.

Hand over what the walk-through found: the actions, what they showed, any known
limitation, where the screenshots are, given as the full path of the
walk-through folder in the main folder, and whether the evidence behind it is
automated, manual, source-backed, or operational. Describe any gap as expected
versus actual, and fix it at the root.

### How the walk-through looks

First read the capability profile's `Walk-through eyes:` line, which says what
this machine can look with. A project founded before that line existed has
none, so check each tool below with `command -v` now and say once what you
found.

Try the means for the piece's output in this order:

- A web page: the coding agent's own browser tool where it has one, such as
  Claude in Chrome on Claude Code. Otherwise Playwright's command line,
  `npx --no-install playwright screenshot --full-page <address> <file>`, where
  the project or the machine already has Playwright. The kit never installs a
  browser.
- A PDF: `pdftoppm -png -r 80 -f 1 -l 30 <file> <folder>/page`, from Poppler,
  which writes one image for each of the first 30 pages. `pdfinfo <file>`,
  from the same package, gives the page count. In a longer file, the pages
  past the thirtieth are named as not seen, and the piece goes to `to check`.
- A Word, PowerPoint, Excel or OpenDocument file:
  `soffice --headless --convert-to pdf --outdir <folder> <file>`, from
  LibreOffice, and then the PDF route. Where the command is named
  `libreoffice`, it takes the same options.
- An image in PNG, JPEG, GIF or WebP: read it directly. An SVG:
  `magick <file> <folder>/<name>.png`, from ImageMagick, and read the PNG.
  Where only an older ImageMagick is installed, `convert` takes the same two
  names.

Open each image with your file reader, which shows it to you. Record what each
one showed and what you compared it against, such as the Done when line, the
project's design system, or the same screen before the piece.

`<folder>` is that folder in the main folder, never a folder inside a worktree.
Find the main folder with this command:

`git worktree list --porcelain | sed -n '1s/^worktree //p'`

It prints the first `worktree` line, which is always the main folder. Outside a
worktree it prints the top of the project you are in, which is the main folder,
so nothing changes there. Create that folder where it does not exist yet; the
foundation's `.gitignore` already ignores `.agents/tmp/`. A picture inside a
worktree counts as unsaved work there and keeps the worktree after its pull
request closes. Each piece has its own folder, so walk-throughs running side by
side never overwrite each other.

Where a renderer fails on the file, such as a PDF it cannot open, record that as
a finding about the piece, expected versus actual. Treat it as the renderer's
fault only when you can say why, and say it.

Where no means fits the output, or the coding agent cannot read images, record
that you could not look and what you checked instead. The piece then takes the
could-not-see path above: on the pull-request route it goes to `to check` and
the pull request names what was not seen, pages past the thirtieth included.

### When the person tries it themselves

A person can ask to try a piece before it is saved. A `Waiting on you: try it`
line on the piece asks for that piece alone. A `check-myself|yes` line in
`.ai-build-kit-maintenance` asks for every piece. Any command writes that line
when the person asks for it, and takes it out when they ask to stop. With
either, walk through the piece first, then give one address to open and up to
three numbered things to try there, each with what they should see. The address
is the preview, or a local server started from the piece's branch. In a run on
Claude Code, that server runs in the piece's worktree on the port its run state
records, and the hand-over names that port and that worktree. Before giving
it, send a request to it and give the address that answered. Where the usual
port was taken or the server stopped, that is the address you actually used.
Where none answers, say so and give no address. Then stop, and save nothing
until the person replies.

In an unattended run nobody is there to try it. On the pull-request route, save
the piece as step 8 says, open its pull request and move it to `to check`, and
write in the pull request that it waits for the person's try before it is
merged. Then take the next piece. On the checkpoint route, commit it on its own
branch without closing the piece, note on the piece that it waits for the
person's try, and take the next piece.

## 7. Run required review

Before deciding which review applies, load `references/reach-check.md`. Check
what else the finished change reaches and which existing tests cover it, then
run those tests first. Use what the change actually reaches when applying the
review triggers below. On Build with care, compare the reached paths and crossed
boundaries with the sensitive-area map in the masterplan. A match starts the
review and says exactly: "This change reaches <area>, so a review is running."
Check a boundary with sentrux or dependency-cruiser where either is already
present, and by reading the changed imports where neither is present.
Update that map in the same save as any code move that changes it. Keep the full
project check for the pull-request gate.

Compare the finished structure with the baseline from step 4, using the same
engine. Say one line only when it got worse: "This change added a loop between
<part> and <part>." On Build with care, use "This change crossed the boundary
around <area>." Never show a score. When nothing worsened, say nothing. If it
did, the person can ask to fix it before the save or leave it; record the choice
on the piece and carry on.

Review triggers come from the build path, the change's consequence
classification, or the masterplan's sensitive areas. When
any of those apply, run second-opinion using the best independent method
recorded in the capability profile before offering to save; this fires off
what the change actually touched, so it never depends on anyone remembering.

Where the trigger names who must review, that person is the review. Running
second-opinion instead is a different thing, worth doing and worth saying is not
the named one. Evidence the change works is also not a review: a green check
proves the behaviour, and the review exists for what the check cannot see.

## 8. Save

Before anything is saved, on any route, run this skill's `scripts/test-guard.sh
<base> <piece file> <checks commit>` from the project's folder. The base is the
commit the piece's branch was cut from: `main`, or the branch of the piece it
stacks on. The checks commit is the one step 4 made. The piece file holds the
piece's text, saved with `gh issue view <number> --json body --jq .body` into
`.agents/tmp/`. The guard lists each existing test file changed since the base
that the piece's `Under the hood` does not name, and any check changed since its
own commit. Put each listed file back as it was, `git checkout <base> --
<file>`, or `git checkout <checks commit> -- <file>` for a check. Where the
guard says a listed file was moved, remove the moved copy too. Then run the
checks again. Where the piece cannot pass without that change, step 4 says what
to report.

Before saving on any route, apply the piece's `## Masterplan change` and update
the trued-against mark as
the `setup-ai-build-kit` skill's `references/masterplan-changes.md` describes.
The record changes in step 9 are part of this save, not a later /sync task.

Checkpoint route: update the records, commit, and state the saved checkpoint.
There is no pull request to wait on, and the walk-through in step 6, or the
person's own try where they asked for one, stood in for their check, so close
the issue and take `building` off it in the same step. This is the one route
where a piece closes when it is saved rather than when a pull request merges,
and it never passes through `to check`. Where the walk-through could not see
what somebody would see, the person's try in step 6 comes before this save.

Pull-request route: update the records, commit, push, open a pull request
titled after the piece with a plain-language summary, aimed at the branch the
piece was cut from, and run the project checks. The project's first upload waits for the yes in step 1. Where the
piece is an issue, write `Closes #<number>` in the pull request body, so
merging it closes the piece rather than leaving somebody to remember.

A closing word appears only on a `Closes #<number>` line, one line for each
piece the pull request finishes. GitHub closes an issue when a merged pull
request or commit puts one of nine closing words straight before its number:
close, closes, closed, fix, fixes, fixed, resolve, resolves or resolved. It
reads only the word and the number, so a sentence saying the pull request does
not close a piece still closes it when the closing word stands straight before
the number. So in the pull request's title and body, in commit messages and in
changelog files, no number that names another piece has a closing word before
it. Name another piece by its number and its title, with no closing word before
the number, and say "after", "builds on" or "merge first", as in "Merge
#<number>, the date filter, first." A pull request that finishes one piece and
mentions another carries one `Closes` line, for the piece it finishes, and
names the other that way.

Once it is open, write the piece's changelog file, as step 9 describes, and
push it.
When the pull request opens, move the piece from `building` to `to check` in the same
step, `gh issue edit <number> --add-label "to check" --remove-label building`,
since it now waits for the person to try it or merge it. Wait for the check as
`references/merge.md` says under "Waiting for the check", and never present the
pull request as ready until the check is green; if it goes red,
say so plainly, pull the failing output yourself, fix through the normal
steps, and push again.

Once the check is green the piece is ready for review. Merge it only as
`references/merge.md` says: on a yes that names it, or under the person's
pre-approval of a run when the piece meets all six of its conditions.
Otherwise the pass stops there. Report the piece as ready for review, not as
done.

Flagged route: where the person carried on and the acceptance is recorded,
this is the pull-request route and nothing below applies. Otherwise do the
pull-request route for everything up to the condition, then:

- record the exact condition that must be met, and say that /ship prepares a
  handover for the area on request;
- move the piece from `building` to `parked` in one step, with the condition
  written on it, `gh issue edit <number> --add-label parked --remove-label building`;
- name what other work may still continue;
- state plainly that the flagged capability is not ready or live, with no
  softer wording that could be read otherwise.

A piece that ends here, with all five done, is safely prepared and correctly
parked. Report it as a completed pass, and leave it alone until the
condition is met or the person carries on after the notice and the acceptance
is recorded.

## 9. Sync the records

Each fact the piece settled goes to one home, and nowhere else:

- what changed for the person: the piece's changelog file, below;
- the product, its promises and decisions: the masterplan, through the piece's
  recorded change;
- lasting technical design, how a part of the tool works and the rules it
  keeps: `docs/<concept>.md`, one concept to a file, under the headings What it
  is, How it works, Rules, and Where it lives. A concept file is one listed in
  `docs/README.md`, a line each with its name and what it owns. Update the
  concept's file where it has one. A fact that fits no concept file yet starts
  a new one, named for its concept, never a general notes file, and gets a line
  in `docs/README.md`, never in AGENTS.md;
- a durable operating convention: one short rule in AGENTS.md, or a pointer to
  the file that owns it;
- anything particular to this piece: the piece itself.

AGENTS.md holds rules and pointers only. Never write a date, an issue number or
a code name into it. A code name is a function, variable or file name from the
project's code; those belong in the concept file, the piece or the changelog
file. The project check goes red when AGENTS.md passes 200 lines, so move
detail to its home rather than past the ceiling.

Where the piece added, removed, or changed something outside the tool that it
reaches, update the masterplan's connections picture too, and say in one line
what the tool now reaches, so the person can say whether it should. A
correctly completed build does not need /sync afterward.

Once the pull request merges it closes the issue, so there is no
status to set by hand. After that merge, take `to check` off the closed issue,
since a closed issue is done and carries no state, and refresh
the printout with `sh .agents/tools/plan-refresh.sh` so the person's list matches
what just happened.

When the report names a next piece, refresh the printout first if this pass has
not, and name only a piece under its `To build` group marked `(ready)`. Where
there is none, say nothing is ready to build now and name no piece. Never work
the next piece out from the issue list by hand.

The piece's changelog entry goes into its own file,
`changes/<issue number>-<short name>.md`, never into `CHANGELOG.md`. Two pieces
built at the same time would both add a line at the top of that one file, and
every merge after the first would conflict there. The merge folds the files into
`CHANGELOG.md`, as `references/merge.md` says, and `/sync` and `/ship` fold any
files still waiting, such as one a merge made on GitHub by hand left behind.
Create the `changes/` folder when the project
has none; an older project gets it from its first piece. The issue number keeps
two pieces with the same short name apart. Where the work has no issue, use the
pull request's number instead. Checkpoint work with neither takes the date and
the branch's short name, `changes/<YYYY-MM-DD>-<short name>.md`.
Content the person asks to keep after using the tool on it, as the
`change-triage` skill describes, is saved through the build path's save route with its own changelog
file, named as work with no issue is, and is never left on a branch nobody
pushes.

The file holds one or two sentences on what changed for the person, then the
pull request's link on its own line. Write it after the pull request opens, as
a second commit on the same branch, so it can carry the link. One file per
piece: a later commit or review round rewrites that file and never adds another.
On the checkpoint route there is no pull request, so the file names the issue
instead and goes into the checkpoint commit. With no merge to fold it, run the
`sync` skill's `scripts/fold-changes.py` from the project root and commit the
fold as a second checkpoint commit, so the history there stays whole too. The
file carries no date, because the fold dates it by the day it reached `main`.

Write those sentences from the piece's own `So that` and `Done when`, in plain
language. Not from its title, and not from the pull request. A changelog
assembled out of titles reads like a list of tasks, and this record exists so
somebody who has not read the code understands what happened to their project
six months later.

## Excuses that don't hold

- Urgency does not remove the need for evidence.
- Small does not permit hidden scope.
- Visual work does not need a fake automated test to look rigorous.
- Private exploration does not need pull-request ceremony it doesn't need.
- Shared or risky work does not get downgraded because setup is inconvenient.
- A review finding does not authorise unrelated cleanup.
- The trim does not authorise a restructure. It removes and folds, and reports
  the rest.

## Done when

One of two outcomes, both complete passes:

- Complete: the agreed behaviour has credible evidence, with any available
  machine check run and green, the checks were written first and seen to fail,
  no test changed that the piece does not name, the walk-through is recorded or
  the person tried it where they asked to,
  required review is satisfied, the records match reality, and the selected save
  route is complete.
- Safely parked: the piece stopped at its recorded condition, moved from
  `building` to `parked`, with the caution recorded on it, work that can go on
  identified, and no claim that the flagged capability is ready or live.
