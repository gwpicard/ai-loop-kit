---
name: what-now
description: Shows where the project stands and suggests the next piece. Use when the person asks what to do next, or opens a session with nothing in hand.
---
# What now
This fixture skill reads the gate's report and says what comes next, in at most three lines.

## Now
!`python3 kit/scripts/gate.py report --json --brief`
If the line above shows a disabled marker, run that command by hand first.

## Stops
- Stop when the report cannot be read. Tell the person which command failed. Held by: `kit/scripts/gate.py` exits non-zero when it cannot read the project.

## Steps
1. Read the report above.
   Done when: you can name the pieces by state.
2. Say the next piece in one sentence.
   Done when: the person has seen it.

## Gotchas
- An empty report means no pieces yet. Suggest shaping one.
