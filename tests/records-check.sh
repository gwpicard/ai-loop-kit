#!/usr/bin/env sh
# records-check.sh: found a throwaway project from the kit's templates, require
# kit/scripts/records-check.py to pass on it, then plant each fault in a clone
# of it and require the check to fail with that fault's rule, and no other.
#
# The control comes first for each fault: the clone passes before the plant, so
# a check that failed on everything would fail here as surely as one that failed
# on nothing. The run lines of the shipped checks.yml are read out and run as they
# stand. Nothing here deletes anything: each fault goes in a fresh clone.
#
# No network, no GitHub account and no model. Run it alone: tests/records-check.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/kit/scripts/records-check.py"
TEMPLATES="$ROOT/kit/templates"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

[ -f "$CHECK" ] || fail "there is no records check at kit/scripts/records-check.py"
for template in AGENTS.md CLAUDE.md overview.md docs-README.md CHANGELOG.md area-map checks.yml; do
  [ -f "$TEMPLATES/$template" ] || fail "the template kit/templates/$template is missing"
done

. "$ROOT/tests/lib/throwaway-project.sh"
tp_new founded

save() {
  # save <folder> <message>: commit everything in a clone or in the project.
  git -C "$1" add -A
  git -C "$1" commit -q --allow-empty -m "$2"
}

# --- found the project from the templates -----------------------------------

mkdir -p "$TP_ROOT/docs" "$TP_ROOT/.github/workflows" "$TP_ROOT/.agents/loop" \
  "$TP_ROOT/.agents/guard" "$TP_ROOT/.claude"
# Founding places these too, and AGENTS.md names them.
cp "$TEMPLATES/blocked-commands.md" "$TP_ROOT/.agents/guard/blocked-commands.md"
cp "$TEMPLATES/claude-settings.json" "$TP_ROOT/.claude/settings.json"
cp "$TEMPLATES/AGENTS.md" "$TP_ROOT/AGENTS.md"
cp "$TEMPLATES/CLAUDE.md" "$TP_ROOT/CLAUDE.md"
cp "$TEMPLATES/CHANGELOG.md" "$TP_ROOT/CHANGELOG.md"
cp "$TEMPLATES/overview.md" "$TP_ROOT/docs/overview.md"
cp "$TEMPLATES/docs-README.md" "$TP_ROOT/docs/README.md"
cp "$TEMPLATES/area-map" "$TP_ROOT/docs/area-map"
sed 's/{{KIT_REF}}/main/' "$TEMPLATES/checks.yml" > "$TP_ROOT/.github/workflows/checks.yml"
cp "$TEMPLATES/policy.json" "$TP_ROOT/.agents/loop/policy.json"
save "$TP_ROOT" "Found the project from the templates"

run_check() {
  # run_check <folder> [args]: print the JSON, set code to the exit code.
  folder=$1
  shift
  code=0
  out=$(cd "$folder" && python3 "$CHECK" --json "$@" 2>/dev/null) || code=$?
}

rules_of() {
  printf '%s' "$out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(" ".join(sorted({f["rule"] for f in data.get("faults", [])})))'
}

run_check "$TP_ROOT"
[ "$code" = 0 ] || fail "a project founded from the templates fails the check: $out"
ok "a project founded from the templates passes"

# --- each fault, in a clone of the founded project --------------------------

case_number=0
plant() {
  # plant <name> <rule> <shell commands run in the clone> [-- check arguments]
  name=$1
  rule=$2
  commands=$3
  shift 3
  case_number=$((case_number + 1))
  clone="$TP_BASE/fault-$case_number"
  git clone -q "$TP_ROOT" "$clone"
  run_check "$clone"
  [ "$code" = 0 ] || fail "$name: the control clone fails before the fault is planted: $out"
  (cd "$clone" && sh -c "$commands")
  save "$clone" "Plant: $name"
  run_check "$clone" "$@"
  [ "$code" = 1 ] || fail "$name: expected exit 1, got $code: $out"
  found=$(rules_of)
  [ "$found" = "$rule" ] || fail "$name: expected the rule '$rule' alone, got '$found'"
  ok "$name fails with $rule"
}

plant "AGENTS.md over 150 lines" agents.lines \
  'i=0; while [ $i -lt 40 ]; do printf "\n## Extra %s\n\n- a line\n" "$i" >> AGENTS.md; i=$((i+1)); done'

plant "an AGENTS.md section over 12 lines" agents.section \
  'i=0; while [ $i -lt 13 ]; do printf -- "- rule %s, with its reason.\n" "$i" >> AGENTS.md; i=$((i+1)); done'

plant "a path AGENTS.md names that does not exist" names \
  'printf "\nRun \`scripts/release.sh\` to ship.\n" >> AGENTS.md'

plant "CLAUDE.md that holds more than the import" claude.import \
  'printf "\nAlso be kind.\n" >> CLAUDE.md'

plant "an overview over 100 lines" overview.lines \
  'i=0; while [ $i -lt 100 ]; do printf "Extra line %s.\n\n" "$i" >> docs/overview.md; i=$((i+1)); done'

plant "an overview area the map does not have" overview.area \
  'printf "| ghost | Nothing | no | | \`docs/README.md\` |\n" >> docs/overview.md'

plant "an area in the map that the overview does not name" overview.area \
  'mkdir src && echo 1 > src/a.js && printf "src/ app\n" >> docs/area-map'

plant "a sensitive flag that is not yes or no" overview.sensitive \
  'sed "s/| no |/| perhaps |/" docs/overview.md > docs/overview.tmp && mv docs/overview.tmp docs/overview.md'

plant "a sensitive area with no boundary" overview.sensitive \
  'sed "s/| no |/| yes |/" docs/overview.md > docs/overview.tmp && mv docs/overview.tmp docs/overview.md'

plant "an area doc over 300 lines" docs.lines \
  'mkdir src && echo 1 > src/a.js && printf "src/ app\n" >> docs/area-map
   printf "| app | The app | no | | \`docs/app.md\` |\n" >> docs/overview.md
   i=0; while [ $i -lt 301 ]; do echo "- requirement $i" >> docs/app.md; i=$((i+1)); done'

plant "an area that names no doc" docs.missing \
  'mkdir src && echo 1 > src/a.js && printf "src/ app\n" >> docs/area-map
   printf "| app | The app | no | | |\n" >> docs/overview.md'

plant "a tracked file in no area" areas \
  'mkdir scripts && echo 1 > scripts/run.py'

plant "a closed piece with no changelog entry" changelog.entry \
  ':' --closing 7

plant "a repeated paragraph" repeat \
  'p="To release the tool, first make sure the environment file holds the database address and the payment key. Then run the release script from the project root, wait for the health check to pass, and tell the team in the channel that the new version is live. If the health check fails, roll back to the previous release."
   printf "\n%s\n" "$p" >> AGENTS.md
   printf "\n%s\n" "$p" >> docs/README.md'

# A closed piece that has an entry passes.
clone="$TP_BASE/entry"
git clone -q "$TP_ROOT" "$clone"
printf '\n## 2026-10-06\n\n### Added\n\n- Refunds. ([piece 7](https://example.invalid/issues/7))\n' >> "$clone/CHANGELOG.md"
save "$clone" "An entry for piece 7"
run_check "$clone" --closing 7
[ "$code" = 0 ] || fail "a closed piece with an entry fails: $out"
ok "a closed piece with a changelog entry passes"

# --- the shipped checks.yml --------------------------------------------------

step_run() {
  # step_run <step name>: print the run block of that step in the shipped checks.yml.
  awk -v want="      - name: $1" '
    $0 == want { inside = 1; next }
    inside && /^      - / { exit }
    inside && /^        run: \|/ { block = 1; next }
    inside && block { sub(/^          /, ""); print }
  ' "$TEMPLATES/checks.yml"
}

grep -qi "ai.build.kit" "$TEMPLATES/checks.yml" && fail "checks.yml still names the old product"
ok "checks.yml names no old product"

records_step=$(step_run "Check the records")
[ -n "$records_step" ] || fail "checks.yml has no step named Check the records with a run block"
code=0
(cd "$TP_ROOT" && CLAUDE_PLUGIN_ROOT="$ROOT/kit" sh -c "$records_step") >/dev/null 2>&1 || code=$?
[ "$code" = 0 ] || fail "the Check the records step fails on the founded project (exit $code)"
ok "the Check the records step passes on the founded project"

code=0
(cd "$clone" && printf '\nRun `scripts/gone.sh`.\n' >> AGENTS.md &&
  CLAUDE_PLUGIN_ROOT="$ROOT/kit" sh -c "$records_step") >/dev/null 2>&1 || code=$?
[ "$code" = 1 ] || fail "the Check the records step passes on a project with a fault (exit $code)"
ok "the Check the records step fails on a project with a fault"

empty="$TP_BASE/empty-path"
mkdir -p "$empty"
code=0
said=$(cd "$TP_ROOT" && PATH="$empty" /bin/sh -c "$records_step" 2>&1) || code=$?
[ "$code" = 2 ] || fail "with no python3 the step should exit 2, got $code"
case "$said" in
  *"needs Python 3"*) ok "with no python3 the step says so and exits 2" ;;
  *) fail "with no python3 the step did not say it needs Python 3: $said" ;;
esac

test_step=$(step_run "Install and test")
[ -n "$test_step" ] || fail "checks.yml has no step named Install and test with a run block"
base=$(git -C "$TP_ROOT" rev-parse HEAD)
run_hosted() {
  code=0
  said=$(cd "$1" && CLAUDE_PLUGIN_ROOT="$ROOT/kit" PR_BASE_SHA="$base" \
    SCAFFOLD_TEST_COMMAND="${2:-}" sh -c "$test_step" 2>&1) || code=$?
}
run_hosted "$TP_ROOT"
[ "$code" = 0 ] || fail "F2-FOUND founding with no runner should pass: $said"
case "$said" in
  *"no project tests exist yet"*) ok "F2-FOUND founding says tests are unavailable" ;;
  *) fail "F2-FOUND founding must not claim project tests passed: $said" ;;
esac

bootstrap="$TP_BASE/bootstrap"
git clone -q "$TP_ROOT" "$bootstrap"
mkdir "$bootstrap/tests"
printf '#!/bin/sh\necho scaffold tests ran\n' > "$bootstrap/tests/run.sh"
save "$bootstrap" "Add the first test runner"
run_hosted "$bootstrap" "sh tests/run.sh"
[ "$code" = 0 ] || fail "F2-SCAFFOLD the scaffold command should run: $said"
case "$said" in
  *"scaffold tests ran"*) ok "F2-SCAFFOLD empty policy runs the scaffold judge" ;;
  *) fail "F2-SCAFFOLD no scaffold judge ran: $said" ;;
esac
run_hosted "$bootstrap" "exit 1"
[ "$code" = 1 ] || fail "F2-RED a failing scaffold command must fail: $said"
run_hosted "$bootstrap"
[ "$code" = 1 ] || fail "F2-MISSING a scaffold with no known command must fail: $said"
base=$(git -C "$bootstrap" rev-parse HEAD)
run_hosted "$bootstrap" "echo must not run"
[ "$code" = 1 ] || fail "F2-LATER a project with a runner requires policy test_command: $said"
case "$said" in
  *"no test_command"*) ok "F2-LATER existing projects keep the empty-policy refusal" ;;
  *) fail "F2-LATER the refusal must name test_command: $said" ;;
esac
base=$(git -C "$TP_ROOT" rev-parse HEAD)
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["test_command"] = "echo the tests ran"
json.dump(data, open(path, "w"))
PY
code=0
said=$(cd "$TP_ROOT" && CLAUDE_PLUGIN_ROOT="$ROOT/kit" sh -c "$test_step" 2>&1) || code=$?
[ "$code" = 0 ] || fail "with a test_command the test step should pass, got $code: $said"
case "$said" in
  *"the tests ran"*) ok "the test step runs the policy's test command" ;;
  *) fail "the test step did not run the test command: $said" ;;
esac

echo
echo "records-check.sh: all checks passed"
