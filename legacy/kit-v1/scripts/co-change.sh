#!/usr/bin/env sh
# co-change.sh: list the files that tend to change together with the given ones.
#
# Research in /shape asks saved history one question before a piece is built:
# which other files changed in the same commits as the ones this piece touches?
# A file that keeps changing alongside them is part of what the piece reaches,
# even where no import or caller shows it.
#
# Usage: co-change.sh <path>...
#
# Run it from inside the project. Paths are read from the folder it runs in,
# as git reads them. It reads the last 200 commits that are not merges, on
# origin/main where that exists and on the checked-out commit otherwise, so
# work only this computer holds does not count once the project is online.
#
# Prints one path per line, the file changed with the given ones most often
# first, and ties in path order. The given paths are never printed. Prints
# nothing, and exits 0, when there is no history or nothing changed with them.
# Exits 2 when it could not run: no path given, or not inside a repository.

set -eu

LIMIT=200

fail() {
  echo "co-change.sh: $1" >&2
  exit 2
}

[ "$#" -ge 1 ] || fail "usage: co-change.sh <path>..."
git rev-parse --git-dir >/dev/null 2>&1 || fail "not inside a git repository"

if git rev-parse --verify --quiet refs/remotes/origin/main >/dev/null; then
  ref=refs/remotes/origin/main
elif git rev-parse --verify --quiet HEAD >/dev/null; then
  ref=HEAD
else
  # A repository with no commits has no history to read.
  exit 0
fi

prefix=$(git rev-parse --show-prefix)
tab=$(printf '\t')
history=$(git -c core.quotepath=off log -n "$LIMIT" --no-merges \
  --format='tformat:@@commit@@' --name-only "$ref" --) || fail "could not read the history of $ref"

{
  for path in "$@"; do
    path=${path#./}
    printf '@@given@@\t%s%s\n' "$prefix" "$path"
  done
  printf '%s\n' "$history"
} | awk '
  function flush(   i, hit) {
    hit = 0
    for (i = 1; i <= n; i++) if (files[i] in given) hit = 1
    if (hit) for (i = 1; i <= n; i++) if (!(files[i] in given)) count[files[i]]++
    n = 0
  }
  index($0, "@@given@@\t") == 1 { given[substr($0, 11)] = 1; next }
  $0 == "@@commit@@" { flush(); next }
  $0 == "" { next }
  { files[++n] = $0 }
  END {
    flush()
    for (f in count) printf "%d\t%s\n", count[f], f
  }
' | sort -t "$tab" -k1,1nr -k2,2 | cut -f2-
