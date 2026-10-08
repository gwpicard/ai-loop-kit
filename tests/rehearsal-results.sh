#!/usr/bin/env sh
# Separate required skips, optional omissions, passes and failures in the runner.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
# Retain fixtures and logs for inspection.
failures=0
check() {
  if "$@"; then :; else
    echo "FAIL: $*" >&2
    failures=$((failures + 1))
  fi
}
new_tree() {
  tree="$WORK/$1"
  mkdir -p "$tree/tests"
  cp "$ROOT/tests/run-all.sh" "$tree/tests/run-all.sh"
}
stub() {
  printf '#!/bin/sh\nprintf "%%s\\n" "%s"\nexit %s\n' "$2" "$3" > "$tree/tests/$1.sh"
  chmod +x "$tree/tests/$1.sh"
}
run() {
  status=0
  GITHUB_STEP_SUMMARY="$tree/summary.md" "$tree/tests/run-all.sh" > "$tree/output.log" 2>&1 || status=$?
}
new_tree mixed
stub a-pass 'a ran' 0
stub b-skip 'skipped: required tool missing' 77
stub c-fail 'skipped: one subcheck; another failed' 9
stub d-pass 'd ran' 0
run
check test "$status" -eq 1
check grep -qF '2 of 4 rehearsals passed' "$tree/output.log"
check grep -qF '1 skipped, 1 failed' "$tree/output.log"
check grep -qF 'd ran' "$tree/output.log"
check grep -qF 'skipped: `b-skip`' "$tree/summary.md"
check grep -qF 'failed: `c-fail`' "$tree/summary.md"
check test "$(grep -c 'passed: b-skip' "$tree/output.log" || true)" -eq 0
new_tree skipped
stub a-skip 'skipped: required tool missing' 77
stub b-pass 'b ran' 0
run
check test "$status" -eq 1
check grep -qF '1 of 2 rehearsals passed' "$tree/output.log"
check grep -qF '1 skipped, 0 failed' "$tree/output.log"
check test "$(grep -c 'Every rehearsal passed' "$tree/output.log" || true)" -eq 0
new_tree legacy
stub a-skip 'skipped: required tool missing' 0
run
check test "$status" -eq 1
check grep -qF '0 of 1 rehearsals passed' "$tree/output.log"
new_tree optional
stub a-validator '  skipped: optional validator unavailable' 0
run
check test "$status" -eq 0
check grep -qF '1 of 1 rehearsals passed' "$tree/output.log"
check grep -qF '0 skipped, 0 failed' "$tree/output.log"
check grep -qF 'optional validator unavailable' "$tree/output.log"
check grep -qF 'optional validator unavailable' "$tree/summary.md"
new_tree empty
run
check test "$status" -eq 1
check test "$(grep -c 'Every rehearsal passed' "$tree/output.log" || true)" -eq 0
# Remove pytest from a fixture, then drive each actual rehearsal through the runner.
# No session starts: the missing-tool check must terminate first.
for rehearsal in ready-gate judge-runner trim review-loop; do
  new_tree "missing-$rehearsal"
  mkdir -p "$tree/bin" "$tree/tests/lib"
  cp "$ROOT/tests/$rehearsal.sh" "$tree/tests/$rehearsal.sh"
  : > "$tree/tests/lib/throwaway-project.sh"
  printf '#!/bin/sh\nexit 1\n' > "$tree/bin/python3"
  chmod +x "$tree/bin/python3"
  code=0
  PATH="$tree/bin:$PATH" "$tree/tests/$rehearsal.sh" > "$tree/direct.log" 2>&1 || code=$?
  check test "$code" -eq 77
  check grep -qF 'skipped: pytest is not installed' "$tree/direct.log"
  PATH="$tree/bin:$PATH" run
  check test "$status" -eq 1
  check grep -qF '0 of 1 rehearsals passed' "$tree/output.log"
  check grep -qF "skipped: \`$rehearsal\`" "$tree/summary.md"
done
[ "$failures" -eq 0 ] || exit 1
echo 'rehearsal-results.sh: all checks passed'
