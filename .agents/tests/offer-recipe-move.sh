#!/usr/bin/env sh
# offer-recipe-move.sh: guard the monthly offer to move a project onto a recipe.
#
# A project founded before recipes existed, or on a stack of its own, can be
# built much like a recipe on the menu. On a recipe /ship checks the launch
# steps, and off one it can only name what it could not check. So the monthly
# visit offers the move. The rules worth holding are the ones whose loss would
# be quiet: the move is offered and never required, nothing changes without a
# yes, a yes becomes a piece rather than work done inside the visit, an open
# piece stops the offer, a no is recorded and not asked again until the menu or
# the stack changes, a recipe that joined the menu after founding is offered to
# an own stack that has not moved, the offer names what the move gains, and
# nothing is said when no recipe is close. A visit that nagged, or moved a project without
# asking, would read perfectly well in a transcript.
#
# The menu is read from the ship skill's recipes folder at run time, so the
# skill names no hosting, data or deploy product. The product list is read from
# hosting-request.sh, which owns it, rather than kept here as a second copy.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
HOSTING="$ROOT/.agents/tests/hosting-request.sh"

rs_init "Recipe-move checks"
rs_exists "$MAINTAIN" "$WORKFLOW" "$HOSTING"

# The monthly pass calls it, and not where nothing goes live.
rs_rule "the monthly pass runs it" \
  'unless the project explores privately, run .offering a move onto a recipe. below'
rs_rule "explore privately is skipped" 'skip this on explore privately'

# Offered, never required.
rs_rule "the move is never required" 'the move is never required'

# Which projects count as off a recipe.
rs_rule "none, no line or a missing file is off a recipe" \
  'no line at all, or a file that is no longer there counts as off a recipe'

# The menu is read from the recipes folder, and names come from it.
rs_rule "the menu is read from the installed recipes folder" \
  'each file directly in the installed ship skill.s .recipes/. folder, not the .parts/. folder'
rs_rule "product names come from the recipe files" \
  'take every product name from those files, and never write one into this skill'

# What close means.
rs_rule "close is the same framework and data service" \
  'the same framework and the same data service\. it stays close'
rs_rule "a different deploy target is still close" \
  'it stays close when the project deploys somewhere else, or lacks something the recipe adds'
# Picking one close recipe before the founding-menu and decline tests run
# lets an older recipe that matches a little better hide a new one, which is
# then never offered. So the pick comes last, among what those steps allow.
rs_rule "no close recipe is picked before the later steps" \
  'keep every close recipe for now, and do not pick one yet'
rs_rule "the pick is made only among the recipes still allowed" \
  'compare only the close recipes that steps 5 and 6 still allow'
rs_rule "after a no, a new recipe on the menu is not hidden by the declined ones" \
  'where only the menu changed, allow only the close recipes the line does not list, and the ones it lists stay declined'
rs_rule "the stack is read from the project" \
  'read that from the project.s code and dependency files, not from memory'

# A copy of the data service run on the project's own server is not close,
# because the recipe's backup and restore checks rely on the managed backups.
rs_rule "a self-run copy of the data service is not the same service" \
  'is not the same data service, because it lacks the managed backups'

# A yes files a piece, and an open piece stops the offer, or every visit would
# file another copy of the same move.
rs_rule "an open move piece ends the step" \
  'where an open piece already proposes a move onto a recipe'

# A person who chose their own stack.
rs_rule "own stack is offered only when it has become close" \
  'offer the move only when the stack has become close since'
rs_rule "or when the close recipe is new since founding" \
  'or when the close recipe is new since founding'
rs_rule "and a choice made against a close recipe on that menu stands" \
  'where a close recipe was on that menu and the stack was already that close then, their choice stands'

# A recipe that joined the menu after founding was never a choice the person
# turned down. Founding records its menu, and the visit reads that record, or a
# close recipe added later would never be offered to an unchanged stack.
rs_rule "the founding menu is read from the check-up file" \
  'read the .founding-menu. line in .\.ai-build-kit-maintenance.'
rs_rule "a close recipe missing from it is offered once, stack unchanged" \
  'a close recipe that line does not list joined the menu later, .* offer it once, even if the stack has not changed'
rs_rule "a project with no founding-menu line treats every close recipe as new" \
  'a project with no .founding-menu. line was founded before founding kept one, so every close recipe counts as new for it, once'
rs_rule "after a no, the decline line decides" \
  'after a no, step 6 decides whether the offer comes back'

# Silence when nothing is close.
rs_rule "nothing is said when no recipe is close" 'when no recipe is close, or an earlier no stands, say nothing'

# The offer: once, with the gain and the change named.
rs_rule "the move is offered once" 'offer the move once, in one reply'
rs_rule "the gain is named" \
  'say what it gains in plain words: the launch checks /ship would then run'
rs_rule "the change is named" 'say what it would change, from the differences'
rs_rule "a dashboard-only schema moves into migrations" \
  'move those tables into migrations'

# Approval first, and a yes becomes a piece.
rs_rule "nothing changes without approval" 'change nothing without approval\. on a yes'
rs_rule "a yes becomes a piece like any other" \
  'leave it for /shape and /implement like any other piece'
rs_rule "the move is not made during the visit" 'do not make the move during the visit'

# A no.
rs_rule "a no is not asked again that visit" \
  'on a no, leave the project alone and do not ask again this visit'
# A no is recorded, and the offer comes back only after a change. Without the
# record the visit would ask every month.
rs_rule "a no is recorded with its date, recipe and menu" \
  'record the no in .\.ai-build-kit-maintenance. as one line'
rs_rule "the record holds the date, the recipe and the menu" \
  '.recipe-move-declined\|<yyyy-mm-dd>\|<recipe file>\|<menu files, comma separated>.'
rs_rule "the offer comes back only after the menu or stack changed" \
  'offer again only when the menu or the project.s stack has changed since that no'
rs_rule "otherwise the no stands" 'otherwise the earlier no stands'
rs_guard "$MAINTAIN" "maintain's recipe-move step"

# The skill names no product. The list lives in hosting-request.sh.
PRODUCTS=$(sed -n "s/^PRODUCTS='\(.*\)'\$/\1/p" "$HOSTING")
[ -n "$PRODUCTS" ] || rs_fail "could not read the product list from hosting-request.sh"
rs_require_absent "the maintain skill names no hosting, data or deploy product" \
  "$MAINTAIN" "$PRODUCTS"
if [ -z "${RS_LIST:-}" ]; then
  { cat "$MAINTAIN"; echo 'Move the tool to Vercel.'; } > "$rs_dir/named.md"
  rs_fold "$rs_dir/named.md" | grep -qE "$PRODUCTS" ||
    rs_fail "a product named in the maintain skill was not noticed"
  rs_ok "a product named in the maintain skill is noticed"
fi

# The story is told in WORKFLOW.md too.
rs_require "WORKFLOW says the visit offers the move once with its gain" "$WORKFLOW" \
  'the monthly visit then offers the move once, and says what it gains'
rs_require "WORKFLOW says a yes becomes a piece and is not offered again" \
  "$WORKFLOW" 'a yes becomes a piece, shaped and built like any other, and the offer does not come back while that piece is open'
rs_require "WORKFLOW says a no is recorded and waits for a change" "$WORKFLOW" \
  'a no is recorded, and the offer comes back only when the menu or your stack has changed since'
rs_require "the maintenance record template names the line" \
  "$ROOT/.agents/skills/setup-ai-build-kit/templates/maintenance-record" 'recipe-move-declined'
rs_require_load_bearing "the maintenance record template names the founding menu line" \
  "$ROOT/.agents/skills/setup-ai-build-kit/templates/maintenance-record" 'founding-menu'
rs_require_load_bearing "WORKFLOW says a recipe added since founding is offered" \
  "$WORKFLOW" 'a close recipe that joined the menu after you founded the project is offered once, even if your stack has not changed'
rs_require "WORKFLOW says the move is never required" "$WORKFLOW" \
  'the move is never required\. when no recipe is close, you hear nothing'

rs_done
