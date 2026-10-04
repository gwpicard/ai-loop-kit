#!/usr/bin/env sh
# pull-request-base.sh: check the guard that refuses a pull request into stable.
#
# `stable` is the default branch, so a pull request aims at it unless somebody
# changes the base. One did, and merged, and the next release could not move
# `stable` until a person turned a protection off by hand. The guard is a check
# that goes red on such a pull request. This runs the real script against both
# bases and reads the workflow that calls it.
#
# The workflow half matters as much as the script. A script that refuses
# `stable` proves nothing if the workflow hands it the wrong branch, or never
# runs again after somebody fixes the base, which leaves the red mark in place
# and teaches people to ignore it.
#
# No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
CHECK="$ROOT/.agents/tools/check-pull-request-base.sh"
WORKFLOW="$ROOT/.github/workflows/pull-request-base.yml"
SOURCE_CHECKS="$ROOT/.github/workflows/source-checks.yml"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

[ -x "$CHECK" ] || { echo "FAIL: $CHECK is not executable" >&2; exit 1; }
[ -f "$WORKFLOW" ] || { echo "FAIL: $WORKFLOW is missing" >&2; exit 1; }

echo "== What it refuses =="

if "$CHECK" stable >/dev/null 2>&1; then
  fail "a pull request based on stable was accepted"
else
  pass "a stable base is refused"
fi

# The message is what a person sees on a red check, so it has to name the
# branch it refused and the way out.
message=$("$CHECK" stable 2>&1 >/dev/null || true)
printf '%s' "$message" | grep -qF "'stable'" \
  && pass "the refusal names stable" \
  || fail "the refusal does not name stable"
printf '%s' "$message" | grep -qF -- "--base main" \
  && pass "the refusal names --base main" \
  || fail "the refusal does not say to pass --base main"

# A missing base is a broken workflow, not a pull request that passed.
if "$CHECK" >/dev/null 2>&1; then
  fail "no base at all was accepted"
else
  pass "no base at all is refused"
fi
if "$CHECK" "" >/dev/null 2>&1; then
  fail "an empty base was accepted"
else
  pass "an empty base is refused"
fi

echo "== What it accepts =="

"$CHECK" main >/dev/null 2>&1 \
  && pass "a main base is accepted" \
  || fail "a pull request based on main was refused"

# Stacking one pull request on another working branch is ordinary. A guard that
# refused every base but main would stop it.
"$CHECK" refuse-pull-request-into-stable >/dev/null 2>&1 \
  && pass "a base on another working branch is accepted" \
  || fail "a pull request stacked on a working branch was refused"

# Branch names are exact. A branch that only contains the word is a different
# branch, and a loose match would refuse it.
for near in stable-fix unstable Stable; do
  "$CHECK" "$near" >/dev/null 2>&1 \
    || fail "'$near' was refused, so the match is not on the whole name"
done
pass "a branch that only resembles stable is accepted"

echo "== The workflow calls it correctly =="

# Comments come out first. The workflow explains itself in prose, and a grep
# that reads the explanation would pass a file whose real line was deleted.
declared=$(sed 's/#.*//' "$WORKFLOW")

printf '%s\n' "$declared" | grep -qE '^ +BASE: \$\{\{ github\.event\.pull_request\.base\.ref \}\}$' \
  && pass "the workflow reads the base from the pull request" \
  || fail "the workflow does not pass the pull request's base branch"

printf '%s\n' "$declared" | grep -qE '^ +run: \.agents/tools/check-pull-request-base\.sh "\$BASE"$' \
  && pass "the workflow runs the script with the base from the environment" \
  || fail "the workflow does not run check-pull-request-base.sh with \"\$BASE\""

# A branch name written straight into the run block would be read as part of
# the command.
if printf '%s\n' "$declared" | grep -E '^ +run:' | grep -qF 'github.event'; then
  fail "the run block expands the pull request's data directly"
else
  pass "no pull request data is expanded inside the run block"
fi

# Changing the base sends `edited`. Without it the red mark stays after the fix.
printf '%s\n' "$declared" | grep -qE '^ +types: \[.*\bedited\b.*\]$' \
  && pass "the check runs again when the base is changed" \
  || fail "the workflow does not run on edited, so a fixed base stays red"

# Source checks cancels a running rehearsal when the same pull request fires
# again, and `edited` fires on every change to a title. The guard stays apart.
if grep -qF 'check-pull-request-base' "$SOURCE_CHECKS"; then
  fail "the guard moved into source checks, where an edit would cancel the rehearsals"
else
  pass "the guard stays out of source checks"
fi

if [ "$FAIL" -eq 0 ]; then
  echo
  echo "pull-request-base.sh: all checks passed"
else
  echo
  echo "pull-request-base.sh: FAILED" >&2
fi
exit "$FAIL"
