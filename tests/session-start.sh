#!/usr/bin/env sh
# session-start.sh: drive the session start hook the way Claude Code does after
# a compaction (and at a start), and check what it says.
#
# The hook runs `gate.py report --json --brief` and passes what it prints to the
# session. When that fails, it prints one fixed fallback line instead. This test
# checks the fallback line with a stand-in gate. P11 checks the real report.
#
# The hook is copied into a throwaway kit folder beside a stand-in gate.py, so
# the test never needs the real gate. The scratch folder is left in place.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HOOK_SOURCE="$ROOT/kit/scripts/session-start.sh"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

FALLBACK='The loop state could not be read just now. Run "gate.py report --json --brief" and carry on from its "next:" line.'

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
ok() {
  echo "  ok: $1"
}

[ -x "$HOOK_SOURCE" ] || fail "kit/scripts/session-start.sh is missing or not executable. next: build P10"

SCRATCH=$(mktemp -d)
OUT="$SCRATCH/out"
ARGS_LOG="$SCRATCH/gate-args"
export ARGS_LOG

# A project that runs the loop, and a kit folder with a stand-in gate.
PROJECT="$SCRATCH/project"
KIT="$SCRATCH/kit"
mkdir -p "$PROJECT/.agents/loop" "$KIT/scripts"
git -C "$PROJECT" init -q -b main
printf '{}\n' > "$PROJECT/.agents/loop/policy.json"
git -C "$PROJECT" -c user.name=T -c user.email=t@example.com add -A
git -C "$PROJECT" -c user.name=T -c user.email=t@example.com commit -q -m "Start"
HOOK="$KIT/scripts/session-start.sh"
cp "$HOOK_SOURCE" "$HOOK"
chmod +x "$HOOK"

stand_in() {
  # stand_in <exit code> <stdout text>
  cat > "$KIT/scripts/gate.py" <<PY
import os, sys
open(os.environ["ARGS_LOG"], "w").write(" ".join(sys.argv[1:]) + "\n")
sys.stdout.write('''$2''' + "\n")
sys.exit($1)
PY
}

run_hook() {
  # run_hook <stdin payload> [option]
  ( cd "$PROJECT" && printf '%s' "$1" | "$HOOK" ${2:-} ) > "$OUT" 2> "$SCRATCH/err" || \
    fail "the session hook exited non-zero (it must never stop a session)"
}

COMPACT='{"hook_event_name":"SessionStart","source":"compact"}'
STARTUP='{"hook_event_name":"SessionStart","source":"startup"}'

echo "Session start hook checks:"

# --- the report works -------------------------------------------------------------
stand_in 0 '{"state":"building","next":"gate.py run"}'
run_hook "$COMPACT" --claude-hook
[ "$(wc -l < "$OUT")" -eq 1 ] || fail "Claude hook mode did not give one line of JSON after a compaction"
python3 - "$OUT" <<'PYEOF' || fail "the hook output after a compaction is not the JSON Claude Code reads"
import json, sys
body = json.load(open(sys.argv[1]))
out = body["hookSpecificOutput"]
assert out["hookEventName"] == "SessionStart", out
assert '"state":"building"' in out["additionalContext"].replace(" ", ""), out
PYEOF
ok "after a compaction it passes the brief report to the session"
[ "$(cat "$ARGS_LOG")" = "report --json --brief" ] || \
  fail "the hook called the gate with '$(cat "$ARGS_LOG")', not 'report --json --brief'"
ok "it calls gate.py with report --json --brief"

run_hook "$STARTUP" --claude-hook
grep -qF 'building' "$OUT" || fail "a session start does not get the report too"
ok "a session start gets the report too"

run_hook "$COMPACT"
grep -qF '"next":"gate.py run"' "$OUT" || fail "plain mode did not print the report"
ok "plain mode prints the report"

# --- the report fails: the fallback line -------------------------------------------
stand_in 3 'boom'
run_hook "$COMPACT" --claude-hook
python3 - "$OUT" "$FALLBACK" <<'PYEOF' || fail "after a failed report the hook did not print the fallback line"
import json, sys
body = json.load(open(sys.argv[1]))
text = body["hookSpecificOutput"]["additionalContext"]
assert sys.argv[2] in text, text
assert "boom" not in text, text
PYEOF
ok "a failing report gives the fallback line, and not the failure text"

stand_in 0 ''
run_hook "$COMPACT"
grep -qF "$FALLBACK" "$OUT" || fail "an empty report did not give the fallback line"
ok "an empty report gives the fallback line"

rm "$KIT/scripts/gate.py"
run_hook "$COMPACT"
grep -qF "$FALLBACK" "$OUT" || fail "a missing gate did not give the fallback line"
ok "a missing gate gives the fallback line"

# --- it stays quiet outside a loop project, and never stops a session ---------------
stand_in 0 '{"state":"idle"}'
OTHER="$SCRATCH/other"
mkdir -p "$OTHER"
git -C "$OTHER" init -q -b main
( cd "$OTHER" && printf '%s' "$COMPACT" | "$HOOK" --claude-hook ) > "$OUT" 2>&1 || \
  fail "the hook failed in a folder with no loop"
[ ! -s "$OUT" ] || fail "the hook spoke in a project that does not run the loop"
ok "it prints nothing in a project that does not run the loop"

( cd "$PROJECT" && printf '%s' 'not json' | "$HOOK" --claude-hook ) > "$OUT" 2>&1 || \
  fail "the hook failed on input that is not JSON"
ok "input that is not JSON does not stop it"

( cd "$PROJECT" && "$HOOK" --nonsense ) > "$OUT" 2>&1 || fail "the hook failed on an unknown option"
ok "an unknown option does not stop it"

# --- it changes nothing --------------------------------------------------------------
[ -z "$(git -C "$PROJECT" status --porcelain)" ] || fail "the hook changed project files"
ok "it changes nothing in the project"

# The old check-up reminder is gone.
if grep -qE 'AI_BUILD_KIT_TODAY|ai-build-kit|AI Build Kit|check-up' "$HOOK_SOURCE"; then
  fail "the hook still carries the old check-up reminder or the old product name"
fi
ok "the old check-up reminder and product name are gone"

echo "session-start.sh: all checks passed (scratch: $SCRATCH)"
