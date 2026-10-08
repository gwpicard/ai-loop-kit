Handle an empty list in the sample total.

<!-- spec:start version=1 -->
Path: quick

## Goal
The bug.py module's total(items) returns zero for an empty list.

## Expected flow
FL-1 The person totals an empty list and sees zero.

## Edge cases
EC-1 When the list is [2, 3], then the total is 5.

## Changes to current behaviour
Changed: An empty list totals zero, while non-empty lists keep their sum. Docs: docs/README.md.

## Must stay the same
The scaffold test still passes.
Check: python3 -m pytest tests/test_scaffold.py -q

## Judge
Kind: reproducing test, a single test
Command: python3 -m pytest tests/test_bug.py -q
Proves: FL-1, EC-1
Held-out cases: fingerprint {{HELD}}

## Links
Relies on: pytest
Touches: project-records
<!-- spec:end -->
