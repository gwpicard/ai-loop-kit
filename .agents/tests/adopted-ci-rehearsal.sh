#!/usr/bin/env sh
# adopted-ci-rehearsal.sh: run the founding bootstrap in throwaway projects and
# read what it left in .github/workflows/.
#
# A project the kit adopts may already run its tests on every pull request.
# The bootstrap once copied the kit's checks.yml whenever that file was
# missing, and its placeholder step fails on purpose, so an adopted skill
# library got a red check on every pull request beside its working one. The
# agent there deleted the file by hand. So where a workflow already runs on
# pull requests and has a run: line containing the word test, the bootstrap
# copies no checks.yml and names that file. Everything else stays as it was: a
# project with no CI, a workflow that runs only on push, and a pull request
# workflow that runs no tests all still get checks.yml, and a checks.yml the
# project already had is kept untouched.
#
# adopted-ci.sh reads the written rules back. This one runs the script.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SKILL="$ROOT/.agents/skills/setup-ai-build-kit"
TEMPLATE="$SKILL/templates/foundation/checks.yml"

SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT

passed=0
fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
  passed=$((passed + 1))
}

# project <name>: a folder holding its own installed copy of the founding
# skill, as a whole copy or the shared installer leaves one.
project() {
  dir="$SCRATCH/$1"
  mkdir -p "$dir/.agents/skills" "$dir/.github/workflows"
  cp -R "$SKILL" "$dir/.agents/skills/setup-ai-build-kit"
  printf '%s\n' "$dir"
}

bootstrap() {
  (cd "$1" && sh .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh) \
    > "$1.out" 2>&1 || { cat "$1.out" >&2; fail "the bootstrap stopped in $(basename "$1")"; }
}

echo "Adopted CI rehearsal:"

# 1. A workflow on pull requests whose run: line runs the tests.
P=$(project own-ci)
cat > "$P/.github/workflows/ci.yml" <<'YML'
name: ci
on:
  pull_request:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test
YML
bootstrap "$P"
[ ! -e "$P/.github/workflows/checks.yml" ] || \
  fail "a project whose own workflow runs its tests on pull requests was given checks.yml"
ok "a project whose own CI runs its tests gets no checks.yml"
grep -q '\.github/workflows/ci\.yml' "$P.out" || \
  fail "the bootstrap did not name the project's own workflow"
[ "$(grep -c 'ci\.yml' "$P.out")" -eq 1 ] || \
  fail "the bootstrap named the workflow on more than one line"
ok "the bootstrap names the project's own workflow in one line"
[ -f "$P/AGENTS.md" ] && [ -f "$P/.claude/settings.json" ] && \
  [ -f "$P/.agents/hooks/check-sensitive-areas.sh" ] || \
  fail "the other foundation files were not copied beside the project's own CI"
ok "every other foundation file is still copied"
grep -q 'npm test' "$P/.github/workflows/ci.yml" || \
  fail "the project's own workflow was changed"
ok "the project's own workflow is left as it was"

# 2. A .yaml file whose tests run inside a multi-line run: block.
P=$(project own-ci-block)
cat > "$P/.github/workflows/test.yaml" <<'YML'
on: [pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install and test
        run: |
          pip install -r requirements.txt
          python -m pytest
YML
bootstrap "$P"
[ ! -e "$P/.github/workflows/checks.yml" ] || \
  fail "a .yaml workflow running pytest in a run block was not counted"
grep -q '\.github/workflows/test\.yaml' "$P.out" || \
  fail "the bootstrap did not name the .yaml workflow"
ok "a .yaml workflow whose tests run in a run block counts too"

# 3. No workflow at all: checks.yml as today.
P=$(project no-ci)
bootstrap "$P"
cmp -s "$TEMPLATE" "$P/.github/workflows/checks.yml" || \
  fail "a project with no CI did not get the kit's checks.yml"
ok "a project with no CI gets checks.yml as today"
if grep -qi 'workflow' "$P.out"; then
  fail "the bootstrap named a workflow in a project that has none"
fi
ok "and hears nothing about a workflow of its own"

# 4. A workflow that runs its tests only on push is not a pull request check.
P=$(project push-only)
cat > "$P/.github/workflows/nightly.yml" <<'YML'
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: make test
YML
bootstrap "$P"
cmp -s "$TEMPLATE" "$P/.github/workflows/checks.yml" || \
  fail "a project whose only workflow runs on push was not given checks.yml"
ok "a workflow that runs only on push is not a pull request check"

# 5. A pull request workflow that runs no tests, such as a labeller.
P=$(project labeller)
cat > "$P/.github/workflows/labeller.yml" <<'YML'
on:
  pull_request:
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v5
      - run: echo "labelled"
YML
bootstrap "$P"
cmp -s "$TEMPLATE" "$P/.github/workflows/checks.yml" || \
  fail "a pull request workflow that runs no tests stopped checks.yml being copied"
ok "a pull request workflow that runs no tests is not a project check"
grep -q 'labelled' "$P/.github/workflows/labeller.yml" || \
  fail "the labeller was changed"
ok "and the project's workflows stay as they are"

# 6. A checks.yml the project already had, that is not the kit's placeholder.
P=$(project own-checks)
cat > "$P/.github/workflows/checks.yml" <<'YML'
on: pull_request
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - run: go test ./...
YML
cp "$P/.github/workflows/checks.yml" "$SCRATCH/own-checks.before"
bootstrap "$P"
cmp -s "$SCRATCH/own-checks.before" "$P/.github/workflows/checks.yml" || \
  fail "the project's own checks.yml was overwritten"
ok "a checks.yml the project already had is kept untouched"

echo
echo "$(basename -- "$0"): all $passed checks passed"
