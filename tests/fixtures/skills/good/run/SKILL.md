---
name: run
description: Starts a run that builds the ready pieces. The person starts it by hand.
disable-model-invocation: true
---
# Run
This fixture skill starts the run script and reports what it does.

## Now
!`python3 kit/scripts/gate.py report --json --brief`
If the line above shows a disabled marker, run that command by hand first.

## Stops
- Stop when the pre-run check refuses. Show each refusal. Held by: `kit/scripts/pre-run-check.py` exits 3 and the run script calls it first.

## Steps
1. Run the pre-run check.
   Done when: it exits 0.
2. Start the run script.
   Done when: it prints the run name.

## Gotchas
- A run that finds no ready pieces is not a fault. Say so and stop.
