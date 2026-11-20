Your job: attack one surface of the project, named in the prompt, on the loop
branch, as a hostile but realistic user would: odd inputs, missing files,
interrupted runs, repeated runs, wrong order. Use the real thing, not mocks.

A finding counts only with a failing test. For each defect, write one new
test file named for the defect, in the style of the project's tests, under
`.loop/pass/` at the path where it belongs in the project: for example
`.loop/pass/tests/test_bom.py` belongs at `tests/test_bom.py`. The pass copies
it there (the path must not exist yet) and runs the project's Test files
command (the Test command when none is set), so the file must be one that
command finds at that path. It must fail now, for the reason you name (an
assertion, not a syntax or import error), and pass once the defect is fixed.

Run your new tests with the Test files command, replacing `{files}` with
their paths; use the Test command when none is set. The hook may stop you
copying them into the project, in which case run them from `.loop/pass/`.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <what is wrong and how the test shows it> | .loop/pass/<where it belongs>
