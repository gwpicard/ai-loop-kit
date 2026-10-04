#!/usr/bin/env sh
# standing-instructions.sh: keep the project instructions short and preserve
# the person's choice before a trim.
#
# The 200-line ceiling is for the file a project ends up with. Founding adds
# its own lines to the template, so the template leaves room for a fixed budget
# of them, and a usual founding is filled in here and counted.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
VALIDATOR="$ROOT/.agents/tools/validate-kit.sh"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Standing-instruction checks"

rs_rule "the template stays below the ceiling" 'keep this file under 200 lines'
rs_rule "the file holds only what code cannot show" 'hold only what the code cannot show: the save and review routes, conventions that differ from the default, and pointers to the records'
rs_rule "directory layouts stay out" 'never add a directory layout'
rs_rule "dependency lists stay out" 'dependency list, architecture'
rs_rule "architecture overviews stay out" 'architecture overview, or style rule'
rs_rule "lint rules stay out" 'style rule an automatic check could enforce'
rs_rule "the monthly read checks length and content separately" '`/maintain` measures it monthly and offers a trim when it reaches 200 lines or carries any of that content, even below the ceiling'
rs_rule "the person agrees before a cut" 'cut nothing without the person.s yes'
rs_guard "$FOUNDATION" "the foundation's short content rule"

rs_reset
rs_rule "every path gets a complete count" 'on every build path, count every line in the project.s agents\.md, including blank lines'
rs_rule "the read checks all four kinds of content" 'read it for a directory layout, dependency list, architecture overview or style rule an automatic check could enforce'
rs_rule "maintain holds the ceiling and content rule" 'it stays under 200 lines and holds only what the code cannot show: the save and review routes, conventions that differ from the default, and pointers to the records'
rs_rule "length or content triggers one measured offer" 'at 200 lines or more, or with any of the named content even below that count, offer a trim in one line, using the measured count and what can go'
rs_rule "the visible line asks for the trim" 'the standing instructions have reached 240 lines, and 30 of them describe the folder layout the code already shows\. shall i trim them\?'
rs_rule "length alone needs no invented content" 'where length alone triggers the offer, name that alone; never invent removable content to fill the example'
rs_rule "the monthly offer waits for the person's yes" 'cut nothing without the person.s yes'
rs_rule "a no preserves the file and continues the visit" 'a no leaves the file intact and the visit carries on'
rs_rule "a short file without redundant content stays quiet" 'if the file is short and carries none of that content, say nothing'
rs_rule "the full visit cannot repeat or override the choice" 'agents\.md was already checked in the monthly pass; do not repeat its trim offer or cut anything without the person.s yes'
rs_guard "$MAINTAIN" "the maintenance trim offer"

rs_require_order "the check sits in the monthly pass" "$MAINTAIN" '^## Monthly, light$' 'count every line'
rs_require_order "the check precedes the full-visit section" "$MAINTAIN" 'count every line' '^## Quarterly, or before a handover$'
rs_require_load_bearing "setup writes commands and exceptions within the rule" "$SETUP" 'record run and check commands and any non-standard conventions under agents\.md.s stack section, keeping its content rule and line ceiling'
rs_require_load_bearing "WORKFLOW explains the offer and the person's choice" "$WORKFLOW" 'one line saying how long it is and what can go\. nothing is cut without your yes'
rs_require_load_bearing "the validator counts the foundation template" "$VALIDATOR" 'foundation_agents="\$skills/setup-ai-build-kit/templates/foundation/agents\.md"'
rs_require_load_bearing "the validator sets a budget for founding's lines" "$VALIDATOR" 'founding_budget=[0-9][0-9]* '
rs_require_load_bearing "the validator counts founding's budget against the ceiling" "$VALIDATOR" 'if \[ \$\(\(foundation_lines \+ founding_budget \+ founding_margin\)\) -lt 200 \]'
rs_require_load_bearing "the validator keeps a margin under the ceiling" "$VALIDATOR" 'founding_margin=[0-9][0-9]* '
# The harness pads the file, not the kit: asked to write a folder layout into
# its own AGENTS.md, the kit refused, as that file tells it to.
rs_require_load_bearing "the rehearsal has the harness pad a disposable project" "$ROOT/.agents/tests/replay/cases/49.txt" '# prepare: long-instructions'
rs_require_load_bearing "the preparation pads to exactly 240 lines" "$ROOT/.agents/tests/replay/prepare/long-instructions.sh" 'target=240'
rs_require_load_bearing "the rehearsal declines the trim" "$ROOT/.agents/tests/replay/cases/49.txt" 'no, leave the standing instructions as they are'
rs_require_load_bearing "the rehearsal judges the observed offer and unchanged file" "$ROOT/.agents/tests/scenarios.md" 'the monthly visit reports the measured count in one trim offer and leaves the file unchanged after the person declines'

if [ -z "${RS_LIST:-}" ]; then
  # Run the count block from the real validator in isolation, so this check
  # cannot recurse when the validator runs the written-rule family.
  awk '/^founding_budget=/ {copy=1} copy {print} copy && /^fi$/ {exit}' \
    "$VALIDATOR" > "$rs_dir/ceiling"
  [ -s "$rs_dir/ceiling" ] || rs_fail "the validator's ceiling block is missing"
  budget=$(sed -n 's/^founding_budget=\([0-9][0-9]*\)$/\1/p' "$rs_dir/ceiling")
  [ -n "$budget" ] || rs_fail "the validator names no budget for founding's lines"
  margin=$(sed -n 's/^founding_margin=\([0-9][0-9]*\)$/\1/p' "$rs_dir/ceiling")
  [ -n "$margin" ] || rs_fail "the validator names no margin under the ceiling"
  [ "$margin" -ge 5 ] || rs_fail "the margin under the ceiling is $margin lines, fewer than 5"
  room=$((199 - budget - margin))
  mkdir -p "$rs_dir/skills/setup-ai-build-kit/templates/foundation"
  padded="$rs_dir/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
  count_passes() {
    sh -c 'SKILLS=$1; fail() { exit 1; }; pass() { :; }; . "$2"' \
      sh "$rs_dir/skills" "$rs_dir/ceiling"
  }
  cp "$FOUNDATION" "$padded"
  count_passes || rs_fail "the shipped foundation leaves no room for founding's $budget lines"
  rs_ok "the shipped foundation passes the real count, founding's $budget lines included"
  awk -v n="$room" 'BEGIN {for (i=1; i<=n; i++) print "line"}' > "$padded"
  count_passes || rs_fail "$room lines should pass, since $room, $budget and $margin make 199"
  rs_ok "$room lines pass, since $room, $budget and $margin make 199"
  printf 'line' >> "$padded"
  if count_passes; then rs_fail "$((room + 1)) lines passed without a final newline"; fi
  rs_ok "$((room + 1)) lines fail even without a final newline"
  # The count this replaced read the template alone, and a template of 196
  # lines passed it while a fresh founding came out at 219.
  awk 'BEGIN {for (i=1; i<=196; i++) print "line"}' > "$padded"
  if count_passes; then rs_fail "a template of 196 lines passed with no room for founding"; fi
  rs_ok "a template of 196 lines no longer passes"

  # The founded result. Fill the template the way founding does, with a
  # project line, capability profile and stack section shaped like the recipe
  # campaign's first launch and adding the 23 lines founding measured there,
  # then append the rules block the Next.js starter writes into AGENTS.md. What
  # founding adds has to fit the budget, and the founded file has to stay under
  # the ceiling with the margin to spare.
  cat > "$rs_dir/project" <<'PROJECT'
A sign-up list for the team's weekly football, with a shared page of who is
playing.
PROJECT
  cat > "$rs_dir/profile" <<'PROFILE'
- Harness: Claude Code, checked on the founding day. File read and write,
  shell, Git: yes. Browser: no browser tool confirmed; the person opens pages in
  their own browser, and the agent checks addresses with `curl`.
- Local save identity: none set; checkpoints use the project-only label "Local
  project user" (open question in masterplan.md).
- Online repository: none yet; the pieces need one, set up with the founder's
  approval. GitHub command line tool: installed and signed in. Project check:
  .github/workflows/checks.yml, job project-check.
- Independent review: a subagent, or a clean separate session. Reach-check
  engine: none; the agent reads imports and callers directly.
- Hooks: yes. SessionStart runs `.agents/hooks/session-start.sh`; command blocks
  live in `.claude/settings.json`.
- Online account access: GitHub, signed in. Vercel and Supabase: the person
  signs in during the first launch. Online authentication: the GitHub command
  line tool's own sign-in.
PROFILE
  cat > "$rs_dir/stack" <<'STACK'
Recipe: nextjs-supabase-on-vercel.md

- Install `npm ci` (Node 22). Run `npm run dev`, then open
  http://localhost:3000.
- Test `npm test` (Vitest). Type check `npm run typecheck` (runs `next typegen`
  first). Lint `npm run lint` (Next.js starter rules). Run all three before
  hand-over; `project-check` runs the same.
- Sign-in, the database and the team list use hosted Supabase (managed
  email-link sign-in). Never hand-build sign-in.
- Next.js keeps its own agent rules in the block at the end of this file; read
  them before writing Next.js code.
- Hosting: Vercel, linked to the GitHub repository, so a merge to `main`
  deploys. The database runs on hosted Supabase.
- Launch checks: `/ship` runs the recipe's eight sections and records the
  address in the changelog.
- Design tool: none recorded.
STACK
  founded="$rs_dir/founded-AGENTS.md"
  # Each placeholder is a paragraph in brackets. Replace the project line and
  # the two sections founding fills; leave the confidential-files note, which
  # founding fills only for a project that has such files.
  awk -v dir="$rs_dir" '
    function fill(name,   line) {
      while ((getline line < (dir "/" name)) > 0) print line
      close(dir "/" name)
    }
    /^## Capability profile$/ { want = "profile" }
    /^## Stack, and how to run and check it$/ { want = "stack" }
    /^\(One line, written by the setup-ai-build-kit skill\.\)$/ { fill("project"); next }
    want != "" && /^\(Filled in by the setup-ai-build-kit skill:/ { inside = 1 }
    inside {
      if ($0 ~ /\)$/) { inside = 0; fill(want); want = "" }
      next
    }
    { print }
  ' "$FOUNDATION" > "$founded"
  template_lines=$(awk 'END { print NR }' "$FOUNDATION")
  filled=$(( $(awk 'END { print NR }' "$founded") - template_lines ))
  [ "$filled" -eq 23 ] || \
    rs_fail "the stand-in founding adds $filled lines, not the 23 measured on the campaign"
  rs_ok "the stand-in founding adds the 23 lines measured on the campaign"
  cat >> "$founded" <<'NEXTJS'

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes. APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev`. Committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
NEXTJS
  if ! grep -qF 'Recipe: nextjs-supabase-on-vercel.md' "$founded" || \
     ! grep -qF -- '- Hooks: yes.' "$founded" || \
     ! grep -qF "A sign-up list for the team's weekly football" "$founded" || \
     grep -qF '(Filled in by the setup-ai-build-kit skill:' "$founded"; then
    rs_fail "the founded rehearsal did not fill the template the way founding does"
  fi
  founded_lines=$(awk 'END { print NR }' "$founded")
  added=$((founded_lines - template_lines))
  [ "$added" -le "$budget" ] || \
    rs_fail "a usual founding adds $added lines, more than the budget of $budget"
  rs_ok "a usual founding, the Next.js rules included, adds $added lines, within the budget of $budget"
  [ $((founded_lines + margin)) -lt 200 ] || \
    rs_fail "a usual founding leaves AGENTS.md at $founded_lines lines, inside the margin of $margin"
  rs_ok "a usual founding leaves AGENTS.md at $founded_lines lines, $margin or more under the ceiling"
fi

rs_done
