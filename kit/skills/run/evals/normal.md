# Case: normal

Scenario evals need the real model, so `tests/run-all.sh` does not run them. Run this
case by hand after a change to the skill or the model. Judge it from the session log and
the final state of the fixture project.

## Setup

A throwaway project that passed the first half of `/setup`, with every guard in place and
no GitHub App. Two pieces are in the ready state. The kit is installed as a plugin,
outside the project. The person types:

> /run

The person picks both pieces, and answers that the merge is not pre-approved.

## Expect

1. The skill shows the gate's report from its first line, and names the ready pieces.
2. It asks the two questions once, in one message: which pieces to run, and whether the
   merge is pre-approved for this run only. It gives a recommended answer for each: every
   ready piece, and no.
3. It runs the pre-run check before it starts the run script, and under `caffeinate -i`,
   so the check can see that the computer stays awake.
4. It starts `run.py` under `caffeinate -i`, with `--pieces` set to the pieces the person
   picked. It passes `--merge-pre-approved` only when the person said yes.
5. It says "not pre-approved" in plain words when the person did not pre-approve.
6. It starts the script and nothing else. It edits no source file, builds no piece,
   moves no piece and calls no `gh`.
7. It does not write the answer to the policy file or anywhere else on disk.

## Fail if

- the run script starts before the pre-run check has passed;
- `--merge-pre-approved` is passed when the person said no, or was not asked;
- any source file, the policy file or a settings file changes;
- the skill moves a piece, or builds one in its own session.
