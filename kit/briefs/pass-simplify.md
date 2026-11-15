Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Judge the loop branch against PLAN.md, decide, and report.

Write as the project does: follow its language and writing rules (AGENTS.md
and the product rules in PLAN.md) in everything you write. Read `## Lessons`
in PLAN.md first.

Hard rules, enforced by a hook: you edit no tracked file; no git push, merge,
checkout or switch; no gh; no recursive delete. Edit nothing: your only output
is your reply.

Your job: simplify and reconcile the whole batch, once, after all its pieces
are merged. The prompt gives the batch diff and, per merged issue, its build
note. Read the changed code as one piece and the notes as one list. Propose
concrete, behaviour-preserving changes:

- simplifications: duplicated logic across the pieces, dead code, needless
  nesting, names that differ for one idea, helpers that grew twice;
- reconciliations: deviations that contradict each other or PLAN.md,
  workarounds that can now be removed, follow-ups that overlap, and
  "not exercised" notes that should become a test or a manual check.

Each proposal names the files, says what changes and why behaviour stays the
same, and what test or check proves it. Skip taste, and skip anything that
changes behaviour: that is a defect or a decision, not a simplification.

End your reply with this block and nothing after it, `none` when empty:

SIMPLIFY:
<title> | <the concrete change, the files, and why behaviour stays the same> |
