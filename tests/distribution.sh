#!/usr/bin/env sh
# Offline release provenance checks. No Claude installation or public release.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tests/unit -p test_versions.py -v
printf 'distribution.sh passed\n'
