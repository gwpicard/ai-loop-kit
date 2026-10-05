#!/usr/bin/env sh
# trim.sh: guard the rules of the trim, the single pass that takes out what a
# change added and does not need before the person tries it.
#
# trim-rehearsal.sh runs the engines and the pass. This half reads back the
# rules a run cannot show going missing. The one guarded hardest is the limit
# on what the trim may change: removing and folding, and nothing else. A pass
# allowed to reshape code until the tests stop passing learns to delete what
# the tests do not cover, and every step still looks green, so losing that
# sentence would make the trim quietly dangerous rather than visibly broken.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

TRIM="$ROOT/.agents/skills/section-builder/references/trim.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FIX="$ROOT/.agents/skills/section-builder/references/fix-loop.md"
WORKFLOW="$ROOT/WORKFLOW.md"
SOURCES="$ROOT/docs/SOURCES.md"

rs_init "Trim rules"
rs_exists "$TRIM" "$BUILDER" "$FIX" "$WORKFLOW" "$SOURCES"

# Where and when it runs.
rs_rule "it does not run on Explore privately" 'not on explore privately'
rs_rule "it runs once, after the ordinary checks" 'it runs once, after the tests, the type check and the linter pass'
rs_rule "it looks only at the change" 'only what this change added or changed'
rs_rule "untouched code is left to the quarterly visit" 'code the change did not touch is out of scope'
rs_rule "imports are left to the linter" 'unused imports and unused local names are also out of scope'

# What it may change.
rs_rule "a one-use dependency is only reported" 'a dependency the change added for a single use\. reported only'
rs_rule "a copy is only reported" 'closely matches code already in the project\. reported only'
rs_rule "a function over the limit is only reported" 'over the limit below\. reported only'
rs_rule "what the piece exists to provide is left alone" 'leave alone anything the piece exists to provide'
rs_rule "only removing and folding" 'two kinds of edit, and no others: removing, and folding'
rs_rule "never a restructure" 'the trim never renames, splits, extracts, reorders, restyles or adds code'
rs_rule "never a test or its data" 'it never changes a test or the data a test reads'
rs_rule "any other improvement becomes a report" 'becomes a report on the piece'

# The pass.
rs_rule "the piece is committed before the trim" 'commit the piece as built'
rs_rule "each finding gets a second look" 'search the whole project for the name'
rs_rule "a name found elsewhere is dropped" 'drop an unused finding whose name turns up anywhere outside its own definition'
rs_rule "an untested fold is only reported" 'when none do, report the fold rather than applying it'
rs_rule "the checks run after every edit" 'apply each removal or fold on its own, then run the tests'
rs_rule "a red check undoes the edit" 'undo that edit and record it on the piece as a wrong call'
rs_rule "a test is never changed to keep an edit" 'never change a test to keep an edit'
rs_rule "the second run applies nothing" 'apply nothing it finds; list it on the piece'
rs_rule "the trim has its own commit" 'commit the trim on its own'
rs_rule "no change means no commit" 'when nothing was changed, there is no commit'

# Engines.
rs_rule "the last resort is reading the code" 'the last resort for every row is reading the changed code directly'
rs_rule "an engine is fetched only after asking" 'ask once, the first time the trim needs it'
rs_rule "vulture runs at the stated setting" '`vulture --min-confidence 60 \.`'
rs_rule "the report folder stays outside the project" 'point it at a temporary folder outside the project'

# The limit.
rs_rule "the limit is lizard's published default" '`lizard --ccn 15 --csv <changed files>`'
rs_rule "never the project's own average" 'never the project.s own average'
rs_rule "a changed function is judged against itself" 'reported only when the change raised its count'
rs_rule "a function is never split" 'the trim never splits a function'

# What the person sees.
rs_rule "finding nothing is silent" 'when the trim changed nothing and has nothing to report, say nothing'
rs_rule "the fixed line" 'i took out <count> things this change did not need\. they are listed on the piece\.'
rs_rule "no score reaches the person" 'never show a function.s path count or any other score'
rs_rule "no engine names reach the person" 'keep engine names out of what the person reads'
rs_guard "$TRIM" "the shipped trim.md"

rs_reset
rs_rule "section-builder runs the trim" 'load `references/trim\.md` and run its single pass'
rs_rule "section-builder keeps it off Explore privately" 'once those pass, on build and run it and build with care'
rs_rule "the trim is no excuse for a restructure" 'the trim does not authorise a restructure'
rs_guard "$BUILDER" "section-builder's trim step"

rs_require_order "the trim runs after the type check and linter" "$BUILDER" \
  'run the type check and linter that AGENTS' 'references/trim\.md'
rs_require_order "the trim runs before the hand-over" "$BUILDER" \
  'references/trim\.md' '^Then walk through the piece\.'

rs_require_load_bearing "the fix loop runs the trim on a repair" "$FIX" \
  'run the trim in the `section-builder` skill.s `references/trim\.md`'
rs_require "WORKFLOW says what the trim takes out" "$WORKFLOW" \
  'takes out anything the change added that nothing needs'
rs_require "WORKFLOW says it only removes or folds" "$WORKFLOW" \
  'only removes things or folds them into the one place that uses them'
rs_require "WORKFLOW gives the same line" "$WORKFLOW" \
  'i took out two things this change did not need'
rs_require "SOURCES credits the published limit" "$SOURCES" 'terryyin/lizard'

rs_done
