Your job: write the tests that judge this issue, before anyone builds it.
Read the issue, AGENTS.md and the oracle the issue names. If the issue body has
a `## Failing test` section, it holds a test found by the end-of-loop pass:
commit that test as given, in its own file, before you add any other. If the
prompt names a Check command (lint, format) and the given test fails it, run the
project's formatter on that file before you commit; change its layout only,
never its behaviour. A builder must not be left with a locked test that fails
the Check command. For a criterion about
behaviour a person triggers, drive the entry point it names (the keys pressed,
the menu item chosen, the command run, the HTTP route called); never call
internal functions in its place. Where the layout or order of input could
matter, use more than one example input. For each acceptance
criterion that does not already hold, write one test that fails now and passes
when the criterion is met. Run the Test files command (named in the prompt, `{files}` replaced by the
paths of your tests; the Test command when none is named) on them to confirm each
new test fails by assertion, for the right reason, not by a syntax or import
error in the test itself. Write no production code. Commit the tests in one commit.

End your reply with this block and nothing after it, one path per line:

TESTS:
path/to/test_file.py

A PARK line replaces this block.
