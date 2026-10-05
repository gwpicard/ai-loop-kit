# Check whether the tests notice

Once every acceptance check passes, break the code this piece changed on
purpose and see whether the acceptance checks notice. Do this without offering
first, on every build path, wherever StrykerJS or mutmut is already among the
project's dependencies. Never install a runner to do it. An acceptance check
that notices none of the breakages goes to the person's review; it never stops
the piece.

## The acceptance checks, once the build is green

Limit the deliberate breakages to code changed by this piece against its base.
In a repair, the regression test is the acceptance check, run against the
repaired code. Use the runner to find the breakages, then save each one as a
patch and run it through the gate, which applies it in a temporary worktree at
the commit the piece's branch holds and records the run:

    python3 .agents/tools/gate.py evidence <number> --breakage <patch> -- <acceptance check command>

Run each acceptance check against each breakage. Never apply a breakage to the
piece's own folder, and never leave deliberately broken code in the working
tree. Run locally, with no hosted service and no real records or live actions.

Before the piece moves to review, the gate reads those runs on the current
commit. An acceptance check that failed on none of them is written to
`forced.jsonl` as a `weak_check`, and the piece waits for the person. Where the
project has a runner and no breakage is recorded on the current commit, the gate
refuses the move and names the command to run. A new commit needs its own
breakages. Where the project has neither runner, the gate writes one line saying
the checks were not tested by breaking the code, and nothing is forced.

## The optional run on other code

The person may also want to know whether the project's other tests notice a
breakage of the changed code. This run is offered only on Build with care, and
only where a local runner exists for the project's language. Say: "I can break
the changed code on purpose to check the tests notice." It is optional
evidence. A declined or unavailable run does not hold up the piece, and no
result from it becomes an automatic gate. Existing required checks and
sensitive-area cautions still apply. Run it only if the person accepts the
offer, and never across the whole project.

## Under the hood

Mutation testing means changing code deliberately and checking whether tests
fail. Use StrykerJS in incremental mode for JavaScript or TypeScript, with
`--mutate` restricted to the changed files or lines. Incremental mode alone
does not set that scope: its report can retain older results for other code.
For Python, use mutmut with targets restricted to the changed functions and
the relevant tests selected. Read the installed runner's guidance before
choosing its options. Where no suitable runner exists, leave this evidence
out rather than inventing a runner or requiring a service.

Take counts only from valid breakages in this run's changed scope. Count a
breakage as caught only when a test fails because of it. List crashes,
timeouts and invalid changes separately as unchecked; do not count them as
caught. If the run cannot complete, say what was left unchecked rather than
presenting a complete result. Keep runner names and the word "mutation" out
of the person's report.

## What the person sees

Use this fixed one-line shape, replacing the counts with the observed results:

"The tests were checked by breaking the code on purpose <tried> times. They
caught <caught>. The <missed> they missed are listed on the piece."

Use the right singular form for one miss. With no misses, end with "They
missed none." For example: "The tests were checked by breaking the code on
purpose 40 times. They caught 37. The three they missed are listed on the piece."

List each miss on the piece in plain words: what changed, what the tests let
through, and which promised behaviour that could affect. Compare its location
with the area map: run `python3 .agents/tools/area-map.py which <path>`, and a
miss in an area whose `sensitive:` line names a sensitive area is inside that
area. A miss inside a named sensitive area
goes under "Worth stopping for", with the area named; a miss elsewhere goes
under "Worth knowing". Explain a change with no observable effect as such.
The person decides whether a miss matters and whether to strengthen the
evidence before saving; record that choice on the piece.

Never write a test only to raise the count. Add or improve a test only when
it protects promised behaviour, and show that it catches the relevant
breakage. A higher count does not prove the software is correct. After the
check, confirm the working code is intact and rerun the ordinary tests before
saving.
