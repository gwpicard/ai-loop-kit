Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. You may create new files under
`.lite/pass/` only.

Your job: the rubric review of the batch. The prompt gives the batch diff command.
Check the changed code for: readability a new reader can follow; errors that
are swallowed or reach the person as a traceback; tests that only restate
constants or the code; fixed sleeps and other timing guesses; dead code and
unused names. Give `file:line` evidence in every finding.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <file:line and what is wrong> |
