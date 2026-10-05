#!/usr/bin/env sh
# test-guard.sh: list the test files a piece changed without naming them.
#
# An existing test may change only when the piece's Under the hood names it and
# gives the reason, and a check written first changes only by being reported.
# A builder working alone can otherwise weaken a test until it passes, and a
# green check then proves nothing. Telling it not to does not change how often
# it happens, so a script holds the rule. section-builder runs this before it
# saves a piece, and the fix loop before it saves a repair.
#
# Usage: test-guard.sh <base> <piece-file> [checks-commit]
#   base           the commit the piece's branch was cut from: main, or the
#                  branch of the piece it stacks on
#   piece-file     the piece's text, or - to read it from standard input
#   checks-commit  the commit that holds the checks written first, if any
#
# Run it from inside the project. It compares with the working tree, so a
# change that is committed, staged or not yet staged all count.
#
# It lists two kinds of file:
# - a test file that existed at the base and has changed since, unless the
#   piece's Under the hood names it by its whole path. A new test file is not
#   listed: adding a check changes no existing test;
# - any file the checks commit added or changed that has changed since that
#   commit, named or not, because a check written first changes only by being
#   reported.
#
# A test file is any file under a folder named test, tests, __tests__ or spec,
# or whose name contains .test. or .spec., ends in _test or _spec before its
# extension, or starts with test_. A piece with no Under the hood section names
# no test.
#
# Prints one path per line on standard output. A listed file that was moved is
# named with its new path on standard error, so the new copy can be removed when
# the old one is put back. Exits 0 when nothing is listed, 1 when something is,
# and 2 when it could not run.

set -eu

fail() {
  echo "test-guard: $1" >&2
  exit 2
}

[ "$#" -eq 2 ] || [ "$#" -eq 3 ] || \
  fail "usage: test-guard.sh <base> <piece-file> [checks-commit]"
base=$1
piece=$2
checks=${3:-}

gitq() { git -c core.quotePath=false "$@"; }

gitq rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
  fail "run it from inside the project's folder"
gitq rev-parse --verify --quiet "$base^{commit}" >/dev/null || \
  fail "the base '$base' is not a commit in this project"
if [ -n "$checks" ]; then
  gitq rev-parse --verify --quiet "$checks^{commit}" >/dev/null || \
    fail "the checks commit '$checks' is not a commit in this project"
fi

if [ "$piece" = "-" ]; then
  text=$(cat)
else
  [ -f "$piece" ] || fail "the piece file '$piece' does not exist"
  text=$(cat "$piece")
fi

# Only the Under the hood section names the tests a piece may change. It is a
# collapsed details block on a piece written from the template, or a heading on
# one written by hand. It is cut into words, with the punctuation around a path
# taken off, so a path counts as named only when it appears whole.
named=$(printf '%s\n' "$text" | awk '
  /<summary>[[:space:]]*Under the hood[[:space:]]*<\/summary>/ { inside = 1; next }
  inside == 1 && /<\/details>/ { inside = 0; next }
  /^#+[[:space:]]*Under the hood[[:space:]]*$/ { inside = 2; next }
  inside == 2 && /^#+[[:space:]]/ { inside = 0 }
  inside {
    gsub(/[][[:space:],;:()"`<>*\047]+/, "\n")
    n = split($0, word, "\n")
    for (i = 1; i <= n; i++) {
      sub(/\.+$/, "", word[i])
      if (word[i] != "") print word[i]
    }
  }
')

is_test() {
  case "/$1" in
    */test/*|*/tests/*|*/__tests__/*|*/spec/*) return 0 ;;
  esac
  name=${1##*/}
  case "$name" in
    *.test.*|*.spec.*|test_*) return 0 ;;
  esac
  stem=${name%.*}
  case "$stem" in
    *_test|*_spec) return 0 ;;
  esac
  return 1
}

is_named() {
  printf '%s\n' "$named" | grep -qxF -- "$1"
}

# Renames are split into a deletion and an addition, so a test moved away
# counts as changed at its old path.
unnamed=$(gitq diff --no-renames --name-status "$base" -- | \
  while IFS="$(printf '\t')" read -r status path; do
    [ "$status" = "A" ] && continue
    is_test "$path" || continue
    is_named "$path" && continue
    printf '%s\n' "$path"
  done)

touched=""
if [ -n "$checks" ]; then
  touched=$(gitq diff --no-renames --name-only "$checks^" "$checks" -- | \
    while IFS= read -r path; do
      gitq diff --quiet "$checks" -- "$path" 2>/dev/null && continue
      printf '%s\n' "$path"
    done)
fi

listed=$(printf '%s\n%s\n' "$unnamed" "$touched" | awk 'NF && !seen[$0]++')
[ -n "$listed" ] || exit 0

# Name the new copy of anything that was moved, for the put-back.
gitq diff -M --name-status "$base" -- | \
  while IFS="$(printf '\t')" read -r status old new; do
    case "$status" in
      R*) if printf '%s\n' "$listed" | grep -qxF -- "$old"; then
            echo "test-guard: $old was moved to $new" >&2
          fi ;;
    esac
  done

printf '%s\n' "$listed"
exit 1
