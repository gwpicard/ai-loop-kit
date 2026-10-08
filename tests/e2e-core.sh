#!/usr/bin/env sh
# The core from founding to a person's merge, before and after the App.
# Only stand-ins run here. Scratch projects stay in place for inspection.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 -m pytest --version >/dev/null 2>&1 || {
  echo "FAIL: pytest is required; the core rehearsal did not run" >&2
  exit 1
}
exec python3 "$ROOT/tests/fixtures/e2e-core/rehearse.py" "$@"
