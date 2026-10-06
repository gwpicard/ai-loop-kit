#!/usr/bin/env sh
# newtest-lint.sh: the new-test lint, run as the gate will run it.
#
#   1. rule-shape: each rule is declared once in loop/newtest_lint.py, and
#      removing one declaration is caught;
#   2. each planted smell, in Python and in TypeScript, is refused for its own
#      rule; the report-only rules report and never refuse; a clean test passes;
#   3. a mutation per rule: a copy of the lint with that one rule switched off
#      lets the planted smell through;
#   4. the git route, in a throwaway project: only added lines are judged.
#
# No network, no GitHub account, no model.
#
# Run alone: tests/newtest-lint.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

# shellcheck disable=SC1091
. "$ROOT/tests/lib/rule-shape.sh"

LINT="$ROOT/kit/scripts/newtest-lint.py"
MODULE="$ROOT/kit/scripts/loop/newtest_lint.py"
FIX="$ROOT/tests/fixtures/test-smells"

REFUSING="no_assertion skip_added assert_true duplicate_assertion conditional_logic sleep
  debug_print own_module_mock call_count test_detect snapshot_rewritten suppression
  swallowed_error debug_leftover"
REPORTING="assertion_roulette magic_number"
# Judged as a source file, not as a test.
SOURCE_RULES=" test_detect "

# --- 1. rule-shape ----------------------------------------------------------
rs_init "New-test lint rules"
for rule in $REFUSING $REPORTING; do
  rs_rule "the rule $rule is declared once" "= \"$rule\""
done
rs_rule "the refusing rules are named in one place" 'refusing = frozenset'
rs_rule "the report-only rules are named in one place" 'report_only = frozenset'
rs_guard "$MODULE" "loop/newtest_lint.py"
rs_require "the script is marked for the contract test" "$LINT" '# contract: agent'

fail() { rs_fail "$1"; }

WORK=$(mktemp -d)

stage() {
  # stage <rule> <language>: copy a fixture under a name that says what it is.
  rule=$1
  lang=$2
  case "$SOURCE_RULES" in
    *" $rule "*) name="app.$lang" ;;
    *) if [ "$lang" = py ]; then name="test_$rule.py"; else name="$rule.test.ts"; fi ;;
  esac
  mkdir -p "$WORK/$rule-$lang"
  cp "$FIX/$rule.$lang.fixture" "$WORK/$rule-$lang/$name"
  echo "$WORK/$rule-$lang/$name"
}

run_lint() {
  # run_lint <out-name> <args...>: save standard output and the exit code.
  out=$1
  shift
  code=0
  "$LINT" "$@" >"$WORK/$out.json" 2>"$WORK/$out.err" || code=$?
}

mentions() {
  # mentions <file> <word>: the JSON names the rule.
  grep -q "\"rule\": \"$2\"" "$1"
}

# --- 2. each smell, and the clean tests -------------------------------------
for lang in py ts; do
  for rule in $REFUSING; do
    [ "$rule" = snapshot_rewritten ] && continue
    file=$(stage "$rule" "$lang")
    run_lint "r-$rule-$lang" --file "$file" --own-module billing --json
    [ "$code" = 1 ] || fail "$rule ($lang): expected exit 1, got $code"
    mentions "$WORK/r-$rule-$lang.json" "$rule" || fail "$rule ($lang): the refusal does not name the rule"
    grep -q '^next: ' "$WORK/r-$rule-$lang.err" || fail "$rule ($lang): no next: line"
    rs_ok "$rule is refused in $lang"
  done
  for rule in $REPORTING; do
    file=$(stage "$rule" "$lang")
    run_lint "r-$rule-$lang" --file "$file" --own-module billing --json
    [ "$code" = 0 ] || fail "$rule ($lang): a report-only rule must not refuse, exit $code"
    mentions "$WORK/r-$rule-$lang.json" "$rule" || fail "$rule ($lang): not reported"
    rs_ok "$rule is reported and never refuses in $lang"
  done
  if [ "$lang" = py ]; then clean="test_clean.py"; else clean="clean.test.ts"; fi
  mkdir -p "$WORK/clean-$lang"
  cp "$FIX/clean.$lang.fixture" "$WORK/clean-$lang/$clean"
  run_lint "clean-$lang" --file "$WORK/clean-$lang/$clean" --own-module billing --json
  [ "$code" = 0 ] || fail "the clean $lang test was refused: $(cat "$WORK/clean-$lang.json")"
  rs_ok "a clean $lang test passes"
done

# The snapshot rule reads a change list, so it runs through the git route below.

# --- 3. a mutation per rule -------------------------------------------------
for rule in $REFUSING; do
  [ "$rule" = snapshot_rewritten ] && continue
  mut="$WORK/mutant-$rule"
  mkdir -p "$mut/loop"
  cp "$ROOT"/kit/scripts/loop/*.py "$mut/loop/"
  cp "$LINT" "$mut/newtest-lint.py"
  sed "s@^DEFAULT_RULES = .*@DEFAULT_RULES = frozenset(r for r in Rule if r.value != \"$rule\")@" \
    "$MODULE" > "$mut/loop/newtest_lint.py"
  grep -q "r.value != \"$rule\"" "$mut/loop/newtest_lint.py" || fail "$rule: the mutation did not apply"
  for lang in py ts; do
    file=$(stage "$rule" "$lang")
    code=0
    "$mut/newtest-lint.py" --file "$file" --own-module billing --json >"$WORK/m.json" 2>/dev/null || code=$?
    [ "$code" = 0 ] || fail "$rule ($lang): with the rule off the smell was still refused"
  done
  rs_ok "with $rule switched off its planted smell passes, so the rule does the work"
done

# --- 3b. the variants of a rule ---------------------------------------------
# A cheap way round a rule is a variant. Each planted variant is refused for its
# own rule, and with that rule off it passes, so the rule does the work.
VAR="$FIX/variants"
for fixture in "$VAR"/*.fixture; do
  base=$(basename "$fixture" .fixture)       # <rule>--<name>.<lang>
  lang=${base##*.}
  head=${base%.*}
  rule=${head%%--*}
  name=${head#*--}
  mkdir -p "$WORK/v-$head-$lang"
  if [ "$lang" = py ]; then vfile="$WORK/v-$head-$lang/test_$name.py"; else vfile="$WORK/v-$head-$lang/$name.test.ts"; fi
  cp "$fixture" "$vfile"
  run_lint "v-$head-$lang" --file "$vfile" --own-module billing --json
  [ "$code" = 1 ] || fail "variant $head ($lang): expected exit 1, got $code"
  mentions "$WORK/v-$head-$lang.json" "$rule" || fail "variant $head ($lang): the refusal does not name $rule"
  mut="$WORK/mutant-$rule"
  code=0
  "$mut/newtest-lint.py" --file "$vfile" --own-module billing --json >"$WORK/m.json" 2>/dev/null || code=$?
  [ "$code" = 0 ] || fail "variant $head ($lang): with $rule off the variant was still refused"
  rs_ok "variant $head ($lang) is refused for $rule, and passes with $rule off"
done

# --- 4. the git route -------------------------------------------------------
. "$ROOT/tests/lib/throwaway-project.sh"
tp_new tested
cd "$TP_ROOT"
mkdir -p tests/__snapshots__ src
cat > tests/test_billing.py <<'PY'
import time

from billing import total


def test_old_sleeper():
    time.sleep(1)
    assert total([1, 2]) == 3
PY
printf 'def total(items):\n    return sum(items)\n' > src/billing.py
printf 'snapshot one\n' > tests/__snapshots__/test_billing.ambr
git add -A
git commit -q -m "Add billing and its tests"

run_lint git-clean --base HEAD --json
[ "$code" = 0 ] || fail "an unchanged project was refused: $(cat "$WORK/git-clean.json")"
rs_ok "no change, nothing to refuse (the old sleep is left alone)"

# A clean new test, and a new test with only report-only smells.
cat >> tests/test_billing.py <<'PY'


def test_new_total():
    assert total([5, 6]) == 11
    assert total([40, 2]) == 42
    assert total([98, 1]) == 99
PY
run_lint git-report --base HEAD --json
[ "$code" = 0 ] || fail "a clean new test was refused: $(cat "$WORK/git-report.json")"
mentions "$WORK/git-report.json" magic_number || fail "the magic numbers were not reported"
rs_ok "a new test with only report-only smells passes and is reported"

# A new sleeper, a rewritten snapshot beside a code change, and a test-env check.
cat >> tests/test_billing.py <<'PY'


def test_new_sleeper():
    time.sleep(2)
    assert total([3]) == 3
PY
printf 'snapshot two\n' > tests/__snapshots__/test_billing.ambr
printf 'import os\n\n\ndef total(items):\n    if os.environ.get("PYTEST_CURRENT_TEST"):\n        return 3\n    return sum(items)\n' > src/billing.py
printf 'def test_untracked():\n    total([1])\n' > tests/test_untracked.py
run_lint git-bad --base HEAD --json
[ "$code" = 1 ] || fail "the bad change was not refused (exit $code)"
for rule in sleep snapshot_rewritten test_detect no_assertion; do
  mentions "$WORK/git-bad.json" "$rule" || fail "the bad change did not trip $rule"
done
grep -q '"line": 7,' "$WORK/git-bad.json" && fail "the old sleep (line 7) was judged, but only added lines count"
grep -q '^next: ' "$WORK/git-bad.err" || fail "no next: line on the refusal"
rs_ok "the bad change trips sleep, snapshot_rewritten, test_detect and no_assertion (an untracked test too)"

# --- refusals of bad use ----------------------------------------------------
cd "$WORK"
run_lint none --json
[ "$code" = 2 ] || fail "no arguments should exit 2, got $code"
grep -q '^next: ' "$WORK/none.err" || fail "no next: line for no arguments"
run_lint nofile --file "$WORK/does-not-exist.py" --json
[ "$code" = 4 ] || fail "a missing file should exit 4, got $code"
run_lint both --file x.py --base HEAD --json
[ "$code" = 2 ] || fail "--file with --base should exit 2, got $code"
rs_ok "bad use exits 2 or 4 with a next: line"

rs_done
