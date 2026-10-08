#!/usr/bin/env sh
# Manual App smoke on a private test repository. This calls real Claude.
# Usage: AI_LOOP_KIT_REAL_SMOKE=1 tests/smoke/run-real.sh /path/to/test-project
# The project must have only README.md tracked, a clean working tree, a GitHub
# origin, and its test App already configured in .agents/loop/local.json.
# It must be a disposable test repository with no production services.
# The person reviews and merges each pull request on GitHub when prompted.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
[ "${AI_LOOP_KIT_REAL_SMOKE:-}" = 1 ] && [ -t 0 ] && [ -t 1 ] || {
  echo "Manual smoke needs AI_LOOP_KIT_REAL_SMOKE=1 and a terminal." >&2
  exit 3
}
[ "$#" -eq 1 ] || { echo "Usage: $0 /path/to/test-project" >&2; exit 2; }
python3 -m pytest --version >/dev/null
command -v claude >/dev/null
command -v gh >/dev/null
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$ROOT/tests/fixtures/e2e-core/rehearse.py" --case app --real "$1"
