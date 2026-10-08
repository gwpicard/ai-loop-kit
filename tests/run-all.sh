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

# No bytecode folders, so a run leaves nothing for Git to see.
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1

# Exit 77 means a required rehearsal did not run. Older rehearsals use a
# top-level "skipped:" line with exit zero; keep those outside the pass total.
# Indented skip lines describe optional subchecks, never extra passes.
failed=""
skipped=""
failed_count=0
skipped_count=0
passed_count=0
total=0
WORK=$(mktemp -d) || exit 1
# Keep the output files as evidence, including on failure.
optional="$WORK/optional.log"
: > "$optional"

for script in tests/*.sh; do
  name=$(basename "$script" .sh)
  case "$name" in
    mutate | 'mutate '* | run-all | 'run-all '*) continue ;;
  esac

  total=$((total + 1))
  printf '\n=== %s ===\n' "$name"
  status=0
  "$script" > "$WORK/$name.log" 2>&1 || status=$?
  cat "$WORK/$name.log"
  # A real failure takes precedence over any skip marker in its output.
  if [ "$status" -ne 0 ] && [ "$status" -ne 77 ]; then
    printf '  FAILED: %s\n' "$name"
    failed="$failed $name"
    failed_count=$((failed_count + 1))
  elif [ "$status" -eq 77 ] || grep -q '^skipped:' "$WORK/$name.log"; then
    printf '  skipped: %s\n' "$name"
    skipped="$skipped $name"
    skipped_count=$((skipped_count + 1))
  else
    printf '  passed: %s\n' "$name"
    passed_count=$((passed_count + 1))
  fi
  if grep -q '^  *skipped:' "$WORK/$name.log"; then
    printf '%s:\n' "$name" >> "$optional"
    grep '^  *skipped:' "$WORK/$name.log" >> "$optional"
  fi
done

printf '\n===================================\n'
printf '%d of %d rehearsals passed\n' "$passed_count" "$total"
printf '%d skipped, %d failed\n' "$skipped_count" "$failed_count"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    printf '## Rehearsals\n\n'
    printf '%d of %d passed.\n\n' "$passed_count" "$total"
    printf '%d skipped, %d failed.\n\n' "$skipped_count" "$failed_count"
    for name in $skipped; do
      printf -- '- skipped: `%s`\n' "$name"
    done
    for name in $failed; do
      printf -- '- failed: `%s`\n' "$name"
    done
    if [ -s "$optional" ]; then
      printf '\nOptional checks omitted (outside the pass total):\n\n'
      cat "$optional"
    fi
  } >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$total" -eq 0 ]; then
  printf 'No rehearsals ran.\n'
  exit 1
fi

if [ "$skipped_count" -gt 0 ]; then
  printf '\nRequired rehearsals skipped:\n'
  for name in $skipped; do
    printf -- '  - %s\n' "$name"
  done
fi

if [ "$failed_count" -gt 0 ]; then
  printf '\nThese rehearsals failed:\n'
  for name in $failed; do
    printf -- '  - %s\n' "$name"
  done
  printf '\nRun one on its own to read its output: tests/<name>.sh\n'
  exit 1
fi

[ "$skipped_count" -eq 0 ] || exit 1
printf 'Every rehearsal passed.\n'
