#!/usr/bin/env sh
# recheck-before-merge-rehearsal.sh: show, in a throwaway repository, why every
# merge brings the branch up to date and checks it again first.
#
# recheck-before-merge.sh holds the rule as written. This half proves the rule
# is needed and that the shipped `bring-up-to-date.sh` does its part. Two
# branches each pass the project's tiny test alone: one renames a function, the
# other adds a call to its old name. After the first merges, the script brings
# the second up to date, and the test on the updated branch fails. That red is
# the one a check against the older `main` never sees. The script itself never
# merges anything into `main`.
#
# It also holds the exception: where `main` has not moved and nothing is left
# to fold, the script makes no commit and prints the head the branch already
# has, so the green check already there stands.
#
# A bare repository stands in for GitHub, and a second clone stands in for its
# merge button. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"

SCRIPT="$ROOT/kit/scripts/bring-up-to-date.sh"

rs_init "Re-check before the merge rehearsal"
[ -z "${RS_LIST:-}" ] || exit 0
[ -x "$SCRIPT" ] || rs_fail "bring-up-to-date.sh is missing or not runnable"
command -v python3 >/dev/null 2>&1 || rs_fail "python3 is needed to run the fold"

W="$rs_dir/w"
mkdir -p "$W/no-hooks"

setup() {
  git -C "$1" config user.name Rehearsal
  git -C "$1" config user.email rehearsal@example.invalid
  git -C "$1" config commit.gpgsign false
  git -C "$1" config core.hooksPath "$W/no-hooks"
}
run() {
  # run <folder>: the script's output in $out, its exit in $code.
  set +e
  out=$(sh "$SCRIPT" "$@" 2>&1)
  code=$?
  set -e
}
passes() {
  # passes <folder>: the project's test, run the way its check would.
  (cd "$1" && sh test.sh >/dev/null 2>&1)
}

git init -q --bare -b main "$W/origin.git"
git clone -q "$W/origin.git" "$W/work" 2>/dev/null
setup "$W/work"
git clone -q "$W/origin.git" "$W/hub" 2>/dev/null
setup "$W/hub"

# The project: one function, and a test that runs every file in tests/.
cd "$W/work"
git checkout -q -b main
printf 'greet() { printf "hello %%s\\n" "$1"; }\n' > lib.sh
mkdir -p tests
printf 'set -e\n. ./lib.sh\nfor t in tests/*.sh; do . "$t"; done\n' > test.sh
printf '[ "$(greet Ada)" = "hello Ada" ]\n' > tests/greet.sh
printf '# Changelog\n' > CHANGELOG.md
git add -A
git commit -q -m "Start"
git push -q origin main
start=$(git rev-parse HEAD)
passes "$W/work" || rs_fail "the starting project should pass its own test"

# Branch one renames greet to hello, and its test with it. It carries no
# changelog file, as a pull request opened outside the kit would not.
git checkout -q -b rename main
printf 'hello() { printf "hello %%s\\n" "$1"; }\n' > lib.sh
printf '[ "$(hello Ada)" = "hello Ada" ]\n' > tests/greet.sh
git add -A
git commit -q -m "Rename greet to hello"
git push -q origin rename
passes "$W/work" || rs_fail "the renaming branch should pass its test alone"
rs_ok "the renaming branch passes alone"

# Branch two adds a farewell that calls greet by its old name.
git checkout -q -b farewell main
printf 'farewell() { printf "%%s, goodbye\\n" "$(greet "$1")"; }\n' > farewell.sh
printf '. ./farewell.sh\n[ "$(farewell Bob)" = "hello Bob, goodbye" ]\n' > tests/farewell.sh
mkdir -p changes
printf 'Added a farewell.\n' > changes/farewell.md
git add -A
git commit -q -m "Add a farewell that greets first"
git push -q origin farewell
passes "$W/work" || rs_fail "the farewell branch should pass its test alone"
rs_ok "the farewell branch passes alone"
farewell_head=$(git rev-parse HEAD)

# GitHub merges the first pull request.
git -C "$W/hub" fetch -q origin
git -C "$W/hub" checkout -q -B main origin/main
git -C "$W/hub" merge -q --no-ff --no-edit -m "Merge rename" origin/rename
git -C "$W/hub" push -q origin main
main_after_first=$(git -C "$W/hub" rev-parse HEAD)

# The second branch's green check is against the older main. Bring it up to
# date, as the merge step does before every merge.
run "$W/work"
[ "$code" -eq 0 ] || rs_fail "bringing the farewell branch up to date should succeed (exit $code): $out"
rs_ok "the script brings the second branch up to date"
new_head=$(printf '%s\n' "$out" | tail -n 1)
[ "$new_head" = "$(git -C "$W/work" rev-parse HEAD)" ] ||
  rs_fail "the last line should be the branch's new head"
[ "$new_head" != "$farewell_head" ] || rs_fail "the branch should have taken in main"
git -C "$W/work" merge-base --is-ancestor "$main_after_first" HEAD ||
  rs_fail "the updated branch should hold the first merge"
rs_ok "its last line is the new head, which holds the first merge"

if passes "$W/work"; then
  rs_fail "the updated branch passed, so the rehearsal does not show two green pieces failing together"
fi
rs_ok "the test on the updated branch fails: two pieces green alone fail together"

# The pieces merged since the branch's last green check, as the merge step reads them.
old_base=$(git -C "$W/work" merge-base "$farewell_head" origin/main)
[ "$old_base" = "$start" ] || rs_fail "the old base should be where the checked head met main"
since=$(git -C "$W/work" log --first-parent --format=%s "$old_base..origin/main")
[ "$since" = "Merge rename" ] || rs_fail "the pieces merged since should be the rename alone, got: $since"
rs_ok "the log from the old base names the rename as what merged since"

git -C "$W/hub" fetch -q origin
[ "$(git -C "$W/hub" rev-parse origin/main)" = "$main_after_first" ] ||
  rs_fail "the script moved main; it must never merge anything itself"
rs_ok "main is where the first merge left it: the script merged nothing"

# The exception: main has not moved and nothing waits to fold.
git -C "$W/work" checkout -q -b docs origin/main
printf 'A note.\n' > "$W/work/NOTE.txt"
git -C "$W/work" add NOTE.txt
git -C "$W/work" commit -q -m "Add a note"
git -C "$W/work" push -q origin docs
docs_head=$(git -C "$W/work" rev-parse HEAD)
before_log=$(git -C "$W/work" rev-list --count HEAD)

run "$W/work"
[ "$code" -eq 0 ] || rs_fail "a branch already holding main should come back ready (exit $code): $out"
[ "$(printf '%s\n' "$out" | tail -n 1)" = "$docs_head" ] ||
  rs_fail "with main unmoved and nothing to fold, the last line should be the unchanged head"
[ "$(git -C "$W/work" rev-list --count HEAD)" = "$before_log" ] ||
  rs_fail "with main unmoved and nothing to fold, the script should make no commit"
git -C "$W/work" fetch -q origin
[ "$(git -C "$W/work" rev-parse origin/docs)" = "$docs_head" ] ||
  rs_fail "with nothing new, the script should push nothing"
rs_ok "main unmoved and nothing to fold: no commit, no push, and the unchanged head is printed"

rs_done
