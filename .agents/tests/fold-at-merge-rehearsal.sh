#!/usr/bin/env sh
# fold-at-merge-rehearsal.sh: run the fold the merge step makes, in throwaway
# repositories, and read what it left.
#
# fold-at-merge.sh holds the rules as written. This half runs the shipped
# `bring-up-to-date.sh` and `fold-changes.py --main` against a bare repository
# standing in for GitHub, because the promises that matter are about history:
# two pieces merged one after the other leave both entries in CHANGELOG.md and
# nothing in `changes/`, a file that waited on `main` keeps the day it arrived
# there, a retry never writes an entry twice, and a merge from `main` that
# conflicts leaves the branch exactly as it was. A broken fold would lose or
# double the project's history, and nobody reads loose files to notice.
#
# A second clone stands in for GitHub's merge button: it merges the pull
# request's branch into `main` with a merge commit and pushes it to the bare
# repository. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SCRIPT="$ROOT/.agents/skills/section-builder/scripts/bring-up-to-date.sh"
FOLD="$ROOT/.agents/skills/sync/scripts/fold-changes.py"
WORKTREE="$ROOT/.agents/skills/implement/scripts/worktree.sh"
TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/CHANGELOG.md"

rs_init "Fold at the merge rehearsal"
[ -z "${RS_LIST:-}" ] || exit 0
[ -x "$SCRIPT" ] || rs_fail "bring-up-to-date.sh is missing or not runnable"
[ -x "$FOLD" ] || rs_fail "fold-changes.py is missing or not runnable"
command -v python3 >/dev/null 2>&1 || rs_fail "python3 is needed to run the fold"

W="$rs_dir/w"
mkdir -p "$W/no-hooks"
TODAY=$(date +%Y-%m-%d)

# setup <clone>: an identity, no signing, and none of the maintainer's hooks.
setup() {
  git -C "$1" config user.name Rehearsal
  git -C "$1" config user.email rehearsal@example.invalid
  git -C "$1" config commit.gpgsign false
  git -C "$1" config core.hooksPath "$W/no-hooks"
}
at() {
  # at <date> <git args...>: a commit or merge dated that day.
  when="$1T12:00:00"
  shift
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git "$@"
}
run() {
  # run [--no-fold] <folder>: the script's output in $out, its exit in $code.
  set +e
  out=$(sh "$SCRIPT" "$@" 2>&1)
  code=$?
  set -e
}

git init -q --bare -b main "$W/origin.git"
git clone -q "$W/origin.git" "$W/work" 2>/dev/null
setup "$W/work"
git clone -q "$W/origin.git" "$W/hub" 2>/dev/null
setup "$W/hub"

# hub_merge <date> <branch>: merge the pull request's branch on "GitHub".
hub_merge() {
  git -C "$W/hub" fetch -q origin
  git -C "$W/hub" checkout -q main 2>/dev/null || git -C "$W/hub" checkout -q -b main origin/main
  git -C "$W/hub" merge -q --ff-only origin/main
  at "$1" -C "$W/hub" merge -q --no-ff --no-edit -m "Merge $2" "origin/$2" ||
    rs_fail "merging $2 into main conflicted"
  git -C "$W/hub" push -q origin main
}
# hand_merge <date> <branch> <file> <text>: a pull request someone merged on
# GitHub by hand, so nothing folded its file.
hand_merge() {
  git -C "$W/hub" fetch -q origin
  git -C "$W/hub" checkout -q -B "$2" origin/main
  mkdir -p "$(dirname -- "$W/hub/$3")"
  printf '%s\n' "$4" > "$W/hub/$3"
  git -C "$W/hub" add -A
  at "$1" -C "$W/hub" commit -q -m "$2"
  git -C "$W/hub" push -q origin "$2"
  hub_merge "$1" "$2"
}
# piece <branch> <file> <text>: a piece branch cut from main in the work clone.
piece() {
  git -C "$W/work" fetch -q origin
  git -C "$W/work" checkout -q -b "$1" origin/main 2>/dev/null
  git -C "$W/work" branch -q --unset-upstream 2>/dev/null || true
  mkdir -p "$(dirname -- "$W/work/$2")"
  printf '%s\n\nhttps://example.invalid/pull/%s\n' "$3" "$1" > "$W/work/$2"
  git -C "$W/work" add -A
  git -C "$W/work" commit -q -m "$1"
  git -C "$W/work" push -q origin "$1"
}
on_origin() { git -C "$W/work" show "origin/$1:CHANGELOG.md"; }
count() { printf '%s\n' "$1" | grep -c "$2" || true; }
under() {
  # under <changelog> <day> <text>: the text sits under that day's heading.
  printf '%s\n' "$1" | awk -v day="## $2" -v text="$3" '
    /^## / { current = $0 }
    index($0, text) && current == day { found = 1 }
    END { exit found ? 0 : 1 }'
}

cp "$TEMPLATE" "$W/work/CHANGELOG.md"
printf 'one\ntwo\n' > "$W/work/app.txt"
git -C "$W/work" add -A
at 2026-07-01 -C "$W/work" commit -q -m "Founded"
git -C "$W/work" push -q origin main

# --- two pieces merged one after the other ------------------------------------

piece a changes/10-a.md "Invoices can be sent by email."
piece b changes/11-b.md "Invoices show the due date."
hand_merge 2026-07-02 hand changes/9-hand.md "Receipts can be printed."

git -C "$W/work" checkout -q a
run "$W/work"
if [ "$code" = 0 ]; then r=yes; else r=no; fi; rs_report "the first piece is brought up to date and folded (exit 0)" "$r"
printf '%s\n' "$out" | sed 's/^/    /'
if [ "$(printf '%s\n' "$out" | tail -1)" = "$(git -C "$W/work" rev-parse origin/a)" ]; then r=yes; else r=no; fi
rs_report "the last line is the pushed commit the check must pass on" "$r"
if [ "$(git -C "$W/work" rev-parse a)" = "$(git -C "$W/work" rev-parse origin/a)" ]; then r=yes; else r=no; fi
rs_report "the local branch is level with the pushed one" "$r"
if [ "$(git -C "$W/work" log -1 --format=%s origin/a)" = "Fold the changelog" ]; then r=yes; else r=no; fi
rs_report "the fold is its own commit, named Fold the changelog" "$r"
log=$(on_origin a)
if under "$log" "$TODAY" "sent by email"; then r=yes; else r=no; fi
rs_report "the piece's own file is dated today, the day of its merge" "$r"
if under "$log" 2026-07-02 "can be printed"; then r=yes; else r=no; fi
rs_report "a file merged by hand on GitHub is dated by the day it reached main" "$r"
if [ -z "$(git -C "$W/work" ls-tree --name-only origin/a changes/)" ]; then r=yes; else r=no; fi
rs_report "changes/ is empty on the branch after the fold" "$r"

hub_merge "$TODAY" a

git -C "$W/work" checkout -q b
run "$W/work"
if [ "$code" = 0 ]; then r=yes; else r=no; fi; rs_report "the second piece takes in the first and folds with no conflict" "$r"
log=$(on_origin b)
first=$(printf '%s\n' "$log" | grep -n 'due date' | cut -d: -f1)
second=$(printf '%s\n' "$log" | grep -n 'sent by email' | cut -d: -f1)
if [ -n "$first" ] && [ -n "$second" ] && [ "$first" -lt "$second" ] &&
  [ "$(count "$log" 'due date')" = 1 ] && [ "$(count "$log" 'sent by email')" = 1 ]; then r=yes; else r=no; fi
rs_report "CHANGELOG.md holds both entries once, newest first" "$r"

# The session dies after the fold is pushed and before the merge: the retry
# undoes the earlier fold, folds again, and writes nothing twice.
run "$W/work"
log=$(on_origin b)
if [ "$code" = 0 ] && [ "$(count "$log" 'due date')" = 1 ] &&
  [ "$(count "$log" 'sent by email')" = 1 ] && [ "$(count "$log" 'can be printed')" = 1 ]; then r=yes; else r=no; fi
rs_report "running it twice on one branch leaves one line per file" "$r"

hub_merge "$TODAY" b
git -C "$W/work" fetch -q origin
log=$(on_origin main)
if [ "$(count "$log" 'due date')" = 1 ] && [ "$(count "$log" 'sent by email')" = 1 ] &&
  [ -z "$(git -C "$W/work" ls-tree --name-only origin/main changes/)" ]; then r=yes; else r=no; fi
rs_report "after both merges main holds both lines and changes/ is empty" "$r"

# --- nothing waits ----------------------------------------------------------------

hand_merge 2026-07-03 main-moves app2.txt "a later change on main"
git -C "$W/work" fetch -q origin
git -C "$W/work" checkout -q -b c "origin/main~1" 2>/dev/null
git -C "$W/work" branch -q --unset-upstream 2>/dev/null || true
printf 'three\n' > "$W/work/other.txt"
git -C "$W/work" add -A
git -C "$W/work" commit -q -m "c, with no changes file"
git -C "$W/work" push -q origin c
before=$(git -C "$W/work" show origin/main:CHANGELOG.md)
run "$W/work"
folds=$(git -C "$W/work" log --format=%s origin/main..origin/c | grep -c '^Fold the changelog$' || true)
if [ "$code" = 0 ] && [ "$folds" = 0 ] &&
  git -C "$W/work" merge-base --is-ancestor origin/main origin/c &&
  [ "$(printf '%s\n' "$out" | tail -1)" = "$(git -C "$W/work" rev-parse origin/c)" ] &&
  [ "$(on_origin c)" = "$before" ]; then r=yes; else r=no; fi
rs_report "with nothing waiting it takes in main, commits no fold, and prints the head" "$r"

# --- a stale fold, with another merge in between ------------------------------------

hand_merge 2026-07-04 hand2 changes/12-hand2.md "Reports can be exported."
piece d changes/14-d.md "Clients can be archived."
piece e changes/15-e.md "Clients can be merged."
git -C "$W/work" checkout -q d
run "$W/work"
git -C "$W/work" checkout -q e
run "$W/work"
hub_merge "$TODAY" e
git -C "$W/work" checkout -q d
run "$W/work"
if [ "$code" = 0 ]; then r=yes; else r=no; fi; rs_report "a retry after another merge folded the same file succeeds" "$r"
hub_merge "$TODAY" d
git -C "$W/work" fetch -q origin
log=$(on_origin main)
if [ "$(count "$log" 'be exported')" = 1 ] && [ "$(count "$log" 'be archived')" = 1 ] &&
  [ "$(count "$log" 'be merged')" = 1 ] && under "$log" 2026-07-04 'be exported' &&
  [ -z "$(git -C "$W/work" ls-tree --name-only origin/main changes/)" ]; then r=yes; else r=no; fi
rs_report "the stale fold is undone first, so each entry appears once" "$r"

# --- --no-fold ----------------------------------------------------------------------

hand_merge 2026-07-05 hand3 changes/16-hand3.md "Notes can be pinned."
piece u changes/17-u.md "Notes can be coloured."
run --no-fold "$W/work"
if [ "$code" = 0 ] &&
  git -C "$W/work" merge-base --is-ancestor origin/main origin/u &&
  [ -n "$(git -C "$W/work" ls-tree --name-only origin/u changes/17-u.md)" ] &&
  [ -n "$(git -C "$W/work" ls-tree --name-only origin/u changes/16-hand3.md)" ]; then r=yes; else r=no; fi
rs_report "--no-fold takes in main and folds nothing" "$r"

# --- a conflict from main -----------------------------------------------------------

piece f changes/18-f.md "The app says one-and-a-half."
printf 'one and a half\ntwo\n' > "$W/work/app.txt"
git -C "$W/work" commit -q -am "f edits the app"
git -C "$W/work" push -q origin f
git -C "$W/hub" fetch -q origin
git -C "$W/hub" checkout -q -B conflict origin/main
printf 'one point five\ntwo\n' > "$W/hub/app.txt"
at 2026-07-06 -C "$W/hub" commit -q -am "conflict"
git -C "$W/hub" push -q origin conflict
hub_merge 2026-07-06 conflict
head=$(git -C "$W/work" rev-parse HEAD)
run "$W/work"
if [ "$code" = 1 ]; then r=yes; else r=no; fi; rs_report "a merge from main that conflicts exits 1" "$r"
if printf '%s\n' "$out" | grep -q 'app.txt'; then r=yes; else r=no; fi
rs_report "the conflicting file is named" "$r"
if [ "$(git -C "$W/work" rev-parse HEAD)" = "$head" ] &&
  [ "$(git -C "$W/work" symbolic-ref --short HEAD)" = f ] &&
  [ -z "$(git -C "$W/work" status --porcelain)" ] &&
  [ "$(git -C "$W/work" rev-parse origin/f)" = "$head" ]; then r=yes; else r=no; fi
rs_report "the branch's head and working tree are left as they were" "$r"

# --- origin out of reach, and no branch ----------------------------------------------

url=$(git -C "$W/work" remote get-url origin)
git -C "$W/work" remote set-url origin "$W/missing.git"
run "$W/work"
git -C "$W/work" remote set-url origin "$url"
if [ "$code" = 2 ] && [ "$(git -C "$W/work" rev-parse HEAD)" = "$head" ] &&
  [ -z "$(git -C "$W/work" status --porcelain)" ]; then r=yes; else r=no; fi
rs_report "origin out of reach exits 2 and changes nothing" "$r"

git -C "$W/work" checkout -q --detach
run "$W/work"
if [ "$code" = 2 ]; then r=yes; else r=no; fi; rs_report "a folder on no branch exits 2" "$r"
git -C "$W/work" checkout -q f

printf 'unsaved\n' >> "$W/work/app.txt"
run "$W/work"
if [ "$code" = 2 ] && [ "$(git -C "$W/work" rev-parse HEAD)" = "$head" ] &&
  grep -q unsaved "$W/work/app.txt"; then r=yes; else r=no; fi
rs_report "a folder with uncommitted work is not used, and the work stays" "$r"
git -C "$W/work" checkout -q -- app.txt

# --- the push is refused ---------------------------------------------------------------

piece r changes/19-r.md "Tags can be renamed."
hand_merge 2026-07-07 hand4 app3.txt "main moves again"
git clone -q "$W/origin.git" "$W/other" 2>/dev/null
setup "$W/other"
git -C "$W/other" checkout -q r
# Between the script's fetch and its push, somebody pushes to the branch.
mkdir -p "$W/race-hooks"
cat > "$W/race-hooks/post-merge" <<EOF
#!/bin/sh
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX
[ -e "$W/raced" ] && exit 0
: > "$W/raced"
printf 'from elsewhere\n' > "$W/other/elsewhere.txt"
git -C "$W/other" add -A
git -C "$W/other" commit -q -m "pushed meanwhile"
git -C "$W/other" push -q origin r
EOF
chmod +x "$W/race-hooks/post-merge"
git -C "$W/work" config core.hooksPath "$W/race-hooks"
git -C "$W/work" checkout -q r
head=$(git -C "$W/work" rev-parse HEAD)
main_before=$(git -C "$W/hub" rev-parse main)
run "$W/work"
git -C "$W/work" config core.hooksPath "$W/no-hooks"
if [ -e "$W/raced" ]; then r=yes; else r=no; fi; rs_report "the race happened between the fetch and the push" "$r"
if [ "$code" = 3 ]; then r=yes; else r=no; fi; rs_report "a refused push exits 3" "$r"
git -C "$W/work" fetch -q origin
if [ "$(git -C "$W/work" rev-parse origin/main)" = "$main_before" ] &&
  [ "$(git -C "$W/work" log -1 --format=%s origin/r)" = "pushed meanwhile" ]; then r=yes; else r=no; fi
rs_report "nothing merges and GitHub's branch holds only the other push" "$r"
run "$W/work"
if [ "$code" = 0 ] &&
  git -C "$W/work" merge-base --is-ancestor "$(git -C "$W/other" rev-parse HEAD)" origin/r; then r=yes; else r=no; fi
rs_report "asking again takes in the other push and folds" "$r"

# --- a commit only this computer holds ---------------------------------------------------

piece l changes/20-l.md "Labels can be sorted."
printf 'not pushed\n' > "$W/work/local-only.txt"
git -C "$W/work" add -A
git -C "$W/work" commit -q -m "a commit the pull request does not show"
head=$(git -C "$W/work" rev-parse HEAD)
remote_l=$(git -C "$W/work" rev-parse origin/l)
run "$W/work"
git -C "$W/work" fetch -q origin
if [ "$code" = 3 ] && [ "$(git -C "$W/work" rev-parse HEAD)" = "$head" ] &&
  [ "$(git -C "$W/work" rev-parse origin/l)" = "$remote_l" ]; then r=yes; else r=no; fi
rs_report "a commit the pull request does not show is never pushed by the fold (exit 3)" "$r"

# --- a stacked pull request whose base merged by squash ---------------------------------

piece v changes/24-v.md "Invoices can be duplicated."
git -C "$W/work" checkout -q -b w v
git -C "$W/work" branch -q --unset-upstream 2>/dev/null || true
printf 'Duplicated invoices keep their notes.\n\nhttps://example.invalid/pull/w\n' > "$W/work/changes/25-w.md"
git -C "$W/work" add -A
git -C "$W/work" commit -q -m w
git -C "$W/work" push -q origin w
git -C "$W/work" checkout -q v
run "$W/work"
git -C "$W/hub" fetch -q origin
git -C "$W/hub" checkout -q main
git -C "$W/hub" merge -q --ff-only origin/main
git -C "$W/hub" merge -q --squash origin/v >/dev/null
git -C "$W/hub" commit -q -m "Squash v"
git -C "$W/hub" push -q origin main
git -C "$W/work" checkout -q w
run "$W/work"
log=$(on_origin w)
if [ "$code" = 0 ] && [ "$(count "$log" 'be duplicated')" = 1 ] &&
  [ "$(count "$log" 'keep their notes')" = 1 ] &&
  [ -z "$(git -C "$W/work" ls-tree --name-only origin/w changes/)" ]; then r=yes; else r=no; fi
rs_report "a stacked branch after a squash-merged base writes the base's entry once" "$r"

# --- the branch is not on this computer ------------------------------------------------

piece s changes/21-s.md "Tasks can be starred."
git clone -q "$W/origin.git" "$W/fresh" 2>/dev/null
setup "$W/fresh"
(cd "$W/fresh" && sh "$WORKTREE" open 21-s s origin/s >/dev/null)
wt="$W/fresh/.agents/worktrees/21-s"
if [ -d "$wt" ] && [ "$(git -C "$wt" rev-parse HEAD)" = "$(git -C "$W/fresh" rev-parse origin/s)" ]; then r=yes; else r=no; fi
rs_report "a worktree made from origin/<branch> starts at the pull request's head" "$r"
run "$wt"
if [ "$code" = 0 ] && [ "$(git -C "$W/fresh" symbolic-ref --short HEAD)" = main ] &&
  under "$(git -C "$wt" show HEAD:CHANGELOG.md)" "$TODAY" "be starred"; then r=yes; else r=no; fi
rs_report "the fold runs in that worktree and the main folder stays on main" "$r"

# --- a project founded before changes/ existed -----------------------------------------

git init -q --bare -b main "$W/old.git"
git clone -q "$W/old.git" "$W/old" 2>/dev/null
setup "$W/old"
printf '# Changelog\n\n## 2026-06-01\n\n- Founded.\n' > "$W/old/CHANGELOG.md"
git -C "$W/old" add -A
at 2026-06-01 -C "$W/old" commit -q -m "Founded"
git -C "$W/old" push -q origin main
git -C "$W/old" checkout -q -b t
printf 'x\n' > "$W/old/x.txt"
git -C "$W/old" add -A
git -C "$W/old" commit -q -m t
git -C "$W/old" push -q origin t
run "$W/old"
if [ "$code" = 0 ] && [ ! -e "$W/old/changes" ] &&
  [ "$(git -C "$W/old" show origin/t:CHANGELOG.md)" = "$(printf '# Changelog\n\n## 2026-06-01\n\n- Founded.')" ]; then r=yes; else r=no; fi
rs_report "a project with no changes/ folder gets nothing written" "$r"

# --- the checkpoint route ---------------------------------------------------------------

git init -q -b main "$W/solo"
setup "$W/solo"
cp "$TEMPLATE" "$W/solo/CHANGELOG.md"
git -C "$W/solo" add -A
at 2026-07-01 -C "$W/solo" commit -q -m "Founded"
mkdir -p "$W/solo/changes"
printf 'Photos can be cropped.\n\nIssue 30\n' > "$W/solo/changes/30-crop.md"
git -C "$W/solo" add -A
git -C "$W/solo" commit -q -m "Crop photos"
(cd "$W/solo" && python3 "$FOLD" >/dev/null && git add CHANGELOG.md && git commit -q -m "Fold the changelog")
if under "$(cat "$W/solo/CHANGELOG.md")" "$TODAY" "be cropped" &&
  [ ! -e "$W/solo/changes/30-crop.md" ] && [ -z "$(git -C "$W/solo" status --porcelain)" ] &&
  [ "$(git -C "$W/solo" log -1 --format=%s)" = "Fold the changelog" ] &&
  [ "$(git -C "$W/solo" log -2 --format=%s | tail -1)" = "Crop photos" ]; then r=yes; else r=no; fi
rs_report "on the checkpoint route the piece's file is folded in a second checkpoint commit" "$r"

rs_done
