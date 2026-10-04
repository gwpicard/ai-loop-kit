#!/usr/bin/env sh
# bring-up-to-date.sh: bring a pull request's branch up to date with `main` and
# fold the waiting changelog files, just before the merge.
#
# The merge step in references/merge.md runs this after the yes that names the
# merge and before `gh pr merge`. Merges are made one at a time, so the branch
# it prepares holds everything already merged, and the fold never conflicts
# with another piece's.
#
# Usage: bring-up-to-date.sh [--no-fold] <folder>
#   folder     a working folder on the pull request's branch, with no
#              uncommitted change
#   --no-fold  take in `main` but fold nothing, for when an earlier records
#              pull request that folded files is still open
#
# In order, it:
# 1. fetches `origin`, and starts from GitHub's copy of the branch, which the
#    pull request shows; it stops where this computer holds commits that copy
#    does not;
# 2. undoes, with `git revert`, each `Fold the changelog` commit on the branch
#    that `main` does not hold and nothing has undone yet, so an older fold is
#    never merged beside a newer one;
# 3. takes in `origin/main` with a merge commit, never a rebase;
# 4. runs the sync skill's `scripts/fold-changes.py --main origin/main`, which
#    never writes an entry CHANGELOG.md already holds, and commits what it
#    folded as `Fold the changelog`;
# 5. pushes to the branch on `origin`, never with force, and moves the local
#    branch to match.
#
# It works on a detached copy of the branch and moves the branch only once the
# push has landed, so a stop at any point leaves the branch exactly as it was.
# It never force-pushes, never resets, and never touches `main`.
#
# The last line printed on success is the commit the project check must pass
# on. Exit codes:
#   0  ready: wait for the project check on that commit
#   1  a merge from `main`, or the undoing of an older fold, conflicted; each
#      conflicting file is named and the branch is as it was
#   2  nothing changed: `origin` could not be reached, the folder is not on a
#      pull request's branch, or it holds uncommitted work
#   3  the push was refused, or this computer holds commits on the branch that
#      the pull request does not; the branch is as it was and nothing merges

set -u

say() { printf '%s\n' "$*"; }
stop() {
  code=$1
  shift
  printf 'bring-up-to-date: %s\n' "$*" >&2
  exit "$code"
}

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
FOLD="$HERE/../../sync/scripts/fold-changes.py"

fold=yes
if [ "${1:-}" = "--no-fold" ]; then
  fold=no
  shift
fi
[ $# -eq 1 ] || stop 2 "usage: bring-up-to-date.sh [--no-fold] <folder>"
cd -- "$1" 2>/dev/null || stop 2 "cannot open $1; nothing changed"
top=$(git rev-parse --show-toplevel 2>/dev/null) || stop 2 "$1 is not inside a git project; nothing changed"
cd -- "$top" || stop 2 "cannot open $top; nothing changed"

branch=$(git symbolic-ref --short -q HEAD) || stop 2 "the folder is not on a branch; nothing changed"
[ "$branch" != main ] || stop 2 "the folder is on main, not on a pull request's branch; nothing changed"
[ -z "$(git status --porcelain)" ] ||
  stop 2 "the folder holds uncommitted work, so it is not used for the merge; nothing changed"
if [ "$fold" = yes ]; then
  [ -f "$FOLD" ] || stop 2 "the sync skill's scripts/fold-changes.py is not beside this skill; nothing changed"
  command -v python3 >/dev/null 2>&1 || stop 2 "python3 is needed for the fold; nothing changed"
fi

git fetch -q origin 2>/dev/null || stop 2 "origin could not be reached; nothing changed"
remote=$(git rev-parse -q --verify "refs/remotes/origin/$branch^{commit}") ||
  stop 2 "origin has no branch $branch; nothing changed"
git rev-parse -q --verify "refs/remotes/origin/main^{commit}" >/dev/null ||
  stop 2 "origin has no main; nothing changed"
local_head=$(git rev-parse HEAD)

# Start from GitHub's copy, the one the pull request shows and the yes covered.
# A commit only this computer holds was never in it, so the merge waits.
if git merge-base --is-ancestor "$local_head" "$remote"; then
  start=$remote
else
  stop 3 "this computer holds commits on $branch that the pull request does not, so the merge waits until they are pushed or dropped; nothing changed"
fi

# back_out <code> <message>: return to the branch as it was, and stop.
back_out() {
  git checkout -q "$branch" 2>/dev/null ||
    printf 'bring-up-to-date: could not return to %s; the folder is on a detached copy\n' "$branch" >&2
  stop "$@"
}

git checkout -q --detach "$start" 2>/dev/null || stop 2 "could not start from $branch; nothing changed"

# 2. Undo each earlier fold main does not hold, newest first.
bodies=$(git log --format=%B "refs/remotes/origin/main..HEAD")
stale=$(git log --format='%H %s' "refs/remotes/origin/main..HEAD" | while read -r sha subject; do
  [ "$subject" = "Fold the changelog" ] || continue
  case $bodies in (*"This reverts commit $sha"*) continue ;; esac
  printf '%s\n' "$sha"
done)
for sha in $stale; do
  if ! git revert --no-edit "$sha" >/dev/null 2>&1; then
    files=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
    git revert --abort >/dev/null 2>&1
    back_out 1 "undoing the earlier fold $(git rev-parse --short "$sha") conflicted in: ${files% }. The branch is as it was."
  fi
  say "Undid the earlier fold $(git rev-parse --short "$sha"), since main does not hold it."
done

# 3. Take in main with a merge commit.
before=$(git rev-parse HEAD)
if ! git merge -q --no-edit -m "Merge main into $branch" refs/remotes/origin/main >/dev/null 2>&1; then
  files=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
  git merge --abort >/dev/null 2>&1
  back_out 1 "the merge from main conflicted in: ${files% }. The branch is as it was."
fi
if [ "$(git rev-parse HEAD)" = "$before" ]; then
  say "The branch already holds main."
else
  say "Took in main."
fi

# 4. Fold what waits in changes/.
if [ "$fold" = yes ]; then
  if ! folded=$(python3 "$FOLD" --main refs/remotes/origin/main); then
    back_out 2 "the fold could not run; nothing was pushed"
  fi
  if [ -n "$folded" ]; then
    printf '%s\n' "$folded"
    git add -- CHANGELOG.md
    git commit -q -m "Fold the changelog" || back_out 2 "the fold could not be committed; nothing was pushed"
  else
    say "Nothing waits in changes/."
  fi
else
  say "Folded nothing, as asked."
fi

# 5. Push, then move the local branch to match.
new=$(git rev-parse HEAD)
if [ "$new" != "$remote" ]; then
  if ! git push -q origin "HEAD:refs/heads/$branch" >/dev/null 2>&1; then
    back_out 3 "GitHub refused the push to $branch, most likely because somebody pushed to it meanwhile. Nothing merges; asking again takes their commit in."
  fi
  say "Pushed $branch."
fi
if [ "$new" != "$local_head" ]; then
  git update-ref -m "bring-up-to-date" "refs/heads/$branch" "$new" "$local_head" ||
    back_out 2 "could not move $branch to $new, though it was pushed"
fi
git checkout -q "$branch" || stop 2 "could not return to $branch"
say "$new"
