#!/usr/bin/env sh
# setup-first-half.sh: drive kit/scripts/setup.py, the steps behind the first half of /setup.
#
# The skill is a conversation and needs a model, so its scenario evals sit in
# kit/skills/setup/evals/ and run by hand. This check holds what a script can hold,
# on an empty throwaway project and on one with code, settings and an AGENTS.md:
#
# - nothing is overwritten, and the person's settings rules stay;
# - the foundation files, the hooks, the ignore file, the allowlist and the policy;
# - no App step, and no GitHub write before the App exists;
# - the stops: a missing tool, no origin, and the kit's own repository;
# - spend caps on an API key, and the free-plan warning;
# - the pre-run check: attended passes with a notice, unattended and
#   pre-approved merge refuse.
#
# The kit runs from a plugin folder outside the project, as it does once
# installed. No network, no GitHub account and no model. Run it alone:
# tests/setup-first-half.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SETUP_SRC="$ROOT/kit/scripts/setup.py"
SKILL="$ROOT/kit/skills/setup/SKILL.md"
PRC="$ROOT/kit/scripts/pre-run-check.py"
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
ok() {
  echo "  ok: $1"
}

[ -f "$SETUP_SRC" ] || { echo "FAIL: missing $SETUP_SRC" >&2; exit 1; }
[ -f "$SKILL" ] || { echo "FAIL: missing $SKILL" >&2; exit 1; }

# shellcheck disable=SC1091
. "$ROOT/tests/lib/throwaway-project.sh"
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_PLUGIN_ROOT ANTHROPIC_API_KEY 2>/dev/null || true

# js <json> <python expression over d>
js() {
  printf '%s' "$1" | python3 -c 'import json,sys; d=json.load(sys.stdin); v=eval(sys.argv[1]); print(v if isinstance(v,str) else json.dumps(v,sort_keys=True))' "$2" 2>/dev/null
}

# snap <folder>: a list of every file with its hash, outside .git.
snap() {
  (cd "$1" && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort | while read -r f; do
    printf '%s %s\n' "$(shasum "$f" | cut -d' ' -f1)" "$f"
  done)
}

# new_project <name>: a throwaway project, the kit in a plugin folder beside it,
# and a data folder with no App key in it.
new_project() {
  tp_new "$1"
  KIT="$TP_BASE/plugin"
  cp -R "$ROOT/kit" "$KIT"
  TP_DATA2="$TP_BASE/data-no-app"
  mkdir -p "$TP_DATA2"
  AI_LOOP_KIT_DATA="$TP_DATA2"
  export AI_LOOP_KIT_DATA
  PATH="$FAKE_COMPUTER:$PATH"
  mkdir -p "$TP_BASE/tmp"
  TMPDIR="$TP_BASE/tmp"
  export PATH TMPDIR
  : > "$FAKE_GH_LOG"
}

# run_setup <arguments>: run the script from the plugin folder, in the project.
# The output goes to $OUT, the error text to $ERR, and the code to $CODE.
run_setup() {
  OUT="$TP_BASE/out.json"
  ERR="$TP_BASE/err.txt"
  set +e
  (cd "$TP_ROOT" && python3 "$KIT/scripts/setup.py" --json "$@") > "$OUT" 2> "$ERR"
  CODE=$?
  set -e
}

# The person publishes preparation only on the local origin and GitHub stand-in.
prepare_foundation() {
  (cd "$TP_ROOT"
    git checkout -q -b "$1"
    git add -A
    git commit -qm 'Prepare the foundation and its scaffold command'
    git push -q origin "$1"
    pr=$(gh pr create --base main --head "$1" --title 'Prepare the foundation' --body 'Person preparation.')
    gh pr merge "${pr##*/}" --merge --match-head-commit "$(git rev-parse HEAD)" >/dev/null
    git fetch -q origin main
    git checkout -q main
    git merge -q --ff-only origin/main
  )
}

echo "First half of /setup:"

# --- the script follows the contract ----------------------------------------------

python3 "$SETUP_SRC" --help | grep -q 'exit codes' || fail "setup.py --help names no exit codes"
python3 "$SETUP_SRC" found --help | grep -q -- '--dry-run' || fail "found --help has no --dry-run"
head -4 "$SETUP_SRC" | grep -q 'contract: agent' || fail "setup.py is not marked contract: agent"
head -4 "$SETUP_SRC" | grep -q 'contract: changes-state' || fail "setup.py is not marked contract: changes-state"
ok "setup.py has --help, --dry-run and its contract marks"

# --- the empty project --------------------------------------------------------------

new_project empty
BEFORE=$(snap "$TP_ROOT")

# The edge case: a missing tool stops everything and writes nothing.
LIM="$TP_BASE/limited-bin"
mkdir -p "$LIM"
for t in git python3 sh; do ln -s "$(command -v $t)" "$LIM/$t"; done
set +e
(cd "$TP_ROOT" && PATH="$LIM" python3 "$SETUP_SRC" found --json) > "$TP_BASE/o" 2> "$TP_BASE/e"
CODE=$?
set -e
[ "$CODE" -eq 4 ] || fail "a missing tool did not stop with exit 4 (got $CODE)"
grep -q '^next:' "$TP_BASE/e" || fail "the missing-tool stop has no next: line"
grep -qi 'openssl' "$TP_BASE/e" || fail "the missing-tool stop does not name the tool"
[ "$(snap "$TP_ROOT")" = "$BEFORE" ] || fail "a missing tool did not stop before writing"
[ ! -d "$TP_ROOT/.claude" ] || fail "a missing tool still wrote settings"
ok "a missing tool stops with the install line and writes nothing"

# The refusal case: origin is the kit's own repository.
git -C "$TP_ROOT" remote set-url origin "https://github.com/gwpicard/ai-loop-kit.git"
run_setup found
[ "$CODE" -eq 3 ] || fail "the kit's own repository was not refused with exit 3 (got $CODE)"
grep -q '^next:' "$ERR" || fail "the kit-repository refusal has no next: line"
[ "$(snap "$TP_ROOT")" = "$BEFORE" ] || fail "the kit-repository refusal wrote files"
[ ! -s "$FAKE_GH_LOG" ] || fail "the kit-repository refusal called gh"
[ "$(git -C "$TP_ROOT" remote get-url origin)" = "https://github.com/gwpicard/ai-loop-kit.git" ] \
  || fail "the skill changed origin"
ok "the kit's own repository is refused: no file, no gh call, no change to origin"

# A name that only starts like the kit's is not the kit: the rule is the exact name.
git -C "$TP_ROOT" remote set-url origin "https://github.com/gwpicard/ai-loop-kit-demo.git"
run_setup found --dry-run
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "gwpicard/ai-loop-kit-demo was refused as the kit's own repository (got $CODE)"; }
ok "a repository named like the kit, but not the kit, is not refused"
git -C "$TP_ROOT" remote set-url origin "https://github.com/gwpicard/ai-loop-kit.git"

# No origin at all.
git -C "$TP_ROOT" remote remove origin
run_setup found
[ "$CODE" -eq 3 ] || fail "no origin was not refused with exit 3 (got $CODE)"
grep -q '^next:.*remote add origin' "$ERR" || fail "the no-origin stop does not name the command"
[ "$(snap "$TP_ROOT")" = "$BEFORE" ] || fail "the no-origin stop wrote files"
ok "no origin stops with a next: line"
git -C "$TP_ROOT" remote add origin "$TP_BASE/origin.git"

# A dry run changes nothing.
run_setup found --dry-run
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "found --dry-run failed (got $CODE)"; }
[ "$(snap "$TP_ROOT")" = "$BEFORE" ] || fail "--dry-run wrote files"
[ "$(js "$(cat "$OUT")" 'd["dry_run"]')" = "true" ] || fail "--dry-run does not say it was a dry run"
[ "$(js "$(cat "$OUT")" '"AGENTS.md" in d["created"]')" = "true" ] || fail "--dry-run does not list AGENTS.md"
[ ! -e "$KIT/version.json" ] || fail "--dry-run wrote the version record"
ok "--dry-run lists what it would write and writes nothing"

# The real run, with a test command so the pre-run check can pass later.
run_setup found --test-command "sh -c 'exit 0'" --billing-mode subscription \
  --repo-visibility private --plan paid --language node
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "found failed (got $CODE)"; }
FOUND=$(cat "$OUT")
for f in AGENTS.md CLAUDE.md docs/overview.md docs/README.md docs/area-map CHANGELOG.md \
  .github/workflows/checks.yml .gitignore .claude/settings.json .githooks/pre-push \
  .agents/guard/blocked-commands.md .agents/loop/policy.json .agents/loop/network-allowlist.json; do
  [ -f "$TP_ROOT/$f" ] || fail "found did not write $f"
done
ok "the foundation files are written"

# No placeholder is left in any written file.
if grep -rlE '\{\{[A-Z_]+\}\}' "$TP_ROOT" --exclude-dir=.git >/dev/null 2>&1; then
  grep -rnE '\{\{[A-Z_]+\}\}' "$TP_ROOT" --exclude-dir=.git | head -3 >&2
  fail "a placeholder is left unfilled in a founded project"
fi
grep -q "$KIT/scripts/records-check.py" "$TP_ROOT/AGENTS.md" || fail "AGENTS.md has no absolute kit path"
[ ! -e "$TP_ROOT/kit" ] || fail "a copy of the kit was placed inside the project"
grep -q 'ref: "' "$TP_ROOT/.github/workflows/checks.yml" || fail "checks.yml has no ref"
ok "no placeholder is left, the kit paths are absolute and the kit is not copied in"
python3 - "$TP_ROOT/.github/workflows/checks.yml" <<'PYTEST' || fail "F2-RENDER the scaffold command was not rendered"
import json, sys
line = next(line for line in open(sys.argv[1]) if "SCAFFOLD_TEST_COMMAND:" in line)
assert json.loads(line.split(":", 1)[1]) == "sh -c 'exit 0'", "F2-RENDER"
PYTEST
ok "F2-RENDER founding records the scaffold command without filling the policy"


# Settings: the template merged, the hook wired with an absolute path.
python3 - "$TP_ROOT/.claude/settings.json" "$KIT" <<'PY' || fail "the settings are not what the template says"
import json, sys
s = json.load(open(sys.argv[1]))
kit = sys.argv[2]
assert s["sandbox"]["enabled"] is True
assert "Bash(git push -f:*)" in s["permissions"]["deny"]
cmd = json.dumps(s["hooks"]["SessionStart"])
assert kit + "/scripts/session-start.sh" in cmd, cmd
PY
ok "the settings wire the session-start hook and carry the guards"

# The pre-push hook is installed, runs, and Git is told to use it.
RENDERED_HOOK="$TP_BASE/hook-rendered"
python3 - "$KIT/templates/githooks/pre-push" "$(cd "$KIT" && pwd -P)" "$RENDERED_HOOK" <<'PY'
import sys
text = open(sys.argv[1]).read().replace("{{KIT_DIR}}", sys.argv[2])
open(sys.argv[3], "w").write(text)
PY
cmp -s "$TP_ROOT/.githooks/pre-push" "$RENDERED_HOOK" || fail "the pre-push hook differs from the template rendered with the kit folder"
grep -q '{{' "$TP_ROOT/.githooks/pre-push" && fail "the pre-push hook keeps a placeholder"
[ -x "$TP_ROOT/.githooks/pre-push" ] || fail "the pre-push hook is not executable"
[ "$(git -C "$TP_ROOT" config --get core.hooksPath)" = ".githooks" ] || fail "core.hooksPath is not .githooks"
ok "the pre-push hook is installed and switched on"

# The version record for a plugin install (P13).
[ -f "$KIT/version.json" ] || fail "setup did not write the plugin's version record"
ok "the plugin's version record is written"

# The ignore file covers what it must.
for p in .agents/runs/a/run.json .agents/pieces/1/evidence.jsonl debug.log .agents/worktrees/p1/x \
  .claude/settings.local.json .agents/loop/local.json; do
  git -C "$TP_ROOT" check-ignore -q "$p" || fail "the ignore file does not cover $p"
done
if git -C "$TP_ROOT" check-ignore -q .agents/loop/policy.json; then fail "the ignore file hides the policy"; fi
ok "the ignore file covers the run folder, piece records, logs, worktrees and local settings"

# The allowlist, for the language, with no GitHub host.
python3 - "$TP_ROOT/.agents/loop/network-allowlist.json" <<'PY' || fail "the allowlist is wrong"
import json, sys
a = json.load(open(sys.argv[1]))
assert a["language"] == "node", a
assert "registry.npmjs.org" in a["allowedDomains"], a
assert not any("github" in h for h in a["allowedDomains"]), a
PY
for f in "$ROOT"/kit/templates/network-allowlist/*.txt; do
  if grep -qi 'github' "$f" | grep -v '^#'; then :; fi
  if grep -v '^#' "$f" | grep -qi 'github'; then fail "$f names a GitHub host"; fi
done
ok "the allowlist suits the language and holds no GitHub host"

# The policy.
python3 - "$ROOT/kit/scripts" "$TP_ROOT/.agents/loop/policy.json" <<'PY' || fail "the policy is not valid"
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from loop import policy
data = policy.load(Path(sys.argv[2]))
assert data["test_command"] == "", data["test_command"]
PY
ok "the policy is written and valid, and keeps test_command empty while there is no test runner"

# No App step.
[ ! -e "$TP_DATA2/app-key.pem" ] || fail "a key file was written"
if find "$TP_DATA2" -name '*.pem' | grep -q .; then fail "a key file was written"; fi
[ ! -e "$TP_ROOT/.agents/loop/local.json" ] || fail "local settings were written before the App exists"
if grep -rIl 'key_file\|github_app\|app-key' "$TP_ROOT" --exclude-dir=.git | grep -q .; then
  fail "an App key path or setting is stored in the project"
fi
if grep -qiE 'settings/apps|manifest|app-key|new GitHub App' "$SKILL" "$ROOT"/kit/skills/setup/references/*.md; then
  fail "the skill shows the App manifest link or key step"
fi
if grep -qiE 'settings/apps|manifest|app-key' "$OUT"; then fail "the script shows the App manifest link"; fi
[ "$(js "$FOUND" '"second half of /setup" in d["closing"]')" = "true" ] || fail "the closing message does not name the second half of /setup"
grep -q 'second half of `/setup`' "$SKILL" || fail "the skill does not say the App comes in the second half"
ok "no App step: no link, no key file, no key path, and the closing names the second half"

# The gate's next: line for the labels is given. No label file is written: nothing reads one.
[ ! -e "$TP_ROOT/.agents/tmp/labels.txt" ] || fail "an unread label file was written"
js "$FOUND" 'd["labels"]["next"]' | grep -q 'gate.py sync' || fail "the label next: line does not name the sync command"
js "$FOUND" 'd["labels"]["names"]' | grep -q 'state:shaping' || fail "the label names lack the gate's labels"
ok "the label names and their next: line are given, and no label file is written"

# A second run changes nothing.
AFTER=$(snap "$TP_ROOT")
run_setup found --test-command "sh -c 'exit 0'" --billing-mode subscription \
  --repo-visibility private --plan paid --language node
[ "$CODE" -eq 0 ] || fail "the second run failed"
[ "$(snap "$TP_ROOT")" = "$AFTER" ] || fail "the second run changed a file"
[ "$(js "$(cat "$OUT")" 'd["created"]')" = "[]" ] || fail "the second run created files"
ok "a second run changes nothing"

# The person commits and merges the foundation before the piece gets its own branch.
prepare_foundation founding
: > "$FAKE_GH_LOG"

# The first piece, captured locally on the quick path.
run_setup first-piece --test-command "sh -c 'exit 0'"
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "first-piece failed (got $CODE)"; }
N=$(js "$(cat "$OUT")" 'd["piece"]')
[ -n "$N" ] || fail "first-piece printed no piece number"
SHOWN=$(cd "$TP_ROOT" && python3 "$KIT/scripts/spec.py" show "$N" --json 2>/dev/null || true)
[ "$(js "$SHOWN" 'd.get("found")')" = "true" ] || fail "the first piece has no spec block"
[ "$(js "$SHOWN" 'd.get("path")')" = "quick" ] || fail "the first piece is not on the quick path"
(cd "$TP_ROOT" && python3 "$KIT/scripts/spec.py" lint "$N" >/dev/null 2>&1) || fail "the first piece's spec does not lint"
run_setup first-piece --test-command "sh -c 'exit 0'"
[ "$(js "$(cat "$OUT")" 'd["captured"]')" = "false" ] || fail "a second first-piece captured another piece"
[ ! -s "$FAKE_GH_LOG" ] || fail "first-piece called gh"
[ "$(js "$SHOWN" 'd["judge"]["kind"]')" = "scaffold" ] || fail "the first piece's Kind is not scaffold"
[ "$(js "$SHOWN" 'len(d.get("must_stay_checks") or [])')" -ge 1 ] 2>/dev/null || fail "the first piece's Check: line is not found by the parser"
ok "the first piece is captured locally, once, on the quick path, as a scaffold with a Check: line"

# The first piece reaches ready in an empty project, with no test runner. The gate says
# so itself: only a quick-path scaffold piece may. The policy stays free of a command.
set +e
(cd "$TP_ROOT" && python3 "$KIT/scripts/gate.py" move "$N" ready --json) > "$TP_BASE/ready.out" 2> "$TP_BASE/ready.err"
READY=$?
set -e
if [ "$READY" -ne 0 ]; then cat "$TP_BASE/ready.out" "$TP_BASE/ready.err" >&2; fi
[ "$READY" -eq 0 ] || fail "the gate did not move the first piece to ready in an empty project (got $READY)"
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY' || fail "the first piece wrote its command into the policy"
import json, sys
assert json.load(open(sys.argv[1]))["test_command"] == ""
PY
ok "the first piece reaches ready in an empty project, and the policy still has no test command"

# The scaffold piece's own change sets the policy. Here the test does it by hand.
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["test_command"] = "sh -c 'exit 0'"
open(p, "w").write(json.dumps(d, indent=2) + "\n")
PY

# GitHub steps with no App.
: > "$FAKE_GH_LOG"
GH_STATE_BEFORE=$(cat "$FAKE_GH_STATE" 2>/dev/null || true)
run_setup github labels
[ "$CODE" -eq 3 ] || fail "creating labels with no App did not exit 3 (got $CODE)"
grep -q '^next:.*gate.py sync' "$ERR" || fail "the labels step has no next: line naming the command"
printf 'The idea.\n' > "$TP_BASE/body.md"
run_setup github issue --title "Export invoices" --body-file "$TP_BASE/body.md"
grep -q 'gate.py sync' "$ERR" "$OUT" || fail "the issue step has no next: line naming the command"
[ ! -s "$FAKE_GH_LOG" ] || { cat "$FAKE_GH_LOG" >&2; fail "a GitHub step called gh"; }
[ "$(cat "$FAKE_GH_STATE" 2>/dev/null || true)" = "$GH_STATE_BEFORE" ] || fail "a GitHub step changed GitHub"
ok "a GitHub step with no App changes nothing on GitHub and names the command to run"

# The pre-run check.
git -C "$TP_ROOT" add -A
git -C "$TP_ROOT" commit -q -m "Found the project"
CLAUDE_PLUGIN_ROOT="$KIT"
export CLAUDE_PLUGIN_ROOT
prc() {
  set +e
  python3 "$PRC" --project "$TP_ROOT" --json "$@" > "$TP_BASE/prc.out" 2> "$TP_BASE/prc.err"
  PRC_CODE=$?
  set -e
}
prc
if [ "$PRC_CODE" -ne 0 ]; then cat "$TP_BASE/prc.out" "$TP_BASE/prc.err" >&2; fi
[ "$PRC_CODE" -eq 0 ] || fail "the pre-run check refused an attended run with no App (got $PRC_CODE)"
grep -qi 'second half' "$TP_BASE/prc.out" || fail "the pre-run check gave no notice that the second half of /setup is missing"
prc --unattended
[ "$PRC_CODE" -eq 3 ] || fail "an unattended run was not refused"
grep -qi 'second half' "$TP_BASE/prc.out" "$TP_BASE/prc.err" || fail "the unattended refusal does not name the second half"
prc --merge-pre-approved
[ "$PRC_CODE" -eq 3 ] || fail "a pre-approved merge was not refused"
ok "the pre-run check passes attended with a notice, and refuses unattended and pre-approved runs"

# A real push from the founded project, with the kit in a plugin folder outside it, passes
# the secret scan the hook finds there.
git -C "$TP_ROOT" checkout -q -b probe
set +e
git -C "$TP_ROOT" push origin probe > "$TP_BASE/push.out" 2>&1
PUSH=$?
set -e
if [ "$PUSH" -ne 0 ]; then cat "$TP_BASE/push.out" >&2; fi
[ "$PUSH" -eq 0 ] || fail "a real git push from the founded project was stopped (got $PUSH)"
git -C "$TP_BASE/origin.git" rev-parse -q --verify refs/heads/probe >/dev/null || fail "the push did not arrive at the remote"
git -C "$TP_ROOT" checkout -q main
ok "a real git push from the founded project passes the secret scan the hook finds in the plugin folder"

# A scan written into the project cannot stand in for the kit's.
git -C "$TP_ROOT" checkout -q -b leak
printf 'ghp_%s\n' "$(printf 'a%.0s' $(seq 1 36))" > "$TP_ROOT/creds.txt"
git -C "$TP_ROOT" add creds.txt
git -C "$TP_ROOT" commit -q -m "a secret"
mkdir -p "$TP_ROOT/kit/scripts"
printf 'import sys\nsys.exit(0)\n' > "$TP_ROOT/kit/scripts/secret-scan.py"
set +e
git -C "$TP_ROOT" push origin leak > "$TP_BASE/leak.out" 2>&1
LEAK=$?
set -e
LEAK_ARRIVED=no
git -C "$TP_BASE/origin.git" rev-parse -q --verify refs/heads/leak >/dev/null && LEAK_ARRIVED=yes
git -C "$TP_ROOT" checkout -q main
# Clean up the two named files, so the later steps see a clean project.
[ ! -e "$TP_ROOT/creds.txt" ] || rm "$TP_ROOT/creds.txt"
rm "$TP_ROOT/kit/scripts/secret-scan.py"
rmdir "$TP_ROOT/kit/scripts" "$TP_ROOT/kit"
[ "$LEAK" -ne 0 ] || fail "a scan written into the project let a secret through"
[ "$LEAK_ARRIVED" = no ] || fail "the secret arrived at the remote"
ok "a scan written into the project cannot stand in for the kit's"

# The raw template is not the hook of a founded project (the kit is outside it).
cp "$TP_ROOT/.githooks/pre-push" "$TP_BASE/hook-keep"
cp "$KIT/templates/githooks/pre-push" "$TP_ROOT/.githooks/pre-push"
prc
cp "$TP_BASE/hook-keep" "$TP_ROOT/.githooks/pre-push"
[ "$PRC_CODE" -ne 0 ] || fail "the pre-run check accepted the raw hook template in a founded project"
grep -q 'pre-push-hook' "$TP_BASE/prc.out" "$TP_BASE/prc.err" || fail "the refusal does not name the pre-push hook"
prc
[ "$PRC_CODE" -eq 0 ] || fail "the pre-run check refused the rendered hook after the restore (got $PRC_CODE)"
ok "the pre-run check refuses the raw hook template in a founded project"

# The hook still fails closed when the scan is truly missing.
mkdir -p "$TP_BASE/lonely" "$TP_BASE/nohome"
sed "s#{{KIT_DIR}}#$TP_BASE/nowhere#" "$KIT/templates/githooks/pre-push" > "$TP_BASE/lonely/pre-push"
set +e
(cd "$TP_ROOT" && HOME="$TP_BASE/nohome" sh "$TP_BASE/lonely/pre-push" origin x \
  < /dev/null) > "$TP_BASE/lonely.out" 2> "$TP_BASE/lonely.err"
LONELY=$?
set -e
[ "$LONELY" -eq 1 ] || fail "the hook did not fail closed with no scan (got $LONELY)"
grep -q 'cannot find secret-scan.py' "$TP_BASE/lonely.err" || fail "the hook gave no reason when the scan is missing"
ok "the hook fails closed when the scan is missing"
unset CLAUDE_PLUGIN_ROOT

# --- spend caps and the free-plan warning ------------------------------------------

new_project billing
run_setup found --billing-mode api_key --repo-visibility private --plan free --language python
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "found with an API key failed"; }
B=$(cat "$OUT")
js "$B" 'd["asks"]' | grep -q 'spend_cap_per_piece_usd' || fail "no spend cap was asked for on an API key"
js "$B" 'd["asks"]' | grep -q 'spend_cap_per_run_usd' || fail "no run spend cap was asked for on an API key"
js "$B" 'd["warnings"]' | grep -qi 'free' || fail "no free-plan warning on a private free repository"
js "$B" 'd["warnings"]' | grep -qi 'server-side' || fail "the free-plan warning does not say there are no server-side rules"
ok "spend caps are asked for on an API key, and the free-plan warning is given"
run_setup found --billing-mode api_key --spend-cap-piece 5 --spend-cap-run 20 --plan free --repo-visibility public
[ "$(js "$(cat "$OUT")" 'd["asks"]')" = "[]" ] || fail "caps were asked for after they were given"
[ "$(js "$(cat "$OUT")" 'd["warnings"]')" = "[]" ] || fail "a public repository got the free-plan warning"
ok "no question and no warning when the caps are given and the repository is public"

# --- a project with code, settings, an AGENTS.md and a hook ------------------------

new_project existing
cd "$TP_ROOT"
mkdir -p src .claude .githooks
printf '{"name":"demo","version":"1.0.0"}\n' > package.json
printf 'console.log(1)\n' > src/index.js
printf '# Mine\n\nMy own rules.\n' > AGENTS.md
printf 'build/\n.env\n' > .gitignore
printf '#!/bin/sh\necho mine\n' > .githooks/pre-push
chmod +x .githooks/pre-push
printf '{"permissions":{"deny":["Bash(curl:*)"],"allow":["Bash(npm test:*)"]},"model":"mine"}\n' > .claude/settings.json
git add -A
git commit -q -m "Existing code"
cd "$ROOT"
PRE=$(snap "$TP_ROOT")
run_setup found
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "found on an existing project failed"; }
E=$(cat "$OUT")
[ "$(cat "$TP_ROOT/AGENTS.md")" = "$(printf '# Mine\n\nMy own rules.\n')" ] || fail "an existing AGENTS.md was changed"
[ "$(cat "$TP_ROOT/.githooks/pre-push")" = "$(printf '#!/bin/sh\necho mine\n')" ] || fail "an existing pre-push hook was overwritten"
js "$E" '"AGENTS.md" in d["kept"]' | grep -q true || fail "AGENTS.md is not reported as kept"
js "$E" '".githooks/pre-push" in d["kept"]' | grep -q true || fail "the existing hook is not reported as kept"
grep -q 'next:' "$TP_BASE/err.txt" 2>/dev/null || true
python3 - "$TP_ROOT/.claude/settings.json" <<'PY' || fail "the person's settings were not kept"
import json, sys
s = json.load(open(sys.argv[1]))
assert "Bash(curl:*)" in s["permissions"]["deny"]
assert s["permissions"]["allow"] == ["Bash(npm test:*)"]
assert s["model"] == "mine"
assert "Bash(git push -f:*)" in s["permissions"]["deny"]
assert s["sandbox"]["enabled"] is True
PY
head -2 "$TP_ROOT/.gitignore" | grep -q '^build/$' || fail "the person's ignore lines moved"
grep -q '^build/$' "$TP_ROOT/.gitignore" && grep -q '^\.env$' "$TP_ROOT/.gitignore" || fail "the person's ignore lines were lost"
git -C "$TP_ROOT" check-ignore -q .agents/runs/x || fail "the existing ignore file was not extended"
python3 - "$TP_ROOT/.agents/loop/network-allowlist.json" <<'PY' || fail "the language was not detected from package.json"
import json, sys
assert json.load(open(sys.argv[1]))["language"] == "node"
PY
[ -f "$TP_ROOT/src/index.js" ] && [ "$(cat "$TP_ROOT/src/index.js")" = "console.log(1)" ] || fail "existing code changed"
ok "existing files are kept, the person's rules stay, and the language is detected"

# An open question is written, not a stop, when a nice-to-have answer is missing.
new_project unknown
run_setup found
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "founding stopped on an unknown language"; }
[ -f "$TP_ROOT/docs/open-questions.md" ] || fail "an unknown language wrote no open question"
grep -qi 'language' "$TP_ROOT/docs/open-questions.md" || fail "the open question does not name the language"
ok "an unanswered nice-to-have becomes an open question, never a stop"

# No test command and no language: first-piece stops and asks for --test-command.
BEFORE_FP=$(snap "$TP_ROOT")
run_setup first-piece
[ "$CODE" -eq 3 ] || fail "first-piece with no known test command did not stop with exit 3 (got $CODE)"
grep -q '^next:.*--test-command' "$ERR" || fail "the first-piece stop does not ask for --test-command"
grep -qi 'every test' "$TP_ROOT/docs/open-questions.md" || fail "no open question names the test command"
[ ! -d "$TP_ROOT/.agents/pieces" ] || fail "first-piece captured a piece with no command"
ok "first-piece with no known command writes an open question and stops with a next: line"
run_setup first-piece --test-command "make check"
[ "$CODE" -eq 3 ] || fail "F2-UNKNOWN a chosen command without committed preparation was accepted"
prepare_foundation unknown-command
run_setup first-piece --test-command "make check"
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "first-piece with --test-command failed"; }
grep -rq 'Command: make check' "$TP_ROOT/.agents" || fail "the command did not reach the first piece"
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY' || fail "first-piece wrote the command into the policy"
import json, sys
assert json.load(open(sys.argv[1]))["test_command"] == ""
PY
ok "--test-command is carried as the first piece's Command, not as the policy's"


# The scaffold command can be chosen after founding, including an unknown language.
python3 - "$TP_ROOT/.github/workflows/checks.yml" <<'PYTEST' || fail "F2-AGREED unknown-language scaffold command differs from hosted command"
import json, sys
line = next(line for line in open(sys.argv[1]) if "SCAFFOLD_TEST_COMMAND:" in line)
assert json.loads(line.split(":", 1)[1]) == "make check", "F2-AGREED"
PYTEST
ok "F2-AGREED an unknown-language scaffold uses the agreed hosted command"

new_project custom-bootstrap
run_setup found --language python
[ "$CODE" -eq 0 ] || fail "F2-CUSTOM founding failed"
printf '\n# The person added this before capturing the scaffold.\n' >> "$TP_ROOT/.github/workflows/checks.yml"
before_workflow=$(shasum "$TP_ROOT/.github/workflows/checks.yml")
run_setup first-piece --dry-run --test-command "sh tests/run.sh"
[ "$CODE" -eq 3 ] || fail "F2-DRY first-piece dry run should report missing preparation"
[ "$(shasum "$TP_ROOT/.github/workflows/checks.yml")" = "$before_workflow" ] \
  || fail "F2-DRY first-piece dry run changed the workflow"
run_setup first-piece --test-command "sh tests/run.sh"
[ "$CODE" -eq 3 ] || fail "F2-CUSTOM capture did not require person preparation"
prepare_foundation custom-command
run_setup first-piece --test-command "sh tests/run.sh"
[ "$CODE" -eq 0 ] || { cat "$ERR"; fail "F2-CUSTOM first-piece failed"; }
python3 - "$TP_ROOT/.github/workflows/checks.yml" <<'PYTEST' || fail "F2-CUSTOM hosted command differs or custom workflow text changed"
import json, sys
text = open(sys.argv[1]).read()
line = next(line for line in text.splitlines() if "SCAFFOLD_TEST_COMMAND:" in line)
assert json.loads(line.split(":", 1)[1]) == "sh tests/run.sh", "F2-CUSTOM"
assert text.endswith("# The person added this before capturing the scaffold.\n"), "F2-PRESERVE"
PYTEST
mkdir "$TP_ROOT/tests"
printf 'echo F2-CUSTOM a failing scaffold >&2\nexit 9\n' > "$TP_ROOT/tests/run.sh"
git -C "$TP_ROOT" add -A
git -C "$TP_ROOT" commit -qm "The scaffold"
bootstrap_cmd=$(python3 - "$TP_ROOT/.github/workflows/checks.yml" <<'PYTEST'
import json, sys
line = next(line for line in open(sys.argv[1]) if "SCAFFOLD_TEST_COMMAND:" in line)
print(json.loads(line.split(":", 1)[1]))
PYTEST
)
code=0
(cd "$TP_ROOT" && python3 "$(dirname "$SETUP_SRC")/hosted-check.py" --base HEAD^ \
  --scaffold-command "$bootstrap_cmd") > "$TP_BASE/hosted.out" 2>&1 || code=$?
[ "$code" = 9 ] || fail "F2-CUSTOM hosted check skipped the failing custom judge: $(cat "$TP_BASE/hosted.out")"
ok "F2-CUSTOM the custom scaffold judge fails hosted checks and the person's workflow text stays"

if [ "$FAIL" -ne 0 ]; then
  echo "Setup first-half checks FAILED" >&2
  exit 1
fi
echo "Setup first-half checks passed."
