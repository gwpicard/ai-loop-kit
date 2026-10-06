An accountant can download one month of invoices as a single CSV file.

<!-- spec:start version=1 -->
## Goal
An accountant can download every invoice from one month as one CSV file,
ready to import into the books.

## User story
As the accountant, I want one file per month, so that I can import a month
in one step.

## Expected flow
FL-1 The accountant opens Invoices and picks a month.
FL-2 They choose "Export CSV".
FL-3 The browser downloads invoices-2026-09.csv.

## How to observe it
The file has a header line and one row per invoice dated in that month.

## Edge cases
EC-1 When the month has no invoices, then the file holds the header line only.
EC-2 When an invoice is a credit note of 40.00, then its row shows -40.00.

## Limits
A month of 5,000 invoices downloads in under 10 seconds.

## Must stay the same
The single-invoice PDF download still works (tests/invoice-pdf.test.ts).

## Follow
The existing receipts export in src/export/receipts.ts.

## Changes to current behaviour
Added: an "Export CSV" button on Invoices. Docs: docs/invoices.md.

## Coverage
Permissions: only accountants see the button. Data kept: none new.
Errors: a failed export shows a message and keeps the page.
Empty states: EC-1. What leaves the tool: the downloaded file only.

## Not in this piece
PDF export. Scheduled exports.

## Judge
Kind: acceptance tests, first commit 9f8e7d6 on the piece branch
Command: npm test -- tests/acceptance/invoice-export.test.ts
Proves: FL-1, FL-2, FL-3, EC-1, EC-2
Held-out cases: fingerprint 4c1e9a2 (stored outside git; gate only)
Fails today: 5 of 5 tests fail on their assertion; main at a1b2c3d;
5 October 2026 (written by the gate)

## Links
Relies on: GET /api/invoices?month= in src/api/invoices.ts
Blocked by: a GitHub link to the credit notes piece, not a spec field
Touches: invoices, export

## Sensitive areas
None.

## Decisions
- Dates in the file use the form 2026-09-30. Decided by the person,
  4 October 2026.
- Columns follow the receipts export. Assumed by the agent, for review.

## Research
- The accounting package imports UTF-8 CSV with a header row.
  Source: the package's import help page. Checked 3 October 2026.
  Rests on: package version 4.2.

## Open questions
- Should cancelled invoices appear in the file? Why it matters: they
  change the month's total. Recommended: no. Who: the person.
<!-- spec:end -->

## Needs (written by the gate; do not edit)
- Open question for the person: should cancelled invoices appear in the file?
- The two fresh test lists have not run yet.

<!-- loop:fingerprint none yet; taken at ready -->
