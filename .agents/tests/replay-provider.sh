#!/usr/bin/env sh
# replay-provider.sh: prove the replay harness can drive Claude Code and Codex.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PROVIDER="$ROOT/.agents/tests/replay/provider.sh"
RUNNER="$ROOT/.agents/tests/replay/run.sh"
README="$ROOT/.agents/tests/replay/README.md"
GRADER="$ROOT/.agents/tests/replay/grader-prompt.md"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

TEST_WORK=$(mktemp -d)
trap 'rm -rf "$TEST_WORK"' EXIT INT TERM
BIN="$TEST_WORK/bin"
mkdir -p "$BIN" "$TEST_WORK/project" "$TEST_WORK/fake-github" "$TEST_WORK/fake-host"
PROVIDER_LOG="$TEST_WORK/provider.log"
export PROVIDER_LOG

cat > "$BIN/codex" <<'STUB'
#!/bin/sh
set -eu
printf 'codex %s\n' "$*" >> "$PROVIDER_LOG"
output=
previous=
for argument in "$@"; do
  if [ "$previous" = "-o" ]; then output=$argument; fi
  previous=$argument
done
[ -n "$output" ] || exit 2
case " $* " in
  *" --ephemeral "*)
    printf '%s' '{"scenario":1,"verdicts":{"Expected path":{"verdict":"hit","quote":"kept","note":"kept"}},"pushback":{"verdict":"unobservable","quote":"","note":"none"},"held":true,"held_clause":0,"held_note":"held"}' > "$output"
    ;;
  *" exec resume "*) printf '%s' 'codex resumed' > "$output" ;;
  *) printf '%s' 'codex started' > "$output" ;;
esac
printf '%s\n' '{"type":"thread.started","thread_id":"codex-thread"}'
STUB

cat > "$BIN/claude" <<'STUB'
#!/bin/sh
set -eu
printf 'claude %s\n' "$*" >> "$PROVIDER_LOG"
# What a turn's environment says about the host's accounts.
printf '%s|%s|%s|%s|%s|%s\n' "${VERCEL_TOKEN:-}" "${SUPABASE_ACCESS_TOKEN:-}" \
  "${DOCKER_HOST:-}" "${DOCKER_CONFIG:-}" "${PGPASSFILE:-}" "${PGSERVICEFILE:-}" \
  > "$PROVIDER_LOG.host-env"
# Which gh a login shell finds here, the way Claude Code's Bash tool builds its
# environment from one.
printf '%s\n' "${ZDOTDIR:-}" > "$PROVIDER_LOG.zdotdir"
if command -v zsh >/dev/null 2>&1; then
  zsh -l -c 'command -v gh' > "$PROVIDER_LOG.login-gh" 2>/dev/null || true
  zsh -l -c 'command -v vercel' > "$PROVIDER_LOG.login-vercel" 2>/dev/null || true
fi
case " $* " in
  *" --allowedTools  "*)
    printf '%s\n' '{"result":"{\"scenario\":1,\"verdicts\":{\"Expected path\":{\"verdict\":\"hit\",\"quote\":\"kept\",\"note\":\"kept\"}},\"pushback\":{\"verdict\":\"unobservable\",\"quote\":\"\",\"note\":\"none\"},\"held\":true,\"held_clause\":0,\"held_note\":\"held\"}"}'
    ;;
  *" --resume "*) printf '%s\n' '{"result":"claude resumed"}' ;;
  *) printf '%s\n' '{"result":"claude started"}' ;;
esac
STUB

chmod +x "$BIN/codex" "$BIN/claude"
PATH="$BIN:$PATH"
export PATH

fail_provider() {
  echo "FAIL: $1" >&2
  exit 1
}
fail() {
  fail_provider "$1"
}
new_uuid() {
  printf '%s\n' claude-session
}

REPLAY_DIR="$ROOT/.agents/tests/replay"
WORK="$TEST_WORK/work"
GH_DIR="$TEST_WORK/fake-github"
HOST_DIR="$TEST_WORK/fake-host"
TIMEOUT_CMD=
mkdir -p "$WORK"
. "$PROVIDER"

REPLAY_PROVIDER=codex
MODEL=codex-model
GRADER_MODEL=codex-grader
provider_check
provider_prepare
provider_new_session

codex_reply="$TEST_WORK/codex-reply"
provider_turn "$TEST_WORK/project" "first turn" "$TEST_WORK/codex-first.jsonl" "$codex_reply" \
  || fail_provider "Codex could not start a replay thread"
[ "$(cat "$codex_reply")" = "codex started" ] \
  && pass "Codex returns the first reply" \
  || fail_provider "Codex first reply was not captured"
[ "$PROVIDER_SESSION" = "codex-thread" ] \
  && pass "Codex thread id is read from JSONL" \
  || fail_provider "Codex thread id was not retained"

provider_turn "$TEST_WORK/project" "second turn" "$TEST_WORK/codex-second.jsonl" "$codex_reply" \
  || fail_provider "Codex could not resume a replay thread"
[ "$(cat "$codex_reply")" = "codex resumed" ] \
  && pass "Codex resumes the same conversation" \
  || fail_provider "Codex resume reply was not captured"

grep -q "exec resume.*codex-thread" "$PROVIDER_LOG" \
  && pass "Codex resume receives the recorded thread id" \
  || fail_provider "Codex resume did not receive the thread id"
grep -q "shell_environment_policy.inherit=all" "$PROVIDER_LOG" \
  && pass "Codex inherits the isolated replay environment" \
  || fail_provider "Codex did not inherit the replay environment"
grep -qF "$GH_DIR" "$WORK/replay-shell/.zprofile" \
  && pass "the Codex zsh profile restores fake GitHub after login" \
  || fail_provider "the Codex zsh profile does not name fake GitHub"
grep -qF "$GH_DIR" "$WORK/replay-shell/bash-env" \
  && pass "the Codex bash profile restores fake GitHub after login" \
  || fail_provider "the Codex bash profile does not name fake GitHub"

printf '%s\n' grading > "$TEST_WORK/input"
provider_grade "$TEST_WORK/input" "$TEST_WORK/codex-grade.raw"
[ -s "$TEST_WORK/codex-grade.raw.events" ] \
  && pass "Codex grader events are kept for inspection" \
  || fail_provider "Codex grader events were discarded"
python3 - "$TEST_WORK/codex-grade.raw" <<'PY' \
  && pass "Codex grader output uses the existing outer JSON shape" \
  || fail_provider "Codex grader output was not wrapped for the parser"
import json
import sys
outer = json.load(open(sys.argv[1]))
inner = json.loads(outer["result"])
assert inner["held"] is True
PY
grep -q -- "--ephemeral.*--sandbox read-only" "$PROVIDER_LOG" \
  && pass "the Codex grader is ephemeral and read-only" \
  || fail_provider "the Codex grader did not use its restricted mode"

REPLAY_PROVIDER=claude
MODEL=opus
GRADER_MODEL=opus

# Claude Code's Bash tool builds its environment from a login shell, which
# reads the person's own profile. On a Mac with Homebrew first in that profile,
# the real gh won over the stand-in in one recorded run. So the Claude route
# gets the same throwaway profiles as Codex. Start from nothing, so the Codex
# preparation above cannot stand in for it.
unset ZDOTDIR BASH_ENV
rm -rf "$WORK/replay-shell"
printf '#!/bin/sh\necho stand-in\n' > "$GH_DIR/gh"
chmod +x "$GH_DIR/gh"
printf '#!/bin/sh\necho stand-in\n' > "$HOST_DIR/vercel"
chmod +x "$HOST_DIR/vercel"
provider_prepare
provider_new_session
grep -qF "$GH_DIR" "$WORK/replay-shell/.zprofile" \
  && [ "${ZDOTDIR:-}" = "$WORK/replay-shell" ] \
  && pass "the Claude route writes the profile that puts fake GitHub first" \
  || fail_provider "the Claude route has no profile that puts fake GitHub first"
provider_turn "$TEST_WORK/project" "first turn" "$TEST_WORK/claude-zdot.json" \
  "$TEST_WORK/claude-zdot-reply" || fail_provider "Claude could not start a turn"
[ "$(cat "$PROVIDER_LOG.zdotdir")" = "$WORK/replay-shell" ] \
  && pass "a Claude turn runs with that profile" \
  || fail_provider "a Claude turn ran without the throwaway profile"
# A login shell, which reads that profile, finds the stand-in rather than the
# person's own gh. Where this machine has no zsh there is nothing to try.
if command -v zsh >/dev/null 2>&1; then
  [ "$(cat "$PROVIDER_LOG.login-gh")" = "$GH_DIR/gh" ] \
    && pass "a login shell in a Claude turn finds fake GitHub first" \
    || fail_provider "a login shell in a Claude turn found $(cat "$PROVIDER_LOG.login-gh")"
  # The host's stand-ins come next, so a login shell never finds a deploy
  # command that may be signed in to somebody's account.
  [ "$(cat "$PROVIDER_LOG.login-vercel")" = "$HOST_DIR/vercel" ] \
    && pass "a login shell in a Claude turn finds the host's stand-ins first" \
    || fail_provider "a login shell in a Claude turn found $(cat "$PROVIDER_LOG.login-vercel")"
fi
# A turn must find no account in the host's real tools either. The harness
# sets a token that belongs to no account for Vercel and Supabase, an engine
# that does not exist for Docker, and no stored password for the database.
grep -q 'provider_isolate_host "$project"' "$RUNNER" \
  && pass "every replay turn isolates the host's tools" \
  || fail_provider "run.sh no longer isolates the host's tools for each turn"
(
  provider_isolate_host "$TEST_WORK/project"
  provider_turn "$TEST_WORK/project" "first turn" "$TEST_WORK/claude-host.json" \
    "$TEST_WORK/claude-host-reply"
) || fail_provider "Claude could not start a turn with the host isolated"
[ "$(cat "$PROVIDER_LOG.host-env")" = "replay-no-account|replay-no-account|unix:///nonexistent/replay.sock|$TEST_WORK/project/.docker-empty|/dev/null|/dev/null" ] \
  && pass "a replay turn carries no account for Vercel, Supabase, Docker or the database" \
  || fail_provider "a replay turn's host environment was: $(cat "$PROVIDER_LOG.host-env")"

provider_check
provider_new_session
claude_reply="$TEST_WORK/claude-reply"
provider_turn "$TEST_WORK/project" "first turn" "$TEST_WORK/claude-first.json" "$claude_reply" \
  || fail_provider "Claude Code could not start a replay session"
[ "$(cat "$claude_reply")" = "claude started" ] \
  && pass "Claude Code keeps its first-turn route" \
  || fail_provider "Claude Code first reply changed"
provider_turn "$TEST_WORK/project" "second turn" "$TEST_WORK/claude-second.json" "$claude_reply" \
  || fail_provider "Claude Code could not resume a replay session"
[ "$(cat "$claude_reply")" = "claude resumed" ] \
  && pass "Claude Code keeps its resume route" \
  || fail_provider "Claude Code resume changed"
grep -q -- "--session-id claude-session" "$PROVIDER_LOG" \
  && pass "Claude Code still starts with the harness session id" \
  || fail_provider "Claude Code lost its chosen session id"
grep -q -- "--resume claude-session" "$PROVIDER_LOG" \
  && pass "Claude Code still resumes the chosen session" \
  || fail_provider "Claude Code lost its resume id"

provider_grade "$TEST_WORK/input" "$TEST_WORK/claude-grade.raw"
python3 "$REPLAY_DIR/grade-parse.py" \
  "$TEST_WORK/claude-grade.raw" "$TEST_WORK/claude-grade.json" 1
python3 - "$TEST_WORK/claude-grade.json" <<'PY' \
  && pass "Claude Code grader output still parses" \
  || fail_provider "Claude Code grader output no longer parses"
import json
import sys
assert json.load(open(sys.argv[1]))["held"] is True
PY

grep -q 'REPLAY_PROVIDER=${REPLAY_PROVIDER:-claude}' "$RUNNER" \
  && pass "Claude Code remains the default provider" \
  || fail_provider "the default replay provider changed"
grep -q 'REPLAY_PROVIDER=codex REPEATS=1' "$README" \
  && pass "the Codex command is documented" \
  || fail_provider "the Codex command is missing from the guide"
grep -q "Expected path.*recorded build path" "$GRADER" \
  && grep -q "before a build.*not a path change" "$GRADER" \
  && pass "the grader treats Expected path as a build path" \
  || fail_provider "the grader still confuses the path with a build command"

# A run that lost the stand-in reads normally, so the harness has to find it.
# The transcript holds only what was said, so the provider's own record of each
# command's output is read too. The signs are the real, signed-out CLI's own
# sentences. A kit telling the person to run "gh auth login" is advice, and
# must not cost a run its grade.
RECORDS="$TEST_WORK/records"
mkdir -p "$RECORDS"
printf '%s\n' '### kit reply 1' 'Please run gh auth login, then try again.' \
  > "$RECORDS/advice.transcript"
printf '%s\n' '{"type":"tool_result","content":"To get started with GitHub CLI, please run:  gh auth login"}' \
  > "$RECORDS/signed-out.jsonl"
printf '%s\n' '{"type":"tool_result","content":"You are not logged into any GitHub hosts. To log in, run: gh auth login"}' \
  > "$RECORDS/no-hosts.jsonl"

if printf '%s\n' "$RECORDS/advice.transcript" | real_gh_answered >/dev/null; then
  fail_provider "a kit's advice to sign in was taken for the real GitHub CLI"
else
  pass "advice to run gh auth login is not a sign of the real CLI"
fi
for record in signed-out no-hosts; do
  sign=$(printf '%s\n' "$RECORDS/advice.transcript" "$RECORDS/$record.jsonl" \
    | real_gh_answered) \
    && case $sign in *"$record.jsonl"*) true ;; *) false ;; esac \
    && pass "the real CLI's $record sentence is found and its file named" \
    || fail_provider "the real CLI's $record sentence was not found"
done
if grep -qF -e "$REAL_GH_SIGNED_OUT" -e "$REAL_GH_NO_HOSTS" \
  "$ROOT/.agents/tests/replay/fake-github/gh"; then
  fail_provider "the stand-in prints a sentence that marks the real CLI"
else
  pass "the stand-in never prints the real CLI's signed-out sentences"
fi

# Claude Code keeps the session under its configuration folder, by the id the
# harness chose and wrote beside the run. Codex keeps it in each turn's output.
CLAUDE_CONFIG_DIR="$TEST_WORK/claude-config"
export CLAUDE_CONFIG_DIR
mkdir -p "$CLAUDE_CONFIG_DIR/projects/-some-project"
: > "$CLAUDE_CONFIG_DIR/projects/-some-project/claude-session.jsonl"
printf '%s\n' claude-session > "$RECORDS/s01-r1.session"
REPLAY_PROVIDER=claude
provider_session_records "$RECORDS/s01-r1" | grep -q '/claude-session.jsonl$' \
  && pass "the Claude Code session record is found by the recorded id" \
  || fail_provider "the Claude Code session record was not found"
: > "$RECORDS/s01-r1-t1.json"
: > "$RECORDS/s01-r1-t2.json"
REPLAY_PROVIDER=codex
[ "$(provider_session_records "$RECORDS/s01-r1" | wc -l | tr -d ' ')" = 2 ] \
  && pass "every Codex turn's output is read as its session record" \
  || fail_provider "the Codex turn outputs were not all listed"
REPLAY_PROVIDER=claude

grep -q 'PROVIDER_SESSION:-}" > "$WORK/s${number}-r${repeat}.session"' "$RUNNER" \
  && pass "the runner writes each run's session id beside it" \
  || fail_provider "the runner no longer records the session id"
awk '/real_gh_answered\); then/ { seen = 1 }
     /grade_once "\$1"/ { if (seen) found = 1; exit }
     END { exit found ? 0 : 1 }' "$RUNNER" \
  && pass "the runner looks for the real CLI before it grades" \
  || fail_provider "the runner grades without looking for the real CLI"

ROLLUP_RESULTS="$TEST_WORK/rollup"
mkdir -p "$ROLLUP_RESULTS"
printf '%s\n' '{"scenario":53,"error":"the real GitHub CLI answered a command (\"To get started with GitHub CLI, please run\" in s.jsonl); not graded"}' \
  > "$ROLLUP_RESULTS/s53-r1.json"
printf '%s\n' '{"scenario":53,"held":true,"verdicts":{}}' > "$ROLLUP_RESULTS/s53-r2.json"
rolled=$(sh "$ROOT/.agents/tests/replay/rollup.sh" "$ROLLUP_RESULTS")
printf '%s\n' "$rolled" | grep -q 'Scenario 53   held 1/1' \
  && pass "a run the real CLI answered is left out of the rate" \
  || fail_provider "a run the real CLI answered was counted in the rate"
printf '%s\n' "$rolled" | grep -q 's53-r1.json: the real GitHub CLI answered' \
  && pass "the roll-up says why a run was not graded" \
  || fail_provider "the roll-up names an ungraded run without its reason"

if (REPLAY_PROVIDER=unknown; provider_check) >/dev/null 2>&1; then
  fail_provider "an unknown replay provider was accepted"
else
  pass "an unknown replay provider is refused"
fi

echo
echo "replay-provider.sh: all checks passed"
