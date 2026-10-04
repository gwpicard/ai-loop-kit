#!/usr/bin/env sh
# waste-read.sh: guard the rules of the quarterly waste read.
#
# waste-read-rehearsal.sh runs the engines. This half reads back the rules the
# engines cannot enforce: where the read applies, the settings chosen on
# purpose, the second look that drops a name found elsewhere, the shared cap,
# the sentence that says what the read cannot find, and silence when it finds
# nothing. Those are the rules whose loss would go unnoticed, because a read
# without them still produces a tidy-looking list.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

READ="$ROOT/.agents/skills/maintain/references/waste-read.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Waste read rules"
rs_exists "$READ" "$MAINTAIN" "$WORKFLOW"

rs_rule "it follows the shared rules" 'whole-project-reads\.md` apply'
rs_rule "it does not run on Explore privately" 'not on explore privately'
rs_rule "renamed copies are found as well as exact ones" 'finds a copy whose names were changed after pasting'
rs_rule "vulture runs at certainty" '`vulture --min-confidence 100 \.`'
rs_rule "it says what certainty leaves out" 'it does not name an unused function or import at that setting'
rs_rule "the report folder stays outside the project" 'point it at a temporary folder outside the project'
rs_rule "the last resort is reading the code" 'the last resort for every row is reading the code directly'
rs_rule "an engine is fetched only after asking" 'ask once before doing that'
rs_rule "a dependency is given its line" 'find its line in the package file'
rs_rule "a name found elsewhere is dropped" 'if the name turns up anywhere outside its own definition, drop the finding'
rs_rule "the kind of finding stays with it" 'keep the kind of finding with it'
rs_rule "the cap of three is shared" 'the cap of three proposals holds for all of them together'
rs_rule "the rest is counted and offered" 'say how many more findings there are in one line'
rs_rule "nothing is removed without a yes" 'remove nothing without a yes'
rs_rule "it says what it cannot find" 'it does not find two pieces of code that do the same job written differently'
rs_rule "finding nothing is silent" 'there is no filler proposal'
rs_guard "$READ" "the shipped waste-read.md"

rs_require_load_bearing "the quarterly step loads the read" "$MAINTAIN" 'load `references/waste-read\.md`'
rs_require "the quarterly cap is still three" "$MAINTAIN" 'propose no more than three simplifications'
rs_require "WORKFLOW says what it finds" "$WORKFLOW" 'code copied from one place to another, code nothing uses any more'
rs_require "WORKFLOW says what it cannot find" "$WORKFLOW" 'it does not find two pieces of code that do the same job written differently'

rs_done
