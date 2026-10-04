---
name: what-now
description: Orientation for a lost or returning user. Trigger when someone asks what to do next, has been away a while, feels lost, or a session died in the middle of something. Reads the documents and the git state and says where the project stands and what to do next. Never builds, fixes, or changes anything.
---

# What now

You are the safety net under the other six commands. Someone who forgets everything else and remembers this one is fine.

## Read

masterplan.md (build-path section first), the project's pieces, the recent
changelog and `changes/`, the capability profile in AGENTS.md, git status, the recent commits
and merged pull requests, any open pull requests, and a run's state file in `.agents/runs/` of the main folder, the first worktree git lists.

Refresh the printout with `sh .agents/tools/plan-refresh.sh` and read
`plan.local.md`. Where the project has no copy of the helper,
the `setup-ai-build-kit` skill's `references/pieces.md` says what to run
instead; never sort the pieces by hand. If GitHub cannot be reached, work from the printout and say when
it was written, because an old list a person can see beats no list at all. Note
whether the project has launched (the changelog says), whether work sits
half-done (git status says), whether a finished piece is waiting for its
merge click (an open pull request says), whether any check is failing,
whether an earlier review left an unresolved finding, whether flagged work is
still waiting, what the build-path section's `Accepted:` lines say the project
has knowingly given up, whether a manual setup step was left mid-way, whether Git
shows a merge or rebase conflict, whether a check-up is overdue, and whether
anything on the build path's recheck-when list has happened.

For the check-up, run `.agents/hooks/session-start.sh` with no options, its plain
mode, and take its answer, so what you say and what a session heard when it
opened always agree. It counts both the days and the changes landed since the
last visit, and prints nothing when neither is due. Only where the project has no
such script, take it from `.ai-build-kit-maintenance` when that file exists and
from the changelog dates when it does not.

Read which AI Build Kit release the project holds from the installed `maintain`
skill's `VERSION` file, or from `.ai-build-kit-version` at the project root where
that file is missing. Those are what the project's files are, so read them even
where the `kit` line in `.ai-build-kit-maintenance` names another version. Then
ask for the latest published release with
`gh api repos/gwpicard/ai-build-kit/releases/latest --jq .tag_name`. Ask that
endpoint and no other, the one `/maintain` asks, because it never answers with a
draft or a prerelease.

## Say

Open with where the build stands, in one line, then which command comes next and
why, in a few sentences of plain language.

Before the first ship, count: "you are four pieces in with three left, nothing
blocked and nothing half done". Once the project is live, drop the counts and
describe the state instead: "nothing is blocked and nothing is half done, three
things are waiting". A count reads as progress towards a finish line, and a live
project's list never empties.

Run the gate's report first. Where `python3 .agents/tools/gate.py report` names anything, lead with it,
before anything else: a piece with no state, two states, a sub-label beside the
wrong state, or a label the kit does not use. A board that says something
untrue makes every other line read from it wrong. Say each in the piece's own
words, and point at `/sync`, which asks the person how to put it right.

An open piece labelled `type:bug` comes next, before the counts. A thing that used to
work and no longer does outranks a thing that was never built: "the booking
confirmation is broken, so /fix comes before anything else". Name what is broken
rather than saying a piece is labelled.

A failing check is named next, after anything broken and before the counts. Say
it plainly as failing, because a red check is a fact the person cannot see for
themselves. An open review finding still waiting, and a setup step left
half-done, are named in the same place. None of the three is left sitting under a
"nothing is blocked"; each has its own recovery route below.

A piece being built or waiting for the person's check that was never shaped, or
never had its readiness check, is named in the same place, once, with what it is
missing. The printout lists it under Needs attention. Say it in the piece's own
words: "the late fees piece is being built, but nobody ever wrote down what done
looks like for it". Name it before it is merged rather than after.

Say how many entries are still notes rather than pieces, when any are, in the
words a person would use: "two things on the list are still just notes, so I
will ask you about them before building them". The printout counts them in its
last line. Knowing
that before a build session is worth more than meeting it during one.

Where a waiting piece says why it is waiting, pass the reason on rather than the
label: one needs a few questions, one needs a throwaway build before anybody can
decide, one needs a fact the agent can go and confirm on its own. Say which of
the three, because the first two need the person in the room and the third does
not. Somebody with ten minutes can answer the questions, or leave `/shape` to
settle the research without them.

Weigh the waiting pieces against the ready ones, in the same place as the counts
and never ahead of anything broken. Where more pieces are waiting on a question
than are ready to build, say that this session is better spent planning than
building, and give the reason in the counts themselves: one piece ready and four
nobody can build yet. Where the ready pieces outnumber the waiting ones, say
nothing about it and let the usual advice stand.

A piece in `state:in-review` with `review:person` is the person's own: it is built, and its pull request
is waiting for them to try it or merge it. The printout lists it under "In
review, waiting for you". Name it apart from the agent's work,
in the piece's own words: "the overdue list is built and waiting for you to try
it and merge it". Nothing moves it on except the person, so a piece left there
unnamed waits for good.

An unfinished run is named next, after anything broken or failing: a run whose
state file still shows a piece waiting or being built. Say how far it got and
what is left, in piece names, and offer to resume it. Its recovery route is
below.

A piece waiting on the person is named apart from the rest, as their own thing
to do rather than something the agent is working through: "nothing can happen on
the payment piece until somebody opens the card account, and it takes about ten
minutes". Say what the step is and where it happens, in the piece's own words,
because a step nobody names is a step nobody does.

Where the release the project holds and the published one differ, say so in one
line, close to: "This project holds v0.20.0, and v0.21.0 is published. /maintain
updates it." Where they match, or the call fails, say nothing about the version.
A version that matches is not news, and a failed call is no reason to say
anything either way. The version line is not one of the three things named
below.

Say piece names, never issue numbers. Say dependencies as sentences: "deposits
cannot start until card payments are set up", never "blocked by #9". Name at
most three things; if more apply, say how many and name the nearest. More than
three stops being orientation and becomes a report. When the person asks what
else can be worked on, still name at most three, and offer /queue for the rest:
it prints the plan a run would follow and ends on the command that runs it. Match where the project is in its life. Still building toward the first launch: the answer is usually /implement for the next ready piece, /shape to shape a new one, or /ship when the plan has run dry. Live and running: the answer is usually "say what you want to /shape", /fix for the thing that broke, or the /maintain that the check-up reminder shows is due.

End with a short recap of where the tool has got to, in the words a person would
use. Say what the last stretch of work was about, and whether anything is on the
go right now, drawn from the changelog, the recent commits, and the merged pull
requests read together. Tell it as a short account of where things stand, not a
count of commits or pieces. Leave out the broken or waiting items already named
above, since the recap is the wider sense of the project rather than a second
list. Where nothing has happened lately, say nothing here and the answer ends
where it did before.

## Recovery routes

### Uncommitted work

Explain what it appears to belong to, then offer a choice: continue it, save
it as a checkpoint, or clear it after showing exactly what would be lost.
Never run a destructive command without explicit approval for that specific
action.

### An unfinished run

A run of several pieces stopped part-way, usually because its session ended.
Name the pieces it finished, the one it was building and the ones still
waiting, read from the state file rather than remembered. Offer to resume it
with `/implement queue`, which carries on from where the state file says it
stopped, the piece it was building from its last commit. Change nothing
yourself.

### Merge or rebase conflict

Explain which two intentions collided. Resolve it automatically only when
the records make the right outcome unambiguous; otherwise preserve both
sides and ask. Treat any conflict touching data or deployment as one to
escalate rather than guess through.

### Missing capability

State plainly what the current harness cannot do, name the fallback in use,
and give one concrete setup action when one would remove the gap. Do not
imply the whole kit is incompatible because one optional enhancement is
missing.

### Flagged work waiting

State the blocked area, the help it's waiting on, where its brief lives, and
which work can keep going safely in the meantime. Say that the wait ends either
way: when that help happens, or when they carry on after the notice and their
acceptance goes on the record.

### A step only you can do

Name the step, where it happens, and what to bring back, in the words the piece
uses. Say what starts moving again once it is done, and what can carry on in the
meantime. Never repeat a key, password, or token back, and never ask for one to
be pasted into a message.

### Failing check

Name the check that is failing and what it is there to catch, in plain words,
for example the test that stops a booking being taken twice. Say that a red check
means the tool is not doing something it is meant to, and that /fix is where that
goes. Do not show the check's output or its logs.

### Open review finding

Where an earlier review raised something and nobody has settled it, name it in
the words the review used and say it is still open. Say it is a point somebody
made and no one has answered, so it is worth closing before more is built on top
of it. Name the piece it belongs to.

### Unfinished setup step

Where a manual setup step was started and left part-way, name the step and say it
is unfinished, so the person knows the tool is not fully stood up. Give the one
action that would finish it, and say what stays unavailable until it is done.

### Accepted risks

Where the build-path section carries `Accepted:` lines, say what the project has
given up, in one line each and in the words the person would use. This is a
reminder rather than a reopened argument: name what it was, when, and who
accepted it, and say plainly that it can be revisited by asking for the check
that was skipped. Do not ask again unasked.

## Done when

The next command is clear, the reason for it is said, nothing half-done or blocked is lying around unacknowledged, and no technical recovery decision has been pushed onto the user.
