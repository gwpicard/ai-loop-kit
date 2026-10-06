#!/usr/bin/env sh
# check-recipes.sh: check that each recipe file has the shape the format asks for.
#
# The format lives in .agents/skills/ship/references/recipe-format.md. A recipe
# is only worth offering if every one of the eight sections says how it works,
# how anybody would know it did, and who runs that check, and if the file
# carries the dates that say when it was last read and when it was really run.
# A missing section is easy to miss by eye and costs the person a launch step
# nobody can check, so a machine reads for it.
#
# Usage:
#   check-recipes.sh [--template] FILE...
#   check-recipes.sh --part FILE...
#   check-recipes.sh --rehearsal RECIPE REHEARSAL
#
# A recipe may add one section to the eight, "## Settings the kit can read",
# between health and the proven section. When it is there, it is held to the
# same three lines as the others, and the proven section gives it an outcome
# line.
#
# With --template the two dates may still read YYYY-MM-DD and "Who runs it:"
# may still be a placeholder, since the blank has nothing real to give. Every
# other rule applies to the blank as well, so it cannot drift away from the
# format it is copied from.
#
# With --part the file is a shared part from recipes/parts/, which holds the
# same three lines a section would and nothing else is asked of it.
#
# With --rehearsal the second file must be a real rehearsal for the first: it
# uses the shared rule-shape helper and names the recipe file. A rehearsal that
# only says `exit 0` would otherwise count as proof.
#
# Prints each problem and exits 1 when any file has one. Writes nothing.

set -eu

mode=recipe
case "${1:-}" in
  --template) mode=template; shift ;;
  --part) mode=part; shift ;;
  --rehearsal) mode=rehearsal; shift ;;
esac

[ "$#" -gt 0 ] || { echo "usage: check-recipes.sh [--template|--part] FILE... | --rehearsal RECIPE REHEARSAL" >&2; exit 2; }

if [ "$mode" = rehearsal ]; then
  [ "$#" -eq 2 ] || { echo "usage: check-recipes.sh --rehearsal RECIPE REHEARSAL" >&2; exit 2; }
  name=$(basename -- "$1")
  if [ ! -f "$2" ]; then
    echo "$1: no rehearsal guards it; add $2"
    exit 1
  fi
  status=0
  if ! grep -Eq '^[[:space:]]*\.[[:space:]].*lib/rule-shape\.sh' "$2"; then
    echo "$2: does not source lib/rule-shape.sh, so it cannot prove the recipe's rules are load-bearing"
    status=1
  fi
  if ! grep -qF "recipes/$name" "$2"; then
    echo "$2: does not name the recipe file recipes/$name"
    status=1
  fi
  exit "$status"
fi

today=$(date +%Y-%m-%d)
status=0

for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "$file: no such file"
    status=1
    continue
  fi
  awk -v mode="$mode" -v today="$today" -v file="$file" -v dir="$(dirname -- "$file")" '
    function problem(msg) { print file ": " msg; bad = 1 }
    function realdate(v,   y, m, d, days) {
      if (v !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return 0
      y = substr(v, 1, 4) + 0; m = substr(v, 6, 2) + 0; d = substr(v, 9, 2) + 0
      if (m < 1 || m > 12 || d < 1) return 0
      days = 31
      if (m == 4 || m == 6 || m == 9 || m == 11) days = 30
      if (m == 2) days = ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) ? 29 : 28
      return d <= days
    }
    function datecheck(label, value) {
      if (mode == "template" && value == "YYYY-MM-DD") return
      if (!realdate(value)) problem(label " is not a real date written YYYY-MM-DD: " value)
      else if (value > today) problem(label " is in the future: " value)
    }
    # An optional opening line. The terms of a plan change without notice, so the
    # line has to say when they were read and where, or nobody can tell a
    # stale restriction from a current one.
    function planterms(line) {
      if (!match(line, /^Plan terms: [^(]+ \(read [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] at [^)]+\)$/)) {
        problem("\"Plan terms:\" does not read as a sentence ending \"(read YYYY-MM-DD at <source page>)\"")
        return
      }
      match(line, /\(read [0-9-]+ at /)
      datecheck("Plan terms", substr(line, RSTART + 6, 10))
    }
    function whocheck(where, value) {
      if (mode == "template" && value ~ /^</) return 1
      if (value == "the kit" || value == "a companion or the person, result read back" || value == "a person looking") return 1
      problem(where " says \"Who runs it: " value "\", which is not one of: the kit; a companion or the person, result read back; a person looking")
      return 1
    }
    # One line of a section, or of a part, recorded under key.
    function body(key, line, where) {
      if (line ~ /^How it works: ./) works[key] = 1
      else if (line ~ /^How it is checked: ./) checked[key] = 1
      else if (line ~ /^Who runs it:/) { who[key] = 1; whocheck(where, substr(line, 14)) }
    }
    function lacks(key, where) {
      if (!(key in works)) problem(where " does not say \"How it works:\"")
      if (!(key in checked)) problem(where " does not say \"How it is checked:\"")
      if (!(key in who)) problem(where " does not say \"Who runs it:\"")
    }
    # A section carries its three lines, written out or in the part it links.
    function section_lines(s,   path, line) {
      if (s in part) {
        path = dir "/" part[s]; line = ""
        if ((getline line < path) < 0) { problem("\"## " s "\" links a shared part that does not exist: " part[s]); return }
        do { body(s, line, part[s]) } while ((getline line < path) > 0)
        close(path)
        lacks(s, part[s] " (linked from \"## " s "\")")
      } else {
        lacks(s, "\"## " s "\"")
      }
    }
    BEGIN {
      n = split("Preview|Going live|Rollback|Backup|Restore|Secrets|Logs|Health|Proven", order, "|")
      extra = "Settings the kit can read"
      for (i = 1; i <= n; i++) want[order[i]] = i
    }
    mode == "part" { body("part", $0, "the part"); next }
    /^## / {
      section = substr($0, 4)
      if (section in want) { seen[section] = 1; pos[section] = ++count }
      # The one section a recipe may add to the eight. It sits after health.
      if (section == extra) { hasextra = 1; extrapos = count }
      next
    }
    section == "" && /^Fits: ./             { head["Fits"] = 1 }
    section == "" && /^Recommended when: ./ { head["Recommended when"] = 1 }
    section == "" && /^Build stack: ./      { head["Build stack"] = 1 }
    section == "" && /^Deploy target: ./    { head["Deploy target"] = 1 }
    section == "" && /^Command-line tools: ./ { head["Command-line tools"] = 1 }
    section == "" && /^Last checked:/       { head["Last checked"] = 1; datecheck("Last checked", substr($0, 15)) }
    section == "" && /^Plan terms:/         { planterms($0) }
    section == "Proven" && /^Real run:/     { realrun = 1; datecheck("Real run", substr($0, 11)); next }
    section == "Proven" {
      for (i = 1; i < n; i++)
        if (index($0, order[i] ": ") == 1 && length($0) > length(order[i]) + 2) outcome[order[i]] = 1
      if (index($0, extra ": ") == 1 && length($0) > length(extra) + 2) outcome[extra] = 1
      next
    }
    section != "" && /^Shared part: / {
      link = $0
      if (match(link, /\]\(parts\/[A-Za-z0-9_.-]+\.md\)/)) part[section] = substr(link, RSTART + 2, RLENGTH - 3)
      else problem("\"## " section "\" has a shared part that is not a link into parts/")
      next
    }
    section != "" { body(section, $0, "\"## " section "\"") }
    END {
      if (mode == "part") { lacks("part", "the part"); exit bad }
      split("Fits|Recommended when|Build stack|Deploy target|Command-line tools|Last checked", heads, "|")
      for (i = 1; i <= 6; i++)
        if (!(heads[i] in head)) problem("the opening lines lack \"" heads[i] ":\"")
      for (i = 1; i <= n; i++) {
        s = order[i]
        if (!(s in seen)) { problem("no \"## " s "\" section"); continue }
        if (pos[s] != i) problem("\"## " s "\" is out of order")
        if (s == "Proven") continue
        section_lines(s)
      }
      if (hasextra) {
        if (extrapos != 8) problem("\"## " extra "\" does not sit between \"## Health\" and \"## Proven\"")
        section_lines(extra)
      }
      if ("Proven" in seen) {
        if (!realrun) problem("\"## Proven\" does not open with \"Real run:\" and a date")
        for (i = 1; i < n; i++)
          if (!(order[i] in outcome)) problem("\"## Proven\" has no outcome line for " order[i])
        if (hasextra && !(extra in outcome)) problem("\"## Proven\" has no outcome line for " extra)
      }
      exit bad
    }
  ' "$file" || status=1
done

exit "$status"
