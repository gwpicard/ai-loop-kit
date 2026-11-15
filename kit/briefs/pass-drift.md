Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. You may create new files under
`.lite/pass/` only.

Your job: the drift review of the batch. The prompt gives the batch diff command.
Read the diff and PLAN.md, then check: decisions in PLAN.md still hold; budgets
and size limits are met; the same logic is not written twice across issues;
docs and comments describe what the code now does; the lessons in PLAN.md
are still true.

Report only real problems with evidence; do not report taste. One finding per
line, each as `<short title> | <what is wrong and the evidence> | <path>`;
leave the path empty unless the task asks for one. End your reply with this
block and nothing after it, writing `none` when there is nothing:

FINDINGS:
<title> | <evidence> |

If PLAN.md has no bullet lines under `## Surfaces`, also end with a block
`SURFACES:` of at most four parts of the project a red team should attack,
one per line (a command, an input format, a screen).
