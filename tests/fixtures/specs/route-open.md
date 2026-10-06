Make the search page faster.

<!-- spec:start version=1 -->
## Goal
The search page answers in under 300 ms for most users.

## User story
As a user, I want quick search, so that I keep my train of thought.

## Expected flow
FL-1 The user types a query and presses Enter.

## How to observe it
Results show in under 300 ms.

## Edge cases
EC-1 When the query is empty, then no request is sent.

## Limits
The 95th percentile is under 300 ms.

## Must stay the same
Search results keep their order (tests/search-order.test.ts).

## Follow
The index code in src/search/index.ts.

## Changes to current behaviour
Changed: the search answers faster. Docs: docs/search.md.

## Coverage
Permissions: none new. Data kept: none. Errors: a timeout shows a message.
Empty states: EC-1. What leaves the tool: the query, as today.

## Judge
Kind: measurement, metric p95 latency
Command: npm run bench:search
Route: open
Hypotheses: add an index; cache the last query
Held-out cases: fingerprint 77aa11b (stored outside git; gate only)

## Links
Relies on: src/search/index.ts
Touches: search
<!-- spec:end -->
