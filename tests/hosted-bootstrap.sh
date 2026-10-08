#!/usr/bin/env sh
# The hosted command must reach the actual scaffold branch through person preparation.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export ROOT PYTHONDONTWRITEBYTECODE
fail() { echo "FAIL: $1" >&2; exit 1; }
ok() { echo "  ok: $1"; }
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_PLUGIN_ROOT ANTHROPIC_API_KEY 2>/dev/null || true
. "$ROOT/tests/lib/throwaway-project.sh"
tp_new bootstrap-gate
KIT="$TP_BASE/plugin"
cp -R "$ROOT/kit" "$KIT"
PATH="$ROOT/tests/stand-ins/fake-computer:$PATH"
CLAUDE_PLUGIN_ROOT="$KIT"
export PATH CLAUDE_PLUGIN_ROOT
cd "$TP_ROOT"
python3 "$KIT/scripts/setup.py" found --language python --json > "$TP_BASE/found.json"

# These commands act as the person, solely against tp_new's local origin and GitHub stand-in.
prepare() {
  git checkout -q -b "$1"
  git add -A
  git commit -qm "$2"
  git push -q origin "$1"
  pr=$(gh pr create --base main --head "$1" --title "$2" --body 'Prepare the scaffold command.')
  gh pr merge "${pr##*/}" --merge --match-head-commit "$(git rev-parse HEAD)" >/dev/null
  git fetch -q origin main
  git checkout -q main
  git merge -q --ff-only origin/main
}
prepare founding 'Found the project'
# Keep a person's unsaved workflow edit, including its line endings.
python3 - <<'PY'
from pathlib import Path
p = Path('.github/workflows/checks.yml')
p.write_bytes(p.read_bytes().replace(b'\n', b'\r\n') + b'# Person edit\r\n')
PY
COMMAND='sh tests/run.sh'
first() {
  code=0
  python3 "$KIT/scripts/setup.py" first-piece --test-command "$COMMAND" --json "$@" \
    > "$TP_BASE/first.json" 2> "$TP_BASE/first.err" || code=$?
}
first
if [ "$code" != 3 ]; then
  python3 "$KIT/scripts/gate.py" branch 1 --json > "$TP_BASE/stale-branch.json"
  fail "F2-BRANCH actual gate created a stale scaffold branch after an unprepared capture"
fi
[ ! -d .agents/pieces ] || fail "F2-PREP refusal captured a piece"
grep -q 'person.*pull request' "$TP_BASE/first.err" || fail "F2-PREP no person preparation next step"
first
[ "$code" = 3 ] || fail "F2-REPEAT local command alignment must not bypass committed main"
before=$(shasum .github/workflows/checks.yml)
first --dry-run
[ "$code" = 3 ] || fail "F2-DRY a stale base remains a refusal in dry-run"
[ "$(shasum .github/workflows/checks.yml)" = "$before" ] || fail "F2-DRY changed the workflow"
python3 - <<'PY'
from pathlib import Path
p = Path('.github/workflows/checks.yml').read_bytes()
assert p.endswith(b'# Person edit\r\n'), 'F2-PRESERVE'
assert b'\n' not in p.replace(b'\r\n', b''), 'F2-CRLF'
PY
ok 'F2-PREP repeated refusal and dry-run preserve the person edits'

# An already captured piece must not evade the check at actual branch creation.
sed 's#{{TEST_COMMAND}}#sh tests/run.sh#' "$KIT/templates/first-piece.md" > "$TP_BASE/spec.md"
python3 "$KIT/scripts/gate.py" capture --title Scaffold --body-file "$TP_BASE/spec.md" --json \
  > "$TP_BASE/captured.json"
branch() {
  code=0
  python3 "$KIT/scripts/gate.py" branch 1 --json "$@" \
    > "$TP_BASE/branch.json" 2> "$TP_BASE/branch.err" || code=$?
}
branch
[ "$code" = 3 ] || fail 'F2-BRANCH actual gate must refuse the stale committed workflow'
! git show-ref --verify --quiet refs/heads/piece-1 || fail 'F2-BRANCH created a stale branch'
branch --dry-run
[ "$code" = 3 ] || fail 'F2-BRANCH dry-run must report the same refusal'
prepare bootstrap-preparation 'Prepare the selected scaffold command'
first
[ "$code" = 0 ] || fail "F2-PREP person preparation did not allow the existing capture"
branch
[ "$code" = 0 ] || fail "F2-BRANCH a prepared committed main was refused"
selected=$(git show piece-1:.github/workflows/checks.yml | python3 -c '
import json,sys
line = next(l for l in sys.stdin if l.startswith("          SCAFFOLD_TEST_COMMAND: "))
print(json.loads(line.split(":",1)[1]))')
[ "$selected" = "$COMMAND" ] || fail 'F2-BRANCH the actual branch inherited another command'
# A branch predating preparation cannot escape by losing the generated entry.
git checkout -q piece-1
cp .github/workflows/checks.yml "$TP_BASE/prepared-workflow.yml"
python3 - <<'CHECK'
from pathlib import Path
p=Path('.github/workflows/checks.yml')
p.write_bytes(b''.join(line for line in p.read_bytes().splitlines(keepends=True)
                      if not line.startswith(b'          SCAFFOLD_TEST_COMMAND: ')))
CHECK
git add .github/workflows/checks.yml
git commit -qm 'Preserve the historical unprepared branch case'
branch
[ "$code" = 3 ] || fail 'F2-EXISTING a branch without the prepared marker escaped the gate'
cp "$TP_BASE/prepared-workflow.yml" .github/workflows/checks.yml
git add .github/workflows/checks.yml
git commit -qm 'The person prepares the existing branch'
branch
[ "$code" = 0 ] || fail 'F2-EXISTING the prepared existing branch was refused'
ok 'F2-EXISTING a missing branch marker refuses and person preparation repairs it'
base=$(git rev-parse main)
git checkout -q piece-1
mkdir tests
printf 'echo F2-RUNNER failing selected runner >&2\nexit 9\n' > tests/run.sh
git add tests/run.sh
git commit -qm 'The scaffold runner'
code=0
python3 "$KIT/scripts/hosted-check.py" --base "$base" --scaffold-command "$selected" \
  > "$TP_BASE/hosted.log" 2>&1 || code=$?
[ "$code" = 9 ] || fail 'F2-RUNNER hosted check did not run the failing selected command'
ok 'F2-BRANCH actual committed scaffold branch runs the selected judge'

# A new selected command on main must not silently reuse an older captured branch.
git checkout -q main
python3 - <<'PY'
from pathlib import Path
p=Path('.github/workflows/checks.yml')
s=p.read_bytes().replace(b'"sh tests/run.sh"', b'"sh tests/new.sh"')
p.write_bytes(s)
PY
prepare changed-base 'Change the foundation command'
branch
[ "$code" = 3 ] || fail 'F2-MAIN changed main must refuse the old selected command'
# The old branch remains available for inspection.
git show-ref --verify --quiet refs/heads/piece-1 || fail 'F2-KEEP removed the old branch'
ok 'F2-MAIN changed main refuses the stale captured piece and preserves its branch'

# Also check a new capture after preparation, without relying on the existing-piece path.
tp_new prepared-capture
CLAUDE_PLUGIN_ROOT="$KIT"
export CLAUDE_PLUGIN_ROOT
cd "$TP_ROOT"
python3 "$KIT/scripts/setup.py" found --language python --test-command "$COMMAND" --json \
  > "$TP_BASE/found.json"
first
[ "$code" = 3 ] || fail 'F2-FOUND an uncommitted foundation must be prepared first'
prepare prepared-foundation 'Prepare the chosen foundation command'
first
[ "$code" = 0 ] || fail 'F2-CAPTURE a prepared selected command was refused'
branch
[ "$code" = 0 ] || fail 'F2-CAPTURE gate did not create the prepared scaffold branch'
ok 'F2-CAPTURE person-prepared foundation allows capture and the real branch'

echo 'Hosted bootstrap checks passed.'
