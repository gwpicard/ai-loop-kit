#!/usr/bin/env sh
# test-strength.sh: guard the optional check that tests notice broken code.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

RULES="$ROOT/.agents/skills/section-builder/references/test-strength.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FIX="$ROOT/.agents/skills/fix/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Test-strength rules"
rs_exists "$RULES" "$BUILDER" "$FIX" "$WORKFLOW"

rs_rule "only offered on Build with care" 'offered only on build with care'
rs_rule "needs a runner for the language" "only where a local runner exists for the project's language"
rs_rule "uses the plain offer" 'i can break the changed code on purpose to check the tests notice'
rs_rule "keeps the check optional" 'it is optional evidence'
rs_rule "declining does not block work" 'a declined or unavailable check does not hold up the piece'
rs_rule "results introduce no gate" 'no result from it becomes an automatic gate'
rs_rule "keeps existing cautions" 'existing required checks and sensitive-area cautions still apply'
rs_rule "waits for the person to accept" 'run the check only if the person accepts the offer'
rs_rule "checks only changed code" 'limit the deliberate breakages to code changed by this piece'
rs_rule "uses the regression test in repairs" 'in a repair, use the regression test against the repaired code'
rs_rule "runs locally on a copy" 'run locally in a disposable copy'
rs_rule "has no hosted service" 'with no hosted service'
rs_rule "does not touch live records or actions" 'no real records or live actions'
rs_rule "never widens to the whole project" 'never run it across the whole project'
rs_rule "never leaves code broken" 'or leave deliberately broken code in the working tree'
rs_rule "names StrykerJS incremental mode" 'use strykerjs in incremental mode'
rs_rule "restricts the StrykerJS scope" '`--mutate` restricted to the changed files or lines'
rs_rule "names mutmut with a changed-function scope" 'use mutmut with targets restricted to the changed functions'
rs_rule "limits counts to this run" "take counts only from valid breakages in this run's changed scope"
rs_rule "requires a test failure to call a breakage caught" 'count a breakage as caught only when a test fails because of it'
rs_rule "does not count failed runs as catches" 'list crashes, timeouts and invalid changes separately as unchecked'
rs_rule "reports incomplete evidence" 'say what was left unchecked rather than presenting a complete result'
rs_rule "keeps tool words out of the report" 'keep runner names and the word "mutation" out of the person'
rs_rule "keeps the fixed report shape" 'the tests were checked by breaking the code on purpose <tried> times\. they caught <caught>\. the <missed> they missed are listed on the piece'
rs_rule "handles no misses honestly" 'with no misses, end with "they missed none\."'
rs_rule "lists the missed behaviour on the piece" 'list each miss on the piece in plain words'
rs_rule "reads the sensitive-area map" "compare its location with the masterplan's sensitive-area map"
rs_rule "sorts sensitive misses as worth stopping for" 'a miss inside a named sensitive area goes under "worth stopping for", with the area named'
rs_rule "sorts other misses as worth knowing" 'a miss elsewhere goes under "worth knowing"'
rs_rule "explains changes without an observable effect" 'explain a change with no observable effect as such'
rs_rule "lets the person decide" 'the person decides whether a miss matters'
rs_rule "records that decision" 'record that choice on the piece'
rs_rule "refuses tests written to raise a count" 'never write a test only to raise the count'
rs_rule "requires tests to protect promised behaviour" 'add or improve a test only when it protects promised behaviour'
rs_rule "rechecks intact code" 'confirm the working code is intact and rerun the ordinary tests before saving'
rs_guard "$RULES" "the optional test-strength check"

rs_reset
rs_rule "builder activates the optional check" 'on build with care, where a runner exists for the project.s language, offer the optional check in `references/test-strength\.md`'
rs_rule "builder reports and sorts misses" "use that reference's one-line report and sort the misses on the piece"
rs_guard "$BUILDER" "section-builder's test-strength offer"

rs_reset
rs_rule "fix offers to test the regression check" "on build with care, where a runner exists for the project's language, offer to check the regression test by breaking the repaired code on purpose"
rs_rule "fix loads the shared rules" 'follow the `section-builder` skill.s `references/test-strength\.md` for this optional check'
rs_rule "fix limits the run to its repair" 'keep the run to the repaired code and the regression test'
rs_rule "fix does not repeat the offer at save" 'do not offer it again when section-builder saves the repair'
rs_guard "$FIX" "fix's test-strength offer"

rs_require "WORKFLOW explains the optional offer" "$WORKFLOW" 'on build with care, /implement can offer to break the changed code on purpose'
rs_require "WORKFLOW explains the repair offer" "$WORKFLOW" '/fix offers the same check for the test that keeps a repaired fault from returning'
rs_require "WORKFLOW explains how misses are sorted" "$WORKFLOW" 'misses in a named sensitive area are worth stopping for; the rest are worth knowing'

rs_done
