#!/usr/bin/env sh
# pre-run-check.sh: take each guard away in turn, and require a refusal that names it.
#
# Each case builds a throwaway project with every guard in place (tests/lib/
# throwaway-project.sh), spoils one thing, and runs kit/scripts/pre-run-check.py.
# A refusal must exit 3, name the guard, and name the half of /setup that puts
# it back. With every guard in place the check passes. The computer's power,
# sleep, memory and disk, and the Claude Code version, come from the stand-ins
# in tests/stand-ins/fake-computer, never from this machine.
#
# Everything runs in throwaway folders. No network, no account, no model.

set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/kit/scripts/pre-run-check.py"
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

# shellcheck disable=SC1091
. "$ROOT/tests/lib/throwaway-project.sh"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

# json_get <json> <python expression over d>
json_get() {
  printf '%s' "$1" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$2" 2>/dev/null
}

# seal_kit: write the plugin's version record for the kit folder in $KIT.
seal_kit() {
  python3 - "$CHECK" "$KIT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("pre_run_check", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["pre_run_check"] = module
spec.loader.exec_module(module)
module.write_record(__import__("pathlib").Path(sys.argv[2]))
PY
}

# edit_json <file> <python statements over d>
edit_json() {
  python3 - "$1" "$2" <<'PY'
import json, sys
path, code = sys.argv[1:3]
with open(path) as handle:
    d = json.load(handle)
exec(code)
with open(path, "w") as handle:
    json.dump(d, handle, indent=2)
PY
}

set_env() {
  eval "$1=\$2"
  export "$1"
}

# build <founded|repo>: a project with every guard in place.
#   founded  the kit sits in a plugin folder with a version record, as installed
#   repo     the kit sits in the project's own kit/ folder, tracked by Git
build() {
  tp_new demo
  unset FAKE_COMPUTER_POWER FAKE_COMPUTER_SLEEP FAKE_COMPUTER_FREE_MB \
    FAKE_COMPUTER_DISK_GB FAKE_CLAUDE_VERSION ANTHROPIC_API_KEY
  PATH="$FAKE_COMPUTER:$PATH"
  # The copy of main that the check tests lands in the throwaway folder.
  mkdir -p "$TP_BASE/tmp"
  TMPDIR="$TP_BASE/tmp"
  export PATH TMPDIR
  if [ "$1" = repo ]; then
    cp -R "$ROOT/kit" "$TP_ROOT/kit"
    KIT="$TP_ROOT/kit"
    unset CLAUDE_PLUGIN_ROOT
    git -C "$TP_ROOT" add kit
    git -C "$TP_ROOT" commit -q -m "Add the kit"
    git -C "$TP_ROOT" push -q origin main
  else
    KIT="$TP_BASE/plugin"
    cp -R "$ROOT/kit" "$KIT"
    CLAUDE_PLUGIN_ROOT="$KIT"
    export CLAUDE_PLUGIN_ROOT
    seal_kit
  fi
  # Settings: the kit's template, merged as /setup merges it.
  python3 "$ROOT/kit/scripts/merge-settings.py" "$KIT/templates/claude-settings.json" \
    "$TP_ROOT/.claude/settings.json" --set "KIT_DIR=$KIT" >/dev/null 2>&1
  # The pre-push hook, and the setting that turns it on.
  mkdir -p "$TP_ROOT/.githooks"
  if [ "$1" = repo ]; then
    cp "$KIT/templates/githooks/pre-push" "$TP_ROOT/.githooks/pre-push"
  else
    # /setup renders the hook with the kit folder, as a founded project holds it.
    sed "s#{{KIT_DIR}}#$KIT#g" "$KIT/templates/githooks/pre-push" > "$TP_ROOT/.githooks/pre-push"
  fi
  chmod +x "$TP_ROOT/.githooks/pre-push"
  git -C "$TP_ROOT" config core.hooksPath .githooks
  # The policy, from the template, with a test command that passes.
  mkdir -p "$TP_ROOT/.agents/loop"
  cp "$KIT/templates/policy.json" "$TP_ROOT/.agents/loop/policy.json"
  edit_json "$TP_ROOT/.agents/loop/policy.json" 'd["test_command"] = "sh -c \"exit 0\""'
  POLICY="$TP_ROOT/.agents/loop/policy.json"
  SETTINGS="$TP_ROOT/.claude/settings.json"
}

run_check() {
  python3 "$CHECK" --project "$TP_ROOT" --json "$@" 2>"$TP_BASE/stderr"
}

# expect_refusal <description> <guard> <half: first|second|none> <text the output must hold>... -- <check arguments>
expect_refusal() {
  desc=$1 guard=$2 half=$3
  shift 3
  needles=""
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do
    needles="$needles
$1"
    shift
  done
  [ "${1:-}" = "--" ] && shift
  out=$(run_check "$@") && code=0 || code=$?
  if [ "$code" -ne 3 ]; then
    fail "$desc: expected a refusal (exit 3), got $code: $out"
    return
  fi
  if ! printf '%s' "$out" | grep -q "\"guard\": \"$guard\""; then
    fail "$desc: the refusal does not name the guard $guard: $out"
    return
  fi
  if [ "$half" != none ] && ! printf '%s' "$out" | grep -q "$half half of /setup"; then
    fail "$desc: the refusal does not name the $half half of /setup: $out"
    return
  fi
  if ! grep -q "^next:" "$TP_BASE/stderr"; then
    fail "$desc: the refusal prints no next: line"
    return
  fi
  printf '%s\n' "$needles" | while IFS= read -r needle; do
    [ -z "$needle" ] && continue
    printf '%s' "$out" | grep -qF -- "$needle" || {
      echo "FAIL: $desc: the refusal does not hold: $needle" >&2
      exit 1
    }
  done || { FAIL=1; return; }
  pass "$desc"
}

expect_pass() {
  desc=$1
  shift
  out=$(run_check "$@") && code=0 || code=$?
  if [ "$code" -eq 0 ] && [ "$(json_get "$out" 'd["ok"]')" = "True" ]; then
    pass "$desc"
  else
    fail "$desc: expected a pass, got $code: $out"
  fi
}

echo "== Every guard in place =="
build founded
expect_pass "a project with every guard in place passes"
[ "$(json_get "$out" 'd["notices"]')" = "[]" ] \
  && pass "it prints no notice when the App credential is there" \
  || fail "a notice was printed with every guard in place: $out"
expect_pass "an unattended run passes with the App credential" --unattended
expect_pass "a pre-approved merge passes with the App credential" --merge-pre-approved
python3 "$CHECK" --help 2>&1 | grep -q "exit codes" \
  && pass "--help names the exit codes" \
  || fail "--help does not name the exit codes"

echo "== The guard hook =="
build founded
edit_json "$KIT/hooks/hooks.json" 'd["hooks"].pop("PreToolUse")'
seal_kit
expect_refusal "the guard hook taken out of the hook list" guard-hook first "PreToolUse"

build founded
mv "$KIT/hooks/guard.py" "$KIT/hooks/guard.py.gone"
seal_kit
expect_refusal "the guard script missing" guard-hook first "guard.py"

echo "== The deny rules =="
build founded
edit_json "$SETTINGS" 'd["permissions"]["deny"].remove("Bash(rm -r:*)")'
expect_refusal "one deny rule taken away" deny-rule first "Bash(rm -r:*)"

build founded
edit_json "$SETTINGS" 'del d["permissions"]'
expect_refusal "every deny rule taken away" deny-rule first "Bash(git push --force:*)"

build founded
rm "$SETTINGS"
expect_refusal "no settings file at all" deny-rule first ".claude/settings.json"

echo "== The sandbox =="
build founded
edit_json "$SETTINGS" 'del d["sandbox"]'
expect_refusal "the sandbox taken away" sandbox first "sandbox"

build founded
edit_json "$SETTINGS" 'd["sandbox"]["enabled"] = False'
expect_refusal "a setting of the person's switches the sandbox off" sandbox first "sandbox.enabled"

build founded
edit_json "$SETTINGS" 'd["sandbox"]["allowUnsandboxedCommands"] = True'
expect_refusal "unsandboxed commands allowed" sandbox first "allowUnsandboxedCommands"

build founded
mkdir -p "$TP_ROOT/.claude"
printf '{"sandbox": {"enabled": false}}\n' > "$TP_ROOT/.claude/settings.local.json"
expect_refusal "the local settings switch the sandbox off" sandbox first "sandbox.enabled"

build founded
edit_json "$KIT/templates/builder-settings.json" 'd["sandbox"]["network"]["strictAllowlist"] = False'
seal_kit
expect_refusal "the builder network allowlist not strict" sandbox first "strictAllowlist"

echo "== Another guard value a person's setting beats =="
build founded
edit_json "$SETTINGS" 'd["permissions"]["disableBypassPermissionsMode"] = "allow"'
expect_refusal "bypass mode switched back on" setting-override first "disableBypassPermissionsMode"

echo "== The pre-push hook =="
build founded
rm "$TP_ROOT/.githooks/pre-push"
expect_refusal "the pre-push hook missing" pre-push-hook first ".githooks/pre-push"

build founded
git -C "$TP_ROOT" config --unset core.hooksPath
expect_refusal "the hook folder not switched on" pre-push-hook first "core.hooksPath"

build founded
printf '#!/usr/bin/env sh\nexit 0\n' > "$TP_ROOT/.githooks/pre-push"
expect_refusal "a pre-push hook that differs from the kit's" pre-push-hook first "differs"

build founded
cp "$KIT/templates/githooks/pre-push" "$TP_ROOT/.githooks/pre-push"
expect_refusal "the raw hook template in a founded project" pre-push-hook first "differs"

echo "== The installed kit folder =="
build founded
printf '\n# changed\n' >> "$KIT/scripts/secret-scan.py"
expect_refusal "a changed file in the installed kit folder" kit-folder first "scripts/secret-scan.py"

build founded
printf 'x\n' > "$KIT/scripts/extra.py"
expect_refusal "an added file in the installed kit folder" kit-folder first "scripts/extra.py"

build founded
rm "$KIT/version.json"
expect_refusal "no version record in the installed kit folder" kit-folder first "version.json"

build repo
expect_pass "in the kit's repository a clean kit/ folder passes"
printf '\n# changed\n' >> "$TP_ROOT/kit/scripts/secret-scan.py"
expect_refusal "a changed file under kit/ in a repository" kit-folder first "kit/scripts/secret-scan.py"

echo "== The policy =="
build founded
rm "$POLICY"
expect_refusal "a missing policy" policy first ".agents/loop/policy.json"

build founded
printf '{not json' > "$POLICY"
expect_refusal "a policy that is not JSON" policy first "not valid JSON"

build founded
edit_json "$POLICY" 'd["builder_cap"] = "three"'
expect_refusal "a malformed policy value is named by key" policy-value first "builder_cap"

build founded
edit_json "$POLICY" 'd["billing"] = {"mode": "free"}'
expect_refusal "a malformed nested value is named by key" policy-value first "billing.mode"

build founded
edit_json "$POLICY" 'd["merge_pre_approved"] = True'
expect_refusal "a pre-approval key in the policy" policy-value first "merge_pre_approved" "--merge-pre-approved"

echo "== The lock =="
build founded
sleep 30 &
holder=$!
mkdir -p "$TP_ROOT/.agents/runs/earlier"
printf '%s\n' "$holder" > "$TP_ROOT/.agents/runs/earlier/lock"
expect_refusal "a lock held by another run" lock none "earlier" "$holder" -- --run today
kill "$holder" 2>/dev/null
wait "$holder" 2>/dev/null

build founded
true &
gone=$!
wait "$gone"
mkdir -p "$TP_ROOT/.agents/runs/earlier"
printf '%s\n' "$gone" > "$TP_ROOT/.agents/runs/earlier/lock"
expect_pass "a lock left by a run that is no longer there does not stop a run" --run today

echo "== The computer =="
build founded
set_env FAKE_COMPUTER_POWER battery
expect_refusal "the computer on battery" battery none "battery"
set_env FAKE_COMPUTER_POWER ac
set_env FAKE_COMPUTER_SLEEP free
expect_refusal "sleep not held off" sleep none "caffeinate"
set_env FAKE_COMPUTER_SLEEP held
set_env FAKE_COMPUTER_FREE_MB 300
expect_refusal "too little free memory" memory none "300 MB"
set_env FAKE_COMPUTER_FREE_MB 8192
set_env FAKE_COMPUTER_DISK_GB 1
expect_refusal "low disk" disk none "1 GB"
set_env FAKE_COMPUTER_DISK_GB 100
set_env FAKE_CLAUDE_VERSION 2.1.218
expect_refusal "a Claude Code older than 2.1.219" claude-version none "2.1.219"
set_env FAKE_CLAUDE_VERSION not-a-version
expect_refusal "a Claude Code version nobody can read" claude-version none "not-a-version"
set_env FAKE_CLAUDE_VERSION 2.1.219
expect_pass "Claude Code 2.1.219 passes"
set_env FAKE_CLAUDE_VERSION 2.10.0
expect_pass "Claude Code 2.10.0 passes, as a number and not as text"
set_env FAKE_CLAUDE_VERSION 2.1.219
edit_json "$POLICY" 'd["min_free_memory_mb"] = 256'
set_env FAKE_COMPUTER_FREE_MB 300
expect_pass "the memory floor comes from the policy"

echo "== Main =="
build founded
printf 'red\n' > "$TP_ROOT/RED"
git -C "$TP_ROOT" add RED
git -C "$TP_ROOT" commit -q -m "Break main"
git -C "$TP_ROOT" push -q origin main
edit_json "$POLICY" 'd["test_command"] = "sh -c \"test ! -f RED\""'
expect_refusal "a red main" main none "RED" "test ! -f RED"

build founded
edit_json "$POLICY" 'd["test_command"] = "sh -c \"test ! -f RED\""'
printf 'red\n' > "$TP_ROOT/RED"
expect_pass "an unsaved change in the working folder is not part of main"

build founded
edit_json "$POLICY" 'd["test_command"] = ""'
expect_refusal "no test command in the policy" main none "test_command"

build founded
git -C "$TP_ROOT" branch -m main trunk
expect_refusal "no main branch" main none "main"

echo "== The GitHub App =="
build founded
mv "$TP_APP_KEY" "$TP_APP_KEY.away"
out=$(run_check) && code=0 || code=$?
if [ "$code" -eq 0 ] \
  && printf '%s' "$out" | grep -qF 'the second half of `/setup` is missing: the run stops if this computer sleeps or this session closes, and GitHub steps wait for you'; then
  pass "an attended local run passes with one notice naming the second half"
else
  fail "an attended run with no App credential: $code $out"
fi
[ "$(json_get "$out" 'len(d["notices"])')" = "1" ] \
  && pass "it prints one notice, not more" \
  || fail "the notice count is not one: $out"
expect_refusal "an unattended run with no App credential" app-key second "second half" -- --unattended
expect_refusal "a pre-approved merge with no App credential" app-key second "second half" -- --merge-pre-approved

build founded
chmod 644 "$TP_APP_KEY"
expect_refusal "an App key other users can read" app-key second "other users" -- --unattended

build founded
chmod 644 "$TP_APP_KEY"
expect_refusal "an App key other users can read stops an attended run too" app-key second "other users"

build founded
inside="$TP_ROOT/.local-data"
mkdir -p "$inside"
keypath=$(AI_LOOP_KIT_DATA="$inside" PYTHONPATH="$ROOT/kit/scripts" python3 -c '
import sys
from pathlib import Path
from loop.paths import Paths
print(Paths.for_project(Path(sys.argv[1])).app_key_file)' "$TP_ROOT")
mkdir -p "$(dirname -- "$keypath")"
cp "$TP_APP_KEY" "$keypath"
chmod 600 "$keypath"
set_env AI_LOOP_KIT_DATA "$inside"
expect_refusal "an App key inside the project" app-key second "inside the project"

echo "== An API key =="
build founded
edit_json "$POLICY" 'd["billing"] = {"mode": "api_key"}'
expect_refusal "an API key with no spend caps" api-spend-cap second "spend_cap_per_run_usd"

build founded
edit_json "$POLICY" 'd["billing"] = {"mode": "api_key", "spend_cap_per_piece_usd": 5, "spend_cap_per_run_usd": 20}'
expect_pass "an API key with both spend caps passes"

build founded
set_env ANTHROPIC_API_KEY "sk-ant-stand-in-value-0001"
expect_refusal "an API key in the environment with no spend caps" api-spend-cap second "spend caps"
[ -n "$out" ] && printf '%s' "$out" | grep -q "sk-ant-stand-in-value-0001" \
  && fail "the refusal printed the API key" \
  || pass "the refusal never prints the key"
edit_json "$POLICY" 'd["billing"] = {"mode": "api_key", "spend_cap_per_piece_usd": 5, "spend_cap_per_run_usd": 20}'
expect_pass "an API key in the environment with caps in the policy passes"
unset ANTHROPIC_API_KEY

echo "== The kit's own repository =="
build founded
git -C "$TP_ROOT" remote set-url origin "https://github.com/gwpicard/ai-loop-kit.git"
expect_refusal "origin set to the kit's own repository" kit-repository first "gwpicard/ai-loop-kit"

echo "== Every refusal is reported at once =="
build founded
edit_json "$SETTINGS" 'del d["sandbox"]'
rm "$POLICY"
set_env FAKE_COMPUTER_POWER battery
out=$(run_check) && code=0 || code=$?
for guard in sandbox policy battery; do
  printf '%s' "$out" | grep -q "\"guard\": \"$guard\"" \
    && pass "a run with three faults names $guard" \
    || fail "a run with three faults left out $guard: $out"
done

echo "== Not a project =="
elsewhere=$(mktemp -d)
out=$(cd "$elsewhere" && python3 "$CHECK" --json 2>"$TP_BASE/stderr") && code=0 || code=$?
[ "$code" -ne 0 ] && grep -q "^next:" "$TP_BASE/stderr" \
  && pass "a folder that is not a project is refused with a next: line" \
  || fail "a folder that is not a project: $code"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "pre-run-check.sh: all checks passed"
else
  echo "pre-run-check.sh: FAILED" >&2
fi
exit "$FAIL"
