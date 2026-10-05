#!/usr/bin/env sh
# bar-guard.sh: list every change a build made to what it is measured against.
#
# A builder working alone can turn a red check green without touching the code
# under test: edit the check, skip it, silence the linter on the line it trips,
# loosen a tool's settings, rewrite a snapshot, or change the project check or
# the gate itself. This lists each such change, named or not, so the gate can
# refuse the ones the piece did not name and send the named ones to the
# person. It wraps test-guard.sh, beside it, for the tests.
#
# Usage: bar-guard.sh <base> <piece-file> [spec-commit]
#   base         the commit the piece's branch was cut from: main, or the
#                branch of the piece it stacks on
#   piece-file   the piece's text, or - to read it from standard input
#   spec-commit  the commit at the tip of the piece's acceptance branch when it
#                was made ready. A build or fix piece with no acceptance branch
#                gives the commit on its branch that first holds its checks
#                instead. Left out for a goal or gauntlet piece, and then no
#                acceptance check is listed.
#
# Run it from inside the project. It compares with the working tree, so a
# change that is committed, staged or not yet staged all count, and so does a
# new file git does not ignore.
#
# It prints one line for each change, as <kind><TAB><path><TAB>named or
# <kind><TAB><path><TAB>not named. The seven kinds:
#   acceptance-check  a file the acceptance branch added or changed, between
#                     its merge base with origin/main (or with the base, where
#                     there is no origin/main) and the spec commit, that has
#                     changed since the spec commit. It is never named: a check
#                     changes only by being reported.
#   existing-test     a test that existed at the base and was edited, deleted
#                     or moved: test-guard.sh's rule, and its naming rule.
#   skip-or-focus     a skip or focus marker added to a test.
#   suppression       a lint or type suppression added.
#   tool-settings     a test, lint, type-check or coverage tool's settings file
#                     gained or lost a line. Taking a setting out can loosen a
#                     tool as surely as adding one.
#   snapshot          a snapshot that existed at the base and changed.
#   guarded-file      a change to a workflow, the gate and its scripts, the
#                     hooks or the Claude Code settings.
# A marker or suppression that is only taken out is not listed. The acceptance checks are left out of the six other kinds, since they
# are the bar rather than the build.
#
# For the five kinds after existing-test, a change counts as named only on a
# line under the piece's Under the hood that starts `Changes the bar:` and gives
# the whole path and then a reason:
#   Changes the bar: jest.config.js, because the refund tests need longer.
#
# A test file moved away is listed under its old path, and its new path is
# named on standard error. Exits 0 when nothing is listed or every listed change
# is named, 1 when a listed change is not named, and 2 when it could not run.

set -eu

fail() {
  echo "bar-guard: $1" >&2
  exit 2
}

[ "$#" -eq 2 ] || [ "$#" -eq 3 ] || \
  fail "usage: bar-guard.sh <base> <piece-file> [spec-commit]"
base=$1
piece=$2
spec=${3:-}

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_guard="$here/test-guard.sh"
[ -f "$test_guard" ] || fail "test-guard.sh is not beside this script"

gitq() { git -c core.quotePath=false "$@"; }

gitq rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
  fail "run it from inside the project's folder"
gitq rev-parse --verify --quiet "$base^{commit}" >/dev/null || \
  fail "the base '$base' is not a commit in this project"
if [ -n "$spec" ]; then
  gitq rev-parse --verify --quiet "$spec^{commit}" >/dev/null || \
    fail "the spec commit '$spec' is not a commit in this project"
fi
top=$(gitq rev-parse --show-toplevel)
cd "$top"

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT INT TERM

if [ "$piece" = "-" ]; then
  cat > "$scratch/piece"
else
  [ -f "$piece" ] || fail "the piece file '$piece' does not exist"
  cat "$piece" > "$scratch/piece"
fi

# The paths named on a Changes the bar line under Under the hood, found the way
# test-guard.sh finds the section: a collapsed details block, or a heading of
# its own. A line counts only with a reason after the path.
awk '
  /<summary>[[:space:]]*Under the hood[[:space:]]*<\/summary>/ { inside = 1; next }
  inside == 1 && /<\/details>/ { inside = 0; next }
  /^#+[[:space:]]*Under the hood[[:space:]]*$/ { inside = 2; next }
  inside == 2 && /^#+[[:space:]]/ { inside = 0 }
  inside && /^[[:space:]]*([-*][[:space:]]+)?Changes the bar:/ {
    line = $0
    sub(/^[[:space:]]*([-*][[:space:]]+)?Changes the bar:[[:space:]]*/, "", line)
    path = line
    sub(/[,[:space:]].*$/, "", path)
    rest = substr(line, length(path) + 1)
    gsub(/[`"\047]/, "", path)
    if (path != "" && rest ~ /[A-Za-z0-9]/) print path
  }
' "$scratch/piece" > "$scratch/named"

# The same rule for a test file as test-guard.sh's, kept identical to it.
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

in_list() {
  grep -qxF -- "$1" "$2" 2>/dev/null
}

# --- the acceptance checks ------------------------------------------------

: > "$scratch/acceptance"
if [ -n "$spec" ]; then
  if gitq rev-parse --verify --quiet "refs/remotes/origin/main^{commit}" >/dev/null; then
    from=$(gitq merge-base origin/main "$spec") || fail "the spec commit shares no history with origin/main"
  else
    from=$(gitq merge-base "$base" "$spec") || fail "the spec commit shares no history with the base"
  fi
  gitq diff --no-renames --name-only "$from" "$spec" -- > "$scratch/acceptance"
fi

: > "$scratch/listed"
add() {
  # add <kind> <path> <named|not named>
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$scratch/listed"
}

if [ -n "$spec" ]; then
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    gitq diff --quiet "$spec" -- "$path" 2>/dev/null && continue
    add acceptance-check "$path" "not named"
  done < "$scratch/acceptance"
fi

# --- the existing tests, through test-guard.sh ------------------------------
#
# Run once with no piece, which lists every changed test, and once with the
# piece, which lists those it does not name. The difference is the named ones.

set +e
sh "$test_guard" "$base" - < /dev/null > "$scratch/tests-all" 2> "$scratch/tests-moved"
all_code=$?
sh "$test_guard" "$base" "$scratch/piece" > "$scratch/tests-unnamed" 2> "$scratch/tests-err"
unnamed_code=$?
set -e
[ "$all_code" -ne 2 ] || fail "test-guard.sh could not run: $(cat "$scratch/tests-moved")"
[ "$unnamed_code" -ne 2 ] || fail "test-guard.sh could not run: $(cat "$scratch/tests-err")"

while IFS= read -r path; do
  [ -n "$path" ] || continue
  in_list "$path" "$scratch/acceptance" && continue
  if in_list "$path" "$scratch/tests-unnamed"; then
    add existing-test "$path" "not named"
  else
    add existing-test "$path" "named"
  fi
done < "$scratch/tests-all"

# A moved test's new path, for the put-back.
while IFS= read -r line; do
  case "$line" in
    "test-guard: "*" was moved to "*)
      old=${line#test-guard: }
      old=${old%% was moved to *}
      in_list "$old" "$scratch/acceptance" || echo "bar-guard: ${line#test-guard: }" >&2 ;;
  esac
done < "$scratch/tests-moved"

# --- the five kinds this script adds ---------------------------------------

named_or_not() {
  if in_list "$1" "$scratch/named"; then echo "named"; else echo "not named"; fi
}

SKIP='\.skip\(|\.only\(|(^|[^A-Za-z0-9_.$])(xit|xdescribe|xtest|fit|fdescribe)\(|@pytest\.mark\.(skip|xfail)|pytest\.skip\(|(^|[^A-Za-z0-9_])t\.Skip|@?unittest\.skip'
SUPPRESS='eslint-disable|@ts-ignore|@ts-expect-error|#[[:space:]]*type:[[:space:]]*ignore|#[[:space:]]*noqa|#[[:space:]]*pylint:[[:space:]]*disable|//[[:space:]]*nolint'

# How many lines carry a pattern, at the base and now.
count_base() {
  if gitq cat-file -e "$base:$2" 2>/dev/null; then
    gitq show "$base:$2" | grep -I -c -E -- "$1" || true
  else
    echo 0
  fi
}
count_now() {
  if [ -f "$2" ]; then grep -I -c -E -- "$1" "$2" || true; else echo 0; fi
}
gained() {
  [ "$(count_now "$1" "$2")" -gt "$(count_base "$1" "$2")" ]
}

is_settings() {
  case "${1##*/}" in
    jest.config.*|vitest.config.*|eslint.config.*|.eslintrc*|.coveragerc|setup.cfg|\
    pyproject.toml|ruff.toml|mypy.ini) return 0 ;;
    tsconfig*.json) return 0 ;;
  esac
  return 1
}

is_snapshot() {
  case "/$1" in
    */__snapshots__/*|*.snap) return 0 ;;
  esac
  return 1
}

is_guarded() {
  case "$1" in
    .github/workflows/*|.agents/hooks/*|.agents/tools/*|.githooks/*|.husky/*|\
    .claude/settings.json) return 0 ;;
  esac
  return 1
}

# Every changed path, with a file nobody has staged yet counted as added.
tab=$(printf '\t')
gitq diff --no-renames --name-status "$base" -- > "$scratch/changed"
gitq ls-files --others --exclude-standard | while IFS= read -r path; do
  printf 'A\t%s\n' "$path"
done >> "$scratch/changed"
while IFS="$tab" read -r status path; do
  [ -n "$path" ] || continue
  in_list "$path" "$scratch/acceptance" && continue
  if [ "$status" != "D" ]; then
    if is_test "$path" && gained "$SKIP" "$path"; then
      add skip-or-focus "$path" "$(named_or_not "$path")"
    fi
    if gained "$SUPPRESS" "$path"; then
      add suppression "$path" "$(named_or_not "$path")"
    fi
  fi
  if is_settings "$path"; then
    # Lines added and lines taken out both count: a setting removed, such as
    # "strict": true, lowers the bar as surely as one added.
    if gitq ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
      moved=$(gitq diff --numstat "$base" -- "$path" | awk -F "$tab" '{ s += $1 + $2 } END { print s + 0 }')
    elif [ -f "$path" ]; then
      moved=$(grep -c '' "$path" || true)
    else
      moved=$(gitq diff --numstat "$base" -- "$path" | awk -F "$tab" '{ s += $1 + $2 } END { print s + 0 }')
    fi
    if [ "$moved" -gt 0 ]; then
      add tool-settings "$path" "$(named_or_not "$path")"
    fi
  fi
  if is_snapshot "$path" && [ "$status" != "A" ]; then
    add snapshot "$path" "$(named_or_not "$path")"
  fi
  if is_guarded "$path"; then
    add guarded-file "$path" "$(named_or_not "$path")"
  fi
done < "$scratch/changed"

cat "$scratch/listed"
if grep -q "${tab}not named\$" "$scratch/listed"; then
  exit 1
fi
exit 0
