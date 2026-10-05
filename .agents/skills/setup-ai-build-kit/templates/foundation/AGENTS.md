# AGENTS.md

(One line, written by the setup-ai-build-kit skill.)

Standing instructions for this project, read every session. This file is an
index: the standing rules in short form, then a pointer for each topic to the
file that owns it. Before any work, read the build-path section of
`masterplan.md`, right after its short header. It decides which evidence,
review, saving, and sensitive-area rules apply. Then read the relevant part of
the masterplan, the current piece, and the capability profile below. Never rely
on a hook, slash command, subagent, browser, or remote service the current
harness does not have.

Keep this file under 200 lines and hold only what the code cannot show: the
save and review routes, conventions that differ from the default, and pointers
to the records. Never add a directory layout, dependency list, architecture
overview, or style rule an automatic check could enforce, and never a date, an
issue number or a code name: a function, variable or file name from the
project's code. The project check fails above 200 lines. `/maintain` measures
it monthly and offers a trim when it reaches 200 lines or carries any of that
content, even below the ceiling. Cut nothing without the person's yes.

## Standing rules

The work lives in thirteen installed AI Build Kit skills. Eight are commands:
start the one the user types, names, or asks for in plain words, and say which
one you are running. Never start a command the user did not ask for. The other
five run in the background when a command needs them.

- Commands: `setup-ai-build-kit`, `shape`, `implement`, `queue`, `ship`, `sync`,
  `maintain`, `what-now`.
- Background skills: `clarify`, `change-triage`, `screen-check`,
  `section-builder`, `second-opinion`.

When a skill says to run another skill, load that installed skill and follow it.
Skills sit in `.agents/skills/`, `.claude/skills/` or a plugin's folder; a
pointer such as the `ship` skill's `templates/handover.md`, or `<name>/SKILL.md`
without native discovery, names a file there. Keep project rules here, never in
an installed skill. For GitHub failures, follow the `setup-ai-build-kit` skill's `references/required-tools.md`.

The user describes intent in plain language; change-triage chooses the route.
Build one agreed, visible slice at a time. Add nothing the slice did not ask
for, and never widen a fix into a tidy-up. When a written instruction and an
automatic check disagree, trust the check and say so plainly: it tests the real
work, and an instruction can fall out of date. Use the save route the build
path and change require. Private, disposable exploration may end in a confirmed
checkpoint. Shared, live, behavioural, data, access, integration, service, or
operational changes use a short-lived branch, a pull request, and the project
check. Commit with a clear message. A merge needs a yes naming it or a run's
pre-approval. Present what changed, what was checked and what is uncertain.

Every promised behaviour needs evidence: an automated check where a machine can
judge it reliably, a guided manual check for visual or exploratory work, a
source check for a decision that rests on an external fact, and a rehearsal for
backup, restore, migration, rollback, or other operational claims. When a
piece carries `visual`, or a change touches a screen file, load `screen-check`
before the guided manual check. It reads this project's design rules first and
never calls a screen accessible, compliant, or good.

The people directing the work are never asked to read code or logs: report
what they achieved in plain words, define a technical term once where it cannot
be avoided, and describe a check as an action with an expected result. Keep
progress updates tied to a decision, blocker, or visible outcome, never routine
inspection, command output, retries, or waiting. Immediately before a technical
confirmation, say what the person will notice, why it is needed, if anything
leaves the computer, if it is temporary or saved, what stays unconfirmed if
they decline, and that a confirmation box comes next.

The `setup-ai-build-kit` skill's `references/blocked-commands.md` always
applies. Save a checkpoint before sweeping work. Stop and ask when:

- the work exceeds the agreed slice, or needs a new dependency or service;
- the request changes data, access, money, automatic actions, reliance, or
  external users, or would delete data or do anything irreversible or outside
  this computer, such as a live service's settings: name all it changes and
  if it can be undone;
- a sensitive area's caution is a person who has not yet looked, or a risk
  notice is waiting on the person's answer;
- the masterplan is silent on a consequential decision, or the harness lacks a
  required capability;
- the expected result cannot be reproduced or verified.

### Areas and sensitive areas

Every folder belongs to an area named in the Areas section of
`docs/working-rules.md`. Move the map in the same save as the code; the project
check says whether it still matches. The build-path section may name sensitive
areas, each with a caution: a backup restored once, a managed service, or a
person who looks before the work goes live. Do the caution where it is the
kit's to do. Where it is a person's and they have not looked, give the risk
notice once, in full: who is exposed, what happens to them, what would
normally prevent it, what the person can do, and that you flag what you can
recognise and will miss things.

Nothing is refused, and the work does not stop there. If the person carries on
after the notice, that is their acceptance: record it in the build-path section
with the date and their own words, and build in that same reply, with no further
yes asked for. A lock that only waits for that caution opens with it, unless the
person asks to keep it. Silence is not carrying on. The record says the risk was
accepted, never that the caution was done. Cost, deadlines and team size change
what the person decides, never who is exposed, so never soften or drop the
notice, or recast a named control into something you can satisfy yourself. Where
the notice names who should look, that is a person, and no session meets it: not
a fresh one, not a subagent, and not the project's own review method. That
method exists for a different job from the one a named reviewer was named for.

### Secrets and confidential files

Keys, passwords, and tokens live in `.env`. Never print, commit, or copy one
into a document, check, or changelog, or write one to `/tmp`. Record where any
other secret lives, never its value, in the masterplan's "How it stays running",
and read it there. If none is recorded, ask once. Rotate a secret that appears
where it should not, even one given as a reply: record it nowhere, say it is now
in this chat, and ask for its location. A secret with no known location is never
called absent. Never take a login another tool stores for itself, as in the
keychain or its files, or use one on an API. Use that tool's own commands or
the project's own keys. If you cannot, say so and ask; never then read it
another way. If the project works from confidential files, founding records
their folder and handling rules here. Never stage, commit, print, or copy their
contents into code, checks, documents, or the changelog.

## The records

If it is not written down, it does not exist. `masterplan.md` holds the product
in the present tense, in roughly one or two pages; its build-path section
changes only by rerunning the fit check. Each piece is one issue, shaped as the
`setup-ai-build-kit` skill's `references/pieces.md` says, with a subject label
set once by change-triage; a merged pull request saying `Closes #<number>`
closes it. `plan.local.md` is a printout from `.agents/tools/plan-refresh.sh`;
change the issue, not the file. A piece writes its entry to its own file in
`changes/`; its merge folds it into `CHANGELOG.md`, or later /sync or /ship.
When one document says another will do a job, write it into that one too.

## Technical design

Lasting technical design lives in `docs/<concept>.md`, one concept to a file,
under the headings What it is, How it works, Rules, and Where it lives. A fact
that fits no file yet starts a new concept file, never a general notes file.
`docs/README.md` lists the concept files, and only those, each with what it
owns.

## Capability profile

What each line means is in the `setup-ai-build-kit` skill's
`references/capability-check.md`.

(Filled in by the setup-ai-build-kit skill: harness, file access, shell, Git,
local save identity, online repository, online account access, online
authentication, `Project check: <workflow file>, job <job name>`, `Walk-through
eyes:`, independent-review method, and optional harness capabilities.)

## Stack, and how to run and check it

Launch checks live in the recipe, shaped as the `ship` skill's
`references/recipe-format.md` says. The project check runs the commands below.

(Filled in by the setup-ai-build-kit skill: `Recipe: <file name>.md` or
`Recipe: none`, `Test command: <command>` or `Test command: none for
<language>`, then install, run, test, type check and lint commands, or
`none for <language>`, conventions that differ from the default, and
`Design tool: <name>` or `none recorded`. Leave dependency lists in code.)
