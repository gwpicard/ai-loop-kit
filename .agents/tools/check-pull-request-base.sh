#!/usr/bin/env sh
# Only a release may move stable. Pull requests belong on main.
set -eu
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "usage: check-pull-request-base.sh <base branch>" >&2
  exit 2
fi
if [ "$1" = stable ]; then
  echo "Only a release may move 'stable'. Change this pull request's base to 'main'." >&2
  echo "Run gh pr edit <number> --base main; open new ones with gh pr create --base main." >&2
  exit 1
fi
echo "Pull request base '$1' is allowed."
