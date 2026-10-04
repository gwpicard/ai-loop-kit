#!/usr/bin/env sh
# one-recipe-menu.sh: leave one recipe on a replay project's menu.
#
# Scenario 51 founds with a menu of one recipe, the menu a real founding had on
# 25 September 2026 when it skipped the menu and the recipe's tool report. The
# kit now ships more than one recipe, so the harness takes the others out of
# the installed kit before the project's first commit. A whole copy of the kit
# carries the ship skill twice, once under `.agents/skills/` and once under
# `agent-plugin/skills/`, and both lose the same files, so whichever copy the
# kit reads, it finds the same menu.
#
# Only files directly in a `recipes/` folder are menu entries. The `parts/`
# folder is left alone, since the recipe that stays links to it.
#
# Usage: one-recipe-menu.sh <project-dir>

set -eu

project=${1:?project directory}
keep=nextjs-supabase-on-vercel.md

# The harness runs this before the project's first commit, so a folder already
# inside a git work tree is not a replay project. Refusing it means the script
# can never delete a recipe from the repository it lives in.
if git -C "$project" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "one-recipe-menu.sh: $project is inside a git work tree, so it is not a fresh replay project" >&2
  exit 1
fi

folders=$(find "$project" -path "$project/.git" -prune -o -type d -path '*/skills/ship/recipes' -print)
[ -n "$folders" ] || { echo "one-recipe-menu.sh: no ship recipes folder in $project" >&2; exit 1; }

printf '%s\n' "$folders" | while IFS= read -r folder; do
  [ -f "$folder/$keep" ] || { echo "one-recipe-menu.sh: $folder has no $keep" >&2; exit 1; }
  for recipe in "$folder"/*.md; do
    [ "$(basename -- "$recipe")" = "$keep" ] || rm -f "$recipe"
  done
  left=$(find "$folder" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')
  [ "$left" -eq 1 ] || { echo "one-recipe-menu.sh: $folder holds $left recipes, not 1" >&2; exit 1; }
done
