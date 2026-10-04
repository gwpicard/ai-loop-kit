#!/usr/bin/env sh
# stack-research.sh: guard the rules that keep the maintainer's stack research
# a proposal rather than an edit.
#
# The read looks at products the kit does not control and writes down what
# moved. It goes wrong quietly. It edits a recipe it was only meant to read, or
# moves a last-checked date nobody agreed to, or proposes a change to how a
# section works without saying the recipe then needs a new real run, or cites a
# summary site as if it were the product's own page. Each of those reads fine
# in the note and leaves the menu promising something nobody has proved.
#
# So the rules live as prose in the skill, and this check reads them back and
# proves each is load-bearing. It also holds where the note goes: into a folder
# git ignores, so it is never tracked and never reaches a release.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILL="$ROOT/.agents/maintainer-skills/stack-research/SKILL.md"
AGENTS="$ROOT/AGENTS.md"
MAINTAINING="$ROOT/docs/MAINTAINING.md"
GITIGNORE="$ROOT/.gitignore"
MANIFEST="$ROOT/release-manifest.txt"

rs_init "Stack research checks"
rs_exists "$SKILL" "$AGENTS" "$MAINTAINING" "$GITIGNORE" "$MANIFEST"

# --- it proposes and never edits ------------------------------------------
rs_rule "it changes nothing without the maintainer" 'changes nothing in the kit without the maintainer'
rs_rule "it does not edit a recipe or part" 'it does not edit a recipe, a part, a rehearsal or the hosting request'
rs_rule "the date moves only with the maintainer" 'the date moves only when the maintainer agrees'
rs_rule "a new recipe is a proposal only" 'a new recipe is a proposal and nothing more'
rs_rule "no recipe file is written" 'do not write a recipe file'

# --- what the note holds ---------------------------------------------------
rs_rule "every recipe and every part is listed" 'list every recipe and every part'
rs_rule "no change is an answer" '"no change" is an answer the maintainer can act on'
rs_rule "a how-it-works change needs a new real run" 'needs a new real run before the next release. say so on every proposal that changes one'
rs_rule "a part names every recipe that links it" 'name every recipe that links it'

# --- where the evidence comes from ----------------------------------------
rs_rule "a secondary summary site is a pointer only" 'is a pointer only'
rs_rule "the supplier's own page is the evidence" 'a supplier.s own page is the evidence'
rs_rule "the hosting request fields are compared" 'compare those fields with the kit.s hosting request'

# --- where the note goes ---------------------------------------------------
rs_rule "the note goes to the ignored folder" 'write the note to .\.agents/tmp/stack-research/'
rs_rule "the note carries no issue number" 'name no issue or pull request by number in the note'
rs_guard "$SKILL" "the stack-research skill"

# The skill has no adapter and no command, so a document saying where it lives
# is the only way anybody finds it.
rs_require_load_bearing "AGENTS.md says where to load it from" \
  "$AGENTS" 'maintainer-skills/stack-research/skill\.md'
rs_require "MAINTAINING.md accounts for it" "$MAINTAINING" 'stack-research'

# The note is kept out of the repository by the ignore file, and out of a
# release by the allowlist. Either one going quietly would put a dated note,
# naming products, where somebody installing the kit could find it.
rs_require "git ignores the folder the note goes to" "$GITIGNORE" '(^| )\.agents/tmp/( |$)'
rs_require_absent "the release allowlist carries no working notes" "$MANIFEST" '\.agents/tmp'

rs_done
