#!/usr/bin/env sh
# build-adapters.sh: regenerate the per-tool adapter files from the canonical
# skills in .agents/skills/. Run this after adding, renaming, or removing a
# skill. End users never run it; the output is committed so a fresh clone works
# in every tool straight away.
#
# Single source of truth: .agents/skills/<name>/SKILL.md
# Generated (thin) adapters, all pointing back at canonical:
#   .claude/commands/<name>.md       the nine commands as Claude Code slash commands
#   .claude/skills/<discipline>/      the five disciplines as auto-triggering skills
#   .cursor/commands/<name>.md        the nine commands as Cursor slash commands
#   .gemini/commands/<name>.toml      the nine commands as Gemini CLI slash commands
#
# A skill only the kit's own maintainers use lives under
# .agents/maintainer-skills/ and gets no adapter at all. A shared skills
# installer reads .agents/skills/ and .claude/skills/ and merges what it finds
# by the name in the frontmatter, so anything sitting in either folder is a
# skill somebody installs. Keeping the maintainer's writing skill out of both is
# what stops a project receiving a fifteenth.
#
# Codex, Cursor, and Gemini discover the canonical .agents/skills/ tree
# directly. Claude Code needs its project skill under .claude/skills/.
#
# Adapters carry only what each tool must index locally (the description) and
# defer the body to the canonical file, so editing a skill means editing one
# file. Not touched here: .claude/settings.json (hand-maintained deny list).
#
# Usage:
#   build-adapters.sh          regenerate the adapters in place (the normal use).
#   build-adapters.sh --check  generate into a scratch directory and diff
#                               against what's committed, without touching the
#                               real adapter trees. Exits non-zero on drift.
#                               Used by CI and validate-kit.sh so a stale,
#                               hand-edited, or forgotten-to-regenerate adapter
#                               fails the build instead of shipping quietly.
#
# POSIX sh, no dependencies beyond awk/sed/grep/find/sort/diff.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SKILLS="$ROOT/.agents/skills"
GENERATED_DIRS="commands skills"

CHECK=0
case "${1:-}" in
  --check) CHECK=1 ;;
  "") ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

[ -d "$SKILLS" ] || { echo "error: $SKILLS not found" >&2; exit 1; }

# Read one frontmatter field from a SKILL.md file. Fold a YAML block scalar
# into one line so portable upstream skills can supply a longer description.
field() {
  # $1 = field name, $2 = file
  awk -v k="$1" '
    /^---[ \t]*$/ { fm++; next }
    fm==1 {
      if (block) {
        if ($0 ~ /^[ \t]+/) {
          sub(/^[ \t]+/, "")
          printf "%s%s", separator, $0
          separator=" "
          next
        }
        print ""
        exit
      }
      if ($0 ~ "^" k ":[ \t]") {
        sub("^" k ":[ \t]*", "")
        if ($0 == "|" || $0 == ">") { block=1; next }
        print
        exit
      }
    }
    END { if (block) print "" }
  ' "$2"
}

# Generate the full adapter tree under $1 (either $ROOT for a real run, or a
# scratch directory for --check). Prints the count of commands and disciplines
# generated on fd 3, so the caller can validate the inventory without a second
# parsing pass over the skills.
generate_all() {
  OUT="$1"

  rm -rf \
    "$OUT/.claude/commands" "$OUT/.claude/skills" \
    "$OUT/.cursor/commands" \
    "$OUT/.gemini/commands"
  mkdir -p \
    "$OUT/.claude/commands" "$OUT/.claude/skills" \
    "$OUT/.cursor/commands" \
    "$OUT/.gemini/commands"

  commands=0
  disciplines=0

  for dir in $(find "$SKILLS" -mindepth 1 -maxdepth 1 -type d | sort); do
    name=$(basename "$dir")
    file="$dir/SKILL.md"
    [ -f "$file" ] || continue

    fm_name=$(field name "$file")
    desc=$(field description "$file")
    # A skipped skill still leaves a self-consistent tree, so the drift check
    # passes and the skill is simply absent everywhere. Stopping is the same
    # answer a mismatched name already gets three lines below.
    [ -n "$desc" ] || {
      echo "error: $name/SKILL.md has no description, which every adapter needs" >&2
      exit 1
    }
    if [ "$fm_name" != "$name" ]; then
      echo "error: $name/SKILL.md declares name '$fm_name', which does not match its folder" >&2
      exit 1
    fi
    # First sentence, for short help strings.
    short=$(printf '%s' "$desc" | sed 's/\([^.]*\.\).*/\1/')
    # TOML-safe: escape backslash and double-quote for the description string.
    short_toml=$(printf '%s' "$short" | sed 's/\\/\\\\/g; s/"/\\"/g')

    # One setting marks a background skill. A SKILL.md carrying
    # 'user-invocable: false' is a discipline another skill calls. A skill
    # without that line is a command, which the agent may start when the
    # person types it, names it, or asks for its job in plain words. Nothing
    # else is declared, so a dropped user-invocable line cannot hide: it shows
    # up as ten commands and three disciplines and stops the build at the
    # count check below.
    if grep -q '^user-invocable:[ \t]*false' "$file"; then
      kind=discipline
      disciplines=$((disciplines + 1))
    else
      kind=command
      commands=$((commands + 1))
    fi

    claude_banner="<!-- GENERATED from .agents/skills/$name/. Do not edit here; regenerate with .agents/tools/build-adapters.sh -->"

    if [ "$kind" = command ]; then
      # Claude Code slash command
      {
        printf '%s\n' "---"
        printf 'description: %s\n' "$short"
        printf '%s\n' "---"
        printf '%s\n\n' "$claude_banner"
        printf 'When this command comes from a Claude plugin, load and follow `${CLAUDE_PLUGIN_ROOT}/.agents/skills/%s/SKILL.md`. Otherwise, load and follow `.agents/skills/%s/SKILL.md`. It is the single source of truth for the `/%s` command. Treat anything typed after the command as the user'"'"'s request and pass it through unchanged.\n' "$name" "$name" "$name"
      } > "$OUT/.claude/commands/$name.md"

      # Cursor slash command
      {
        printf '%s\n\n' "$claude_banner"
        printf 'Load and follow `.agents/skills/%s/SKILL.md`, the single source of truth for the `/%s` command. Treat anything typed after the command as the user'"'"'s request and pass it through unchanged.\n' "$name" "$name"
      } > "$OUT/.cursor/commands/$name.md"

      # Gemini CLI slash command (TOML)
      {
        printf '# GENERATED from .agents/skills/%s/. Do not edit here.\n' "$name"
        printf '# Regenerate with .agents/tools/build-adapters.sh\n'
        printf 'description = "%s"\n' "$short_toml"
        printf 'prompt = """\n'
        printf 'Load and follow the instructions in `.agents/skills/%s/SKILL.md`, the single source of truth for the /%s command.\n' "$name" "$name"
        printf 'Treat the following as the user'"'"'s request (it may be empty): {{args}}\n'
        printf '"""\n'
      } > "$OUT/.gemini/commands/$name.toml"
    else
      # Claude Code auto-triggering skill (disciplines only), hidden from the
      # user command menu but still available for a command to compose.
      mkdir -p "$OUT/.claude/skills/$name"
      {
        printf '%s\n' "---"
        printf 'name: %s\n' "$name"
        printf 'description: %s\n' "$desc"
        printf 'user-invocable: false\n'
        printf '%s\n' "---"
        printf '%s\n\n' "$claude_banner"
        printf 'When this skill comes from a Claude plugin, load and follow `${CLAUDE_PLUGIN_ROOT}/.agents/skills/%s/SKILL.md`. Otherwise, load and follow `.agents/skills/%s/SKILL.md`. It is the single source of truth for this skill.\n' "$name" "$name"
      } > "$OUT/.claude/skills/$name/SKILL.md"
    fi
  done

  if [ "$commands" -ne 9 ] || [ "$disciplines" -ne 5 ]; then
    echo "error: expected 9 commands and 5 disciplines; found $commands and $disciplines" >&2
    exit 1
  fi

  echo "$commands $disciplines" >&3
}

if [ "$CHECK" -eq 1 ]; then
  SCRATCH=$(mktemp -d)
  trap 'rm -rf "$SCRATCH"' EXIT

  counts=$(generate_all "$SCRATCH" 3>&1 1>&2)
  read -r commands disciplines <<EOF
$counts
EOF

  drift=0
  for d in .claude/commands .claude/skills .cursor/commands .gemini/commands; do
    if ! diff -rq "$ROOT/$d" "$SCRATCH/$d" >/tmp/adapter-check-diff.$$ 2>&1; then
      echo "drift in $d:" >&2
      cat /tmp/adapter-check-diff.$$ >&2
      drift=1
    fi
    rm -f /tmp/adapter-check-diff.$$
  done

  if [ "$drift" -ne 0 ]; then
    echo "error: committed adapters do not match what .agents/skills/ generates. Run .agents/tools/build-adapters.sh and commit the result." >&2
    exit 1
  fi

  echo "adapters match: $commands commands, $disciplines disciplines, no drift"
  exit 0
fi

counts=$(generate_all "$ROOT" 3>&1 1>&2)
read -r commands disciplines <<EOF
$counts
EOF

echo "Regenerated adapters for $((commands + disciplines)) skills ($commands commands, $disciplines disciplines) into .claude/ .cursor/ .gemini/"
echo "Generated files:"
find "$ROOT/.claude/commands" "$ROOT/.claude/skills" "$ROOT/.cursor/commands" "$ROOT/.gemini/commands" -type f | sed "s|^$ROOT/||" | sort
