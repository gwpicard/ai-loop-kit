#!/usr/bin/env sh
# Runs every check: the kit's tests (in parallel, one process per test
# module), then the house rules.
set -u
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
python3 kit/tests/run.py || status=1
sh tests/house-rules.sh || status=1
if [ "$status" -eq 0 ]; then echo "All checks passed."; else echo "Some checks failed." >&2; fi
exit "$status"
