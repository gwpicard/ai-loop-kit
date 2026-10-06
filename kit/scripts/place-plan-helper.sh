#!/usr/bin/env sh
# place-plan-helper.sh: put the plan printout helper, the gate script, the
# ready-gate lint the gate calls, the area map script, the bar guard and the
# test guard it wraps, and the state guard hook into a founded project.
#
# Founding copies all seven in. The two guards ship in the section-builder
# skill, beside this one, and are copied from there. A project founded before one of them shipped
# inside this skill has no copy, or holds the older copy a whole copy of the
# kit carried, and an update only ever refreshes skills. So /maintain runs this
# on every visit, and this is how they reach such a project.
#
# It is safe to run again. A copy that already matches is left alone. A copy
# that differs is replaced, because all seven are the kit's machinery rather than
# the project's own work, and /maintain runs this only after its clean
# checkpoint, so the older copy stays in the project's saved history.
#
# Usage: place-plan-helper.sh [project-folder]
# With no folder, the current folder is the project.

set -eu

SKILL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
FOUNDATION="$SKILL_ROOT/templates/foundation"

# Each file this places: its path from this skill's foundation templates, where
# it goes in the project, and what it is called when this says what it did.
PLACED='plan-refresh.sh|.agents/tools/plan-refresh.sh|plan helper
gate.py|.agents/tools/gate.py|gate script
ready-lint.py|.agents/tools/ready-lint.py|ready-gate lint
area-map.py|.agents/tools/area-map.py|area map script
../../../section-builder/scripts/bar-guard.sh|.agents/tools/bar-guard.sh|bar guard
../../../section-builder/scripts/test-guard.sh|.agents/tools/test-guard.sh|test guard
state-guard.sh|.agents/hooks/state-guard.sh|state guard hook'

fail() {
  echo "AI Build Kit could not place the plan helper, gate script, ready-gate lint, area map script, bar guard, test guard and state guard hook: $1" >&2
  exit 1
}

case "$#" in
  0) PROJECT_ROOT=$(pwd -P) ;;
  1) PROJECT_ROOT=$1 ;;
  *) fail "usage: place-plan-helper.sh [project-folder]" ;;
esac

[ -d "$PROJECT_ROOT" ] || fail "project folder does not exist: $PROJECT_ROOT"
PROJECT_ROOT=$(CDPATH= cd -- "$PROJECT_ROOT" && pwd -P)
# A founded project has a masterplan. Without one this is not a project the kit
# founded, and writing into it would be a guess about somebody else's folder.
[ -f "$PROJECT_ROOT/masterplan.md" ] || \
  fail "this folder holds no masterplan.md, so it is not a founded project"

for part in .agents .agents/tools .agents/hooks; do
  [ ! -L "$PROJECT_ROOT/$part" ] || \
    fail "project path is redirected outside the project: $part"
  [ ! -e "$PROJECT_ROOT/$part" ] || [ -d "$PROJECT_ROOT/$part" ] || \
    fail "project path is not a folder: $part"
done

# The two guards come from the section-builder skill beside this one. Where it
# is not installed, they are left out and that is said, and the rest are placed.
missing_sibling() {
  [ "${1#../}" != "$1" ] && [ ! -e "$FOUNDATION/$1" ]
}
AVAILABLE=$(printf '%s\n' "$PLACED" | while IFS='|' read -r source target name; do
  missing_sibling "$source" || printf '%s|%s|%s\n' "$source" "$target" "$name"
done)
printf '%s\n' "$PLACED" | while IFS='|' read -r source target name; do
  if missing_sibling "$source"; then
    echo "$name: not placed, since the section-builder skill is not installed beside this one"
  fi
done
PLACED=$AVAILABLE

# Every source and destination is checked before anything is written, so a
# refusal for one never leaves the others placed.
while IFS='|' read -r source target name; do
  [ -f "$FOUNDATION/$source" ] && [ ! -L "$FOUNDATION/$source" ] || \
    fail "the installed skills carry no $name to copy"
  destination="$PROJECT_ROOT/$target"
  [ ! -L "$destination" ] || fail "$target is a link, so it was left alone"
  [ ! -e "$destination" ] || [ -f "$destination" ] || \
    fail "$target is not a file, so it was left alone"
done <<EOF
$PLACED
EOF

mkdir -p "$PROJECT_ROOT/.agents/tools" "$PROJECT_ROOT/.agents/hooks"

while IFS='|' read -r source target name; do
  source_file="$FOUNDATION/$source"
  destination="$PROJECT_ROOT/$target"
  if [ -f "$destination" ] && cmp -s "$source_file" "$destination"; then
    if [ -x "$destination" ]; then
      echo "$name: already current at $target"
    else
      chmod 755 "$destination"
      echo "$name: already current at $target, and made runnable again, which is a change to save"
    fi
    continue
  fi
  if [ -f "$destination" ]; then
    outcome="replaced a copy that differed at $target. Any change somebody made to it by hand was replaced too, and the earlier copy is in the checkpoint saved before this ran"
  else
    outcome="added $target"
  fi
  cp "$source_file" "$destination"
  chmod 755 "$destination"
  echo "$name: $outcome"
done <<EOF
$PLACED
EOF
