Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Leave nothing running that outlives your session: prefer foreground runs and
`docker run --rm`, and stop whatever you start.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. You may create new files under
`.lite/pass/` only.

Your job: attack one surface of the project, named in the prompt, on the loop
branch, as a hostile but realistic user would: odd inputs, missing files,
interrupted runs, repeated runs, wrong order. Use the real thing, not mocks.

A finding counts only with a failing test. For each defect, write one new
test file named for the defect, in the style of the project's tests, under
`.lite/pass/` at the path where it belongs in the project: for example
`.lite/pass/tests/test_bom.py` belongs at `tests/test_bom.py`. The pass copies
it there (the path must not exist yet) and runs the project's Test command, so
the file must be one that command finds at that path. It must fail now, for
the reason you name (an assertion, not a syntax or import error), and pass
once the defect is fixed. Run it to see it fail; the hook may stop you
copying it into the project, in which case run it from `.lite/pass/`.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <what is wrong and how the test shows it> | .lite/pass/<where it belongs>
