#!/usr/bin/env sh
# spec-lint.sh: put three issues into the GitHub stand-in and run
# `spec.py lint` and `spec.py needs --json` on each.
#
#   1. a finished spec: the lint passes and the needs list is empty;
#   2. the design's example issue: the lint passes and one need names the person;
#   3. a chore with a refused phrase, a vague word and too many lines: the lint
#      fails with exit code 1 and a next: line, and the needs list holds lint gaps.
#
# No network, no GitHub account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT
. "$ROOT/tests/lib/throwaway-project.sh"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

SPEC="$ROOT/kit/scripts/spec.py"
FIX="$ROOT/tests/fixtures/specs"

tp_new demo
tp_app
cd "$TP_ROOT"

url1=$(tp_issue "Rename a report" "$(cat "$FIX/ready.md")")
url2=$(tp_issue "Export a month's invoices" "$(cat "$FIX/example-issue.md")")
# A chore, with a refused phrase, a vague word and more than 80 lines.
python3 - "$FIX/ready.md" > "$TP_BASE/broken.md" <<'PY'
import sys
b = open(sys.argv[1], encoding="utf-8").read()
b = b.replace("Names have at most 80 characters.", "Names have at most 80 characters, TBD.")
b = b.replace("The report list shows the new name at once.",
              "The report list shows the new name and is fast.")
b = b.replace("Bulk rename.", "Bulk rename." + "\n- more" * 90)
sys.stdout.write(b)
PY
url3=$(gh issue create --title "Rename chore" --label "type:chore" --body-file "$TP_BASE/broken.md")
n1=${url1##*/}
n2=${url2##*/}
n3=${url3##*/}

check() {
  # check <label> <file> <python expression over d>
  python3 - "$2" "$3" <<'PY' && pass "$1" || fail "$1"
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)
PY
}

run() {
  # run <name> <command...>: save stdout and stderr, and the exit code.
  name=$1
  shift
  code=0
  "$@" >"$TP_BASE/$name.json" 2>"$TP_BASE/$name.err" || code=$?
  eval "code_$name=$code"
}

# --- 1. the finished spec ---------------------------------------------------
run lint1 "$SPEC" lint "$n1" --json
[ "$code_lint1" = 0 ] && pass "lint passes on the finished spec" || fail "lint exited $code_lint1 on the finished spec"
check "the lint result says passed with no gap" "$TP_BASE/lint1.json" 'd["ok"] is True and d["gaps"] == []'
run needs1 "$SPEC" needs "$n1" --json
check "the needs list is empty" "$TP_BASE/needs1.json" 'd["needs"] == [] and d["needs_you"] is False and d["empty"] is True'

# --- 2. the design's example ------------------------------------------------
run lint2 "$SPEC" lint "$n2" --json
[ "$code_lint2" = 0 ] && pass "lint passes on the example issue" || fail "lint exited $code_lint2 on the example issue: $(cat "$TP_BASE/lint2.json")"
run needs2 "$SPEC" needs "$n2" --json
check "one need, the open question, names the person" "$TP_BASE/needs2.json" \
  'len(d["needs"]) == 1 and d["needs"][0]["kind"] == "open_question" and d["needs_you"] is True and d["empty"] is False'

# --- 3. the broken chore ----------------------------------------------------
run lint3 "$SPEC" lint "$n3" --json
[ "$code_lint3" = 1 ] && pass "lint exits 1 on the broken chore" || fail "lint exited $code_lint3 on the broken chore"
check "the gaps name the phrase, the word and the length" "$TP_BASE/lint3.json" \
  'd["ok"] is False and {"refused_phrase","vague_word","length"} <= {g["rule"] for g in d["gaps"]}'
grep -q '^next: ' "$TP_BASE/lint3.err" && pass "the failure has a next: line" || fail "no next: line on the lint failure"
run needs3 "$SPEC" needs "$n3" --json
check "the needs list holds the lint gaps and none for the person" "$TP_BASE/needs3.json" \
  'len([n for n in d["needs"] if n["kind"] == "lint_gap"]) >= 3 and d["needs_you"] is False'

# The type can also be given on the command line, and it changes the answer.
run lint3b "$SPEC" lint --file "$TP_BASE/broken.md" --type feature --json
check "as a feature the same body is not too long" "$TP_BASE/lint3b.json" \
  '"length" not in {g["rule"] for g in d["gaps"]}'

# Tests traced to the IDs: a test file that names three of the four IDs.
mkdir "$TP_BASE/acceptance"
cat > "$TP_BASE/acceptance/test_rename.py" <<'PY'
def test_flow():
    """FL-1 FL-2"""

def test_empty_name():
    """EC-1"""
PY
run lint4 "$SPEC" lint --file "$FIX/ready.md" --tests "$TP_BASE/acceptance" --json
[ "$code_lint4" = 1 ] && pass "lint exits 1 when a test is missing for an ID" || fail "lint exited $code_lint4 with a missing test"
check "the gap names EC-2" "$TP_BASE/lint4.json" \
  'any("EC-2" in g["message"] and g["rule"] == "id_trace" for g in d["gaps"])'

# --- the same answer from a file --------------------------------------------
run needs1f "$SPEC" needs --file "$FIX/ready.md" --json
check "the file route gives an empty list too" "$TP_BASE/needs1f.json" 'd["needs"] == []'

# --- refusals ---------------------------------------------------------------
run bad "$SPEC" lint "$n1" --type epic --json
[ "$code_bad" = 2 ] && pass "an unknown type exits 2" || fail "an unknown type exited $code_bad"
run none "$SPEC" lint 999 --json
[ "$code_none" != 0 ] && pass "a missing issue fails" || fail "a missing issue did not fail"
grep -q '^next: ' "$TP_BASE/none.err" && pass "the missing issue failure has a next: line" || fail "no next: line"

[ "$FAIL" = 0 ] || exit 1
echo "ok: spec-lint passed"
