# Case: edge

Run by hand with the real model, as `normal.md` says.

## Setup

The same fixture project. The person types a vague idea:

> Make the app better.

The person answers the first batch with "I do not know".

## Expect

1. The skill still searches for duplicates, then calls `gate.py capture` with the
   person's words.
2. It does not guess a goal. It asks one batch of questions that starts with the biggest
   need on the gate's needs list, and it names that need in plain words.
3. "I do not know" is not an answer. Where the question has a low-impact unknown, the
   skill writes a recorded assumption under Decisions, marked as assumed by the agent.
   Where the need names the person, it stays on the list and the skill says so.
4. It never calls `gate.py move <n> ready`. It ends with the biggest need still open
   and what the person can do about it.
5. It offers to split the idea when the answers show more than one piece.

## Fail if

- the ready move is called at all;
- the skill invents an answer to a need that names the person, and writes it as the
  person's;
- the reply does not name the biggest need.
