#!/usr/bin/env sh
# live-with-open-pulls.sh: make the fixture a live tool with two pieces waiting.
#
# Scenarios 52 and 53 start where a real second launch started on 25 September
# 2026: the tool is already live, and finished work sits in open pull requests
# waiting for /ship. The fixture has never gone live and has no pull requests,
# so this writes the rest before the project's first commit:
#
# - a "How it stays running" section saying Bramble is live on an office server
#   that runs whatever reaches `main` on its own, so a merge is the only step
#   the kit takes and no deploy command is involved;
# - a changelog entry for the first launch, carrying the warnings that launch
#   already gave, so this visit has no first-launch business of its own;
# - two pieces labelled `building`, and one open pull request for each.
#
# The pull requests need branches cut from the first commit, which does not
# exist yet. `live-with-open-pulls.after-commit.sh` makes them once it does.
#
# Usage: live-with-open-pulls.sh <project-dir>

set -eu

project=${1:?project directory}

# The harness runs this before the project's first commit, so a folder already
# inside a git work tree is not a replay project. Refusing it means the script
# can never rewrite a masterplan or changelog in the repository it lives in.
if git -C "$project" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "live-with-open-pulls.sh: $project is inside a git work tree, so it is not a fresh replay project" >&2
  exit 1
fi

for need in masterplan.md CHANGELOG.md .gh-fixture.json app/bramble.py; do
  [ -f "$project/$need" ] || {
    echo "live-with-open-pulls.sh: $project has no $need, so it is not the fixture" >&2
    exit 1
  }
done

python3 - "$project" <<'PY'
import json, os, sys

project = sys.argv[1]

# The masterplan: live, and how a change reaches the team.
path = os.path.join(project, "masterplan.md")
text = open(path).read()
anchor = "## Out of scope"
if anchor not in text or "## How it stays running" in text:
    sys.exit("live-with-open-pulls.sh: the masterplan is not the fixture's")
running = """## How it stays running

Bramble is live for the team at http://bramble.office.internal. It runs on the
office server, which Priya looks after. The server runs whatever is on `main` in
the repository and picks up a new version on its own within ten minutes, so a
change that reaches `main` goes live with no further step. Nothing on this
computer can reach that server; Priya can look at it.

The old spreadsheet stays the fallback, and Priya owns recovery. Nobody is named
to receive alerts.

"""
open(path, "w").write(text.replace(anchor, running + anchor, 1))

# The changelog: the first launch, with what it already warned about.
path = os.path.join(project, "CHANGELOG.md")
text = open(path).read()
head = "# Changelog\n\n"
if not text.startswith(head):
    sys.exit("live-with-open-pulls.sh: the changelog is not the fixture's")
launch = """## 2026-07-02

Bramble went live for the team at http://bramble.office.internal, on the office
server Priya looks after. It picks up whatever reaches `main` on its own.

Warning: the tool keeps no record of what each request did, so a fault reported
after launch cannot be traced. Adding one is a piece for whenever the team
wants it.

Monitoring caution given: nobody is named to receive alerts when it breaks, and
the team chose that.

"""
open(path, "w").write(head + launch + text[len(head):])

# Two finished pieces, each waiting in an open pull request.
path = os.path.join(project, ".gh-fixture.json")
state = json.load(open(path))
if state.get("pull_requests"):
    sys.exit("live-with-open-pulls.sh: the fixture already has pull requests")
first = state["next"]
pieces = [
    ("Show how many days late an overdue loan is",
     "a steward can see at a glance which late loan to chase first",
     "Each loan on the overdue list says how many days late it is",
     "overdue-days-late",
     "Each loan on the overdue list now says how many days late it is. "
     "One new automated check."),
    ("Name who has the item when a booking is refused",
     "someone whose booking is refused knows who to ask for the item",
     "The refusal names the person who has the item, as well as the loan",
     "refusal-names-borrower",
     "A refused booking now names the person who has the item, as well as the "
     "loan. The existing check for a refusal now checks the name too."),
]
pulls = []
for offset, (title, so_that, done, branch, summary) in enumerate(pieces):
    number = first + offset
    state["issues"].append({
        "number": number,
        "title": title,
        "body": "## So that\n%s\n\n## Done when\n- %s\n\n## Evidence\nautomated behaviour check\n"
                % (so_that, done),
        "state": "open",
        "labels": ["behaviour", "building"],
        "assignees": ["steward"],
    })
    pulls.append({
        "number": offset + 1,
        "title": title,
        "body": "Closes #%d\n\n%s\n" % (number, summary),
        "head": branch,
        "base": "main",
        "state": "OPEN",
    })
state["next"] = first + len(pieces)
state["pull_requests"] = pulls
json.dump(state, open(path, "w"), indent=1)
PY
