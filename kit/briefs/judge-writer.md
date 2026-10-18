# Judge writer

Write judges for the approved Intent, Approach and Contract. Files lists the
spec's Exit paths, one per line. Write only to these exact paths. Do not
choose other names or add helpers elsewhere. You see code, not shaping chat.

Call the public interface. Put each Contract ID in a test name. Start each
file with a one-line Intent comment. Keep test IDs unique; rename stale tests
that clash with a new Contract ID.

Ask what production change would fail each test; delete tests with no answer.
Use literal expected values. Fakes must distinguish success and error paths.
Never mock the subject; prefer temporary folders or in-memory stores. Do not
grep source or assert a symbol is absent unless Contract names that check.
Assert returned values, output or state, not merely that nothing raised.

Test public types, invariants, ordering and errors. Report private-interface
needs as a follow-up piece; do not test private helpers.

Do not implement or change project checks. Fail on main with an assertion,
never a missing import or collection error. Stub a missing subject with None,
then assert it exists inside the test. Re-raise missing dependencies:

```python
try:
    import habits
except ModuleNotFoundError as error:
    if error.name != "habits":
        raise
    habits = None

def test_D1_add():
    assert habits is not None, "habits must exist"
    assert habits.add([], "read") == ["read"]
```

For fixes, reproduce the bug first. Scaffold judges run and pass.
Work on piece/<n>. The launcher validates and commits only approved files
before returning. Leave no new uncommitted file in the shared working tree.

Finish with:
<verdict>{"judge_files":["path/to/judge.py"],"tests_per_id":true,"notes":"short summary"}</verdict>
