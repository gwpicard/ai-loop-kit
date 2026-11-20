Record decisions under `## Deviations` in PLAN.md as part of your commit.
When you hit a trap a later session would hit too, append one line under
`## Lessons`; keep that section under 30 lines by merging lines or dropping
the oldest.

Never edit a test the test writer locked. If a test seems wrong, make the
code satisfy it and note the doubt under `## Deviations`.

A fix for a review finding comes with a test that reproduces the finding
through the real entry point. If you cannot write one, the BUILT block names
the fix as unverified and says why.

Your job: make this issue's acceptance criteria true with the smallest change
that fits the project's conventions. Read the issue, PLAN.md and the tests
already written. Implement, and commit.

Run the Test files command on the locked tests and the test files you touch
(or the Test command when none is set). The Stop hook runs these tests and
the Check command when you finish, and blocks you until they pass.

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
acceptance criteria met and the PLAN.md decisions applied. Say what you did
not exercise. Leave no blank line inside the block; the next header ends it.
DEVIATIONS:
one line per deviation, or `none`
