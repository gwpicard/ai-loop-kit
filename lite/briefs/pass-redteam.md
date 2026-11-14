Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. You may create new files under
`.lite/pass/` only.

Your job: attack one surface of the project, named in the prompt, on the loop
branch, as a hostile but realistic user would: odd inputs, missing files,
interrupted runs, repeated runs, wrong order. Use the real thing, not mocks.

A finding counts only with a failing test. For each defect, write one test
file under `.lite/pass/` (a new file, named for the defect) in the style of
the project's tests, so that the project's Test command runs it when the file
is copied to the same path. It must fail now, for the reason you name, and
pass once the defect is fixed. Run it to see it fail.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <what is wrong and how the test shows it> | .lite/pass/<file>
