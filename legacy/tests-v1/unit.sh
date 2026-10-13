#!/usr/bin/env sh
# unit.sh: run every Python unit test under tests/unit/.
#
# One file runs alone with:
#   python3 -m unittest tests/unit/test_<name>.py
#
# A run that finds no test is a failure, because a check that did not run is
# never green.

set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1

PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$ROOT/kit/scripts"
export PYTHONDONTWRITEBYTECODE PYTHONPATH

out=$(mktemp)
if ! python3 -m unittest discover -v -s tests/unit -p 'test_*.py' >"$out" 2>&1; then
  cat "$out"
  echo "FAIL: a unit test failed. Run one file alone: python3 -m unittest tests/unit/test_<name>.py" >&2
  exit 1
fi
cat "$out"

if grep -q '^Ran 0 tests' "$out"; then
  echo "FAIL: no unit test ran, so nothing was checked. Add tests/unit/test_<name>.py." >&2
  exit 1
fi
echo "ok: the unit tests passed"
