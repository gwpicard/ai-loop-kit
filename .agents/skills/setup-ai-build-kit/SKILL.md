---
name: setup-ai-build-kit
description: Begin a new project, or resume a beginning that was interrupted. Use when the user types /setup-ai-build-kit or asks to start or set up a new tool. Runs once per project; if the founding documents already exist and are complete, say so and point at /implement. Do not use for new features on an existing project (that is shape) or for repairs (that is fix).
---

# Start

You take a team from an idea to a project ready to build: interviewed,
assessed, documented, stood up. You write no feature code in this skill. It is
resumable: read what already exists, say plainly which step you are resuming
from, and carry on.

## Conversation contract

`/setup-ai-build-kit` guides the person through project decisions. Speak when they need to
answer a question, make a decision, approve an action, understand a blocker,
or see a result that changes what they can do next. Finishing an internal step
is not a user-facing result by itself. Routine reading, research, setup, and
checking happen quietly.

Ask every question in the shape clarify's "How to ask" section describes,
whichever step you are on. A short and complete set of answers may be offered
as choices; anything the person would answer in their own words is asked as a
plain question.

Do not narrate commands, search queries, package or version selection, retries,
waiting, terminal output, or internal technical reasoning. Record technical
choices in AGENTS.md. Name a tool or service in the conversation only when the
person must choose it, pay for it, create or own its account, grant it access,
or understand a limit that affects the product. When you name one, say what it
is in one plain sentence at the same moment, so the person can decide without
already knowing the word.

A harness may show its own command or status text. Do not repeat that text or
translate each line as it appears. If the harness requires an update during a
long operation, say only which visible outcome is still being checked and
whether anything has changed.

Give the plain permission explanation once, immediately before a real
confirmation box. Do not announce that a confirmation might appear later. If
the action and its boundaries were already explained, refer back to that
explanation instead of repeating the full checklist.

## Founding ends with something stood up

Every step below wants something from the person. None of them is a gate. This
skill is finished when the project exists and a checkpoint is saved, and that
outcome outranks any answer still outstanding.

An answer you would like but do not need becomes an open question in the
masterplan, your best guess recorded beside it, and founding carries on. Ask it
later, once there is a project to change.

A step that tells you to check something is a check, not an interview question.
Where a step says to answer from the masterplan, answer from the masterplan. A
gap found that way becomes a setup task or an open question, and the person is
told what was recorded rather than asked to fill it in.

A person who says to get on with it has answered everything outstanding at once.
Take the guesses, say in one line what you assumed, and stand the project up.

Founding that stops with nothing stood up has helped nobody, whatever it was
waiting for. There is no answer worth more than a saved project, because every
answer can still be changed afterwards and an unfounded project cannot.

## 0. Resume safely

Before anything is written, read which branch the folder is on. A founding once
saved its checkpoint onto a feature branch the person had checked out, so the
main branch never received the records and the commits were moved across by
hand. Read the current branch with `git branch --show-current`, or with
`git rev-parse --abbrev-ref HEAD` where an older Git refuses that. Then read the
default branch: the remote's, from
`git symbolic-ref --short refs/remotes/origin/HEAD` with `origin/` taken off,
else a local `main`, else a local `master`. With no remote and neither of those,
the current branch is the default.

A folder with no commits yet, or one already on the default branch, gets nothing
said. A detached checkout counts as another branch: name it by its short commit,
and go back to it with `git switch --detach <commit>`.

On another branch, look for unsaved work with `git status --porcelain`. Where it
prints nothing, switch with `git switch <default>`, or with
`git checkout <default>` where an older Git refuses that. Either one creates the
default branch from the remote's copy when it exists only there. Then say once,
in one line, close to: "This folder was on `<branch>`, so I moved it to
`<default>` before writing anything. That way the records land where every later
piece starts. Say if you want it founded on `<branch>` instead." This is not a
question, and founding does not wait for an answer.

Where it prints anything, never switch, because switching would carry or disturb
the person's work. Say once instead that founding stays on this branch because
it holds unsaved work, and that the records reach `<default>` only when this
branch merges.

Where the switch fails, stay on the current branch, say so and why in that same
one line, and carry on founding; never stop for it. The usual cause is a
worktree made by another tool, where the default branch is already checked out
in another folder.

Where the person says to found on their own branch, in the interview or in
answer to that line, switch back to it before the founding save with
`git switch <branch>`, and write that choice into the setup notes so a resumed
founding keeps it. The folder held nothing of theirs unsaved, and founding's own
files usually move across with the switch. Where Git refuses the switch back,
because a file founding wrote would overwrite one on their branch, stay, say so
once, and carry on as for any failed switch. The founding save below says what
is then written down.

This read runs again whenever founding resumes, from the setup notes or from
anywhere else, so a founding picked up on another branch meets the same rules.
Files founding wrote itself in an earlier session are not the person's unsaved
work: stay on the branch that session left, and say nothing more about it. In
the kit's own source, where `release-manifest.txt` and `docs/MAINTAINING.md` sit
at the root, switch nothing.

Then run `scripts/bootstrap-project.sh` from this installed skill folder in
the project root. It creates only missing project foundation files and leaves
anything already there untouched. If the harness cannot run the script, copy
the missing files from `templates/foundation/` to the paths named by the
script. Never replace an existing file during this preparation. When an
existing `AGENTS.md` lacks the installed-skill load rule, preserve its project
instructions and add the smallest compatible rule before continuing.

The same script works when a coding agent runs this skill from a plugin, in
Claude Code or through the Agent Plugins format. If it reports that the
project has both a plugin and a separate AI Build Kit skill installation, stop
before preparing the project. Keep the plugin when one coding agent runs the
project, or keep the shared skills installation when the project uses more
than one coding agent. Never leave both active. If it stops at a broken link,
say so in plain words and offer to install the kit again the same way, which
repairs it. If it prints a setup note instead, about an empty skill folder or a
second copy that differs from this one, founding carries on: say the note once,
in plain words, and record it as an open question in the masterplan.

A folder holding the kit and nothing else is the normal place to found a
project, not a reason to stop. A fresh installation leaves `README.md`,
`WORKFLOW.md`, `docs/`, `.agents/skills/` and `agent-plugin/` in the project
root, which reads exactly like the kit's own source code, and the answer is not
to guess from how it looks. Look for `.ai-build-kit-version`: every release
carries it and the kit's source never does. Where it is there, this is an
installation waiting for a project, so found here without asking.

The kit's own source is the one place founding does not belong, and it says so
plainly: `release-manifest.txt`, `.agents/tests/` and `docs/MAINTAINING.md` sit
at its root and reach no release. Only where those are present is stopping
right, and then say which of them you found rather than describing the folder.

Never make a location the thing founding waits on. Where the person meant a
different folder they will say so, and a project founded in the wrong place
costs a move; a project never founded costs everything that was said to get
there.

Read the repository's current state before doing anything else. Check whether
masterplan.md and CHANGELOG.md already exist, whether the project's pieces
exist as issues, and whether any of them look complete or
half-written. Check for unfinished setup: an uncommitted change, an open
question left in the changelog, or a placeholder still in the file the
capability profile's `Project check:` line records, which is
`.github/workflows/checks.yml` only where that is the file recorded or no line
is written yet. Say plainly where the process is resuming from. Never
overwrite an existing record without saying so and getting agreement first.

Look for `.agents/tmp/setup-notes.md` in that read. It holds the answers agreed
so far when an earlier session stopped before masterplan.md existed. Where it
exists and masterplan.md does not, say you are carrying on from those answers,
read them back as one short list, and wait for a yes. Handle a correction the
way you handle a wrong guess: the person says what changed, and you update the
file.

## 1. Orientation

Before any technical action, say what is about to happen, close to: "First
I'll help turn your idea into a small plan. Then I'll prepare a private
working version, check that it opens, and save a checkpoint. Nothing will be
published or shared unless I explain that separately and you approve it."
When step 3 finds an existing project to adopt, replace "turn your idea into
a small plan" with something about understanding what already exists before
anything changes. Say nothing about GitHub or shared setup here; it is
set up later, at the step that creates the pieces, not now. Skip
repeating this when a resumed session already covered it in step 0.

## 2. Capability check

Load references/required-tools.md before the tooling check. Its "When GitHub
access fails" route applies to a network failure or a client refusing a command;
request the needed access before treating the person as signed out.

First run `scripts/check-tooling.sh` from this installed skill folder. It reports
whether Git, the GitHub command line tool, and python3 are ready and signed in,
so a missing one is caught here rather than at the later step that creates the
issues. It also says what the walk-through can look with. A missing one of
those never stops founding: pass on the install command it prints, and leave
installing to the person. If the harness cannot run the script, work through
references/required-tools.md by hand. When a tool is missing, guide the install
following references/manual-setup.md before going on.

Load references/capability-check.md and work through it. Record the result in
AGENTS.md under Capability profile: harness name when known, file read/write,
shell, Git, local save identity, online repository, online account access,
online authentication, available test/runtime commands, the walk-through's
eyes, independent-review options, the reach-check engine, hook support, and
subagent support. Choose a
fallback for anything missing. Do not make the user configure an optional
feature before the interview; a missing capability becomes a setup task or a
reduced-automation fallback, decided later at the step that needs it.

## 3. Fresh project, or adopting something that exists?

Ask whether code already exists: an app built in an all-in-one builder, a
tool living inside a chat assistant, an earlier attempt. If yes, follow
references/adopting.md, which reshapes the steps below around what exists;
the one-line summary is read first, interview against reality, pin down
behaviour before changing it. If starting fresh, continue here.

## 4. Test the need for software

Test the idea against the ladder, cheapest first: a process change, a feature
in something the team already pays for, a spreadsheet or database view, an
off-the-shelf product, an automation inside an existing service, a configured
AI chat, an agent skill, a lightweight form or no-code workflow, custom
software. Ask the four questions: will it keep records that build up over
time? Will other people use it without the person who made it? Should it act
on its own? Must it enforce rules? Where custom software does not provide
material value over something cheaper, say so once, plainly, and say what would
do instead. Saving the team a project is a good outcome.

Say it once, and do not stop to ask. The case is made in one reply, at this
step, and the same reply carries straight on into the next one. Do not end the
turn on it, do not ask which way they want to go, and do not wait for an answer:
a person who wanted the cheaper thing will say so unprompted, and one who did
not has lost nothing. Naming a product they might already have is enough. Do not
tell them to go to whoever administers it, because that turns a remark into an
errand.

If they want the tool anyway, that is their decision and not a fault to be
corrected: record the cheaper option and the choice in the masterplan, and carry
on founding. Do not ask the question again, do not hold the interview open until
it is answered, and never make an answer a condition of founding.

## 5. Founding interview

Run the clarify skill for the founding interview. During it: resolve
overloaded terms rather than letting them pass; use concrete examples to
settle ambiguity; invoke source research when an answer depends on an
external fact; settle a visual or behavioural question with a mock or
sketch the person already has, or a disposable decision prototype where they
have none; keep open questions visible
rather than quietly guessing past them. It ends when your guesses keep being
right.

Write each answer into `.agents/tmp/setup-notes.md` as it is agreed, before
asking the next question, so a long conversation cannot lose it. Plain
sentences under the question they answer, no template. Before that first write,
check `.gitignore` carries `.agents/tmp/` and add the line when it is missing,
so the notes stay out of every commit. Say nothing about the file: it is
housekeeping rather than a decision the person makes.

## 6. Fit check and build path

Go through references/fit-check.md: the consequence and ownership questions,
one at a time, guesses attached like the interview. Record the result in the
same working notes as it is settled: which of the three build paths, why,
each sensitive area and its caution, the recheck triggers, and today's date.
Before naming a sensitive area, work through the redesign options in
fit-check.md; if a redesign changes the answers, run the check again. Where an
area survives that, give the risk notice fit-check.md describes, once and in
full, before any of the flagged work goes ahead. If the person carries on after
it, write their acceptance into the working notes with their words and the
date, so the masterplan's `Accepted:` line carries it, and go on in that same
reply. Do not ask a further yes, and do not keep a rule in the plan that only
waits for the caution they skipped. If they do
not, founding goes on anyway and the area's caution stays `not yet done`. A no
to an ownership question becomes a founding task rather than a path move.

## 7. Write the masterplan

Create masterplan.md from templates/masterplan.md, filled from the interview,
present tense throughout. Open it with its short header for the person: two or
three plain sentences on what the tool is, who uses it, and where it stands.
Write everything below the header for the agent first, complete and exact. The
build-path section comes right after the header: the fit check's result. Create `.ai-build-kit-maintenance`
from `templates/maintenance-record` and put today's date on its `founded` line.
Leave the two pass lines empty, because `/maintain` fills those in. Do not
mention that small file to the person.

Add a line to that file, written as `kit|<version>|<commit>`, so the project
records which AI Build Kit release it holds. Take the version from the installed
`maintain` skill's `VERSION` file. A whole copy of the kit can lack that file,
and then `.ai-build-kit-version` at the project root gives the version. Take the
commit from the release's tag with
`gh api repos/gwpicard/ai-build-kit/git/ref/tags/<version> --jq '.object.type, .object.sha'`.
Where the type it prints is `tag` rather than `commit`, the tag is annotated:
read `.object.url` once with `gh api` and take the commit from its
`.object.sha`. Where the lookup fails, because GitHub is signed out or out of
reach, write the commit as `unknown` and carry on founding. A missing commit
never stops a founding. A resumed founding that finds a `kit` line already
there keeps it.

Create CHANGELOG.md from its template, and write its first entry under today's
date, naming the same version and commit, close to: "Founded with AI Build Kit
v0.19.2, commit fd0780a." The first seven characters of the commit are enough
there. A resumed founding whose CHANGELOG.md already holds that entry writes it
no second time. It has to exist before the next step writes to it.

Do not create team.md; it no longer exists. Fill in AGENTS.md's project line
and the capability profile from step 2. Replace README.md's project-name and purpose placeholders with a
short description taken from the masterplan.

Where README.md holds no such placeholders, it is somebody's real file: an
installation that arrived as a whole copy of the kit leaves the kit's own
read-me at that path, and an adopted project has its own. Leave it exactly as it
is. Say in one line that the description is going into masterplan.md and
AGENTS.md instead, and carry on. Never overwrite it, and never stop to ask which
the person would prefer. A read-me is the cheapest thing in the project to
change later and the founding is the most expensive thing to lose.

Fill the masterplan from the working notes as well as from the conversation,
then delete `.agents/tmp/setup-notes.md` in this same step. The masterplan
carries everything the notes held, so nothing is lost by clearing them.

Draw the connections section from what the interview found, then read the
picture back in plain words and let the team confirm each outside connection
before going on: that it should reach their email, their calendar, whatever the
picture shows. A connection nobody meant to agree to is cheapest to catch here.

Where the tool has sign-in, or keeps a history that grows over weeks, offer a
small set of sample data or test accounts once, so that each build can walk
through the tool with something in it. Say it close to: "Each build checks its
work by using the tool the way you would. Shall I plan a few made-up records and
a test account for that?" Write the answer as a `Sample data:` line in the
masterplan's "How it stays running": what the set holds and where it lives, or
that the person said no. A yes becomes a piece when the plan is cut in step 10.
A test account's password goes where the Secrets rule says, never into the
masterplan. The offer never holds founding up: with no answer, write
`Sample data: not agreed yet` and carry on. A tool with neither sign-in nor a growing
history needs no offer, since a build makes up the small case it needs.

On Build with care, write the sensitive-area paths and any one-line boundaries
from `references/fit-check.md`, read each area and its home back in plain words,
then run the sensitive-area check installed by the bootstrap step. On the other
two paths, leave the map absent; the check says nothing.

If docs/MAINTAINING.md exists, delete it as part of this same commit. Current
starter releases exclude that source-only file, but older direct clones
may still contain it. Do this yourself rather than asking the user to remember.

If the project needs a `.env`, copy `.env.example` to `.env` now, confirm
`.env` is listed in `.gitignore`, and never print its contents back to the
user.

## 8. Review the masterplan

Who this is for decides whether it runs. On Build with care, the masterplan is
read before flagged work continues, because somebody other than the builder is
going to be relied on and the plan is what they will be relied on against. On Build and run it, skip it: an ordinary
internal tool has no exposure for a reviewer to find, and a review nobody needed
costs the person a wait they did not ask for. Say in one line that it was
skipped and why, and record that in the changelog, so a project that later moves
up a build path knows this never happened.

Where it does run, use the best independent method recorded in the capability
profile: an independent subagent, a clean separate session, or a user-opened
clean chat with a prepared instruction. A same-session fallback is permitted
only for Explore privately, and must be labelled plainly as not independent.

Where no independent method exists at all, say so, record it in the changelog as
a setup gap to close before flagged work continues, and carry on founding. Do
not wait for one to appear. This step used to stop until the review had
happened, which in a session with nobody else to ask is a wait that never ends,
and it cost two measured runs their whole founding. A masterplan nobody has read
is a gap worth naming; a project that was never stood up is not worth trading
for it.

When resuming, look for the review's note in the changelog.

## 9. Ownership check

Answer from the masterplan alone, no memory allowed: can the team explain the
main flow? Can it explain who can see and change what? Can it identify where
important data, secrets, and service accounts live? Can it recover or
continue manually if the tool stops? Is somebody responsible for alerts,
backups, bills, and access? A "no" to any of these becomes a setup task before
build starts: a piece on the plan where there is work to do, or a line in the
masterplan's "How it stays running" section where there is only a fact to
record, following fit-check.md's ownership rule. It never moves the build path.
The fit check owns the present facts in "How it stays running"; the changelog
records only that this ownership check ran and when. Do not copy the answers
into the changelog.

## 10. Cut the plan

Pieces sized for one sitting, and small enough for a fresh session to hold
whole, in the order they unblock each other, each cutting vertically through the
whole tool so the unknowns surface early: what the user can do or see when the
piece is complete, its evidence, and its genuine dependencies. Do not split one
user capability into separate "database", "API", and "UI" pieces.

Before the first issue, check which repository the project points at. A project
founded from a whole copy of the kit can keep the kit's `origin`, and the
GitHub tool would then open its pieces on the kit's own repository,
`gwpicard/ai-build-kit`. The tooling report in scripts/check-tooling.sh says
so when it finds that. Where it does, change nothing there: open no issue, make
or remove no label, change no setting, and push nothing. Say in one line that
the project still points at the kit's repository, and ask for the person's own.
With one, point `origin` at it, run the report again, and carry on with what it
finds. With none, save everything else and say plainly that the pieces are
created once the project has a repository of its own, the way the last
paragraph of this step handles a GitHub setup that cannot be finished.

Each piece becomes an issue, written to the shape in references/pieces.md. This
needs a GitHub repository and the GitHub command line tool signed in; where that
is not yet in place, guide the person through it now, following
references/manual-setup.md, because the pieces live as issues and there is no
file-based substitute. A private repository keeps issues just as well as a
public one, so a project that wants to stay private still uses one. Do this
without narrating it.

Before the first issue, create the label set with
`python3 .agents/tools/gate.py labels`, which makes the 26 labels in
references/pieces.md and names any this account could not create. Then
delete the labels GitHub made by itself, and copy
templates/foundation/piece-issue.yml to `.github/ISSUE_TEMPLATE/piece.yml`.

Open each piece through the gate script, never with `gh issue create`. Write
its body to a file and open it with `gate.py capture`, which gives it
`state:shaping` and `shaping:raw`. Then give it exactly one `type:` label with
`gh issue edit` before its first move: `type:feature`, `type:bug` for behaviour
the masterplan promised that does not work, or `type:chore` for upkeep nobody
would notice in the tool. Add every subject label that fits. Move it only with
`gate.py move`, which checks each move and refuses a wrong one. The commands,
in order:

```sh
python3 .agents/tools/gate.py labels
gh label delete "<label>" --yes
python3 .agents/tools/gate.py capture --title "<title>" --body-file <file>
gh issue edit <number> --add-label "type:<feature|bug|chore>"
gh issue edit <number> --add-label "<subject>"
python3 .agents/tools/gate.py move <number> <target>
```

A piece that still holds an open question for `/shape` to settle carries it
under `## Open question`, one question, and moves to `clarify`, `research` or
`prototype`, whichever says who can answer it. A piece founding shapes fully
moves to `spec`, then to `check` once its contract is written, and ends in
`shaping:check`. Founding runs the readiness check in the `shape` skill's
`references/readiness-check.md` on each shaped piece through a session that
did not shape it. The piece moves to `state:ready` only through the gate, with
`gate.py move <number> ready`, which needs a `## Readiness` section saying
Ready with no blocking line. On Not ready, move it to the sub-state its first
blocking line needs. Where the coding agent cannot start such a session, each
shaped piece stays in `shaping:check`, and is checked before it can be built.
When the gate refuses a move, do what its `next:` line says, and never write a
state label by hand. Link the pieces that genuinely block each other using
GitHub's blocked-by relationship.

Then run `sh .agents/tools/plan-refresh.sh` once, so the person has their list
before they need it. The bootstrap placed that helper in the project, whichever
route installed the kit.

Set the repository to delete a merged pull request's branch automatically, so
the branch list does not fill with finished piece branches
(`gh api -X PATCH repos/OWNER/REPO -F delete_branch_on_merge=true`), and say in
one line that you did. That is the whole of the pull-request hygiene the kit sets
up on the repository. A direct push to `main` is forbidden by
references/blocked-commands.md, and the Claude Code settings refuse the usual
ways of writing one, rather than a branch protection rule.

The labels GitHub creates on a new repository are `bug`, `documentation`,
`duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`,
`question` and `wontfix`. Delete every one that is still there. This is safe here
and only here, because founding happens before any issue exists to be wearing one.

Say which ones went, in one line, rather than deleting them silently. Where the
account cannot delete a label, say which stayed and carry on: a leftover label
is untidy rather than harmful. Anything a person added themselves is left alone
under the ordinary rule.

An idea that did not make the cut is opened with `gate.py capture` like any
piece, then closed as not planned with `gate.py drop <number> --reason "<why>"`,
which keeps the reason on it.

With the pieces created, load references/coverage-read.md and run the coverage
read against the masterplan. This is the cheapest moment in the project's life
to find a promise nobody planned to build.

Where the person cannot complete the GitHub setup in this session, save the
masterplan and everything else, and say plainly that the pieces cannot be
created until the GitHub command line tool is signed in. Name that as the one
remaining step. Do not invent a file in its place; the pieces live as issues,
and this step is only finished once they exist.

## 11. Stand the project up

Ask two questions: will the team use this in a browser, and does it need to
work when your machine is off? Ask them even when the menu holds a single
recipe, unless the interview already answered them. From those answers and the
interview, name the app's shape in one plain sentence, such as "a web app your
team signs in to, with saved data".

Then offer the recipe menu. A recipe is one build stack paired with one place
to run it, which the kit knows well enough to check at launch. The installed
ship skill sits beside this skill's folder, however the kit was installed, and
its `ship/references/recipe-format.md` says what a recipe holds. The menu is
the files directly in the `recipes/` folder of the installed ship skill, beside
this skill's folder, read now rather than remembered. Nothing else is on it:
not the `parts/` folder, and not a recipe kept anywhere else while it waits for
its real run. Read each file's `Fits:` line and keep the ones that fit the
shape.

If one recipe fits, recommend it and still show it as a menu. A menu of one
follows every rule below, as a longer menu does, including the sentence naming
it the default, and it is shown in a reply before the stand-up begins, never
only as a choice reported in the completion report. If several fit, recommend
the one whose `Recommended when:` line best matches what the interview said, or
the first by file name when none or several match. Show the ones that fit with
exactly one recommended. For each, say in plain words what it promises: the
launch steps the kit can check on it, such as preview, rollback, backup and
restore. Say what running it involves in the same plain words, meaning which
accounts the person will hold and whether the tool runs on a hosting platform
or on a server they rent. Never quote a price. Take every product name from the
recipe file at this moment, and never write one into this skill. Say that they
may bring their own stack instead.

Read each offered recipe's `Plan terms:` line, where it has one. When the
interview shows the tool is for a work team, a business or any paid work, say
that line once, in plain words, beside that recipe: which plan such a team
needs, and that the free one is not meant for them. Never then call that
recipe's account free or say a free plan fits them. For a personal project
nobody is paid to build, leave the line out, since it does not apply. Where the
interview did not say, ask nothing: give the line once as a condition, such as
"if this is for work".

In the same reply, say that the recommended recipe is the default and that
founding carries on with it unless they pick another. Showing the menu does not
end the turn: carry on with the setup below while they read it. If they give no
answer, or say to get on with it, keep the recommended recipe. The menu is
never a condition of founding.

If they choose their own stack, say once what the kit then cannot check: the
launch steps a recipe would have checked. Record their choice and `Recipe:
none`, and do not raise it again. Where no recipe fits the shape, such as a
command-line tool or a desktop app, say so in one line, record `Recipe: none`,
and set up as below without a menu.

Whatever the choice, record the menu this step read, so a later monthly visit
can tell which recipes joined it afterwards. In `.ai-build-kit-maintenance`,
which step 7 created, add one line, replacing any earlier one without asking,
since it is kit bookkeeping and not one of the project records step 0 protects:
`founding-menu|<YYYY-MM-DD>|<menu files, comma separated>`. List every file
directly in the `recipes/` folder, including the ones that did not fit, each
written exactly as it sits there with `.md` included. Write this line before
the first checkpoint, so the save holds it. Do not mention it to the person.

Once a recipe is chosen, build on its `Build stack:` line. Record it in
AGENTS.md's stack section as `Recipe: <file name>.md`, the file name exactly
as it sits in the folder with `.md` included, so /ship can open it. Run
`scripts/check-tooling.sh --recipe <recipe file>` from this installed skill
folder, passing the chosen file's path inside the ship skill's `recipes/`
folder beside it. Run it for every chosen recipe, a menu of one included,
before the first checkpoint, and let the completion report's recipe line say
what it found. A tool it reports missing is needed before the first /ship,
not now: name it once, add it to the masterplan as a setup task, and carry on.
That report never stops founding.

Without a recipe, set up accordingly: one established, conventional stack,
because the agent is strongest where the conventions run deepest.

Write the masterplan's `Goes live:` line in "How it stays running" before the
first checkpoint, from answers founding already has, and ask nothing new for
it. On a recipe, write what its going-live section says, read as the
`section-builder` skill's `references/merge.md` reads it: `on every merge`
where a change to `main` goes live, and `through /ship` otherwise. Off a
recipe, write `Goes live: not hosted` where the interview or the two questions
above say nothing is hosted, because people install the tool, copy it, or run
it on their own computer. Otherwise write no line, and the first merge asks.
In the same save, set the confirmation box as the `section-builder` skill's
`references/merge.md` says under "The confirmation box on a merge that goes
live": `add` for `on every merge`, `remove` for any other value.

On any stack, recipe or not, use managed services for anything storing
sign-ins, payments, or files; those never get hand-built, however capable you
feel, unless a person who does that work for a living owns a different design
and has said so on the record. Use references/manual-setup.md for any step only
a human can complete. If hosting is needed, arrange it so day-to-day pushes
land at a preview address and only /ship changes the address the team uses; on
a recipe, its preview section says how. Where a hosting companion or whoever
runs the server will host it, /ship writes the hosting request on the first
launch, and the person takes it there.

Choose routine technical parts quietly. Record run and check commands and any
non-standard conventions under AGENTS.md's stack section, keeping its content
rule and line ceiling. Name the install command among them, since a run
installs each worktree's dependencies with it. Leave dependency lists in the
code. In the conversation,
describe what the setup lets the person do. Name
a product or service only when it creates a choice, cost, account, access step,
ownership duty, or product limit that the person needs to understand.

Read the design tool, if any, from answers already given. Where one was named,
record it in the stack section. Where none was named, write `Design
tool: none recorded`. Do not add a founding question. If the first structure
prototype could use a design tool and none is recorded, ask once then and
update the stack section. That later question must never stop founding.

If the interview surfaced confidential working files, create their folder
now, add it to .gitignore, and record the handling rules in AGENTS.md. Write
`confidential|<folder>` to `.ai-build-kit-maintenance` as well, so the worktree
script can refuse that folder without reading prose. If the tool keeps a list
of files to carry into a working copy, add the folder there too; in Claude
Code that list is .worktreeinclude. That list is for Claude Code's own
worktrees. The kit's run worktrees read the `worktree-links` line instead. The
worktrees the kit opens for a run do not carry that folder, so a piece that
needs those files is built with the person present, never in a run.

A build can need files git ignores that hold no secret, such as licensed fonts
or large sample inputs, and a run's worktree has only what it links. From the
project root, run the `implement` skill's `scripts/worktree.sh` with `candidates`. It
lists the ignored files and folders at the top two levels, leaving out
dependency and build folders, every `.env` file, `.agents/`, `.claude/`,
system files such as `.DS_Store`, and the confidential folder. Where it lists nothing, write no line and ask nothing.
Otherwise ask once which of them a build or a walk-through needs, with your
best guess attached: a font, a sample input, or an asset folder the build
reads. Ask it beside other work, so the question never ends the turn on its
own. Write the paths the person confirms to a `worktree-links|<path> ; <path>`
line in `.ai-build-kit-maintenance`. Where founding ends with no answer, write
no line: `/maintain` offers the question again.

Wire the project check according to the build path. Where the bootstrap
script named a workflow of the project's own that already runs its tests on
pull requests, or `.github/workflows/` holds one, load
`references/project-check.md`: it chooses the job, records it, and offers the
kit's steps once. Otherwise, if `.github/workflows/checks.yml` is missing, copy
it from `templates/foundation/checks.yml`, and record `Project check:
.github/workflows/checks.yml, job project-check` in the capability profile.
Explore privately needs a local test or smoke command, and the remote
pull-request check stays optional; Build and run it, and Build with care, both
need the remote check working before any shared or live behavioural work.

Configure only the job the `Project check:` line records.

In the kit's own `checks.yml`, replace the placeholder `Install and test`
commands with the project's real install and check commands. A job of the
project's own already runs its real commands, so leave them as they are.
Load `references/check-floor.md`: those commands include a type check and a linter wherever the project's
language has them, and a language without one is recorded as having none.
On Build with care, where an area in the map names a boundary, load
`references/boundary-rules.md` and offer once to have the check hold it.

An older project may still carry the legacy `source-kit-validation` job and
its repository conditions. Leave that job and its conditions unchanged. Edit
only the recorded job in either layout.

Do not replace the entire workflow file from memory. Edit only the
placeholder step, or add the steps `references/project-check.md` offers, unless
the project genuinely requires a broader workflow change.

Say one sentence about it when done: "green means the tests really passed;
red means don't merge, tell /fix."

Before starting the unfinished project to prove it runs, explain the action
using the rule in AGENTS.md, close to: "I'm going to start the unfinished
tool briefly and check that its main page opens at the recorded address. It
will run only on this computer, nothing will be published, and I'll stop it
again once the check is done." Where the harness allows it, treat starting,
checking the page, confirming the address, and stopping as one understandable
operation rather than several unrelated technical approvals, then give
AGENTS.md's warning that a technical confirmation box may appear next.

Before the first checkpoint, check whether the project already has a
suitable save name and email configured. Never invent a real identity, and
never copy the latest commit's author: that person may be the kit's own author,
an earlier collaborator, or someone with no connection to whoever is sitting
here now.

Where none is configured, do not stop for one. Save under a project-only
neutral label, "Local project user", applying only inside this project, and say
in one line that the checkpoint carries that label, that it can be changed, and
that no online account was created and nothing was uploaded. Record the real
identity as an open question in the masterplan.

A neutral label is not an invented identity, which is what that rule protects
against, and it is the same fallback this step already offered a disposable
experiment. Waiting for an answer here costs the whole founding, and a label on
a checkpoint is among the cheapest things in the project to change afterwards.

When the setup is ready to save, say so before saving, close to: "The
initial setup is ready to save. I'm going to save a checkpoint inside this
project so this working state can be recovered later. Nothing will be
uploaded."

Finish with: one command that proves the project starts, one small passing
behaviour or smoke check, a recorded preview or local run path, and the initial
state saved as a checkpoint on this computer. Load
references/completion-report.md and report the result in its shape.

The founding save is always the checkpoint route, whatever the tool will grow
into. It stands an initial state up rather than changing anything anybody
relies on, so there is nothing yet for a reviewer to compare against and nothing
live to protect. Do not push it, do not open a pull request for it, and do not
read a remote being reachable as a reason to use one. Founding already told the
person "Nothing will be uploaded", and that has to stay true. Where the online
repository holds none of the code yet, the code stays on this computer until
the first piece that pushes asks the person first, as section-builder's "The
first upload" describes.

Where founding saves anywhere but the default branch, because the person chose
their own branch, the branch held unsaved work, or the switch failed, say so
where it lasts. Write a line in CHANGELOG.md under today's date naming the
branch and the reason, and saying the records reach the default branch when it
merges. The completion report says the same.

section-builder chooses between the checkpoint, pull-request and flagged routes
for each piece built afterwards, on what that piece touches. That choice is
about the work, not about this. A tool the whole team will share still founds
locally, and its first piece takes whichever route it earns.

## Done when

The build path is recorded, the records exist (masterplan.md, CHANGELOG.md, and
the pieces as issues), AGENTS.md contains the capability profile and project
commands, the masterplan has had whatever review its build path called for or a
changelog line saying why none ran, the initial state is saved as a local
checkpoint, the plan is made of visible pieces each carrying one state,
`state:ready` or `state:shaping` with one sub-label, and one `type:` label, one
check passes, and the user has received the plain-language
completion report, which ends on a clean cut naming `/implement` and `/shape`
rather than an offer to build in this session.
