#!/usr/bin/env sh
# spec-parse.sh: put the design's example issue into the GitHub stand-in and
# read it back through `kit/scripts/spec.py show --json`.
#
# Also checks that an issue with an unknown spec version is refused with a
# `next:` line and exit code 3, and that a missing issue fails plainly.
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

url=$(tp_issue "Export a month's invoices as one CSV file" "$(cat "$FIX/example-issue.md")")
number=${url##*/}

out=$("$SPEC" show "$number" --json) || fail "show failed on the example issue"
printf '%s\n' "$out" > "$TP_BASE/show.json"

check() {
  # check <label> <python expression over d>
  python3 - "$TP_BASE/show.json" "$2" <<'PY' && pass "$1" || fail "$1"
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)
PY
}

check "the result says ok" 'd["ok"] is True'
check "the version is 1" 'd["version"] == 1'
check "the path is full" 'd["path"] == "full"'
check "the IDs are read back" 'd["ids"] == ["FL-1","FL-2","FL-3","EC-1","EC-2"]'
check "the judge command is read back" 'd["judge"]["command"].startswith("npm test")'
check "nothing required is missing" 'd["missing"] == []'
check "the open question is read back" 'len(d["open_questions"]) == 1'

# The same answer from the file route and the issue route.
"$SPEC" show --file "$FIX/example-issue.md" --json > "$TP_BASE/file.json"
python3 - "$TP_BASE/show.json" "$TP_BASE/file.json" <<'PY' && pass "issue and file give the same answer" || fail "issue and file differ"
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
for d in (a, b):
    d.pop("source", None)
sys.exit(0 if a == b else 1)
PY

# Unknown version: refused (exit 3) with a next: line.
url2=$(tp_issue "Later format" "$(cat "$FIX/unknown-version.md")")
code=0
"$SPEC" show "${url2##*/}" --json >"$TP_BASE/bad.out" 2>"$TP_BASE/bad.err" || code=$?
[ "$code" = 3 ] && pass "an unknown version exits 3" || fail "unknown version exited $code, not 3"
grep -q '^next: ' "$TP_BASE/bad.err" && pass "the refusal has a next: line" || fail "no next: line"

# A missing issue fails and names the next command.
code=0
"$SPEC" show 999 --json >/dev/null 2>"$TP_BASE/gone.err" || code=$?
[ "$code" != 0 ] && pass "a missing issue fails" || fail "a missing issue did not fail"
grep -q '^next: ' "$TP_BASE/gone.err" && pass "the failure has a next: line" || fail "no next: line for a missing issue"

# With no App, spec.py reads the gate's own record and never the person's
# sign-in. A piece the gate does not hold stops with a next: line.
tp_new demo-no-app
unset FAKE_APP_KEY
cd "$TP_ROOT"
python3 "$ROOT/kit/scripts/gate.py" capture --title "Export invoices" \
  --body-file "$FIX/example-issue.md" --json > /dev/null || fail "capture with no App failed"
: > "$FAKE_GH_LOG"
"$SPEC" show 1 --json > "$TP_BASE/show.json" || fail "show with no App failed on a captured piece"
check "with no App, show reads the gate's record" 'd["ok"] is True and len(d["open_questions"]) == 1'
code=0
"$SPEC" show 7 --json >/dev/null 2>"$TP_BASE/no-app.err" || code=$?
[ "$code" = 3 ] && pass "with no App, a piece the gate does not hold is refused" \
  || fail "with no App, show 7 exited $code, not 3"
grep -q '^next: .*--file' "$TP_BASE/no-app.err" && pass "the refusal names spec.py show --file" \
  || fail "no next: line naming --file: $(cat "$TP_BASE/no-app.err")"
grep -q '^CALL' "$FAKE_GH_LOG" && fail "spec.py started gh with no App: $(cat "$FAKE_GH_LOG")" \
  || pass "with no App, spec.py starts no gh"

[ "$FAIL" = 0 ] || exit 1
echo "ok: spec-parse passed"
