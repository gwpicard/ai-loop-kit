# WORKFLOW.md: how this project runs

This is the reference card. When you are not sure what to type, read this page,
or type /what-now and let it tell you. Type a command as `/` and its name
(`/setup-ai-build-kit`, `/shape`, `/implement`, and so on), or ask for it by name. You can also
just say what you want done, in your own words, and the agent picks the command
and says which one. The Claude Code plugin
adds the prefix `ai-build-kit:`, so `/setup-ai-build-kit` becomes `/ai-build-kit:setup-ai-build-kit`.

The kit is for technical builders who direct agents. It takes Git, branches and
pull requests as familiar and uses those words without explaining them. It never
asks you to read the code.

You shape the work; the kit builds it in loops and checks it against a bar fixed
before the build.

## 1. Commands

Command names say when to use them.

| When | Type |
|---|---|
| I'm starting something | /setup-ai-build-kit |
| I want it to... (a new idea) | /shape |
| Build the next ready piece | /implement |
| I'm taking on several things | /queue |
| It's broken | /fix |
| I think it's ready | /ship |
| I'm done for today | /sync |
| It's been a while | /maintain |
| I'm lost | /what-now |

Two of them change the tool. /implement makes it do something new or different, and /fix brings it back to doing what it already should. /shape decides what to change next and turns it into a ready piece, without touching the tool yet. The other six are housekeeping around those.

You run /setup-ai-build-kit once. After that, start wherever you actually are. You can open a session with /fix as readily as with /implement, and neither needs the other to have run first. If you pick the wrong one it costs you nothing, because each checks what you typed against the masterplan and sends it down the right route.

You never choose the method either. The agent decides whether the request needs an interview, a prototype, research, a test, a review, or a person to look at one area.

## 2. The three records

The records are the project's memory. The agent forgets everything between sessions; these don't, and every piece of work starts by reading them.

Two of them are files you can open. The third, what's left to build, lives in your project's issues on GitHub, because that is what lets more than one person work without clashing over the same file. You never have to open it: `/what-now` tells you where things stand, recaps what the recent work was about, names anything broken or left unfinished, and tells you when a piece is waiting on something only you can do, such as opening an account or handing over a key, and a plain list is printed to `plan.local.md` on your own machine so you can always see it, even when GitHub cannot be reached. That printout is a photocopy. Nobody edits it, and changing a piece means telling the agent, not editing the file.

If refreshing the plan fails, you see the GitHub error with credentials masked
and a recovery step. The last printout stays as it was, with its age reported.
For a Codex session that cannot reach GitHub or use its stored login, follow the
[GitHub access guidance](docs/COMPATIBILITY.md#github-access-in-codex).
The kit carries a launcher for a fresh Codex session to use your existing login
without saving the credential. It runs from an ordinary terminal.

| Record | Purpose |
|---|---|
| masterplan.md | What the tool is, in the present tense. Its first part, the build-path section, records how careful this project needs to be. |
| the project's issues | What's left to build: one issue per piece, each with what done looks like, its evidence, and what it needs. `/what-now` reads them for you. |
| CHANGELOG.md | What happened, dated, in plain language, when work actually landed. Each piece writes its entry to its own small file in `changes/`, so two pieces built at the same time never change the same lines. Merging a piece folds its file, and any still waiting, into CHANGELOG.md under the day each reached `main`; /sync and /ship catch any a merge made on GitHub by hand left behind. |

`AGENTS.md` sits alongside the three records as the instruction file the agent reads to know how this repository works. It is a short index: the standing rules, then a pointer for each topic to the file that owns it, such as the stack's recipe or a design note in `docs/`. The records are written for the agent first, each under a short header you can read, such as the few plain sentences that open the masterplan.

The dividing rule: the masterplan describes the present, the plan holds the future, and the moment a sentence is about when, why, or how something was built, it belongs in the changelog.

You can work with the issues yourself, and nothing you do there will be undone. Open one and write it however you like, in as little as half a sentence. /shape settles what done means with you and marks the piece ready; /implement builds only ready pieces and never guesses past an open question. If a piece is not ready when you reach for /implement, it points you to /shape and takes the next ready piece instead.

A piece is written in two layers. The short header you read says, in plain words, what the piece is for, what done means, including the cases that are not the normal one, such as empty or failing, and what it changes in the masterplan. Below it sits the agent layer, which is complete: every choice you would notice by trying the tool, the data it stores, anything that leaves the tool, the rules it must still meet, what it relies on and which areas it touches. A field that does not apply says why in one line, so a small piece stays short. The build detail sits in a collapsed "under the hood" section you never have to open. Anything that affects the whole product is written into the masterplan instead. Lasting technical design goes into its own file in `docs/`, one concept to a file, listed in `docs/README.md`. AGENTS.md keeps only rules and a pointer to that list, so no fact is copied into two places.

A decision can say what it rests on, in one short line beside it. When /shape
uses that decision, or /sync checks the masterplan, the agent reads its support
again. If it has gone, you hear which decision has lost its ground and answer
in plain words. You never have to read a test or find a saved change yourself.

Assign yourself to claim a piece, or let the agent put your name on it when it starts; either way nobody else builds the same thing. Close an issue you have decided against and it stays closed. Labels of your own are left alone, and milestones and boards are ignored entirely, so you can use them however suits you.

A piece too big to build in one go is split into parts. You will see it marked "made of parts" with a count of how many are done. The agent builds the parts one at a time, and the whole piece closes itself when the last part is finished, so there is nothing for you to tick off.

Each piece is labelled with what it is about. The labels are not decoration: they decide how carefully the agent has to prove the work.

| Label | The piece is about |
|---|---|
| `visual` | the interface |
| `how it works` | the rules and logic |
| `data` | information the tool stores |
| `accounts and permissions` | who can get in |
| `finance` | charging, refunds, pricing |
| `external service` | somebody else's system |
| `background automation` | anything that runs on its own |

A piece often carries two, because a checkout is finance and an outside service at once. More labels means more proof and a more careful save.

Every open piece is in exactly one state, and a label says which: `idea` when it is only written down, `shaping` while a question about it is being settled, `ready` when it can be built, `building` while somebody is on it, `to check` when its pull request is waiting for you, and `parked` when it has stopped, with the reason written on it. An issue you open with no label counts as an idea. A closed issue is done, except an idea you decided against, which stays closed and labelled `parked`.

A piece waiting on another piece keeps its state and is linked to it. `plan.local.md` prints the states as the columns of a board, after anything that needs attention, such as a piece carrying two states or a piece being built or checked that was never shaped, and anything broken. `broken` sits beside the state on a repair, and sends it to `/fix`.

Three more labels sit beside `shaping` and say what the question needs: `needs-clarification` (talking it through settles it), `needs-prototype` (a throwaway is needed first to see what it should look like), and `needs-research` (a fact from outside the project is needed). Anything you jot down starts as an idea; `/shape` settles it and marks the piece `ready`, and `/implement` builds only ready pieces. What settled it is written onto the piece before the label changes, so a month later you can see what was decided rather than only that something was.

## 3. The build path

Every project has exactly one build path at a time, set by the fit check and rechecked as the project changes character.

**Explore privately.** Nobody depends on it yet, data is disposable, and nothing it does is hard to undo. Manual checks are fine for visual and exploratory work, and a confirmed checkpoint commit is enough to save it.

**Build and run it.** The team's own tool, with a manual fallback and consequences that are limited and recoverable. Promised behaviour gets evidence, shared or behavioural changes go through a pull request, and named risky areas get an independent review before they go live.

**Build with care.** Some of the work touches a sensitive area: personal data, money, sign-in by outsiders, automatic action on people or other systems, irreplaceable live data, or a regulated decision. The masterplan names each area in your tool's own words, with the one caution that goes with it. The kit builds everything else the ordinary way, and in a named area the caution happens before that part goes live, or you accept skipping it on the record.

Each sensitive area also says where it lives in the tool. A check keeps that
list true: a moved place or a new part with no area stops the check and asks
you where it belongs. When a change reaches one of those places, the review
starts from what the change touched rather than from what the piece expected
to touch. The map exists only on Build with care.

An area can also name one boundary, such as "the ledger is only reached through
the charge step". At founding, and at the quarterly visit for a newly named
area, the agent offers once to have the check hold it. Say yes and put the rule
in your own words, and a change that crosses it turns the tick red with your
sentence beside it. Nothing is added or taken away without your yes, and a
language with no tool for it is told plainly that it has none.

None of these paths is the kit refusing to build. Build with care is where it says plainly what would normally prevent the harm, and you decide. That is the risk notice, in section 8.

## 4. Day one

Type /setup-ai-build-kit. It checks what the current tool can actually do, then tries to talk you out of building if something simpler would do the job. It makes that case once. If you still want the tool, that is your call, and it records the cheaper option and gets on with founding rather than asking again. It interviews you, one question at a time with its best guess attached, and runs the fit check to set the project's build path. From those answers it writes the masterplan, cuts the work into pieces on the plan, and stands the project up with one passing check, saved on your own computer with nothing uploaded. If none of your code is online yet, it stays there until your first build asks you before putting it online. Before it writes anything, it checks which branch your folder is on. If that is not your main branch and nothing there is unsaved, it moves to the main branch and says so in one line, so the setup lands where every later piece starts; tell it if you wanted your own branch. If the branch holds unsaved work it stays put, says why, and the setup reaches the main branch when that branch merges. Where the work carries real exposure, it also has an independent method read the masterplan looking for holes before any of that flagged work goes ahead; for an ordinary internal tool it says it skipped that and why, rather than making you wait for it. Before it stands anything up it checks that every promise on the masterplan has a piece that builds it, and names the ones that do not, so you can add them while the plan is minutes old. Interrupt it anywhere; typing /setup-ai-build-kit again resumes where it stopped.

While it works, the conversation stays on project decisions and results you can
use. Routine searches, setup commands, retries, and waiting stay behind the
scenes unless they create a blocker or need a decision from you.

Before it stands the project up, it names the kind of tool you are building and
shows the recipes that fit, with one recommended. A recipe is one build stack
paired with one place to run it, which the kit knows well enough to check at
launch. For each one it says what the kit can check and what running it
involves, such as the accounts you will hold. If the tool is for work and a
recipe's free plan is for personal use only, it tells you once which plan a
work team needs; a personal project does not hear it. When only one recipe
fits, you still see it the same way, recommended and named the default. You can bring
your own stack instead: it says once what it then cannot check, and records
your choice. If you do not answer, it takes the recommended recipe and carries
on. It then checks this computer for the tools that recipe's launch checks use,
and the completion report says whether any is missing. Where no
recipe fits, such as a command-line tool, it says so in one line and picks a
conventional stack. The choice is written in AGENTS.md, in the stack section,
and the kit notes which recipes were on the menu, so a later check-up can offer
one added since.

The coverage read includes who can see and do what, the data the tool holds,
and its outside connections. It names any gaps together and offers once to add
the missing work. You decide whether it belongs in the plan.

Already built something, in an app builder, a chat assistant, or an earlier attempt? /setup-ai-build-kit adopts it instead of replacing it: it reads what exists, interviews you about what the tool is supposed to do, writes the masterplan for what's actually there, and pins down current behaviour with tests before anything changes. Where it already runs its tests on every pull request, that automation stays its project check: founding records which workflow it is, adds no failing check beside it, and asks before adding the kit's own steps to it.

The masterplan carries a picture of everything outside the tool that it reaches: where it keeps your data, and each outside service. You confirm each one at founding, and the picture is redrawn whenever a piece adds or drops a connection, so a tool never quietly reaches something you did not agree to.

Already sketched, mocked, or written down what you want? Show it during the interview. /setup-ai-build-kit reads it, says back what it sees so you can correct it, records what that settles, and builds toward it. What the mock doesn't cover gets asked rather than guessed, and a mock never carries work past the fit check.

If the tool needs confidential files to work from, say so during the interview. /setup-ai-build-kit makes a folder for them that stays on each machine and never reaches GitHub, and writes the handling rules into AGENTS.md.

## 5. Day to day

Typed alone, /implement takes the next ready piece from the plan. It agrees with you in one sentence what the piece should do, writes the checks that piece needs and shows they fail, builds until they pass, then walks through the tool itself with sample data before saving the piece for you to check. If you would rather try a piece yourself before it is saved, you can ask for that, as the Evidence section says. A piece that is not ready yet, still waiting on a question, goes to /shape first; /implement builds, it does not shape.

Each command moves a piece to its next state and takes the old one off in the same step, so a piece never shows in two columns. /shape moves an idea to shaping, and a shaped piece to ready. /implement claims a ready piece as building before it changes anything, and moves it to to check when its pull request opens. From there the piece is yours to try and merge, and /what-now names it as yours.

A piece that stops at a recorded condition, or fails three attempts, is parked with the reason written on it. If GitHub cannot be reached, /implement says so and does not start a piece it could not claim, and /fix does not start a repair it could not claim either. /sync puts right a piece carrying two states, or a closed issue still carrying one, and tells you what it changed. It never touches an idea you closed as parked.

Before saving, the kit checks what else the change touches and runs the tests
that already cover those parts first. If it reaches another part of the tool,
you get one line naming that part and saying whether its tests passed. The
check is worked out afresh from the current code, so there is no map to keep up
to date. The full project check still runs before a pull request is ready.

It also compares the tool's structure before and after the build. You hear one
line only when the change made later work harder, such as two parts now looping
through each other or a named boundary being crossed. There is no score to
interpret. You can ask for the structure to be fixed before saving, or leave it
and have that choice recorded on the piece.

Before the walk-through, or your own try when you ask for one, the kit takes out
anything the change added that nothing needs, such as a helper only one place
uses or code nothing calls. It only removes things or folds them into the one place that uses them, never
reshapes the code, and runs the tests after every step. Anything that would
need reshaping, such as a function grown hard to follow, is listed on the piece
for you to decide instead.

You hear one line, such as "I took out two things this change did not need.
They are listed on the piece.", or nothing when there was nothing to take out.
The removals are saved as their own step, so asking for one back undoes only
that step. /fix does the same for a repair.

If a build uncovers another piece of work, that new piece says "Found while
building the invoice list", using the title of the piece that surfaced it.
Both pieces link to each other, so you can follow where the work came from.
Parts of the same outcome stay together as parts; a different outcome keeps
its own piece.

When a piece is about the interface, or its files change a screen, the agent
applies the screen rules before your guided check. Your project's `DESIGN.md`,
design system, or component library comes first. The house rules cover forms,
tables, states, actions, words, keyboard use, contrast, and the familiar visual
defaults that coding agents reach for. The report says which rules were applied
and what still needs your eyes. It never claims the screen is accessible,
compliant, or good, and a piece with no screen sees none of this. If the result
is wrong, describe what happened and type /fix.

If the change touched an area the build path flags, the best independent method available reviews it first. It reports in plain language, sorted into what's worth stopping for and what's worth knowing.

/queue shows the plan a run would follow. Type it when you are taking on several pieces rather than one, or when you ask /what-now what else can be worked on and it points you here. It changes nothing and builds nothing, so /implement is still what does the work. If the list looks out of date, type /queue again, since it is printed fresh from your project's issues every time.

The plan comes in five parts. First the order: every ready piece, then each piece waiting only on those, after what it depends on. A piece waiting on another piece is never in it unless that piece is in the plan too, and whatever still waits gets a line saying which piece has to land first: "deposits cannot start until card payments is built". Next the groups. No two pieces in a group change the same area, going by the Touches line each piece carries, so the pieces in one group can be built at the same time in any order. Each still merges one at a time, brought up to date with `main` and checked again first, since two pieces that each pass alone can still fail together. A piece with no Touches line goes alone. A run builds the plan one piece at a time unless you choose otherwise: in Claude Code it asks before it starts.

Then what a run can do with each piece: take it, leave it for you because it sits in a sensitive area you have not accepted or waits on a step only you can do, leave it because its readiness check found a gap, check it first because nobody has yet, or build it and stop for your try. A piece built on top of one the run cannot take waits for it, and says why. Then which pieces build on another. The last line is the command that runs the plan, ready to type. With nothing ready there is no command, only what would make something ready.

/shape is how you bring anything new: "/shape add a filter to the board". You never sort your own request; the agent works out what kind of work it is. Clear and piece-sized becomes a ready piece, and /shape offers to build it now or leave it for /implement later. Vague gets a short interview.

Before a piece turns ready, a session that did not shape it checks it against a fixed list: the cases that are not the normal one, what gets stored, what leaves the tool, the rules it must still meet, and any choice you would notice that is still open. You see one line, such as "A session that did not shape this piece checked it: ready, with two notes for the builder." The result is written on the piece under Readiness. A gap that would change what you see or do, what is stored, or what leaves the tool keeps the piece in shaping, with the gap written on it, and /shape asks you about it. If your coding agent cannot start that second session itself, /shape gives you one line to paste into a new one. Ready says the piece is complete enough to build. It says nothing about safety, so the review and the screen rules still run.

Each piece says what it changes in the masterplan, and the masterplan says when
it was last checked. You see a line such as "When this lands, the masterplan
gains a weekly summary email", or "nothing" when it already covers the result.
A new rule you could check, such as a list now sorted by name, counts as a
change even when the masterplan already describes that list. /implement applies that change as it saves the work, so the page keeps up
without a separate /sync visit.

A question a conversation can't settle gets a disposable prototype, a source check, or a search for something that already does the job. Two of those need you there; the research does not, so you can tell /shape you're leaving and it settles what it can alone, then tells you which pieces are waiting on you. Type /shape with a piece's number to settle that one rather than the next in line.

Typing /shape is the choice to shape, so it starts on a question straight away. Before an interview or a prototype it says in one line that this takes a sitting, and you can say "later" at any point: the piece is filed with its question and your words, to come back to. If all you want is to note an idea, say so, for example "note this for later" or "just file this idea", or type /shape later with it, and it is filed with nothing started, as an idea in your own words. Nothing filed can be built until the question is answered, and /what-now tells you when enough pieces are waiting that the session is better spent planning than building.

Show a mock of what you want and it settles the question instead, with no throwaway built. A prototype comes back as one of two things: a single file you open and click through yourself, or three genuinely different versions to move between and pick from. If setup recorded a design tool, the agent may use its canvas before a real page exists or when you want to draw a redesign. The real page still wins wherever one exists, and without a recorded tool the ordinary coded throwaway stays the default.

Anything touching data, access, or money gets written into the masterplan first. If another piece already open would be built in the same place, /shape names it before the work starts, so you can decide whether to carry on, wait, or fold the two together.

Work on your own computer rather than on the tool, such as installing or repairing a program, is kept apart from the project. Nothing is installed, replaced or removed outside the project's folder until you have said yes to what it is, where it goes and how to undo it, and nothing about your computer is written into the project. You hear what was done in the reply instead.

Using the tool on your own material, such as running a document through it to see what it makes, needs no piece, since nothing about the tool changes. The output goes to a folder the project does not save, and the reply says where. Ask to keep it and it is saved like any other change, with its own changelog entry. If the run shows the tool getting something wrong, that becomes a /fix or a new piece.

If the request would change what kind of project this is, by bringing in outside users or real money or a promise to someone, the agent re-runs the fit check with you before building. A different build path needs different care before people rely on it.

/fix is for when something that should work doesn't: "/fix the board duplicates cards when I drag them". Paste the whole error if there is one. It builds the tightest repeatable check it can find for the exact symptom and works out the cause before touching code, driving the app in a browser or adding temporary logging when it needs to see what is actually going wrong. It resets failed attempts rather than stacking them, and finishes with evidence that keeps the bug from coming back.

Before repairing, it reads the changelog and finished pieces for the same part
of the tool. That keeps a failed repair from being tried as if it were new, and
lets an earlier cause lead the search. Existing covering tests run before a new
one is written. When there is a known time the behaviour worked, /fix searches
the saved changes for where it broke, then removes every temporary log before
the repair is saved.

After launch, /fix also reads the tool's own record of what each request did
alongside your report, so it can trace the failed step. You do not need to read
that record yourself.

If the same piece fails three rounds in a row, it stops patching and routes by what the failures revealed. That may mean another interview, a rebuild from the masterplan, a stop for missing access, or naming the area as sensitive so somebody who does that work for a living looks at it.

## 6. Evidence

Every promised behaviour gets evidence, in one of four forms:

- an automated behaviour check, for business rules, calculations, permissions, data changes, integrations, and bugs, where a machine can judge the result reliably;
- a guided manual check, for copy, layout, colour, and exploratory or subjective work;
- a source-backed fact, when correctness depends on something an external service or provider actually does;
- an operational rehearsal, for backups, restores, migrations, rollback, or anything else that only proves itself by being run.

The agent chooses the form the change actually needs; the report says what was proved and what remains a judgement call.

Every check a machine can run is written first and shown to fail on today's
code, and saved on its own before any code. A check that already passes proves
nothing about the new work, so the agent tells you that done line is wrong
rather than building it. Checks scale with the change: a colour change runs the
checks a colour change needs, and the full check on the pull request runs the
rest.

The agent changes an existing test only when the piece names it and says why. A
small script lists any other test that changed, and any check that changed after
it was first saved, and each one is put back before the piece is saved. A test
in the way, or a done line that cannot be met, is reported to you and never
worked round.

Once the piece is built, the agent walks through the tool itself with sample
data, the way you would, and records what it saw. It keeps every picture it
takes in the main folder's `.agents/tmp/walkthrough/<issue number>/`, which
never reaches GitHub, and never inside a piece's worktree. Founding offers to
plan that sample data, or a test account, when the tool has sign-in or builds up history over weeks. The walk-through stands in
for your try before saving, and a piece on a pull request still waits in to
check until you merge it, or until a pre-approved run merges it, so you can try
it then. When the agent could not see the screen, it says what it could not
check. On a pull request the piece waits for you in to check as usual. On the
checkpoint route, which has no pull request, the agent gives you something to
try and waits for your reply before saving.

The walk-through looks at what you would see. For a web page, it takes a
screenshot with the coding agent's own browser tool, or with Playwright where
the project already has it. For a PDF, a document or an image, it turns each
page into a picture and reads it, up to the first 30 pages of a long file.
Whatever it could not look at, it names, and the piece waits in to check for
you.

Founding writes down what your computer can look with on a `Walk-through eyes:`
line, and the tooling report prints the install command for each tool that is
missing: Poppler for PDFs, LibreOffice for Word and other office files,
ImageMagick for SVG drawings. To give the walk-through more eyes, run that
command yourself, since the kit never installs them.

To try one piece yourself before it is saved, put a `Waiting on you: try it`
line on it. To try every piece, ask for that in any command, and the agent
writes a `check-myself|yes` line in `.ai-build-kit-maintenance`. Ask again to
stop, and it takes the line out. You then get one address, which the agent has
checked answers, and up to three numbered things to try there, and nothing is
saved until you reply. When nobody is there, as in an unattended run, the piece
goes to to check with a pull request saying it waits for your try before it is
merged.

On Build with care, /implement can offer to break the changed code on purpose
to check whether its tests notice. /fix offers the same check for the test
that keeps a repaired fault from returning. It runs locally when the language
has a suitable tool, covers only the changed code, and is optional.

You get one line: "The tests were checked by breaking the code on purpose 40
times. They caught 37. The three they missed are listed on the piece." Misses
in a named sensitive area are worth stopping for; the rest are worth knowing.
You decide whether they matter. The kit records that choice, and only adds a
test to protect promised behaviour, never just to raise the count.

## 7. Saving work

Every piece saves through one of three routes. The checkpoint route commits, and that commit may stay local, so private, disposable exploration can be saved without pushing. The pull-request route pushes and opens a pull request, for shared, live, behavioural, data, access, integration, service, or operational changes. The flagged route does the same, and also attaches the condition the touched area requires; a piece that stops there, marked parked and the condition on record, counts as finished until that condition is met or you carry on after the risk notice and your acceptance is recorded. When you are there and carry on at the notice, the piece is built and saved like any other. Only the `Closes` line closes a piece: a pull request carries one for each piece it finishes, and names any other piece by its number and title with no closing word such as "fixes" before the number, because GitHub closes a piece on that word even in a sentence saying it does not.

On either route, the first time anything pushes your project's code online, the agent asks you first, naming the repository and whether it is public or private. It asks once for each project: once the code is on GitHub, it does not ask again. If you say no, or nobody is there to answer, the piece is still built and checked, and it waits on its own branch on your computer until you say yes. If the repository already holds something that is not your project, or still points at the kit's own repository, nothing is pushed and the agent asks you what to do.

Next to the merge button sits that check. It re-runs the project's real commands on a clean machine, so the pull request's claims get verified rather than trusted. Those commands include the mechanical checks your project's language offers, a type check and a linter wherever it has them, which catch a whole class of mistakes before anyone tries the tool. They use each tool's own default rules, so a red tick points at a real mistake rather than a matter of taste. The agent runs the same checks before it hands any work over. Green means the checks that exist really passed, which is a smaller promise than nothing being wrong: it covers the behaviour somebody thought to check and nothing else. Red means don't merge; say it to /fix, and the agent reads what failed itself. You never read the machine's logs, and you never merge over a red check. The agent waits for the check with one command your coding agent allows, and a check that has not finished, or that it could not read, is never called green.

No command merges a pull request you have not agreed to. The same merge step serves /implement, /fix, /ship and /sync, so the rule holds on every route. The agent names each pull request and what it changes, then asks for a yes that names the merge, and a reply such as "merge 1, 2 and 4" covers each one it names. Saying "put it live" before any merge was named is not that yes, so it asks again. Each merge is made on the pull request itself, never by merging on your computer and pushing `main`, and a pull request stacked on another is merged after it. If GitHub cannot be reached, the merge waits, and you can merge it on GitHub yourself.

A green check only says the pull request passed against the `main` it started from, and two pieces that each pass alone can break `main` together. So just before the merge, the agent brings the pull request up to date with `main`, on every merge whether or not there is anything to fold, and folds the waiting changelog files into CHANGELOG.md, as one more commit on the pull request. It then waits for the project check on GitHub on that commit and merges only when it is green, so each merge takes one more run of the check. When `main` has not moved and nothing waits to fold, there is no new commit and the green check already there stands. Merges happen one at a time, so two pieces built side by side never conflict over the changelog, and nobody has to type a command for the history to stay whole.

If `main` changed the same lines as the piece, nothing merges: the agent names the files, leaves one comment on the pull request saying so, and takes it to /fix. If the check turns red only once `main` is taken in, nothing merges either. The agent tells you the piece passed alone and fails with what merged since, names those pieces, and takes it to /fix.

Before a run, you can say that pieces which pass may be merged. That covers merges that reach a preview: nothing goes live without your yes naming it, or /ship. The agent then merges a piece only when its check is green, its review found nothing worth stopping for, it flags nothing for you to confirm, it touches no sensitive area, you have not asked to try it yourself, and its merge would not go live. Anything else waits for you in to check, and the report says which condition it missed. That permission ends with the run.

At the end, a pre-approved run merges its pieces one at a time, each brought up to date and checked again before the next starts. A piece that conflicts with `main` or turns red there stays in to check with the reason, and the pieces built on it wait too. Each merge waits for one more run of the check, so a long check makes a long sweep, and the report says how long it waited.

The kit's default is that a merge reaches a preview and /ship puts it live. The masterplan's "How it stays running" section records which way your tool goes live. Where your host puts every merge live instead, the ask says "this goes live now", and the first such merge runs /ship's first-launch checks before it happens. A tool with no live address, such as a library people install or a program they run on their own computer, records `not hosted` instead. Its merges are never a launch, and a run may merge them. If the masterplan does not say, the first merge asks which of the three it is, once.

Where your host puts every merge live, Claude Code also shows its own confirmation box before each merge, so no merge goes live without a person seeing it, whatever the session was told. Founding, the merge step and /ship add the box when they record that every merge goes live, and take it out when that changes.

The monthly visit offers it once to a project that recorded the line before the box existed, and a no is kept. A merge made on GitHub's website, or in a session set to skip every confirmation box, does not meet it, so the rule that a person says yes to each merge still holds. Other coding agents have no such box and keep the written rule alone.

After a merge, everyone pulls main. Flagged areas also get the review the build path names before the pull request is offered as ready. A direct push to `main` is forbidden, and in Claude Code the project settings refuse the usual ways of writing one, so every change reaches it through a pull request. Each piece starts from an up-to-date `main`.

The settings also refuse deleting a folder with everything in it, in the common spellings, and the two Git commands that clear the history Git uses to recover lost work. When a command is refused, the agent stops and tells you in one line which command it was and what it was for. It never tries another way round, such as another spelling, another tool or the same work in small steps. The decision is yours, and a command you want run anyway is one the agent gives you to run yourself. On a coding agent with no such settings, the same rule holds in writing.

## 8. Sensitive areas, and the risk notice

Six areas count as sensitive, and the list is fixed: personal or sensitive data, money, sign-in and permissions, automatic action on people or other systems, irreplaceable live data, and regulated decisions. Each carries a default caution, which is what would normally prevent the harm: a person who did not build the tool reviews who can see what; a managed payment or sign-in service so the tool never holds card details or passwords; a person approves each automatic action until a live run has shown it right; a backup restored once and the change rehearsed on a copy; somebody qualified signs off a regulated rule. The build path's section names each area in your tool's own words, its caution, and whether the caution is done. Where the caution is a backup, a copy or a managed service, the kit does it. Where it is a person, the kit tells you so once, in the risk notice below, and the choice of whether to wait for them is yours. It keeps building everywhere else either way.

Before work in a named area goes ahead, you get a risk notice. It comes once, in full, in one reply. It says who is exposed, what happens to them if it goes wrong, what would normally prevent that, what you can do, and that the kit flags what it can recognise and will miss things. It names people rather than saying something is risky, because the exposure a tool creates usually lands on somebody else.

Then it is your call. You can have the caution done first, take the thing out of scope so the risk goes away, or carry on. Carrying on is accepting the risk: say go ahead in any words and the work goes ahead. You are not asked a second time, and nothing the notice named stays switched off waiting for the check you chose to skip. Saying nothing is not carrying on, and neither is asking a question, nor is a form sent back with nothing chosen. Nothing is refused and nothing stops you.

When you carry on, an acceptance is written into the build-path section before the work starts, as a dated line saying what was skipped, with your words quoted exactly as you typed them, or the option you chose, and your name. Any sentence elsewhere that still says the thing is kept out is corrected in the same save, and the agent tells you which ones changed. It says the risk was accepted, never that the caution was done. Making a project less careful is a decision you record, not something the agent does on its own, and the accumulated lines are the honest answer to "what did we knowingly skip?" when somebody asks in six months.

What the agent may not do is take the notice back. Pushing back on the cost, the wait, or the fuss changes what you decide and changes nothing about who is exposed, so the notice stays put however many times it comes up. A named check cannot be quietly turned into something the agent does itself either: where the build path asks for another person's eyes, the agent reading its own work does not count, and neither does a passing test.

## 9. Shipping

/ship reads the build path first, and each path gets only the process it needs, not a shared ceremony trimmed after the fact.

**Explore privately.** /ship runs no production evidence or launch procedure; it only confirms the prototype stays disposable and private, and records what would have to change to graduate.

**Build and run it.** /ship runs the full evidence run, independent review, operational readiness, and the live transition. Off a recipe, readiness is a general list: a backup, a restored-backup rehearsal, a manual fallback, rollback, and a single caution if nobody receives alerts. Anything missing from it is a warning you hear once and find in the changelog, and the launch goes ahead.

**Build with care.** /ship ships everywhere outside a named sensitive area, does the caution it can do itself (a backup restored once, a rehearsal on a copy), and at a caution that is a person who has not looked, gives you the risk notice once. If you carry on, your acceptance is written down and that area goes live too. Where somebody outside the team is going to look, ask for the handover and /ship prepares it.

On a recipe, the recipe's own checks take the place of that list. /ship reads
the recipe your project's AGENTS.md names and works through its eight sections
in order, and each one gives you a plain line: preview up, live address updated,
rollback possible, backup present, restore works, no secret in the repo, logs
readable, health answers. The rollback line says a rollback is possible and
was not tried, because the kit does not roll back the live tool just to check.

The kit runs the checks it can reach. Where a check runs on a server the kit
cannot reach, you paste the result back and the kit reads it. Where only a
person can judge, you look and the kit writes down what you said. A check that
fails or cannot run is a warning, said once and written in the changelog, and
the launch goes ahead. The one thing a first launch waits for is its address,
because a tool with no recorded address is not live.

Before the launch review asks you to look up a setting, the kit reads it itself
where it can: from an address the service answers in public, with the key your
tool already sends to the browser, or through the commands of a tool it is
already signed in to. It asks you only about a setting it cannot read, and says
why it cannot.

The kit never takes a login another tool keeps for itself, such as one stored
in your computer's keychain. That login can reach everything on your account,
not only this tool. Once the kit has told you it cannot read a setting, it does
not then read it some other way. It asks you, and names the page where the
setting lives.

A command that changes a live service's settings or data, other than saving
code through the save route, waits for your yes, in /implement and in /ship
alike. The kit first names everything the command will change, not only the
setting it meant to change, and says whether it can be undone. A real build
once pushed a whole settings file to change one thing, and switched off a live
setting it then could not switch back on. The commands your project's recipe
names are the launch you asked for, and need no second yes.

/ship merges the way every route does, as section 7 describes. Where merges
reach a preview, going live is a promote: /ship names what will go live, runs
its checks, and promotes on your yes. A yes to a merge does not cover it. When
a deploy's result is unclear, /ship checks whether it went live before it tries
again. A second deploy of the same version leaves nothing older to roll back
to, and /ship says so before running one. A warning you have already heard is
not repeated in the same /ship.

On a tool that is not hosted, going live is a release. /ship names each change
since the last release, runs the evidence run and the review, proposes the next
version, such as v1.5.0 after v1.4.2, and makes a GitHub release on your yes
naming it. There is no hosting request, no address and no rollback line. The
changelog then reads "Released" with the version. Anyone who installs straight
from `main` still gets each merge the moment it lands: the release marks when
the kit calls the work live, and it does not hold `main` back.

The records /ship writes during a launch, such as its changelog entries and a
colleague later saying the new version is live, take the same save route as a
piece. On a shared project they go on one branch and one pull request for each
/ship, never straight to `main`, and merging that pull request needs its own
yes. Where your host builds every change to `main`, /ship tells you that
merging it starts one more build and moves the rollback target, and offers to
leave it for the next change. Work of yours that is not saved yet is left where
it is, kept out of the records and never thrown away. The same records pull
request folds any files still waiting in `changes/` into CHANGELOG.md, such as
one from a merge made on GitHub by hand, so the history holds what this launch
carried.

Some checks need a secret, such as a database password kept in a file on your
computer. When you tell the kit where one lives, in any session, it writes down
where, never the secret itself, in the masterplan's "How it stays running"
section. A later /ship reads that line before the backup, restore or database
check. If nothing is recorded, it asks you once. If you cannot say, the warning
says the kit does not know where the secret is kept, and never that it is gone.

On both live paths, /ship checks that the tool keeps a plain record of what each
request did, without personal data, secrets or confidential file contents. If
it does not, you hear once: "The tool keeps no record of what each request did,
so a fault reported after launch cannot be traced. I have noted that in the
changelog, and adding the record is one piece whenever you want it." The
launch does not wait for it. A record that holds personal data, secrets or
confidential contents still gets repaired.

It also tells you once: "Once real people use this, the only record of what
went wrong will be the record the tool writes. If you want somebody to be told
when it breaks, that is a service somebody runs and pays for, and the kit does
not set one up." If the fit check already names who receives alerts, it does
not repeat this caution. Explore privately gets neither check nor caution.

When the tool will run on a server somebody else runs, the first launch needs
an address, and the kit never contacts that server. So /ship writes a hosting
request into the masterplan's "How it stays running" section and prints it for
you. It names the repository and branch, the lane (private network or
internet), the port, the names of the settings the tool needs, the folders that
must survive a restart, and the path that shows the tool is healthy. It also
says how the tool builds and which address it listens on, read from the code,
because the server builds and checks it from those two facts. It holds
names only, never a password or key. You take it to whoever runs the server,
and paste back what they send. On a later launch /ship reads the request back
rather than asking again.

After the first launch, shipping gets lighter: it re-checks what changed since the last ship and moves that over, rechecking the build path first if reliance or consequence has grown. A warning the changelog already holds comes back as one line pointing to it, so anything given in full is new.

## 10. Running a plan: /implement queue

Give /implement several piece numbers, or type "/implement queue" for every ready piece and every piece waiting only on those, and it builds them without you between them. "/implement auto" is the same thing. It says the plan once: each piece in order, whether the run can take it and why not, and which pieces build on another. You approve it once, and say whether pieces that pass may be merged while you are away. A merge that would put the tool live still waits for you. Then it runs.

A run decides piece by piece what it can take. A piece needs to be ready, checked by a session that did not shape it, and complete enough to build with nobody to ask. A piece in a sensitive area is taken only once your acceptance is on the record, and a run never gives one for you. A piece you asked to try yourself is built and then waits for you in to check, whatever you said about merging.

Each piece goes through the same steps as a single build: claimed, checks written first and seen to fail, built, walked through, reviewed. Each piece arrives as its own pull request, and the parts of one piece share one. A piece that needs another built earlier in the run is built on top of it, and its pull request says which to merge first.

In Claude Code, each piece in a run is built in its own copy of the project, a worktree in `.agents/worktrees/` named after the piece, so your own folder stays on its branch and one piece's half-built work never sits under another's. The project's checks, its tests among them, leave those copies out, so a check run from your folder reads each problem once. Other coding agents build a run's pieces one after another in your one folder.

In Claude Code, when the plan has a group of pieces that can go together, the run also asks whether to build a group's pieces at the same time. Each one runs its own install and its own copy of the tool, so this uses more memory, and on a machine with little memory it can crash it. One at a time is the default, and you say a number if you want more. Each piece built alongside others still gets every step of a single build, its own review and its own pull request. The session you started the run in claims each piece, reviews it and opens its pull request, and the pieces merge one at a time, each checked again first. If the session dies, resuming keeps your number and offers to lower it.

Each copy links to your `.env` rather than copying it, and installs its own dependencies. A file your build needs that git ignores and that holds no secret, such as a licensed font, is linked into each copy too, once founding has asked you which ones. Your confidential folder never is. Its dev server runs on a free port the run records, and the hand-over names that port. The server stops once the pull request opens, and the run's report says how to start it again. The kit clears a copy away once its pull request has merged or closed and nothing in it is unsaved, at the next run or the next /sync. A copy holding unsaved work is kept and named.

If the run meets a choice nobody made, a hard one, about stored data, syncing or what leaves the tool, sends that piece back to shaping with the question on it. A hard choice the run can already see in a piece sends it back the same way before any branch is cut, and the plan names it as going back, so it does not come back to every run. An easy one takes the option simplest to undo and is flagged in the pull request. A piece that fails three attempts is parked with a note on what it revealed. Either way the run moves on.

The run keeps a state file in your project, which git ignores, and a live progress page where your coding agent can publish one. If a session dies, a new session picks the run up from its state file, and /what-now and /sync both offer to resume it.

When nothing is left that the run can take, it stops at once with one report: each piece, its pull request and where it stands, the choices flagged for you, what was parked and why, and the order to merge in. You answer with the pull requests to merge. If the run disappointed you, improve the documents rather than the code. Sharpen the done lines, add the missing rule to the masterplan, and run it again.

Some harnesses provide goal or long-run modes, such as Claude Code's `/goal`: "keep going until this condition holds". Same run, same rules: take the condition from a done line, a named sensitive area stops the piece that touches it, never the run, and each piece still lands through the save route the build path requires.

## 11. Team use

GitHub collaborators identify who has access. Invite someone under the repository's Settings, then Collaborators. They accept the email, open the repo in their own tool, and make their own .env from .env.example.

Nothing else changes when a second person arrives: naming a piece before starting it already stops two people building the same thing. Each of you gets your own printed list, so there is no shared file to clash over. Open pull requests show work in progress, and /what-now identifies conflicts and unfinished work rather than leaving you to read Git state yourself.

The agent posts under your account, so a colleague reads its comments as you. Nothing goes to a colleague in your name until you have seen the words and said yes, and an issue a colleague opened keeps its title and scope unless you agree to the change. Labels and the kit's own bookkeeping notes go on without asking.

## 12. Sync and maintenance

Normal /implement and /fix completion updates the records directly; you don't need /sync after a piece that finished cleanly. /sync exists for interrupted work, work done outside the workflow, long sessions whose context went foggy, and handovers. A report-only reminder can optionally run at session end, where the tool supports it, but nothing writes to the records without a skill deciding to. /sync also re-reads the masterplan against your pieces, and says if a promise has lost the piece that builds it. /sync reads the newest check on `main` first: if it is red, perhaps because a pull request was merged on GitHub by hand without the re-check, it says so before anything else, names what merged since it was last green, and points you to /fix. Its corrections are saved the way a piece is saved, through the route your build path requires, so on a shared project they arrive as a pull request you decide to merge, and uncommitted work it finds on arrival is reported and left alone. It also folds any files still waiting in `changes/` into CHANGELOG.md, the way /ship does when it launches. Each merge folds its own piece's file, so these are the ones a merge made on GitHub by hand left behind, and only files already on `main` are folded.

/sync also picks up changes a finished piece was meant to make to the
masterplan but never did. It checks what actually landed, applies what is still
missing and records where it checked up to. The monthly visit uses that point
to say how much work has since touched the tool's data, permissions or
connections. When there is any, it gives the count and offers /sync in one
line. That is a reason to check the page, not a claim that it is wrong.

The coverage read includes permissions, data and outside connections here too.
It also compares settled terms on every piece with the masterplan, even if a
piece was parked or reshaped. A missing or different meaning joins the same
list of gaps, with one offer to put the records right. Planning leaves the
term on its piece until it is carried across, so parking the work cannot lose
what you agreed.

When the core masterplan grows beyond roughly two pages, /sync says so once
and offers to move detail about individual pieces onto those pieces. It leaves
the page alone without your yes, and keeps the tool's present promises and
decisions on the masterplan.

/sync also reads the project's README, and any document AGENTS.md points at,
against the project itself. It names a file, link, command or setting a
document mentions that no longer exists, at the line it sits on, and offers to
correct just that name or to file it for later. A document that says less than
the project does is fine. It checks names only, so it cannot tell you whether a
described step still happens that way, and it says so. When every name still
points at something real, you hear nothing about it.

/sync names open pieces untouched for 30 days in one short list and asks once
whether each is still wanted, should be parked, or is done. It changes nothing
on that list without your yes. You can leave them as they are and carry on.

/maintain is the service visit: monthly and light for AI Build Kit updates,
project dependency updates, and anything the error alerts caught. Every visit
names two numbers, the version your project holds and the latest published AI
Build Kit, and says plainly when they differ. An update gives you that
published release and never work nobody has released yet. When a newer
kit is available, the agent shows the version and what changed, then waits for
approval. An update refreshes only the fourteen AI Build Kit skills and leaves
your tool, its records, and its own checks alone. It also adds any skill the
kit has renamed or added since, and says if the installation is short of the
fourteen. When the kit has renamed a command, the update also rewrites the
command list in your AGENTS.md, with your approval, so you are not left to
edit it by hand. A project founded from a whole copy of the kit also carries
the kit's own command files, which make each command show twice; the visit
offers to remove those and leaves anything you wrote yourself alone. It
removes a saved folder in a way the project's history can undo, and gives you
the command for a folder that was never saved. Every
visit also checks the small helper that prints your list of pieces to
`plan.local.md`. A project founded before every installation carried it gets it
then, so the kit reads what is ready from that list rather than working it out
by hand. A clean checkpoint comes first, so an interrupted update can
be recovered. The one update that split the
old `/build` into what are now `/shape` and `/implement` runs a one-time step that labels your
existing pieces so they can still be built; it says what it changed. Any
visit that finds an older `plan.md` list offers to move it into your project's
issues, and keeps offering until it is moved. Any visit that finds a line in
AGENTS.md or the masterplan pointing at a skill's file by a folder your
installation may not have offers to name the skill instead, changing only
those lines, and only on your yes. The first
visit after the kit changed how it decides the build path offers to rewrite
the build-path section of your masterplan to the new shape, shows the old text
above the new, keeps every accepted risk word for word, and changes nothing
without your approval.

Your project records which AI Build Kit release it holds, and the commit that
release was cut from, in a small file founding writes and every update
rewrites. So you can always say exactly which kit you have. You do not have to
wait for the monthly visit to hear about a new one either: when a newer release
is out, /what-now says so in one line, names both versions and points you to
/maintain. Update the kit only through /maintain. The installer's own
`npx skills update` can drop a renamed skill without a word and leave the kit
half updated, so the agent will not run it for you.

The standing instructions in AGENTS.md stay under 200 lines and hold what the
code cannot show, such as how work is saved and reviewed and which conventions
differ from the default. /maintain counts the lines every month and offers a
trim if the file reaches 200, or contains a folder layout, dependency list,
architecture overview or style rule an automatic check could enforce. You see
one line saying how long it is and what can go. Nothing is cut without your yes.
A newly founded project starts well under the limit, with room left for what
founding writes into the file. Between visits, the project check goes red when
AGENTS.md passes 200 lines, and names both numbers.

A project founded before AGENTS.md became an index has a longer file, and a
check that does not count it. The monthly visit offers once to move it onto the
index: each lasting fact goes to its one home, dates and issue numbers leave
the file, and the check gains the step that counts it. Nothing moves without
your yes, and a no is not asked again.

A project founded before that record, where the kit's placeholder check sits
red beside CI of the project's own, is offered once to record its own as the
check and remove the placeholder. Nothing changes without your yes, and a no is
asked again only when the project's workflows change.

A project with no recipe may still be built much like one on the menu, with
the same framework and the same data service, even if it runs somewhere else or
lacks the recipe's Dockerfile and health route. That covers a project founded
before recipes existed and one founded on its own stack. The monthly visit then
offers the move once, and says what it gains: the launch checks /ship would run
on that recipe. It also says what the move would change. Nothing changes without
your yes. A yes becomes a piece, shaped and built like any other, and the
offer does not come back while that piece is open. A no is recorded, and the
offer comes back only when the menu or your stack has changed since. The move
is never required. When no recipe is close, you hear nothing.

If you chose your own stack, founding noted which recipes were on the menu. A
close recipe that joined the menu after you founded the project is offered
once, even if your stack has not changed. A project founded before that note
existed treats every close recipe as new, once.

/maintain also lists old branches whose work is already in your main branch,
on your computer and on GitHub, each with the command that removes it. It
keeps two kinds apart: the ones Git can confirm, and the ones only GitHub
records as merged. The second kind comes from a pull request that combined its
changes into one, which Git cannot check. It never removes a branch itself,
and it cannot tell whether somebody still plans to use one. When there are
none, you hear nothing.

/maintain also lists any worktree a run left behind whose pull request has
closed, such as one from a session that died before it could clear up. It
removes each one you say yes to, never by force, and keeps one that holds
unsaved work, saying what is unsaved. Removing a worktree leaves its branch,
which the list of old branches picks up at the next visit.

If you use another tool that makes worktrees of its own, the kit never touches a worktree another tool made. A run started inside one keeps its record and its copies in your main project folder, and says so.

A project founded before the kit could link ignored build files gets one question: which ignored files a build needs. A no is recorded, and the question comes back only when a new ignored file appears.

A project founded before the six states gets one offer to move onto them. Pieces waiting on a question gain shaping, open pieces with no state gain idea, and a piece labelled blocked becomes parked with its reason. Ideas you closed as parked stay as they are. Nothing changes without your yes, and a no is recorded, so the offer comes back only when a release changes the states again.

In Claude Code, the settings founding gave your project refuse a direct push
to `main`, a recursive delete and clearing Git's recovery history. When a
later release catches more of these, the
monthly visit names the new rules and offers to add them to
`.claude/settings.json`, once. It adds nothing without your yes and leaves the
rest of the file as it is. A no is recorded, and the offer comes back only
when a release adds another rule.

/maintain writes the date of each visit into the project. When more than a month
has gone by, or once 20 changes have landed since the last visit, whichever comes
first, opening a session says so and names /maintain. A busy project can do a
month's work in a week, and its records drift just as far. The count is of the
changes saved to your main branch, and it counts only what this computer already
holds, so merges made on GitHub since you last pulled show up late.

A tool that cannot run anything when a session opens says it when you type
/what-now instead, and /what-now asks the same script, so the two agree.
Nothing is blocked and nothing changes without a command. If you ask a visit to
leave kit updates alone, it does not add that reminder either, and says so. A
project whose reminder script came before the change count is offered the newer
one at the monthly visit, and a no keeps the old one until the next visit asks
again.

The quarterly visit is fuller, with a hot-spot tidy-up and an ownership check
that can name a new sensitive area or, after a genuine redesign, take one off.
Its hot-spot read counts how widely the quarter's saved changes spread instead
of guessing from memory. Unless the project is a private exploration, it also
looks for code copied from one place to another, code nothing uses any more,
and dependencies nothing needs, using tools that read the project rather than
the agent's impression of it. Each finding names the file and line, and it
joins the same short list of at most three proposals. It finds copied code; it
does not find two pieces of code that do the same job written differently. When
it finds nothing, you hear nothing about it. It also compares the project's
structure with the last full visit and names any new place where two parts
have started to depend on each other in a circle. The earlier structure is read
again from the saved history each time rather than kept anywhere, so it cannot
go out of date. Most quarters nothing got worse, and you hear nothing. It also reads all
of the project's documents for bloat: a paragraph written out in full in two
places, and a document nothing mentions any more. Each one comes as an offer, to keep one copy
or to delete the page, and nothing changes without your yes. It finds copies,
not two documents that say the same thing in different words. /maintain also owns the ending,
when a tool's time is over: export the data, tell the team, revoke access, and
switch off the services.

## What stays yours

Three things no skill ever takes: saying clearly what you want going in (a real example, the output you expect, what done means), deciding what merges and what goes live, and accepting a risk after its notice.

Trying every piece is not on that list. The agent's walk-through checks each piece before it is saved, and records what it saw. When it could not see the screen, it says so and gives you something to try. Trying a piece yourself is always open to you: put a `Waiting on you: try it` line on one piece, or ask to check every piece. The system automates the routine and never the judgement.
