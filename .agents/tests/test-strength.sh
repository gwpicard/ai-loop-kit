#!/usr/bin/env sh
# test-strength.sh: guard the check that tests notice broken code.
#
# Once a piece's acceptance checks pass, the build breaks the code it changed
# on purpose and has the gate run the acceptance checks against each
# breakage. That happens without an offer, on every build path, wherever the
# project already has a runner for it, and a check that notices nothing sends
# the piece to the person rather than stopping it. A second, optional run on
# the project's other tests stays an offer on Build with care. The rules are
# prose an agent reads, so each one is read back here and proved load-bearing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

RULES="$ROOT/.agents/skills/section-builder/references/test-strength.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
FIX="$ROOT/.agents/skills/section-builder/references/fix-loop.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Test-strength rules"
rs_exists "$RULES" "$BUILDER" "$FIX" "$WORKFLOW"

# The acceptance checks, once the build is green. It used to be an offer on
# Build with care; a weak bar is as weak on every path, so it is not one now.
rs_rule "runs once every acceptance check passes" \
  'once every acceptance check passes, break the code this piece changed on purpose'
rs_rule "runs without an offer, on every build path" \
  'do this without offering first, on every build path'
rs_rule "only where a runner is already a dependency" \
  'wherever strykerjs or mutmut is already among the project.s dependencies'
rs_rule "never installs a runner" 'never install a runner to do it'
rs_rule "a check that notices nothing goes to the person and never stops the piece" \
  'an acceptance check that notices none of the breakages goes to the person.s review; it never stops the piece'
rs_rule "checks only changed code" \
  'limit the deliberate breakages to code changed by this piece against its base'
rs_rule "in a repair the regression test is the acceptance check" \
  'in a repair, the regression test is the acceptance check, run against the repaired code'
rs_rule "each breakage is saved as a patch and run through the gate" \
  'save each one as a patch and run it through the gate'
rs_rule "names the gate's breakage command" \
  'gate\.py evidence <number> --breakage <patch> -- <acceptance check command>'
rs_rule "never breaks the piece's own folder" \
  'never apply a breakage to the piece.s own folder'
rs_rule "never leaves code broken" 'never leave deliberately broken code in the working tree'
rs_rule "runs locally on this computer" 'run locally, with no hosted service and no real records or live actions'
rs_rule "the gate reads the runs on the current commit" \
  'the gate reads those runs on the current commit'
rs_rule "a check that failed on none is a weak_check" \
  'an acceptance check that failed on none of them is written to `forced\.jsonl` as a `weak_check`'
rs_rule "a runner and no breakage is refused" \
  'where the project has a runner and no breakage is recorded on the current commit, the gate refuses the move'
rs_rule "no runner is one line and nothing forced" \
  'the gate writes one line saying the checks were not tested by breaking the code, and nothing is forced'

# The optional run on other code keeps both of its old limits.
rs_rule "the optional run is offered only on Build with care" \
  'this run is offered only on build with care'
rs_rule "the optional run needs a runner for the language" \
  "only where a local runner exists for the project's language"
rs_rule "uses the plain offer" 'i can break the changed code on purpose to check the tests notice'
rs_rule "keeps the optional run optional" 'it is optional evidence'
rs_rule "declining does not block work" 'a declined or unavailable run does not hold up the piece'
rs_rule "its results introduce no gate" 'no result from it becomes an automatic gate'
rs_rule "keeps existing cautions" 'existing required checks and sensitive-area cautions still apply'
rs_rule "waits for the person to accept" 'run it only if the person accepts the offer'
rs_rule "never widens to the whole project" 'never across the whole project'

# How a runner is used and counted.
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
rs_rule "reads the area map through the script" \
  'compare its location with the area map: run `python3 \.agents/tools/area-map\.py which <path>`'
rs_rule "sorts sensitive misses as worth stopping for" 'a miss inside a named sensitive area goes under "worth stopping for", with the area named'
rs_rule "sorts other misses as worth knowing" 'a miss elsewhere goes under "worth knowing"'
rs_rule "explains changes without an observable effect" 'explain a change with no observable effect as such'
rs_rule "lets the person decide" 'the person decides whether a miss matters'
rs_rule "records that decision" 'record that choice on the piece'
rs_rule "refuses tests written to raise a count" 'never write a test only to raise the count'
rs_rule "requires tests to protect promised behaviour" 'add or improve a test only when it protects promised behaviour'
rs_rule "rechecks intact code" 'confirm the working code is intact and rerun the ordinary tests before saving'
rs_guard "$RULES" "the test-strength reference"

rs_reset
rs_rule "builder breaks the changed code once the checks pass" \
  'once every acceptance check passes, where strykerjs or mutmut is already among the project.s dependencies, break the code this piece changed on purpose'
rs_rule "builder runs each breakage through the gate" \
  'run each acceptance check against each breakage through the gate, as `references/test-strength\.md` says'
rs_rule "builder does it without an offer and installs nothing" \
  'do it without an offer, on every build path, and never install a runner'
rs_rule "builder's missed breakage adds no refusal" \
  'an acceptance check that notices none of them goes to the person.s review and adds no refusal of its own'
rs_rule "builder's hand-over says when nothing was broken" \
  'where neither runner is there, say so in one sentence in the pull request description: "the checks were not tested by breaking the code, because the project has neither strykerjs nor mutmut\."'
rs_rule "builder still offers the optional run on Build with care" \
  'on build with care, where a runner exists for the project.s language, offer the optional run on the project.s other tests in that reference'
rs_rule "builder reports and sorts misses" "use that reference's one-line report and sort the misses on the piece"
rs_guard "$BUILDER" "section-builder's test-strength steps"

rs_reset
rs_rule "fix breaks the repaired code once the regression test passes" \
  'once the regression test passes, it is the acceptance check that section-builder breaks the repaired code against'
rs_rule "fix loads the shared rules" 'as the `section-builder` skill.s `references/test-strength\.md` says'
rs_rule "fix limits the run to its repair" 'keep the breakages to the repaired code'
rs_rule "fix does not repeat it at save" 'do not run it again when section-builder saves the repair'
rs_guard "$FIX" "the fix loop's breakage of the repaired code"

rs_require "WORKFLOW explains the breakage without asking" "$WORKFLOW" \
  'once every acceptance check passes, the agent breaks the changed code on purpose and has the gate run the acceptance checks against each breakage'
rs_require "WORKFLOW says it never installs a runner" "$WORKFLOW" \
  'where the project already has strykerjs or mutmut, and it never installs either'
rs_require "WORKFLOW explains the repair" "$WORKFLOW" \
  'in a repair, the test that keeps the fault from returning is the acceptance check'
rs_require "WORKFLOW explains the optional offer" "$WORKFLOW" \
  'on build with care the agent can also offer to break the changed code'
rs_require "WORKFLOW explains how misses are sorted" "$WORKFLOW" \
  'misses in a named sensitive area are worth stopping for; the rest are worth knowing'

rs_done
