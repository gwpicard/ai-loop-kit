#!/usr/bin/env sh
# grader-recovery.sh: prove the replay grader parser recovers a whole grading
# that lost only its final brace, and still refuses anything truncated earlier.
#
# The replay harness excludes a run whose grader output does not parse, which is
# correct: a half-graded run counted as a pass is the fault a strict parser
# exists to prevent. But twice a complete grading was thrown away because the
# grader ended its turn one closing brace short. Recovering that is a different
# thing from tolerating partial output, and this check enforces the difference
# rather than trusting it.

set -eu

REPLAY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/replay" && pwd)
PARSER="$REPLAY_DIR/grade-parse.py"
FIXTURES="$REPLAY_DIR/grader-fixtures"

command -v python3 >/dev/null 2>&1 || {
  echo "FAIL: python3 is needed to run the grader parser" >&2
  exit 1
}
[ -f "$PARSER" ] || { echo "FAIL: parser missing at $PARSER" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

pass=0

# field <file> <key>: read one top-level value from a result JSON, empty if absent.
field() {
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
v = d.get(sys.argv[2])
print("" if v is None else v)
' "$1" "$2"
}

grade() {
  # grade <fixture-basename> -> writes $WORK/out.json
  python3 "$PARSER" "$FIXTURES/$1" "$WORK/out.json" 24
}

check() {
  # check <description> <condition-result>
  if [ "$2" = "yes" ]; then
    echo "  ok: $1"
    pass=$((pass + 1))
  else
    echo "FAIL: $1" >&2
    exit 1
  fi
}

echo "Grader recovery checks:"

# A clean grading parses and is not marked recovered.
grade clean.raw
[ -n "$(field "$WORK/out.json" held_note)" ] && [ -z "$(field "$WORK/out.json" error)" ] \
  && [ -z "$(field "$WORK/out.json" recovered)" ] && r=yes || r=no
check "a whole grading is graded and not marked recovered" "$r"

# A grading missing only its final brace is recovered, graded, and says so.
grade missing-brace.raw
[ -z "$(field "$WORK/out.json" error)" ] \
  && [ "$(field "$WORK/out.json" held)" = "True" ] \
  && [ -n "$(field "$WORK/out.json" held_note)" ] \
  && [ -n "$(field "$WORK/out.json" recovered)" ] && r=yes || r=no
check "a grading one brace short is recovered and marked recovered" "$r"

# A grading truncated inside the verdicts is refused, whatever braces are added.
grade truncated-midway.raw
[ "$(field "$WORK/out.json" error)" = "grader output was not JSON" ] \
  && [ -z "$(field "$WORK/out.json" held_note)" ] && r=yes || r=no
check "a grading truncated in the middle is still refused" "$r"

# The mirror case: a whole grading with one stray closing brace after it. A
# scenario 49 grading was thrown away for exactly this.
grade extra-brace.raw
[ -z "$(field "$WORK/out.json" error)" ] \
  && [ -n "$(field "$WORK/out.json" held_note)" ] \
  && [ -n "$(field "$WORK/out.json" recovered)" ] && r=yes || r=no
check "a grading with one extra brace is recovered and marked recovered" "$r"

# Only braces come off. A grading followed by words is still refused, so this
# cannot grow into a parser that takes the first object it finds.
grade trailing-words.raw
[ "$(field "$WORK/out.json" error)" = "grader output was not JSON" ] && r=yes || r=no
check "a grading followed by other text is still refused" "$r"

# A grader's own error object is passed through unchanged, not recovered.
grade incomplete-transcript.raw
[ "$(field "$WORK/out.json" error)" = "transcript is incomplete" ] \
  && [ -z "$(field "$WORK/out.json" recovered)" ] && r=yes || r=no
check "a deliberate grader error object passes through unchanged" "$r"

echo
echo "grader-recovery.sh: all $pass checks passed"
