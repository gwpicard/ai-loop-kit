#!/usr/bin/env sh
# first-upload.sh: make the fixture a founded project whose code was never
# uploaded, with one small piece ready to build.
#
# Scenario 55 starts where the pre-release run of 26 September 2026 was when it
# reached its first /implement: the pieces are issues on GitHub, the repository
# holds nothing else, and founding told the person no code was uploaded. That
# run pushed main to the empty repository without asking. The fixture already
# keeps its pieces as issues and the harness already starts every remote empty,
# so this writes the rest before the project's first commit:
#
# - a changelog entry saying the pieces moved into GitHub issues and no code
#   was uploaded;
# - the repository recorded as private, so the kit has something to name;
# - one small piece labelled `ready`, the only one /implement can take.
#
# `first-upload.after-commit.sh` names the first branch main and checks that
# the remote is still empty.
#
# Usage: first-upload.sh <project-dir>

set -eu

project=${1:?project directory}

# The harness runs this before the project's first commit, so a folder already
# inside a git work tree is not a replay project. Refusing it means the script
# can never rewrite a changelog in the repository it lives in.
if git -C "$project" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "first-upload.sh: $project is inside a git work tree, so it is not a fresh replay project" >&2
  exit 1
fi

for need in masterplan.md CHANGELOG.md .gh-fixture.json app/bramble.py; do
  [ -f "$project/$need" ] || {
    echo "first-upload.sh: $project has no $need, so it is not the fixture" >&2
    exit 1
  }
done

python3 - "$project" <<'PY'
import json, os, sys

project = sys.argv[1]

path = os.path.join(project, "CHANGELOG.md")
text = open(path).read()
head = "# Changelog\n\n"
if not text.startswith(head) or "No code was uploaded" in text:
    sys.exit("first-upload.sh: the changelog is not the fixture's")
moved = """## 2026-06-20

The pieces moved into GitHub issues, in the team's new repository
bramble-team/bramble. No code was uploaded. The repository holds the issues
and nothing else, and every change so far is saved on this computer.

"""
open(path, "w").write(head + moved + text[len(head):])

path = os.path.join(project, ".gh-fixture.json")
state = json.load(open(path))
if state.get("pull_requests") or any("ready" in i.get("labels", []) for i in state["issues"]):
    sys.exit("first-upload.sh: the fixture already has pull requests or a ready piece")
state["visibility"] = "PRIVATE"
state["issues"].append({
    "number": state["next"],
    "title": "Show how many days late an overdue loan is",
    "body": "## So that\n"
            "a steward can see at a glance which late loan to chase first\n\n"
            "## Done when\n"
            "- Each loan on the overdue list says how many days late it is, "
            "and a loan not yet due says 0\n\n"
            "## Evidence\n"
            "automated behaviour check\n\n"
            "## Not in this piece\n"
            "A screen for the number. The overdue list already carries each loan.\n",
    "state": "open",
    "labels": ["behaviour", "ready"],
    "assignees": [],
    "blocked_by": [],
    "sub_issues": [],
})
state["next"] += 1
json.dump(state, open(path, "w"), indent=1)
PY
