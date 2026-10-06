# Case: normal

Scenario evals need the real model, so `tests/run-all.sh` does not run them. Run this
case by hand after a change to the skill or the model. Judge it from the session log and
the final state of the fixture project.

## Setup

A throwaway project with the stand-in GitHub and the stand-in App, one area in the area
map (`billing`), a test runner, and no piece yet. The person types one line:

> Let people export their invoices as a CSV file.

The person answers every question by accepting the recommended answer.

## Expect

1. The skill searches for a duplicate first (`find-duplicates.py`), finds none, and says so.
2. It calls `gate.py capture` with the person's own words as the title. It does not
   reword the title.
3. It asks its questions in one batch. The batch holds five questions at most (the
   `question_cap` in the policy file). Each question says why it matters and carries a
   recommended answer.
4. It writes each answer into the spec block. It does not settle a need that names the
   person by itself.
5. It stores the held-out cases with `python3 -m loop.heldout store`. Only the
   fingerprint that the command prints appears in the spec, in `Held-out cases:`. No
   case text appears in the issue, in a commit or in a tracked file.
6. It fills `Touches:` from the area map and `co-change.sh`.
7. `spec.py lint` runs and passes before `gate.py move <n> ready` is called. The ready
   move is called once, and only after the lint passed.
8. If the ready gate refuses, the skill reads the `next:` line, reports it plainly and
   does not try another route to the same result.

## Fail if

- the ready move is called before `spec.py lint` exits 0;
- a held-out case text is found anywhere in git or in the issue body;
- the batch holds more than five questions;
- a question has no recommended answer or no reason.
