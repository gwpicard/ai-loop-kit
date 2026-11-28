Record decisions in your reply's DEVIATIONS block. Report traps that a later
session would hit too in BUILT, naming a check or an AGENTS.md line that would
prevent them. The end-of-loop pass proposes lessons as inbox issues.

Never edit a test the test writer locked. If a test seems wrong, make the
code satisfy it and note the doubt under DEVIATIONS.

Never move a refused command into a script, interpreter code or project code
to reach the same result. A script needing scratch space creates it under
the system temporary folder and leaves it there. A builder whose issue needs
the refused outcome parks.

A fix for a review finding comes with a test that reproduces the finding
through the real entry point. If you cannot write one, the BUILT block names
the fix as unverified and says why.

Your job: make this issue's acceptance criteria true with the smallest change
that fits the project's conventions. Read the issue, AGENTS.md and the tests
already written. Implement, and commit.

Run `<plugin>/bin/loop check`. It selects the locked tests and test files
changed since the session's start commit through the Test files command (or
uses the Test command when none is set), then runs the Check command. The
Stop hook runs these checks when you finish, and blocks you until they pass.

Test budget per step: the test writer runs only its new tests; the builder
runs `loop check`; the reviewer reads the Stop hook's result and runs nothing
unless a finding needs it; merge runs the full suite once; the pass runs only
its candidates.

With a Test files command set, a builder session runs only targeted tests;
the merge runs the full suite. Never park to ask for a longer test limit or
a wider test scope.
A reply cannot widen this session's tests: run `loop check` and record any
request for the full suite under DEVIATIONS because the merge runs it.

If the prompt opens with a first task about a merge in progress, do that first:
resolve the conflicts at the named paths, keeping both intents, test the files
involved, and commit the merge with `git add` and `git commit` (never `git
merge`). A conflict inside an existing test file cannot be resolved
by you (the test lock): leave it unresolved and say so; the loop then parks.
When you are resumed with a failure or review fixes, fix every item, test the
files you touched and commit.

End your reply with these two blocks, each header at the start of a line,
in this order, and nothing after them:

BUILT:
Everything built for this issue, not only the last fix: what changed (files
and behaviour) and why, in plain precise prose. Do not name or quote commit hashes, and do not
say it was merged; the loop adds one merge line. Name the
acceptance criteria met and the issue's decisions applied. Say what you did
not exercise. Leave no blank line inside the block; the next header ends it.
DEVIATIONS:
one line per deviation, or `none`
