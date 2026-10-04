#!/usr/bin/env sh
# three-ready-pieces.after-commit.sh: put scenario 57's project online.
#
# A run opens a pull request for each piece it builds, and one stacked on
# another aims at that piece's branch. With an empty remote, the first push
# would be the project's first upload, which waits for the person's yes, and a
# run has nobody there to give it. So the code is already online here: the
# first branch is named main, since Git's default is master on some hosts, and
# pushed to the remote next door.
#
# Usage: three-ready-pieces.after-commit.sh <project-dir>

set -eu

project=${1:?project directory}
me=three-ready-pieces.after-commit.sh

# Only a fresh replay project: its own repository, one commit made by the
# harness, and the remote next door. Anything else, this repository included,
# is refused before a branch is renamed or pushed.
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
git -C "$project" push -q origin main

[ -z "$(git -C "$project" status --porcelain)" ] || {
  echo "$me: the project was left with uncommitted changes" >&2
  exit 1
}
