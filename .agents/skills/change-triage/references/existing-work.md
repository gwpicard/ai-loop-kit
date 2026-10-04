# Existing work

Use when the open question is whether something already exists that could do the
job. A question about one external fact runs source-check.md instead.

## Where to look, in order

1. the project itself, because the nearest thing to what is wanted is often
   already here under another name;
2. what the project already depends on, since a capability already paid for
   costs nothing more to use;
3. the language or framework's own standard parts;
4. a well-established package that many projects rely on;
5. an official example or template from the provider.

Stop at the first level that answers the question. A new dependency is the last
resort rather than the first search.

## What to check before naming a candidate

- Is it maintained? Recent releases and answered questions, rather than a
  promising name and three years of silence.
- What does its licence allow? Say plainly where one would restrict how this
  project can be used, shared, or sold.
- What does it cost? Money, an account somebody has to own, or a free limit that
  bites later.
- Where does the data go? Anything that sends the project's data elsewhere is a
  product decision for the person, not a technical one.
- How hard is it to remove? Something that touches every part of the project is
  a bigger commitment than something sitting behind one seam.

Confirm each of those from the provider's own pages rather than from memory.
Where the question narrows to a single fact, that is source-check.md's job.

## What to record on the piece

At most three candidates, which one is recommended, and why. On the surface, in
plain words: what it lets the person do, what it costs, whether anything leaves
the project, and what changing it later would take. The technical detail goes
under the hood.

Record the date checked, and what was rejected and why, so the next session does
not search the same ground again.

## What this never does

- It never installs, adds, or configures anything. Planning records and stops.
- It never recommends something that costs money or needs an account without
  saying so in the same breath.
- It never settles how something should look or behave. That is the decision
  prototype.
- It never claims a capability it has not read on the provider's own pages.
