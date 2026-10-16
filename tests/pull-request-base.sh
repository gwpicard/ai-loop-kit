#!/usr/bin/env sh
# Check both the branch decision and the workflow that supplies its input.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/.agents/tools/check-pull-request-base.sh"
WORKFLOW="$ROOT/.github/workflows/pull-request-base.yml"
fail() { echo "FAIL: $1" >&2; exit 1; }

[ -x "$CHECK" ] || fail "a pull request aimed at stable has no base guard"
status=0
message=$("$CHECK" stable 2>&1) || status=$?
[ "$status" -eq 1 ] || fail "stable must be refused with exit 1"
printf '%s' "$message" | grep -qF -- '--base main' || fail "no repair instruction"
for base in main topic stable-fix unstable Stable; do
  "$CHECK" "$base" >/dev/null || fail "$base was refused"
done
for base in missing empty extra; do
  status=0
  case "$base" in
    missing) "$CHECK" >/dev/null 2>&1 || status=$? ;;
    empty) "$CHECK" '' >/dev/null 2>&1 || status=$? ;;
    extra) "$CHECK" main extra >/dev/null 2>&1 || status=$? ;;
  esac
  [ "$status" -eq 2 ] || fail "$base input must exit 2"
done

[ -f "$WORKFLOW" ] || fail "the base guard has no workflow"
declared=$(sed 's/#.*//' "$WORKFLOW")
printf '%s\n' "$declared" | grep -qE '^  pull_request:$' || fail "no PR trigger"
printf '%s\n' "$declared" | grep -qE '^ +types: \[opened, reopened, synchronize, edited, ready_for_review\]$' || fail "the workflow must recheck an edited base"
printf '%s\n' "$declared" | grep -qF 'BASE: ${{ github.event.pull_request.base.ref }}' || fail "wrong base input"
printf '%s\n' "$declared" | grep -qE '^ +run: \.agents/tools/check-pull-request-base\.sh "\$BASE"$' || fail "the workflow must pass BASE as data"
if printf '%s\n' "$declared" | grep -E '^ +run:' | grep -qF 'github.event'; then
  fail "PR data is interpolated into a command"
fi
echo "pull-request-base: all checks passed"
