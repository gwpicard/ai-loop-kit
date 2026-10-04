#!/usr/bin/env sh
# check-floor-rehearsal.sh: found a throwaway project, wire its check the way
# check-floor.md says, and watch the check go red on a type error and green
# once the error is fixed.
#
# The commands come out of the shipped reference's table rather than being
# written here, so a table that named a command that does not work fails this
# rehearsal. The check starts from the shipped workflow template, and each
# step's command is run locally in order, which is what the hosted check does.
#
# The broken function has no test. That is the point of the floor: the tests
# pass, and the type check is what turns the tick red.
#
# Python is the language rehearsed because its two tools install as small
# packages. They are used from PATH when present and otherwise installed into a
# throwaway environment. A machine that can do neither fails here rather than
# skipping, since a rehearsal that passes by never running proves nothing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
FLOOR="$ROOT/.agents/skills/setup-ai-build-kit/references/check-floor.md"
TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml"
SENSITIVE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/check-sensitive-areas.sh"
# Founding writes AGENTS.md from this, and the check counts its lines.
INSTRUCTIONS="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
# Founding copies the gate script into every project, and a script the kit puts
# there must never turn the project's own check red. Each founded project below
# carries it where founding places it.
GATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/gate.py"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -f "$GATE" ] || fail "the setup skill carries no gate script at templates/foundation/gate.py"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PROJECT="$WORK/project"
mkdir -p "$PROJECT/.github/workflows" "$PROJECT/.agents/hooks"

# --- the commands, read from the shipped table ------------------------------

row=$(grep '^| Python |' "$FLOOR") || fail "check-floor.md has no Python row"
type_check=$(printf '%s\n' "$row" | awk -F'|' '{print $3}' | sed -n 's/.*`\([^`]*\)`.*/\1/p')
lint=$(printf '%s\n' "$row" | awk -F'|' '{print $4}' | sed -n 's/.*`\([^`]*\)`.*/\1/p')
[ -n "$type_check" ] || fail "the Python row names no type check command"
[ -n "$lint" ] || fail "the Python row names no lint command"
echo "  type check: $type_check"
echo "  lint: $lint"

# --- the tools --------------------------------------------------------------

if ! command -v mypy >/dev/null 2>&1 || ! command -v ruff >/dev/null 2>&1; then
  echo "  mypy or ruff not on PATH, installing both into a throwaway environment"
  python3 -m venv "$WORK/venv" ||
    fail "could not make a Python environment, so the check could not be rehearsed"
  "$WORK/venv/bin/pip" install --quiet mypy ruff ||
    fail "could not install mypy and ruff, so the check could not be rehearsed"
  PATH="$WORK/venv/bin:$PATH"
  export PATH
fi

# --- founding: the project and its wired check ------------------------------

cp "$SENSITIVE" "$PROJECT/.agents/hooks/check-sensitive-areas.sh"
cp "$INSTRUCTIONS" "$PROJECT/AGENTS.md"
mkdir -p "$PROJECT/.agents/tools"
cp "$GATE" "$PROJECT/.agents/tools/gate.py"

# The edit founding makes: the placeholder step goes, and install, type check,
# lint and test go in its place, each as its own named step.
awk -v tc="$type_check" -v li="$lint" '
  /- name: Install and test/ { skipping = 1 }
  skipping { next }
  { print }
  END {
    print "      - name: Install"
    print "        run: python3 -m pip install mypy ruff"
    print "      - name: Type check"
    print "        run: " tc
    print "      - name: Lint"
    print "        run: " li
    print "      - name: Test"
    print "        run: python3 -m unittest"
  }
' "$TEMPLATE" > "$PROJECT/.github/workflows/checks.yml"

grep -q 'placeholder' "$PROJECT/.github/workflows/checks.yml" &&
  fail "the placeholder step survived the edit"

cat > "$PROJECT/pricing.py" <<'PY'
def total(price: int, count: int) -> int:
    return price * count
PY

cat > "$PROJECT/test_pricing.py" <<'PY'
import unittest

from pricing import total


class TotalTest(unittest.TestCase):
    def test_total(self) -> None:
        self.assertEqual(total(2, 3), 6)


if __name__ == "__main__":
    unittest.main()
PY

# --- running the check the way the hosted runner would ----------------------

# Prints the name of the first step that failed, or nothing when all passed.
# The Install step is left to the rehearsal, which already provided the tools.
run_check() {
  awk '
    /^ *- name: / { sub(/^ *- name: /, ""); name = $0; next }
    /^ *run: /    { sub(/^ *run: /, ""); print name "\t" $0 }
  ' "$PROJECT/.github/workflows/checks.yml" > "$WORK/steps"
  tab=$(printf '\t')
  while IFS="$tab" read -r step command; do
    [ "$step" = "Install" ] && continue
    if ! (cd "$PROJECT" && sh -c "$command") > "$WORK/last-output" 2>&1; then
      printf '%s\n' "$step"
      return 0
    fi
  done < "$WORK/steps"
}

started=$(date +%s)
first=$(run_check)
finished=$(date +%s)
[ -z "$first" ] || { cat "$WORK/last-output" >&2; fail "the new project's check was red on day one, at $first"; }
echo "  ok: the founded project's check is green on day one ($((finished - started))s), with the gate script in place"

# Green with the gate script proves nothing unless the check reads it. The
# linter does: an unused import added to the placed copy turns Lint red.
cp "$PROJECT/.agents/tools/gate.py" "$WORK/gate.kept"
printf '\nimport os\n' >> "$PROJECT/.agents/tools/gate.py"
first=$(run_check)
[ "$first" = "Lint" ] || fail "the linter did not read the placed gate script, got '${first:-nothing}'"
grep -q 'gate.py' "$WORK/last-output" || fail "the lint failure did not name gate.py"
mv "$WORK/gate.kept" "$PROJECT/.agents/tools/gate.py"
echo "  ok: the linter reads the placed gate script, so its green counts"

# mypy leaves folders whose names start with a dot out of "mypy .", so the
# type check is also run on the gate script by name, the way a project that
# points its type check there would.
(cd "$PROJECT" && mypy .agents/tools/gate.py) > "$WORK/last-output" 2>&1 ||
  { cat "$WORK/last-output" >&2; fail "the type check fails when pointed at the gate script"; }
echo "  ok: the type check passes on the gate script by name"

# A type error in code no test reaches.
cat >> "$PROJECT/pricing.py" <<'PY'


def describe(count: int) -> str:
    return count
PY

(cd "$PROJECT" && python3 -m unittest) > "$WORK/tests-only" 2>&1 ||
  fail "the tests should still pass with the type error in place"
echo "  ok: the tests alone still pass with the type error in place"

first=$(run_check)
[ "$first" = "Type check" ] || fail "expected the Type check step to go red, got '${first:-nothing}'"
grep -q 'pricing.py' "$WORK/last-output" || fail "the type check did not name the file"
echo "  ok: the check goes red at Type check, naming pricing.py"

# The fix.
sed 's/    return count/    return str(count)/' "$PROJECT/pricing.py" > "$WORK/fixed"
mv "$WORK/fixed" "$PROJECT/pricing.py"
first=$(run_check)
[ -z "$first" ] || { cat "$WORK/last-output" >&2; fail "the check stayed red after the fix, at $first"; }
echo "  ok: the check goes green once the type error is fixed"

# An unused import is the linter's to catch, with the type check still green.
printf 'import os\n%s\n' "$(cat "$PROJECT/pricing.py")" > "$WORK/linted"
mv "$WORK/linted" "$PROJECT/pricing.py"
first=$(run_check)
[ "$first" = "Lint" ] || fail "expected the Lint step to go red, got '${first:-nothing}'"
echo "  ok: the check goes red at Lint on an unused import"

# --- the same again for TypeScript -------------------------------------------
#
# The web app recipes build with Next.js in TypeScript, so the TypeScript row is
# rehearsed the same way. This founds a small TypeScript project from the same
# template and takes its commands from the table. It does not run the Next.js
# starter: that would download the whole framework, and a project the starter
# made would use the starter's own lint settings, which the reference says to
# keep as they stand. The table's row is what founding writes when there are
# none, so that is the half worth watching go red.
#
# The tools install into the throwaway project, as a founded project's own
# dependencies. The tests run through tsx, which strips the types without
# checking them, so as with Python the tests pass and the type check is what
# turns the tick red.

echo
echo "TypeScript:"
command -v npm >/dev/null 2>&1 || fail "npm is needed to rehearse the TypeScript row"

row=$(grep '^| TypeScript |' "$FLOOR") || fail "check-floor.md has no TypeScript row"
type_check=$(printf '%s\n' "$row" | awk -F'|' '{print $3}' | sed -n 's/^[^`]*`\([^`]*\)`.*/\1/p')
lint=$(printf '%s\n' "$row" | awk -F'|' '{print $4}' | sed -n 's/^[^`]*`\([^`]*\)`.*/\1/p')
[ -n "$type_check" ] || fail "the TypeScript row names no type check command"
[ -n "$lint" ] || fail "the TypeScript row names no lint command"
printf '%s\n' "$row" | grep -q "ESLint's own recommended rules and typescript-eslint's recommended rules" ||
  fail "the TypeScript row no longer says which lint rules it starts from"
echo "  type check: $type_check"
echo "  lint: $lint"

PROJECT="$WORK/ts-project"
mkdir -p "$PROJECT/.github/workflows" "$PROJECT/.agents/hooks" "$PROJECT/src"
cp "$SENSITIVE" "$PROJECT/.agents/hooks/check-sensitive-areas.sh"
cp "$INSTRUCTIONS" "$PROJECT/AGENTS.md"
mkdir -p "$PROJECT/.agents/tools"
cp "$GATE" "$PROJECT/.agents/tools/gate.py"

awk -v tc="$type_check" -v li="$lint" '
  /- name: Install and test/ { skipping = 1 }
  skipping { next }
  { print }
  END {
    print "      - name: Install"
    print "        run: npm install"
    print "      - name: Type check"
    print "        run: " tc
    print "      - name: Lint"
    print "        run: " li
    print "      - name: Test"
    print "        run: npx tsx --test src/pricing.test.ts"
  }
' "$TEMPLATE" > "$PROJECT/.github/workflows/checks.yml"
grep -q 'placeholder' "$PROJECT/.github/workflows/checks.yml" &&
  fail "the placeholder step survived the edit"

cat > "$PROJECT/package.json" <<'JSON'
{
  "name": "rehearsal",
  "private": true,
  "type": "module",
  "devDependencies": {
    "@eslint/js": "^9",
    "@types/node": "^22",
    "eslint": "^9",
    "tsx": "^4",
    "typescript": "^5",
    "typescript-eslint": "^8"
  }
}
JSON

cat > "$PROJECT/tsconfig.json" <<'JSON'
{
  "compilerOptions": {
    "strict": true,
    "noEmit": true,
    "module": "nodenext",
    "target": "es2022",
    "skipLibCheck": true
  },
  "include": ["src"]
}
JSON

# ESLint's own recommended rules and typescript-eslint's, and nothing else.
cat > "$PROJECT/eslint.config.mjs" <<'JS'
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default [js.configs.recommended, ...tseslint.configs.recommended];
JS

cat > "$PROJECT/src/pricing.ts" <<'TS'
export function total(price: number, count: number): number {
  return price * count;
}
TS

cat > "$PROJECT/src/pricing.test.ts" <<'TS'
import { test } from "node:test";
import assert from "node:assert/strict";

import { total } from "./pricing.js";

test("total", () => {
  assert.equal(total(2, 3), 6);
});
TS

echo "  installing the project's own check tools"
(cd "$PROJECT" && npm install --no-audit --no-fund --silent) ||
  fail "could not install the TypeScript check tools, so the check could not be rehearsed"

started=$(date +%s)
first=$(run_check)
finished=$(date +%s)
[ -z "$first" ] || { cat "$WORK/last-output" >&2; fail "the new TypeScript project's check was red on day one, at $first"; }
[ -f "$PROJECT/.agents/tools/gate.py" ] || fail "the TypeScript project lost its gate script"
echo "  ok: the founded TypeScript project's check is green on day one ($((finished - started))s), with the gate script in place"

# A type error in code no test reaches. It is exported, so the linter has no
# reason to object and only the type check can see it.
cat >> "$PROJECT/src/pricing.ts" <<'TS'

export function describe(count: number): string {
  return count;
}
TS

(cd "$PROJECT" && npx tsx --test src/pricing.test.ts) > "$WORK/tests-only" 2>&1 ||
  { cat "$WORK/tests-only" >&2; fail "the TypeScript tests should still pass with the type error in place"; }
echo "  ok: the tests alone still pass with the type error in place"

first=$(run_check)
[ "$first" = "Type check" ] || fail "expected the TypeScript Type check step to go red, got '${first:-nothing}'"
grep -q 'pricing.ts' "$WORK/last-output" || fail "the TypeScript type check did not name the file"
echo "  ok: the check goes red at Type check, naming pricing.ts"

sed 's/  return count;/  return String(count);/' "$PROJECT/src/pricing.ts" > "$WORK/fixed"
mv "$WORK/fixed" "$PROJECT/src/pricing.ts"
first=$(run_check)
[ -z "$first" ] || { cat "$WORK/last-output" >&2; fail "the TypeScript check stayed red after the fix, at $first"; }
echo "  ok: the check goes green once the type error is fixed"

printf 'import { readFileSync } from "node:fs";\n%s\n' "$(cat "$PROJECT/src/pricing.ts")" > "$WORK/linted"
mv "$WORK/linted" "$PROJECT/src/pricing.ts"
first=$(run_check)
[ "$first" = "Lint" ] || { cat "$WORK/last-output" >&2; fail "expected the TypeScript Lint step to go red, got '${first:-nothing}'"; }
echo "  ok: the check goes red at Lint on an unused import"

echo
echo "check-floor-rehearsal.sh: red on a type error, green once fixed, in Python and TypeScript"
