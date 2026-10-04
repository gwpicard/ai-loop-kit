#!/usr/bin/env sh
# preflight-cutover.sh: assert everything that has to be true before the tree in
# this repository is pushed into the public one.
#
# The push is irreversible in one respect: what becomes public stays public. So
# every item here is an assertion with an expected answer, rather than a list
# somebody reads and judges. A checklist you interpret is a checklist you pass.
#
# Run it immediately before the push, not once in advance. The merged-tree
# rehearsal failed on its very first run because a new file was still untracked,
# which is exactly the class of fault that appears between "checked it" and
# "pushed it".
#
# It reads. It writes nothing except the record file it is asked for, and that
# lives outside both repositories.
#
# Run it with nothing else working in this repository. A review agent, another
# session, or an editor saving a file makes the tree momentarily dirty, and this
# reports that as a failure. It is right to: the cutover reads the commit while
# the merged-tree rehearsal reads the disk, so a tree that is not settled makes
# the two measure different things. A false alarm here costs a re-run. The
# reverse mistake costs a push nobody can take back.
#
# Usage:
#   preflight-cutover.sh              run every check, report, exit non-zero on failure
#   preflight-cutover.sh <record>     also append the results to a record file

set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT" || exit 1

RECORD=${1:-}

FAIL=0
checks=0
fail() { echo "  FAIL: $1" >&2; FAIL=1; }
ok()   { echo "  ok: $1"; }
count() { checks=$((checks + 1)); }

# expect <label> <expected> <actual>
expect() {
  count
  if [ "$2" = "$3" ]; then
    ok "$1"
  else
    fail "$1 (expected '$2', got '$3')"
  fi
}

# expect_empty <label> <value>
expect_empty() {
  count
  if [ -z "$2" ]; then
    ok "$1"
  else
    fail "$1, but found:"
    printf '%s\n' "$2" | sed 's/^/      /' >&2
  fi
}

echo "== B1. The source is what you think it is =="

# SRC and SRCTREE below are read from main, so this has to be run from main.
# On a branch the checks would read the branch's files while the recorded tree
# named main's, and the cutover asserts against the recorded one.
expect "HEAD is main" "main" "$(git rev-parse --abbrev-ref HEAD)"

expect_empty "the working tree is clean" "$(git status --porcelain)"

git fetch -q origin 2>/dev/null || true
expect "local main matches origin/main" \
  "$(git rev-parse origin/main 2>/dev/null)" "$(git rev-parse main 2>/dev/null)"

expect_empty "no case-insensitive path collisions" \
  "$(git ls-files | sort -f | uniq -di)"
expect_empty "no non-ASCII paths" \
  "$(git ls-files | LC_ALL=C grep '[^ -~]')"
expect_empty "no symlinks and no submodules" \
  "$(git ls-files -s | awk '$1!="100644" && $1!="100755"')"
expect_empty "no .gitattributes, so git archive is a faithful export" \
  "$(git ls-files | grep gitattributes)"

SRC=$(git rev-parse main)
SRCTREE=$(git rev-parse main^{tree})
echo "  SRC     = $SRC"
echo "  SRCTREE = $SRCTREE"

echo
echo "== B3. The tree is green standing alone =="

count
if python3 -c 'import yaml' 2>/dev/null; then
  ok "PyYAML is available, so the validator runs its full workflow checks"
else
  fail "PyYAML is missing; the validator would drop to its grep fallback and skip its strongest workflow assertions while still printing a pass"
fi

count
validator_out=$(.agents/tools/validate-kit.sh 2>&1)
if printf '%s' "$validator_out" | grep -q "all checks passed"; then
  ok "the validator passes"
else
  fail "the validator did not pass"
  printf '%s\n' "$validator_out" | grep -E "^FAIL" | sed 's/^/      /' >&2
fi

count
notes=$(printf '%s' "$validator_out" | grep "^NOTE" || true)
if [ -z "$notes" ]; then
  ok "the validator skipped nothing"
else
  fail "the validator printed a NOTE, which means a check was reduced rather than run:"
  printf '%s\n' "$notes" | sed 's/^/      /' >&2
fi

count
suite_out=$(.agents/tests/run-all.sh 2>&1)
suite_line=$(printf '%s' "$suite_out" | grep -E "^[0-9]+ of [0-9]+ rehearsals passed" || true)
if printf '%s' "$suite_out" | grep -q "Every rehearsal passed"; then
  ok "every rehearsal passed: $suite_line"
else
  fail "a rehearsal failed: $suite_line"
  printf '%s' "$suite_out" | grep -E "^  - " | sed 's/^/      /' >&2
fi

echo
echo "== B4. The rework is real =="

# The strings below are built from parts so this file does not match its own
# searches. It lives in .agents/tools/ and searches .agents/tools/, so written
# out whole it would find itself, count itself, and fail. The validator's
# issue-number check builds its pattern the same way and for the same reason.
retired_repo="ai-build-kit-""maintainer"
credential="STARTER_""APP_|create-github-""app-token|x-access-""token"

expect_empty "no retired repository name in the workflows or the tools" \
  "$(grep -rn "$retired_repo" .github/workflows .agents/tools 2>/dev/null)"

expect "the retired name survives only where a check uses it as the thing to catch" \
  "3" "$(grep -rn "$retired_repo" $(git ls-files) 2>/dev/null | wc -l | tr -d ' ')"

expect_empty "no workflow can mint a credential beyond the run's own token" \
  "$(grep -rnE "$credential" .github/workflows 2>/dev/null)"

expect "the credential strings survive only in one guard and one record" \
  "2" "$(grep -rlE "$credential" $(git ls-files) 2>/dev/null | wc -l | tr -d ' ')"

expect "every workflow gate names the public repository" \
  "6" "$(grep -c "github.repository == 'gwpicard/ai-build-kit'" .github/workflows/*.yml | awk -F: '{s+=$2} END {print s}')"

expect_empty "no gate names any other repository" \
  "$(grep -n "github.repository" .github/workflows/*.yml | grep -v "github.repository == 'gwpicard/ai-build-kit'")"

expect "the deleted publisher has not come back" \
  "0" "$(find .github/workflows .agents/tools -name '*publish-starter*' 2>/dev/null | wc -l | tr -d ' ')"

echo
echo "  The two branch-protection contexts, read off the workflow:"
python3 - <<'PY' 2>/dev/null || echo "      (could not read; PyYAML missing)"
import yaml
d = yaml.safe_load(open('.github/workflows/source-checks.yml'))
for job, body in d['jobs'].items():
    named = body.get('name')
    print(f"      {job}" + (f"  (name: {named})" if named else "  (no name: key, so the job id is the check name)"))
PY

echo
echo "== B5. The distribution surface survives =="

count
missing=$(python3 - <<'PY'
import json, os
m = json.load(open('.claude-plugin/plugin.json'))
paths = [p for k in ('commands', 'skills') for p in m.get(k, [])]
print("\n".join(p for p in paths if not os.path.exists(os.path.normpath(p))))
PY
)
if [ -z "$missing" ]; then
  ok "every path the Claude plugin manifest names resolves"
else
  fail "the Claude plugin manifest names paths that do not exist:"
  printf '%s\n' "$missing" | sed 's/^/      /' >&2
fi

count
if grep -qF '"source": "./"' .claude-plugin/marketplace.json; then
  ok "the marketplace still publishes the repository root"
else
  fail "the marketplace no longer publishes the repository root"
fi

count
if [ ! -e .github/workflows/checks.yml ]; then
  ok "the project's placeholder check is not at this repository's root"
else
  fail ".github/workflows/checks.yml is at the root; that placeholder always fails and belongs only in an assembled release"
fi

count
if [ -f .agents/skills/setup-ai-build-kit/templates/foundation/checks.yml ]; then
  ok "the project check template is where the release builder reads it"
else
  fail "the project check template is missing"
fi

echo
echo "== B7. The tree carries a real version =="

count
version_line=$(printf '%s' "$validator_out" | grep "version-bearing files agree" || true)
if [ -n "$version_line" ]; then
  ok "${version_line#ok: }"
else
  fail "the validator did not report the three version-bearing files agreeing"
fi

count
if .agents/tools/stamp-version.sh --check v0.10.0 >/dev/null 2>&1; then
  ok "main is stamped at v0.10.0, which is what the public repository publishes today"
else
  fail "main is not stamped at v0.10.0; a cutover now would publish a tree calling itself 0.0.0-development"
fi

echo
echo "==================================="
if [ "$FAIL" -ne 0 ]; then
  echo "PRE-FLIGHT FAILED. Do not push." >&2
else
  echo "Pre-flight passed: $checks checks."
  echo "SRCTREE $SRCTREE is what the cutover must reproduce exactly."
fi

if [ -n "$RECORD" ]; then
  {
    printf '\n=== pre-flight %s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'SRC     = %s\n' "$SRC"
    printf 'SRCTREE = %s\n' "$SRCTREE"
    printf 'result  = %s (%s checks)\n' "$([ "$FAIL" -eq 0 ] && echo passed || echo FAILED)" "$checks"
  } >> "$RECORD"
  echo "Recorded in $RECORD"
fi

exit "$FAIL"
