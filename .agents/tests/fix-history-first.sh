#!/usr/bin/env sh
# fix-history-first.sh: guard the evidence read and cleanup around a repair.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIX="$ROOT/.agents/skills/fix/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Fix history-first rules"
rs_exists "$FIX" "$BUILDER" "$WORKFLOW"

rs_rule "reads the changelog and closed pieces first" 'before ranking causes, read `changelog\.md` and closed pieces for the same area'
rs_rule "rules out a failed repair" 'repair already tried and failed is ruled out'
rs_rule "ranks an established cause first" 'cause already established ranks first'
rs_rule "uses the fixed history line" 'this was tried on <date> and did not hold, so it is ruled out'
rs_rule "runs existing covering tests first" 'run the existing tests it finds before writing a new focused test'
rs_rule "bisects only from a known-good point" 'do not bisect when there is no known-good point'
rs_rule "reports the breaking change by title and date" 'it broke in the change called <piece title> on <date>'
rs_rule "names every temporary item" 'name every temporary log and harness added'
rs_rule "removes each temporary item" 'remove each one'
rs_rule "reruns evidence without instrumentation" 'run the regression evidence without them'
rs_guard "$FIX" "fix/SKILL.md"

rs_reset
rs_rule "a retry-only pass is a test fault" 'passes only on a retry is a fault in the test'
rs_rule "a retry-only pass is never accepted" 'never a passing result'
rs_guard "$BUILDER" "section-builder/SKILL.md"

rs_require "WORKFLOW explains the history read" "$WORKFLOW" 'reads the changelog and finished pieces for the same part'

rs_done
