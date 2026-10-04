#!/usr/bin/env sh
# changelog-files.sh: guard the one changelog file each piece writes, and the
# fold that gathers those files into CHANGELOG.md.
#
# Every piece used to add its entry at the top of CHANGELOG.md. Two pieces built
# at the same time then both changed the same lines, and in a real project
# nearly every merge in a batch hit that conflict, until the agent wrote its own
# script to merge the entries. So a piece now writes its own small file in
# `changes/`, and the merge folds the files into CHANGELOG.md, with /sync and
# /ship folding any a merge made by hand left behind. fold-at-merge.sh holds
# the merge's fold; this check holds the files and the fold script's order.
#
# The rules are prose a coding agent reads, so the first half reads them back
# and proves each one load-bearing. The second half runs the shipped fold
# against a throwaway repository: two branches that each add a file merge with
# no conflict, the fold writes them newest first under the day each reached
# `main`, and the folder ends up empty. A file still on an unmerged branch, and
# one nobody has committed yet, stay out of the history. A project founded
# before `changes/` existed gets nothing written by a fold.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FIX="$ROOT/.agents/skills/fix/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
SHIP="$ROOT/.agents/skills/ship/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
AGENTS="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
README="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/README.md"
TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/CHANGELOG.md"
WORKFLOW="$ROOT/WORKFLOW.md"
FOLD="$ROOT/.agents/skills/sync/scripts/fold-changes.py"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"

rs_init "Changelog file checks"
rs_exists "$BUILDER" "$FIX" "$SYNC" "$SHIP" "$MAINTAIN" "$SETUP" "$AGENTS" "$README" "$TEMPLATE" "$WORKFLOW"

# --- section-builder writes one file per piece ------------------------------

rs_rule "the piece's entry goes in its own file" 'changes/<issue number>-<short name>\.md'
rs_rule "never into the shared changelog" 'never into `changelog\.md`'
rs_rule "because parallel pieces conflict at its top" 'every merge after the first would conflict there'
rs_rule "an older project gets the folder from its first piece" 'create the `changes/` folder when the project has none'
rs_rule "one or two sentences for the person" 'one or two sentences on what changed for the person'
rs_rule "then the pull request link" 'then the pull request.s link on its own line'
rs_rule "written after the pull request opens, as a second commit" 'after the pull request opens, as a second commit on the same branch'
rs_rule "one file per piece" 'one file per piece'
rs_rule "a later commit rewrites it, never adds another" 'rewrites that file and never adds another'
rs_rule "the checkpoint route names the issue instead" 'the file names the issue instead'
rs_rule "the issue number keeps two short names apart" 'the issue number keeps two pieces with the same short name apart'
rs_rule "work with no issue uses the pull request number" 'where the work has no issue, use the pull request.s number'
rs_rule "the file carries no date" 'the file carries no date'
rs_rule "checkpoint work with neither takes the date and branch name" 'changes/<yyyy-mm-dd>-<short name>\.md'
rs_guard "$BUILDER" "section-builder's changelog file"

rs_require_load_bearing "section-builder opens the pull request before writing the file" \
  "$BUILDER" 'once it is open, write the piece.s changelog file'
rs_require_absent "section-builder no longer writes a changelog line itself" \
  "$BUILDER" 'write the changelog line from'

rs_require_load_bearing "/fix writes the cause into the repair's file" \
  "$FIX" 'the repair.s file in `changes/`'
rs_require_absent "/fix no longer records the cause in the changelog itself" \
  "$FIX" 'record the cause in the changelog'
rs_require_load_bearing "/fix reads the unfolded entries too" \
  "$FIX" 'the entries in `changes/` not yet folded'

# --- /sync and /ship fold -----------------------------------------------------

rs_reset
rs_rule "sync folds with the shipped script" 'this skill.s `scripts/fold-changes\.py`'
rs_rule "newest first under the day it reached main" 'newest first under the day each file reached `main`'
rs_rule "the folded files are deleted" 'deletes the files it folded'
rs_rule "only the branch being saved is folded" 'only files on the branch being saved are folded'
rs_rule "so an unmerged piece never enters the history" 'never puts an unmerged piece into the history'
rs_rule "a file nobody committed is left alone" 'a file nobody has committed stays where it is'
rs_rule "the direct writers are named" 'founding, /ship, /maintain and /sync write `changelog\.md` directly'
rs_rule "only pieces write the folder" 'only section-builder and /fix write to `changes/`'
# Without these, /sync reads a waiting file as work the changelog missed and
# writes the entry a second time, or folds files a records pull request still
# open has already folded.
rs_rule "the read counts a waiting entry as written" 'counting an entry waiting in `changes/` as written'
rs_rule "no second line for work waiting in changes/" 'counts as written, so never add a second line for the same work'
rs_rule "no fold while an earlier fold is still open" 'do not fold again until it merges, since a second fold would write the same entries twice'
rs_guard "$SYNC" "sync's fold"

rs_require_load_bearing "/ship folds before it writes the launch lines" \
  "$SHIP" 'fold first and write the launch lines after'
rs_require_load_bearing "/ship does not fold while an earlier fold is still open" \
  "$SHIP" 'still open, say so in one line and do not fold again until it merges'
rs_require_load_bearing "pieces.md counts a waiting entry as a changelog line" \
  "$PIECES" 'counting an entry waiting in `changes/` as a line'
rs_require_load_bearing "/what-now reads the waiting entries" "$WHATNOW" 'recent changelog and `changes/`'
rs_require_load_bearing "change-triage reads the waiting entries" "$TRIAGE" 'recent changelog and `changes/`'
rs_require_load_bearing "/ship folds on its records branch with the same script" \
  "$SHIP" 'fold any files still waiting in `changes/` into changelog\.md with the `sync` skill.s `scripts/fold-changes\.py`'

# The direct writers keep writing. /ship's launch and rollback lines are read by
# the replay harness, so a fold that took their place would lose them.
rs_require "/ship still records a warning in CHANGELOG.md" "$SHIP" 'record in changelog\.md, with the date'
rs_require "/maintain still adds a dated changelog line" "$MAINTAIN" 'add a dated changelog line'
rs_require "founding still creates CHANGELOG.md" "$SETUP" 'create changelog\.md from its template'
rs_require "/sync still appends the lines the work missed" "$SYNC" 'append any changelog lines the work missed, dated'

# --- the records name both places ---------------------------------------------

rs_require_load_bearing "the founded AGENTS.md names the folder" "$AGENTS" 'its own file in `changes/`'
rs_require_load_bearing "the founded AGENTS.md says the fold gathers it" "$AGENTS" 'folds it into `changelog\.md`'
rs_require_load_bearing "the founded README names the folder" "$README" '`changes/`'
rs_require_load_bearing "the changelog template says where new entries wait" "$TEMPLATE" '`changes/`'
rs_require_load_bearing "WORKFLOW names the folder" "$WORKFLOW" 'its own small file in `changes/`'
rs_require_load_bearing "WORKFLOW says the fold gathers them" "$WORKFLOW" 'folds its file, and any still waiting, into changelog\.md'

# --- the fold, run ------------------------------------------------------------

[ -z "${RS_LIST:-}" ] || exit 0
[ -x "$FOLD" ] || rs_fail "the fold script is missing or not runnable"
command -v python3 >/dev/null 2>&1 || rs_fail "python3 is needed to run the fold"

WORK="$rs_dir/work"
mkdir -p "$WORK"
cd "$WORK"
git init -q -b main project
cd project
gitc() {
  git -c user.name=Rehearsal -c user.email=rehearsal@example.invalid "$@"
}
at() {
  # at <date> <git args...>: a commit or merge dated that day.
  when="$1T12:00:00"
  shift
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" gitc "$@"
}

cp "$TEMPLATE" CHANGELOG.md
printf '\n## 2026-07-01\n\n- Went live. Rollback: possible, not tried.\n' >> CHANGELOG.md
printf 'app\n' > app.txt
git add -A
at 2026-07-01 commit -q -m "A project founded before changes/ existed"

# A project with no folder: the fold writes nothing and creates nothing.
before=$(cat CHANGELOG.md)
out=$(python3 "$FOLD")
if [ -z "$out" ] && [ "$(cat CHANGELOG.md)" = "$before" ] && [ ! -e changes ] &&
  [ -z "$(git status --porcelain)" ]; then r=yes; else r=no; fi
rs_report "a project with no changes/ folder gets nothing written by a fold" "$r"

# The control. Two branches that each put an entry at the top of CHANGELOG.md
# conflict, so the rehearsal below can tell the old way from the new.
gitc switch -q -c old-a main
sed -i.bak '1a\
- Old way, first piece.' CHANGELOG.md && rm CHANGELOG.md.bak
at 2026-07-02 commit -q -am "old a"
gitc switch -q -c old-b main
sed -i.bak '1a\
- Old way, second piece.' CHANGELOG.md && rm CHANGELOG.md.bak
at 2026-07-02 commit -q -am "old b"
gitc switch -q main
at 2026-07-02 merge -q --no-ff -m "merge old a" old-a
if at 2026-07-02 merge -q --no-ff -m "merge old b" old-b >/dev/null 2>&1; then
  rs_fail "the control did not conflict, so the rehearsal cannot tell the two ways apart"
fi
gitc merge --abort
gitc reset -q --hard HEAD~1
rs_ok "the control: two entries added at the top of CHANGELOG.md conflict"

# Two pieces with the same short name, each on its own branch from main. The
# first piece in an older project creates the folder.
gitc switch -q -c piece-12 main
mkdir -p changes
printf 'Signing in now remembers you for a week.\n\nhttps://example.invalid/pull/31\n' > changes/12-sign-in.md
git add -A
at 2026-07-03 commit -q -m "piece 12"
gitc switch -q -c piece-15 main
mkdir -p changes
printf 'Signing in with a wrong password now says which part was wrong.\n\nhttps://example.invalid/pull/33\n' > changes/15-sign-in.md
git add -A
at 2026-07-03 commit -q -m "piece 15"
gitc switch -q -c piece-20 main
mkdir -p changes
printf 'The export includes the date column.\n\nhttps://example.invalid/pull/40\n' > changes/20-export.md
git add -A
at 2026-07-03 commit -q -m "piece 20, never merged"

gitc switch -q main
at 2026-07-04 merge -q --no-ff -m "merge 12" piece-12
if at 2026-07-06 merge -q --no-ff -m "merge 15" piece-15 >/dev/null 2>&1; then
  rs_ok "two branches that each add a changes file merge into main with no conflict"
else
  rs_fail "two branches that each add a changes file conflicted"
fi
if [ -f changes/12-sign-in.md ] && [ -f changes/15-sign-in.md ]; then r=yes; else r=no; fi
rs_report "the issue number keeps two pieces with the same short name apart" "$r"

# The fold runs on a branch cut from main, the way /sync and /ship save.
gitc switch -q -c records main
printf 'Half-written by somebody else.\n' > changes/30-draft.md
out=$(python3 "$FOLD")
printf '%s\n' "$out" | sed 's/^/    /'

log=$(cat CHANGELOG.md)
first=$(printf '%s\n' "$log" | grep -n '^## 2026-07-06$' | cut -d: -f1)
second=$(printf '%s\n' "$log" | grep -n '^## 2026-07-04$' | cut -d: -f1)
third=$(printf '%s\n' "$log" | grep -n '^## 2026-07-01$' | cut -d: -f1)
e15=$(printf '%s\n' "$log" | grep -n 'says which part was wrong' | cut -d: -f1)
e12=$(printf '%s\n' "$log" | grep -n 'remembers you for a week' | cut -d: -f1)
if [ -n "$first" ] && [ -n "$second" ] && [ -n "$third" ] && [ -n "$e15" ] && [ -n "$e12" ] &&
  [ "$first" -lt "$e15" ] && [ "$e15" -lt "$second" ] && [ "$second" -lt "$e12" ] &&
  [ "$e12" -lt "$third" ]; then r=yes; else r=no; fi
rs_report "the fold writes each entry newest first under the day it reached main" "$r"

if printf '%s\n' "$log" | grep -q '^- Signing in now remembers you for a week\. https://example\.invalid/pull/31$'; then r=yes; else r=no; fi
rs_report "an entry keeps its sentences and its pull request link on one line" "$r"

if printf '%s\n' "$log" | grep -q 'Went live. Rollback: possible, not tried.'; then r=yes; else r=no; fi
rs_report "a launch line /ship wrote directly is kept" "$r"
if printf '%s\n' "$log" | grep -q 'Example entry'; then r=yes; else r=no; fi
rs_report "the template's example is left as it was" "$r"

if [ -z "$(git ls-files changes/)" ] && [ ! -e changes/12-sign-in.md ] &&
  [ ! -e changes/15-sign-in.md ]; then r=yes; else r=no; fi
rs_report "the folded files are deleted, so the folder holds nothing saved" "$r"

if printf '%s\n' "$log" | grep -q 'date column'; then r=no; else r=yes; fi
rs_report "a file on an unmerged branch is not folded" "$r"
if [ -f changes/30-draft.md ] && ! printf '%s\n' "$log" | grep -q 'Half-written'; then r=yes; else r=no; fi
rs_report "a file nobody has committed stays where it is" "$r"

if git diff --cached --name-only | grep -q '^changes/12-sign-in.md$' &&
  ! git diff --cached --name-only | grep -q 'CHANGELOG.md'; then r=yes; else r=no; fi
rs_report "the fold stages the deletions and leaves the rest to the save route" "$r"

git add CHANGELOG.md
at 2026-07-06 commit -q -m "Fold the changes files"
out=$(python3 "$FOLD")
if [ -z "$out" ] && [ -z "$(git status --porcelain --untracked-files=no)" ]; then r=yes; else r=no; fi
rs_report "a second fold finds nothing and writes nothing" "$r"

# A reopened piece writes a file under a name the last fold already took away.
# It is dated by the day it arrived this time, never the first time.
gitc switch -q main
at 2026-07-06 merge -q --no-ff -m "merge the fold" records
gitc switch -q -c piece-12-again main
mkdir -p changes
printf 'Signing in now also remembers you on a second device.\n\nhttps://example.invalid/pull/52\n' > changes/12-sign-in.md
git add changes/12-sign-in.md
at 2026-07-08 commit -q -m "piece 12 reopened"
gitc switch -q main
at 2026-07-09 merge -q --no-ff -m "merge 12 again" piece-12-again
gitc switch -q -c records-2 main
python3 "$FOLD" > /dev/null
log=$(cat CHANGELOG.md)
top=$(printf '%s\n' "$log" | grep -n '^## 2026-07-09$' | cut -d: -f1)
again=$(printf '%s\n' "$log" | grep -n 'second device' | cut -d: -f1)
old=$(printf '%s\n' "$log" | grep -n '^## 2026-07-06$' | cut -d: -f1)
if [ -n "$top" ] && [ -n "$again" ] && [ -n "$old" ] && [ "$top" -lt "$again" ] &&
  [ "$again" -lt "$old" ]; then r=yes; else r=no; fi
rs_report "a name used again is dated by the day it arrived this time" "$r"
git add CHANGELOG.md
at 2026-07-09 commit -q -m "Fold again"

# A day that already has its own heading takes the new line at its top, with
# no second heading for the same day.
gitc switch -q main
at 2026-07-09 merge -q --no-ff -m "merge the second fold" records-2
gitc switch -q -c piece-21 main
mkdir -p changes
printf 'The report prints on one page.\n\nhttps://example.invalid/pull/60\n' > changes/21-report.md
git add changes/21-report.md
at 2026-07-09 commit -q -m "piece 21"
gitc switch -q main
at 2026-07-09 merge -q --no-ff -m "merge 21" piece-21
gitc switch -q -c records-3 main
python3 "$FOLD" > /dev/null
log=$(cat CHANGELOG.md)
heads=$(printf '%s\n' "$log" | grep -c '^## 2026-07-09$' || true)
head=$(printf '%s\n' "$log" | grep -n '^## 2026-07-09$' | cut -d: -f1)
report=$(printf '%s\n' "$log" | grep -n 'one page' | cut -d: -f1)
again=$(printf '%s\n' "$log" | grep -n 'second device' | cut -d: -f1)
if [ "$heads" = 1 ] && [ -n "$report" ] && [ "$head" -lt "$report" ] &&
  [ "$report" -lt "$again" ]; then r=yes; else r=no; fi
rs_report "an entry for a day that has its heading goes at the top of it" "$r"

# A changelog whose headings carry a title after the date, as a real one did.
# Those headings set the order and are never merged into, and a new day never
# lands at the end of the file.
cd "$WORK"
git init -q -b main titled
cd titled
printf '# Changelog\n\n## 2026-07-10 Launch of the booking page\n\n- Went live.\n\n## 2026-07-01 First version\n\n- Founded.\n' > CHANGELOG.md
git add -A
at 2026-07-01 commit -q -m "A changelog with titled headings"
mkdir -p changes
printf 'Bookings can be cancelled.\n\nhttps://example.invalid/pull/7\n' > changes/7-cancel.md
git add -A
at 2026-07-05 commit -q -m "piece 7"
printf 'Bookings show the room.\n\nhttps://example.invalid/pull/8\n' > changes/8-room.md
git add -A
at 2026-07-12 commit -q -m "piece 8"
printf 'Bookings show the price.\n\nhttps://example.invalid/pull/9\n' > changes/9-price.md
git add -A
at 2026-07-10 commit -q -m "piece 9, the launch day"
python3 "$FOLD" > /dev/null
log=$(cat CHANGELOG.md)
n12=$(printf '%s\n' "$log" | grep -n '^## 2026-07-12$' | cut -d: -f1)
room=$(printf '%s\n' "$log" | grep -n 'show the room' | cut -d: -f1)
launch=$(printf '%s\n' "$log" | grep -n '^## 2026-07-10 Launch' | cut -d: -f1)
price=$(printf '%s\n' "$log" | grep -n 'show the price' | cut -d: -f1)
n05=$(printf '%s\n' "$log" | grep -n '^## 2026-07-05$' | cut -d: -f1)
cancel=$(printf '%s\n' "$log" | grep -n 'can be cancelled' | cut -d: -f1)
first=$(printf '%s\n' "$log" | grep -n '^## 2026-07-01 First' | cut -d: -f1)
last=$(printf '%s\n' "$log" | tail -1)
if [ -n "$n12" ] && [ -n "$room" ] && [ -n "$launch" ] && [ -n "$n05" ] && [ -n "$cancel" ] &&
  [ -n "$first" ] && [ "$n12" -lt "$room" ] && [ "$room" -lt "$launch" ] &&
  [ -n "$price" ] && [ "$launch" -lt "$price" ] && [ "$price" -lt "$n05" ] &&
  [ "$n05" -lt "$cancel" ] && [ "$cancel" -lt "$first" ] &&
  [ "$last" = "- Founded." ]; then r=yes; else r=no; fi
rs_report "titled headings set the order, and a new day never lands at the end" "$r"

rs_done
