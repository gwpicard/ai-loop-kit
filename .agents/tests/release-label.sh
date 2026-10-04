#!/usr/bin/env sh
# release-label.sh: check the guard that refuses an unsorted pull request.
#
# The failure it exists to stop is silent. An unlabelled pull request does not
# error; Release Drafter files it under "Other changes" and calls the release a
# patch. So the only thing worth testing is that the guard actually refuses, and
# that it refuses nothing it should accept.
#
# The second assertion here matters more than the first. The accepted set is
# written out in the script, and the labels Release Drafter reads are written out
# in its configuration. Two lists of the same thing drift. This reads the
# configuration and requires the script to accept every label named in it, so a
# label added to one and forgotten in the other fails here rather than in a
# release.
#
# Everything runs against the real script. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
CHECK="$ROOT/.agents/tools/check-release-label.sh"
DRAFTER="$ROOT/.github/release-drafter.yml"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

[ -x "$CHECK" ] || { echo "FAIL: $CHECK is not executable" >&2; exit 1; }
[ -f "$DRAFTER" ] || { echo "FAIL: $DRAFTER is missing" >&2; exit 1; }

echo "== What it refuses =="

# The case the guard exists for. Nothing is wrong with the pull request; nobody
# has said what kind of change it is.
if printf '' | "$CHECK" >/dev/null 2>&1; then
  fail "a pull request with no labels at all was accepted"
else
  pass "no label at all is refused"
fi

# A pull request can carry plenty of labels and still say nothing about the
# release. Subject labels are for reading the backlog, not for sorting a release.
if printf 'area:skills\nrefined\nepic\n' | "$CHECK" >/dev/null 2>&1; then
  fail "labels that say nothing about the release were accepted"
else
  pass "labels that do not sort the release are refused"
fi

# The message is what a person sees on a red check, so it has to name the way out
# rather than only the problem.
message=$(printf 'area:docs\n' | "$CHECK" 2>&1 >/dev/null || true)
printf '%s' "$message" | grep -q "feature" \
  && pass "the refusal names the labels that would pass" \
  || fail "the refusal does not say what to add"
printf '%s' "$message" | grep -q "area:docs" \
  && pass "the refusal says which labels it did find" \
  || fail "the refusal does not report the labels found"

echo "== What it accepts =="

for label in feature enhancement bug documentation chore skip-release-notes \
             release-major release-minor release-patch; do
  printf '%s\n' "$label" | "$CHECK" >/dev/null 2>&1 \
    || fail "$label was refused"
done
pass "every label that sorts a release is accepted"

# A real pull request carries a mix. One accepted label among several is enough,
# because somebody chose.
printf 'area:skills\nrefined\nbug\n' | "$CHECK" >/dev/null 2>&1 \
  && pass "one sorting label among several others is enough" \
  || fail "a mix containing bug was refused"

# Near-misses. A label that merely contains an accepted word has not sorted
# anything, and matching loosely would accept the very pull requests this exists
# to catch.
for near in bugfix features documentation-only release; do
  printf '%s\n' "$near" | "$CHECK" >/dev/null 2>&1 \
    && fail "'$near' was accepted, so the match is not on the whole label" \
    || true
done
pass "a label that only resembles an accepted one is refused"

echo "== The two lists cannot drift apart =="

# Every label Release Drafter reads has to be one this guard accepts. Otherwise
# somebody labels a pull request the way the configuration says, and the check
# refuses it.
drafter_labels=$(grep -oE '^ +- [a-z-]+$' "$DRAFTER" | sed 's/^ *- //' | sort -u)
drafter_labels="$drafter_labels
$(grep -oE 'label: [a-z-]+' "$DRAFTER" | sed 's/label: //' | sort -u)"

missing=""
for label in $drafter_labels; do
  [ -n "$label" ] || continue
  printf '%s\n' "$label" | "$CHECK" >/dev/null 2>&1 \
    || missing="$missing $label"
done

if [ -n "$missing" ]; then
  fail "Release Drafter reads labels this guard refuses:$missing"
else
  pass "every label Release Drafter reads is accepted here"
fi

if [ "$FAIL" -eq 0 ]; then
  echo
  echo "release-label.sh: all checks passed"
else
  echo
  echo "release-label.sh: FAILED" >&2
fi
exit "$FAIL"
