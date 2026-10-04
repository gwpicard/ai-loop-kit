#!/usr/bin/env sh
# Runs every rehearsal in this folder, one after another, and reports each by
# name.
#
# A hosted job for each rehearsal names a failure on the checks list by itself,
# but a job is billed a whole minute however long it takes, and most of these
# finish in under ten seconds. Twenty five jobs cost twenty five minutes to do
# about three minutes of work. Running them here costs one job and still names
# every failure.
#
# A failing rehearsal does not stop the others. One failure must never hide
# another, so the run continues to the end and lists everything that broke.
# rehearsal-runner.sh is what proves that, since no validator can read it off
# this file the way it could read fail-fast: false off the workflow.
#
# mutate.sh audits the suite rather than passing or failing, so it is not a
# rehearsal and is not run here.
#
# Both exclusions match the leading name rather than the whole one, because a
# copy is not called run-all. A sync daemon watching this folder writes copies
# as "<name> 2.sh" and "<name> copy.sh", and a copy of this file that is not
# excluded gets run as though it were a rehearsal. It then runs the whole suite
# again and reaches its own copy again, so the run never finishes and never
# reports. A hosted job does not fail when that happens, it hangs, and it is
# billed for every minute until something cuts it off.

set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT" || exit 1

failed=""
failed_count=0
total=0

for script in .agents/tests/*.sh; do
  name=$(basename "$script" .sh)
  case "$name" in
    mutate | 'mutate '* | run-all | 'run-all '*) continue ;;
  esac

  total=$((total + 1))
  printf '\n=== %s ===\n' "$name"
  if "$script"; then
    printf '  passed: %s\n' "$name"
  else
    printf '  FAILED: %s\n' "$name"
    failed="$failed $name"
    failed_count=$((failed_count + 1))
  fi
done

passed_count=$((total - failed_count))

printf '\n===================================\n'
printf '%d of %d rehearsals passed\n' "$passed_count" "$total"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    printf '## Rehearsals\n\n'
    printf '%d of %d passed.\n\n' "$passed_count" "$total"
    for name in $failed; do
      printf -- '- failed: `%s`\n' "$name"
    done
  } >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$failed_count" -gt 0 ]; then
  printf '\nThese rehearsals failed:\n'
  for name in $failed; do
    printf -- '  - %s\n' "$name"
  done
  printf '\nRun one on its own to read its output: .agents/tests/<name>.sh\n'
  exit 1
fi

printf 'Every rehearsal passed.\n'
