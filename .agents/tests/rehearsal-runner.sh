#!/usr/bin/env sh
# rehearsal-runner.sh: prove the runner that carries every other rehearsal keeps
# the guarantee it inherited.
#
# One failure must never hide another. A job for each rehearsal got that from
# the workflow's fail-fast: false, which a validator could read straight off the
# file. Running them all in one job is what keeps the bill down, and it puts the
# same guarantee in a shell loop, where nothing can read it off the file and
# only running it settles whether it holds. So this runs it.
#
# The runner finds its folder from its own location, so a copy placed in a
# throwaway tree rehearses against stub scripts and never touches the real ones.

set -eu

RUNNER=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/run-all.sh
[ -x "$RUNNER" ] || { echo "FAIL: no runnable runner at $RUNNER" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

TESTS="$WORK/.agents/tests"
mkdir -p "$TESTS"
cp "$RUNNER" "$TESTS/run-all.sh"
chmod +x "$TESTS/run-all.sh"

stub() {
  # stub <name> <exit-code>
  printf '#!/bin/sh\necho "%s ran"\nexit %s\n' "$1" "$2" > "$TESTS/$1.sh"
  chmod +x "$TESTS/$1.sh"
}

# The first one fails. If the run stopped there, nothing after it would report,
# which is the exact fault fail-fast: false was set to prevent.
stub a-first-fails 1
stub b-passes 0
stub c-also-fails 1
stub d-passes 0

# mutate.sh audits the suite rather than passing or failing. It must be skipped,
# not run and counted.
stub mutate 1

# A sync daemon watching this folder writes copies as "<name> 2.sh". A copy of
# the runner that is not skipped gets run as a rehearsal, runs the whole suite
# again, reaches its own copy again, and never finishes. That is worse than a
# failure: a hosted job hangs rather than fails, and is billed until it is cut
# off.
#
# These stand in for the copies rather than being real ones. A real copy would
# recurse for as long as the rule is right and for ever the moment it is wrong,
# and a check that hangs the suite is worse than the fault it is testing. What
# is actually in question is the selection, so a stub that says whether it was
# invoked settles it: remove the leading-name match and these get run, and the
# checks below say so.
stub 'mutate 2' 1
stub 'run-all 2' 1

OUT="$WORK/out.log"
status=0
GITHUB_STEP_SUMMARY="$WORK/summary.md" "$TESTS/run-all.sh" > "$OUT" 2>&1 || status=$?

pass=0
check() {
  # check <description> <condition-already-evaluated>
  if [ "$2" = yes ]; then
    echo "  ok: $1"
    pass=$((pass + 1))
  else
    echo "FAIL: $1" >&2
    echo "--- runner output ---" >&2
    cat "$OUT" >&2
    exit 1
  fi
}

said() {
  if grep -qF "$1" "$OUT"; then echo yes; else echo no; fi
}

check "a failing rehearsal makes the run fail" \
  "$([ "$status" -ne 0 ] && echo yes || echo no)"

# The guarantee itself: a failure at the very start does not stop what follows.
check "a rehearsal after the first failure still ran" "$(said 'b-passes ran')"
check "the last rehearsal still ran" "$(said 'd-passes ran')"

check "the first failure is named" "$(said 'a-first-fails')"
check "the second failure is named too, so one cannot hide another" \
  "$(said 'c-also-fails')"
check "a passing rehearsal is not reported as failed" \
  "$(grep -A9 'These rehearsals failed' "$OUT" | grep -qF 'b-passes' && echo no || echo yes)"

check "mutate is skipped rather than run" \
  "$(grep -qF 'mutate ran' "$OUT" && echo no || echo yes)"
check "a copy of the runner is skipped, so the suite cannot run itself" \
  "$(grep -qF 'run-all 2 ran' "$OUT" && echo no || echo yes)"
check "a copy of mutate is skipped too" \
  "$(grep -qF 'mutate 2 ran' "$OUT" && echo no || echo yes)"
check "the count covers every rehearsal and no more" "$(said '2 of 4 rehearsals passed')"

check "the run summary names the failures" \
  "$(grep -qF 'a-first-fails' "$WORK/summary.md" && \
     grep -qF 'c-also-fails' "$WORK/summary.md" && echo yes || echo no)"

# A suite where everything passes must not be reported as a failure.
rm "$TESTS/a-first-fails.sh" "$TESTS/c-also-fails.sh"
clean=0
"$TESTS/run-all.sh" > "$WORK/clean.log" 2>&1 || clean=$?
check "a suite with nothing failing passes" \
  "$([ "$clean" -eq 0 ] && grep -qF '2 of 2 rehearsals passed' "$WORK/clean.log" && \
     echo yes || echo no)"

echo
echo "rehearsal-runner.sh: all $pass checks passed"
