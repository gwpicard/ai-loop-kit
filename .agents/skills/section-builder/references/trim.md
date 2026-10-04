# The trim

Before a piece is handed over, take out what the change added that its
behaviour does not need. A wrapper with one user passes every test, and so
does an export nothing calls, and each is harder to remove once later work
starts using it. The trim finds them while they are still free to remove.

## Where it applies

Every build on Build and run it and on Build with care, including a repair
that /fix saves. Not on Explore privately, where the work is thrown away.

It runs once, after the tests, the type check and the linter pass and before
the walk-through, or the person's try when they opt in, so the piece is judged
as it will be saved.

## What it looks at

Only what this change added or changed: the difference between the working
tree and the commit the piece started from. Code the change did not touch is
out of scope, even when it is plainly wasteful. The quarterly visit owns that.
Unused imports and unused local names are also out of scope, because the
linter already reports them.

## The list

Each finding names a file and a line the change added or changed.

1. Unused. A function, class, export, file or dependency the change added that
   nothing uses. The trim removes it.
2. One value. A parameter, setting or flag the change added that no caller
   sets, or that every caller sets to the same value. The trim removes it, or
   puts the one value where the option was read.
3. One user. A wrapper the change added that exactly one place uses, where a
   wrapper is a function whose body is a single line handing its work to
   something else. Or an interface or base class the change added with exactly
   one implementation. The trim folds it into that place: its body goes where
   it was used, and the original is removed. A function with real work of its
   own is not a wrapper, however few places use it. Naming a step is often
   what makes code readable.
4. A dependency the change added for a single use. Reported only.
5. A block the change added that closely matches code already in the project.
   Reported only.
6. A function the change added or changed that is over the limit below.
   Reported only.

Leave alone anything the piece exists to provide, such as a function other
projects are meant to call, or a page, route or command a person uses. Nothing
inside the project uses those, and that is correct.

## What the trim may change

Two kinds of edit, and no others: removing, and folding. Folding means moving a
one-user item into its one user, or putting an option's one value where the
option was read, and then removing the original.

The trim never renames, splits, extracts, reorders, restyles or adds code. It
never changes a test or the data a test reads. An improvement that needs any
other kind of edit becomes a report on the piece, however clear the
improvement is.

That rule is why the tests can be trusted here. A pass allowed to reshape code
until the tests stop passing learns to delete what the tests do not cover, and
every step looks green. The trim works through a fixed list instead, and the
tests only confirm that nothing broke on the way.

## The pass

1. Commit the piece as built, so the trim sits in its own commit after it.
2. Gather the findings with the engines below, and keep only those on lines
   this change added or changed.
3. Look at each finding a second time. Search the whole project for the name.
   Code can be reached by a name built at run time, a framework convention or
   a configuration file, and no engine sees those. Drop an unused finding whose
   name turns up anywhere outside its own definition. Drop a one-user finding
   whose name turns up in more than one place outside its definition.
4. Before a fold, use `section-builder/references/reach-check.md` to find the
   existing tests that run the code being folded. When none do, report the
   fold rather than applying it.
5. Apply each removal or fold on its own, then run the tests the reach check
   names, the type check and the linter. When any of them fails, undo that
   edit and record it on the piece as a wrong call. Never change a test to
   keep an edit.
6. Run the list once more over the result. Apply nothing it finds; list it on
   the piece. The trim runs once and stops.
7. Run the whole test suite, then commit the trim on its own. When nothing was
   changed, there is no commit.

A person who wants something back undoes that one commit, and the piece they
confirmed is untouched.

## Engines, best first

| What | JavaScript and TypeScript | Python | Any other language |
|---|---|---|---|
| Unused code | `knip --include files,exports --reporter json` | `vulture --min-confidence 60 .` | read the code directly |
| Unused dependencies | `knip --include dependencies --reporter json` | `deptry .` | read the code directly |
| Uses of a name | the order in `section-builder/references/reach-check.md` | the same | the same |
| Copied code | `jscpd --ignore-identifiers --reporters json --output <temporary folder> .` | the same | the same |
| Function limit | `lizard --CCN 15 --csv <changed files>` | the same | the same, where lizard reads the language |

The last resort for every row is reading the changed code directly. Say in the
internal evidence which engine was used, and when it was the fallback.

Where an engine is not already in the project, `npx` or `pipx run` can fetch it
for this build without adding it to the project. Ask once, the first time the
trim needs it, and write the answer into AGENTS.md's stack section so later
builds do not ask again. If the person says no, use the next entry.

`vulture` runs at 60 here, lower than the quarterly read, because at 100 it
names no unused function at all. That is safe only because every finding is
limited to this change, looked at a second time, and followed by the tests.

`jscpd` writes a report folder. Point it at a temporary folder outside the
project, made with `mktemp -d`, so nothing is saved. Leave it there for the
computer to clear, since a recursive delete is refused.

## The function limit

A function is over the limit when its cyclomatic complexity, a count of the
separate paths through it, is above 15. That is lizard's documented default
warning. The yardstick is published practice from outside the project. It is
never a number the kit invents, and never the project's own average, which
would treat a project that is already hard to follow as normal.

Length and parameter limits are left out until each has a published source
worth naming. lizard's own default length limit is 1,000 lines, which is too
loose to mean anything.

The limit applies to every function the change added or changed. A changed
function already over the limit is reported only when the change raised its
count. Run lizard on the same file at the commit the piece started from to
compare. The trim never splits a function to bring it under the limit, since
splitting is a restructure.

## What the person sees

When the trim changed nothing and has nothing to report, say nothing.

Otherwise, at hand-over, one line from this fixed shape:

"I took out <count> things this change did not need. They are listed on the
piece."

Use "one thing" for a single removal. When there is also something only
reported, add "<count> more could be simpler, and are listed there too." When
there is only something reported, say "<count> things in this change could be
simpler. They are listed on the piece."

On the piece, list each item in plain words: what was taken out or folded and
why nothing needed it, each wrong call that was undone, and each report. Name a
function over the limit as harder to follow than the usual limit, as in "The
new invoice total is harder to follow than the usual limit." Never show a
function's path count or any other score. Keep engine names out of what the
person reads.
