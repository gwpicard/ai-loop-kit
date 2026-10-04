#!/usr/bin/env sh
# boundary-rules.sh: guard the rules for holding a sensitive area's boundary in
# the project check.
#
# boundary-rules-rehearsal.sh proves a held boundary turns the check red. This
# half reads back the rules that keep it from becoming a red check nobody
# trusts: it is offered and never imposed, only for a boundary the masterplan
# already names, added and removed only on a yes, green on the day it is added,
# withdrawn plainly where the language has no tool, and worded in the person's
# own sentence rather than the tool's.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

RULES="$ROOT/.agents/skills/setup-ai-build-kit/references/boundary-rules.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Boundary rule rules"
rs_exists "$RULES" "$SETUP" "$MAINTAIN" "$FIT" "$WORKFLOW"

rs_rule "it follows the shared rules" 'the rules in `whole-project-reads\.md` apply'
rs_rule "only on Build with care, for a named boundary" 'on build with care, for an area that already has a `boundary:` line'
rs_rule "offered, never imposed" 'offer it, never impose it'
rs_rule "no invented boundary" 'never invent a boundary the masterplan does not name'
rs_rule "the rule is in the person's words" 'ask the person to say the rule in their own words'
rs_rule "added and removed only on a yes" 'add no rule without a yes, and take one away only with a yes too'
rs_rule "the yes is recorded on the line" 'record the yes on the area.s boundary line'
rs_rule "a language with no tool withdraws the offer" 'and withdraw the offer'
rs_rule "no imitation of a rule" 'never imitate a rule with a script that only looks like one'
rs_rule "an existing tool is kept" 'keeps that tool, and the rule is added there'
rs_rule "the comment is the sentence word for word" "the comment is the person's sentence, word for word"
rs_rule "the rule has its own named step" 'put the check command in its own step named `boundary rules`'
rs_rule "green on the day it is added" 'it has to pass'
rs_rule "a red check is described in their sentence" 'describe it to the person with their own sentence'
rs_rule "a rule follows its area" 'its rule changes or comes off with it'
rs_guard "$RULES" "the shipped boundary-rules.md"

rs_require_load_bearing "founding offers it" "$SETUP" 'load `references/boundary-rules\.md` and offer once'
rs_require_load_bearing "the quarterly visit offers it for a new area" "$MAINTAIN" 'offer the boundary rule in'
rs_require "the fit check says a boundary can be held" "$FIT" 'the project check can hold that boundary once the person agrees'
rs_require "WORKFLOW explains it" "$WORKFLOW" 'turns the tick red with your sentence beside it'

rs_done
