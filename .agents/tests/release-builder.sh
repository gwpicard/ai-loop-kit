#!/usr/bin/env sh
# release-builder.sh: prove that the maintainer source assembles one clean,
# repeatable starter without changing the source tree.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -x "$BUILDER" ] || fail "release builder is missing or not executable"

SCRATCH=$(mktemp -d)
MARKER="$ROOT/.claude/.release-builder-untracked-$$"
INSIDE_SOURCE="$ROOT/release-builder-inside-source-$$"
cleanup() {
  [ ! -e "$MARKER" ] || rm -f "$MARKER"
  [ ! -e "$INSIDE_SOURCE" ] || rm -R "$INSIDE_SOURCE"
  rm -R "$SCRATCH"
}
trap cleanup EXIT
FIRST="$SCRATCH/first"
SECOND="$SCRATCH/second"
MARKER_BUILD="$SCRATCH/marker-build"

if "$BUILDER" not-a-version "$FIRST" >/dev/null 2>&1; then
  fail "an invalid release version was accepted"
fi

if "$BUILDER" v0.1.0 "$INSIDE_SOURCE" >/dev/null 2>&1; then
  fail "builder accepted an output inside the maintainer source"
fi

printf '%s\n' "maintainer-only marker" > "$MARKER"
"$BUILDER" v0.1.0 "$MARKER_BUILD"
[ ! -e "$MARKER_BUILD/.claude/$(basename "$MARKER")" ] || \
  fail "an untracked file inside an approved folder crossed into the starter"
rm -f "$MARKER"

"$BUILDER" v0.1.0 "$FIRST"
"$BUILDER" v0.1.0 "$SECOND"

for required in \
  .agents/skills/setup-ai-build-kit/SKILL.md \
  .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh \
  .agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md \
  .agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh \
  .agents/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh \
  .agents/skills/setup-ai-build-kit/scripts/place-plan-helper.sh \
  .agents/skills/setup-ai-build-kit/templates/maintenance-record \
  .agents/skills/screen-check/SKILL.md \
  .agents/skills/ship/references/recipe-format.md \
  .agents/skills/ship/templates/recipe.md \
  .agents/skills/maintain/VERSION \
  .claude-plugin/plugin.json \
  .claude-plugin/marketplace.json \
  agent-plugin/plugin.json \
  agent-plugin/skills/screen-check/SKILL.md \
  agent-plugin/skills/setup-ai-build-kit/SKILL.md \
  agent-plugin/skills/setup-ai-build-kit/scripts/bootstrap-project.sh \
  agent-plugin/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh \
  .agents/guard/blocked-commands.md \
  .agents/tools/build-adapters.sh \
  .agents/hooks \
  .claude/settings.json \
  .github/copilot-instructions.md \
  SECURITY.md \
  .claude/commands/setup-ai-build-kit.md \
  .cursor/commands/setup-ai-build-kit.md \
  .gemini/commands/setup-ai-build-kit.toml \
  .github/ISSUE_TEMPLATE/bug-report.yml \
  .github/ISSUE_TEMPLATE/feature-request.yml \
  .github/ISSUE_TEMPLATE/config.yml \
  .github/workflows/checks.yml \
  AGENTS.md CONTRIBUTING.md README.md WORKFLOW.md CLAUDE.md GEMINI.md \
  docs/PHILOSOPHY.md docs/COMPATIBILITY.md docs/SOURCES.md \
  .ai-build-kit-version .env.example .gitignore LICENSE; do
  [ -e "$FIRST/$required" ] || fail "starter is missing $required"
done

for forbidden in \
  .ai-build-kit-maintenance \
  release-manifest.txt \
  docs/MAINTAINING.md \
  .github/release.yml \
  .github/release-drafter.yml \
  .github/workflows/release-drafter.yml \
  .agents/maintainer-skills \
  skills \
  plugin.json \
  .agents/tests \
  .agents/tools/finish-release-draft.sh \
  .agents/tools/stamp-version.sh \
  .agents/tools/rehearse-merged-tree.sh \
  .agents/tools/preflight-cutover.sh \
  .agents/tools/validate-kit.sh \
  .agents/tools/plan-refresh.sh \
  .agents/tools/build-release.sh; do
  [ ! -e "$FIRST/$forbidden" ] || fail "starter contains maintainer-only $forbidden"
done

# A maintainer skill is kept out of a project by living outside every folder an
# installer reads, so the copy to look for is one of those skills under a folder
# the release does ship. The names are read off the folder rather than written
# here: the first version of this list named the one maintainer skill that
# existed, and the second one arrived without the list noticing.
maintainer_skill_names=$(find "$ROOT/.agents/maintainer-skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
  | while IFS= read -r skill_dir; do basename -- "$skill_dir"; done)
[ -n "$maintainer_skill_names" ] || \
  fail "no maintainer skill folder could be read, so none was checked against the starter"
for name in $maintainer_skill_names; do
  for shipped in .agents/skills .claude/skills agent-plugin/skills; do
    [ ! -e "$FIRST/$shipped/$name" ] || \
      fail "starter contains maintainer-only $shipped/$name"
  done
done

[ "$(cat "$FIRST/.ai-build-kit-version")" = "v0.1.0" ] || \
  fail "starter version marker is wrong"
[ "$(cat "$FIRST/.agents/skills/maintain/VERSION")" = "v0.1.0" ] || \
  fail "installed maintain skill version is wrong"
grep -qF '"version": "0.1.0"' "$FIRST/.claude-plugin/plugin.json" || \
  fail "Claude plugin version does not match the release"
grep -qF '"./.claude/commands/setup-ai-build-kit.md"' "$FIRST/.claude-plugin/plugin.json" || \
  fail "Claude plugin does not load the nine manual commands"
grep -qF '"./.claude/skills/screen-check"' "$FIRST/.claude-plugin/plugin.json" || \
  fail "Claude plugin does not load the internal disciplines"
if grep -qF 'disable-model-invocation' "$FIRST/.claude/commands/setup-ai-build-kit.md"; then
  fail "Claude plugin start command still carries the retired manual-only setting"
fi
grep -qF '${CLAUDE_PLUGIN_ROOT}/.agents/skills/setup-ai-build-kit/SKILL.md' \
  "$FIRST/.claude/commands/setup-ai-build-kit.md" || \
  fail "Claude plugin start command does not load its canonical skill"
grep -qF '"source": "./"' "$FIRST/.claude-plugin/marketplace.json" || \
  fail "Claude marketplace does not publish the repository-root plugin"
grep -qF '"version": "0.1.0"' "$FIRST/agent-plugin/plugin.json" || \
  fail "agent plugin version does not match the release"
grep -qF 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json' \
  "$FIRST/agent-plugin/plugin.json" || \
  fail "agent plugin does not declare the open plugin standard"
agent_plugin_skill_count=$(find "$FIRST/agent-plugin/skills" -mindepth 2 -maxdepth 2 \
  -name SKILL.md | wc -l | tr -d ' ')
[ "$agent_plugin_skill_count" -eq 14 ] || \
  fail "agent plugin does not expose exactly fourteen installable skills"
[ "$(cat "$FIRST/agent-plugin/skills/maintain/VERSION")" = "v0.1.0" ] || \
  fail "agent plugin maintain skill version is wrong"
released_skill_count=$(find "$FIRST/.agents/skills" -mindepth 2 -maxdepth 2 \
  -name SKILL.md | wc -l | tr -d ' ')
[ "$released_skill_count" -eq 14 ] || \
  fail "release does not expose exactly fourteen installable skills"
cmp -s "$FIRST/AGENTS.md" \
  "$FIRST/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md" || \
  fail "released root instructions differ from start's foundation template"
cmp -s "$FIRST/.claude/settings.json" \
  "$FIRST/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json" || \
  fail "released Claude settings differ from start's foundation template"
grep -qF 'SessionStart' "$FIRST/.claude/settings.json" || \
  fail "released Claude settings do not wire the session hook"
[ -x "$FIRST/.agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh" ] || \
  fail "released session hook script is not executable"
grep -qF 'npx skills add gwpicard/ai-build-kit' "$FIRST/README.md" || \
  fail "starter README does not give the shared skills installation command"
grep -qF 'claude plugin install ai-build-kit@ai-build-kit --scope local' \
  "$FIRST/README.md" || \
  fail "starter README does not give the Claude plugin installation command"

checks="$FIRST/.github/workflows/checks.yml"
[ ! -e "$FIRST/.github/workflows/maintainer-branch-check.yml" ] || \
  fail "starter contains the maintainer-only branch validation fallback"
cmp -s "$checks" "$FIRST/.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml" || \
  fail "starter project check differs from start's foundation template"
grep -qF "project-check:" "$checks" || \
  fail "starter does not carry the project check"
if grep -qF "source-kit-validation" "$checks"; then
  fail "starter project check exposes maintainer validation"
fi

if grep -R -n -F "ai-build-kit-maintainer" "$FIRST" >/dev/null 2>&1; then
  fail "starter exposes the private maintainer repository"
fi

if ! diff -qr "$FIRST" "$SECOND" >/dev/null; then
  fail "two builds from the same source and version differ"
fi

if "$BUILDER" v0.1.0 "$FIRST" >/dev/null 2>&1; then
  fail "builder overwrote an existing output folder"
fi

echo "release-builder.sh: all checks passed"
