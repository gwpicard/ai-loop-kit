#!/usr/bin/env sh
# long-instructions.sh: pad a replay project's AGENTS.md to exactly 240 lines.
#
# Scenario 49 needs standing instructions past their 200-line ceiling, carrying
# the kind of content the monthly visit offers to trim: a folder layout. The
# case used to ask the kit to write it, and the kit rightly refused, because
# AGENTS.md itself forbids a directory layout. So the harness writes it here,
# before the project's first commit, and the conversation starts at /maintain.
#
# Every added line names a file that is really on disk, so the layout is true.
# The original instructions are left exactly as they were.
#
# Usage: long-instructions.sh <project-dir>

set -eu

project=${1:?project directory}
file="$project/AGENTS.md"
target=240

[ -f "$file" ] || { echo "long-instructions.sh: no AGENTS.md in $project" >&2; exit 1; }

have=$(wc -l < "$file" | tr -d ' ')
# A blank line, a heading and a blank line come before the entries.
need=$((target - have - 3))
[ "$need" -gt 0 ] || { echo "long-instructions.sh: AGENTS.md already has $have lines" >&2; exit 1; }

entries=$(cd "$project" && find . -type f ! -path './.git/*' ! -name AGENTS.md \
  | sed 's|^\./||' | LC_ALL=C sort | head -n "$need")
count=$(printf '%s\n' "$entries" | grep -c . || true)
[ "$count" -eq "$need" ] || { echo "long-instructions.sh: only $count files to describe, $need needed" >&2; exit 1; }

{
  printf '\n## Folder layout\n\n'
  printf '%s\n' "$entries" | sed 's|^\(.*\)$|- `\1`: part of the project.|'
} >> "$file"

got=$(wc -l < "$file" | tr -d ' ')
[ "$got" -eq "$target" ] || { echo "long-instructions.sh: AGENTS.md has $got lines, not $target" >&2; exit 1; }
