#!/usr/bin/env sh
# Runs when a working session opens, and after a compaction. It asks the gate
# for a short report of the loop's state and hands that report to the session,
# so the agent carries on from the real state and not from memory.
#
# It calls `gate.py report --json --brief`, next to this file. When the call
# fails, or prints nothing, it prints one fixed fallback line instead. It
# prints nothing in a project that does not run the loop. It then asks
# `gate.py check-main --brief --json` for a merge the person made on GitHub, and
# adds one line when it finds one. That call reads and changes nothing, and does
# nothing while a run is going. The only fetch is the one it makes, as the gate's
# App, when a piece waits in approval. The hook edits nothing and starts no other
# agent. Every route through it exits 0, so it cannot stop a session from opening.
#
# Wiring: the SessionStart block of the settings template, kit/templates/
# claude-settings.json.
#
# Usage:
#   session-start.sh                plain text, for a person or an agent to show
#   session-start.sh --claude-hook  one JSON object, for Claude Code's hook

set -u

MODE=plain
case "${1:-}" in
  --claude-hook) MODE=claude-hook ;;
  ""|--plain) MODE=plain ;;
  *) exit 0 ;;
esac

FALLBACK='The loop state could not be read just now. Run "gate.py report --json --brief" and carry on from its "next:" line.'

SELF=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd -P) || exit 0

# Claude Code sends the hook a payload on standard input. This hook says the
# same thing for every start reason, so it does not read the payload. It only
# empties it, so a writer never waits on a pipe.
if [ "$MODE" = claude-hook ] && [ ! -t 0 ]; then
  cat >/dev/null 2>&1 || true
fi

# A project that runs the loop has a loop folder in its main folder.
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
COMMON=$(git rev-parse --git-common-dir 2>/dev/null) || COMMON=""
case "$COMMON" in
  /*) MAIN=$(CDPATH= cd -- "$COMMON/.." 2>/dev/null && pwd -P) || MAIN=$ROOT ;;
  *) MAIN=$ROOT ;;
esac
[ -d "$MAIN/.agents/loop" ] || [ -d "$ROOT/.agents/loop" ] || exit 0

report=""
if [ -f "$SELF/gate.py" ]; then
  report=$(python3 "$SELF/gate.py" report --json --brief 2>/dev/null) || report=""
fi
[ -n "$report" ] || report=$FALLBACK

# A merge the person made on GitHub since the last session, if any. A failure, a slow
# answer or text that is not JSON adds nothing: the report above still stands.
if [ -f "$SELF/gate.py" ]; then
  merged=$(python3 - "$SELF/gate.py" <<'PYEOF' 2>/dev/null
import json, subprocess, sys
try:
    done = subprocess.run([sys.executable, sys.argv[1], "check-main", "--brief", "--json"],
                          capture_output=True, text=True, timeout=20, check=False,
                          stdin=subprocess.DEVNULL)
    line = json.loads(done.stdout.strip().splitlines()[-1]).get("line", "")
    print(line if isinstance(line, str) else "")
except Exception:
    pass
PYEOF
  ) || merged=""
  if [ -n "$merged" ]; then
    report="$report
$merged"
  fi
fi

if [ "$MODE" = plain ]; then
  printf '%s\n' "$report"
  exit 0
fi

json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk '{ printf "%s\\n", $0 }'
}

escaped_context=$(printf '%s\n' "$report" | json_escape)

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' \
  "$escaped_context"

exit 0
