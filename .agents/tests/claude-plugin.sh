#!/usr/bin/env sh
# claude-plugin.sh: rehearse the command and background-skill boundary, local
# install, bootstrap, failed and successful updates, and removal without
# touching the maintainer's real Claude configuration.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

command -v claude >/dev/null 2>&1 || fail "Claude Code is not installed"
[ -x "$BUILDER" ] || fail "release builder is missing or not executable"

SCRATCH=$(mktemp -d)
CONFIG="$SCRATCH/claude-config"
MARKET="$SCRATCH/market"
MARKET_OFFLINE="$SCRATCH/market-offline"
PROJECT="$SCRATCH/project"
LISTING="$SCRATCH/plugins.json"
DETAILS="$SCRATCH/plugin-details.txt"
cleanup() {
  rm -R "$SCRATCH"
}
trap cleanup EXIT

mkdir -p "$CONFIG" "$PROJECT"
"$BUILDER" v0.2.0 "$MARKET" >/dev/null
CLAUDE_CONFIG_DIR="$CONFIG" claude plugin validate "$MARKET" --strict >/dev/null
CLAUDE_CONFIG_DIR="$CONFIG" claude plugin marketplace add "$MARKET" >/dev/null

(
  cd "$PROJECT"
  CLAUDE_CONFIG_DIR="$CONFIG" \
    claude plugin install ai-build-kit@ai-build-kit --scope local >/dev/null
  CLAUDE_CONFIG_DIR="$CONFIG" claude plugin list --json > "$LISTING"
  CLAUDE_CONFIG_DIR="$CONFIG" \
    claude plugin details ai-build-kit@ai-build-kit > "$DETAILS"
)

grep -qF '"id": "ai-build-kit@ai-build-kit"' "$LISTING" || \
  fail "Claude did not install the AI Build Kit plugin"
grep -qF '"version": "0.2.0"' "$LISTING" || \
  fail "Claude installed the wrong plugin version"
grep -qF '"scope": "local"' "$LISTING" || \
  fail "Claude did not keep the plugin local to the project"
grep -qF 'Skills (5)  change-triage, clarify, screen-check, second-opinion, section-builder' \
  "$DETAILS" || fail "Claude did not keep the plugin command and discipline boundaries separate"

INSTALL_PATH=$(sed -n 's/^[[:space:]]*"installPath": "\([^"]*\)",$/\1/p' "$LISTING")
[ -n "$INSTALL_PATH" ] || fail "Claude did not report the plugin cache path"
BOOTSTRAP="$INSTALL_PATH/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
[ -x "$BOOTSTRAP" ] || fail "installed Claude plugin has no start bootstrap"

# The nine commands are checked where Claude reads them. Its details listing
# counts skills, agents, hooks and servers and says nothing about commands, so
# the installed manifest and the command files in the plugin cache are the only
# evidence that Claude offers all nine. A command carries no trigger setting,
# because the agent may start one when the person asks for it, so a command
# file still carrying the retired manual-only setting would put that command
# back out of reach in silence.
for word in fix implement maintain queue setup-ai-build-kit shape ship sync what-now; do
  grep -qF "\"./.claude/commands/$word.md\"" "$INSTALL_PATH/.claude-plugin/plugin.json" || \
    fail "installed Claude plugin manifest does not offer the command: $word"
  [ -f "$INSTALL_PATH/.claude/commands/$word.md" ] || \
    fail "installed Claude plugin has no command file for: $word"
  if grep -qF 'disable-model-invocation' "$INSTALL_PATH/.claude/commands/$word.md"; then
    fail "installed Claude command still carries the retired manual-only setting: $word"
  fi
done
grep -qF '${CLAUDE_PLUGIN_ROOT}/.agents/skills/setup-ai-build-kit/SKILL.md' \
  "$INSTALL_PATH/.claude/commands/setup-ai-build-kit.md" || \
  fail "installed start command does not load the plugin's canonical skill"
# Founding reads the recipe menu from the ship skill beside its own folder,
# which on this route is inside the plugin cache.
for recipe in "$ROOT"/.agents/skills/ship/recipes/*.md; do
  [ -f "$recipe" ] || continue
  [ -f "$INSTALL_PATH/.agents/skills/ship/recipes/$(basename -- "$recipe")" ] || \
    fail "installed Claude plugin lost a recipe founding offers: $(basename -- "$recipe")"
done
grep -qF 'user-invocable: false' \
  "$INSTALL_PATH/.claude/skills/change-triage/SKILL.md" || \
  fail "installed internal discipline is visible in Claude's command menu"
"$BOOTSTRAP" "$PROJECT" >/dev/null || \
  fail "installed Claude plugin could not prepare the project"
[ -f "$PROJECT/AGENTS.md" ] || fail "Claude plugin did not prepare project instructions"
[ -f "$PROJECT/.claude/settings.json" ] || \
  fail "Claude plugin did not prepare shared safety settings"
[ -f "$PROJECT/.claude/settings.local.json" ] || \
  fail "Claude did not record the local plugin installation"
[ ! -e "$PROJECT/.agents/skills" ] || \
  fail "Claude plugin copied a second skill installation into the project"
[ -x "$PROJECT/.agents/hooks/session-start.sh" ] || \
  fail "Claude plugin bootstrap did not prepare the project session hook"
grep -qF 'SessionStart' "$PROJECT/.claude/settings.json" || \
  fail "Claude plugin bootstrap did not wire the session hook"

# A missing marketplace must leave the installed version available. The
# person's project checkpoint does not cover Claude's external plugin cache.
mv "$MARKET" "$MARKET_OFFLINE"
if CLAUDE_CONFIG_DIR="$CONFIG" \
  claude plugin marketplace update ai-build-kit >/dev/null 2>&1; then
  fail "Claude updated the plugin from an unavailable marketplace"
fi
(
  cd "$PROJECT"
  CLAUDE_CONFIG_DIR="$CONFIG" claude plugin list --json > "$LISTING"
)
grep -qF '"version": "0.2.0"' "$LISTING" || \
  fail "a failed marketplace refresh removed the installed plugin version"
grep -qF '"enabled": true' "$LISTING" || \
  fail "a failed marketplace refresh disabled the installed plugin"
mv "$MARKET_OFFLINE" "$MARKET"

rm -R "$MARKET"
"$BUILDER" v0.2.1 "$MARKET" >/dev/null
CLAUDE_CONFIG_DIR="$CONFIG" claude plugin marketplace update ai-build-kit >/dev/null
(
  cd "$PROJECT"
  CLAUDE_CONFIG_DIR="$CONFIG" \
    claude plugin update ai-build-kit@ai-build-kit --scope local >/dev/null
  CLAUDE_CONFIG_DIR="$CONFIG" claude plugin list --json > "$LISTING"
)
grep -qF '"version": "0.2.1"' "$LISTING" || \
  fail "Claude plugin update did not install the later release"

(
  cd "$PROJECT"
  CLAUDE_CONFIG_DIR="$CONFIG" \
    claude plugin uninstall ai-build-kit@ai-build-kit --scope local -y >/dev/null
  CLAUDE_CONFIG_DIR="$CONFIG" claude plugin list --json > "$LISTING"
)
if grep -qF '"id": "ai-build-kit@ai-build-kit"' "$LISTING"; then
  fail "Claude plugin remained installed after removal"
fi

echo "claude-plugin.sh: all checks passed"
