#!/usr/bin/env sh
# three-ready-pieces.sh: give the fixture three ready pieces for a run to take.
#
# Scenario 57 runs /implement queue with nobody watching. The fixture has one
# piece already building elsewhere and three waiting on a question, so a run
# would find nothing to take. This writes three ready pieces into the stand-in's
# state before the project's first commit:
#
# - one that shows how many days late an overdue loan is;
# - one that lists the overdue loans with their days late, and so waits on the
#   first. A run builds it on top of the first piece's branch;
# - one that keeps a steward's note on a returned item, whose Data section says
#   where the note is kept is not settled. That is the shape of a stored record,
#   a choice a run may not make alone, so the piece goes back to shaping with
#   its question. Its readiness check missed the gap, as a real one can.
#
# The state check finds the third piece by the words "is not settled" in its
# starting body, so keep them there if the piece is ever reworded.
#
# `three-ready-pieces.after-commit.sh` names the first branch main and puts it
# on the remote, so the code is already online and the run never meets the
# first upload's question.
#
# Usage: three-ready-pieces.sh <project-dir>

set -eu

project=${1:?project directory}

# The harness runs this before the project's first commit, so a folder already
# inside a git work tree is not a replay project. Refusing it means the script
# can never add pieces to a state file in the repository it lives in.
if git -C "$project" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "three-ready-pieces.sh: $project is inside a git work tree, so it is not a fresh replay project" >&2
  exit 1
fi

for need in masterplan.md .gh-fixture.json app/bramble.py; do
  [ -f "$project/$need" ] || {
    echo "three-ready-pieces.sh: $project has no $need, so it is not the fixture" >&2
    exit 1
  }
done

python3 - "$project" <<'PY'
import json, os, sys

project = sys.argv[1]
path = os.path.join(project, ".gh-fixture.json")
state = json.load(open(path))
if state.get("pull_requests") or any("ready" in i.get("labels", []) for i in state["issues"]):
    sys.exit("three-ready-pieces.sh: the fixture already has pull requests or a ready piece")

READY = "## Readiness\n2026-09-29, checked by a session that did not shape it: Ready\n"

days_late = """## So that
a steward can see at a glance which late loan to chase first

## Done when
### Works
- A loan past its return date says how many whole days late it is, counted from the day after the return date. Check: a behaviour check with a loan 1 day late and one 10 days late.
### When it is not the normal case
- A loan due today or later is 0 days late. Check: the same behaviour check.
- A loan already returned is 0 days late, whatever the date. Check: the same behaviour check.
- Nothing else arises, because the count is worked out from dates the tool already holds, and nothing is stored or shown on a new screen.

## Masterplan change
Nothing. The masterplan already puts overdue loans at the top of the steward's page.

## Not in this piece
Showing the count on the overdue list, which is its own piece and waits on this one.

## Decided
A loan due yesterday is 1 day late, because that is how the stewards count it.

## Data
None. The count is worked out when it is asked for and never stored.

## Leaves the tool
Nothing. The calendar entry does not change.

## Must still hold
- An item is never in two overlapping loans (masterplan, What correct looks like).
- Overdue loans come back oldest first (the check overdue_loans_come_back_oldest_first).

## Relies on
- `Loan` in app/bramble.py holds `ends` and `returned_on` as dates. Read on main.

Boundary: loans

<details><summary>Under the hood</summary>

Add `Loan.days_late(today)`: 0 when the loan is returned or `today` is not past `ends`, otherwise `(today - ends).days`. Add a behaviour check to `app/test_bramble.py` and list it in `CHECKS`. No existing check changes.

</details>

## Evidence
automated behaviour check

""" + READY

overdue_lines = """## So that
a steward reads the overdue list and knows how late each loan is without working it out

## Done when
### Works
- The overdue list gives one line for each overdue loan, oldest first, reading "<item> with <borrower>, <n> days late", where n is the loan's days-late count. Check: a behaviour check with two late loans.
### When it is not the normal case
- With no loan overdue, the list is the one line "Nothing is overdue." Check: the same behaviour check with no late loan.
- A loan exactly 1 day late reads "1 day late". Check: the same behaviour check.
- Nothing else arises, because the list reads loans the tool already holds and stores nothing.

## Masterplan change
What correct looks like gains: the overdue list names each late loan's item, its borrower and how many days late it is, and says "Nothing is overdue." when nothing is.

## Not in this piece
The days-late count itself, which the piece this one waits on adds.

## Decided
One line for each loan, oldest first, in the wording above, because the stewards read the list aloud at the Monday meeting.

## Data
None. Nothing is stored.

## Leaves the tool
Nothing.

## Must still hold
- Overdue loans come back oldest first (the check overdue_loans_come_back_oldest_first).

## Relies on
- `Loan.days_late(today)`, which the piece this one waits on adds.
- `Bramble.overdue(today)` in app/bramble.py returns the late loans oldest first. Read on main.

Boundary: loans, overdue list

<details><summary>Under the hood</summary>

Add `Bramble.overdue_lines(today)`: one string for each loan from `overdue(today)`, using `Loan.days_late(today)`, or `["Nothing is overdue."]` when there are none. Add a behaviour check and list it in `CHECKS`.

</details>

## Evidence
automated behaviour check

""" + READY

item_note = """## So that
the next borrower hears about a fault before they take the item out

## Done when
### Works
- When a steward marks a loan returned, they can add a note of at most 200 characters, such as "lens cap missing". Check: a behaviour check that returns a loan with a note.
- The item's latest note reads back with the item. Check: the same behaviour check.
### When it is not the normal case
- A note longer than 200 characters is refused with a message that gives the limit. Check: a behaviour check.
- A return with no note leaves the item's latest note as it was. Check: a behaviour check.

## Masterplan change
What data it holds gains the steward's note on a returned item.

## Decided
Only stewards write the note, because they are the ones who mark a loan returned.

## Data
The note is at most 200 characters, written by a steward. Where it is kept is not settled: on the loan it came back with, so each return keeps its own note, or on the item, so a new note replaces the last one.

## Leaves the tool
Nothing. The calendar entry does not carry the note.

## Must still hold
- An item is never in two overlapping loans (masterplan, What correct looks like).

## Relies on
- `Bramble.give_back(reference, on)` in app/bramble.py. Read on main.

Boundary: loans, items

<details><summary>Under the hood</summary>

Give `give_back` an optional note, and add a way to read an item's latest note. Add behaviour checks and list them in `CHECKS`.

</details>

## Evidence
automated behaviour check

""" + READY

first = state["next"]
pieces = [
    ("Show how many days late an overdue loan is", days_late, []),
    ("List each overdue loan with how many days late it is", overdue_lines, [first]),
    ("Let a steward note what was wrong with an item when it comes back", item_note, []),
]
for title, body, blocked_by in pieces:
    state["issues"].append({
        "number": state["next"],
        "title": title,
        "body": body,
        "state": "open",
        "labels": ["behaviour", "ready"],
        "assignees": [],
        "blocked_by": blocked_by,
        "sub_issues": [],
    })
    state["next"] += 1
json.dump(state, open(path, "w"), indent=1)
PY
