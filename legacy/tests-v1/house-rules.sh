#!/usr/bin/env sh
# House rules for every tracked file, as one rehearsal.
#
# Lifted from the old kit validator, so the guards survive when that validator
# is removed. It checks, over the files Git tracks:
#   1. no issue or pull request number written as a hash and digits;
#   2. no AI attribution line and no link back to a coding session;
#   3. no copied-and-kept file beside an original;
#   4. every shell file under kit/ and tests/ passes sh -n;
#   5. every script under kit/ and tests/ that starts with a shebang is
#      saved as runnable, apart from files that are only ever sourced;
#   6. the commit-msg hook is saved as runnable.
#
# The patterns are built from pieces so this file does not report itself.
#
# Usage:
#   tests/house-rules.sh                 check the repository holding this file,
#                                        then run the self-test
#   tests/house-rules.sh --root <folder> check another Git repository, then
#                                        run the self-test
#   tests/house-rules.sh --selftest      plant each fault in a throwaway
#                                        repository and require a failure

set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
SELF="$HERE/$(basename -- "$0")"
MODE=check

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      [ $# -ge 2 ] || { echo "house-rules: --root needs a folder" >&2; exit 2; }
      ROOT=$(CDPATH= cd -- "$2" && pwd) || exit 2
      shift 2
      ;;
    --selftest) MODE=selftest; shift ;;
    *) echo "house-rules: unknown option $1" >&2; exit 2 ;;
  esac
done

# Files that are only sourced or imported, so they need no runnable mode.
sourced_only="rule-shape.sh recipe-rehearsal.sh _common.sh permission-matcher.py"

run_checks() {
  root="$1"
  failures=0
  fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }
  pass() { printf 'ok: %s\n' "$1"; }

  git -C "$root" rev-parse --git-dir >/dev/null 2>&1 || {
    echo "house-rules: $root is not a Git repository" >&2
    return 2
  }

  # 1. Numbers.
  hash_char='#'
  refs=$(git -C "$root" grep -InE \
    "(^|[^A-Za-z0-9\$}])${hash_char}[0-9]{2,4}([^0-9]|\$)" 2>/dev/null | cut -c1-120)
  if [ -n "$refs" ]; then
    fail "a tracked file cites an issue or pull request by number:"
    printf '%s\n' "$refs" | sed 's/^/    /'
  else
    pass "no tracked file cites an issue or pull request by number"
  fi

  # 2. Attribution and session links.
  attr_session=$(printf 'claude.ai/code/%s' 'session_')
  attr_author=$(printf 'Co-%sed-By: Claude' 'Author')
  attr_vendor=$(printf 'noreply@%s.com' 'anthropic')
  attr_hits=$(git -C "$root" grep -InIiF \
    -e "$attr_session" -e "$attr_author" -e "$attr_vendor" \
    -- . ':(exclude).githooks/commit-msg' 2>/dev/null | cut -c1-120)
  if [ -n "$attr_hits" ]; then
    fail "a tracked file carries an AI attribution line or a session link:"
    printf '%s\n' "$attr_hits" | sed 's/^/    /'
  else
    pass "no tracked file carries an AI attribution line or a session link"
  fi

  # 3. Copies lying beside originals.
  strays=$(git -C "$root" ls-files | grep -E \
    '(^|/)[^/]* [0-9](\.[^/]*)?(/|$)|(^|/)[^/]* copy(\.[^/]*)?(/|$)' || true)
  if [ -n "$strays" ]; then
    fail "copies of files are lying beside the originals:"
    printf '%s\n' "$strays" | sed 's/^/    /'
  else
    pass "no copied-and-kept files are tracked"
  fi

  # 4 and 5. Shell syntax and runnable mode.
  syntax_bad=""
  mode_bad=""
  files=$(git -C "$root" ls-files -s -- kit tests 2>/dev/null)
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    mode=${line%% *}
    path=${line#*	}
    [ -f "$root/$path" ] || continue
    base=$(basename -- "$path")
    case "$base" in
      *.sh)
        sh -n "$root/$path" 2>/dev/null || syntax_bad="$syntax_bad $path"
        ;;
    esac
    case " $sourced_only " in *" $base "*) continue ;; esac
    first=$(head -c 2 "$root/$path" 2>/dev/null)
    if [ "$first" = '#!' ] && [ "$mode" != "100755" ]; then
      mode_bad="$mode_bad $path"
    fi
  done <<LIST
$files
LIST
  if [ -n "$syntax_bad" ]; then
    fail "sh -n refuses:$syntax_bad"
  else
    pass "every shell file under kit and tests passes sh -n"
  fi
  if [ -n "$mode_bad" ]; then
    fail "a script starts with a shebang but is not saved as runnable:$mode_bad"
  else
    pass "every script under kit and tests is saved as runnable"
  fi

  # 6. The commit-msg hook.
  hook_mode=$(git -C "$root" ls-files -s -- .githooks/commit-msg | cut -d' ' -f1)
  if [ -z "$hook_mode" ] || [ "$hook_mode" = "100755" ]; then
    pass "the commit-msg hook is saved as runnable"
  else
    fail ".githooks/commit-msg is saved as $hook_mode, not 100755"
  fi

  [ "$failures" -eq 0 ]
}

if [ "$MODE" = check ]; then
  run_checks "$ROOT" || exit 1
  # The self-test runs after every check, so the run-all runner proves that
  # the check can fail each time it proves that the repository passes.
  exec "$SELF" --selftest
fi

# ---------------------------------------------------------------------------
# Self-test. A check that cannot fail proves nothing, so plant each fault in a
# throwaway repository and require the check to refuse it.

WORK=$(mktemp -d) || exit 2
trap 'rm -rf "$WORK"' EXIT INT TERM
selftest_failed=0

new_repo() {
  repo="$WORK/$1"
  mkdir -p "$repo/kit/scripts" "$repo/tests"
  git -C "$repo" init -q
  printf '#!/usr/bin/env sh\necho fine\n' > "$repo/kit/scripts/ok.sh"
  printf '#!/usr/bin/env sh\necho fine\n' > "$repo/tests/ok.sh"
  chmod 755 "$repo/kit/scripts/ok.sh" "$repo/tests/ok.sh"
  printf 'A plain note.\n' > "$repo/README.md"
  git -C "$repo" add -A
}

expect_pass() {
  new_repo "$1"
  if run_checks "$repo" >/dev/null 2>&1; then
    echo "ok: clean repository passes"
  else
    echo "SELFTEST FAIL: a clean repository was refused"
    selftest_failed=1
  fi
}

expect_refusal() {
  label="$1"
  plant="$2"
  new_repo "$label"
  eval "$plant"
  git -C "$repo" add -A
  if run_checks "$repo" >/dev/null 2>&1; then
    echo "SELFTEST FAIL: planted fault not caught: $label"
    selftest_failed=1
  else
    echo "ok: planted fault caught: $label"
  fi
}

expect_pass clean
expect_refusal number \
  'printf "See %s%s for the story.\n" "#" "123" > "$repo/note.md"'
expect_refusal session-link \
  'printf "from %s%s\n" "claude.ai/code/" "session_abc" > "$repo/note.md"'
expect_refusal author-line \
  'printf "%s%s\n" "Co-Author" "ed-By: Claude" > "$repo/note.md"'
expect_refusal stray-copy \
  'cp "$repo/kit/scripts/ok.sh" "$repo/kit/scripts/ok copy.sh"; chmod 755 "$repo/kit/scripts/ok copy.sh"'
expect_refusal not-runnable \
  'chmod 644 "$repo/tests/ok.sh"'
expect_refusal bad-syntax \
  'printf "#!/usr/bin/env sh\nif then fi\n" > "$repo/tests/bad.sh"; chmod 755 "$repo/tests/bad.sh"'

# The number rule must also reach files that are not Markdown or shell.
expect_refusal number-in-python \
  'printf "# see %s%s\n" "#" "456" > "$repo/kit/scripts/x.py"'

# The check must not report itself: run it on the real tree's own file.
if grep -nE "(^|[^A-Za-z0-9\$}])#[0-9]{2,4}([^0-9]|\$)" "$SELF" >/dev/null 2>&1; then
  echo "SELFTEST FAIL: this file carries a number pattern"
  selftest_failed=1
else
  echo "ok: this file carries no number pattern"
fi

[ "$selftest_failed" -eq 0 ] && echo "Self-test passed." || echo "Self-test failed."
exit "$selftest_failed"
