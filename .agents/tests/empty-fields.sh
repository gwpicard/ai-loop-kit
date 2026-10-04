#!/usr/bin/env sh
# empty-fields.sh: guard the two words a scenario uses for a field with nothing
# in it, and the two meanings that go with them.
#
# The contract used to say "nothing happens here" six ways: none is due,
# unaffected, none required, none., unchanged, not applicable. Nothing defined
# any of them, and the grader was told about only one. So it improvised, and a
# single measured run marked an absent risk notice as nothing to see and an
# absent review as a failure, off the same construction. The verdict that came
# out of that sent a maintainer looking for a kit fault that was not there.
#
# Two words now, with opposite consequences, which is why the wording alone
# cannot be left to a reading. check-parser.sh refuses a third wording
# mechanically. This guards the meanings, which are prose and cannot be checked
# that way.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SCENARIOS="$ROOT/.agents/tests/scenarios.md"
GRADER="$ROOT/.agents/tests/replay/grader-prompt.md"

rs_init "Empty-field checks"
rs_exists "$SCENARIOS" "$GRADER"

# The contract tells the person writing a scenario which word to reach for.
rs_rule "there are exactly two words" 'one of exactly two words'
rs_rule "and they are not interchangeable" 'they do not mean the same thing'
rs_rule "none is due forbids the thing" 'says the kit must not do this'
rs_rule "and a run that does it anyway is marked against" \
  'a run that does it anyway is marked against'
rs_rule "unaffected means the scenario does not judge the field" \
  'does not exercise the field'
rs_rule "and grades to nothing either way" 'returns nothing for it either way'
rs_rule "a third wording is refused mechanically" 'fails on any other wording'
rs_guard "$SCENARIOS" "the scenario contract's header"

# The grader is the other half. A word defined in the contract and unknown to
# the grader is the exact hole this closes.
rs_reset
rs_rule "the grader is told to read which word is there first" \
  'read which one is there'
rs_rule "unaffected returns unobservable" \
  'unaffected. means the scenario does not exercise this field'
rs_rule "and the transcript does not change that" \
  'it does not matter what the transcript shows'
rs_rule "none is due is a claim about the kit" \
  'the contract is making a claim'
rs_rule "not doing it is a hit" 'where the transcript shows it did not'
rs_rule "doing it anyway is a miss, with the line quoted" \
  'shows it did anyway, quoting the line'
rs_rule "and the reason it matters is stated" \
  'work the person did not want'
rs_rule "the two are graded the same way every time" \
  'grade the two the same way every time'
rs_guard "$GRADER" "the grader prompt"

rs_done
