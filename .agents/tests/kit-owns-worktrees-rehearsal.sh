#!/usr/bin/env sh
# kit-owns-worktrees-rehearsal.sh: run the worktree script in a throwaway
# project and read what it did.
#
# kit-owns-worktrees.sh holds the rules as written. This half runs the shipped
# `worktree.sh` the rules name, because the promises that matter are about what
# happens on disk: git ignores the folder, the .env arrives as a link and never
# as a copy, the main folder never moves off its branch, and a worktree is
# removed after its pull request closes only when nothing in it is unsaved.
# Removing the wrong worktree loses somebody's work, and nothing would say so.
#
# It also runs the worktree-links line, which links ignored build files such
# as fonts into each worktree and refuses confidential, env, tracked, outside
# and missing paths by name, and a sibling worktree standing for another
# tool's, which the script must never list, change or remove.
#
# A stand-in for the GitHub command line tool answers the pull request lookup
# from a small file, and a wrapper around git records every call, so a forced
# removal is caught even if it happened to succeed. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SCRIPT="$ROOT/.agents/skills/implement/scripts/worktree.sh"
IGNORE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/gitignore"

pass=0
fail() { echo "FAIL: $1" >&2; exit 1; }
ok() { echo "  ok: $1"; pass=$((pass + 1)); }
check() { if [ "$2" = yes ]; then ok "$1"; else fail "$1"; fi; }

[ -f "$SCRIPT" ] || fail "there is no worktree script at $SCRIPT"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

REAL_GIT=$(command -v git)
mkdir -p "$WORK/bin"
# Only the script's own calls are logged: `run` marks them. FAKE_GIT_VERSION
# stands in for an older Git.
cat > "$WORK/bin/git" <<SH
#!/usr/bin/env sh
[ -z "\${WT_REHEARSAL_LOG:-}" ] || printf '%s\n' "\$*" >> "$WORK/git.log"
if [ -n "\${FAKE_GIT_VERSION:-}" ] && [ "\$1" = "--version" ]; then
  echo "git version \$FAKE_GIT_VERSION"
  exit 0
fi
exec "$REAL_GIT" "\$@"
SH
chmod +x "$WORK/bin/git"

# The stand-in answers `gh pr list --head <branch> ...` from $WORK/prs, whose
# lines are "<branch> <state> <head commit>". GH_FAIL makes it fail, as a
# signed-out tool does.
cat > "$WORK/bin/gh" <<SH
#!/usr/bin/env sh
printf '%s\n' "\$*" >> "$WORK/gh.log"
[ -z "\${GH_FAIL:-}" ] || exit 1
[ "\$1 \$2" = "pr list" ] || exit 1
head=""
while [ \$# -gt 0 ]; do
  [ "\$1" = "--head" ] && head=\$2
  shift
done
python3 - "\$head" "$WORK/prs" <<'PY'
import json, os, sys
head, path = sys.argv[1:3]
out = []
if os.path.exists(path):
    for line in open(path):
        parts = line.split()
        if len(parts) >= 2 and parts[0] == head:
            out.append({"state": parts[1], "headRefOid": parts[2] if len(parts) > 2 else ""})
print(json.dumps(out))
PY
SH
chmod +x "$WORK/bin/gh"
PATH="$WORK/bin:$PATH"
export PATH
: > "$WORK/prs"

run() {
  # run <project> <args...>: the script from the project's main folder.
  dir=$1
  shift
  (cd "$dir" && WT_REHEARSAL_LOG=1 && export WT_REHEARSAL_LOG && sh "$SCRIPT" "$@")
}
pr() { printf '%s\n' "$*" >> "$WORK/prs"; }
branch_of() { git -C "$1" symbolic-ref --short HEAD; }

# project <dir> <gitignore>: a project with a remote, main pushed, and a .env
# holding a secret the rehearsal never prints.
project() {
  git init -q --bare -b main "$1.git"
  git init -q -b main "$1"
  git -C "$1" config user.email "worktree@example.invalid"
  git -C "$1" config user.name "Worktree rehearsal"
  git -C "$1" config commit.gpgsign false
  cp "$2" "$1/.gitignore"
  # A Next.js project keeps its keys in .env.local, and ignores it.
  echo ".env.local" >> "$1/.gitignore"
  echo "tool" > "$1/tool.txt"
  echo "SAMPLE_KEY=" > "$1/.env.example"
  git -C "$1" add -A
  git -C "$1" commit -q -m "Project"
  git -C "$1" remote add origin "$1.git"
  git -C "$1" push -q -u origin main 2>/dev/null
  echo "SECRET_KEY=not-a-real-secret" > "$1/.env"
  echo "LOCAL_KEY=not-a-real-secret" > "$1/.env.local"
}

# commit_in <worktree> <file>: one saved change in a worktree.
commit_in() {
  echo "$2" > "$1/$2"
  git -C "$1" add "$2"
  git -C "$1" commit -q -m "Build $2"
}

P="$WORK/project"
project "$P" "$IGNORE"

echo "== Opening a worktree =="

out=$(run "$P" open 12-invoice-list 12-invoice-list origin/main)
W="$P/.agents/worktrees/12-invoice-list"
[ -d "$W" ] && r=yes || r=no
check "a run's piece gets a worktree at .agents/worktrees/<number>-<name>" "$r"
[ "$(branch_of "$W")" = 12-invoice-list ] && r=yes || r=no
check "the worktree is on the piece's branch" "$r"
[ "$(branch_of "$P")" = main ] && r=yes || r=no
check "the main folder stays on main" "$r"
git -C "$P" check-ignore -q .agents/worktrees/12-invoice-list && r=yes || r=no
check "git ignores the worktree folder" "$r"
[ -z "$(git -C "$P" status --porcelain)" ] && r=yes || r=no
check "nothing tracked changed in the main folder" "$r"
[ -z "$(git -C "$W" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" ] && r=yes || r=no
check "the piece's branch does not track main" "$r"

[ -L "$W/.env" ] && [ -L "$W/.env.local" ] && r=yes || r=no
check "the worktree's .env and .env.local are links" "$r"
[ "$(readlink "$W/.env")" = "../../../.env" ] && \
  [ "$(cd "$W/../../.." && pwd -P)" = "$(cd "$P" && pwd -P)" ] && r=yes || r=no
check "the link leads to the main folder's .env" "$r"
cmp -s "$W/.env" "$P/.env" && r=yes || r=no
check "the worktree reads the main folder's secret through the link" "$r"
[ ! -L "$W/.env.example" ] && [ -f "$W/.env.example" ] && r=yes || r=no
check "a tracked .env.example is checked out, not linked" "$r"
copies=$(find "$WORK" -name '.env' -type f | grep -v "^$P/.env\$" || true)
[ -z "$copies" ] && r=yes || r=no
check "no copy of .env exists outside the main folder" "$r"
case $out in *"Linked"*) r=yes ;; *) r=no ;; esac
check "it says the .env was linked" "$r"
[ -z "$(git -C "$W" status --porcelain)" ] && r=yes || r=no
check "the links are not unsaved work" "$r"

echo "== A piece that stacks on another =="

commit_in "$W" days.txt
run "$P" open 13-overdue-list 13-overdue-list 12-invoice-list >/dev/null
S="$P/.agents/worktrees/13-overdue-list"
git -C "$S" merge-base --is-ancestor 12-invoice-list HEAD && r=yes || r=no
check "a stacked piece's worktree starts from its base piece's branch" "$r"
[ "$(branch_of "$P")" = main ] && r=yes || r=no
check "the main folder is still on main" "$r"

echo "== What counts as unsaved =="

run "$P" unsaved "$W" >/dev/null 2>&1 && r=no || r=yes
check "a commit missing from the remote is unsaved work" "$r"
git -C "$W" push -q -u origin 12-invoice-list 2>/dev/null
run "$P" unsaved "$W" >/dev/null 2>&1 && r=yes || r=no
check "once pushed, nothing is unsaved" "$r"
echo "draft" > "$W/draft.txt"
run "$P" unsaved "$W" >/dev/null 2>&1 && r=no || r=yes
check "a new file git does not ignore is unsaved work" "$r"
rm -f "$W/draft.txt"

echo "== A path already there =="

out=$(run "$P" open 12-invoice-list 12-invoice-list origin/main) && code=0 || code=$?
[ "$code" -eq 0 ] && case $out in *Reused*) true ;; *) false ;; esac && r=yes || r=no
check "a worktree on the same branch with nothing unsaved is reused" "$r"
out=$(run "$P" open 12-invoice-list 99-something-else origin/main) && code=0 || code=$?
[ "$code" -eq 1 ] && case $out in *"Skip this piece"*"12-invoice-list"*) true ;; *) false ;; esac && r=yes || r=no
check "a worktree on another branch is named and the piece skipped" "$r"
echo "half done" > "$W/half.txt"
out=$(run "$P" open 12-invoice-list 12-invoice-list origin/main) && code=0 || code=$?
[ "$code" -eq 1 ] && [ -f "$W/half.txt" ] && case $out in *"unsaved work"*) true ;; *) false ;; esac && r=yes || r=no
check "a worktree holding unsaved work is named, kept, and the piece skipped" "$r"
out=$(run "$P" open --resume 12-invoice-list 12-invoice-list origin/main) && code=0 || code=$?
[ "$code" -eq 1 ] && [ -f "$W/half.txt" ] && r=yes || r=no
check "a resumed piece with uncommitted changes is not reused over them" "$r"
rm -f "$W/half.txt"
commit_in "$W" more.txt
out=$(run "$P" open --resume 12-invoice-list 12-invoice-list origin/main) && code=0 || code=$?
[ "$code" -eq 0 ] && r=yes || r=no
check "a resumed piece reuses its worktree over its own unpushed commits" "$r"
git -C "$W" push -q origin 12-invoice-list 2>/dev/null
mkdir -p "$P/.agents/worktrees/14-stray"
echo x > "$P/.agents/worktrees/14-stray/file"
out=$(run "$P" open 14-stray 14-stray origin/main) && code=0 || code=$?
[ "$code" -eq 1 ] && [ -f "$P/.agents/worktrees/14-stray/file" ] && r=yes || r=no
check "a folder that is not a worktree is left alone and the piece skipped" "$r"

echo "== A branch that already exists =="

git -C "$P" branch -q --no-track 15-parked-before origin/main
run "$P" open 15-parked-before 15-parked-before origin/main >/dev/null
[ "$(branch_of "$P/.agents/worktrees/15-parked-before")" = 15-parked-before ] && r=yes || r=no
check "a piece whose branch exists continues on it" "$r"

echo "== Clearing worktrees away =="

# 12: merged, pushed, nothing unsaved. 13: closed with an uncommitted change.
# 15: merged, with a commit that never reached the remote. 16: open.
# 17: merged, its remote branch since deleted, its head the merged commit.
run "$P" open 16-open-piece 16-open-piece origin/main >/dev/null
run "$P" open 17-squashed 17-squashed origin/main >/dev/null
commit_in "$P/.agents/worktrees/17-squashed" squash.txt
pr "12-invoice-list MERGED $(git -C "$W" rev-parse HEAD)"
pr "13-overdue-list CLOSED"
echo "unsaved" > "$S/unsaved.txt"
commit_in "$P/.agents/worktrees/15-parked-before" local.txt
pr "15-parked-before MERGED $(git -C "$P" rev-parse origin/main)"
pr "16-open-piece OPEN"
pr "17-squashed MERGED $(git -C "$P/.agents/worktrees/17-squashed" rev-parse HEAD)"

out=$(GH_FAIL=1; export GH_FAIL; run "$P" tidy)
[ -d "$W" ] && case $out in *"Could not read"*) true ;; *) false ;; esac && r=yes || r=no
check "with no pull requests to read, nothing is removed" "$r"

out=$(run "$P" tidy)
[ ! -d "$W" ] && r=yes || r=no
check "a merged piece's worktree with nothing unsaved is removed" "$r"
git -C "$P" show-ref --verify -q refs/heads/12-invoice-list && r=yes || r=no
check "its branch is kept" "$r"
[ -f "$P/.env" ] && grep -q SECRET_KEY "$P/.env" && r=yes || r=no
check "the main folder's .env survives the removal" "$r"
[ -d "$S" ] && [ -f "$S/unsaved.txt" ] && case $out in *"Kept .agents/worktrees/13-overdue-list"*"unsaved"*) true ;; *) false ;; esac && r=yes || r=no
check "a closed piece's worktree holding an uncommitted change is kept and named" "$r"
[ -d "$P/.agents/worktrees/15-parked-before" ] && case $out in *"Kept .agents/worktrees/15-parked-before"*"commit"*) true ;; *) false ;; esac && r=yes || r=no
check "a merged piece's worktree holding an unpushed commit is kept and named" "$r"
[ -d "$P/.agents/worktrees/16-open-piece" ] && case $out in *16-open-piece*) false ;; *) true ;; esac && r=yes || r=no
check "an open pull request's worktree is left alone, and not mentioned" "$r"
[ ! -d "$P/.agents/worktrees/17-squashed" ] && r=yes || r=no
check "a merged piece whose remote branch is gone counts its merged commit as saved" "$r"
[ "$(branch_of "$P")" = main ] && [ -z "$(git -C "$P" status --porcelain)" ] && r=yes || r=no
check "the main folder is still on main, with nothing changed" "$r"

echo "== A run still building a piece =="

mkdir -p "$P/.agents/runs/2026-09-30-221500"
run "$P" open 18-in-a-run 18-in-a-run origin/main >/dev/null
pr "18-in-a-run CLOSED"
cat > "$P/.agents/runs/2026-09-30-221500/state.json" <<'JSON'
{"run": "2026-09-30-221500", "merge_preapproved": false, "pieces": [
 {"number": 18, "state": "building", "branch": "18-in-a-run", "base": "main",
  "worktree": ".agents/worktrees/18-in-a-run", "port": null, "pull_request": null,
  "attempts": 0, "flags": [], "reason": ""}]}
JSON
run "$P" tidy >/dev/null
[ -d "$P/.agents/worktrees/18-in-a-run" ] && r=yes || r=no
check "a worktree an unfinished run is building is never removed" "$r"
[ -z "$(git -C "$P" status --porcelain)" ] && r=yes || r=no
check "the run state in the main folder is not tracked" "$r"

echo "== Leftovers and removing one on a yes =="

rm -f "$S/unsaved.txt"
run "$P" open 19-never-opened 19-never-opened origin/main >/dev/null
out=$(run "$P" leftovers)
case $out in *13-overdue-list*"nothing in it is unsaved"*) r=yes ;; *) r=no ;; esac
check "a closed pull request's worktree is listed as a leftover" "$r"
case $out in *19-never-opened*"no pull request"*) r=yes ;; *) r=no ;; esac
check "a worktree with no pull request is listed as a leftover" "$r"
case $out in *15-parked-before*"unsaved work"*) r=yes ;; *) r=no ;; esac
check "a leftover holding unsaved work says so" "$r"
case $out in *16-open-piece*) r=no ;; *) r=yes ;; esac
check "an open pull request's worktree is not a leftover" "$r"
case $out in *18-in-a-run*) r=no ;; *) r=yes ;; esac
check "a worktree a run is building is not a leftover" "$r"
[ -d "$S" ] && [ -d "$P/.agents/worktrees/19-never-opened" ] && r=yes || r=no
check "listing leftovers removes nothing" "$r"

run "$P" remove "$S" >/dev/null
[ ! -d "$S" ] && git -C "$P" show-ref --verify -q refs/heads/13-overdue-list && r=yes || r=no
check "a leftover is removed on a yes, and its branch kept" "$r"
out=$(run "$P" remove "$P/.agents/worktrees/15-parked-before") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$P/.agents/worktrees/15-parked-before" ] && r=yes || r=no
check "a leftover holding unsaved work is kept, even on a yes" "$r"
out=$(run "$P" remove "$P/.agents/worktrees/16-open-piece") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$P/.agents/worktrees/16-open-piece" ] && r=yes || r=no
check "a worktree whose pull request is open is not removed" "$r"
out=$(run "$P" remove "$P/.agents/worktrees/18-in-a-run") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$P/.agents/worktrees/18-in-a-run" ] && r=yes || r=no
check "a worktree a run is building is not removed" "$r"
out=$(run "$P" remove "$P") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$P/.git" ] && r=yes || r=no
check "the main folder itself can never be removed" "$r"

echo "== No .env, and no ignore line =="

Q="$WORK/bare-project"
grep -v '^\.agents/worktrees/$' "$IGNORE" > "$WORK/gitignore-older"
project "$Q" "$WORK/gitignore-older"
rm -f "$Q/.env" "$Q/.env.local"
out=$(run "$Q" open 21-first 21-first origin/main)
[ ! -e "$Q/.agents/worktrees/21-first/.env" ] && case $out in *"nothing was linked"*) true ;; *) false ;; esac && r=yes || r=no
check "with no .env in the main folder, nothing is linked" "$r"
git -C "$Q" check-ignore -q .agents/worktrees/21-first && [ -f "$Q/.agents/worktrees/.gitignore" ] && r=yes || r=no
check "an older project with no ignore line gets a folder that ignores itself" "$r"
[ -z "$(git -C "$Q" status --porcelain)" ] && r=yes || r=no
check "and nothing tracked changes" "$r"

echo "== A link that cannot be made =="

mkdir -p "$WORK/noln"
printf '#!/usr/bin/env sh\nexit 1\n' > "$WORK/noln/ln"
chmod +x "$WORK/noln/ln"
echo "SECRET_KEY=not-a-real-secret" > "$Q/.env"
out=$(PATH="$WORK/noln:$PATH"; export PATH; run "$Q" open 22-no-link 22-no-link origin/main) && code=0 || code=$?
[ "$code" -eq 0 ] && [ ! -e "$Q/.agents/worktrees/22-no-link/.env" ] && r=yes || r=no
check "where the link cannot be made, no copy is made either" "$r"
case $out in *"runs without secrets"*"flag anything"*) r=yes ;; *) r=no ;; esac
check "it says the piece runs without secrets and to flag what needs a key" "$r"

echo "== A free port =="

port=$(run "$Q" port 12)
case $port in '' | *[!0-9]*) r=no ;; *) r=yes ;; esac
check "the port step prints a port" "$r"
python3 - "$port" "$WORK/listening" <<'PY' &
import socket, sys, time
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen(1)
open(sys.argv[2], "w").write("ready")
time.sleep(20)
PY
listener=$!
tries=0
while [ ! -f "$WORK/listening" ] && [ $tries -lt 50 ]; do
  python3 -c 'import time; time.sleep(0.1)'
  tries=$((tries + 1))
done
second=$(run "$Q" port 12)
kill "$listener" 2>/dev/null || true
[ -n "$second" ] && [ "$second" != "$port" ] && r=yes || r=no
check "a port something is listening on is never given" "$r"

echo "== Ignored files that are still work =="

R="$WORK/review-project"
project "$R" "$IGNORE"
pr_clear() { : > "$WORK/prs"; }
run "$R" open 30-notes 30-notes origin/main >/dev/null
N="$R/.agents/worktrees/30-notes"
mkdir -p "$N/node_modules/pkg" "$N/dist" "$N/.agents/tmp"
echo dep > "$N/node_modules/pkg/index.js"
echo build > "$N/dist/app.js"
run "$R" unsaved "$N" >/dev/null && r=yes || r=no
check "dependency and build folders are not unsaved work" "$r"
echo "a note only here" > "$N/.agents/tmp/note.md"
out=$(run "$R" unsaved "$N") && code=0 || code=$?
[ "$code" -eq 1 ] && case $out in *"ignored file"*) true ;; *) false ;; esac && r=yes || r=no
check "an ignored real file outside those folders is unsaved work" "$r"
pr "30-notes MERGED $(git -C "$N" rev-parse HEAD)"
out=$(run "$R" tidy)
[ -f "$N/.agents/tmp/note.md" ] && case $out in *"Kept .agents/worktrees/30-notes"*"ignored file"*) true ;; *) false ;; esac && r=yes || r=no
check "tidy keeps and names a worktree holding an ignored file" "$r"
out=$(run "$R" remove "$N") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -f "$N/.agents/tmp/note.md" ] && r=yes || r=no
check "remove, at the end of a run or on a yes, keeps it too" "$r"

echo "== Walk-through pictures go to the main folder =="

# section-builder names the lookup that finds the main folder. It is taken from
# the shipped text and run as written, from inside a worktree and from the main
# folder, so a lookup that named the wrong folder, or a rule that went, fails
# here rather than in somebody's run.
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
LOOKUP=$(sed -n 's/.*`\(git worktree list --porcelain[^`]*\)`.*/\1/p' "$BUILDER" | head -n 1)
[ -n "$LOOKUP" ] || fail "section-builder names no lookup for the main folder"
ok "section-builder names the lookup for the main folder"
run "$R" open 40-walkthrough 40-walkthrough origin/main >/dev/null
K="$R/.agents/worktrees/40-walkthrough"
rm -rf "$R/.agents/tmp"
main=$(cd "$K" && sh -c "$LOOKUP")
[ "$(cd "$main" && pwd -P)" = "$(cd "$R" && pwd -P)" ] && r=yes || r=no
check "from inside a worktree, the lookup names the main folder" "$r"
main_here=$(cd "$R" && sh -c "$LOOKUP")
[ "$(cd "$main_here" && pwd -P)" = "$(cd "$R" && pwd -P)" ] && r=yes || r=no
check "from the main folder, the lookup names the main folder itself" "$r"
mkdir -p "$main/.agents/tmp/walkthrough/40"
echo "picture" > "$main/.agents/tmp/walkthrough/40/step-1.png"
[ -z "$(git -C "$R" status --porcelain)" ] && r=yes || r=no
check "a picture in the main folder's walkthrough folder never reaches git" "$r"
[ ! -e "$K/.agents/tmp" ] && r=yes || r=no
check "and nothing was written inside the worktree" "$r"
pr "40-walkthrough MERGED $(git -C "$K" rev-parse HEAD)"
out=$(run "$R" remove "$K") && code=0 || code=$?
[ "$code" -eq 0 ] && [ ! -d "$K" ] && r=yes || r=no
check "the worktree is cleared away once its pull request closes" "$r"
[ -f "$R/.agents/tmp/walkthrough/40/step-1.png" ] && r=yes || r=no
check "and the picture outlives it, in the one place the person looks" "$r"

echo "== A copy of .env where a link would go =="

run "$R" open 31-copy 31-copy origin/main >/dev/null
C="$R/.agents/worktrees/31-copy"
rm -f "$C/.env"
cp "$R/.env" "$C/.env"
out=$(run "$R" unsaved "$C") && code=0 || code=$?
[ "$code" -eq 1 ] && r=yes || r=no
check "a copy of .env in a worktree is unsaved work, so it is never removed" "$r"
out=$(run "$R" open --resume 31-copy 31-copy origin/main) && code=0 || code=$?
case $out in *"A copy of .env already sits in this worktree"*"copy outside the main folder"*) r=yes ;; *) r=no ;; esac
check "an existing copy of .env is named and not linked" "$r"
case $out in *"No .env in the main folder"*) r=no ;; *) r=yes ;; esac
check "and it is never called a missing .env" "$r"
[ ! -L "$C/.env" ] && r=yes || r=no
check "the copy is left as it is" "$r"
rm -f "$C/.env"

T="$WORK/nested-project"
project "$T" "$IGNORE"
rm -f "$T/.env" "$T/.env.local"
mkdir -p "$T/app"
echo "SECRET_KEY=not-a-real-secret" > "$T/app/.env"
out=$(run "$T" open 32-nested 32-nested origin/main)
case $out in *"A .env sits in app rather than at the top"*) r=yes ;; *) r=no ;; esac
check "a .env only in a subfolder is named, and nothing is linked" "$r"
case $out in *"No .env in the main folder"*) r=no ;; *) r=yes ;; esac
check "and the main folder is not said to have none" "$r"

echo "== A worktree on no branch =="

run "$R" open 33-detached 33-detached origin/main >/dev/null
D="$R/.agents/worktrees/33-detached"
"$REAL_GIT" -C "$D" checkout -q --detach
: > "$WORK/gh.log"
out=$(run "$R" tidy)
[ -d "$D" ] && r=yes || r=no
check "tidy never removes a worktree on no branch" "$r"
out=$(run "$R" leftovers)
case $out in *"33-detached: it is on no branch"*) r=yes ;; *) r=no ;; esac
check "leftovers lists a worktree on no branch" "$r"
if grep -E -- '--head( |$)(--|$)' "$WORK/gh.log" >/dev/null || grep -E -- '--head  ' "$WORK/gh.log" >/dev/null; then
  fail "the pull requests were asked about an empty branch"
fi
ok "no pull request lookup is ever made for an empty branch"
run "$R" remove "$D" >/dev/null && [ ! -d "$D" ] && r=yes || r=no
check "a clean worktree on no branch can be removed on a yes" "$r"

echo "== Skip reasons and a folder that is gone =="

out=$(run "$R" open 34-bad-base 34-bad-base no-such-base) && code=0 || code=$?
[ "$code" -eq 1 ] && case $out in *"fatal:"*) true ;; *) false ;; esac && r=yes || r=no
check "a skip gives git's own reason line" "$r"
"$REAL_GIT" -C "$R" show-ref --verify -q refs/heads/34-bad-base && r=no || r=yes
check "a failed open leaves no branch behind" "$r"
run "$R" open 35-gone 35-gone origin/main >/dev/null
rm -rf "$R/.agents/worktrees/35-gone"
out=$(run "$R" open 35-gone 35-gone origin/main) && code=0 || code=$?
[ "$code" -eq 1 ] && case $out in *"git worktree prune"*) true ;; *) false ;; esac && r=yes || r=no
check "a folder git still lists but is gone names git worktree prune" "$r"
out=$(run "$R" leftovers)
case $out in *"35-gone is gone"*"git worktree prune"*) r=yes ;; *) r=no ;; esac
check "and the leftover list names it too" "$r"
"$REAL_GIT" -C "$R" worktree prune

echo "== A failed open deletes only the branch it made =="

chmod 555 "$R/.agents/worktrees"
out=$(run "$R" open 36-readonly 36-readonly origin/main) && code=0 || code=$?
chmod 755 "$R/.agents/worktrees"
[ "$code" -eq 1 ] && r=yes || r=no
check "an open that cannot make its folder skips the piece" "$r"
"$REAL_GIT" -C "$R" show-ref --verify -q refs/heads/36-readonly && r=no || r=yes
check "the branch that open made is deleted again" "$r"
"$REAL_GIT" -C "$R" branch -q --no-track 37-existing origin/main
chmod 555 "$R/.agents/worktrees"
out=$(run "$R" open 37-existing 37-existing origin/main) && code=0 || code=$?
chmod 755 "$R/.agents/worktrees"
"$REAL_GIT" -C "$R" show-ref --verify -q refs/heads/37-existing && r=yes || r=no
check "a branch that existed before is kept when open fails" "$r"

echo "== A Git older than 2.17 =="

out=$(FAKE_GIT_VERSION=2.16.4; export FAKE_GIT_VERSION; run "$R" open 38-old 38-old origin/main) && code=0 || code=$?
[ "$code" -eq 4 ] && [ ! -d "$R/.agents/worktrees/38-old" ] && case $out in *"older than 2.17"*) true ;; *) false ;; esac && r=yes || r=no
check "an older Git gets the one-checkout route and no worktree" "$r"

echo "== A port taken only on ::1 =="

if python3 -c 'import socket; s = socket.socket(socket.AF_INET6); s.bind(("::1", 0))' 2>/dev/null; then
  free=$(run "$R" port 40)
  python3 - "$free" "$WORK/listening6" <<'PY' &
import socket, sys, time
s = socket.socket(socket.AF_INET6)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("::1", int(sys.argv[1])))
s.listen(1)
open(sys.argv[2], "w").write("ready")
time.sleep(20)
PY
  listener6=$!
  tries=0
  while [ ! -f "$WORK/listening6" ] && [ $tries -lt 50 ]; do
    python3 -c 'import time; time.sleep(0.1)'
    tries=$((tries + 1))
  done
  again=$(run "$R" port 40)
  kill "$listener6" 2>/dev/null || true
  [ -n "$again" ] && [ "$again" != "$free" ] && r=yes || r=no
  check "a port something listens on at ::1 is never given" "$r"
else
  echo "  note: this computer has no IPv6 loopback, so the ::1 case was not run"
fi

echo "== Ignored build files the worktree-links line names =="

# L's build needs files git ignores and that hold no secret: a folder of
# fonts, a sample input inside an ignored folder, and a folder whose name has
# a space. Its confidential folder, its env files, a tracked file, a path
# outside the project and a deleted one are on the line too, and each must be
# refused by name.
L="$WORK/links-project"
project "$L" "$IGNORE"
printf 'fonts/\nsamples/\nbrand assets/\nprivate/\ndata/\ngone.bin\n.env.production\n*.woff\n' >> "$L/.gitignore"
mkdir -p "$L/assets" "$L/lib/sub"
echo "kept" > "$L/assets/readme.txt"
echo "kept" > "$L/lib/sub/readme.txt"
git -C "$L" add .gitignore assets lib
git -C "$L" commit -q -m "Ignore the build files"
git -C "$L" push -q origin main 2>/dev/null
mkdir -p "$L/fonts" "$L/samples" "$L/brand assets" "$L/private" "$L/data/secret"
echo "font" > "$L/assets/logo.woff"
echo "font" > "$L/lib/sub/deep.woff"
mkdir -p "$L/node_modules/pkg" "$L/.agents/tmp"
echo "dep" > "$L/node_modules/pkg/index.js"
echo "note" > "$L/.agents/tmp/note.md"
echo "font" > "$L/fonts/Brand.ttf"
echo "a,b" > "$L/samples/big input.csv"
echo "logo" > "$L/brand assets/logo.svg"
echo "report" > "$L/private/report.pdf"
echo "secret" > "$L/data/secret/list.csv"
echo "PROD_KEY=not-a-real-secret" > "$L/.env.production"
echo "far" > "$WORK/elsewhere.txt"
cat >> "$L/.ai-build-kit-maintenance" <<'REC'
founded|2026-09-01
confidential|private
confidential|data/secret
worktree-links|fonts ; samples/big input.csv ; brand assets ; private/report.pdf ; data ; .env.production ; tool.txt ; ../elsewhere.txt ; /etc/hosts ; gone.bin ; loose.txt ; extra ; kept ; far.txt ; hidden
REC
# A folder whose files are ignored while a placeholder in it is tracked.
mkdir -p "$L/kept"
printf 'kept/*\n!kept/.gitkeep\nfar.txt\nhidden\n' >> "$L/.gitignore"
: > "$L/kept/.gitkeep"
echo "icon" > "$L/kept/icon.otf"
"$REAL_GIT" -C "$L" add .gitignore kept/.gitkeep
"$REAL_GIT" -C "$L" commit -q -m "Keep the kept folder"
"$REAL_GIT" -C "$L" push -q origin main 2>/dev/null
# Links in the main folder that lead outside the project and into the
# confidential folder.
ln -s "$WORK/elsewhere.txt" "$L/far.txt"
ln -s private "$L/hidden"
echo "loose" > "$L/loose.txt"
# An ignore line the main folder has and has not saved yet, so a worktree cut
# from origin/main does not have it.
echo "extra/" >> "$L/.gitignore"
mkdir -p "$L/extra"
echo "extra" > "$L/extra/x.bin"

out=$(run "$L" candidates)
case $out in *fonts*) r=yes ;; *) r=no ;; esac
check "candidates lists an ignored folder at the top level" "$r"
case $out in *"brand assets"*) r=yes ;; *) r=no ;; esac
check "candidates lists a folder whose name has a space" "$r"
case $out in *"assets/logo.woff"*) r=yes ;; *) r=no ;; esac
check "candidates lists an ignored file at the second level" "$r"
case $out in *private* | *"data/secret"* | *.env* | *node_modules* | *.agents* | *"lib/sub"*) r=no ;; *) r=yes ;; esac
check "candidates leaves out the confidential folder, env files, dependency folders, the kit's folder and anything deeper than two levels" "$r"
printf '%s\n' "$out" | grep -qx data && r=no || r=yes
check "candidates leaves out a folder that holds a confidential folder" "$r"

out=$(run "$L" open 50-report 50-report origin/main) && code=0 || code=$?
LW="$L/.agents/worktrees/50-report"
[ "$code" -eq 0 ] && r=yes || r=no
check "a piece whose line names refused paths still opens" "$r"
[ -d "$LW/fonts" ] && [ ! -L "$LW/fonts" ] && [ -L "$LW/fonts/Brand.ttf" ] && \
  [ "$(readlink "$LW/fonts/Brand.ttf")" = "../../../../fonts/Brand.ttf" ] && \
  cmp -s "$LW/fonts/Brand.ttf" "$L/fonts/Brand.ttf" && r=yes || r=no
check "a listed folder is made in the worktree, each thing in it a relative link to the main folder's own" "$r"
[ -d "$LW/samples" ] && [ ! -L "$LW/samples" ] && [ -L "$LW/samples/big input.csv" ] && \
  [ "$(readlink "$LW/samples/big input.csv")" = "../../../../samples/big input.csv" ] && \
  cmp -s "$LW/samples/big input.csv" "$L/samples/big input.csv" && r=yes || r=no
check "a file inside an ignored folder the worktree lacks gets the folder made and the file linked, spaces and all" "$r"
[ -L "$LW/brand assets/logo.svg" ] && [ -f "$LW/brand assets/logo.svg" ] && r=yes || r=no
check "a folder whose name has a space is linked" "$r"
[ ! -e "$LW/private/report.pdf" ] && case $out in *"private/report.pdf"*"confidential"*) true ;; *) false ;; esac && r=yes || r=no
check "a path inside a confidential folder is refused by name" "$r"
[ ! -e "$LW/data" ] && case $out in *"Not linked data:"*"confidential"*) true ;; *) false ;; esac && r=yes || r=no
check "a path holding a confidential folder is refused by name" "$r"
[ ! -e "$LW/.env.production" ] || [ -L "$LW/.env.production" ] && case $out in *"Not linked .env.production:"*".env"*) true ;; *) false ;; esac && r=yes || r=no
check "an env file on the line is refused, and left to the .env rule" "$r"
[ ! -L "$LW/tool.txt" ] && case $out in *"Not linked tool.txt:"*"git tracks it"*) true ;; *) false ;; esac && r=yes || r=no
check "a tracked file is refused, since the worktree already has it" "$r"
case $out in *"Not linked ../elsewhere.txt:"*"outside the project"*) r=yes ;; *) r=no ;; esac
check "a path outside the project is refused" "$r"
case $out in *"Not linked /etc/hosts:"*"outside the project"*) r=yes ;; *) r=no ;; esac
check "an absolute path is refused as outside the project" "$r"
[ ! -e "$LW/gone.bin" ] && case $out in *"gone.bin"*"not in the main folder"*"built without gone.bin"*) true ;; *) false ;; esac && r=yes || r=no
check "a listed path deleted from the main folder is named, not linked, and the piece flagged" "$r"
[ ! -e "$LW/loose.txt" ] && case $out in *"Not linked loose.txt:"*"does not ignore it"*) true ;; *) false ;; esac && r=yes || r=no
check "a path git does not ignore is refused, so no link shows as a new file to save" "$r"
[ ! -e "$LW/extra/x.bin" ] && case $out in *"Not linked extra/x.bin:"*"worktree does not ignore the link"*"built without extra/x.bin"*) true ;; *) false ;; esac && r=yes || r=no
check "a link the worktree's own ignore rules do not cover is taken away and named" "$r"
[ -L "$LW/kept/icon.otf" ] && [ -f "$LW/kept/.gitkeep" ] && [ ! -L "$LW/kept/.gitkeep" ] && r=yes || r=no
check "a folder keeping one tracked placeholder links its ignored files and leaves the placeholder" "$r"
[ ! -e "$LW/far.txt" ] && case $out in *"Not linked far.txt:"*"leads outside the project"*) true ;; *) false ;; esac && r=yes || r=no
check "a main-folder link leading outside the project is refused" "$r"
[ ! -e "$LW/hidden" ] && case $out in *"Not linked hidden:"*"confidential"*) true ;; *) false ;; esac && r=yes || r=no
check "a main-folder link leading into the confidential folder is refused" "$r"
copies=$(find "$L/.agents/worktrees" -name 'Brand.ttf' -type f 2>/dev/null || true)
[ -z "$copies" ] && r=yes || r=no
check "no copy of a listed file exists in the worktree" "$r"
run "$L" unsaved "$LW" >/dev/null && r=yes || r=no
check "linked build files are not unsaved work" "$r"
[ -z "$(git -C "$LW" status --porcelain)" ] && r=yes || r=no
check "the links show as no change in the worktree" "$r"

echo "== A copy where a listed link would go, and a link that cannot be made =="

rm -f "$LW/samples/big input.csv"
cp "$L/samples/big input.csv" "$LW/samples/big input.csv"
out=$(run "$L" open --resume 50-report 50-report origin/main) && code=0 || code=$?
case $out in *"A copy of samples/big input.csv already sits in this worktree"*"Flag the piece"*) r=yes ;; *) r=no ;; esac
check "a real copy at a listed path is named as a copy and the piece flagged" "$r"
[ -f "$LW/samples/big input.csv" ] && [ ! -L "$LW/samples/big input.csv" ] && r=yes || r=no
check "the copy is left as it is" "$r"
rm -f "$LW/samples/big input.csv"

out=$(PATH="$WORK/noln:$PATH"; export PATH; run "$L" open 51-no-link 51-no-link origin/main) && code=0 || code=$?
[ "$code" -eq 0 ] && [ ! -e "$L/.agents/worktrees/51-no-link/fonts/Brand.ttf" ] && r=yes || r=no
check "where a listed link cannot be made, the piece goes on and nothing is copied" "$r"
case $out in *"built without fonts"*) r=yes ;; *) r=no ;; esac
check "and it says the piece is built without that path" "$r"
out=$(run "$L/.agents/worktrees/51-no-link" open 53-from-kit 53-from-kit origin/main)
case $out in *"another worktree"*) r=no ;; *) r=yes ;; esac
check "opened from one of the kit's own worktrees, it is not called another tool's" "$r"

pr "50-report MERGED $(git -C "$LW" rev-parse HEAD)"
out=$(run "$L" tidy)
[ ! -d "$LW" ] && r=yes || r=no
check "a worktree holding only links is removed once its pull request merged" "$r"
[ -f "$L/fonts/Brand.ttf" ] && [ -f "$L/samples/big input.csv" ] && [ -f "$L/brand assets/logo.svg" ] && r=yes || r=no
check "removing it leaves the main folder's files in place" "$r"

echo "== No worktree-links line =="

M="$WORK/no-line-project"
project "$M" "$IGNORE"
printf 'fonts/\n' >> "$M/.gitignore"
git -C "$M" add .gitignore
git -C "$M" commit -q -m "Ignore fonts"
mkdir -p "$M/fonts"
echo "font" > "$M/fonts/Brand.ttf"
out=$(run "$M" open 52-plain 52-plain origin/main)
[ ! -e "$M/.agents/worktrees/52-plain/fonts" ] && [ -L "$M/.agents/worktrees/52-plain/.env" ] && r=yes || r=no
check "with no worktree-links line only the .env files are linked" "$r"

echo "== Beside another tool's worktrees =="

# O's main folder is on another branch, and a sibling folder made by
# `git worktree add` stands for another tool's worktree, with main checked
# out in it. A second sibling stands for one on a merged branch.
O="$WORK/orca-project"
project "$O" "$IGNORE"
"$REAL_GIT" -C "$O" checkout -q -b dev
"$REAL_GIT" -C "$O" worktree add -q "$WORK/orca-main" main
"$REAL_GIT" -C "$O" branch -q --no-track orca-feature origin/main
"$REAL_GIT" -C "$O" worktree add -q "$WORK/orca-feature" orca-feature
pr "orca-feature MERGED $(git -C "$O" rev-parse orca-feature)"
pr "orca-main MERGED $(git -C "$O" rev-parse main)"

out=$(run "$WORK/orca-main" open 60-from-orca 60-from-orca origin/main) && code=0 || code=$?
[ "$code" -eq 0 ] && [ -d "$O/.agents/worktrees/60-from-orca" ] && [ ! -e "$WORK/orca-main/.agents/worktrees/60-from-orca" ] && r=yes || r=no
check "started inside another tool's worktree, open makes the piece's worktree in the main folder" "$r"
case $out in *"live in the main folder"*) r=yes ;; *) r=no ;; esac
check "and it says in one line where they are" "$r"
[ "$(branch_of "$WORK/orca-main")" = main ] && [ "$(branch_of "$O")" = dev ] && r=yes || r=no
check "the other tool's worktree stays on main and the main folder on its branch" "$r"
[ "$(git -C "$O/.agents/worktrees/60-from-orca" rev-parse HEAD)" = "$(git -C "$O" rev-parse origin/main)" ] && r=yes || r=no
check "the piece is cut from origin/main while main is checked out elsewhere" "$r"

mkdir -p "$O/.agents/runs/2026-09-30-230000"
run "$WORK/orca-main" open 61-in-orca-run 61-in-orca-run origin/main >/dev/null
pr "61-in-orca-run CLOSED"
cat > "$O/.agents/runs/2026-09-30-230000/state.json" <<'JSON'
{"run": "2026-09-30-230000", "merge_preapproved": false, "pieces": [
 {"number": 61, "state": "building", "branch": "61-in-orca-run", "base": "main",
  "worktree": ".agents/worktrees/61-in-orca-run", "port": null, "pull_request": null,
  "attempts": 0, "flags": [], "reason": ""}]}
JSON
out=$(run "$WORK/orca-main" tidy)
[ -d "$O/.agents/worktrees/61-in-orca-run" ] && r=yes || r=no
check "a run started elsewhere is read from the main folder's run state" "$r"
[ -d "$WORK/orca-feature" ] && [ -d "$WORK/orca-main" ] && case $out in *orca-*) false ;; *) true ;; esac && r=yes || r=no
check "tidy never changes or names another tool's worktree" "$r"
out=$(run "$WORK/orca-main" leftovers)
case $out in *orca-feature* | *orca-main*) r=no ;; *) r=yes ;; esac
check "leftovers never lists another tool's worktree" "$r"
out=$(run "$WORK/orca-main" remove "$WORK/orca-feature") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$WORK/orca-feature" ] && r=yes || r=no
check "remove refuses another tool's worktree" "$r"
out=$(run "$O" remove "$WORK/orca-main") && code=0 || code=$?
[ "$code" -eq 1 ] && [ -d "$WORK/orca-main" ] && [ "$(branch_of "$WORK/orca-main")" = main ] && r=yes || r=no
check "remove refuses it from the main folder too, and leaves it on main" "$r"

echo "== What git was asked to do =="

if grep -E 'worktree remove.*(--force|(^| )-f( |$))' "$WORK/git.log" >/dev/null; then
  fail "a worktree was removed by force"
fi
ok "no worktree was ever removed by force"
if grep -E '^(-C [^ ]+ )?(branch (-[dD]|--delete)|push .*--delete)' "$WORK/git.log" >/dev/null; then
  fail "a branch was deleted with git branch or a push"
fi
ok "no branch was deleted with git branch or a push"
if grep -E '^(-C [^ ]+ )?(checkout|switch)( |$)' "$WORK/git.log" >/dev/null; then
  fail "a branch was checked out"
fi
ok "the script never checks a branch out"

echo
echo "kit-owns-worktrees-rehearsal.sh: all $pass checks passed"
