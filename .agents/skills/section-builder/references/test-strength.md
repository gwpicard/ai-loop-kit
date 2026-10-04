# Check whether the tests notice

This check is offered only on Build with care, and only where a local runner
exists for the project's language. Say: "I can break the changed code on
purpose to check the tests notice." It is optional evidence. A declined or
unavailable check does not hold up the piece, and no result from it becomes
an automatic gate. Existing required checks and sensitive-area cautions still
apply.

After the ordinary tests pass, run the check only if the person accepts the
offer. Limit the deliberate breakages to code changed by this piece. In a
repair, use the regression test against the repaired code. Run locally in a
disposable copy, with no hosted service and no real records or live actions.
Never run it across the whole project or leave deliberately broken code in
the working tree.

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
with the masterplan's sensitive-area map. A miss inside a named sensitive area
goes under "Worth stopping for", with the area named; a miss elsewhere goes
under "Worth knowing". Explain a change with no observable effect as such.
The person decides whether a miss matters and whether to strengthen the
evidence before saving; record that choice on the piece.

Never write a test only to raise the count. Add or improve a test only when
it protects promised behaviour, and show that it catches the relevant
breakage. A higher count does not prove the software is correct. After the
check, confirm the working code is intact and rerun the ordinary tests before
saving.
