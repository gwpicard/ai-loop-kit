#!/usr/bin/env sh
# co-change-rehearsal.sh: run the history query research uses, in throwaway
# repositories, and read back what it prints.
#
# Research asks saved history one question: which files tend to change in the
# same commits as the ones this piece touches? The section-builder skill's
# scripts/co-change.sh answers it. A file it misses is an area research never
# names, and the piece is shaped as if that area were safe. A wrong order puts
# a file that changed with it once above one that changes with it every time.
#
# Each case builds its own history: two files paired twice, a third paired
# once, a file never paired, a pairing older than the 200 commits it reads, a
# commit only this computer holds once origin/main exists, and a repository
# with no commits at all.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SCRIPT="$ROOT/.agents/skills/section-builder/scripts/co-change.sh"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

pass=0
fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
  pass=$((pass + 1))
}

echo "Co-change rehearsal:"
[ -x "$SCRIPT" ] || fail "the section-builder skill's scripts/co-change.sh is missing or not executable"

new_repo() {
  git init -q -b main "$1"
  git -C "$1" config user.email rehearsal@example.invalid
  git -C "$1" config user.name Rehearsal
  git -C "$1" config commit.gpgsign false
}

change() {
  # change <repo> <message> <file>...: one commit touching each file named.
  repo=$1
  message=$2
  shift 2
  for file in "$@"; do
    mkdir -p "$repo/$(dirname -- "$file")"
    echo "$message" >> "$repo/$file"
    git -C "$repo" add -- "$file"
  done
  git -C "$repo" commit -q -m "$message"
}

# --- a history that pairs two files ----------------------------------------

REPO="$WORK/paired"
new_repo "$REPO"
change "$REPO" one src/a.txt src/b.txt
change "$REPO" two src/a.txt src/b.txt
change "$REPO" three src/a.txt docs/c.txt
change "$REPO" four lone.txt
change "$REPO" five src/b.txt docs/c.txt

got=$(cd "$REPO" && "$SCRIPT" src/a.txt)
expected=$(printf 'src/b.txt\ndocs/c.txt')
[ "$got" = "$expected" ] || fail "co-change of src/a.txt printed '$got', expected '$expected'"
ok "the file changed with it most often comes first, then the next"

got=$(cd "$REPO" && "$SCRIPT" src/a.txt src/b.txt)
[ "$got" = "docs/c.txt" ] || fail "co-change of two files printed '$got', expected docs/c.txt alone"
ok "the files asked about are never printed back"

got=$(cd "$REPO" && "$SCRIPT" lone.txt)
[ -z "$got" ] || fail "a file never changed with another printed '$got'"
ok "a file that always changed alone prints nothing"

got=$(cd "$REPO/src" && "$SCRIPT" a.txt)
[ "$got" = "$expected" ] || fail "run from a subfolder, co-change printed '$got'"
ok "a path given from a subfolder is read from the project root"

# --- only the last 200 commits count ---------------------------------------

REPO="$WORK/long"
new_repo "$REPO"
change "$REPO" old a.txt old.txt
i=0
while [ "$i" -lt 200 ]; do
  i=$((i + 1))
  change "$REPO" "filler $i" filler.txt
done
got=$(cd "$REPO" && "$SCRIPT" a.txt)
[ -z "$got" ] || fail "a pairing older than 200 commits was printed: '$got'"
change "$REPO" recent a.txt new.txt
got=$(cd "$REPO" && "$SCRIPT" a.txt)
[ "$got" = "new.txt" ] || fail "with the old pairing out of range, co-change printed '$got'"
ok "a pairing older than the last 200 commits is left out"

# --- origin/main is the history read, once it exists ------------------------

REPO="$WORK/local"
BARE="$WORK/remote.git"
new_repo "$REPO"
change "$REPO" shared a.txt b.txt
git init -q --bare "$BARE"
git -C "$REPO" remote add origin "$BARE"
git -C "$REPO" push -q origin main
git -C "$REPO" fetch -q origin
change "$REPO" local-only a.txt e.txt
got=$(cd "$REPO" && "$SCRIPT" a.txt)
[ "$got" = "b.txt" ] || fail "with origin/main present, co-change printed '$got', expected b.txt alone"
ok "a commit only this computer holds is left out once origin/main exists"

# --- nothing to read ----------------------------------------------------------

REPO="$WORK/empty"
new_repo "$REPO"
status=0
got=$(cd "$REPO" && "$SCRIPT" a.txt) || status=$?
[ "$status" -eq 0 ] || fail "a repository with no commits exited $status"
[ -z "$got" ] || fail "a repository with no commits printed '$got'"
ok "a repository with no history prints nothing and exits 0"

status=0
(cd "$WORK/paired" && "$SCRIPT" >/dev/null 2>&1) || status=$?
[ "$status" -eq 2 ] || fail "with no path given, co-change exited $status, expected 2"
ok "no path given is refused with exit 2"

mkdir "$WORK/plain"
status=0
(cd "$WORK/plain" && GIT_CEILING_DIRECTORIES="$WORK" "$SCRIPT" a.txt >/dev/null 2>&1) || status=$?
[ "$status" -eq 2 ] || fail "outside a repository, co-change exited $status, expected 2"
ok "a folder that is not a repository is refused with exit 2"

echo
echo "co-change-rehearsal.sh: all $pass checks passed"
