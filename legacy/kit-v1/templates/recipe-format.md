# The recipe format

A recipe is one build stack paired with one place to run it, which the kit knows
well enough to check. The shape of the tool picks the stack: a web app with
sign-in and saved data wants a different one from a static site. The place to
run it is where the tool lives once people use it. Each pair is its own recipe,
so a stack that runs in two places is two recipes.

Recipes live in `ship/recipes/`, one file each, named for the pair in lower case
with hyphens. The folder is the menu: a recipe is offered once its file is there,
and not before. `ship/templates/recipe.md` is the blank to copy.

## What a recipe holds

The file opens with six lines.

- `Fits:` the shape of tool the recipe suits, in words the person would use.
- `Recommended when:` one plain sentence saying when founding should recommend
  this recipe over another that fits the same shape.
- `Build stack:` what the tool is built with.
- `Deploy target:` where it runs once it is live.
- `Command-line tools:` the tools the recipe's checks run on the person's
  machine, as command names separated by commas, or `none`. The setup tooling
  check reads this line and reports each one, and a missing one never stops
  founding, because only a project on this recipe needs it.
- `Last checked:` a date, written YYYY-MM-DD, when somebody last read the recipe
  against the current documentation of everything it names. The date moves only
  when somebody did that.

A seventh line may follow them. `Plan terms:` says, in one plain sentence, who
a free or entry plan the recipe relies on is not for, such as personal,
non-commercial use only, and which plan such a person needs instead. It ends
with when and where the terms were read, as `(read YYYY-MM-DD at <source
page>)`, and the source page is the service's own. Terms change without
notice, and a restriction with no date cannot be told from a current one. The
line never quotes a price. Founding reads it when it offers the recipe, and
says it only to a person it applies to. A recipe whose plans carry no such
limit leaves the line out.

Then comes one section for each of the eight things a live tool needs, in this
order: preview, going live, rollback, backup, restore, secrets, logs and health.

- Preview is how a change is seen somewhere safe before it goes live.
- Going live is how a checked change reaches the live address.
- Rollback is how the live tool goes back to the last version that worked.
- Backup is what is saved, where, and how often.
- Restore is how a backup is put back, and roughly how long that takes.
- Secrets is where keys live and how they reach the tool.
- Logs is where the tool's record of requests and errors is read.
- Health is how anyone knows the live tool is up.

Each section carries three lines. `How it works:` says what happens on this
pair, in the order it happens. `How it is checked:` says how anyone would know
it worked: the command or check and what a pass looks like, or what a person
looks at. `Who runs it:` says who runs that check, and takes one of three
values.

- `the kit` when the kit runs the check itself, from the project.
- `a companion or the person, result read back` when the check runs somewhere
  the kit cannot reach, such as a server it never contacts, and the result is
  pasted back for the kit to read.
- `a person looking` when no machine can judge it.

A section with no check is not finished. Saying the service handles it tells
nobody how they would find out that it did not. A person looking is a full
answer wherever no machine can judge the result.

## Shared parts

Two recipes often share a half. A stack deployed in two places keeps the same
data service, so its backup and restore read the same in both. Such a section
is written once, as a part in `ship/recipes/parts/`, and a recipe links it in
place of writing the section out, with one line: `Shared part:` followed by a
Markdown link to the part's file. A part holds the same three lines a
section would. The parts folder is not a menu entry, and nothing that reads the
menu treats it as one.

## Settings the kit can read

A recipe may carry one more section, `## Settings the kit can read`, between
health and the proven section. It says which settings of the services the tool
runs on the kit can read for itself, and how, so the launch review reads them
rather than asking the person to look them up. Such a read uses only a key the
project already sends to the browser. A setting that needs a secret key to read
does not belong here, and the section says what the kit cannot read and why.
The section carries the same three lines as the others, or a `Shared part:`
link. It is not one of the eight, and /ship gives it no line of its own. A
recipe that carries it gives it an outcome line in its proven section, starting
`Settings the kit can read:`, like each of the eight. A shared part proven in
another recipe's real run may say so there instead.

## What proven means

A recipe joins the menu only when two things are true. Offline rehearsals guard
its rules: a maintainer check names the recipe file and fails when a rule goes
missing. And one real deploy has been run from an empty project to a live
address and through all eight sections, with the maintainer's approval and
accounts, and written down. A shared part proven once, in another recipe's real
run, counts for every recipe that links it. The outcome line for that section
says so and names the run it comes from.

The record lives in the recipe's own proven section, so it travels with the
recipe and anyone can read what was tried. It opens with `Real run:` and the
date, then gives one outcome line for each of the eight sections, starting with
the section's name, saying what was done and what came out. A recipe without
its real run stays out of the folder. There is no draft state, because a draft
in the folder would be on the menu.

A change to any section's `How it works:` line, in the recipe or in a part it
links, needs a new real run before the next release. The old record describes a
recipe that no longer exists.

## Where product names go

A recipe names the services the person's tool runs on: its hosting, its data
and its deploy. That is its job, and the README may name them as well. No
other file in the kit names a service a tool runs on. A skill that needs to know
how one behaves reads the project's recipe, so the skills read the same
whichever recipe a project runs on. Tools the kit itself works through, such as
the coding agent or the issue tracker, are a separate matter and are not
governed here.

## Where a project records its recipe

A project names its recipe in its own AGENTS.md, in the stack section, as
`Recipe: <file name>.md`, the file name with `.md` included, or `Recipe: none`
when the person chose their own stack or no recipe fits.
It does not go in the build-path block. The build path says how carefully the
work is built and the recipe says what it runs on, and the two change for
different reasons.

A project on its own stack still works with the kit, with fewer promises. On a
recipe, each of the eight sections says how it is checked and who runs the
check. On a stack the kit does not know, it can only name what it could not
check.
