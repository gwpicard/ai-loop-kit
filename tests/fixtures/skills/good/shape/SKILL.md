---
name: shape
description: Turns a rough idea into a piece with a spec the gate can check. Use when the person describes work to build and no spec exists yet.
---
# Shape
This fixture skill talks with the person about one piece of work. It leaves a spec on the issue, with a "Done when" section that somebody can check. It asks one question at a time and gives a recommended answer with each.

## Now
!`python3 kit/scripts/gate.py report --json --brief`
If the line above shows a disabled marker, run that command first.

## Stops
- Stop when the piece needs a decision that only the person can make. Tell the person which decision, and wait. Held by: the gate refuses a move to ready without a spec that passes the spec lint.
- Stop when a check fails twice. Show the output. Held by: `kit/scripts/spec.py` exits non-zero on a bad spec.

## Steps
1. Ask what the person wants, in one question with a labelled guess.
   Done when: the person has answered, or has said "you choose".
2. Write the spec from the answers.
   Done when: `python3 kit/scripts/spec.py lint` exits 0.
3. Show the spec and ask for a yes.
   Done when: the person has said yes in the conversation.

## Gotchas
- A short answer from the person is not a yes. Ask once more, with the guess written out.
- The first idea is often two pieces. Offer to split it, and let the person decide.

## When to read more
- Read `references/spec-shape.md` when the spec has more than three sections.
- Read `references/questions.md` before you ask a question that has no obvious guess.
