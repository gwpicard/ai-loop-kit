#!/usr/bin/env sh
# Runs every check: the house rules, then the kit's tests. Last run took about six minutes.
set -u
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
sh tests/house-rules.sh || status=1
sh tests/pull-request-base.sh || status=1
# The kit's own Python (kit/bin/kit-python), with pytest added for the tests that run it.
# RUN_ALL_PYTHON replaces it, so the runner's own test can record the calls.
if [ -n "${RUN_ALL_PYTHON:-}" ]; then
    python() { "$RUN_ALL_PYTHON" "$@"; }
else
    KIT_PY=$(kit/bin/kit-python -c 'import sys; print(sys.executable)') || exit 1
    python() { uv run --quiet --no-project --no-config --python "$KIT_PY" --with pytest python "$@"; }
fi
(cd tests && python -m unittest discover -q -p 'test_*.py') || status=1
(PYTHONPATH=tests python -m unittest discover -s extras/tests -q -p 'test_*.py') || status=1
if [ "$status" -eq 0 ]; then echo "All checks passed."; else echo "Some checks failed." >&2; fi
exit "$status"
