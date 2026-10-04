#!/usr/bin/env sh
# one-story-try.sh: guard the one story the kit tells about who tries a piece.
#
# The kit once told two stories. The build skill, the philosophy and the
# README's cycle sentence said the agent's walk-through stands in for the
# person's try before saving, and the person tries a piece only when they opt
# in. WORKFLOW.md's "What stays yours" and two README sentences said the
# person has to try the result before it is saved. An agent reading one and a
# person reading the other came away with opposite rules, and the person either
# felt they had skipped a duty they never had or trusted a walk-through the page
# said could not replace them.
#
# So this check reads the story back from all four files and proves each
# sentence load-bearing. It also searches every shipped document and skill,
# the foundation templates included, for the old wording, and proves the search finds it on a copy with the old sentence put back.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

WORKFLOW="$ROOT/WORKFLOW.md"
README="$ROOT/README.md"
PHILOSOPHY="$ROOT/docs/PHILOSOPHY.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"

rs_init "One story about the walk-through and the person's try"
rs_exists "$WORKFLOW" "$README" "$PHILOSOPHY" "$BUILDER"

# --- WORKFLOW.md "What stays yours" ----------------------------------------

# Only the section, so a phrase used elsewhere in the page cannot stand in for
# one this section dropped.
section="$rs_dir/stays-yours.md"
awk '/^## What stays yours/ { on = 1; print; next } on && /^## / { on = 0 } on' \
  "$WORKFLOW" > "$section"
[ -s "$section" ] || rs_fail "WORKFLOW.md has no \"What stays yours\" section"

rs_rule "saying clearly what you want stays yours" \
  'saying clearly what you want going in'
rs_rule "deciding what merges and what goes live stays yours" \
  'deciding what merges and what goes live'
rs_rule "accepting a risk after its notice stays yours" \
  'accepting a risk after its notice'
rs_rule "the walk-through checks each piece before it is saved" \
  'the agent.s walk-through checks each piece before it is saved'
rs_rule "trying a piece yourself is always open to you" \
  'trying a piece yourself is always open to you'
rs_rule "one piece opts in with its line" '`waiting on you: try it` line'
rs_rule "or the person asks to check every piece" 'ask to check every piece'
rs_rule "a walk-through that could not see gives the person something to try" \
  'when it could not see the screen, it says so and gives you something to try'
rs_rule "the closing sentence is unchanged" \
  'the system automates the routine and never the judgement'
rs_guard "$section" "WORKFLOW.md's \"What stays yours\""

# --- README.md, the opening and the coding question -------------------------

rs_reset
rs_rule "the opening: you say what happens and decide what merges and goes live" \
  'you say what should happen, decide what merges and what goes live'
rs_rule "the opening: you try anything you want to see for yourself" \
  'you try anything you want to see for yourself'
rs_rule "the coding answer: you decide what merges and goes live" \
  'you do have to say what should happen, decide what merges and what goes live'
rs_rule "the coding answer: the agent walks through each piece" \
  'the agent walks through each piece itself'
rs_rule "the coding answer: you can try any piece whenever you want" \
  'you can try any of them whenever you want to see one working'
rs_guard "$README" "README.md"

# --- PHILOSOPHY.md and section-builder --------------------------------------

rs_reset
rs_rule "the person's standing duty is the merge and go-live decision" \
  'the person.s standing duty is the decision to merge and to go live, not a try of every piece'
rs_guard "$PHILOSOPHY" "PHILOSOPHY.md"
rs_require "PHILOSOPHY keeps its controls sentence" \
  "$PHILOSOPHY" 'by the agent.s walk-through or by the person when they opt in'

rs_reset
rs_rule "the person's decision is the merge" \
  'the person.s decision is the merge: the walk-through is the check before saving unless the person opted in or the walk-through could not see'
rs_guard "$BUILDER" "section-builder"
rs_require "section-builder keeps the walk-through standing in for the try" \
  "$BUILDER" 'the walk-through stands in for the person.s try before saving'

# --- the old sentence, nowhere ---------------------------------------------

# The old wording made a try of every result the person's duty. Any use of
# "try the result" is refused, not only the duty, since a machine cannot tell
# the two apart and a new use can say "try a piece" instead. It is refused in
# every document and skill the kit ships, the foundation templates included,
# so a template carrying it in future fails too.
OLD='try(ing)? the results?( before it.s saved)?'

# old_story <root>: print each file under <root> that carries the old wording.
old_story() {
  for f in "$1/README.md" "$1/WORKFLOW.md" "$1/docs/PHILOSOPHY.md" \
    "$1/llms.txt"; do
    [ -f "$f" ] || continue
    if rs_fold "$f" | grep -qE "$OLD"; then echo "$f"; fi
  done
  if [ -d "$1/.agents/skills" ]; then
    find "$1/.agents/skills" -type f | while read -r f; do
      if rs_fold "$f" | grep -qE "$OLD"; then echo "$f"; fi
    done
  fi
  return 0
}

found=$(old_story "$ROOT")
[ -z "$found" ] || { printf '%s\n' "$found" >&2; rs_fail "the old sentence about trying the result is still shipped"; }
rs_ok "no shipped document or skill makes trying the result a duty"

# Prove the search finds it: put the old sentence back in a copy, once in
# WORKFLOW.md and once in a foundation template.
copy="$rs_dir/copy"
mkdir -p "$copy/.agents/skills/setup-ai-build-kit/templates/foundation"
cp "$WORKFLOW" "$copy/WORKFLOW.md"
printf '%s\n' "Two things no skill ever takes: saying clearly what you want going in, and trying the result before it's saved." >> "$copy/WORKFLOW.md"
found=$(old_story "$copy")
[ -n "$found" ] || rs_fail "the old sentence put back in WORKFLOW.md was not found"
rs_ok "the old sentence put back in WORKFLOW.md is found"

cp "$ROOT/WORKFLOW.md" "$copy/WORKFLOW.md"
printf '%s\n' "You do have to say what should happen, try the result, and decide." \
  > "$copy/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
found=$(old_story "$copy")
[ -n "$found" ] || rs_fail "the old sentence in a foundation template was not found"
rs_ok "the old sentence in a foundation template is found"

# Two sentences outlived the change above, each timing a step by the person's
# try as if one always came: the trim in WORKFLOW.md and the screen rules. The
# walk-through comes before saving on every piece, so they are timed by it.
SCREEN="$ROOT/.agents/skills/screen-check/SKILL.md"
rs_require_absent "WORKFLOW.md does not time the trim by a try that may not come" \
  "$WORKFLOW" 'before you try a piece, the kit takes out'
rs_require "WORKFLOW.md times the trim by the walk-through" \
  "$WORKFLOW" 'before the walk-through, or your own try when you ask for one, the kit takes out'
rs_require_absent "screen-check does not time the rules by a try that may not come" \
  "$SCREEN" 'the first result before the person tries it'
rs_require "screen-check times the rules by the walk-through" \
  "$SCREEN" 'the first result before the walk-through looks at it, or the person tries it'

rs_done
