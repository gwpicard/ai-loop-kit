#!/usr/bin/env sh
# check-pull-request-base.sh: refuse a pull request aimed at `stable`.
#
# `stable` is the default branch, because two of the three installation routes
# read the default branch and should receive a release. Only the release job
# moves it. But GitHub fills in the default branch as the base of a new pull
# request, and `gh pr create` without `--base` does the same. So the easy way to
# open a pull request is the wrong one.
#
# That happened. A version stamp was opened without `--base` and merged into
# `stable`. The next release could not move `stable` onto the release line
# without a force push, which its ruleset refuses, and a person had to turn that
# rule off by hand for the job to finish.
#
# The obvious guard is a ruleset on `stable` that requires a pull request or a
# status check. Either one would also refuse the release job, which moves the
# branch through the API rather than through a pull request. So the guard lives
# here instead, as a check that goes red on the pull request, and it stays off
# the required list for the same reason.
#
# Only `stable` is refused. A pull request based on another working branch is
# ordinary stacking, and refusing everything but `main` would stop it.
#
# Usage:
#   check-pull-request-base.sh <base branch>
#
# Exit 0 when the base is not `stable`, 1 when it is, 2 when no base is given.
#
# POSIX sh.

set -eu

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "usage: check-pull-request-base.sh <base branch>" >&2
  exit 2
fi

base=$1

if [ "$base" != "stable" ]; then
  echo "This pull request merges into '$base', not into 'stable'."
  exit 0
fi

# The message is read by a person looking at a red check, so it says what to do
# rather than what went wrong.
cat >&2 <<'MESSAGE'
This pull request merges into 'stable', and only a release may move 'stable'.
Change its base to 'main': press Edit beside the title and pick main, or run
gh pr edit <number> --base main. Next time, open it with gh pr create --base main.
MESSAGE
exit 1
