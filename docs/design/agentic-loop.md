# Agentic loop: the v1 design

The design for v1 of the kit. A person and the system shape work together until
it can be built with nobody there. The system then builds it in loops, checks it
against a bar fixed before the build, and merges it, and a merge goes live. The
person reviews and steers; they never take part in a build.

The maintainer agreed the decisions in this note on 2 October 2026, after a
review of the kit, its backlog and outside work on agent loops. It replaces the
run, merge and launch parts of [loop-first-redesign.md](loop-first-redesign.md)
and [loop-first-round-2.md](loop-first-round-2.md). The piece contract, the
readiness check and the principle of those notes carry over, changed where this
note says so. The outside work behind the decisions, and where the kit stands
among related projects, is in [agentic-loop-research.md](agentic-loop-research.md).

## The principle

The work is shaping the work. Looping is the consequence.

A person's time goes into deciding what to build and how it will be judged.
Once a piece is shaped well enough that nobody needs to be asked anything, the
build is no longer a craft the person takes part in: it is a loop that runs
until the bar is met. The kit is a loop kit. It gives the person a place to
shape, and a set of loop modules (fix, build, goal and gauntlet) that each turn
one kind of shaped piece into a merged change.

So the quality of a project rests on the quality of its shaping. When a loop
needs a person, that is a gap in the shaping, and the piece goes back to be
shaped again rather than being finished by hand.

## Who it is for

Builders who direct agents: people who know what Git, branches and pull requests
are, and who direct agents rather than write code. They never have to read code.

## The name

With v1 the product becomes AI Loop Kit, in a repository of its own. Setting the
new names is its own piece of work: the plugin and marketplace names, the
founding command and the record files all change, and each step that changes
something online waits for the maintainer's approval at that step.

## Why

The loop-first redesign added unattended runs to a flow built for a person who
is present. Its own evidence showed the limit of that approach: rules held when
a command was typed or a machine enforced them, and prose the agent had to
remember did not. Almost every rule between capture and a merge is still prose.

Outside work points the same way. Teams that run agents unattended keep the
person at two places, deciding what to build and reviewing what was built, and
they hold everything between with fixed steps the agent cannot skip. Teams that
removed the human found that agents weaken the checks to get a green result,
so the checks have to sit where the builder cannot reach them.

So v1 turns the flow round. The loop is the default and a command is a manual
override. Each state change goes through a script. Each piece carries its own
bar, and the bar decides which loop module builds it.

## The model in one picture

```
SHAPING (person + system)                          IMPLEMENTING (system alone)
------------------------------------------         -----------------------------------------------
raw --triage--> decision loop ------> spec --> check --> READY --> BUILDING (loop module) --> IN-REVIEW --> merged
                research (facts)                                    fix | build | goal | gauntlet          = live
                clarify (decisions)
                prototype (decisions)
                     ^                                                     |
                     +-------------- kickback, with findings --------------+
```

## Two zones

Shaping is where every decision is made. The person and the system work
together: the system finds facts, builds throwaway prototypes and writes the
spec, and the person makes the choices. Nothing leaves shaping until the piece
can be built with no further question.

Implementing is where the system works alone. It builds, checks, reviews and
integrates. The person takes part only through review, and review never stops
the loop: the loop moves on to the next piece while a review waits. If a build
meets something that needs a person, the shaping was not finished, and the
piece goes back.

## Issue states

Each open issue carries exactly one state label. A parent, an issue with open
parts, carries none: its parts carry the states. A state that has sub-labels
carries exactly one of them. Labels are prefixed with their dimension.

| State | Meaning | Sub-label, exactly one |
|---|---|---|
| `state:shaping` | Not ready to build | `shaping:raw`, `shaping:research`, `shaping:clarify`, `shaping:prototype`, `shaping:spec`, `shaping:check` |
| `state:ready` | Passed the ready gate; can be built with nobody there | none |
| `state:building` | A run is building it | none |
| `state:in-review` | Built, every gate green, not yet on `main` | `review:auto` or `review:person` |
| closed | Merged (completed) or dropped (not planned) | GitHub's close reason |

Three other dimensions sit beside the state. `type:` is `feature`, `bug` or
`chore`, set at triage. `loop:` is `fix`, `build`, `goal` or `gauntlet`, the
loop module, set before the ready gate. The subject labels name the areas a piece touches.

There is no idea, parked, queued or blocked label. Captured work is
`shaping:raw`, which is the backlog. Work nobody will do is closed as not
planned and can be reopened. A failure during a build is a kickback. Being held
up by another issue is a GitHub blocked-by link. Membership of a run lives in
the run record.

Only the gate script changes a state. It checks the condition, writes the new
labels and the run record in one step, and refuses when the condition fails. A
hook and the deny rules stop the agent editing state labels directly. A person
can still change labels on GitHub, and the next gate run reports what it finds.

Every move reads the piece twice: once to check the condition, and again just
before it writes. If the labels changed in between, another session moved the
piece, and the gate refuses rather than write over that move.

To tell whether a sub-state's question was answered, the gate keeps one hidden
line as the last line of the piece's body:
`<!-- loop:gate sub-state=<sub-state> since=<date> answer=<short hash> -->`. It
writes the line on every move into a shaping sub-state, with a hash of the
section that records that sub-state's answer (`## Decided` for clarify and
prototype, `## Research` for research, `## Loop` and `## Reach` together for
spec, `## Readiness` for check, and an empty section for raw). Spec's hash
leaves out a `Kept branch:` line, which names an earlier spec branch and is
not part of the contract, so adding that line alone never lets a piece leave
spec. Spec's line also
carries `question=<short hash>`, a hash of its `## Open question`, so a move
back to asking needs a question the piece did not carry in. On the way out it
compares the section with the hash. A piece with no such line is
read as having entered with the section empty. Only the gate writes the line,
and it changes nothing else in the body.

| From | To | Condition |
|---|---|---|
| (new) | `shaping:raw` | Captured in the person's words |
| `shaping:raw` | next sub-state | Triaged: a `type:` and the first open question |
| any shaping sub-state | another | The current question is settled and recorded in the piece |
| `shaping:check` | `state:ready` | The machine lint passes, a fresh session finds it ready, and a `loop:` is set |
| `state:ready` | `state:building` | A run claims it; its blockers are closed or earlier in the same run |
| `state:building` | `state:in-review` | The bar is met with fresh evidence, and the automatic review passes |
| `state:building` | `state:shaping` | Kickback, to the sub-state the problem needs |
| `state:in-review` | closed | The PR that carries it merges to `main` |
| `state:in-review` | `state:building` | Review finds a defect the spec already covers |
| `state:in-review` | `state:shaping` | Review finds a problem in the spec |
| `state:ready` | `state:shaping` | The person pulls it back before a run claims it |
| `state:building` or `state:in-review` | `state:ready` | A run gives it back when it ends early or is abandoned, or a piece it needs was kicked back; the branch is kept |

Leaving `shaping:spec` for `research`, `clarify` or `prototype` needs a new
`## Open question` holding one question, the same rule as leaving `raw` for
one of those three.

## Shaping

Each sub-state answers a different kind of question, which is what keeps them
apart.

| Sub-state | Question | Who does it | Output |
|---|---|---|---|
| `raw` | What is this? | Person and system | A type, a first guess at the loop module, any duplicate or overlap found |
| `research` | What is true? | System | Findings with a source for each claim, and a recommendation |
| `clarify` | What do we want? | Person | Decisions recorded in the piece |
| `prototype` | What do we want, when it has to be seen? | System builds, person decides | A decision; the prototype is deleted or kept apart |
| `spec` | No question left | System | The full contract, with the loop module, its bar and the acceptance checks |
| `check` | Is it complete and buildable? | Fresh session and machine lint | Ready, or the gaps |

Research finds facts and never decides. The system settles a fact by itself;
when a finding needs a choice, the piece moves to `clarify`. Clarify and
prototype produce decisions, and only the person makes those. Spec and check
have no open question, so the system works through them alone, and a question
found there sends the piece back.

The decision loop has no fixed order. The piece sits in the sub-state of its
next open question, and an answer is written into the piece before the label
moves. Shaping reads the lessons earlier runs recorded before it researches.

Ceremony follows the size of the piece. A sub-state with nothing to do is
skipped, so a chore can go from `raw` to `spec` to `check`. Each type has a
length limit for its contract, which the lint holds. A bug with a clear
reproduction takes this short route, and can run at once as a run of one.

Sensitive areas are settled here. The risk notice is given in shaping, and the
person's acceptance is recorded before the ready gate. A piece in an area with
no acceptance cannot pass the gate.

## The piece contract

The contract is one issue. Its human header says what the person will be able
to do and how that will be judged. Its agent layer holds everything a builder
needs, because the builder never sees the shaping conversation. The fields of
the earlier contract carry over, with these additions.

- The loop module, and the bar that module needs, described in the next section.
- Acceptance checks written as real tests, committed with the spec on a
  branch, and failing on `main` today.
- The reach fields described in the next section: what the piece may change,
  what else it reaches, what happens if it breaks, what it depends on, and the
  commit the reach was worked out on. A run plans its order from these.
- For a fix, a line saying what must not change.
- An out-of-scope list.
- The crew, written only where it differs from the loop module's default, and
  what the piece needs from the computer. Both are described below.

The brief rules hold the contract to what a builder can use alone: behaviour
rather than steps, interfaces rather than file paths or line numbers, and each
acceptance criterion checkable on its own. The lint checks them.

## Reach and risk

Shaping works out what a piece touches and what happens if it breaks, from the
code as it is today, and records the result in words. It stores no graph. The
evidence behind this is that strong models find code well without a graph, a
stored index goes stale, and the largest measured cut in regressions came from
giving the builder the tests that guard the code it changes.

In `research`, the system runs the reach check on `main`, adds one query of the
saved history for files that tend to change together, and maps every hit to a
named area of the project. In `clarify`, when the reach touches a sensitive
area, stored data or anything that leaves the tool, the person answers one
question: "Say this went live and went wrong. Who noticed, and what did they
see?"

The contract records five fields.

| Field | Contents |
|---|---|
| `Boundary:` | The areas the piece may change |
| `Reaches:` | The areas it affects without changing them, each with the existing tests that guard it by name, or "no test covers it" |
| `If it breaks:` | Who notices what, and how it is undone: a rollback, or not reversible because of data |
| `Depends on:` | The pieces it needs, as blocked-by links |
| `Reach derived at:` | The commit the reach was worked out on |

The tests named under `Reaches:` become guard checks in the frozen bar. A
reached area with no test needs a guard check among the acceptance checks.

The person sees one sentence, such as "This changes sign-in. It also reaches
billing and email, which 14 checks guard. If it breaks, people cannot sign in,
and a rollback undoes it." A diagram appears only when a piece adds or changes
a connection outside the tool, and it is the masterplan's connections picture
with the change marked. A code graph is never shown.

The area map covers the whole project, not only the sensitive areas, so that a
boundary always names real paths. Founding writes it, and the project check
turns red on a folder no area claims. The map lives in the Areas section of
`docs/working-rules.md`, outside the masterplan; a sensitive area points into
it by name.

The ready gate checks that every area exists in the map, that every reached
area names a test or says none covers it, that every sensitive area in the
boundary or the reach has an acceptance, that the dependencies form no cycle,
and that the reach worked out again on today's `main` still matches. At the
start of a run the reach is worked out again and the waves are planned from
overlapping boundaries. A diff that changes files outside its boundary forces
`review:person`.

Richer engines wait for the pilot that measures whether they help: call graphs,
language servers, knowledge graphs, hotspot scores and any saved index. The
pilot also measures how closely each recorded boundary matched what the diff
changed, which decides how far the boundary can be trusted.

## Loop modules

Shaping chooses the loop module, because each module needs a different bar.

| Loop module | Chosen when | Bar in the spec | Loop | Exit |
|---|---|---|---|---|
| `fix` | Something promised, or that once worked, is broken | A reproduction that fails today; what must not change | Reproduce, rank causes, fix, run the regression checks | The reproduction passes and nothing else fails |
| `build` | Done can be stated as checks that pass or fail | The acceptance checks | Show the checks failing, then build until they pass | Every check green, and review passes |
| `goal` | Done is a measured number with a target | The metric and the command that measures it, the target, a budget, guard checks, a held-out check | Measure, change, keep or discard | Target reached with every guard check green |
| `gauntlet` | Done is judged against a specific example | A reference the person approved that can be fetched and compared, the comparison method, a budget, guard checks | Build, then a fresh blind critic compares with the reference | The work wins the comparison with every guard check green |

One piece has one loop module. The builder may switch modules during a build,
and logs the switch, only when the new module's bar comes from the spec with no
new decision. Otherwise the piece is kicked back. Two needs that call for two
modules become two pieces joined by a blocked-by link.

A loop stops at a limit on attempts or at a budget of time or tokens, whichever
comes first. An attempt is a fresh context carrying a note the run script
builds from what failed: the failing checks, their exit codes and the files
touched. A model does not summarise it. Within those limits the builder may research and repair by itself,
provided what it learns does not change the spec.

A goal that spends its budget without reaching the target goes to review as
`review:person`, carrying its best result that passed the guard checks and the
numbers. A gauntlet loop that spends its budget is kicked back.

Fixes follow a stricter discipline. No cause is tested before the reproduction
exists. Causes are ranked and each makes a prediction. Three failed fixes send
the piece back to `research`, because the architecture is in question; a bug
that cannot be reproduced goes back to `clarify`. Each fix adds the cheapest
check that would have caught the fault.

## Crews

A crew is the set of agents a step uses and how they connect. Shaping fixes it,
like the bar, and the run script starts every member. No agent starts a writer.

There are four roles. The builder is the only one that writes. The critic reads
the contract, the diff and any reference, and nothing else. A researcher or
probe only reads. The checker is a fresh session that reads only the contract.
Each role is an agent definition with its own list of allowed tools.

| Step | Crew | Default | Cap |
|---|---|---|---|
| Research | Readers in parallel, then one synthesis | 1 for a fact, 2 to 4 for a comparison | 5 |
| Prototype | Variants side by side for the person | 1 | 3 |
| Readiness check | The lint, then one fresh checker | 1 | 1 |
| Fix | One reading probe per ranked cause, then one builder, then a critic | 1 probe | 3 probes |
| Build | One builder, then one critic | 1 and 1 | The review-round cap |
| Goal | Keep or discard; optionally a race in separate worktrees, judged by the metric | 1 | 3 |
| Gauntlet | One builder, then blind critics judging both orders | 1 critic | 3 critics, from other model families where available |
| Run | Waves of pieces whose boundaries do not overlap, joined by the integration queue | 3 | 1 when boundaries overlap |

The contract's `Crew:` field takes its default from the loop module. Shaping
writes only a change from the default, with its reason. The lint checks that
the crew is a known shape, that each width is within its cap and that a change
carries a reason. One piece has one writer, and a piece that seems to need two
is split.

Helpers only read, count against the piece's budget, and start nothing of their
own. Each member receives only its declared inputs, so a critic never sees the
builder's transcript. Verdicts come back in a fixed format. A finding counts
only once it is reproduced or tied to a failing check. A comparison between two
results runs in both orders, and a split verdict is not a win.

The defaults stay small because of the evidence. Most failures of systems built
from several agents trace back to their design, agents working independently
multiply each other's errors, parallel writers overwrite each other, debate
does no better than a vote, and extra critics soon repeat each other. Every
member also costs roughly a full context of its own.

## The frozen bar

With automatic review, the checks are the only judge, so the builder cannot
change them. When a piece passes the ready gate, the gate script records a hash
of its contract, and a contract changed during the build is a kickback.

The build gate compares the branch with `main` and refuses a diff that edits,
deletes or skips an acceptance check or an existing test. It also refuses an
added lint or type suppression, a lowered threshold, an updated snapshot, and
any change to the project check, the CI workflow, the hooks or the deny rules.
A piece that truly needs one of those changes is forced to `review:person`.

Before a piece moves to `in-review`, the gate needs fresh evidence: each command
run, its exit code, the commit it ran on, and for fix and build, the same check
failing before the change and passing after it. The builder's own statement
that it is done counts for nothing.

A bar can also be weak from the start, so the ready gate tests the checks
themselves. Each acceptance check must fail on `main` on its assertion, never
on an error such as a failed import. The fresh checker matches each check to
the criterion it claims to test. After the build goes green, the existing
test-strength check breaks the changed code on purpose, and an acceptance check
that does not notice forces `review:person`. Red before green is judged as
evidence; the kit does not prescribe the steps a builder takes to get there.

## Review

Every piece gets an automatic review. A fresh session reads only the contract
and the diff, never the builder's account of the work. It gives two verdicts:
whether the change meets the contract, and whether the code is sound. It sorts
each gap as missing, partial, contradicting the contract, or unrequested.
Missing and partial work goes back to the builder within its limits; a
contradiction that needs a decision is a kickback; unrequested work is taken
out, or forces `review:person`. Findings stay within correctness and the stated
requirements, review rounds are capped, and every ruling is logged.

The builder ends each attempt with one status, and each status has one route.

| Builder status | Route |
|---|---|
| Done | Checking: gates and automatic review |
| Done, with concerns | `review:person` |
| Needs context | Kickback |
| Blocked | Kickback |
| Environment failed | Retry, then pause the run; never a kickback |

A failure of the computer or the setup is not a gap in the shaping, so it never
sends a piece back. Otherwise the kickback rate would measure the laptop.

`review:auto` is the default. The system asks whether the person wants to
review particular pieces, and warns when a piece would benefit from it. A
sensitive area, a goal that missed its target, a change to a check or the
project's guards, a change outside the piece's boundary, an acceptance check
that missed a deliberate break, a data change that cannot be undone, a
builder's concerns, and the first deployment always force `review:person`. A review the person owes waits on the shaping
board.

The automatic reviewer is calibrated against the person. Where both judged a
piece, `/maintain` compares their verdicts and proposes changes to the
reviewer's instructions where they disagree.

## Kickback

A kickback returns a piece to the shaping sub-state the problem needs:
`clarify` for a decision, `research` for a fact, `spec` for a contract that
needs rewriting. The piece gains a Kickback section saying what happened, what
was tried and what decision is needed. Its branch is kept. It appears on the
shaping board, and the run carries on with the pieces that do not depend on it.

## Runs

Every build is a run. A run of one builds a single piece on its own branch and
opens a PR to `main`. A run of several builds each piece on its own branch,
integrates them into one integration branch, and opens one PR from that branch
to `main`.

A run starts when the person picks the pieces, or says all ready pieces. It asks
nothing. How many pieces build at once, the budget and the merge policy come
from project settings. No run starts while `main` is red; the kit files a bug
piece instead.

The run plans waves from the `Depends on:` and `Boundary:` fields. Pieces that depend
on each other, or that change the same area, build one after another, and the
parallel count drops to one when every piece shares an area.

Pieces join the integration branch one at a time. Each is brought up to date
with the branch, the full checks run on the combined result, and only then is
the piece integrated. On the automatic path an agent never resolves a merge
conflict by judgement: the later piece is rebuilt on the new head, or kicked
back. If the integration branch goes red, the run finds the piece that broke it
by bisecting and kicks back that piece alone.

The run record holds a status for each piece and for the run. These live in the
record, not in labels, and the gate script writes them in the same step as the
labels.

| Piece status in a run | Issue state at the same time |
|---|---|
| queued | `state:ready` |
| building | `state:building` |
| checking | `state:building` |
| integrated | `state:in-review` |
| kicked back | `state:shaping` |
| withdrawn, because a piece it needs was kicked back | `state:ready` |

| Run status | Meaning |
|---|---|
| planned | Pieces chosen, nothing started |
| running | Pieces are building |
| paused | Stopped by the person or by a limit; it can continue |
| in preview | Every piece is finished and the integration branch has a preview |
| merged | The run's PR merged to `main` and is live |
| abandoned | Stopped for good; the branches are kept |

A run has a budget ceiling as well as each piece's budget, and a cap on CI
rounds. Reaching either, or a run of refused commands, pauses the run and
tells the person.

## Computer resources

The coding agents' own limits do not look at memory, and a real run of ten
builders froze a 15 GiB computer for about four hours. So the run decides how
many builders to start from the computer itself.

Before a run starts, it measures free memory and processor cores and suggests a
number of builders: the memory left after a reserve, divided by what each
builder needs, but never more than half the cores or more than four. The person
may raise it, after one warning, to a hard cap of six. A piece marked heavy,
such as one that runs a container, downloads a model or builds an index, runs
alone.

Before each new builder starts, the run checks memory pressure and swap. Under
pressure it starts no new builder, stops dev servers nobody is using, and lowers
the count for the rest of the run while running builders finish. Under critical
pressure it also stops the newest builder that has no commit yet, keeps its
work and counts no attempt. Starts resume, at the lower count, once pressure has
been normal for ten minutes.

When a usage limit is reached, the run starts nothing new and records when the
allowance resets. Its opening line says that a run of several builders spends
the allowance that many times faster.

Worktrees share what they can: one package store, the coordinator's single
browser, a dev server only during a walk-through, and at most two test workers
for each builder.

A builder's heartbeat is a change in its worktree. After 30 minutes with none,
the run asks it for its state; after 45 it stops the builder, keeps the work and
counts an attempt. Each piece also has a wall-clock cap, two hours unless its
contract says otherwise.

The numbers live in three places. Project and computer settings hold the caps,
the reserve, the pressure thresholds, the timeouts and the model for each role.
The piece holds `Heavy:`, whether it needs a dev server or a browser, its
expected duration and any resource it cannot share. The run record holds the
current count, each change and its reason, the peak memory measured and each
builder's last heartbeat. The memory each builder needs is an estimate until
the first real runs measure it.

## Merging and going live

A merge to `main` goes live. A run's PR merges automatically when every piece is
`review:auto`, every gate is green, no sensitive area is touched, a smoke test
of the acceptance paths passes on the run's preview, the project's recipe has
proven in a real run that previews keep to their own data, and the project has
earned automatic merge. Otherwise the person merges after looking at the preview, and
any piece marked `review:person` can be opened on its own preview or checkout.

Automatic merge is earned. Each project starts with the person merging. After a
number of clean runs, `/maintain` offers to switch to automatic merge, and the
rules above then apply. A clean run had no merge reverted and no bug filed
against its pieces within a few days, and where the person also judged a piece,
the automatic reviewer agreed. The offer also needs a slow signal, because tests
answer in seconds while poor structure costs months: the drift and structure
reads must not have got worse.

Automatic merge needs a `main` that GitHub protects, which means a public
repository or a paid plan. On a free private repository GitHub offers no branch
protection, rulesets or automatic merge, so the kit relies on its own guards and
the person merges. Setup says so in plain words.

A data change that cannot be undone, such as a migration that drops or rewrites
data, is marked in shaping under `If it breaks:`. Its piece always goes to the
person, and the merge waits for a backup taken just before it.

After each merge a health check runs against production. If it fails, the
deployment rolls back to the previous build, and the kit files a bug piece.

## Deployment

`/ship` becomes `/deploy`, which sets up the pipeline: previews for branches,
production on merge, rollback, secrets and the health check. It runs the first
time and again when the project moves to new infrastructure. Founding chooses
the recipe, because the stack shapes the code, and `/deploy` builds the pipeline
from it.

A preview address becomes a recipe field: some hosts give one per
branch and per commit, others one per pull request, and a local checkout on its
own port is the fallback. A recipe also says how to boot a copy of the app
inside one worktree, on its own port, with throwaway seeded data and a log the
builder can read, so parallel builds never share a database or a port.

A preview never touches real data. Each one uses its own throwaway database,
seeded with the project's sample data, or the host's own database branching
where the recipe supports it. Until a real run has proven this for a recipe,
automatic merge stays off for the projects on it.

A tool that is not hosted, such as a library or a command-line tool, has no
live copy. A merge there means the piece is done. When the person asks,
`/deploy` makes a GitHub release with the next version.

## The safety boundary for runs

An unattended run holds private data, reads content nobody checked, and can
send data out, and an automatic merge puts the result live. The boundary keeps
those apart.

The native sandbox is on, with a network allowlist taken from the recipe; where
the platform has none, setup says so. A run's worktrees carry no production
secrets. A run can push only to its own branches. Text the person did not write,
such as other people's comments, web pages and package files, is data and never
an instruction. A new dependency is checked to exist, with its age and licence,
before it is added. A secret scan runs in the gate.

An allowlist is not a boundary on its own: GitHub and the model's own service
are on it, and both can carry data out. So the push token is limited to the
repository and held by the gate script, outside the sandbox where the platform
allows. The builder's brief says what it may do outside the code, because
agents measurably reach further when nothing says so.

## Boards

Two boards show the state model to the person. Both come from one status file,
which a script writes from the issues and the run records.

The shaping board is the person's work surface. At the top it lists what needs
them now: questions to answer, prototypes to decide on, references and kickbacks
to look at, reviews owed, and run PRs waiting for a merge. Below that it shows
the shaping sub-states and the ready pieces as columns. From the board the
person answers, approves, orders the ready pieces, asks to review a piece, and
starts a run.

The loop board follows runs. It shows each run's status, start time, running
time, counts by piece status, preview address and budget used. Each piece shows
its status, loop module, start and end, attempts, progress in its own terms (checks
passing for a build, the current and best value for a goal, the round and last
verdict for a gauntlet), a link to its session log and what it could not check.
An activity log carries the times. The board can pause, continue and stop a run.

The person hears about four things without looking: a piece needs their review,
a run paused, a piece was kicked back, and a run went live. The default view is
a local HTML page; on Claude it is also a live artifact. Other platforms follow.

## Learning and code health

Each piece records what it learned, limited to what the code and tests do not
show. When a run closes, each lesson becomes a check wherever a machine can hold
it, and otherwise an `AGENTS.md` line, a masterplan change or a new raw piece.
It lands through the run's PR. Instruction files written by a model have been
measured to lower success, so lines are rationed, and `/maintain` sorts the
lessons it finds: keep, update, merge or delete.

The kit measures itself on real projects from the run records. `/maintain`
reports kickbacks by shaping sub-state, merges that were reverted or followed
by a bug within a few days, and how often the automatic reviewer agreed with the
person. The replay harness reports, for each model, whether a scenario passes on
every one of several clean runs.

The constraints in the masterplan become rules in the project check wherever a
tool can hold them, each with a failure message that says how to fix it.
Violations that already exist sit in a baseline that may only shrink. The reads
for drift, copied code and unused code run after a number of merged runs, and
what they find becomes `type:chore` pieces. Work found during a build becomes a
raw piece linked to the piece that found it. The record of current behaviour is
updated by each piece's change at the merge.

## Commands

| Command | Job |
|---|---|
| `/setup-ai-build-kit` | Founds a project or adopts one: records, constraints, settings, recipe, labels |
| `/shape` | Captures, triages and shapes, up to the ready gate |
| `/implement` | Starts a run on the chosen pieces, each in its loop module |
| `/deploy` | Sets up or moves the deployment pipeline |
| `/what-now` | Opens the shaping board and the loop board |
| `/maintain` | The health visit: updates, record upkeep, lessons, drift reads, the offer of automatic merge |

`/queue` becomes the plan shown when a run starts and on the loop board. `/sync`
becomes part of `/maintain`, because the merge now applies each piece's record
changes. `/fix` goes: a bug is shaped like any other piece, on the short route
when its reproduction is clear.

The background skills keep their jobs in new places. Change-triage does the
triage in `raw`. Clarify runs the interview in `clarify` and at founding.
Section-builder becomes the engine for the build and fix modules. Second-opinion
becomes the automatic reviewer and the gauntlet's critic. Screen-check becomes a
check a bar can name.

## What a machine enforces

| Rule | Held by |
|---|---|
| One state and one sub-label | The gate script, a hook, deny rules |
| The ready gate | The lint, plus the fresh session's verdict |
| The frozen bar | The gate script's diff check and the contract hash |
| Fresh evidence | The gate script, through a Stop hook that runs the real checks |
| Integration one piece at a time, bisect on red | The run scripts |
| No push to `main`, no force push | Deny rules, and GitHub protection where the plan allows it |
| Automatic merge conditions | The gate script and GitHub's automatic merge |
| Run limits | The run record and the gate script |
| The crew and its inputs | The run script, which starts every member |
| Memory pressure and stuck builders | The run script's checks before each start and on each heartbeat |
| The sandbox and allowlist | The coding agent's sandbox settings |

Judgement stays where a machine cannot reach: research, the fresh readiness
check, the automatic review and the gauntlet's critic. Each runs in a fresh
session and returns a fixed verdict the gate script can read.

Every gate names what it catches, and gates come in two kinds. A guide makes up
for something models cannot yet do reliably; each has a test that removes it to
show whether it still earns its place, run at each release and with each new
model. A sensor guards against the builder's incentives, such as the frozen
bar, fresh evidence and the boundary check, and stays whatever the model.

Every script is quiet when it passes, printing one line, and on failure says
what to do next. A refusal from the gate script names the next allowed action.

## Platforms

Claude Code comes first, with the gates as hooks. Codex gets the same scripts as
its own hooks and rules, graded expected to work until a recorded run. Other
coding agents get the core of shaping and one piece at a time.

## Projects founded with AI Build Kit

AI Loop Kit is for new projects. Moving a project founded with AI Build Kit
onto the new labels, records and commands would be too hard to do safely, so
there is no migration. Those projects stay on AI Build Kit, which keeps fixes
for a stated period and is then archived. AI Loop Kit does not carry the
migrations and upkeep the old kit kept for its older projects.

AI Loop Kit lives in a repository of its own. The mechanisms built in the
overnight batch are reused one at a time rather than merged as a batch: the
recovery helper that keeps failed work and checks a baseline, fresh builder
contexts, the rule for which browser a walk-through may use, the force-push
deny rules, the question box, and continuing in the same turn. The parked
state, the try-it opt-in and shaping inside a run do not carry over.

## 1.0

1.0 promises that the commands, the records and the way work is built will not
change underneath a person. That needs:

- this model complete, with all four loop modules, runs, kickback, `/deploy` and both
  boards;
- real runs recorded, one for each loop module, and one `/deploy` for each recipe;
- the compact masterplan, since 1.0 fixes the project's record format.

## What stays

Shaping with the clarify interview, prototypes and research. The readiness check
in a fresh session. The risk notice and its acceptance, now given in shaping.
The rule that the person never has to read code. Recipes as the only place a
product is named. The kit's refusal to become a service. A person deciding what
reaches live, until a project has earned automatic merge.

## Traps this design avoids

Two sources of truth, which is why the gate script writes labels and the run
record together. Ceremony for its own sake, which is why sub-states can be
skipped and contracts have a length limit. A permanent judge, which is why every
gate names what it catches. Agents organised into a hierarchy, where runs and
gates are enough. A number to game, such as coverage. Review requests so
frequent that the person stops reading them.

An agent resolving a merge
conflict by judgement on the automatic path. Prescribing the steps inside a
loop, where only the evidence is judged. And a flaky guard check sending pieces
back, where it should become a chore piece of its own.

## Settled when built

These numbers are left to the pieces that build them, each with a default to
test: the attempt limit (three today), the CI round cap, the run and piece
budgets, the number of clean runs before automatic merge is offered, the number
of merged runs between drift reads, the length limit for each type's contract,
the memory reserve and the memory each builder needs, the pressure thresholds,
and the timeouts for a stuck builder.

Settled so far: a piece's contract may hold 80 lines for a chore, 120 for a bug
and 250 for a feature, counted without its Readiness, Kickback and Original
report sections. The ready-gate lint holds these limits, and the real runs
measure them.
