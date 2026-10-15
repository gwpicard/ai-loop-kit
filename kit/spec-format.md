# The spec format

A piece is a GitHub issue. Its body is the contract the person approves.

```markdown
## Intent
What the person wants and why, in their words.

Out of scope:
- What this piece will not do.

## Approach
Optional. Name the files, interface, tools and constraints when they help.

## Research
- R1: The API accepts a timeout argument (source: https://example.test/api, read: 2026-10-15)

## Contract
- D1: When I run `habits add read`, then `habits list` shows read.
- D2 (stays): Without `--title`, the output is unchanged.

## Judge
Kind: feature
Command: `python -m pytest tests/judge/test_piece_add.py -q`
Files:
- tests/judge/test_piece_add.py
Keep: `python -m pytest`
# Optional: allow this named file to cross 1,000 lines.
Large file: src/generated.py
```

`Intent` and a non-empty `Out of scope:` list are required. `Approach` is
optional. Contract items start with a unique ID such as `D1`. An item already
true on main can use `(stays)`; its judge test must pass on main.

`Research` is optional. Use one line per outside finding, with a unique `R`
ID, an HTTP or HTTPS source URL and the date read in `YYYY-MM-DD` form. The
gate refuses a malformed finding. At claim, it reports findings older than
30 days as possibly stale. The builder and contract reviewer receive the
findings.

Use `Kind: feature` for new behaviour, `Kind: fix` for a bug, and
`Kind: scaffold` for the first piece in an empty project. A fix starts with
the bug in its first Contract item. `Done when` remains accepted as the old
name for `Contract`.

## Fix example

```markdown
## Intent
Keep a saved habit when another habit is added.

Out of scope:
- Changing how habits are displayed.

## Contract
- D1: When I add a second habit, then the first remains in the saved list.

## Judge
Kind: fix
Command: `python -m pytest tests/judge/test_piece_retains_habit.py -q`
Files:
- tests/judge/test_piece_retains_habit.py
```

## What the gate checks at ready

- Intent and the out of scope list are present, and each Contract item has
  one ID.
- The judge fails on today's main for each item to build. A `(stays)` item
  passes on main and has a test.
- `Keep:` passes on main and after the build.
- `Files:` names judge files inside the project.
- Each Research line has a source URL and a real read date.
- At submit a file may not grow from under 1,000 lines to 1,000 or more
  unless its path is named with `Large file:`.

The gate records a hash of the spec and of the judge bar. A change after ready
means the piece must go back through shaping and ready.

## Project environments

The project's `AGENTS.md` names a Test command and, when needed, a Prepare
command. The gate runs Prepare in each fresh copy before checks, except for
scaffold readiness. The run prepares the build folder before each build.
Write `Keep:` as the plain Test command. Do not put install steps or local
paths in the spec.
