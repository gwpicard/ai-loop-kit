#!/usr/bin/env sh
# check-floor.sh: guard the type check and linter a founded project receives,
# and the reporting rules every whole-project read shares.
#
# The floor is written as prose that founding follows, so this reads it back.
# check-floor-rehearsal.sh is the half that runs: it founds a throwaway project
# and watches its check go red and green.
#
# The shared rules sit here too because the floor was the first read to land
# and wrote them down. Four later reads point at the same file, and a rule that
# quietly went from it would loosen all of them at once.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

REFS="$ROOT/.agents/skills/setup-ai-build-kit/references"
FLOOR="$REFS/check-floor.md"
READS="$REFS/whole-project-reads.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
AGENTS_TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Check floor rules"
rs_exists "$FLOOR" "$READS" "$SETUP" "$BUILDER" "$AGENTS_TEMPLATE" "$WORKFLOW"

rs_rule "a type check and a linter where the language has them" 'a type check and a linter, wherever the language has them'
rs_rule "they share the tick the person already knows" 'so they turn the same tick red'
rs_rule "what the project already runs comes first" 'what the project already runs\.'
rs_rule "a language without one is recorded as none" '`type check: none for <language>`'
rs_rule "founding never stops over it" 'never stop founding over this'
rs_rule "no tool is invented" 'never invent a tool the language does not have'
rs_rule "each tool's own default rules" "use each tool's own default rules"
rs_rule "no style preset" 'do not import a style preset'
rs_rule "no formatter check" 'do not add a formatter check'
rs_rule "the check passes the day it is wired" 'the check passes on the day it is wired'
rs_rule "an adopted project is not turned red" 'do not turn the tick red for work nobody asked for'
rs_rule "each command is its own named step" 'put each command in its own named step'
rs_rule "the same commands go in the stack section" "write the same commands in agents\.md's stack section"
rs_rule "it follows the shared rules" 'the rules in `whole-project-reads\.md` apply'
# A run's worktrees are whole copies of the project inside it. A lint from the
# main folder would read each one again, so the floor keeps them out, and only
# them: the rules above stay as they are.
rs_rule "the checks leave the run's worktrees out" 'leave `\.agents/worktrees/` out of the type check and the lint'
rs_rule "keeping the copies out changes no rule" 'this only keeps the copies out\. it changes no rule'
# The test run reads the same copies. A runner that finds tests under
# .agents/worktrees/ runs every piece's tests again from the main folder, so
# the floor names each common runner's own setting and the two that need none.
rs_rule "the test run leaves the run's worktrees out too" 'leave it out of the test run too, wherever the project.s test runner would find tests there'
rs_rule "Vitest uses its exclude setting" "vitest's \`exclude\`"
rs_rule "Jest uses testPathIgnorePatterns" "jest's \`testpathignorepatterns\`"
rs_rule "Node's runner gets a test path that does not reach .agents/" "for node's own test runner, a test path that does not reach \`\\.agents/\`"
rs_rule "pytest and Go need nothing" 'pytest and `go test \./\.\.\.` already skip folders whose name starts with a dot, so they need nothing'
rs_rule "a runner with no setting is recorded and founding carries on" '`tests: the runner reads \.agents/worktrees/` in agents\.md.s stack section and carry on'
rs_guard "$FLOOR" "the shipped check-floor.md"

rs_reset
rs_rule "a tool finds, the agent reports" 'a tool finds, and the agent reports what the tool found'
rs_rule "engines in a written order ending in reading the code" 'the last entry is always reading the code directly'
rs_rule "the engine used is named" 'name the one used in the internal evidence'
rs_rule "an archived engine is said and skipped" 'if the tool a read would use has been archived, say so'
rs_rule "nothing is saved" 'never write a result, index or graph to a file'
rs_rule "every finding names a file and a line" 'each finding names a file and a line that exist'
rs_rule "a second look before the person sees it" 'drop any finding that does not survive the second look'
rs_rule "the three-proposal cap holds" "the quarterly visit's cap of three proposals holds"
rs_rule "the rest is summarised, not dropped" 'summarise the rest in one line'
rs_rule "nothing got worse is a complete answer" 'nothing got worse is a complete answer'
rs_rule "no score, grade or percentage" 'no score, grade or percentage reaches the person'
rs_rule "confidence set to certainty" 'run it at the setting that reports only what it is certain of'
rs_rule "nothing new to learn" 'no read introduces a term the person has to be taught'
rs_rule "no claim that the rest is fine" 'it never says that the rest of the project is fine'
rs_guard "$READS" "the shipped whole-project-reads.md"

rs_require_load_bearing "founding loads the floor" "$SETUP" 'load `references/check-floor\.md`'
rs_require "the green-tick sentence is unchanged" "$SETUP" "green means the tests really passed; red means don't merge, tell /fix"
rs_require_load_bearing "the builder runs them before hand-over" "$BUILDER" 'before handing over, run the type check and linter'
rs_require "the builder reports a failure as expected versus actual" "$BUILDER" 'a failure is a gap like any other: describe it as expected versus actual'
rs_require "the stack section asks for the commands" "$AGENTS_TEMPLATE" 'run, test, type check and lint commands'
rs_require "WORKFLOW says the check includes them" "$WORKFLOW" 'a type check and a linter wherever it has them'
rs_require_load_bearing "WORKFLOW says the checks leave a run's copies out" "$WORKFLOW" \
  'the project.s checks, its tests among them, leave those copies out'

rs_done
