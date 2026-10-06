# The spec format, version 1

This file is the one home of the spec format. The one parser,
`kit/scripts/loop/spec.py`, reads it. The gate, the lint, the needs list and
the fingerprint all use that parser. No other file reads the markers.

Read a spec with `kit/scripts/spec.py show <number>` or
`kit/scripts/spec.py show --file <path>`. Both print JSON.

## The block

A piece is a GitHub issue. Its body has a short plain header, then the spec
block, then anything the gate writes below it.

```markdown
A one-line plain header that says what the piece is for.

<!-- spec:start version=1 -->
## Goal
...
<!-- spec:end -->
```

- The start marker is `<!-- spec:start version=1 -->`. The end marker is
  `<!-- spec:end -->`. Each sits alone on its line.
- A marker inside a fenced code block does not count.
- An issue has one block. A second block, or a start marker with no end
  marker, is a fault.
- A body with no markers has no spec. The parser reports `found: false`. The
  gate then computes the needs from the empty fields.
- A block with a version the kit does not know is refused. The refusal
  exits with code 3 and has a `next:` line. A block with no version is
  refused in the same way. Version 1 is the only version.
- Text before the start marker is the header. Text after the end marker is
  not part of the spec. The needs list and the fingerprint sit there.

Headings follow the rules of `section()` in `kit/scripts/loop/spec.py`. A field is
a `## ` heading. A heading inside a fenced code block does not count.

## Fields

| Field | Key in the parser | Needed on the full path | Needed on the quick path |
| --- | --- | --- | --- |
| Goal | `goal` | yes | yes |
| User story | `user_story` | yes | no |
| Expected flow | `expected_flow` | yes | yes |
| How to observe it | `how_to_observe` | yes | no |
| Edge cases | `edge_cases` | yes | yes |
| Limits | `limits` | yes | no |
| Must stay the same | `must_stay_the_same` | yes | yes |
| Follow | `follow` | yes | no |
| Changes to current behaviour | `changes` | yes | no |
| Coverage | `coverage` | yes | no |
| Not in this piece | `not_in_this_piece` | yes | no |
| Judge | `judge` | yes | yes |
| Links | `links` | yes | yes |
| Sensitive areas | `sensitive_areas` | yes | no |
| Decisions | `decisions` | no | no |
| Research | `research` | no | no |
| Open questions | `open_questions` | no | no |

A needed field that is missing or empty is listed in `missing`. A field that
holds "None." counts as answered. A field that is not needed may be left out.

## The quick path

A small change uses the quick path. The block opens with the line
`Path: quick`, before the first heading. Without that line the path is
`full`. Any other value is a fault.

The quick path needs only Goal, Expected flow, Edge cases, Must stay the same,
Judge and Links. The change must be one piece, in one area, with no sensitive
area, no new dependency and a judge that is a single test. The gate checks
those limits. The parser only reads the fields.

## IDs

- A flow step is a line that starts with `FL-` and a number, such as
  `FL-1 The user opens the menu.`
- An edge case is a line that starts with `EC-` and a number, such as
  `EC-1 When the month has no invoices, then the file holds the header line only.`
- A step or case may run over more lines. The next line that is not blank and
  not a list item continues it.
- An ID is used once. The parser lists a repeated ID in `duplicate_ids`.
- A line in Expected flow or Edge cases with no ID is listed in
  `flow_without_id` or `edge_cases_without_id`.
- An edge case reads "When ..., then ...". The parser gives `trigger` and
  `result`. A case with no "then" has a `result` of null.
- The Judge field's `Proves:` line names the IDs that the tests prove.

## Coverage

Coverage has one answer for each category below. Write each as `Category:`
and the answer. Several may share a line. An answer may say
"Not applicable, because ..." when the reason is real. A category with no
answer, or with "Not applicable" and no reason, is listed in
`unanswered_coverage`.

The categories (the list is proposed, and this file is its home):

- Permissions
- Data kept
- Errors
- Empty states
- What leaves the tool

## The Judge field

Each line is `Key: value`. A line that does not start with a known key
continues the line above it.

| Key | Meaning |
| --- | --- |
| `Kind:` | The judge kind, then an optional note after a comma. |
| `Command:` | The command that runs the judge. |
| `Proves:` | The IDs the judge proves. |
| `Held-out cases:` | The fingerprint of the hidden cases, as the 64 hex digits that `loop.heldout store` prints. Never their content. The ready gate compares it with the store. |
| `Fails today:` | The gate's record that the judge fails. Only the gate writes it, at ready. |
| `Route:` | The word `open` marks "route open". |
| `Hypotheses:` | The hypotheses of a metric piece or an open route, split by `;`. |

A spec marked "route open" has `Route: open`. The parser sets `route_open`.
The ready gate refuses such a spec until the hypothesis list and the held-out
twin exist.

### Supported test runners

The parser names the runner at the start of `Command:` in `judge.runner`.
It is null for any other command.

| Command starts with | `runner` |
| --- | --- |
| `pytest`, `python3 -m pytest` | `pytest` |
| `python3 -m unittest` | `unittest` |
| `npm`, `pnpm`, `yarn` | `npm`, `pnpm`, `yarn` |
| `vitest`, `npx vitest` | `vitest` |
| `jest`, `npx jest` | `jest` |
| `go test` | `go` |
| `cargo test` | `cargo` |
| `sh`, `bash` | `shell` |

## Links

- `Relies on:` code or services, by name, split by commas.
- `Touches:` areas, split by commas. Each area is in the project's area map,
  `docs/area-map`, or is named under `New area:` in Changes to current
  behaviour. The ready gate refuses any other.

Waiting for another piece is a GitHub blocked-by link. It is not a spec field.

## Changes to current behaviour

Each line may carry these labels, and several may share a line.

- `Added:`, `Changed:` and `Removed:` say what changes.
- `Docs:` names the docs the pull request must change, split by commas.
- `New area:` names a new area, split by commas. Use it when the change makes
  an area that the area map does not hold yet.
- `Not reversible:`, `New dependency:` and `Security:` mark the change. Write
  what is not reversible, which dependency is new, or what security behaviour
  changes. A mark whose text is `no` or `none` marks nothing. Each mark is a
  must-look reason: the ready gate gives the piece individual review.

## Must stay the same

Prose says what must not change. At least one `Check:` line is required. Each
`Check:` line names a command that proves it, such as
`Check: python3 -m pytest tests/test_old.py`. The ready gate refuses a spec with
no `Check:` line, except for the scaffold piece. It runs each command on
`main`, and it must pass there. The parser gives the commands in
`must_stay_checks`.

## Lists

Sensitive areas, Decisions, Research and Open questions are lists. Each item
starts with `- `. A line that continues an item is indented or follows it
directly. "None." in a list field means an empty list.

## Decisions

A line that starts with `must-look` in Decisions, written by the person, marks
the piece for individual review. It is the fifth must-look reason, beside a
sensitive area and the three marks above.

## Sensitive areas

A sensitive area is accepted when its list item holds three things. The first
is the label `Accepted:`. The second is the person's own words in quotes. The
third is a date, written `YYYY-MM-DD` or `D Month YYYY`. An item without all
three stays on the needs list for the person. The check does not judge whether
the words are the person's. The person decides that at the gate.

## What the parser returns

`to_dict()` always has the same keys: `found`, `version`, `path`, `header`,
`fields`, `must_stay_checks`, `missing`, `flow`, `flow_without_id`, `edge_cases`,
`edge_cases_without_id`, `ids`, `duplicate_ids`, `coverage`,
`unanswered_coverage`, `judge`, `route_open`, `links`, `changes`,
`sensitive_areas`, `decisions`, `research` and `open_questions`.
