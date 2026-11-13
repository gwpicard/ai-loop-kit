Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. When a choice is open, decide it from PLAN.md, take the
closest approach that keeps its rules, and record the decision under
`## Deviations` in PLAN.md. If the work needs a decision only the person can
make (money, credentials, permissions, settings, irreversible data, going
public, new dependencies, a protected path), do not guess: end your reply with
one line `PARK: <question> | <recommended answer>` and stop.

Hard rules, enforced by a hook: no git push, merge, checkout or switch; no gh;
no recursive delete; no secrets; do not edit an existing test file. You may
create new test files.

Your job: write the tests that judge this issue, before anyone builds it.
Read the issue, PLAN.md and the oracle the issue names. For each acceptance
criterion that does not already hold, write one test that fails now and passes
when the criterion is met. Run the Test command to confirm each new test fails
for the right reason. Write no production code. Commit the tests in one commit.

End your reply with this block and nothing after it, one path per line:

TESTS:
path/to/test_file.py
