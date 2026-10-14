A user can rename a saved report.

<!-- spec:start version=1 -->
## Goal
A user can rename a saved report from its menu.

## User story
As a user, I want to rename a report, so that I can find it later.

## Expected flow
FL-1 The user opens the menu of a saved report.
FL-2 They choose "Rename" and type a new name.

## How to observe it
The report list shows the new name at once.

## Edge cases
EC-1 When the new name is empty, then the old name stays and a message says
"A name is needed".
EC-2 When the new name is "Q3 plan" and that name exists, then the user sees
"Q3 plan is taken".

## Limits
Names have at most 80 characters. Speed: none.

## Must stay the same
Opening a report still works (tests/reports.test.ts).

## Follow
The rename of folders in src/folders/rename.ts.

## Changes to current behaviour
Added: a "Rename" item in the report menu. Docs: docs/reports.md.
New area: report-menu

## Coverage
Permissions: only the owner can rename.
Data kept: the new name replaces the old name.
Errors: EC-1 and EC-2.
Empty states: not applicable, because a report always has a name.
What leaves the tool: nothing.

## Not in this piece
Bulk rename.

## Judge
Kind: acceptance tests, first commit 1a2b3c4 on the piece branch
Command: pytest tests/acceptance/test_rename.py
Proves: FL-1, FL-2, EC-1, EC-2
Fails today: 4 of 4 tests fail on their assertion; main at a1b2c3d;
5 October 2026 (written by the gate)

## Links
Relies on: PATCH /api/reports/:id in src/api/reports.ts
Touches: reports, menus

## Sensitive areas
None.

## Decisions
- Names are trimmed. Decided by the person, 1 October 2026.

## Research
- The folder rename uses the same rule. Source: src/folders/rename.ts.
  Checked 3 October 2026. Rests on: fingerprint 4c1e9a2.

## Open questions
None.
<!-- spec:end -->

## Needs (written by the gate; do not edit)
- Open question for the person: should a rename be undoable?
