#!/usr/bin/env sh
# lib.sh: shared helpers for the replay harness.
#
# The contract lives in .agents/tests/scenarios.md and nowhere else. Everything
# here reads that file rather than restating it, so a scenario edited there
# changes what the harness expects without a second file needing to agree.

# Locating the contract. A caller may set REPLAY_DIR itself. Otherwise this
# works out where it lives from the running script, and falls back to the
# repository root, so sourcing this file from another directory still finds
# scenarios.md rather than silently parsing nothing.
if [ -z "${REPLAY_DIR:-}" ]; then
  REPLAY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
  if [ ! -f "$REPLAY_DIR/lib.sh" ]; then
    _top=$(git rev-parse --show-toplevel 2>/dev/null || true)
    if [ -n "$_top" ] && [ -f "$_top/.agents/tests/replay/lib.sh" ]; then
      REPLAY_DIR="$_top/.agents/tests/replay"
    fi
  fi
fi
TESTS_DIR=$(CDPATH= cd -- "$REPLAY_DIR/.." && pwd)
# This file sits one level deeper than the rest of the suite, so the repository
# root is two levels above .agents/tests rather than one.
ROOT=$(CDPATH= cd -- "$TESTS_DIR/../.." && pwd)
SCENARIOS="$TESTS_DIR/scenarios.md"

[ -f "$SCENARIOS" ] || {
  echo "FAIL: cannot find the scenario contract; set REPLAY_DIR" >&2
  exit 1
}

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

note() {
  echo "NOTE: $1" >&2
}

# scenario_block <number>
# Print the lines of one scenario, heading included, without the trailing blank.
scenario_block() {
  awk -v want="$1" '
    /^## / {
      inside = 0
      heading = $0
      sub(/^## /, "", heading)
      number = heading
      sub(/\..*$/, "", number)
      if (number == want) inside = 1
    }
    inside { print }
  ' "$SCENARIOS"
}

# scenario_title <number>
scenario_title() {
  scenario_block "$1" | awk 'NR == 1 { sub(/^## [0-9]+\. /, ""); print; exit }'
}

# scenario_labels <number>
# Print the field labels this scenario actually carries, one per line. Scenarios
# 16 to 20 are written as bare statements rather than labelled fields, so this
# returns nothing for them and the caller decides what to do about it.
scenario_labels() {
  scenario_block "$1" | awk '
    /^- [A-Z][^:]*:/ {
      label = $0
      sub(/^- /, "", label)
      sub(/:.*$/, "", label)
      print label
    }
  '
}

# scenario_field <number> <label>
# Print one field, with any indented continuation lines folded in. Scenario 8's
# escalation runs to seven lines, so this cannot assume one line per field.
scenario_field() {
  scenario_block "$1" | awk -v want="$2" '
    /^- [A-Z][^:]*:/ {
      label = $0
      sub(/^- /, "", label)
      sub(/:.*$/, "", label)
      if (label == want) {
        collecting = 1
        value = $0
        sub(/^- [^:]*: */, "", value)
        next
      }
      if (collecting) { print value; collecting = 0; exit }
      collecting = 0
      next
    }
    collecting && /^  +[^ ]/ {
      line = $0
      sub(/^  +/, " ", line)
      value = value line
      next
    }
    collecting && /^$/ { print value; collecting = 0; exit }
    END { if (collecting) print value }
  '
}

# scenario_statements <number>
# For the bare-statement scenarios, print each bullet as its own line.
scenario_statements() {
  scenario_block "$1" | awk '/^- / { sub(/^- /, ""); print }'
}

# scenario_numbers
# Every scenario number in the contract, in file order.
scenario_numbers() {
  awk '/^## [0-9]+\./ { n = $2; sub(/\..*$/, "", n); print n }' "$SCENARIOS"
}

# expectations_json <number>
# The scenario as JSON, which is what the grader receives. Labelled scenarios
# become an object of fields; bare-statement ones become a list.
expectations_json() {
  number=$1
  title=$(scenario_title "$number")
  labels=$(scenario_labels "$number")

  printf '{\n'
  printf '  "scenario": %s,\n' "$number"
  printf '  "title": %s,\n' "$(json_string "$title")"

  if [ -z "$labels" ]; then
    printf '  "shape": "statements",\n'
    printf '  "statements": [\n'
    first=1
    scenario_statements "$number" | while IFS= read -r statement; do
      [ -n "$statement" ] || continue
      if [ "$first" -eq 1 ]; then first=0; else printf ',\n'; fi
      printf '    %s' "$(json_string "$statement")"
    done
    printf '\n  ]\n'
  else
    printf '  "shape": "fields",\n'
    printf '  "fields": {\n'
    first=1
    printf '%s\n' "$labels" | while IFS= read -r label; do
      [ -n "$label" ] || continue
      value=$(scenario_field "$number" "$label")
      if [ "$first" -eq 1 ]; then first=0; else printf ',\n'; fi
      printf '    %s: %s' "$(json_string "$label")" "$(json_string "$value")"
    done
    printf '\n  }\n'
  fi
  printf '}\n'
}

# json_string <text>
# Quote text as a JSON string. Kept here rather than reaching for a language
# runtime, so the harness runs wherever the rest of the suite does.
json_string() {
  printf '%s' "$1" | awk '
    BEGIN { RS = "\0"; printf "\"" }
    {
      gsub(/\\/, "\\\\")
      gsub(/"/, "\\\"")
      gsub(/\t/, "\\t")
      gsub(/\r/, "\\r")
      gsub(/\n/, "\\n")
      printf "%s", $0
    }
    END { printf "\"" }
  '
}
