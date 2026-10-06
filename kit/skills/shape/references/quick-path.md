# The quick path

A small change takes lighter required fields. The format is in `kit/spec-format.md`, and the gate checks the limits.

## When it fits

All of these hold.

- It is one piece, and it touches one area.
- It holds no sensitive area.
- It adds no new dependency.
- Its judge is one test.

A small bug usually fits. There is no separate bug path.

## What to write

Start the spec block with the line `Path: quick`, before the first heading. Then write only these fields: Goal, Expected flow, Edge cases, Must stay the same, Judge and Links.

Each flow step and each edge case still has an ID. Must stay the same still needs a `Check:` line with a command that passes on `main`.

## When it stops fitting

If the answers show a second area, a sensitive area, a new dependency or a judge that needs more than one test, remove the `Path: quick` line and take the full path. Tell the person why in one sentence. The gate refuses a quick piece that breaks a limit, and its `next:` line says so.

## Capture on the quick path

The steps stay the same: search for a duplicate, capture in the person's words, settle the biggest need, lint, ask for ready. Only the list of needs is shorter.
