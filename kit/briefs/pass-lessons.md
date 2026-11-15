Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. You may create new files under
`.lite/pass/` only.

Your job: learn from the batch. The prompt lists, per merged issue, the fix
rounds, deviations and parks, and the titles of this pass's findings. Find what
had to change after the first attempt and why. Propose:

- lessons: one line each, a trap a later session would hit too, short and
  specific, worth adding to `## Lessons` in PLAN.md (skip any already there);
- guardrails: a check or rule that would have caught the problem earlier (a
  lint rule, a size budget, an architecture test), as a titled finding.

End your reply with these blocks and nothing after them, `none` when empty:

LESSONS:
<one lesson per line>

GUARDRAILS:
<title> | <the check to add and the problem it would have caught> |
