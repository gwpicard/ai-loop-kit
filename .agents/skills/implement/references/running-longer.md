# Running a plan

Loaded when `/implement` is given several issue numbers, or `queue`, which is
the command for a plan of ready pieces built with nobody watching. `auto` is
another name for `queue`. The discipline of a single build is unchanged: each
piece goes through section-builder, step by step. What changes is that nobody
is present between the pieces, so the rules below carry the quality, the state
file carries the memory, and everything gets a cap.

## Capability rule

One piece at a time is the default on every coding agent, and nothing is
assumed beyond ordinary agent work, such as a native goal mode. On Claude Code
the person may choose more: a run there can build the pieces of one group at
the same time, each built by its own background agent, as "Building a group at
the same time" below says.

On Claude Code, each piece in a run is built in its own worktree, a second
working copy of the project on the piece's branch, as "Each piece in its own
worktree" below says. The main folder, the project folder the run started in,
stays on the branch it was on: a run never switches the main folder to a
piece's branch. On any other coding agent, or where Git is older than 2.17,
the first with `git worktree remove`, a run works in one checkout, one piece after another, in the
way a person would run them by hand.

Where the coding agent can start a session that did not build the piece, use
it for the readiness check and the independent review, as those steps already
say.

## Which pieces a run may take

Eligibility is decided piece by piece, never earned by the project. A piece is
eligible when all of these hold:

- it carries `state:ready`, and nothing open holds it up that is not built
  earlier in this run;
- it meets the bar: a `## Done when` section, and a `## Readiness` section whose
  first line says Ready;
- it is self-sufficient enough to build without a person present: its `Under
  the hood` notes carry what the build needs;
- it has no `## Waiting on you` step other than `try it`;
- it lies outside every sensitive area named in the build-path section, unless
  that area carries an `Accepted:` line covering it.

A piece in a sensitive area without a recorded acceptance is never taken. A run
never writes an acceptance on the person's behalf, because nobody is there to
carry on after the risk notice. On Explore privately, a run takes only
disposable work whose Done when lines a machine can check.

A ready piece with no `## Readiness` section was shaped before the check
existed. Run the readiness check on it before claiming it, as
the `shape` skill's `references/readiness-check.md` says, through a session
that did not shape it. Ready lets the run take it. Not ready sends it back to shaping with
each blocking gap written on it, through the gate to the sub-state the check's
first BLOCKING line needs, such as
`python3 .agents/tools/gate.py move <number> research`, and the run moves on.

A piece the person opted in to check, with a `Waiting on you: try it` line or a
`check-myself|yes` line in `.ai-build-kit-maintenance`, is taken and built. It
stops at `to check` with a line in its pull request saying it waits for the
person's try, and it is never merged under pre-approval.

A hard open choice in a piece is not a reason to skip it. A hard choice is
about the shape of stored data, how records sync, or what leaves the tool, and
it is open when the piece's `## Done when` and `## Decided` lines leave it
open. Where the run can see one when it plans or claims a piece, send it back
to shaping before claiming it, once the person has approved the plan. Write
the question on the piece under `## Open question`, then move it
with no claim to undo: `python3 .agents/tools/gate.py move <number> clarify`.
Cut no branch and write no claim, since nothing was built. Mark it `shaping`
in the state file, and the plan names it as going back, with its question. Left
`state:ready` and skipped, it would come back to every run, and nothing on it would
tell the person a question was waiting.

An easy open choice seen at the plan leaves the piece eligible. It is built,
and the builder picks the option easiest to undo and flags it, as "An open
choice met while building" below says.

The self-sufficiency test keeps its other job. A piece whose `Under the hood`
notes lack what the build needs, with no open choice in it, is skipped with the
reason and stays in `state:ready`. Where a piece has both a hard open choice and a
missing fact, the hard choice wins, and it goes back to shaping.

Apart from a hard open choice, a piece that is not eligible stays where it is.
The report says why.

## Before the run starts

Check that Git is clean, as section-builder's step 1 does. On Claude Code,
clear away the worktrees whose pull requests have closed, as "Clearing a
worktree away" below says. Refresh the printout. The plan is the pieces the
person named, or with `queue` every piece under `To build` marked `(ready)`. Either way, the plan also takes each piece
under `Held up` whose open blockers are all in the same plan, and orders it
after them, so it stacks on them rather than waiting for a later run. Order the
plan by the blocked-by links, so a piece comes after every piece it depends on,
and by number where the links leave a choice. The parts of one parent sit
together in that order.

Say the plan once: each piece in order, whether it is eligible and why not
where it is not, each piece going back to shaping with its question, and which
pieces will stack on another. Say that the live page
below publishes the pieces' titles and progress to the coding agent's page
service, and offer to run without it. Then ask once whether pieces that pass
may be merged during the run, as the `section-builder` skill's
`references/merge.md` describes.

On Claude Code, where the plan holds a `Go together` group of two or more pieces
the run can take, ask one more question in the same reply as the merge question,
in these words: "Build the pieces in a group at the same time? Each one runs its
own install and its own copy of the tool, so this uses more memory, and on a
machine with little memory it can crash it. One at a time is the default. Say
how many at once if you want more than one." On any other coding agent, where
Git is older than 2.17, or where the plan holds no such group, do not ask: the
run builds one piece at a time.

The answer is a number from 1 up to the size of the largest group in the plan.
No answer, or silence, means one at a time. A larger number is taken as that
size, and the reply says so: "The largest group has three pieces, so three at
once." Zero, or words that are not a number, mean one at a time, said in one
line. Record the answer as `at_once`.

The person approves the plan and answers those questions, and then the run
goes on with nobody in between.

## The run state

A run keeps its state in `.agents/runs/<run name>/`, where the run name is the
date and time it started, `<YYYY-MM-DD>-<HHMMSS>`. That is always the main
folder's `.agents/runs/`, the first worktree git lists, even when the session
sits in another tool's worktree, so every session finds the same run. Git ignores the folder.
Where the project's `.gitignore` has no `.agents/runs/` line, write a
`.gitignore` holding `*` inside `.agents/runs/` before anything else, so the
folder ignores itself and nothing tracked changes.

`state.json` is the record a new session resumes from:

```json
{
  "run": "2026-09-30-221500",
  "merge_preapproved": false,
  "at_once": 1,
  "pieces": [
    {
      "number": 12,
      "state": "to check",
      "branch": "12-invoice-list",
      "base": "main",
      "worktree": ".agents/worktrees/12-invoice-list",
      "port": 4012,
      "pull_request": 31,
      "attempts": 1,
      "flags": ["Sorted the list newest first; the piece did not say."],
      "reason": ""
    }
  ]
}
```

- `merge_preapproved` is the person's answer before the run: `true` or
  `false`. It holds for this run alone, and carries into the run when it is
  resumed.
- `at_once` is how many pieces of one group are built at the same time: 1, the
  default, up to the size of the largest group in the plan. Like
  `merge_preapproved`, it holds for this run alone and is kept when the run is
  resumed.
- `pieces` lists every piece in the plan, in the order the run takes them.
- `state` is one of `waiting` (not started), `building`, `to check`, `merged`, `shaping` (sent back with a question, or kicked back after three failed attempts or at a caution) or `skipped` (not eligible,
  backed off, given back, or not reached before the run ended). The last four
  are final. A piece kicked back after three failed attempts or at a caution is recorded as `shaping`.
- `branch` is the piece's branch, and `base` is the branch it was cut from:
  `main`, or the branch of the piece it stacks on.
- `worktree` is the piece's worktree folder, relative to the main folder, or
  `null` where the piece has none.
- `port` is the port the piece's dev server listens on, or `null` where no
  dev server was started for it.
- `pull_request` is the number of its pull request, or `null` before one opens.
- `attempts` counts the failed attempts at its build.
- `flags` holds each easy-to-undo choice the builder made alone, one line each.
- `reason` says why a piece was kicked back, sent back, skipped, waits, or was not
  merged under pre-approval, naming the condition it failed in
  the `section-builder` skill's `references/merge.md`, such as a merge that
  would go live.

`run.json`, beside it, holds each piece's `status`, written only by the gate script
when a move names the run with `--run <run name>`. Every gate call in a run
names the run. The gate writes the labels and `run.json` in one call, so the two agree,
and a label write that fails leaves `run.json` as it was.

Write the state file after every step that changes a piece, before the next
step starts, so it always says where the run stands. `progress.md`, beside it,
is a short log: one line for each step, with the time, the piece and what
happened. Neither file ever holds a key, a password or a person's data.

Unless the person chose to run without it, and wherever the coding agent can
publish a page, publish a live progress page from the state file when the run
starts, and update it each time the state file changes. It shows each piece's
title, state and pull request link, and nothing else. Where the page cannot be
published, say so once, and carry on with the state file as the record.

## Each piece in its own worktree

This section applies on Claude Code. The kit owns each worktree from the moment
it opens to the moment it is cleared away, so the person never tracks which
copy holds which piece. Run the `implement` skill's `scripts/worktree.sh` from
the main folder, as `sh <installed implement skill>/scripts/worktree.sh`, for
each step it names.

- **Where it lives.** A piece's worktree is
  `.agents/worktrees/<issue number>-<short name>`, on the piece's branch.
  `worktree.sh open <name> <branch> <base>` makes it. Where the project's
  `.gitignore` has no `.agents/worktrees/` line, it first writes a
  `.gitignore` holding `*` inside `.agents/worktrees/`, so git ignores the
  folder and nothing tracked changes. A harness's own worktree folder, such as
  `.claude/worktrees/`, is left alone.
- **Its base.** Bring `main` up to date with `git fetch origin` and cut from
  `origin/main`, or from the branch of the piece it stacks on. Where `origin`
  cannot be reached, cut from the local `main`. Nothing here checks out a
  branch in the main folder.
- **The parts of one parent** share the parent's worktree, since one branch can
  be checked out in only one place.
- **The checkpoint route** gets no worktree. Its commit goes on `main` in the
  main folder, as section-builder's checkpoint route says, so the main folder
  must be on `main`. Where it is on another branch, the piece stops with that
  reason, since a run never switches the main folder.
- **The `.env`.** The worktree's `.env` is a link to the main folder's `.env`
  rather than a copy, so each secret stays in one file. Each other file at the
  top of the main folder whose name starts with `.env.` and that git ignores,
  such as `.env.local`, is linked the same way. With no `.env` in the main
  folder, nothing is linked, and a `.env` found only in a subfolder is named
  rather than linked. Where the link cannot be made on this system, the piece
  runs without secrets: say so once, and flag each part of it that needs a
  key. Never copy the file instead. Where a copy already sits in the
  worktree, the script names it and leaves it, and the piece is flagged.
- **Ignored build files.** A build can need a file git ignores that holds no
  secret, such as a licensed font or a large sample input. The
  `worktree-links` line in `.ai-build-kit-maintenance` lists them, each path
  relative to the project root, a file or a folder. `open` links each one the
  way it links `.env`: a relative symbolic link, never a copy, making the
  link's folder in the worktree first where it is missing. A listed folder is
  made as a real folder and each thing in it is linked, because git does not
  ignore a link named after an ignored folder. The script refuses a path, and
  names the reason, when it sits in or holds a folder on a `confidential`
  line, is named `.env` or starts with `.env.`, is tracked by git, lies outside
  the project, or is not in the main folder. It refuses one git does not
  ignore too, since the link would be a new file to save.
- **When a listed file does not arrive.** With no `worktree-links` line, only
  the `.env` files are linked. Where a listed path is missing or its link
  cannot be made, the piece goes on: say so once and flag the piece "built
  without <path>". Where a copy already sits at a listed path, the script
  names it and leaves it, and the piece is flagged. A link is never unsaved
  work, and removing the worktree leaves the main folder's file in place.
- **Its dependencies.** Before the start ritual, install them inside the
  worktree with the install command AGENTS.md's stack section records. Where
  it records none, use the install step of the project check, in the job
  the capability profile's `Project check:` line records
  (`.github/workflows/checks.yml`, job `project-check`, where that line names
  no file). Where neither has one, there is nothing to install.
- **Its port.** A dev server started for the piece listens on a free port.
  `worktree.sh port <issue number>` prints one nothing else is listening on.
  Record it as `port` in the run state, start the server on it, and name that
  address in the walk-through and the hand-over. The server keeps running
  until the hand-over is given, and stops when the piece's pull request opens.
- **A path already there.** Where the worktree's path exists from an earlier
  run, `open` reuses it only when it is on the same branch and holds no
  unsaved work. Otherwise it names the path and the reason, and the run skips
  that piece with that reason.
- **A full disk.** Where making a worktree or installing into it fails because
  the disk is full, the run stops at the next piece: it starts no other piece,
  leaves the piece in hand as "When the run ends" says, and gives the reason
  in the report.
- **The run state stays in the main folder.** A run writes `state.json` and
  `progress.md` to the main folder's `.agents/runs/`, never inside a worktree,
  so a new session opened in the project resumes from them.

A worktree holds no unsaved work when it has no uncommitted change, counting a
new file git does not ignore, and no commit that only this computer holds. A
file git ignores counts as unsaved too when it is a real file rather than a
link and sits outside a dependency or build folder, such as `node_modules`,
`.next`, `dist` or `build`, since a note or a copied key can live there.
`worktree.sh unsaved <path>` says which, if any.

### Clearing a worktree away

When a piece's pull request has merged or closed, its worktree is removed at
the next run's start or the next `/sync`, by `worktree.sh tidy`. It removes a
worktree only when it holds no unsaved work. A worktree holding unsaved work is
kept, and named with what is unsaved. It never touches a worktree an unfinished
run is still building, and it says nothing about one whose pull request is
still open.

Removal uses `git worktree remove` without force. It takes away the
worktree's link to `.env` and leaves the main `.env` alone. It deletes no
branch: the monthly list of old branches offers that once the work is in
`main`. Any
worktree left over, such as one whose session died, is listed by `/maintain`,
which removes each on a yes.

A single `/implement` outside a run works in the main folder, as always, unless
the person asks for a worktree. Then it opens one for the piece in the same
way, and the same rules clear it away.

### Beside another tool's worktrees

The kit opens, tidies, lists and removes only the worktrees under the main
folder's `.agents/worktrees/`. It never touches a worktree another tool made,
such as a multi-agent coding environment's, wherever that sits. The main folder
is always the first worktree git lists. A run started inside another tool's
worktree keeps its run state in the main folder's `.agents/runs/` and its
pieces' worktrees under the main folder's `.agents/worktrees/`, and `open`
says so in one line when it starts. Each piece is cut from `origin/main`, and
the run never checks `main` out, so it works where the other tool's worktree
has `main` checked out.

## For each piece

Take the pieces in the plan's order. Where `at_once` is above 1, the steps
below are shared out as "Building a group at the same time" says. Every move a
piece makes goes through the gate, with `--run <run name>`. Where the gate refuses a move, tell the person its line in plain words and stop that move:
with nobody watching, the report says it, and the run takes the next piece.
Never write the label another way, as the `setup-ai-build-kit` skill's
`references/blocked-commands.md` says. For each one:

1. **Claim it.** Read the piece first. A piece that already carries `state:building` is being built somewhere else: the gate refuses the claim,
   so skip it. A piece
   whose text shows a hard open choice goes back to shaping unclaimed, as
   "Which pieces a run may take" says, and the run takes the next. Otherwise
   make the claim through the gate, `python3 .agents/tools/gate.py move <number> building --run <run name> --assignee @me`,
   and add a comment naming this run,
   `Claimed by run <run name>`. Then read the claim back with
   `gh issue view <number> --json labels,assignees,comments`. The earliest
   `Claimed by run` comment on the piece wins. Where it names another run, this
   run is the later claimant, so back off that piece: delete this run's own
   comment, take this run's assignee off with
   `gh issue edit <number> --remove-assignee @me` only where the winning run
   uses a different login, leave the label, which is now the winner's, mark
   the piece `skipped` with the reason, and take the next piece. Only the later
   claimant backs off, so a piece is never left `building` with no run behind
   it. A piece that cannot be claimed is never started.
2. **Branch it.** Cut its branch from the up-to-date `main`, or from the
   branch of the piece it stacks on. On Claude Code, open the branch in the
   piece's own worktree and install its dependencies there, as the next
   section says. Record `branch`, `base` and `worktree`.
3. **Run the start ritual.** Read the run state, start the tool, and run a smoke
   check: the tool starts and its first screen or command answers. On Claude
   Code, do this inside the piece's worktree, with a dev server on the piece's
   own port. Then confirm each of the piece's Relies on lines still holds, by
   reading what it names.
4. **Write the checks first**, as section-builder's step 4 says, and show that
   they fail.
5. **Build it**, as section-builder's step 5 says, and verify it with the
   checks the change needs.
6. **Walk through it** with sample data, as section-builder's step 6 says.
7. **Run the independent review**, as section-builder's step 7 says. Where the
   trigger names a person, the review is theirs, and the pull request says it
   is still owed.
8. **Open its pull request**, as section-builder's step 8 says, aimed at the
   piece's `base`. Look first for a pull request already open from its branch,
   `gh pr list --head <branch>`, and use that one, so a resumed run never opens
   a second. Put every flagged choice in it under `## Flagged for
   confirmation`, one line each.
9. **Write its changelog file**, as section-builder's step 9 says.
10. **Move it to `to check`.** Step 8 moved it to `state:in-review` through
    the gate when its pull request opened, so record `to check` in the state
    file. Where `merge_preapproved` is true, merge it only
    when the `section-builder` skill's `references/merge.md` allows; otherwise
    it waits for the person.
11. **Update the run state** and the live page, and add the step to
    `progress.md`.

On Explore privately, a piece on the checkpoint route has no pull request.
Steps 8 to 10 become the checkpoint commit and closing the piece, as
section-builder's step 8 says for that route:
`gh issue close <number> --reason completed` followed by `python3 .agents/tools/gate.py tidy`.
Its state is `merged`.

A Relies on line that no longer holds is an open choice of the hard kind below.
A smoke check that fails on `main` ends the run, because every later piece
relies on it. One that fails on a stacked branch skips only the pieces on that
stack not yet built, with the reason. A base already built stays in `to check`.

## Building a group at the same time

This section applies on Claude Code, and only where `at_once` is above 1. The
session that started the run coordinates. A background agent builds each piece:
an agent the coding agent starts to run in the background, told the folder it
works in.

- **Which pieces run together.** Only pieces in the same `Go together` group
  run at the same time, and never more than `at_once` background agents at
  once. A piece that stacks on another is never in its base's group, so it is
  built after its base, never alongside it. A piece in no group is built on its
  own. The groups are taken in the plan's order, and the next one starts once
  no piece of the one before is still with a background agent.
- **Before an agent starts.** For each piece, the coordinating session makes
  the claim itself, one piece at a time, as step 1 says. It then opens the
  piece's worktree with `worktree.sh open` and takes its port with
  `worktree.sh port`, before it starts that piece's background agent, and
  records both.
- **What an agent does.** It is given the piece's number, its worktree path,
  its port and the run name. It loads section-builder and does steps 3 to 6 of
  "For each piece" inside its worktree: the start ritual, the checks first, the
  build and the walk-through. It commits its work on the piece's branch and
  reports back what it built, the commit that holds the checks, the choices it
  flagged and what the walk-through could not see. It never pushes, since a
  first upload waits for the person and the checkpoint route stays on this
  computer. It never reviews any piece, opens a pull request, writes the run
  state or merges.
- **After an agent reports.** The coordinating session starts that piece's
  independent review itself, as step 7 says, since the review runs from a
  session that did not build the piece. It then opens the pull request and
  writes the changelog file, as steps 8 and 9 say, one piece at a time. Step 8
  is where the branch is first pushed. A problem the review finds is fixed by
  the coordinating session in the piece's worktree before that. Where
  the trigger names a person, the review stays theirs: a background agent never
  meets a named review.
- **One writer.** The coordinating session is the only writer of `state.json`,
  `progress.md` and the live page, so two agents never write the run state at
  once, and the gate script is the only writer of each piece's `status` in `run.json`. It moves each piece to `to check`, and only it merges, one pull request
  at a time, through the `section-builder` skill's `references/merge.md`, each
  brought up to date with `main` and checked again first. Where two pieces
  finish while a merge is under way, it merges them one after the other, each
  checked again.
- **An agent that never reports.** A background agent that ends without
  reporting back counts as a failed attempt at its piece, under the
  three-attempt rule in "When a piece fails", and the run goes on. A smoke
  check that fails on `main` ends the run as it does for one piece: start no
  new agent, wait for the ones still building to report, and leave each piece
  as "When the run ends" says.
- **Two pieces that change one file.** Two pieces of one group can change the
  same file although their `Touches:` lines differ. The second merge's check
  against the latest `main` then finds the conflict, and the
  `section-builder` skill's `references/merge.md` takes it to `/fix`.
- **The browser.** Where a walk-through cannot get the browser because another
  agent holds it, it records that it could not look, and the piece goes to
  `to check` for the person, as section-builder's step 6 says for a
  walk-through that could not see.

## Stacks and parts

A piece that depends on one built earlier in this run and not yet merged stacks
on it. Its branch is cut from that piece's branch, its pull request aims at
that branch, and the pull request says which to merge first, so the stack
merges cleanly in order. It names the base by its number and title with no
closing word before the number, as in "Merge #<number>, the date filter, first;
this builds on it", since a closing word there would close the base, as the
`section-builder` skill's save step says. When the base merges by squash, the stacked branch
takes in `main` at its own merge, as the `section-builder` skill's
`references/merge.md` describes, never by a rebase, since that needs a force
push. The same step re-aims its pull request, and the base's entry is not
written twice. A piece whose blocker is open and not in this run is not eligible. A
stacked piece whose base goes back to shaping is skipped with
that reason.

The parts of one parent share one branch and one pull request. The first part
built cuts the branch, named after the parent, and each later part continues
on it. The pull request opens after the last part that finishes its build,
once no later part of that parent is left to build in the run. A part that
finished earlier waits in `building` with the reason `waiting for the parent's
pull request`. The pull request closes each part it carries with its own
`Closes #<number>` line, and each part's changelog file is written once it
opens. Where no part finishes, nothing opens. Where the run ends before the pull request can open, the finished parts stay on the pushed branch and go back to `state:ready` through the gate,
as "When the run ends" says, and the report names them as built but in no pull
request.

## An open choice met while building

A piece can meet a choice its Done when and `Decided` lines do not settle. Split
it by how hard it is to undo. A hard choice the run could already see in the
piece goes back before the claim, as "Which pieces a run may take" says. This
section is for one the build uncovers.

A hard choice, about the shape of stored data, how records sync, or what leaves
the tool, stops that piece. Write the question on the piece under a `## Kickback` section, push the branch and keep it, and send it back to shaping, `python3 .agents/tools/gate.py move <number> clarify --run <run name>`.
Then take the run's assignee off, `gh issue edit <number> --remove-assignee @me`, since the gate's kickback keeps it.
Mark it `shaping` in the state file.

An easy choice, one a later change can undo without touching stored data, takes
the most reversible option. Record it in `flags` and in the pull request's
`## Flagged for confirmation` list. A flagged piece is never merged under
pre-approval.

Either way the run moves on to the next unblocked piece.

## When a piece fails

Retry within the piece, up to three attempts, the same number fix uses. After
the third, kick it back: write a `## Kickback` section on the piece with one
line on what kept failing, push its branch and keep it, and move it back to
shaping through the gate, to `shaping:spec` with `python3 .agents/tools/gate.py move <number> spec --run <run name>` when an attempt showed a check that cannot be met as written,
and to `shaping:research` with `python3 .agents/tools/gate.py move <number> research --run <run name>` otherwise.
Then take the run's assignee off as a piece sent back does, and take the next
piece. Never let one piece consume the run. `/shape` picks the piece up from
its kickback, which settles a missing decision, chases a missing external
fact, or reassesses a shape the team could not safely own, rather than a
fourth attempt.

A piece whose build needs software installed outside the project folder is kicked back to `shaping:clarify` with a `## Kickback` section naming the tool, where it would go and how to undo it,
such as a tool missing from this computer or one too old:
`python3 .agents/tools/gate.py move <number> clarify --run <run name>`. The run
never installs it, since nobody is there to say yes, and takes the next piece. Where the same missing
tool would stop every piece left, it is a blocking failure every later piece
relies on, and the run ends with that reason, as below.

A blocking failure never stops the whole run unless it touches something every
later piece relies on: the smoke check on `main`, a GitHub that cannot be
reached, so no piece can be claimed, or anything that would change the build
path. A piece stops at any touch of a named sensitive area that carries no
recorded acceptance, even one the plan did not expect: section-builder's
flagged route kicks it back to `shaping:clarify` at the condition, and the run takes the next piece. The
run goes on; only that piece stops. Never guess to keep a run going.

## Resuming

A new session resumes from the state file, never from memory. A run is
unfinished while any piece in its state file is `waiting` or `building`. A run
whose every piece is in a final state is finished, and is never offered for
resuming. `/implement` typed alone or with `queue`, `/what-now` and `/sync`
each notice an unfinished run and offer to resume it. Where two runs are
unfinished, offer the newest and name the other.

Resuming is the same run, so its `merge_preapproved` stands. So does its
`at_once`: the offer to resume names that number and says the person can lower
it in their reply. Where the session died with several pieces built at once,
such as on a machine that ran out of memory, the state file shows each of them
`building` with its worktree, and each continues as below. Read `state.json`,
`progress.md`, `run.json` and each piece's labels, and take the pieces from
where they stand. A session can die after a gate move and before it writes the
state file, so where `state.json` is behind them, take where the labels and `run.json` say the piece stands,
and write `state.json` to match. A piece shown as
`building` continues from its last commit: on Claude Code, open its worktree
again with `worktree.sh open --resume`, which reuses the one already there,
and elsewhere check out its branch. Where that worktree holds an uncommitted
change, the script keeps it as it is: kick the piece back to `shaping:clarify` with a `## Kickback` section naming the worktree and the change, which stays as it is,
since the session that made the change is gone:
`python3 .agents/tools/gate.py move <number> clarify --run <run name>`.
Otherwise read what its commits already hold,
run its checks, and carry on from the first step not done. Read its claim back first. Where the claim is no longer this run's, back
off it as step 1 says.

`/sync` removes a run's folder once every piece in it is merged, closed, given back or kicked back,
counting a piece the run skipped or sent back to shaping as closed to the run,
since the run holds nothing more of it.

## When the run ends

The run ends when no eligible piece is left to take. That includes the moment
every remaining piece is held up, kicked back or skipped: the run ends at once with
its report, and never waits for something to change.

However it ends, whether it ran out of pieces, the smoke check failed on
`main`, GitHub could not be reached, or the build path would change, leave
every piece in a final state before the report:

- every `waiting` piece becomes `skipped`, with the reason the run ended;
- the piece in hand, or each of them where `at_once` is above 1, keeps its
  branch. Whether or not something was built on it, push its branch where it holds anything, keep it, and give the piece back to `state:ready` with `python3 .agents/tools/gate.py move <number> ready --run <run name>`,
  which takes the run's assignee off. Delete this run's claim comment, and mark
  it `skipped`. This includes the finished parts of a parent whose pull request never opened;
- on Claude Code, remove the worktree this run opened for each piece it kicked back, gave back or skipped,
  with `worktree.sh remove <path>`,
  only when nothing in it is unsaved, as defined above. Its branch is pushed
  first, or holds nothing new. A worktree still holding unsaved work is kept,
  and the report names it with what is unsaved. A piece in `to check` keeps
  its worktree until its pull request closes.

Where `merge_preapproved` is true, sweep the pieces in `to check` before the
report, bases first. Merge them one at a time: each one's update, its check and
its `gh pr merge` finish before the next piece is brought up to date, so each
piece is checked against a `main` that holds every merge before it. Merge a
piece only when it meets all six conditions in the `section-builder` skill's
`references/merge.md`, the first of which is a green check on the commit
brought up to date, and mark it `merged`. Test the other five before bringing a
piece up to date, so a piece held back for another reason gets no new commit
and no run of the check.

A piece whose merge from `main` conflicts, or whose check turns red only once
`main` is taken in, is not merged. It stays in `to check`, and its `reason` says
which of the two happened. A conflict still gets its one comment on the pull
request, as the merge step says. The sweep goes on with the pieces that do not stack
on it, and skips each one that does, with that reason. Each merge waits for one
more run of the check, so a sweep over five pieces on a ten-minute check takes
about fifty minutes. Wait for each check as the `section-builder` skill's
`references/merge.md` says under "Waiting for the check".

The report, in plain words, is one list and a merge order:

- what was kicked back to shaping and why, with its question, first;
- each piece with its pull request and its state, in the merge order, bases
  before the pieces stacked on them;
- under each piece, its flagged choices, and what the walk-through could not
  see. Where a dev server ran for it, the server has stopped, so say how to
  start it again rather than give an address: in its worktree, run the install
  and run commands AGENTS.md records, on the port `worktree.sh port <issue
  number>` gives;
- where `merge_preapproved` was true, which pieces were merged, how long the
  sweep waited for checks, and for each piece that was not, the merge condition
  it failed, in the words of the `section-builder` skill's
  `references/merge.md`, or that it conflicted with `main` or turned red once
  `main` was taken in. A piece held back
  because its merge would go live says so, and waits for the person or `/ship`;
- what was not eligible, or not reached, and why.

The person answers with the pull requests to merge, and each merge follows the
`section-builder` skill's `references/merge.md`.

When a run disappoints, the fix is in the documents rather than in the code by
hand: sharpen the done lines that let weak work through, add the missing rule
to the masterplan, then run it again. Hand-editing what a run wrote turns a
readable project into a mystery.

## Goal modes

Some tools ship a /goal feature: state a condition and the agent keeps going
until a separate model judges it met. Treat it as a run wearing the tool's
clothes, under the same rules: the condition comes from a done line or a plan
area's done lines, read aloud; a named sensitive area without a recorded
acceptance stops the piece that touches it, never the run; the three-attempt
kickback rule still applies per piece; the state file is kept the same way; and
each piece still lands through the save route the build path requires. Any
merge follows the `section-builder` skill's `references/merge.md`, however long
the machine ran: on a yes that names it, or on the person's pre-approval given
before the run.
