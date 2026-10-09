#!/usr/bin/env sh
# guard-hook.sh: run the command guard hook as Claude Code does.
#
# Claude Code starts a PreToolUse hook with the call as JSON on standard input.
# Exit 2 refuses the call and shows standard error to the agent. Exit 0 with a
# permissionDecision of "ask" makes Claude Code show its confirmation box. Exit
# 0 with no output lets the call run.
#
# This builds a throwaway project with a worktree, feeds the hook a refusal, an
# ask and a pass, and reads back the exit code, the message and the line each
# one leaves in the project's command log. Then it runs the log hook the way
# Claude Code runs it after a tool call. The unit tests in tests/unit/test_guard.py
# hold the spellings. This holds the wiring.
#
# Usage: tests/guard-hook.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

GUARD="$ROOT/kit/hooks/guard.py"
LOGGER="$ROOT/kit/hooks/command-log.py"

failures=0
fail() {
  echo "  FAIL: $1" >&2
  failures=$((failures + 1))
}
ok() {
  echo "  ok: $1"
}

[ -f "$GUARD" ] || { echo "FAIL: there is no hook at kit/hooks/guard.py. next: build P3" >&2; exit 1; }
[ -f "$LOGGER" ] || { echo "FAIL: there is no hook at kit/hooks/command-log.py. next: build P3" >&2; exit 1; }

. "$ROOT/tests/lib/throwaway-project.sh"
tp_new demo
AI_LOOP_KIT_RUN=night-1
export AI_LOOP_KIT_RUN
LOG="$TP_ROOT/.agents/runs/night-1/commands.log"

git -C "$TP_ROOT" worktree add -q "$TP_ROOT/.agents/worktrees/w1" -b piece-1

# json_for <tool> <field> <value> <cwd>: the hook input for one call.
json_for() {
  python3 -c '
import json, sys
tool, field, value, cwd = sys.argv[1:5]
print(json.dumps({"session_id": "s1", "hook_event_name": "PreToolUse",
                  "tool_name": tool, "tool_input": {field: value}, "cwd": cwd}))
' "$1" "$2" "$3" "$4"
}

OUT="$TP_BASE/hook.out"
ERR="$TP_BASE/hook.err"

# run_guard <tool> <field> <value> <cwd>: sets CODE and fills $OUT and $ERR.
run_guard() {
  CODE=0
  # The project fixture isolates Git through external configuration. These
  # hook controls model a clean session; inherited overrides have unit cases.
  json_for "$@" | python3 -c '
import os, sys
env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_CONFIG")}
os.execve(sys.executable, [sys.executable, sys.argv[1]], env)
' "$GUARD" >"$OUT" 2>"$ERR" || CODE=$?
}

last_log() {
  tail -n 1 "$LOG"
}

# json_field <json> <key>: one field of a log line.
json_field() {
  python3 -c 'import json, sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ""))' "$1" "$2"
}

echo "A refusal"
run_guard Bash command "git -C . push origin main" "$TP_ROOT"
[ "$CODE" -eq 2 ] && ok "git -C . push origin main exits 2" || fail "exit code $CODE, not 2"
[ ! -s "$OUT" ] && ok "a refusal prints nothing on standard output" || fail "standard output holds text"
grep -q "next:" "$ERR" && ok "the message names the next step" || fail "no next: line on standard error"
[ -f "$LOG" ] || fail "no command log at $LOG"
line=$(last_log)
[ "$(json_field "$line" event)" = refuse ] && ok "the log line says refuse" || fail "log line: $line"
[ -n "$(json_field "$line" reason)" ] && ok "the log line holds the reason" || fail "no reason in: $line"
[ "$(json_field "$line" command)" = "git -C . push origin main" ] && ok "the log line holds the command" \
  || fail "wrong command in: $line"

echo "An ask"
run_guard Bash command "gh pr comment 5 --body hello" "$TP_ROOT"
[ "$CODE" -eq 0 ] && ok "a comment in the person's name exits 0" || fail "exit code $CODE, not 0"
decision=$(python3 -c '
import json, sys
body = json.load(open(sys.argv[1]))["hookSpecificOutput"]
print(body["hookEventName"], body["permissionDecision"], bool(body["permissionDecisionReason"]))
' "$OUT" 2>/dev/null || echo "unreadable")
[ "$decision" = "PreToolUse ask True" ] && ok "the output asks, with a reason" || fail "output was: $decision"
line=$(last_log)
[ "$(json_field "$line" event)" = ask ] && ok "the log line says ask" || fail "log line: $line"

echo "A pass"
run_guard Bash command "git push origin piece-1" "$TP_ROOT"
[ "$CODE" -eq 0 ] && ok "a harmless push exits 0" || fail "exit code $CODE, not 0"
[ ! -s "$OUT" ] && [ ! -s "$ERR" ] && ok "a pass prints nothing" || fail "a pass printed text"
line=$(last_log)
[ "$(json_field "$line" event)" = pass ] && ok "the log line says pass" || fail "log line: $line"

echo "Real and throwaway env files"
printf 'SECRET=real\n' > "$TP_ROOT/.env"
run_guard Bash command "cat .env" "$TP_ROOT"
[ "$CODE" -eq 2 ] && ok "cat .env in the main folder is refused" || fail "exit code $CODE, not 2"
MARKER=$(python3 -c '
import os, sys
sys.path.insert(0, os.path.dirname(sys.argv[1]))
import guard
print(guard.THROWAWAY_MARKER)
' "$GUARD")
printf '%s\nPORT=3000\n' "$MARKER" > "$TP_ROOT/.agents/worktrees/w1/.env"
run_guard Bash command "cat .env" "$TP_ROOT/.agents/worktrees/w1"
[ "$CODE" -eq 0 ] && ok "a throwaway .env in a worktree passes" || fail "exit code $CODE, not 0"
printf '%s\nPORT=3000\n' "$MARKER" > "$TP_ROOT/.env"
run_guard Read file_path "$TP_ROOT/.env" "$TP_ROOT"
[ "$CODE" -eq 2 ] && ok "a marked .env in the main folder is still refused" || fail "exit code $CODE, not 2"

echo "The App key and a guarded write"
run_guard Read file_path "$TP_APP_KEY" "$TP_ROOT"
[ "$CODE" -eq 2 ] && ok "the App key file is refused" || fail "exit code $CODE, not 2"
run_guard Write file_path "$TP_ROOT/.claude/settings.json" "$TP_ROOT/.agents/worktrees/w1"
[ "$CODE" -eq 2 ] && ok "a write to the settings is refused" || fail "exit code $CODE, not 2"

echo "The log hook"
python3 -c '
import json, sys
print(json.dumps({"session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Bash",
                  "tool_input": {"command": "git status"}, "tool_response": {"interrupted": False},
                  "cwd": sys.argv[1]}))
' "$TP_ROOT" | python3 "$LOGGER" >"$OUT" 2>"$ERR" && ok "the log hook exits 0" || fail "the log hook failed"
line=$(last_log)
[ "$(json_field "$line" event)" = ran ] && ok "the log line says ran" || fail "log line: $line"

echo "A retry"
run_guard Bash command "git push origin piece-1" "$TP_ROOT"
line=$(last_log)
[ "$(json_field "$line" retry)" -ge 1 ] 2>/dev/null && ok "a repeat is marked as a retry" || fail "no retry count in: $line"

echo "The log is JSON, one line each"
python3 -c '
import json, sys
for n, line in enumerate(open(sys.argv[1]), 1):
    json.loads(line)
print(n)
' "$LOG" >/dev/null && ok "every line of the log parses" || fail "a log line is not JSON"

if [ "$failures" -gt 0 ]; then
  echo "FAIL: $failures check(s) failed. Run one case by hand: python3 kit/hooks/guard.py < input.json" >&2
  exit 1
fi
echo "ok: the guard hook and the command log work as Claude Code runs them"
