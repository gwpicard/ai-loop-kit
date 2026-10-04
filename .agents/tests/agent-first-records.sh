#!/usr/bin/env sh
# agent-first-records.sh: guard the founded AGENTS.md as a short index, the
# route each lasting fact takes to its one home, and the ceiling the project's
# own check holds.
#
# In a real project the founded AGENTS.md grew from 206 lines to 1,019. The
# build step sent every technical fact about the whole project there, so it
# became an architecture overview carrying dates, issue numbers and names from
# the code, read at the start of every session. The ceiling was written down,
# and only a monthly offer that kept being put off ever read it. Shortening the
# masterplan then moved its text word for word into a new catch-all document.
#
# So the check holds four things. The template is an index: past the standing
# rules, each section stays short and names the file that owns its topic, and
# that file is one the kit really writes. The build step routes each kind of
# fact to one home and keeps dates, issue numbers and code names out of
# AGENTS.md. The project check fails above the ceiling and names both numbers,
# which this check proves by running the shipped step in a throwaway folder.
# And a masterplan grown too long moves its detail onto pieces or concept
# files, never into a new catch-all document.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
TEMPLATES="$SKILLS/setup-ai-build-kit/templates"
FOUNDATION="$TEMPLATES/foundation/AGENTS.md"
CHECKS="$TEMPLATES/foundation/checks.yml"
MASTERPLAN="$TEMPLATES/masterplan.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
SYNC="$SKILLS/sync/SKILL.md"
PIECES="$SKILLS/setup-ai-build-kit/references/pieces.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Agent-first record checks"
rs_exists "$FOUNDATION" "$CHECKS" "$MASTERPLAN" "$BUILDER" "$SETUP" "$SYNC" "$PIECES" "$WORKFLOW"

# --- the build step routes each fact to one home ----------------------------

rs_rule "each settled fact goes to one home" 'each fact the piece settled goes to one home'
rs_rule "history goes to the piece's changelog file" 'what changed for the person: the piece.s changelog file'
rs_rule "the product goes to the masterplan" 'the product, its promises and decisions: the masterplan'
rs_rule "lasting technical design goes to a concept file" 'lasting technical design, how a part of the tool works and the rules it keeps: `docs/<concept>\.md`, one concept to a file'
rs_rule "a concept file has fixed headings" 'under the headings what it is, how it works, rules, and where it lives'
rs_rule "a new fact starts a concept file, never a notes file" 'a fact that fits no concept file yet starts a new one, named for its concept, never a general notes file'
rs_rule "a concept file is one the list names" 'a concept file is one listed in `docs/readme\.md`'
rs_rule "a new concept file is listed there, not in AGENTS.md" 'gets a line in `docs/readme\.md`, never in agents\.md'
rs_rule "a build reads the concept files it touches" 'read too each concept file the piece touches'
rs_rule "AGENTS.md takes rules and pointers only" 'agents\.md holds rules and pointers only'
rs_rule "no date, issue number or code name in AGENTS.md" 'never write a date, an issue number or a code name into it'
rs_rule "a code name is defined" 'a code name is a function, variable or file name from the project.s code'
rs_rule "the ceiling is held by the project check" 'the project check goes red when agents\.md passes 200 lines'
rs_guard "$BUILDER" "section-builder's records step"

# --- the template says what it is -------------------------------------------

rs_reset
rs_rule "the file calls itself an index" 'this file is an index: the standing rules in short form, then a pointer for each topic to the file that owns it'
rs_rule "the file keeps out dates, issue numbers and code names" 'never a date, an issue number or a code name: a function, variable or file name from the project.s code'
rs_rule "the file names the check on its ceiling" 'the project check fails above 200 lines'
rs_rule "concept files are one concept to a file" 'lasting technical design lives in `docs/<concept>\.md`, one concept to a file'
rs_rule "a fact with no concept file starts one" 'a fact that fits no file yet starts a new concept file, never a general notes file'
rs_rule "the concept files are listed in docs/README.md, not here" '`docs/readme\.md` lists the concept files, and only those'
rs_rule "the build path is read right after the masterplan's header" 'read the build-path section of `masterplan\.md`, right after its short header'
rs_guard "$FOUNDATION" "the founded AGENTS.md"

# --- the masterplan: a short header, the rest for the agent ------------------

rs_reset
rs_rule "the masterplan opens with a short header for the person" 'a short header for the person'
rs_rule "the rest is written for the agent first" 'everything below the header is written for the agent first'
rs_guard "$MASTERPLAN" "the masterplan template"

rs_reset
rs_rule "founding writes the header" 'open it with its short header for the person'
rs_rule "founding writes the rest for the agent" 'write everything below the header for the agent first'
rs_guard "$SETUP" "founding's masterplan step"

rs_reset
rs_rule "shortening moves technical detail to its concept file" 'lasting technical design goes to its `docs/<concept>\.md`'
rs_rule "shortening never creates a catch-all document" 'never into a new catch-all document'
rs_guard "$SYNC" "the masterplan length offer"

rs_require_load_bearing "pieces.md routes technical design to its concept file" "$PIECES" 'lasting technical design goes in its own `docs/<concept>\.md`'
rs_require_load_bearing "WORKFLOW says design has one file per concept" "$WORKFLOW" 'lasting technical design goes into its own file in `docs/`, one concept to a file'
rs_require_load_bearing "WORKFLOW says the check goes red past the ceiling" "$WORKFLOW" 'the project check goes red when agents\.md passes 200 lines, and names both numbers'
rs_require_absent "WORKFLOW no longer sends whole-project detail to AGENTS.md" "$WORKFLOW" 'anything technical that affects the whole project goes into agents\.md'
rs_require "the project check carries the ceiling step" "$CHECKS" 'name: check the agents\.md ceiling'
rs_require_load_bearing "founding puts the build path right after the header" "$SETUP" 'the build-path section comes right after the header'
rs_require_load_bearing "change-triage routes design to its concept file" "$SKILLS/change-triage/SKILL.md" 'lasting technical design into its concept file, listed in `docs/readme\.md`'
rs_require_load_bearing "shape routes design to its concept file" "$SKILLS/shape/SKILL.md" 'lasting technical design to its concept file listed in `docs/readme\.md`'
rs_require_load_bearing "an adopted file past the ceiling is named in the founding report" \
  "$SKILLS/setup-ai-build-kit/references/completion-report.md" 'above the 200 its automatic check allows, so that check will show red until you type /maintain'

# --- the template is an index: counted, and every pointer opened -------------

[ -n "${RS_LIST:-}" ] && exit 0

# Print each problem with the index, one per line; print nothing when it holds.
# A section is counted from its heading up to the next one, blank lines at its
# end left out. The standing rules are exempt from the count, since they are
# the rules themselves in their short form; every other section is an index
# entry and names the file that owns its topic.
index_problems() {
  file=$1
  work="$rs_dir/index"
  rm -rf "$work"
  mkdir -p "$work"
  awk -v dir="$work" '
    function flush() {
      if (name == "") return
      while (n > 0 && body[n] ~ /^[ \t]*$/) n--
      out = dir "/" count
      print name > (out ".name")
      print n > (out ".lines")
      for (i = 1; i <= n; i++) print body[i] > (out ".text")
      close(out ".name"); close(out ".lines"); close(out ".text")
    }
    /^## / { flush(); count++; name = substr($0, 4); n = 0 }
    name != "" { body[++n] = $0 }
    END { flush() }
  ' "$file"
  grep -qx 'Standing rules' "$work"/*.name 2>/dev/null || \
    echo "no Standing rules section"
  entries=0
  for named in "$work"/*.name; do
    [ -f "$named" ] || continue
    section=$(cat "$named")
    [ "$section" = "Standing rules" ] && continue
    entries=$((entries + 1))
    base=${named%.name}
    lines=$(cat "$base.lines")
    filled=no
    printf '%s\n' "${EXEMPT:-}" | grep -qxF "$section" && filled=yes
    [ "$filled" = yes ] || [ "$lines" -le 12 ] || echo "$section: $lines lines, more than 12"
    joined=$(tr '\n' ' ' < "$base.text" | tr -s ' ')
    skill_pointers=$(printf '%s\n' "$joined" \
      | grep -oE "\`[a-z-]+\` skill's \`[^\`]+\`" || true)
    rest=$(printf '%s\n' "$joined" | sed -E "s/\`[a-z-]+\` skill's \`[^\`]+\`//g")
    records=$(printf '%s\n' "$rest" | grep -oE '`[^` ]+`' | tr -d '`' \
      | grep -E '/|\.md$|\.yml$|\.sh$|^\.' || true)
    if [ -z "$skill_pointers$records" ]; then
      echo "$section: names no file that owns its topic"
    fi
    printf '%s\n' "$skill_pointers" | while IFS= read -r pointer; do
      [ -n "$pointer" ] || continue
      skill=$(printf '%s' "$pointer" | sed -E "s/^\`([a-z-]+)\`.*/\1/")
      path=$(printf '%s' "$pointer" | sed -E "s/.*skill's \`([^\`]+)\`$/\1/")
      [ -f "$SKILLS/$skill/$path" ] || echo "$section: the $skill skill has no $path"
    done
    # What founding writes into a filled section is the project's own, such
    # as a folder its framework keeps, so only the kit's own pointers there
    # are opened.
    if [ "$filled" = yes ]; then
      records=$(printf '%s\n' "$records" | while IFS= read -r r; do
        if record_resolves "$r"; then echo "$r"; fi
      done)
    fi
    printf '%s\n' "$records" | while IFS= read -r record; do
      [ -n "$record" ] || continue
      record_resolves "$record" || echo "$section: $record is not a record the kit writes"
    done
  done
  [ "$entries" -ge 4 ] || echo "only $entries index sections past the standing rules"
  # The template carries no date and no issue number either. `#<number>` in
  # a pull request's closing line is a placeholder, not a number.
  if grep -nE '(19|20)[0-9][0-9]-[01][0-9]-[0-3][0-9]' "$file" >/dev/null; then
    echo "a date is written into the file"
  fi
  if grep -nE '#[0-9]' "$file" >/dev/null; then
    echo "an issue number is written into the file"
  fi
}

# A record resolves when the kit really writes it into a project: a template
# founding copies, or a skill that names the path as the one it writes.
record_resolves() {
  case "$1" in
    masterplan.md) [ -f "$TEMPLATES/masterplan.md" ] ;;
    CHANGELOG.md) [ -f "$TEMPLATES/CHANGELOG.md" ] ;;
    changes/) grep -qF 'changes/<issue number>-<short name>.md' "$BUILDER" ;;
    'docs/<concept>.md') grep -qF '`docs/<concept>.md`' "$BUILDER" ;;
    docs/README.md) tr '\n' ' ' < "$BUILDER" | tr -s ' ' | grep -qF 'one listed in `docs/README.md`' ;;
    .agents/tools/plan-refresh.sh) [ -f "$TEMPLATES/foundation/plan-refresh.sh" ] ;;
    plan.local.md) grep -qF 'plan.local.md' "$TEMPLATES/foundation/plan-refresh.sh" ;;
    .github/workflows/checks.yml) [ -f "$CHECKS" ] ;;
    .env) [ -f "$TEMPLATES/foundation/env.example" ] ;;
    *) return 1 ;;
  esac
}

problems=$(index_problems "$FOUNDATION")
if [ -n "$problems" ]; then
  printf '%s\n' "$problems" | sed 's/^/  /' >&2
  rs_fail "the founded AGENTS.md is not a short index whose pointers all open"
fi
rs_ok "past the standing rules, every section is 12 lines or fewer and names a file that opens"

# The count and the pointers are only worth something if they can fail. Each
# copy below breaks one thing, and the check has to name it.
mutant="$rs_dir/mutant.md"
expect_problem() {
  # expect_problem <description> <text the report must carry>
  found=$(index_problems "$mutant")
  if printf '%s\n' "$found" | grep -qF "$2"; then
    rs_ok "$1"
  else
    rs_fail "$1: the report said '$found'"
  fi
}
first_entry=$(grep -E '^## ' "$FOUNDATION" | grep -vx '## Standing rules' | head -1 | cut -c4-)
[ -n "$first_entry" ] || rs_fail "the template has no index section to break"

awk -v target="## $first_entry" '
  { print }
  $0 == target { for (i = 1; i <= 12; i++) print "padding line " i }
' "$FOUNDATION" > "$mutant"
expect_problem "a section grown past 12 lines is caught" "$first_entry: "

awk -v target="## $first_entry" '
  $0 ~ /^## / { inside = ($0 == target) }
  inside { gsub(/`/, "") }
  { print }
' "$FOUNDATION" > "$mutant"
expect_problem "a section naming no owner is caught" "$first_entry: names no file"

awk -v target="## $first_entry" '
  { print }
  $0 == target { print "See the `ship` skill'"'"'s `references/no-such-file.md`." }
' "$FOUNDATION" > "$mutant"
expect_problem "a pointer to a file no skill has is caught" "the ship skill has no references/no-such-file.md"

awk -v target="## $first_entry" '
  { print }
  $0 == target { print "Everything else is in `docs/notes.md`." }
' "$FOUNDATION" > "$mutant"
expect_problem "a catch-all notes file is caught as no record the kit writes" "docs/notes.md is not a record"

sed 's/^## Standing rules$/## Rules/' "$FOUNDATION" > "$mutant"
expect_problem "a file with no standing rules section is caught" "no Standing rules section"

{ cat "$FOUNDATION"; echo "Moved on 2026-09-30."; } > "$mutant"
expect_problem "a date in the file is caught" "a date is written"

# Built from a variable, so the validator does not read this line as a citation.
hash='#'
{ cat "$FOUNDATION"; echo "Fixed in ${hash}214."; } > "$mutant"
expect_problem "an issue number in the file is caught" "an issue number is written"

# --- a founded file: the sections founding fills are exempt by name ----------

# Founding fills the capability profile and the stack section with the
# project's own facts, so in a founded file those two may pass 12 lines. They
# are exempt by name, and only they: every other section keeps the limit. The
# stand-in is filled the way standing-instructions.sh fills its own, with the
# rules block a Next.js starter appends.
founded="$rs_dir/founded.md"
awk '
  /^## Capability profile$/ { want = "profile" }
  /^## Stack, and how to run and check it$/ { want = "stack" }
  /^\(One line, written by the setup-ai-build-kit skill\.\)$/ {
    print "A sign-up list for the team'"'"'s weekly football."; next
  }
  want != "" && /^\(Filled in by the setup-ai-build-kit skill:/ { inside = 1 }
  inside {
    if ($0 ~ /\)$/) {
      inside = 0
      for (i = 1; i <= 16; i++) print "- " want " fact " i ", as founding writes it."
      want = ""
    }
    next
  }
  { print }
' "$FOUNDATION" > "$founded"
printf '%s\n' '' '<!-- BEGIN:nextjs-agent-rules -->' '' '# This is NOT the Next.js you know' '' \
  'Read the relevant guide in `node_modules/next/dist/docs/` first.' '' \
  '<!-- END:nextjs-agent-rules -->' >> "$founded"
grep -qF -- '- profile fact 16' "$founded" && grep -qF -- '- stack fact 16' "$founded" || \
  rs_fail "the stand-in founding did not fill the two sections"
filled_exempt='Capability profile
Stack, and how to run and check it'
problems=$(EXEMPT="$filled_exempt" index_problems "$founded")
if [ -n "$problems" ]; then
  printf '%s\n' "$problems" | sed 's/^/  /' >&2
  rs_fail "a founded AGENTS.md is not a short index once founding fills it"
fi
rs_ok "a founded file passes, with only the capability profile and stack section past 12 lines"
problems=$(index_problems "$founded")
rs_report "without the exemption, the filled sections are counted" \
  "$(printf '%s\n' "$problems" | grep -q '^Capability profile: ' && echo yes || echo no)"
awk -v target="## $first_entry" '
  { print }
  $0 == target { for (i = 1; i <= 12; i++) print "padding line " i }
' "$founded" > "$mutant"
problems=$(EXEMPT="$filled_exempt" index_problems "$mutant")
rs_report "in a founded file, a section not named in the exemption still keeps 12 lines" \
  "$(printf '%s\n' "$problems" | grep -qF "$first_entry: " && echo yes || echo no)"

# --- the project check holds the ceiling, run both ways ----------------------

# The step's own script, as it ships: its one-line `run:`, or the lines under
# a `run: |`.
step="$rs_dir/ceiling-step.sh"
awk '
  /- name: Check the AGENTS\.md ceiling/ { found = 1; next }
  found && !inside && /^ *run: *\|/ { match($0, /^ */); indent = RLENGTH; inside = 1; next }
  found && !inside && /^ *run: / { sub(/^ *run: /, ""); print; exit }
  inside {
    match($0, /^ */)
    if ($0 !~ /^[ \t]*$/ && RLENGTH <= indent) exit
    print substr($0, indent + 3)
  }
' "$CHECKS" > "$step"
[ -s "$step" ] || rs_fail "the project check has no ceiling step with a script to run"

run_step() {
  # run_step <lines> <final newline: yes|no>: prints the step's output, then
  # its exit status on the last line.
  folder="$rs_dir/project-$1-$2"
  rm -rf "$folder"
  mkdir -p "$folder"
  awk -v n="$1" 'BEGIN { for (i = 1; i < n; i++) print "line " i }' > "$folder/AGENTS.md"
  if [ "$2" = yes ]; then echo "line $1" >> "$folder/AGENTS.md"; else printf 'line %s' "$1" >> "$folder/AGENTS.md"; fi
  shell=sh
  command -v bash >/dev/null 2>&1 && shell=bash
  set +e
  (cd "$folder" && "$shell" -e "$step") 2>&1
  echo "status $?"
  set -e
}

at=$(run_step 200 yes)
rs_report "an AGENTS.md of 200 lines passes" \
  "$(printf '%s\n' "$at" | tail -1 | grep -qx 'status 0' && echo yes || echo no)"
over=$(run_step 201 yes)
rs_report "an AGENTS.md of 201 lines fails" \
  "$(printf '%s\n' "$over" | tail -1 | grep -qx 'status 0' && echo no || echo yes)"
rs_report "the failure names both numbers" \
  "$(printf '%s\n' "$over" | grep -q '201' && printf '%s\n' "$over" | grep -q '200' && echo yes || echo no)"
rs_report "the failure names the one-step fix" \
  "$(printf '%s\n' "$over" | grep -qF '/maintain' && echo yes || echo no)"
unended=$(run_step 201 no)
rs_report "201 lines fail even without a final newline" \
  "$(printf '%s\n' "$unended" | tail -1 | grep -qx 'status 0' && echo no || echo yes)"
rs_report "the pass names both numbers too" \
  "$(printf '%s\n' "$at" | grep -q '200 lines' && printf '%s\n' "$at" | grep -q 'ceiling of 200' && echo yes || echo no)"

rs_done
