---
name: fix
description: Bring the tool back to doing what it already should. Use when the user says something is broken, failing, wrong, regressed, or not behaving as intended. Input is evidence, an error, a wrong output, a screenshot. Do not use for behaviour the masterplan never promised; that is build.
---

# Fix

You restore promised behaviour. The discipline is the order: never change
code before the problem repeats reliably and the cause is understood and
explained.

## 0. Check the report

When `/fix` arrives with no bug described, look for the repair already on the
board before asking the person to describe one. Refresh the printout with
`sh .agents/tools/plan-refresh.sh` and read its Broken group, the same open issues
labelled `broken` that `/what-now` surfaces first. Where the project has no copy
of the helper, the `setup-ai-build-kit` skill's `references/pieces.md` says what
to run instead. If none is labelled `broken`,
ask for the symptom, as step 1 sets out. If exactly one is, name it and use it as
the report. If more than one is, list them and ask which to take.

Read masterplan.md, build-path section first. If the behaviour being asked
for was never promised there, say so kindly and hand the request to `/shape`,
which shapes new work; a new wish treated as a repair ends up in the wrong
procedure. Nobody
can misfile work by picking the wrong command; catching that is this step's
whole job.

Only once the repair is confirmed as promised behaviour, and where it has an
issue, claim it before step 1, the way section-builder's step 1 claims a piece:
add `building` and take off whatever state it carried, in one step,
`gh issue edit <number> --add-label building --remove-label <its state>`,
creating the label first if the project lacks it. Where the issue carries no
state label, add `building` alone. Where GitHub cannot be reached, say so and do
not start on it, since a repair nobody could claim may be claimed by somebody
else. Where a claim was made and the request then turns out to belong to
`/shape`, move it back to the state it had in one step, so nothing is left in
`building` that nobody is building. The save then moves it on as
section-builder's step 8 says.

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
the Secrets rule says, and asks once when that is unknown.

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

Find one repeatable check that catches the exact symptom. Prefer, in order:
an existing failing test; a new focused automated test; a request or command
script; browser automation; replayed input; a small throwaway harness;
structured human-in-the-loop steps, when nothing else can reach the bug.

The user never needs to know which technique this was. The report states how
the bug is triggered, what result marks failure, how long the check takes,
and whether it's reliable.

When no loop can be built, stop and ask for the missing artifact, access, or
permission. Do not begin speculative patching without one.

## 3. Reproduce and minimise

Run the check, confirm it actually catches the user's bug, then remove
irrelevant steps or inputs one at a time until only the smallest case that
still fails remains.

## 4. Rank causes

List two to five plausible causes internally, each with a falsifiable
prediction. Show the list to the user only when their domain knowledge could
change the ranking; otherwise it stays internal.

When the person or changelog identifies a time the behaviour worked, use the
tight reproduction to bisect the saved history before testing the ranked
causes. Report the result as: "It broke in the change called <piece title> on
<date>." Do not bisect when there is no known-good point.

## 5. Test one cause at a time

Change one variable, and keep any temporary instrumentation targeted and clearly
labelled: name the file you write a temporary log to and read it back while
testing the cause, so the evidence sits somewhere you can point at rather than
scroll past. Reset to the last saved state after any failed attempt before trying
differently. Failed fixes never stack; stacked fixes are how clean projects rot.

## 6. Fix and lock it down

Create the regression evidence at the highest credible user-facing boundary,
watch it fail, apply the smallest fix that addresses the actual cause, watch
it pass, then rerun the original, unminimised case. When no credible
automated boundary exists, record that as a maintainability finding and use
the strongest manual or operational evidence available instead.

The checks-first and test rules in section-builder's step 4 apply to a repair
too. Commit the failing regression check on its own before the fix, so the saved
history shows it catching the fault first. An existing test changes only where
the repair's issue names it under `Under the hood`, with the reason. Any other
test that stands in the way is reported as wrong, never weakened, skipped or
deleted, and section-builder's test guard runs before the repair is saved, with
the repair's issue as the piece. A repair with no issue yet gives the guard the
repair's report saved as the piece text, which names no test.

On Build with care, where a runner exists for the project's language, offer
to check the regression test by breaking the repaired code on purpose. Follow
the `section-builder` skill's `references/test-strength.md` for this optional
check, its one-line report, and the misses listed on the repair's piece. Keep
the run to the repaired code and the regression test; do not offer it again
when section-builder saves the repair.

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

Where the repair had an issue, take the `broken` label off once the symptom is
gone. A repair that stays labelled broken keeps reporting a fault that no longer
exists, which is worse than never labelling it.

## Escalation

After three unsuccessful attempts, stop patching. Do not treat a rebuild as
the automatic fourth attempt; route by what the failures actually revealed,
one of:

- an unclear requirement goes back to clarify;
- missing access, environment, or artifact means stopping to ask for it;
- a clear requirement whose failing implementation the project owns and can
  see gets rebuilt from the masterplan;
- repeated failure in one technical area names that area as sensitive, with a
  look by somebody who does that work for a living as its caution;
- being unable to establish any testable boundary is a maintenance finding,
  not a fourth patch;
- a piece that has been rebuilt and still fails has hit a real limit, and that
  one area is worth handing over for somebody else to own.

### What counts as three

Count the fault surviving, not your own tally of the attempts you think should
count. A person saying the fault is still there after three goes has reached this
point, whether or not each attempt was merged, deployed, or tried the way you
would have tried it. Whose code it was, and whether it ever shipped, are facts
about the work. What decides is that the fault is still there and the next thing
asked for is another go at it.

You may disagree with the count, and saying so can be the right thing to do.
Correcting it does not postpone the notice and is not a reason to wait for a
cleaner three. Say what you think actually happened and give the notice in the
same reply, because either way the person is relying on something that produces
wrong results and is asking for another patch on a cause nobody has established.
A correction on its own leaves them where the notice exists to take them out of:
told they are wrong, with nothing to decide.

Naming an area as sensitive is a tightening, so it happens on your own
judgement without asking, and pressure to just fix it does not lift the flag or
turn it back into a rebuild. A component the project does not own or cannot see
is never the rebuild-from-the-masterplan route, however unreliable it looks.
Rebuilding it yourself takes on a new sensitive area rather than repairing a
known one, so it waits behind the notice below.

Declining the fourth attempt is what owes the notice, not the route you pick
after it. Give it in the same reply that declines, in the shape
the `setup-ai-build-kit` skill's `references/fit-check.md` sets out: name who is
exposed, which here is whoever relies on the broken behaviour, say they are still
relying on something that is producing wrong results, say that another attempt on
a cause nobody has established can hide the fault rather than remove it, and say
who would normally establish it first. Stopping here is a pause for the person to
decide. The notice also says what they can do, and if they carry on after it,
the next attempt goes ahead on the record.

Every route owes it, including the ones that sound like good news. Concluding
that the cause is established after all, that the requirement was unclear, or
that no testable boundary exists changes what happens next and changes nothing
about what the person is told. Three failed attempts is the least reliable moment
to trust your own conclusion that you finally understand the fault, and it is the
moment that conclusion is most tempting. A refusal with no notice attached leaves
the person a refusal and no reason, which reads as the kit being difficult rather
than as a risk that is now theirs to decide about.

Not early and not late. Naming who is exposed earlier in the conversation, as a
general worry about the bug, is not this notice and does not discharge it. Giving
it after the person has asked again for the work is too late, because by then
they have decided without it. It belongs in the reply that declines the fourth
attempt, which is the last moment it can still change what they choose.

Then hold that notice. Refusing the cost of a specialist, having no budget, and
asking for one more go are all reasons the person may decide differently, and
none of them is a reason the fault is now understood. Asking for one more go
after hearing the notice is the person carrying on, which is theirs to choose:
record the acceptance as below, then make the attempt.

Where the person does not carry on, move the repair's piece from `building` to
`parked` in one step,
`gh issue edit <number> --add-label parked --remove-label building`, with one
line on what the three attempts revealed and the route you chose. `broken` stays
on it, because the fault is still there.

### Before the next attempt

Another patch after three, or rebuilding the failing area yourself, is the same
decision whatever it is called, so it needs the same notice. Work through these
four in order. Do not start the work until all four are behind you.

1. **Name the risk yourself, before anything is built.** For a rebuild the
   notice covers the replacement rather than the fault: a replacement nobody
   who understands the original failure has looked at can fail the same silent
   way, and your own version passing its own tests is not evidence otherwise,
   because the thing that keeps breaking was never understood. Describing the
   fault accurately while saying nothing about what replaces it is the same
   failure as saying nothing.
2. **Give the notice once, in full, in one reply,** and let the person decide.
3. **Take carrying on as the acceptance.** Any instruction to go on with the
   work after the notice counts: "just rebuild it", "try it anyway", "patch it
   again". Silence does not, and neither does a question or an instruction
   given before the notice, or a form or menu answer with no option selected.
   Somebody who described the risk before you named it has still not been told
   by you, so name it yourself.
4. **Record the acceptance, then build.** The `Accepted:` line goes into the
   masterplan's build-path section before the replacement starts, with the date
   and the person's own words. Those are quoted exactly as typed, in quotation
   marks, and the line names only people the person named and says so when the
   answer was a selected option. Correct every masterplan sentence the
   acceptance makes untrue in the same save, such as one saying the area is
   still waiting for the caution, and name those sentences in one line.
   fit-check.md has the rest of these rules.

The order carries this. An acceptance collected once the replacement exists is
not an acceptance, it is a note about something that already happened.

Read the masterplan back before the replacement starts, and let the `Accepted:`
line being there decide whether it does. Where it is not there, the acceptance
was not recorded whatever was said in the conversation, and the work waits
until it is written. Doing the steps in order is what a run believes it did;
reading the line back is what tells it whether it did.

Carrying on after the notice is the acceptance, and the line quotes the
person's words after hearing who is exposed. Do not ask again for a cleaner yes.
Write the line, read it back and start the replacement in the reply that
answers them, and keep no lock that only waits for the skipped caution;
fit-check.md says why a further question is a stop.
Do not read an acceptance into a reply that does not ask for the work either:
silence, a question, or "I am not sure" leaves the work waiting and the notice
standing.

## Done when

The exact original symptom no longer occurs, the repeatable evidence passes,
temporary debugging changes are gone, the cause is recorded, and the
path-required save and review steps are complete.
