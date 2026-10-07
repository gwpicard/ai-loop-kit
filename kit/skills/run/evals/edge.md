# Case: edge

Run by hand with the real model, as `normal.md` says.

## Setup

A throwaway project that passed the first half of `/setup`. No piece is in the ready
state. One piece is in shaping, and one is done. The person types:

> /run

## Expect

1. The skill reads the gate's report and sees no ready piece.
2. It says so in one line, and names the next step: shape a piece with `/shape`.
3. It asks neither question.
4. It does not run the pre-run check, and it does not start the run script.
5. It changes no file and no state.

## Fail if

- the run script is started, even to find out that nothing is ready;
- the reply is longer than a few lines, or lists every piece;
- the skill moves the piece in shaping to ready, or reaches for `/shape` itself.
