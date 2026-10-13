# The spec format

A piece is a GitHub issue. Its body is the spec. The gate reads two
sections exactly as written here. The others are for people and builders.

```markdown
## Goal
One or two sentences: what the person gets, in their words.

## Done when
- D1: A condition somebody can check. "When I run `habits add read`, then `habits list` shows read."
- D2: One condition per line. Number them D1, D2, D3.

## Judge
Command: `python3 -m pytest tests/judge/test_piece_add.py -q`
Files:
- tests/judge/test_piece_add.py

## Notes
Anything a builder needs: the area of the code, choices already made,
what must stay the same.
```

## What the gate checks at ready

- `## Done when` has at least one `D<number>:` item, and no ID twice.
- `## Judge` has a `Command:` line and lists its judge files under `Files:`.
- The branch `piece/<issue number>` holds the judge files.
- The judge command, run on today's `main` with only the judge files added,
  fails. It fails on an assertion, not on a syntax or collection error.
- Every spec ID appears in the failing output. Put the ID in each test name,
  like `test_D1_add_shows_in_list`.

The gate then fixes the bar: it records a hash of the judge files and a hash
of the spec on the issue. If either changes later, the piece cannot be built
until it goes through ready again.

## The first piece of an empty project

An empty project has nothing to fail. Its first piece sets up the code and
the test runner. Write `Kind: scaffold` under `## Judge`. Its judge is that
the command runs and passes, so the gate skips the "fails on main" check.
