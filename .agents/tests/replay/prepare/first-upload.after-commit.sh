#!/usr/bin/env sh
# first-upload.after-commit.sh: leave scenario 55's project on a branch named
# main, with a remote that holds nothing.
#
# The first upload creates main on GitHub at the commit the piece was cut from,
# found with `git merge-base main <piece branch>`, so the project's first branch
# has to be called main. Git's default is master on some hosts, including the
# one the hosted checks run on, so it is named here rather than left to Git.
# The remote next door stands in for the empty repository. The harness starts
# every remote empty, and this refuses to go on if something reached it.
#
# Usage: first-upload.after-commit.sh <project-dir>

set -eu

project=${1:?project directory}
me=first-upload.after-commit.sh

# Only a fresh replay project: its own repository, one commit made by the
# harness, and the remote next door. Anything else, this repository included,
# is refused before a branch is renamed.
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

git -C "$project" branch -M main

set +e
git -C "$project" ls-remote --exit-code --heads origin >/dev/null 2>&1
listed=$?
set -e
[ "$listed" -eq 2 ] || {
  echo "$me: the remote is not empty, or could not be read (exit $listed)" >&2
  exit 1
}

[ -z "$(git -C "$project" status --porcelain)" ] || {
  echo "$me: the project was left with uncommitted changes" >&2
  exit 1
}
