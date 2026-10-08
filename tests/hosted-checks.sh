#!/usr/bin/env sh
# Check the repository workflow before its full suite runs on GitHub.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import re
import sys

workflow = (Path(sys.argv[1]) / '.github/workflows/v1-checks.yml').read_text()
checks = {
    'pull requests trigger the full suite': r'(?m)^  pull_request:',
    'main pushes trigger the full suite': r'(?m)^  push:\n    branches: \[main\]',
    'manual dispatch remains available': r'(?m)^  workflow_dispatch:',
    'stand-ins run on macOS': r'runs-on: macos-',
    'suite has at least an hour': r'timeout-minutes: (?:60|90|120)',
    'required Python tools are installed': r'pip install.*pytest.*ruff.*mypy',
    'real Claude is excluded before rehearsing': r'if command -v claude',
    'the full suite runs': r'run: tests/run-all.sh',
    'Actions are pinned to exact commits': r'uses: actions/checkout@[a-f0-9]{40}',
    'repository permissions stay read-only': r'permissions:\n  contents: read',
}
failed = [name for name, pattern in checks.items() if not re.search(pattern, workflow)]
for name in failed:
    print('FAIL: CI0: ' + name)
if failed:
    raise SystemExit(1)
print('CI0: all workflow conditions passed')
PY
