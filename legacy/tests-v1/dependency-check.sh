#!/usr/bin/env sh
# dependency-check.sh: run kit/scripts/dependency-check.py on a throwaway project
# with a planted lockfile change, for npm, pnpm and uv. Then check each package
# manager template against the manager on this computer.
#
# The registry is the stand-in under tests/stand-ins/fake-registry, so nothing
# here uses the network. A step that cannot run on this computer prints a
# visible "skipped" line. A skip is never counted as a pass.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT
. "$ROOT/tests/lib/throwaway-project.sh"

FAIL=0
SKIPPED=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}
skip() {
  echo "skipped: $1"
  SKIPPED=$((SKIPPED + 1))
}

CHECK="$ROOT/kit/scripts/dependency-check.py"
REGISTRY="$ROOT/tests/stand-ins/fake-registry"
NOW="2026-10-06T00:00:00Z"

[ -x "$CHECK" ] || {
  echo "FAIL: $CHECK is missing or not executable" >&2
  exit 1
}

tp_new demo
cd "$TP_ROOT"

run_check() {
  # run_check <lockfile> <expected exit code> <label> [more arguments]
  lock=$1
  want=$2
  label=$3
  shift 3
  code=0
  "$CHECK" --lockfile "$lock" --base-ref HEAD --registry "$REGISTRY" --now "$NOW" --json "$@" \
    >"$TP_BASE/out.json" 2>"$TP_BASE/err.txt" || code=$?
  if [ "$code" -ne "$want" ]; then
    cat "$TP_BASE/out.json" "$TP_BASE/err.txt" >&2
    fail "$label (exit $code, wanted $want)"
    return 1
  fi
  pass "$label"
}

finding_names() {
  python3 -c '
import json, sys
print(" ".join(sorted(f["name"] for f in json.load(open(sys.argv[1]))["findings"])))
' "$TP_BASE/out.json"
}

expect_findings() {
  # expect_findings <names> <label>
  got=$(finding_names)
  if [ "$got" = "$1" ]; then
    pass "$2"
  else
    fail "$2 (findings: '$got', wanted '$1')"
  fi
}

# --- npm ----------------------------------------------------------------------
cat > package-lock.json <<'JSON'
{"lockfileVersion": 3, "packages": {
  "": {"name": "demo", "version": "1.0.0"},
  "node_modules/old-mit": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/old-mit/-/old-mit-1.0.0.tgz"}
}}
JSON
git add package-lock.json
git commit -q -m "Add the npm lockfile"

run_check package-lock.json 0 "npm: no change passes"
cat > package-lock.json <<'JSON'
{"lockfileVersion": 3, "packages": {
  "": {"name": "demo", "version": "1.0.0"},
  "node_modules/old-mit": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/old-mit/-/old-mit-1.0.0.tgz"},
  "node_modules/@scope/pkg": {"version": "1.2.3", "resolved": "https://registry.npmjs.org/@scope/pkg/-/pkg-1.2.3.tgz"}
}}
JSON
run_check package-lock.json 0 "npm: an old package with an allowed licence passes"

cat > package-lock.json <<'JSON'
{"lockfileVersion": 3, "packages": {
  "": {"name": "demo", "version": "1.0.0"},
  "node_modules/old-mit": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/old-mit/-/old-mit-1.0.0.tgz"},
  "node_modules/fresh-mit": {"version": "2.0.0", "resolved": "https://registry.npmjs.org/fresh-mit/-/fresh-mit-2.0.0.tgz"},
  "node_modules/old-gpl": {"version": "3.1.0", "resolved": "https://registry.npmjs.org/old-gpl/-/old-gpl-3.1.0.tgz"}
}}
JSON
if run_check package-lock.json 3 "npm: a package too new and a licence not allowed are refused"; then
  expect_findings "fresh-mit old-gpl" "npm: the refusal names both packages"
  grep -q '^next:' "$TP_BASE/err.txt" && pass "npm: the refusal has a next: line" \
    || fail "npm: the refusal has no next: line"
fi
git checkout -q -- package-lock.json

# --- pnpm ---------------------------------------------------------------------
cat > pnpm-lock.yaml <<'YAML'
lockfileVersion: '9.0'

packages:

  old-mit@1.0.0:
    resolution: {integrity: sha512-aaa}
YAML
git add pnpm-lock.yaml
git commit -q -m "Add the pnpm lockfile"
cat > pnpm-lock.yaml <<'YAML'
lockfileVersion: '9.0'

packages:

  fresh-mit@2.0.0:
    resolution: {integrity: sha512-ccc}

  no-licence@0.4.0:
    resolution: {integrity: sha512-ddd}

  old-mit@1.0.0:
    resolution: {integrity: sha512-aaa}
YAML
if run_check pnpm-lock.yaml 3 "pnpm: a package too new and a package with no licence are refused"; then
  expect_findings "fresh-mit no-licence" "pnpm: the refusal names both packages"
fi
git checkout -q -- pnpm-lock.yaml
run_check pnpm-lock.yaml 0 "pnpm: no change passes"

# --- uv -----------------------------------------------------------------------
cat > uv.lock <<'TOML'
version = 1
requires-python = ">=3.10"

[[package]]
name = "demo"
version = "0.1.0"
source = { virtual = "." }

[[package]]
name = "oldpy"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
TOML
git add uv.lock
git commit -q -m "Add the uv lockfile"
run_check uv.lock 0 "uv: no change passes"
cat >> uv.lock <<'TOML'

[[package]]
name = "freshpy"
version = "0.1.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "weirdpy"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "classpy"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
TOML
if run_check uv.lock 3 "uv: a package too new and a licence not allowed are refused"; then
  expect_findings "freshpy weirdpy" "uv: the refusal names the two packages, not the allowed one"
fi
if run_check uv.lock 3 "uv: a shorter age limit lets freshpy in and still refuses the licence" \
  --min-age-days 1; then
  expect_findings "weirdpy" "uv: only the licence is left to refuse"
fi
git checkout -q -- uv.lock

# Run twice: the same answer.
"$CHECK" --lockfile uv.lock --base-ref HEAD --registry "$REGISTRY" --now "$NOW" --json >"$TP_BASE/a.json" 2>/dev/null || true
"$CHECK" --lockfile uv.lock --base-ref HEAD --registry "$REGISTRY" --now "$NOW" --json >"$TP_BASE/b.json" 2>/dev/null || true
cmp -s "$TP_BASE/a.json" "$TP_BASE/b.json" && pass "the same input gives the same answer" \
  || fail "the same input gave two answers"

# --- the templates, against the managers on this computer ----------------------
version_ge() {
  # version_ge <found> <wanted>: true when found is the same or newer
  python3 - "$1" "$2" <<'PY'
import re, sys
def parts(text):
    return [int(n) for n in re.findall(r"\d+", text)[:3]]
sys.exit(0 if parts(sys.argv[1]) >= parts(sys.argv[2]) else 1)
PY
}

NPMRC="$ROOT/kit/templates/npmrc"
UVTOML="$ROOT/kit/templates/uv.toml"
[ -f "$NPMRC" ] || fail "kit/templates/npmrc is missing"
[ -f "$UVTOML" ] || fail "kit/templates/uv.toml is missing"

grep -q '^ignore-scripts=true$' "$NPMRC" && pass "npmrc turns install scripts off" \
  || fail "npmrc does not hold ignore-scripts=true"
grep -q '^min-release-age=' "$NPMRC" && pass "npmrc sets min-release-age (npm, in days)" \
  || fail "npmrc does not set min-release-age"
grep -q '^minimum-release-age=' "$NPMRC" && pass "npmrc sets minimum-release-age (pnpm, in minutes)" \
  || fail "npmrc does not set minimum-release-age"

if command -v npm >/dev/null 2>&1; then
  mkdir -p "$TP_BASE/npm-project"
  cp "$NPMRC" "$TP_BASE/npm-project/.npmrc"
  (cd "$TP_BASE/npm-project" && printf '{"name":"x","version":"1.0.0"}\n' > package.json)
  got=$(cd "$TP_BASE/npm-project" && npm config get ignore-scripts 2>/dev/null)
  [ "$got" = "true" ] && pass "npm reads ignore-scripts=true from the template" \
    || fail "npm reads ignore-scripts as '$got' from the template"
  want=$(sed -n 's/^min-release-age=//p' "$NPMRC")
  # A setting the manager knows has a default in the full listing. One it does
  # not know only shows up when a config file sets it, so look with no files.
  mkdir -p "$TP_BASE/npm-empty"
  known=$(cd "$TP_BASE/npm-empty" && npm config ls -l --userconfig /dev/null --globalconfig /dev/null 2>/dev/null \
    | sed -n 's/^min-release-age = //p')
  npm_version=$(npm --version)
  if [ -z "$known" ]; then
    skip "npm $npm_version has no min-release-age setting (npm 11.10 or later has it)"
  else
    got=$(cd "$TP_BASE/npm-project" && npm config get min-release-age 2>/dev/null)
    [ "$got" = "$want" ] && pass "npm $npm_version reads min-release-age=$want from the template" \
      || fail "npm $npm_version reads min-release-age as '$got', the template says '$want'"
  fi
else
  skip "npm is not installed, so the npm template is not checked"
fi

if command -v pnpm >/dev/null 2>&1; then
  pnpm_version=$(pnpm --version 2>/dev/null)
  got=$(cd "$TP_BASE/npm-project" 2>/dev/null && pnpm config get ignore-scripts 2>/dev/null || echo "")
  [ "$got" = "true" ] && pass "pnpm $pnpm_version reads ignore-scripts=true from the template" \
    || fail "pnpm $pnpm_version reads ignore-scripts as '$got' from the template"
  want=$(sed -n 's/^minimum-release-age=//p' "$NPMRC")
  if version_ge "$pnpm_version" 10.16.0; then
    got=$(cd "$TP_BASE/npm-project" && pnpm config get minimum-release-age 2>/dev/null || echo "")
    [ "$got" = "$want" ] && pass "pnpm $pnpm_version reads minimum-release-age=$want from the template" \
      || fail "pnpm $pnpm_version reads minimum-release-age as '$got', the template says '$want'"
  else
    skip "pnpm $pnpm_version has no minimum-release-age setting (pnpm 10.16 or later has it)"
  fi
else
  skip "pnpm is not installed, so the pnpm template is not checked"
fi

grep -q '^exclude-newer *=' "$UVTOML" && pass "uv.toml sets exclude-newer" \
  || fail "uv.toml does not set exclude-newer"
grep -q '^no-build *= *true' "$UVTOML" && pass "uv.toml turns builds from source off" \
  || fail "uv.toml does not hold no-build = true"

if command -v uv >/dev/null 2>&1; then
  uv_version=$(uv --version)
  uvp="$TP_BASE/uv-project"
  mkdir -p "$uvp"
  printf '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.10"\n' > "$uvp/pyproject.toml"
  cp "$UVTOML" "$uvp/uv.toml"
  if (cd "$uvp" && uv lock --offline >"$TP_BASE/uv.out" 2>&1); then
    pass "$uv_version accepts the whole uv.toml template"
  elif grep -q 'exclude-newer' "$TP_BASE/uv.out"; then
    skip "$uv_version takes only a date for exclude-newer, not a number of days"
    # Every other line must still be read: swap the duration for a date.
    sed 's/^exclude-newer *=.*/exclude-newer = "2026-09-01T00:00:00Z"/' "$UVTOML" > "$uvp/uv.toml"
    if (cd "$uvp" && uv lock --offline >"$TP_BASE/uv.out" 2>&1); then
      pass "$uv_version accepts the rest of the uv.toml template (with a date)"
    else
      cat "$TP_BASE/uv.out" >&2
      fail "$uv_version refuses the uv.toml template even with a date"
    fi
  else
    cat "$TP_BASE/uv.out" >&2
    fail "$uv_version refuses the uv.toml template"
  fi
else
  skip "uv is not installed, so the uv template is not checked"
fi

echo
if [ "$FAIL" -ne 0 ]; then
  echo "FAIL: dependency-check.sh found a fault" >&2
  exit 1
fi
echo "dependency-check.sh passed ($SKIPPED skipped)"
