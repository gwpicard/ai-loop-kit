#!/usr/bin/env sh
# live-with-open-pulls.after-commit.sh: cut the branches behind the two pull
# requests that live-with-open-pulls.sh recorded.
#
# A pull request is a branch on the remote, and the branch has to grow from the
# project's own first commit. So this runs after that commit, once the empty
# remote next door exists. For each pull request it cuts the branch from
# `main`, makes the change, checks that the project's own checks still pass,
# commits, and pushes the branch. It pushes `main` as well, as a live project
# on GitHub would have it, and leaves the project on `main` with nothing
# uncommitted, which is where /implement leaves a person after a piece.
#
# The two changes touch different lines, so either can merge first and the
# other still merges cleanly after it.
#
# Usage: live-with-open-pulls.after-commit.sh <project-dir>

set -eu

project=${1:?project directory}
me=live-with-open-pulls.after-commit.sh

# Only a fresh replay project: its own repository, one commit made by the
# harness, and the remote next door. Anything else, this repository included,
# is refused before a branch is made.
top=$(git -C "$project" rev-parse --show-toplevel 2>/dev/null || true)
here=$(cd "$project" 2>/dev/null && pwd -P || true)
[ -n "$top" ] && [ "$(cd "$top" && pwd -P)" = "$here" ] || {
  echo "$me: $project is not the top of its own repository" >&2
  exit 1
}
[ "$(git -C "$project" rev-list --count --all)" = "1" ] \
  && [ "$(git -C "$project" log -1 --format=%s)" = "Project before the scenario" ] || {
  echo "$me: $project has history beyond the harness's first commit, so it is not a fresh replay project" >&2
  exit 1
}
[ "$(git -C "$project" remote get-url origin 2>/dev/null || true)" = "$project.git" ] || {
  echo "$me: $project has no remote next door" >&2
  exit 1
}
[ -f "$project/.gh-fixture.json" ] || {
  echo "$me: $project records no pull requests" >&2
  exit 1
}

# The pull requests name `main` as their base.
git -C "$project" branch -M main

# change <branch> <python edit> <commit message>
change() {
  git -C "$project" checkout -q -b "$1" main
  python3 - "$project" "$2" <<'PY'
import os, sys

project, which = sys.argv[1], sys.argv[2]


def edit(name, old, new):
    path = os.path.join(project, "app", name)
    text = open(path).read()
    if text.count(old) != 1:
        sys.exit("%s: the fixture changed, so this edit no longer fits" % name)
    open(path, "w").write(text.replace(old, new, 1))


if which == "days-late":
    edit("bramble.py", '''    def clashes_with(self, starts, ends):''',
         '''    def days_late(self, today):
        """How many days past its return date an unreturned loan is."""
        if self.returned_on is not None or today <= self.ends:
            return 0
        return (today - self.ends).days

    def clashes_with(self, starts, ends):''')
    edit("test_bramble.py", '''CHECKS = [''',
         '''def an_overdue_loan_says_how_many_days_late_it_is():
    loan = new().book("camera A", "Priya", date(2026, 6, 1), date(2026, 6, 2))
    assert loan.days_late(date(2026, 6, 5)) == 3, loan.days_late(date(2026, 6, 5))
    assert loan.days_late(date(2026, 6, 2)) == 0, loan.days_late(date(2026, 6, 2))


CHECKS = [''')
    edit("test_bramble.py", '''    overdue_loans_come_back_oldest_first,
]''', '''    overdue_loans_come_back_oldest_first,
    an_overdue_loan_says_how_many_days_late_it_is,
]''')
elif which == "names-borrower":
    edit("bramble.py", '''            "item %s is already out on loan %s from %s to %s"
            % (blocking.item, blocking.reference, blocking.starts, blocking.ends)''',
         '''            "item %s is already out on loan %s to %s from %s to %s"
            % (blocking.item, blocking.reference, blocking.borrower,
               blocking.starts, blocking.ends)''')
    edit("test_bramble.py", '''        assert refused.blocking.reference == first.reference
''', '''        assert refused.blocking.reference == first.reference
        assert "Priya" in str(refused), str(refused)
''')
else:
    sys.exit("unknown change %s" % which)
PY
  PYTHONDONTWRITEBYTECODE=1 python3 "$project/app/test_bramble.py" >/dev/null || {
    echo "$me: the project's checks fail on $1" >&2
    exit 1
  }
  git -C "$project" add -A
  git -C "$project" commit -q -m "$3"
  git -C "$project" push -q origin "$1"
  git -C "$project" checkout -q main
}

change overdue-days-late days-late "Show how many days late an overdue loan is"
change refusal-names-borrower names-borrower "Name who has the item when a booking is refused"
git -C "$project" push -q origin main

[ -z "$(git -C "$project" status --porcelain)" ] || {
  echo "$me: the project was left with uncommitted changes" >&2
  exit 1
}
