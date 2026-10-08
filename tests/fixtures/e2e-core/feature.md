Add a greeting.

<!-- spec:start version=1 -->
Path: quick

## Goal
The greeting.py module has greet(name), returning Hello followed by the name.

## Expected flow
FL-1 The person greets Ada and sees Hello Ada.

## Edge cases
EC-1 When the name is empty, then the greeting is Hello friend.

## Changes to current behaviour
Added: A greeting names the person, or friend for an empty name. Docs: docs/README.md.

## Must stay the same
The scaffold test still passes.
Check: python3 -m pytest tests/test_scaffold.py -q

## Judge
Kind: acceptance tests, a single test
Command: python3 -m pytest tests/test_feature.py -q
Proves: FL-1, EC-1
Held-out cases: fingerprint {{HELD}}

## Links
Relies on: pytest
Touches: project-records
<!-- spec:end -->
