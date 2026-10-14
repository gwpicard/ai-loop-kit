#!/usr/bin/env sh
# bring-up-to-date.sh: bring a combined branch up to date with `main` and fold the waiting
# changelog files, with merge commits and nothing else.
#
# The run's combined branch (loop/run/integrate.py) is brought up to date when `main` moved after
# the final combined check, and the check runs again on the result. A pull request's branch is
# brought up to date the same way, just before the merge. Merges are made one at a time, so the
# branch it prepares holds everything already merged.
#
# Usage: bring-up-to-date.sh [--no-fold] [--no-push] <folder>
#   folder     a working folder on the combined branch, with no uncommitted change
#   --no-fold  take in `main` but fold nothing, for when an earlier records
#              pull request that folded files is still open
#   --no-push  make the commits and move nothing on `origin`. The gate pushes the branch
#              afterwards, as the App, through its push step, which scans for secrets first.
#              The branch needs no copy on `origin` in this mode.
#
# In order, it:
# 1. fetches `origin`, and starts from GitHub's copy of the branch when it has one, which
#    the pull request shows; it stops where this computer holds commits that copy does not;
# 2. takes in `origin/main` with a merge commit, never a rebase, never a revert and never a
#    reset. When the merge conflicts in CHANGELOG.md alone, it takes the changelog of `main`
#    and puts back the entries only this branch holds, with `fold-changes.py --reapply`, so
#    two folds never clash and nothing is undone. Any other conflict stops it;
# 3. runs `fold-changes.py --main origin/main`, which never writes an entry CHANGELOG.md
#    already holds, and commits what it folded as `Fold the changelog`;
# 4. pushes to the branch on `origin`, never with force, and moves the local branch to
#    match (unless --no-push).
#
# It works on a detached copy of the branch and moves the branch only once the
# push has landed, so a stop at any point leaves the branch exactly as it was.
# It never force-pushes, never resets, never reverts and never touches `main`.
#
# The last line printed on success is the commit the project check must pass
# on. Exit codes:
#   0  ready: wait for the project check on that commit
#   1  a merge from `main` conflicted, or the conflict in CHANGELOG.md could not be settled;
#      each conflicting file is named and the branch is as it was
#   2  nothing changed: `origin` could not be reached, the folder is not on a
#      branch, or it holds uncommitted work
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
FOLD="$HERE/fold-changes.py"

fold=yes
push=yes
while [ $# -gt 0 ]; do
  case $1 in
    --no-fold) fold=no; shift ;;
    --no-push) push=no; shift ;;
    --) shift; break ;;
    *) break ;;
  esac
done
[ $# -eq 1 ] || stop 2 "usage: bring-up-to-date.sh [--no-fold] [--no-push] <folder>"
cd -- "$1" 2>/dev/null || stop 2 "cannot open $1; nothing changed"
top=$(git rev-parse --show-toplevel 2>/dev/null) || stop 2 "$1 is not inside a git project; nothing changed"
cd -- "$top" || stop 2 "cannot open $top; nothing changed"

branch=$(git symbolic-ref --short -q HEAD) || stop 2 "the folder is not on a branch; nothing changed"
[ "$branch" != main ] || stop 2 "the folder is on main, not on a combined branch or a pull request's branch; nothing changed"
[ -z "$(git status --porcelain)" ] ||
  stop 2 "the folder holds uncommitted work, so it is not used for the merge; nothing changed"
if [ "$fold" = yes ]; then
  [ -f "$FOLD" ] || stop 2 "fold-changes.py is not beside bring-up-to-date.sh in the kit's scripts folder; nothing changed"
  command -v python3 >/dev/null 2>&1 || stop 2 "python3 is needed for the fold; nothing changed"
fi

git fetch -q origin 2>/dev/null || stop 2 "origin could not be reached; nothing changed"
git rev-parse -q --verify "refs/remotes/origin/main^{commit}" >/dev/null ||
  stop 2 "origin has no main; nothing changed"
local_head=$(git rev-parse HEAD)
remote=$(git rev-parse -q --verify "refs/remotes/origin/$branch^{commit}" 2>/dev/null) || remote=""
if [ -z "$remote" ] && [ "$push" = yes ]; then
  stop 2 "origin has no branch $branch; nothing changed. Push it first, or ask for --no-push"
fi

# Start from GitHub's copy, the one the pull request shows and the yes covered.
# A commit only this computer holds was never in it, so the merge waits. A branch with no copy
# on origin starts from this computer's head, and only with --no-push.
if [ -z "$remote" ]; then
  start=$local_head
elif git merge-base --is-ancestor "$local_head" "$remote"; then
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

# 2. Take in main with a merge commit.
before=$(git rev-parse HEAD)
if ! git merge -q --no-edit -m "Merge main into $branch" refs/remotes/origin/main >/dev/null 2>&1; then
  files=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
  if [ "${files% }" = "CHANGELOG.md" ] && [ "$fold" = yes ]; then
    # Two folds changed the same lines. Main's changelog stands, and this branch's own entries go
    # back in under their day and section. Nothing is reverted.
    if git checkout -q --theirs -- CHANGELOG.md && git add -- CHANGELOG.md &&
      git commit -q --no-edit >/dev/null 2>&1; then
      reapplied=$(python3 "$FOLD" --reapply "$start" --main refs/remotes/origin/main) ||
        back_out 1 "the entries of $branch could not be put back into CHANGELOG.md. The branch is as it was."
      if [ -n "$reapplied" ]; then
        printf '%s\n' "$reapplied"
        git add -- CHANGELOG.md
        git commit -q -m "Fold the changelog" || back_out 2 "the changelog could not be committed; nothing was pushed"
      fi
    else
      git merge --abort >/dev/null 2>&1
      back_out 1 "the merge from main conflicted in: ${files% }, and the conflict could not be settled. The branch is as it was."
    fi
  else
    git merge --abort >/dev/null 2>&1
    back_out 1 "the merge from main conflicted in: ${files% }. The branch is as it was."
  fi
fi
if [ "$(git rev-parse HEAD)" = "$before" ]; then
  say "The branch already holds main."
else
  say "Took in main."
fi

# 3. Fold what waits in changes/.
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

# 4. Push, then move the local branch to match.
new=$(git rev-parse HEAD)
if [ "$push" = yes ] && [ "$new" != "$remote" ]; then
  if ! git push -q origin "HEAD:refs/heads/$branch" >/dev/null 2>&1; then
    back_out 3 "GitHub refused the push to $branch, most likely because somebody pushed to it meanwhile. Nothing merges; asking again takes their commit in."
  fi
  say "Pushed $branch."
fi
if [ "$push" = no ]; then
  say "Pushed nothing, as asked."
fi
if [ "$new" != "$local_head" ]; then
  git update-ref -m "bring-up-to-date" "refs/heads/$branch" "$new" "$local_head" ||
    back_out 2 "could not move $branch to $new, though it was pushed"
fi
git checkout -q "$branch" || stop 2 "could not return to $branch"
say "$new"
