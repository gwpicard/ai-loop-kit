# The fix loop

A piece labelled `loop:fix` is a repair of behaviour the masterplan promised.
change-triage told it from a wish when the piece was shaped, and `/shape` wrote
its reproduction, the check that fails today, and its `Must not change:` line.
section-builder loads this file for such a piece and builds it by these steps in
place of its own steps 2 to 5. The fix loop claims nothing of its own: section-builder's step 1 claimed the piece before it loaded this file.

A repair runs in the same loop as a build. The run script, the fresh builder for each attempt, the five statuses, the limits and the kept work are as the `section-builder` skill's `references/build-loop.md` says. Each builder of a
repair follows the steps below inside its attempt, lists the causes it tested
in its result, and ends with one status. Where a repair goes at its limit is
the last section here.

You restore promised behaviour. The discipline is the order: never change
code before the problem repeats reliably and the cause is understood and
explained. No cause is tested before a reproduction exists, and the gate holds
that order. `gate.py result` and the move to review refuse a repair when a commit that changes a file other than a test was made, in the attempt, before the gate's record showed the reproduction failing at the start commit. So run the `Reproduction:` check through the gate, `python3 .agents/tools/gate.py evidence <number> -- <command>`, on the start commit, before the first change to the code.

Every move this loop makes goes through the gate. Where the gate refuses a move, tell the person its line in plain words and stop that move.
Never write the label another way, as the `setup-ai-build-kit` skill's
`references/blocked-commands.md` says.

## 1. Define the symptom

Record the exact steps that trigger it, the expected result, the actual
result, the error text or artifact verbatim if there is one, the environment
it happened in, and whether it's intermittent. A bug you can't describe this
precisely is a bug you can't verify as fixed.

## 2. Build the tightest feedback loop available

After launch on Build and run it or Build with care, read the tool's own
request record alongside the person's report as a source for the reproduction.
Use it to find the failed step and the smallest repeatable case. If the record
is absent or cannot be reached, say what evidence is missing and continue with
the other sources below; never ask the person to read logs. The project's
Secrets and Confidential files rules still apply to anything read or reported.
A step that needs a secret reads where it lives from the masterplan first, as
the Secrets rule says, and asks once when that is unknown. With nobody there,
that question ends the attempt as `needs_context`, naming `clarify`.

Before ranking causes, read `CHANGELOG.md` and closed pieces for the same area,
with the entries in `changes/` not yet folded into it.
A repair already tried and failed is ruled out or named as a repeat; a cause
already established ranks first. When that history changes the ranking, say one
line: "This was tried on <date> and did not hold, so it is ruled out." The
history is evidence to check against the present, not a verdict to copy.

Load the `section-builder` skill's `references/reach-check.md` and run its
reach check now. Run the existing tests it finds before writing a new focused
test. Prefer the existing test when it catches the exact symptom; add the new
regression test after the cause is known.

Find one repeatable check that catches the exact symptom. The piece's
`Reproduction:` check comes first. Where it does not catch the symptom, prefer,
in order: an existing failing test; a new focused automated test; a request or
command script; browser automation; replayed input; a small throwaway harness.

The person never needs to know which technique this was. The result and the
hand-over state how the bug is triggered, what result marks failure, how long
the check takes, and whether it's reliable.

When no loop can be built, the reproduction cannot be built: end the attempt as `blocked`, naming `clarify` and the missing artifact, access or permission. Do not begin speculative patching without one.

## 3. Reproduce and minimise

Run the check through the gate on the start commit, confirm it actually
catches the person's bug, then remove irrelevant steps or inputs one at a time
until only the smallest case that still fails remains.

A reproduction that passes only sometimes is recorded as unreliable, in the
result's `concerns`. It is ranked as a cause of its own, and the fault is never
counted as fixed on a retry: a pass after a failure on the same commit is the
same unreliable check passing by chance.

## 4. Rank causes

List two to five plausible causes, each with a falsifiable prediction, most likely first, and write them in the result's `causes` list in that rank order, each with its outcome: `ruled out`, `confirmed` or `not tested`. The next attempt reads them in
the note, and a piece sent back to shaping carries them all.

When the piece or the changelog names a time the behaviour worked, use the
tight reproduction to bisect the saved history before testing the ranked
causes. Report the result as: "It broke in the change called <piece title> on
<date>." Do not bisect when there is no known-good point.

## 5. Test one cause at a time

Change one variable, and keep any temporary instrumentation targeted and clearly
labelled: name the file you write a temporary log to and read it back while
testing the cause, so the evidence sits somewhere you can point at rather than
scroll past. Announce a reset to the last saved state after a cause that did
not hold, before trying differently. Between attempts the run script puts the
branch back for you. Failed fixes never stack; stacked fixes are how clean
projects rot.

## 6. Fix and lock it down

Create the regression evidence at the highest credible user-facing boundary,
watch it fail, apply the smallest fix that addresses the actual cause, watch
it pass, then rerun the original, unminimised case. When no credible
automated boundary exists, record that as a maintainability finding and use
the strongest manual or operational evidence available instead.

Each fix adds the cheapest check that would have caught the fault. Usually that
is the reproduction itself, kept as the regression check.

The `Must not change:` line is held by a guard check. Where `Reaches:` already names a test guarding that behaviour, that test is the guard check. Otherwise write one as a new test file in the attempt's first commit, before any other change, and record it with `python3 .agents/tools/gate.py evidence <number> --phase guard -- <command>`. The gate accepts it only when it passes at the start commit, with the branch's tests laid over the code as it was. Then, before the move to review it runs every check recorded with phase `guard` alongside the others, and refuses when one fails.

The checks-first and test rules in section-builder's step 4 apply to a repair
too. Commit the failing regression check on its own before the fix, so the saved
history shows it catching the fault first. An existing test changes only where
the repair's issue names it under `Under the hood`, with the reason. Any other
test that stands in the way is reported as wrong, never weakened, skipped or
deleted, and section-builder's bar guard runs before the repair is saved, with
the repair's issue as the piece. A repair with no issue yet gives the guard the
repair's report saved as the piece text, which names no test.

Once the regression test passes, it is the acceptance check that section-builder
breaks the repaired code against, without an offer, as the
`section-builder` skill's `references/test-strength.md` says. Keep the breakages to the repaired
code, and run each through the gate; do not run it again when section-builder
saves the repair.

## 7. Cleanup

Name every temporary log and harness added during the repair, remove each one,
then run the regression evidence without them. On Build and run it and Build
with care, run the trim in the `section-builder` skill's `references/trim.md`
on the repair, so the repair keeps only what the fix needed. Confirm the
original symptom is gone, write the cause in plain language into the repair's
file in `changes/`, as section-builder's step 9 describes, update the other
records, and use section-builder's save and review route for the change itself.
The repair's pull request merges only as the `section-builder` skill's
`references/merge.md` says, like any other. The report says which temporary
items were removed and that the evidence still passed.

Where the repair had an issue, its pull request's `Closes` line closes it once
the symptom is gone and the pull request merges, and the merge step's
`gate.py tidy` takes its state labels off. Its `type:bug` label stays, since it
says what kind of work it was, and a closed issue never reaches the board.

## At the limit

The loop stops on its own, and the gate takes the route, not the builder. A
repair has two routes back to shaping:

- Three failed fixes: the gate kicks the piece back to `shaping:research`, with the `causes` list of every attempt written into its `## Kickback` section in rank order, because the architecture is in question.
- A reproduction that cannot be built: back to `shaping:clarify`, where the
  person can give the steps, data, access or permission it needs. At the
  limit, the gate sends a repair whose reproduction was never shown failing at
  the start commit there too.

Both go through `python3 .agents/tools/gate.py result <number> <result file>`, which the run script calls, with `--at-limit` once the attempts or the time
are spent. Its `type:bug` label stays on it, because the fault is still there.
A rebuild is never the automatic fourth attempt. Rebuilding the area from the
masterplan, naming it as sensitive, or handing it to somebody else are choices
for the person in `/shape`, and the loop makes none of them.

### What counts as three

Count the fault surviving, not your own tally of the attempts you think should
count. The run script counts an attempt as failed when the gate ran its checks
and the fault was still there, whether or not each attempt was merged, deployed, or tried the way you
would have tried it. A person saying the fault is still there after three goes
has reached this point too. Whose code it was, and whether it ever shipped, are
facts about the work. What decides is that the fault is still there and the next
thing asked for is another go at it.

A builder may disagree with the count, and saying so in its result's
`concerns` can be the right thing to do. Correcting it does not postpone the
notice or the kickback, and is not a reason to wait for a cleaner three. In
`/shape`, say what you think actually happened and give the notice in the same
reply, because either way the person is relying on something that produces
wrong results and is asking for another patch on a cause nobody has
established. A correction on its own leaves them where the notice exists to
take them out of: told they are wrong, with nothing to decide.

### The notice

Declining the fourth attempt is what owes the notice, not the route chosen
after it. In the loop nobody is there to hear it, so the gate writes it into the same `## Kickback` section that declines, in the shape the
`setup-ai-build-kit` skill's `references/fit-check.md` sets out. It names who is
exposed, which here is whoever relies on the broken behaviour, and says they are
still relying on something that is producing wrong results. It says that another
attempt on a cause nobody has established can hide the fault rather than remove
it, and that somebody who knows that part of the tool would normally establish
the cause first. `/shape` reads that section first and passes the notice on in the same reply that declines another patch, its first reply on the piece.

Stopping here is a pause for the person to decide. The notice also says what
they can do, and if they carry on after it, the next attempt goes ahead on the
record: the acceptance is written in `/shape`'s clarify step, never in the loop, and the piece is shaped and built again.

Every route owes it, including the ones that sound like good news. Concluding
that the cause is established after all, that the requirement was unclear, or
that no testable boundary exists changes what happens next and changes nothing
about what the person is told. Three failed attempts is the least reliable moment
to trust your own conclusion that you finally understand the fault, and it is the
moment that conclusion is most tempting. So a builder at its third attempt never patches a fourth time on that conclusion. It ends the attempt, and the
kickback carries the notice. A refusal with no notice attached leaves the person
a refusal and no reason, which reads as the kit being difficult rather than as a
risk that is now theirs to decide about.

Not early and not late. Naming who is exposed earlier, as a general worry about
the bug, is not this notice and does not discharge it. Giving it after the
person has asked again for the work is too late, because by then they have
decided without it. It belongs in the reply that declines the fourth attempt,
which is the last moment it can still change what they choose.

Then hold that notice. Refusing the cost of a specialist, having no budget, and
asking for one more go are all reasons the person may decide differently, and
none of them is a reason the fault is now understood. Asking for one more go
after hearing the notice is the person carrying on, which is theirs to choose
in `/shape`.

### Nobody accepts in the loop

The loop never asks for an acceptance and never writes an `Accepted:` line. An acceptance already on the record stands. Where the person carried on after an earlier notice and the fault survives three more attempts, that record stays as
it was, and the kickback still happens, since nobody is present in the loop to carry on.

## Done when

The exact original symptom no longer occurs, the repeatable evidence passes,
temporary debugging changes are gone, the cause is recorded, and the
path-required save and review steps are complete.
