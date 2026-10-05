#!/usr/bin/env sh
# Prepare the project-owned files that are needed before the start interview.

set -eu

SKILL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
FOUNDATION="$SKILL_ROOT/templates/foundation"

fail() {
  echo "AI Build Kit setup stopped: $1" >&2
  exit 1
}

case "$#" in
  0) PROJECT_ROOT=$(pwd -P) ;;
  1) PROJECT_ROOT=$1 ;;
  *) fail "usage: bootstrap-project.sh [project-folder]" ;;
esac

[ -d "$PROJECT_ROOT" ] || fail "project folder does not exist: $PROJECT_ROOT"
PROJECT_ROOT=$(CDPATH= cd -- "$PROJECT_ROOT" && pwd -P)
[ "$PROJECT_ROOT" != "/" ] || fail "choose a project folder, not the filesystem root"
if [ -n "${HOME:-}" ]; then
  home_root=$(CDPATH= cd -- "$HOME" 2>/dev/null && pwd -P || true)
  [ "$PROJECT_ROOT" != "$home_root" ] || fail "choose a project folder, not the home folder"
fi
[ "$PROJECT_ROOT" != "$SKILL_ROOT" ] || fail "choose the project folder, not the setup-ai-build-kit skill folder"

PLUGIN_ROOT=$(CDPATH= cd -- "$SKILL_ROOT/../../.." && pwd -P)
PLUGIN_MANIFEST="$PLUGIN_ROOT/.claude-plugin/plugin.json"
PLUGIN_INSTALLATION=no
if [ -f "$PLUGIN_MANIFEST" ] && [ ! -L "$PLUGIN_MANIFEST" ] && \
   grep -Eq '"name"[[:space:]]*:[[:space:]]*"ai-build-kit"' "$PLUGIN_MANIFEST" && \
   grep -Eq '"\./\.claude/commands/setup-ai-build-kit\.md"' "$PLUGIN_MANIFEST"; then
  PLUGIN_START="$PLUGIN_ROOT/.agents/skills/setup-ai-build-kit"
  if [ -d "$PLUGIN_START" ]; then
    PLUGIN_START=$(CDPATH= cd -- "$PLUGIN_START" && pwd -P)
    [ "$PLUGIN_START" != "$SKILL_ROOT" ] || PLUGIN_INSTALLATION=yes
  fi
fi

# An Agent Plugins installation puts this skill at <plugin>/skills/setup-ai-build-kit, with
# the plugin manifest beside the skills folder.
AGENT_PLUGIN_ROOT=$(CDPATH= cd -- "$SKILL_ROOT/../.." && pwd -P)
AGENT_PLUGIN_MANIFEST="$AGENT_PLUGIN_ROOT/plugin.json"
if [ "$PLUGIN_INSTALLATION" = "no" ] && \
   [ -f "$AGENT_PLUGIN_MANIFEST" ] && [ ! -L "$AGENT_PLUGIN_MANIFEST" ] && \
   grep -Fq 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json' \
     "$AGENT_PLUGIN_MANIFEST" && \
   grep -Eq '"name"[[:space:]]*:[[:space:]]*"ai-build-kit"' \
     "$AGENT_PLUGIN_MANIFEST" && \
   [ -f "$AGENT_PLUGIN_ROOT/skills/setup-ai-build-kit/SKILL.md" ]; then
  AGENT_PLUGIN_START=$(CDPATH= cd -- "$AGENT_PLUGIN_ROOT/skills/setup-ai-build-kit" && pwd -P)
  [ "$AGENT_PLUGIN_START" != "$SKILL_ROOT" ] || PLUGIN_INSTALLATION=yes
fi

# The shared skills installer puts a project's skills in one of two folders.
# Codex, Cursor, Gemini CLI and GitHub Copilot read .agents/skills. Claude Code
# alone reads .claude/skills, so choosing only Claude Code leaves nothing in
# .agents/skills. With several coding agents, one folder holds the skill and the
# other links to it, or holds a second copy of the same installation. A second
# copy is told from a different installation by comparing the two folders,
# since the installer's copy option makes both real folders.
note() {
  echo "AI Build Kit setup note: $1" >&2
}

INSTALLED_HERE=no
SAME_COPY=no
OTHER_INSTALLATION=no
DIFFERING_FOLDER=
for skills_folder in .agents/skills .claude/skills; do
  installed_start="$PROJECT_ROOT/$skills_folder/setup-ai-build-kit"
  [ -e "$installed_start" ] || [ -L "$installed_start" ] || continue
  # A link that leads nowhere, or a link loop, cannot be read at all. Passing
  # over it in silence would found the project beside a folder that fails every
  # coding agent that looks there.
  [ -d "$installed_start" ] || \
    fail "$skills_folder/setup-ai-build-kit is a broken link; remove it or install the kit again"
  if [ ! -f "$installed_start/SKILL.md" ]; then
    note "$skills_folder/setup-ai-build-kit is an empty folder. Founding carries on; the installer puts the skill there the next time it runs."
    continue
  fi
  resolved_start=$(CDPATH= cd -- "$installed_start" && pwd -P)
  if [ "$resolved_start" = "$SKILL_ROOT" ]; then
    INSTALLED_HERE=yes
  elif diff -rq "$installed_start" "$SKILL_ROOT" >/dev/null 2>&1; then
    SAME_COPY=yes
  else
    OTHER_INSTALLATION=yes
    DIFFERING_FOLDER=$skills_folder
  fi
done

# The running skill is whole, so a differing copy in the other folder does not
# stop founding. It means another coding agent reads a different version of
# the kit, which the person should hear about once.
if [ "$INSTALLED_HERE" = "yes" ] && [ "$OTHER_INSTALLATION" = "yes" ]; then
  note "$DIFFERING_FOLDER/setup-ai-build-kit differs from the copy running now, so another coding agent reads a different version of the kit. Founding carries on with this one; /maintain, or the installer's update, brings the two level."
fi

if [ "$INSTALLED_HERE" = "no" ]; then
  if [ "$OTHER_INSTALLATION" = "yes" ] || [ "$SAME_COPY" = "yes" ]; then
    [ "$PLUGIN_INSTALLATION" != "yes" ] || \
      fail "this project has both an installed AI Build Kit plugin and a separate AI Build Kit skill installation; keep one before running start"
    fail "the chosen project belongs to a different setup-ai-build-kit skill installation"
  fi
  [ "$PLUGIN_INSTALLATION" = "yes" ] || \
    fail "the chosen project does not contain this installed setup-ai-build-kit skill"
fi

validate_foundation_file() {
  source_relative=$1
  destination_relative=$2
  source_file="$FOUNDATION/$source_relative"
  destination_file="$PROJECT_ROOT/$destination_relative"

  [ -f "$source_file" ] && [ ! -L "$source_file" ] || \
    fail "foundation file is missing: $source_relative"

  relative_parent=$(dirname -- "$destination_relative")
  current_parent=$PROJECT_ROOT
  old_ifs=$IFS
  IFS=/
  for component in $relative_parent; do
    [ "$component" = "." ] && continue
    current_parent="$current_parent/$component"
    [ ! -L "$current_parent" ] || \
      fail "project path is redirected outside the project: $relative_parent"
    [ ! -e "$current_parent" ] || [ -d "$current_parent" ] || \
      fail "project path is not a folder: $relative_parent"
  done
  IFS=$old_ifs
}

while IFS='|' read -r source_relative destination_relative; do
  validate_foundation_file "$source_relative" "$destination_relative"
done <<'FOUNDATION_FILES'
AGENTS.md|AGENTS.md
README.md|README.md
CLAUDE.md|CLAUDE.md
GEMINI.md|GEMINI.md
copilot-instructions.md|.github/copilot-instructions.md
checks.yml|.github/workflows/checks.yml
claude-settings.json|.claude/settings.json
session-start.sh|.agents/hooks/session-start.sh
plan-refresh.sh|.agents/tools/plan-refresh.sh
gate.py|.agents/tools/gate.py
ready-lint.py|.agents/tools/ready-lint.py
area-map.py|.agents/tools/area-map.py
state-guard.sh|.agents/hooks/state-guard.sh
env.example|.env.example
gitignore|.gitignore
FOUNDATION_FILES

# The bar guard and the test guard it wraps ship in the section-builder skill,
# beside this one, so their paths climb out of the foundation folder to it.
# Every installation carries that skill. Where it is missing anyway, founding
# carries on without the two and says so once, and /maintain places them once
# the skill is there.
GUARD_FILES=
for guard_name in bar-guard.sh test-guard.sh; do
  guard_source="../../../section-builder/scripts/$guard_name"
  [ -e "$FOUNDATION/$guard_source" ] || continue
  validate_foundation_file "$guard_source" ".agents/tools/$guard_name"
  GUARD_FILES="$GUARD_FILES $guard_name"
done

# The area map lives in docs/working-rules.md. Its template sits beside the
# masterplan's rather than in the foundation folder, since founding fills it in,
# so it is checked and copied on its own, with the same rules.
RULES_TEMPLATE="$SKILL_ROOT/templates/working-rules.md"
RULES_FILE="$PROJECT_ROOT/docs/working-rules.md"
[ -f "$RULES_TEMPLATE" ] && [ ! -L "$RULES_TEMPLATE" ] || \
  fail "template file is missing: templates/working-rules.md"

# The build loop's limits live in .agents/loop-settings.json, which the person
# edits. Its template sits beside the masterplan's rather than in the
# foundation folder, so it is checked and copied on its own, with the same
# rules: a copy already there is the person's, and is kept.
LOOP_TEMPLATE="$SKILL_ROOT/templates/loop-settings.json"
LOOP_FILE="$PROJECT_ROOT/.agents/loop-settings.json"
[ -f "$LOOP_TEMPLATE" ] && [ ! -L "$LOOP_TEMPLATE" ] || \
  fail "template file is missing: templates/loop-settings.json"
[ ! -L "$PROJECT_ROOT/.agents" ] || fail "project path is redirected outside the project: .agents"
[ ! -e "$PROJECT_ROOT/.agents" ] || [ -d "$PROJECT_ROOT/.agents" ] || \
  fail "project path is not a folder: .agents"
[ ! -L "$PROJECT_ROOT/docs" ] || fail "project path is redirected outside the project: docs"
[ ! -e "$PROJECT_ROOT/docs" ] || [ -d "$PROJECT_ROOT/docs" ] || \
  fail "project path is not a folder: docs"

# A project the kit adopts may already run its tests on every pull request, in
# a workflow of its own. That workflow is then the project check, and the kit's
# checks.yml would only add a placeholder that fails on purpose beside it. A
# workflow counts when it runs on pull_request and has a run: line, or a line
# inside a run: block, containing the word test. A labeller runs on pull
# requests and tests nothing, and a workflow on push alone checks no pull
# request, so neither counts. checks.yml itself is left out: where it exists it
# is kept anyway, and the kit's own placeholder mentions tests.
runs_tests_on_pull_requests() {
  grep -q 'pull_request' "$1" || return 1
  awk '
    function indent(s) { match(s, /^[ \t-]*/); return RLENGTH }
    block && indent($0) <= block_indent && $0 !~ /^[ \t]*$/ { block = 0 }
    block && tolower($0) ~ /(^|[^a-z])(py)?test/ { found = 1 }
    /^[ \t-]*run:/ {
      rest = $0
      sub(/^[ \t-]*run:[ \t]*/, "", rest)
      if (rest ~ /^[|>]/) { block = 1; block_indent = indent($0) }
      else if (tolower(rest) ~ /(^|[^a-z])(py)?test/) { found = 1 }
    }
    END { exit found ? 0 : 1 }
  ' "$1"
}

own_ci=
if [ -d "$PROJECT_ROOT/.github/workflows" ] && [ ! -L "$PROJECT_ROOT/.github/workflows" ]; then
  for workflow in "$PROJECT_ROOT"/.github/workflows/*.yml "$PROJECT_ROOT"/.github/workflows/*.yaml; do
    [ -f "$workflow" ] || continue
    case "${workflow##*/}" in checks.yml) continue ;; esac
    if runs_tests_on_pull_requests "$workflow"; then
      own_ci=".github/workflows/${workflow##*/}"
      break
    fi
  done
fi

created=0
kept=0

copy_foundation_file() {
  source_relative=$1
  destination_relative=$2
  source_file="$FOUNDATION/$source_relative"
  destination_file="$PROJECT_ROOT/$destination_relative"

  if [ -e "$destination_file" ] || [ -L "$destination_file" ]; then
    kept=$((kept + 1))
    return
  fi

  # Beside the project's own CI, the kit's placeholder check is not copied.
  case "$source_relative" in
    checks.yml) [ -z "$own_ci" ] || return 0 ;;
  esac

  destination_parent=$(dirname -- "$destination_file")
  mkdir -p "$destination_parent"
  cp -p "$source_file" "$destination_file"
  created=$((created + 1))
}

while IFS='|' read -r source_relative destination_relative; do
  copy_foundation_file "$source_relative" "$destination_relative"
done <<'FOUNDATION_FILES'
AGENTS.md|AGENTS.md
README.md|README.md
CLAUDE.md|CLAUDE.md
GEMINI.md|GEMINI.md
copilot-instructions.md|.github/copilot-instructions.md
checks.yml|.github/workflows/checks.yml
claude-settings.json|.claude/settings.json
session-start.sh|.agents/hooks/session-start.sh
plan-refresh.sh|.agents/tools/plan-refresh.sh
gate.py|.agents/tools/gate.py
ready-lint.py|.agents/tools/ready-lint.py
area-map.py|.agents/tools/area-map.py
state-guard.sh|.agents/hooks/state-guard.sh
env.example|.env.example
gitignore|.gitignore
FOUNDATION_FILES

for guard_name in $GUARD_FILES; do
  copy_foundation_file "../../../section-builder/scripts/$guard_name" ".agents/tools/$guard_name"
done
[ "$GUARD_FILES" = " bar-guard.sh test-guard.sh" ] || \
  note "the section-builder skill is not installed beside this one, so the bar guard and the test guard were not placed in .agents/tools/. Founding carries on; /maintain places them once the skill is installed."

# The area map's file is copied with the same rule: a file already there is
# kept.
if [ -e "$RULES_FILE" ] || [ -L "$RULES_FILE" ]; then
  kept=$((kept + 1))
else
  mkdir -p "$PROJECT_ROOT/docs"
  cp "$RULES_TEMPLATE" "$RULES_FILE"
  created=$((created + 1))
fi

if [ -e "$LOOP_FILE" ] || [ -L "$LOOP_FILE" ]; then
  kept=$((kept + 1))
else
  mkdir -p "$PROJECT_ROOT/.agents"
  cp "$LOOP_TEMPLATE" "$LOOP_FILE"
  created=$((created + 1))
fi

[ -z "$own_ci" ] || \
  echo "AI Build Kit found $own_ci running this project's tests on pull requests, so the kit added no checks.yml beside it"
echo "AI Build Kit prepared $created project file(s) and kept $kept existing file(s)"
