---
name: ship
description: Take checked work to the copy of the tool the team actually uses. The only skill that touches that copy. Use when the user thinks the tool, or a batch of work on it, is ready for people to rely on. Follows the project's current build path and applies only the evidence, review, handover, or launch steps that path requires.
---

# Ship

Everything build and fix make lives on the draft copy until this command moves it over. Read masterplan.md, build-path section first.

## 0. Confirm the build path

Read the build-path section first.

If anything under `Recheck when` has happened since `Last checked`, run the
fit check before continuing.

Read each line under `Sensitive areas`. Say for each whether its caution is
done, accepted, or `not yet done`. An area `not yet done` gets the risk notice
in its own step below, and the rest of the work does not wait for it. Then
run `python3 .agents/tools/area-map.py check` and walk the `## Areas` section of `docs/working-rules.md`:
each area with a `sensitive:` line, where it lives, and its optional
`boundary`. Stop while the check names a folder or a line, and claim the folder
or correct the line first.

Read the `Recipe:` line in the stack section of the project's AGENTS.md. A file
name there, written with its `.md` as founding records it, is the project's
recipe: read that file in this skill's `recipes/`
folder, and each part it links with `Shared part:`. `Recipe: none`, or no line
at all, means the project is off a recipe. If the named file is not there, say
so once and treat the project as off a recipe.

## 1. Follow the current path

Each branch below is self-contained. Follow only the branch that matches the
current build path, stop where it says stop, and do not carry a step from one
branch into another.

### Explore privately

Do not run the production evidence or launch procedure. Nothing below this
point in this branch ever moves work to a live address.

Confirm only:

- the prototype still uses disposable data;
- nobody relies on it;
- no consequential automatic action is active;
- the question or experiment it exists to answer has been checked;
- any preview remains private;
- the user is told plainly that it is not approved for operational reliance.

Record what would need to change before the path could become Build and run
it, then stop.

### Build and run it

Where the `Goes live:` line says `not hosted` and no recipe is named, going
live is a release. Follow "Releasing a tool that is not hosted" below, which
says when steps 1 and 2 run, in place of steps 3 and 4.

1. Run the full evidence run.
2. Run second-opinion using the best independent method recorded in
   AGENTS.md. Before the review asks the person to look up a setting, it
   follows "A setting the kit can read" below.
3. Operational readiness, before any first live use. On a recipe, the
   recipe's own checks replace the general list; "On a recipe" below says how
   to run them. Off a recipe, check whatever of this actually applies: a named
   service and billing owner, a backup, a successful restore rehearsal, a
   manual fallback, a rollback or disable procedure, removal of test data, an
   access review, and clear service-account ownership. Leave out a database
   restore rehearsal for a tool with no stored data, and invent no readiness
   steps a tool with no live reliance doesn't need. Each item that applies and
   is not in place is a warning: name it once in one plain line, record it in
   CHANGELOG.md with the date, and carry on. None of them holds the launch.

   Check that the tool records what each request did: one line per event,
   with a run id shared by that request's events, a time, a level and the step.
   Check this with disposable inputs. Apply AGENTS.md's Secrets and
   Confidential files rules to the record: it must contain no personal data,
   keys, passwords, tokens or confidential file contents. Never print those
   contents while checking it. Keep the field names out of the person's report.

   If the record is absent or cannot trace a request, say once: "The tool
   keeps no record of what each request did, so a fault reported after launch
   cannot be traced. I have noted that in the changelog, and adding the record
   is one piece whenever you want it." Record in CHANGELOG.md, with the date,
   that the tool keeps no such record and what remains untraceable. Then carry
   on with the launch. Do not hold launch for the record, and do not ask the
   person to choose to go live without it. Say it once a visit. When the
   person later asks what remains, a line saying the changelog already notes
   it is enough; do not give the reason or the risk again.

   Do not add a sensitive area or an `Accepted:` line for this operational
   gap. A record containing forbidden data needs a repair; going live without
   a record never waives the data exclusions.

   Give the monitoring caution once, unless the fit check already names an
   alert recipient: "Once real people use this, the only record of what went
   wrong will be the record the tool writes. If you want somebody to be told
   when it breaks, that is a service somebody runs and pays for, and the kit
   does not set one up." Record that the caution was given in CHANGELOG.md;
   do not repeat it in a later reply of the same visit, for another area, or on
   a later /ship visit. A named alert recipient satisfies this caution. Having
   nobody to receive alerts is the person's choice, which the caution covers;
   it is never a piece on the readiness list. Do not set up a hosted service,
   dashboard or alerting as part of this check.
4. Go live, one connection at a time: take the harmless parts live first.
   On a recipe, go live the way its going-live section says, when that
   section's turn comes in the checks below. Any merge or deploy on the way
   follows "Merging and deploying" below.
   If hosting uses a preview address, this is the moment work moves to the
   team's address. That move is what /ship means, and "Promoting to live"
   below says how it is asked for.

   Where the tool will run on a server this session cannot reach, such as one
   the team or a hosting companion runs, the address comes from whoever runs
   that server. The kit never contacts that server. The person carries a short
   request there by hand, and carries the answer back.

   On a recipe whose going-live section the kit runs itself, no hosting
   request is written. The address that section produces, recorded as "On a
   recipe" below says, is the address the first launch waits for.

   On a first launch, read the masterplan's "How it stays running" section.
   When it holds no hosting request, write one there, as
   `references/hosting-request.md` says. That file gives its fields, where
   each comes from, the one line the person hears, how to record the answer,
   and how a later /ship reads the request back.

   The first launch is not finished until an address is recorded under the
   request, or by the kit's own going-live on a recipe. Until then, tell the person plainly that the tool is not live yet
   and is waiting on the server's answer. Do not write it into CHANGELOG.md as
   live.

#### On a recipe

Here the recipe file says what to run and what a pass looks like. Every
command, service and address comes from it at run time. This skill names none
of them, so it reads the same whichever recipe the project is on.

Take the recipe's eight sections in its order: preview, going live, rollback,
backup, restore, secrets, logs and health. For each one, read `How it works:`
for what happens and `How it is checked:` for what a pass looks like. Then let
`Who runs it:` decide how the check is done:

- `the kit`: run the check from the project and read the output against the
  pass the recipe describes.
- `a companion or the person, result read back`: the check runs somewhere this
  session cannot reach. Say in one plain sentence what to fetch and from
  where, ask the person to paste it here, and read it against the pass
  yourself.
- `a person looking`: no machine can judge it. Ask the person to look, say in
  one sentence what they are looking for, and record what they say in their
  own words.

A check that would change the live tool only to prove it can, as a rollback
does, is not run against the live tool. For rollback, confirm with the
recipe's own commands that an earlier production build is listed, and report
the line as "rollback possible, not tried", so it never claims more than was
checked. Run the check in full only when the person asks for a rollback.

Report each section in one plain line, in this order: preview up, live address
updated, rollback possible, backup present, restore works, no secret in the
repo, logs readable, health answers. Each line says what was found, in plain
words, and leaves the command out.

A check that failed, could not run, or got no answer is a warning. Say it once,
on that section's line, record it in CHANGELOG.md with the date and the
section, and go on to the next section. Do not hold the launch for it, and do
not ask the person to choose to go live without it.

On a launch after the first, read CHANGELOG.md before you write these lines.
Where it already holds the same warning for the same section, that section's
line is a one-line pointer and nothing more, such as "backup present: still
none, as the changelog has recorded since 19 September". Leave out the reason
and the risk, and add no second changelog entry for it. A warning the
changelog does not hold, or one whose cause has changed, is new: say it once
in full, as above.

The one wait that remains is the address. Where the kit ran the going-live
section itself, record the live address it produced in the masterplan's "How
it stays running" section. A tool with no recorded address is not called live,
on a recipe or off one: tell the person so plainly, and keep it out of
CHANGELOG.md as a launch.

#### A setting the kit can read

This holds for the launch review and for every check in this skill, on a recipe
or off one. Before you ask the person to look up a setting of a service the
tool uses, check whether the kit can read it with what it already has: an
address the service answers in public, a command-line tool this session is
already signed in to, through that tool's own commands, or the project's own
files. Where it can, read the setting and report its value in one plain line,
instead of asking. On a recipe, its `Settings the kit can read` section, where
it has one, says which settings the kit reads and how.

Such a read uses only a key the project already sends to the browser. Never use
a secret key, a service key or a password to read a setting, and never sign in
to anything new for it. Ask the person only for a setting the kit cannot read
that way, and say in the same sentence why it cannot, for example that the
service shows it only on its own settings page.

#### A login the kit does not own

This holds for the launch review and for every step in this skill that
reaches a service. The kit uses only what a tool offers through its own
commands, and the keys the tool already sends to the browser. It never reads a
stored login, token or password out of the keychain, a credential store, or
another tool's own files, such as its settings or sign-in file. It never calls
a service's management API with such a login. A command-line tool uses its own
sign-in when the kit runs that tool's commands, and the kit never takes that
sign-in out to use it another way.

When the kit cannot read or change a setting that way, it says so truthfully
and asks the person, naming the page where the setting lives. Once it has said
it cannot read something, it never reads it another way. If the person asks it
to try, it says again what it can reach and what it cannot.

This is about a login another tool keeps for itself. A key the person gave
this project, kept where the masterplan records it, belongs to the project,
and "A secret a check needs" below says how to use it.

#### A change to a live service

A command that changes a live service's settings or data, other than saving
code through the save route, waits for a yes that names the change and says
whether it can be undone. Name every setting or record the command will
change, not only the one you meant to change, taken from the command's own
preview where it has one. Pushing a whole local settings file changes
everything in it that differs from the live project. Other examples are
applying migrations to the live project, or changing its sign-in settings.
Where the kit does not know whether the change can be undone, it says that.

The commands the project's recipe names, in any section, are the launch the
person asked for, and need no further yes. Anything the recipe does not name,
and any push of a settings file, waits for the named yes. A no leaves the
service as it was, and the step is a warning like any other.

A token in the person's environment that reaches the whole account is used
only for the reads the recipe names. A change made with it waits for the yes
above.

A secret key is never written to a shared temporary folder such as `/tmp`.
Write what a step needs straight into the git-ignored file that uses it.

#### A secret a check needs

This holds at every go-live, on a recipe or off one. Before a check that needs
a secret, such as the database password for the backup, the restore or the
database guard, read where that secret lives from the masterplan's "How it
stays running" section. Pass it by its location, as a command built in the
person's shell or read inside a script. Never read, print or show the value.
Checking the record means checking that the file or variable exists, never
reading it. When no location is recorded, or nothing is where the record says,
ask the person once where it lives. Record their answer in that section as a
location, never a value, and run the check.

If the answer is the secret itself, record it nowhere. Say plainly that it is
now in this conversation, ask the person to rotate it, and ask for its location
instead.

If they cannot say, the check could not run, and that is a warning like any
other. Its line and its changelog entry say that the kit does not know where
the secret is kept. Never write that the secret is absent, missing or not on
this computer: the kit only knows that it did not find it. Give no reason
for a skipped check that the kit did not itself confirm.

#### Promoting to live

It applies whether or not the project is on a recipe. Read the `Goes live:`
line in the masterplan's "How it stays running" section, as described in the
`section-builder` skill's `references/merge.md`. On `through /ship`, merged
work waits on a preview, and going live is a promote. On `on every merge`,
there is nothing to promote: each merge was a launch, and `merge.md` ran the
first-launch checks before the first of them. On `not hosted`, there is nothing
to promote either: going live is a release, as the next section says.

To promote, name what will go live: each change merged since the last launch,
one plain line each, read from the files in `changes/` and the pull requests
merged since then. Run the checks this path requires before the promote: the
steps above, or on a recipe its checks up to going live. Then ask, for example:
"Say yes to put these three changes live." Promote only on a yes that names the
promote. A yes to a merge does not cover it, and neither does a yes given before
the changes were named. A no leaves the live tool as it was.

The promote is the recipe's going-live section, and its yes covers the commands
that section names. Off a recipe, promote the way "How it stays running"
records. Where it records nothing, ask the person how the preview is put live,
and write their answer there.

At any launch, first or later, where "How it stays running" has no `Goes live:`
line, write one, from the recipe's going-live section or from what the person
says: `through /ship`, `on every merge` or `not hosted`. An older project gets
the line this way, at its next launch.
In the same save, set the confirmation box as the `section-builder` skill's
`references/merge.md` says under "The confirmation box on a merge that goes
live": `add` for `on every merge`, `remove` for any other value.

#### Releasing a tool that is not hosted

This applies where the `Goes live:` line says `not hosted` and no recipe is
named. No server runs such a tool, so going live means cutting a release: a Git
tag with a GitHub release. Where a recipe is named as well, the two disagree.
Say so once, follow the recipe, since a recipe is a place the tool runs, and
leave this section out.

Name what the release holds: each change since the last release tag, one plain
line each, read from the files in `changes/` and the lines of CHANGELOG.md
above its newest `Released` line, or every line when there is none. Where
nothing changed since the last release, say so and make no release.

Run the checks this path requires before the release: the evidence run and the
review, steps 1 and 2 above. Leave out the request record check and the
monitoring caution, since nothing serves requests. Write no hosting request,
wait for no address, and write no rollback line.

Then read the tags GitHub holds with `git fetch --tags`, where there is a
remote, and this computer's with `git tag --list`. Propose the next minor
version after the newest tag of the form `vX.Y.Z`: `v1.4.2` gives `v1.5.0`.
Where no tag has that form, propose `v0.1.0`. Where the newest tag has another
form, name the tag you found in one line, and still count from the newest one
of the form `vX.Y.Z`. The person may name another tag in their reply. Where the
tag already exists, because somebody made it by hand, name it and ask for
another, and create nothing until the person names one.

Ask for a yes that names the release, for example: "Say yes to release v1.5.0
with these three changes." Release only on that yes. A yes to a merge does not
cover the release, and neither does a yes given before the changes were named.
A no leaves everything as it was.

On that yes, write the lines you named to a notes file in `.agents/tmp/`, which
git ignores, and run
`gh release create <tag> --target main --title <tag> --notes-file <file>`.
Where GitHub cannot be reached, no release is made: say in one line that the
release waits and can be asked for again once GitHub answers. Where the project
has no GitHub repository, or saves on the checkpoint route, the release is a
local annotated tag instead, made on the same named yes with
`git tag -a <tag> -m "<tag>" main`. Say that the tag stays on this computer and
nothing was published.

The launch record in CHANGELOG.md reads `Released <tag>`, saved the way
"Merging and deploying" below says for every record a launch writes.

#### Merging and deploying

These rules hold at every go-live, on a recipe or off one, and on Build with
care as well.

Any merge follows the `section-builder` skill's `references/merge.md`, as it
does on every route: the yes that names it, where it is made, and what the ask
says when a merge goes live.

The records /ship writes during a launch, such as its CHANGELOG.md entries and
a confirmation the person gives later, such as a colleague saying the new
version is live, take the save route the build path already requires: the
three routes section-builder names, with no fourth for records. On the
checkpoint route, a checkpoint commit is enough. Otherwise put them on one
branch for this /ship, cut from the up-to-date `main`, and stage only the files
/ship itself changed. On that branch, or in the checkpoint commit, fold any
files still waiting in `changes/` into CHANGELOG.md with the `sync` skill's
`scripts/fold-changes.py`, as /sync does. Each merge folds its own piece's
file, so these are the ones a merge made on GitHub by hand left behind, and
folding them here means the pieces this launch carries reach the history with
it. Fold first and write the launch lines after, so
the launch sits above the pieces it launched under the same date. Where an
earlier records pull request that folded files is still open, say so in one
line and do not fold again until it merges. Open one pull request for them, once, after the
launch is checked and its records are written, and ask for its yes in the reply that
reports the launch. Where GitHub cannot be reached, save the records on that
branch, note in one plain line the step that did not happen, and open the pull
request once GitHub is reachable. The project's first upload waits for the
yes section-builder's "The first upload" describes. Never push records
straight to `main`. A later confirmation joins that branch while its pull
request is open, or a new branch and pull request once it has merged.

The records pull request is a merge like any other, so `merge.md` applies to
it. The yes to the earlier merge does not cover it, because that
pull request did not exist when the person gave it. Where the host builds every
change to `main`, merging it starts one more build of the same code and moves
the rollback target. Say so in the line that asks for its yes, and offer to
leave it open so it goes out with the next change. If they say yes, correct the
rollback line on that branch before the merge. Merging it writes no record of
its own. Uncommitted work of the person's stays exactly where it is: never
sweep it into the records commit, and never discard it to get a clean tree.

Before you decide a deploy failed, read its whole output, or read the host's
own list of deployments or have it read. Where the kit cannot reach the host,
the person or a companion reads that list and pastes it here. Never cut the
output short. Where neither says whether the deploy went live, ask the live
address which version it serves, through its health route where it has one,
or have the person ask it. Never run a deploy a second time until you have
checked that the first did not go live. A second deploy of the same version
replaces the earlier build as the rollback target, so a rollback would bring
back the same version. When a second deploy is still needed, say that in one
line before you run it, and correct the rollback line to match.

A warning said once in a /ship is not said again in that /ship, even when a
step runs twice. Where it matters again, one line saying the changelog already
holds it is enough. The risk notice for a named area is not a warning, and
Build with care still gives it at the moment that area goes live.

### Build with care

Separate the work into what is outside every named area and what is inside
one.

Outside every named area, follow the same four steps as Build and run it
above: evidence run, second-opinion, operational readiness, then go live one
connection at a time. On a recipe, readiness and going live are the recipe's
checks, as "On a recipe" says.

On a tool that is `not hosted`, with no recipe named, readiness and going live
give way to the release, inside the named areas as well as outside them. Give
each area's caution or risk notice as below, then make one release as
"Releasing a tool that is not hosted" says, with no readiness check and no
go-live step of its own for any area.

Inside a named area, take each area in turn:

1. read its line in the build-path section: what touches it, its caution, and
   where the caution stands;
2. where the caution is the kit's to do (a backup restored once, a rehearsal
   on a copy, a managed service, an approval step), do it now or check it was
   done, and write `done` with today's date on the line;
3. where the caution is a person who has not looked, give the risk notice
   here, once and in full, at the moment the area is actually going live
   rather than only when it was first scoped. Say in one sentence what that
   person would confirm. No session meets it; fit-check.md says who does.
   Where an acceptance is already recorded for the area, give no notice; say
   in one line what was accepted and when;
4. if the person carries on after the notice, write the `Accepted:` line with
   their words and the date, as fit-check.md describes, and mark the area's
   line `accepted`, never `done`. Read the line back, then go on in the same
   reply, without a further question about that area. A lock whose only
   purpose is to wait for this caution opens with the acceptance, unless the
   person asks to keep it. Silence, a question, or a request for other work
   is not carrying on, and nor is a form answer with nothing chosen: leave
   that area where it is and ship everything
   outside it;
5. only after the caution is done or accepted does that area get its own
   operational readiness check (including the request record and monitoring
   rules above, without repeating their notices) and its own go-live
   step, one connection at a time, with the result recorded on its line. On a
   recipe, the recipe deploys the whole tool at once, so an area whose caution
   is done or accepted goes live through the next run of the eight checks,
   not through a separate deploy.

Where a caution is a person and the team has nobody to ask, offer the
handover once: `templates/handover.md`, filled in for that area, is what the
team gives somebody outside it to look at that area or to take the build on.
Offer it, prepare it if they say yes, and carry on with everything outside
the area either way. A handover is a document the person asks for, not a
stop.

## 2. Graduation

When shipping or preparing a handover changes the build path or names a new
sensitive area, record:

- what changed;
- why the previous path no longer fits;
- each new area and its caution;
- which work may continue;
- which work waits.

## After the first launch

Applies only once Build and run it, or Build with care outside its named
areas or in an area whose caution is done or accepted, has actually gone live
at least once. Lighter from
then on: re-run the evidence for what changed since the last ship, and move
that over. On a recipe, run its eight checks again, as above. "On a recipe"
says how a warning the changelog already holds is given: as a one-line
pointer, never again in full.
On a tool that is not hosted, each later /ship is another release, made as
"Releasing a tool that is not hosted" says. The hosting request recorded at the
first launch still holds, and
`references/hosting-request.md` says how to read it back. If reliance, data sensitivity, or consequence has
grown since the build path was last checked, rerun the fit check before
shipping further.

## Done when

Explore privately: the private-preview checks are recorded and nothing moved
to a live address. Build and run it, and Build with care outside its named
areas or in an area whose caution is done or accepted: the team can rely on
the copy they use, each readiness item is in place or recorded as a warning,
on a recipe each of the eight checks has its line, and the changelog
says what went live, when, and under which build path. On a tool that is not
hosted, the release was made on a yes naming it, or the reply says why it
waits, and the changelog reads `Released <tag>`. Where a handover was
asked for, it is complete and says what it does not cover.
