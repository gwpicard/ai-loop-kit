# Structure read

Once a quarter, compare how the project's parts depend on each other now with
how they did at the last full visit, and name the few places the structure got
worse. Usually nothing did, and then there is nothing to say.

`section-builder` already makes this comparison for one change. This read makes
the same comparison across the whole project and a whole quarter.

This is a whole-project read, so the rules in
the `setup-ai-build-kit` skill's `references/whole-project-reads.md` apply.

## Where it applies

At the quarterly visit, on Build and run it and on Build with care. Not on
Explore privately.

## Engines, best first

1. `depcruise --no-config --output-type json <source folder>`, from
   dependency-cruiser, for JavaScript and TypeScript.
2. `madge --circular --json <source folder>`, for JavaScript and TypeScript.
3. Read the imports directly, limited to the areas the quarterly spread count
   named, and say in the internal evidence that this was the fallback.

Where an engine is not already in the project, ask once before fetching it with
`npx` for this visit. Use the same engine for both sides of the comparison.

## The earlier state

Save nothing. The earlier state is derived again, every time, from the project
as it was at the last full visit:

1. Read the `last-full-pass` date from `.ai-build-kit-maintenance`. Where there
   is none, this is the first full visit, so use the project's first commit.
2. Find the last commit on or before that date with
   `git rev-list -1 --before="<date> 23:59:59" HEAD`.
3. Copy the project as it was at that commit into a new temporary folder
   outside the project, made with `mktemp -d`, with
   `git archive <commit> | tar -x -C <temporary folder>`. This only reads the
   saved history. It changes nothing in the project.
4. Run the same engine on that copy. Leave the folder for the computer to
   clear, since a recursive delete is refused.

If the engine cannot read the earlier copy, say one line: "The structure
comparison did not happen, because the project as it was at the last visit
could not be read." Then carry on with the rest of the visit.

## What counts as worse

A loop that is there now and was not there before: two or more parts that
depend on each other in a circle, so a change to one can break the other and
neither can be tested alone. Compare the loops as sets of files, so a loop that
only moved to a different starting file is not new.

A loop that was already there at the last visit is not news this quarter. Say
nothing about it unless the person asks.

For each new loop, find the line in each file where it imports the next one.
Those lines are the finding's real place.

## Reliability

This read cannot tell whether the tool is reliable, and neither can any other
read here. That needs the tool running under real failures. If a search of the
code finds an outside call written with no time limit or no retry, say it as a
missing pattern at a named place: "`src/billing.js` at line 12 calls the
payment service with no time limit set." Never say the tool is unreliable, and
never say it is reliable.

## Saying it

A new loop joins the other hot-spot inputs, and the cap of three proposals
holds for all of them together. Rank a loop higher when it sits in an area the
spread count or a repeated bug already named. Say it in plain words:

"Since the last visit, `src/orders.js` and `src/invoices.js` have started to
depend on each other, at line 3 and line 1. A change to either can now break
the other."

When nothing got worse, say nothing about structure. That is the ordinary
result and it is complete.
