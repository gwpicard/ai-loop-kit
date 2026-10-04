#!/usr/bin/env sh
# agent-plugin.sh: rehearse the Agent Plugins distribution route. It builds a
# real release, checks the assembled folder against the standard's rules,
# checks that the one trigger setting marks the five background skills and
# none of the nine commands, and proves that folder can stand a project up on
# its own.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"
SCHEMA="https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}
note() {
  echo "NOTE: $1" >&2
}

[ -x "$BUILDER" ] || fail "release builder is missing or not executable"

SCRATCH=$(mktemp -d)
cleanup() {
  rm -R "$SCRATCH"
}
trap cleanup EXIT

PACK="$SCRATCH/pack"
INSTALLED="$SCRATCH/installed/ai-build-kit"
PROJECT="$SCRATCH/project"
DUPLICATE="$SCRATCH/duplicate"
"$BUILDER" v0.3.0 "$PACK" >/dev/null

PLUGIN="$PACK/agent-plugin"
MANIFEST="$PLUGIN/plugin.json"
SKILLS_DIR="$PLUGIN/skills"

expected_commands="fix
implement
maintain
shape
queue
setup-ai-build-kit
ship
sync
what-now"

expected_disciplines="change-triage
clarify
screen-check
second-opinion
section-builder"

# --- the plugin directory and its manifest -------------------------------
[ -d "$PLUGIN" ] || fail "the release does not contain the agent-plugin folder"
[ -f "$MANIFEST" ] || fail "the agent plugin has no plugin.json at its root"
[ ! -L "$MANIFEST" ] || fail "the agent plugin manifest is a link rather than a file"

grep -qF "\"\$schema\": \"$SCHEMA\"" "$MANIFEST" || \
  fail "the agent plugin manifest does not declare the 1.0.0 schema"
grep -qF '"name": "ai-build-kit"' "$MANIFEST" || \
  fail "the agent plugin manifest does not carry the kit's name"
grep -qF '"version": "0.3.0"' "$MANIFEST" || \
  fail "the agent plugin version does not match the release"
if grep -qF '0.0.0-development' "$MANIFEST"; then
  fail "the agent plugin manifest kept its development version placeholder"
fi

# Fields the standard does not define, named individually because these three
# are exactly what the Claude manifest carries and must never be copied here.
for forbidden in '"displayName"' '"commands"' '"skills"' '.claude/'; do
  if grep -qF "$forbidden" "$MANIFEST"; then
    fail "the agent plugin manifest carries something the standard does not define: $forbidden"
  fi
done

# --- the closed field set, checked properly when python3 is available ----
if command -v python3 >/dev/null 2>&1; then
  CHECKER="$SCRATCH/check-manifest.py"
  cat > "$CHECKER" <<'PYEOF'
import json, re, sys

ALLOWED = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

errors = []
manifest = json.load(open(sys.argv[1]))
if not isinstance(manifest, dict):
    errors.append("plugin.json is not a JSON object")
    manifest = {}

extra = sorted(set(manifest) - ALLOWED)
if extra:
    errors.append("fields the standard does not define: %s" % ", ".join(extra))

if manifest.get("$schema") != SCHEMA:
    errors.append("$schema is not the 1.0.0 schema: %r" % manifest.get("$schema"))

name = manifest.get("name")
if not isinstance(name, str):
    errors.append("name is missing or is not text")
elif (not 1 <= len(name) <= 64
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", name)
        or "--" in name or ".." in name):
    errors.append("name is not a valid plugin name: %r" % name)

author = manifest.get("author")
if author is not None:
    if (not isinstance(author, dict)
            or set(author) - {"name", "email", "url"}
            or not all(isinstance(v, str) for v in author.values())):
        errors.append("author may carry only text name, email, and url")

keywords = manifest.get("keywords")
if keywords is not None and (not isinstance(keywords, list)
        or not all(isinstance(k, str) for k in keywords)):
    errors.append("keywords must be a list of text values")

# The schema requires each namespace to hold an object and assigns no meaning
# to its contents. The reverse-domain shape is the spec's own convention, kept
# here as a house rule so a future namespace cannot be a bare word.
extensions = manifest.get("extensions")
if extensions is not None:
    if not isinstance(extensions, dict):
        errors.append("extensions must be an object")
    else:
        for key, value in extensions.items():
            if not re.fullmatch(r"[a-z0-9]+(?:\.[a-z0-9-]+)+", key):
                errors.append("extension namespace is not reverse-domain: %r" % key)
            if not isinstance(value, dict):
                errors.append("extension %r does not hold an object" % key)

for field in ("version", "description", "homepage", "repository", "license"):
    if field in manifest and not isinstance(manifest[field], str):
        errors.append("%s must be text" % field)

for line in errors:
    print(line)
sys.exit(1 if errors else 0)
PYEOF
  if ! python3 "$CHECKER" "$MANIFEST" > "$SCRATCH/manifest-report.txt" 2>&1; then
    fail "the agent plugin manifest does not match the standard: $(tr '\n' ';' < "$SCRATCH/manifest-report.txt")"
  fi
else
  note "python3 is unavailable; checked the manifest against the named field rules only"
fi

# --- no maintainer skill ships --------------------------------------------
# The names are read off .agents/maintainer-skills/ rather than written here,
# because a written-out name is what this check carried when there was one
# maintainer skill, and the second one arrived unguarded. The match is an exact
# folder or file name, so a passing mention of a skill in some document's prose
# does not count as a copy of it. It runs before the skill count so that a
# leaked skill is named as the cause rather than reported as a wrong count.
maintainer_skill_names=$(find "$ROOT/.agents/maintainer-skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
  | while IFS= read -r skill_dir; do basename -- "$skill_dir"; done)
[ -n "$maintainer_skill_names" ] || \
  fail "no maintainer skill folder could be read, so none was checked against the agent plugin"
for name in $maintainer_skill_names; do
  if find "$PLUGIN" \( -name "$name" -o -name "$name.md" \) | grep -q .; then
    fail "a maintainer skill reached the agent plugin: $name"
  fi
done

# --- skills discovery, exactly as a client performs it ------------------
[ -d "$SKILLS_DIR" ] || fail "the agent plugin has no skills folder"

expected_skills=$(printf '%s\n%s\n' "$expected_commands" "$expected_disciplines" | sort)
found_skills=$(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
if [ "$found_skills" != "$expected_skills" ]; then
  fail "the agent plugin does not expose exactly the fourteen installable skills"
fi

while IFS= read -r skill; do
  [ -n "$skill" ] || continue
  [ -f "$SKILLS_DIR/$skill/SKILL.md" ] || \
    fail "a skill folder in the agent plugin has no SKILL.md a client would read: $skill"
  [ ! -L "$SKILLS_DIR/$skill/SKILL.md" ] || \
    fail "a skill in the agent plugin points at a link rather than a file: $skill"
  grep -q "^name: $skill\$" "$SKILLS_DIR/$skill/SKILL.md" || \
    fail "a skill in the agent plugin does not declare its own folder name: $skill"
done <<SKILLNAMES
$expected_skills
SKILLNAMES

deep=$(find "$SKILLS_DIR" -mindepth 3 -name SKILL.md)
[ -z "$deep" ] || \
  fail "the agent plugin hides a skill below the one level a client reads: $deep"

# --- the one trigger setting marks the disciplines and nothing else -------
# A background skill carries `user-invocable: false` and a command carries no
# trigger setting at all, because the agent may start a command when the
# person asks for it. The manifest used to name the commands under a vendor
# extension as well, but no client read it, so the SKILL.md files are the only
# place the boundary lives and the only place worth checking. The retired
# manual-only setting is refused on a command because a copy of it would put
# that command back out of the agent's reach in silence.
while IFS= read -r discipline; do
  [ -n "$discipline" ] || continue
  grep -Eq '^user-invocable:[ \t]*false' "$SKILLS_DIR/$discipline/SKILL.md" || \
    fail "a background skill in the agent plugin is missing the setting that keeps it out of the person's hands: $discipline"
done <<DISCIPLINES
$expected_disciplines
DISCIPLINES

while IFS= read -r word; do
  [ -n "$word" ] || continue
  if grep -Eq '^user-invocable:[ \t]*false' "$SKILLS_DIR/$word/SKILL.md"; then
    fail "a command in the agent plugin is marked as a background skill: $word"
  fi
  if grep -qF 'disable-model-invocation' "$SKILLS_DIR/$word/SKILL.md"; then
    fail "a command in the agent plugin still carries the retired manual-only setting: $word"
  fi
done <<WORDS
$expected_commands
WORDS

# --- each skill arrived whole, and identical to the canonical release ----
for supporting in \
  setup-ai-build-kit/scripts/bootstrap-project.sh \
  setup-ai-build-kit/templates/foundation/AGENTS.md \
  setup-ai-build-kit/references/fit-check.md \
  ship/templates/handover.md \
  ship/templates/recipe.md \
  ship/references/recipe-format.md \
  implement/references/running-longer.md \
  change-triage/references/source-check.md; do
  [ -f "$SKILLS_DIR/$supporting" ] || \
    fail "the agent plugin lost a file one of its skills needs: $supporting"
done
# Founding reads the recipe menu from the ship skill beside its own folder, so
# every recipe on the menu has to arrive there, and no shared part may be
# mistaken for a menu entry by arriving loose beside them.
for recipe in "$ROOT"/.agents/skills/ship/recipes/*.md; do
  [ -f "$recipe" ] || continue
  [ -f "$SKILLS_DIR/ship/recipes/$(basename -- "$recipe")" ] || \
    fail "the agent plugin lost a recipe founding offers: $(basename -- "$recipe")"
done
for part in "$ROOT"/.agents/skills/ship/recipes/parts/*.md; do
  [ -f "$part" ] || continue
  [ -f "$SKILLS_DIR/ship/recipes/parts/$(basename -- "$part")" ] || \
    fail "the agent plugin lost a shared recipe part: $(basename -- "$part")"
done
cmp -s "$SKILLS_DIR/setup-ai-build-kit/SKILL.md" "$PACK/.agents/skills/setup-ai-build-kit/SKILL.md" || \
  fail "the agent plugin's setup-ai-build-kit skill differs from the released canonical skill"

# --- nothing new at the release root ------------------------------------
[ ! -e "$PACK/skills" ] || \
  fail "the release exposes a second skills folder at its top level"
[ ! -e "$PACK/plugin.json" ] || \
  fail "the release exposes an agent plugin manifest at its top level"

# --- the Claude route is untouched and still complete -------------------
grep -qF '"./.claude/commands/setup-ai-build-kit.md"' "$PACK/.claude-plugin/plugin.json" || \
  fail "the Claude plugin manifest stopped selecting the nine manual commands"
grep -qF '"./.claude/skills/section-builder"' "$PACK/.claude-plugin/plugin.json" || \
  fail "the Claude plugin manifest stopped selecting the internal disciplines"
grep -qF '"version": "0.3.0"' "$PACK/.claude-plugin/plugin.json" || \
  fail "the Claude plugin version no longer matches the release"

# --- the folder stands a project up on its own -------------------------
# The folder is copied out on its own first, which is how a client installs it.
# Run from inside the release folder instead and the Claude plugin manifest one
# level up would be found, so this route's own recognition would go unchecked.
mkdir -p "$(dirname -- "$INSTALLED")"
cp -R "$PLUGIN" "$INSTALLED"
[ ! -e "$(dirname -- "$INSTALLED")/.claude-plugin" ] || \
  fail "the isolated plugin install is not isolated from the Claude plugin manifest"
BOOTSTRAP="$INSTALLED/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
[ -x "$BOOTSTRAP" ] || \
  fail "the agent plugin's setup-ai-build-kit skill has no runnable project bootstrap"

mkdir -p "$PROJECT"
"$BOOTSTRAP" "$PROJECT" >/dev/null || \
  fail "the agent plugin's setup-ai-build-kit skill could not prepare a blank project"
[ -f "$PROJECT/AGENTS.md" ] || \
  fail "the agent plugin did not prepare project instructions"
[ -f "$PROJECT/.claude/settings.json" ] || \
  fail "the agent plugin did not prepare shared safety settings"
[ ! -e "$PROJECT/.agents/skills" ] || \
  fail "the agent plugin copied a second skill installation into the project"

# --- and refuses a project that already has its own installation --------
mkdir -p "$DUPLICATE/.agents"
cp -R "$PACK/.agents/skills" "$DUPLICATE/.agents/skills"
if "$BOOTSTRAP" "$DUPLICATE" >/dev/null 2>&1; then
  fail "the agent plugin accepted a project that already has a separate installation"
fi
[ ! -e "$DUPLICATE/AGENTS.md" ] || \
  fail "the agent plugin wrote project files before reporting the duplicate installation"

echo "agent-plugin.sh: all checks passed"
