Your job: learn from the batch. The prompt lists, per merged issue, the fix
rounds, deviations and parks, and the titles of this pass's findings. Find what
had to change after the first attempt and why. Propose:

- lessons: a trap a later session would hit too, naming the check or AGENTS.md
  line that would prevent it (skip any already covered). Each becomes its own
  inbox issue for the person to approve. Do not append to any file;
- guardrails: a check or rule that would have caught the problem earlier (a
  lint rule, a size budget, an architecture test), as a titled finding.

End your reply with these blocks and nothing after them, `none` when empty:

LESSONS:
<title> | <the trap and the check or AGENTS.md line that would prevent it> |

GUARDRAILS:
<title> | <the check to add and the problem it would have caught> |
