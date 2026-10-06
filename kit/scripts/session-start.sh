#!/usr/bin/env sh
# Runs when a working session opens. It says one thing, and only when the
# project is past its monthly check-up, or has had enough work land since the
# last one that a visit is due anyway. Otherwise it prints nothing. It reads
# project files and saved history, edits nothing, fetches nothing, and starts
# no other agent. Every route through it exits 0, so it cannot stop a session
# from opening.
#
# start copies this file to .agents/hooks/session-start.sh in the project.
#
# Wiring, per tool:
#   Claude Code: the SessionStart block in .claude/settings.json, which start
#                creates together with that file. Nothing here edits settings.
#   Other tools: no session-start mechanism today, so what-now reports an
#                overdue check-up instead.
#
# Usage:
#   session-start.sh                plain text, for a person or an agent to show
#   session-start.sh --claude-hook  one JSON object, for Claude Code's hook
#
# AI_BUILD_KIT_TODAY overrides today's date. It exists so the kit's own cadence
# check can be tested exactly, and is not part of normal use.

set -eu

MODE=plain
case "${1:-}" in
  --claude-hook) MODE=claude-hook ;;
  ""|--plain) MODE=plain ;;
  *) exit 0 ;;
esac

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." 2>/dev/null && pwd -P) || exit 0
cd "$ROOT" 2>/dev/null || exit 0

# The kit's own source repository maintains the kit; it is not a project built
# with the kit, so it never receives a project reminder. Its release allowlist
# and its own test folder identify it without naming any repository.
if [ -f "$ROOT/release-manifest.txt" ] && [ -d "$ROOT/.agents/tests" ]; then
  exit 0
fi

# Claude Code sends the hook a payload naming why the session started. A
# compaction is not a session opening, so it gets nothing.
if [ "$MODE" = claude-hook ] && [ ! -t 0 ]; then
  payload=$(cat 2>/dev/null || true)
  case "$payload" in
    *'"source"'*'"compact"'*) exit 0 ;;
  esac
fi

CADENCE_DAYS=35
# A busy project can do a month's work in a few days, so the reminder also
# speaks once this many changes have landed on the default branch since the
# last visit, however few days that took.
CHANGES_SINCE_VISIT=20
RECORD="$ROOT/.ai-build-kit-maintenance"
today=${AI_BUILD_KIT_TODAY:-$(date -u +%Y-%m-%d 2>/dev/null || true)}

record_value() {
  [ -f "$RECORD" ] || return 0
  sed -n "s/^$1|//p" "$RECORD" 2>/dev/null | head -n 1
}

# Days since a fixed point, from a YYYY-MM-DD date. Plain shell arithmetic, so
# it behaves the same wherever the project is opened; the date command's own
# options for this differ between computers. The difference between two of
# these numbers is an exact day count.
day_number() {
  stamp=$1
  case "$stamp" in
    [1-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
    *) return 1 ;;
  esac
  y=${stamp%%-*}
  rest=${stamp#*-}
  m=${rest%%-*}
  d=${rest#*-}
  m=${m#0}
  d=${d#0}
  if [ "$m" -le 2 ]; then
    y=$((y - 1))
    m=$((m + 12))
  fi
  echo $(( 365 * y + y / 4 - y / 100 + y / 400 + (153 * (m - 3) + 2) / 5 + d ))
}

# A project that has never had a check-up is measured from its founding, so a
# new project is never told it is overdue.
founding_date() {
  recorded=$(record_value founded)
  if [ -n "$recorded" ]; then
    printf '%s\n' "$recorded"
    return 0
  fi
  git log --reverse --diff-filter=A --format=%cd --date=short \
    -- masterplan.md 2>/dev/null | head -n 1
}

# The branch the project's work lands on, from what this computer already
# holds: origin/HEAD where a remote names one, else main, else master, else
# whatever is checked out. Nothing is fetched, so the count can run late by the
# merges made online since the last pull, and never costs a network call.
count_ref() {
  for ref in origin/HEAD main master HEAD; do
    if git rev-parse --verify --quiet "$ref^{commit}" >/dev/null 2>&1; then
      printf '%s\n' "$ref"
      return 0
    fi
  done
  return 1
}

# The changes that landed since a YYYY-MM-DD date. On the first-parent line of
# a branch that only takes pull requests, each one is a merged piece; on a
# branch saved to directly, each one is a checkpoint.
changes_since() {
  case "$1" in
    [1-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
    *) return 1 ;;
  esac
  ref=$(count_ref) || return 1
  git rev-list --count --first-parent --since="$1T00:00:00Z" "$ref" 2>/dev/null
}

maintenance_line() {
  [ -f "$ROOT/masterplan.md" ] || return 0

  visited=$(record_value last-light-pass)
  last=$visited
  [ -n "$last" ] || last=$(founding_date)
  [ -n "$last" ] || return 0

  said=""
  last_day=$(day_number "$last" || true)
  today_day=""
  [ -z "$today" ] || today_day=$(day_number "$today" || true)
  if [ -n "$last_day" ] && [ -n "$today_day" ]; then
    elapsed=$((today_day - last_day))
    if [ "$elapsed" -ge "$CADENCE_DAYS" ]; then
      if [ -n "$visited" ]; then
        echo "It has been $elapsed days since the last check-up."
      else
        echo "The project is $elapsed days old and has had no check-up yet."
      fi
      said=yes
    fi
  fi

  changes=$(changes_since "$last" || true)
  case "$changes" in
    ''|*[!0-9]*) changes=0 ;;
  esac
  if [ "$changes" -ge "$CHANGES_SINCE_VISIT" ]; then
    if [ -n "$visited" ]; then
      echo "$changes changes have landed since the last check-up."
    else
      echo "$changes changes have landed since founding."
    fi
    said=yes
  fi

  [ -n "$said" ] || return 0
  echo "Type /maintain when you have ten minutes."
}

reminder=$(maintenance_line || true)
[ -n "$reminder" ] || exit 0

if [ "$MODE" = plain ]; then
  printf '%s\n' "$reminder"
  exit 0
fi

json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk '{ printf "%s\\n", $0 }'
}

context="The person was told a check-up is overdue: $(printf '%s' "$reminder" | tr '\n' ' ')"

escaped_message=$(printf '%s\n' "$reminder" | json_escape)
escaped_context=$(printf '%s\n' "$context" | json_escape)

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"},"systemMessage":"%s"}\n' \
  "$escaped_context" "$escaped_message"

exit 0
