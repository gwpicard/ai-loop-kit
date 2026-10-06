#!/usr/bin/env sh
# judge-runner.sh: run a judge in a temporary checkout of main, end to end.
#
# It builds a throwaway Python project with a failing acceptance test and runs
# `loop.judge` on main. It checks the result (failed on an assertion naming
# FL-1), the time limit, and the evidence entry. It then stores two held-out
# cases through `loop.heldout`, checks that nothing landed in git, and checks
# their fingerprint. The held-out folder is inside the throwaway data folder,
# never the real one. No network, no model.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$ROOT/kit/scripts"
export PYTHONDONTWRITEBYTECODE PYTHONPATH ROOT
. "$ROOT/tests/lib/throwaway-project.sh"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

if ! python3 -m pytest --version >/dev/null 2>&1; then
  echo "skipped: pytest is not installed, so the judge-runner check did not run"
  exit 0
fi

tp_new demo
cd "$TP_ROOT"
mkdir tests
cat > menu.py <<'PY'
def opens():
    return False
PY
cat > tests/test_menu.py <<'PY'
from menu import opens


def test_menu_opens():
    assert opens() is True, "FL-1 the user opens the menu"
PY
cat > slow.sh <<'SH'
sleep 30
SH
git add menu.py tests slow.sh
git commit -q -m "Add a failing acceptance test"
git push -q origin main

OUT="$TP_BASE/judge.json"
set +e
python3 -m loop.judge run --json --command "python3 -m pytest tests/test_menu.py" \
  --ref main --time-limit 60 > "$OUT" 2> "$TP_BASE/judge.err"
code=$?
set -e

[ "$code" -eq 1 ] && pass "a failing judge exits 1" || fail "expected exit 1, got $code"
python3 - "$OUT" <<'PY' && pass "failed on an assertion naming FL-1" || fail "the result is wrong: $(cat "$OUT")"
import json, sys
r = json.load(open(sys.argv[1]))
assert r["outcome"] == "failed", r
assert r["runner"] == "pytest", r
assert r["failing_ids"] == ["FL-1"], r
assert r["failures"][0]["assertion"] is True, r
PY

# The temporary checkout is gone and the project folder holds nothing new.
[ "$(git worktree list | wc -l | tr -d ' ')" = "1" ] && pass "the temporary checkout was removed" \
  || fail "a worktree was left behind"
[ -z "$(git status --porcelain)" ] && pass "the project folder is clean after the run" \
  || fail "the run changed the project folder: $(git status --porcelain)"

# The time limit.
set +e
python3 -m loop.judge run --json --command "sh slow.sh" --ref main --time-limit 1 \
  > "$TP_BASE/slow.json" 2> /dev/null
code=$?
set -e
[ "$code" -eq 4 ] && pass "a check past its limit exits 4" || fail "expected exit 4, got $code"
grep -q '"outcome": "timeout"' "$TP_BASE/slow.json" && pass "the timeout is reported" \
  || fail "no timeout in $(cat "$TP_BASE/slow.json")"

# Evidence: the gate's side. The judge result becomes one chained entry.
python3 - "$OUT" "$TP_ROOT" <<'PY'
import json, sys
from pathlib import Path
from loop import evidence, judge
from loop.paths import Paths
result = json.load(open(sys.argv[1]))
paths = Paths.for_project(Path(sys.argv[2]))
evidence.append(paths, 7, [judge.evidence_entry(result, fingerprint="f" * 64)])
PY
EVFILE="$TP_ROOT/.agents/pieces/7/evidence.jsonl"
[ -f "$EVFILE" ] && pass "the evidence entry is written under .agents/pieces/7/" \
  || fail "no evidence file"
grep -q '"outcome": "failed"' "$EVFILE" && grep -q '"mac"' "$EVFILE" \
  && pass "the entry holds the outcome and a mac" || fail "the entry is wrong"
python3 -m loop.evidence show --json --piece 7 > "$TP_BASE/ev.json" \
  && pass "the chain reads back" || fail "the chain did not read back"
sed 's/"outcome": "failed"/"outcome": "passed"/' "$EVFILE" > "$TP_BASE/edited.jsonl"
cp "$TP_BASE/edited.jsonl" "$EVFILE"
set +e
python3 -m loop.evidence show --json --piece 7 > /dev/null 2> "$TP_BASE/ev.err"
code=$?
set -e
[ "$code" -eq 3 ] && grep -q '^next:' "$TP_BASE/ev.err" \
  && pass "an edited entry is refused with a next: line" \
  || fail "the edited entry was not refused (exit $code)"

# Held-out cases.
printf 'the menu stays shut when the user is signed out\n' > "$TP_BASE/h1.txt"
printf 'the menu closes after one hour\n' > "$TP_BASE/h2.txt"
python3 -m loop.heldout store --json --piece 7 \
  --case "H-1=$TP_BASE/h1.txt" --case "H-2=$TP_BASE/h2.txt" > "$TP_BASE/ho.json"
FP=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' "$TP_BASE/ho.json")
[ "${#FP}" -eq 64 ] && pass "two held-out cases are stored, with a fingerprint" \
  || fail "no fingerprint: $(cat "$TP_BASE/ho.json")"
[ "$(python3 -m loop.heldout fingerprint --json --piece 7 \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["fingerprint"])')" = "$FP" ] \
  && pass "the fingerprint reads back the same" || fail "the fingerprint changed"
grep -q "very" "$TP_BASE/ho.json" && fail "the result holds case content"
[ -d "$TP_DATA" ] && find "$TP_DATA" -path '*held-out*' -type f | grep -q . \
  && pass "the cases sit in the data folder, outside the project" || fail "cases not in $TP_DATA"
if git status --porcelain --ignored | grep -qi held; then
  fail "a held-out file is in the project folder"
else
  pass "nothing landed in the project folder"
fi
git log --all --name-only --format= | grep -qi held && fail "a held-out file reached git" \
  || pass "nothing landed in git"
case "$TP_DATA" in
  "$TP_ROOT"*) fail "the data folder is inside the project" ;;
  *) pass "the data folder is outside the project" ;;
esac

[ "$FAIL" -eq 0 ] || exit 1
echo "judge-runner: all checks passed"
