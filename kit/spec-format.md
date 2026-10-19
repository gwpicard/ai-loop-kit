# The spec format

A piece is a GitHub issue with an approved body.

```markdown
## Intent
What the person wants and why, in their words.

Out of scope:
- What this piece will not do.

## Approach
Optional. Name useful files, interfaces, tools and constraints.

## Research
- R1: The API accepts a timeout argument (source: https://example.test/api, read: 2026-10-15)

## Contract
- D1: When I run `habits add read`, then `habits list` shows read.
- D2 (stays): Without `--title`, the output is unchanged.

## Exit
### Tests
Command: `python -m pytest tests/judge/test_piece_add.py -q`
Files:
- tests/judge/test_piece_add.py

## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none

## Judge
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

`Risks` is optional for older issues. New issues should include all five
lines. Use comma-separated paths or names, or `none`. `Open choices:` must
say `none` before ready. Protected paths named here are allowed for the
piece. The gate warns when another ready issue names one of the same shared
files. `Needs services:` prevents a walk-away run. At submit, every new
dependency in `package.json` or `pyproject.toml` must be named under
`New dependency:`. Each name needs a reason after a colon, such as
`requests: retry support`.

An `## Exit` section contains one or more checks. Use `### Tests` with
`Command:` and `Files:`, `### Measure` with `Command:`, `Target:` and
`Files:`, or `### Critics` with `Capture:`, `Reference:`, `Criteria:` and
`Files:`. Every check must be unmet on main for the right reason. A piece may
combine check types. The project's Test command always runs. Optional `Keep:`
in `## Judge` adds a distinct check; identical commands run once.
`Playbook: fix` guides the builder and has no gate effect.
`Done when` remains accepted as the old name for `Contract`.

Specs with `## Judge` and `Kind:` remain accepted as one check. A fix
starts with the bug in its first Contract item. Empty projects use the
[scaffold example](examples/scaffold.md). Legacy goal and gauntlet specs keep
their behaviour.

## Measure check

A Measure check uses `Command:` and `Target:`. `Files:` names the measure
script and its support files. The command must print one finite number on its
last non-empty line. The gate runs it three times and uses the median. The
target uses `<`, `<=`, `>` or `>=` followed by a number. At ready, the median
on main must miss the target. Before changing code, each attempt writes one
hypothesis to `.loop/hypothesis`. An attempt passes when the median meets the
target and `Keep:` passes. The pull request records the main and attempt values
and the hypotheses tried.

```markdown
## Exit
### Measure
Command: `python bench.py`
Target: < 200
Files:
- bench.py

## Judge
Keep: `python -m pytest`
```

## Critics check

A Critics check uses `Capture:` to make artefact files under
`.loop/capture/`, `Reference:` to name a project path or URL, and a non-empty
list of `Criteria:`. `Files:` names the capture script, its support files and
any local reference files. The gate freezes these files in the bar. Three
fresh blind critics see the two artefacts in random order. Main must win fewer
than two comparisons at ready. An attempt passes when ours wins at least two
and `Keep:` passes. The pull request records each verdict and the order shown
to each critic.

```markdown
## Exit
### Critics
Capture: `python3 render.py`
Reference: `docs/example.png`
Criteria:
- Readable labels
- Clear hierarchy
Files:
- render.py
- docs/example.png

## Judge
Keep: `python -m pytest`
```

## Fix example

```markdown
## Intent
Keep a saved habit when another habit is added.

Out of scope:
- Changing how habits are displayed.

## Contract
- D1: When I add a second habit, then the first remains in the saved list.

## Exit
### Tests
Command: `python -m pytest tests/judge/test_piece_retains_habit.py -q`
Files:
- tests/judge/test_piece_retains_habit.py

## Judge
Playbook: fix
```

## What the gate checks at ready

- Intent and the out of scope list are present, and each Contract item has
  one ID.
- The judge fails on today's main for each item to build. A `(stays)` item
  passes on main and has a test.
- The Test command and any distinct `Keep:` pass on main and after the build.
- `Files:` names the files an exit check runs, inside the project.
- Each Research line has a source URL and a real read date.
- At submit a file may not grow from under 1,000 lines to 1,000 or more
  unless its path is named with `Large file:`.

Every check in `## Exit` runs on main at ready and after each attempt. Measure
checks use the median of three runs. Critics checks use three blind verdicts.
Every check's `Files:` list is included in the frozen bar. Legacy goal and
gauntlet specs keep the same readiness and attempt rules.

The gate hashes the spec and judge bar. A change after ready
means the piece must go back through shaping and ready.

## Project environments

The project's `AGENTS.md` names the required Test command and optional
Prepare command. Ready records the regression command, Keep limit and main
result. Submit reruns it on the final commit. Scaffold readiness skips the
regression check and Prepare. `Keep:` adds checks; it never replaces the full
suite. Keep install steps and local paths out of specs.

Quality commands are optional project checks. Setup runs each proposed
command on a fresh copy of main after applying the proposed loop commands.
Python mutation checks require mutmut 3.8 or later and configured source
paths. For subprocess acceptance tests, select an in-process adapter test for
the changed function in mutmut's test-selection setting.

When a piece needs stronger tests in an existing mutation adapter, name its
path in Contract so the builder may strengthen it. Keep the adapter out of
Exit `Files:`: those files are frozen at ready, even when Contract names
them. Use a separate judge that does not depend on the editable adapter.

`mutmut-changed.py` selects functions from committed `base...HEAD` changes.
A builder's check before committing may find no changed functions. The
final gate evidence comes after the runner commits the attempt and runs
the checks again.
