#!/usr/bin/env sh
# check-parser.sh: prove the harness reads the scenario contract correctly.
#
# The replay harness treats .agents/tests/scenarios.md as the only source of
# expected behaviour. If the parser silently drops a field, every run downstream
# grades against an incomplete contract and still reports success. This runs
# over every scenario in the contract rather than the ones currently replayed,
# so extending the harness later does not surprise anyone.

set -eu

. "$(dirname -- "$0")/lib.sh"

[ -f "$SCENARIOS" ] || fail "scenario contract is missing at $SCENARIOS"

numbers=$(scenario_numbers)
[ -n "$numbers" ] || fail "no scenarios were found in the contract"

count=$(printf '%s\n' "$numbers" | wc -l | tr -d ' ')
echo "Scenarios found: $count"

# A replayed scenario must carry these fields, because the grader asks about
# every one of them by name. Risk notice and Acceptance are not here: they are
# the risk pair, checked separately below, because a scenario that is not about
# risk carries neither.
REQUIRED_LABELS="Visible explanation
Hidden technique
Evidence
Save route
Review
Escalation"

fielded=0
statements=0

for number in $numbers; do
  title=$(scenario_title "$number")
  [ -n "$title" ] || fail "scenario $number has no title"

  labels=$(scenario_labels "$number")
  if [ -z "$labels" ]; then
    statements=$((statements + 1))
    lines=$(scenario_statements "$number" | grep -c . || true)
    [ "$lines" -gt 0 ] || fail "scenario $number carries neither fields nor statements"
    echo "  $number  statements($lines)  $title"
    continue
  fi

  fielded=$((fielded + 1))
  labelcount=$(printf '%s\n' "$labels" | grep -c . || true)

  # Every labelled field must come back with exactly one folded value. The
  # one-line rule is what catches a parser that emits a field twice, which an
  # emptiness check happily accepts.
  printf '%s\n' "$labels" | while IFS= read -r label; do
    [ -n "$label" ] || continue
    value=$(scenario_field "$number" "$label")
    [ -n "$value" ] || fail "scenario $number field '$label' parsed as empty"
    lines=$(printf '%s\n' "$value" | wc -l | tr -d ' ')
    [ "$lines" -eq 1 ] || \
      fail "scenario $number field '$label' folded to $lines lines rather than one"
  done

  echo "  $number  fields($labelcount)  $title"
done

echo
echo "Labelled scenarios: $fielded"
echo "Statement scenarios: $statements"

# Every scenario with a case file carries the full shape. The list comes from
# the folder rather than from a line here, so adding a case cannot leave this
# check behind.
replayed=$(find "$(dirname -- "$0")/cases" -name '*.txt' -exec basename {} .txt \; \
  | sed 's/^0*//' | sort -n)
[ -n "$replayed" ] || fail "no case files were found"
echo
echo "Checking every replayed scenario carries every graded field:"
for number in $replayed; do
  labels=$(scenario_labels "$number")
  [ -n "$labels" ] || fail "replayed scenario $number is not in the labelled shape"
  printf '%s\n' "$REQUIRED_LABELS" | while IFS= read -r required; do
    [ -n "$required" ] || continue
    printf '%s\n' "$labels" | grep -qxF "$required" || \
      fail "replayed scenario $number is missing the '$required' field"
    value=$(scenario_field "$number" "$required")
    [ -n "$value" ] || fail "replayed scenario $number has an empty '$required'"
  done
  # Risk notice and Acceptance are the risk pair. A scenario about a risk carries
  # both, and scenario 31 carries them as "none is due" to say plainly that none
  # applies. A scenario that is not about risk at all, such as the /setup
  # interview scenarios, carries neither. Require them together, so a risk
  # scenario cannot quietly drop one, without forcing the pair onto a scenario it
  # does not belong to.
  if printf '%s\n' "$labels" | grep -qxF "Risk notice"; then has_risk=yes; else has_risk=no; fi
  if printf '%s\n' "$labels" | grep -qxF "Acceptance"; then has_acc=yes; else has_acc=no; fi
  if [ "$has_risk" != "$has_acc" ]; then
    fail "replayed scenario $number carries only one of the risk pair; it needs both Risk notice and Acceptance, or neither"
  fi
  if [ "$has_risk" = yes ]; then
    for paired in "Risk notice" "Acceptance"; do
      value=$(scenario_field "$number" "$paired")
      [ -n "$value" ] || fail "replayed scenario $number has an empty '$paired'"
    done
  fi

  # Each also names an expected path, route, result, or fallback.
  printf '%s\n' "$labels" | grep -q '^Expected ' || \
    fail "replayed scenario $number names no expected outcome"
  echo "  $number  complete"
done

# The two words for an empty field, and only those two. `none is due` claims the
# kit must not do the thing, and doing it anyway is marked against.
# `unaffected` says this scenario does not judge the field at all. They used to
# be written six ways between them, nothing said which meant what, and a grader
# marked an absent risk notice as nothing to see and an absent review as a
# failure in the same run, off the same construction. A third wording puts the
# grader back to guessing, so this refuses one.
echo
echo "Checking every empty field uses one of the two words:"
empties=0
badwording=$(grep -nE '^- [A-Za-z ]+: (none|nothing|unchanged|not applicable|n/a)\b' "$SCENARIOS" \
  | grep -vE ': none is due' || true)
if [ -n "$badwording" ]; then
  fail "a field is empty in a wording that is neither 'none is due' nor 'unaffected':
$badwording"
fi
empties=$(grep -cE '^- [A-Za-z ]+: (none is due|unaffected)\b' "$SCENARIOS" || true)
[ "$empties" -gt 0 ] || fail "no empty fields were found at all, so this check is reading the wrong file"
echo "  $empties empty fields, all 'none is due' or 'unaffected'"

# Multi-line fields fold correctly. Scenario 8's escalation runs to eight lines
# in the contract, so a parser that stops at the first newline loses most of it.
echo
escalation=$(scenario_field 8 Escalation)
case "$escalation" in
  *"three failed attempts"*"somebody else to own"*)
    echo "Multi-line field check: scenario 8 escalation folded whole"
    ;;
  *)
    fail "scenario 8 escalation did not fold its continuation lines: $escalation"
    ;;
esac

# The JSON handed to the grader parses.
echo
if command -v python3 >/dev/null 2>&1; then
  for number in $numbers; do
    expectations_json "$number" | python3 -c 'import json,sys; json.load(sys.stdin)' || \
      fail "scenario $number produced JSON the grader cannot read"
  done
  echo "Grader JSON check: all $count scenarios parse"
else
  note "python3 is unavailable; the grader JSON was not parsed"
fi

echo
echo "check-parser.sh: all checks passed"
