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
(cd tests && python3 -m unittest discover -q -p 'test_*.py') || status=1
(PYTHONPATH=tests python3 -m unittest discover -s extras/tests -q -p 'test_*.py') || status=1
if [ "$status" -eq 0 ]; then echo "All checks passed."; else echo "Some checks failed." >&2; fi
exit "$status"
