#!/usr/bin/env sh
# question-box.sh: guard how clarify asks a question, and what happens when
# nobody answers it.
#
# A machine cannot watch a question box without paying a model, so this guards
# the written route clarify reads. The question is one short sentence with a
# labelled guess. Choices appear only when the real answers form a short,
# complete list, with the guess first and free text kept. The route depends on
# who is there: the tool the session really exposes, the plain-words fallback,
# or a background agent passing the question to the session that started its
# run.
#
# The rule that matters most is the one for a person who is not there. An
# earlier version set such a piece aside in a parked state. There is no parked
# state now, so the piece stays in its sub-state with the question and the
# labelled guess written on it, and /shape names it as waiting for the person.
# A guess written as an answer is the failure this exists to prevent: the
# question would read as settled and the build would rest on the guess.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

CLARIFY="$ROOT/.agents/skills/clarify/SKILL.md"

rs_init "Question-box checks"
rs_exists "$CLARIFY"

# The box itself.
rs_rule "one question at a time, in one short sentence" \
  'one question at a time, in one short sentence'
rs_rule "background stays short" 'background is at most two short sentences'
rs_rule "the guess is labelled" 'label the best guess as a guess'
rs_rule "choices only for a short, complete list, with the guess first" \
  'when the real answers are a short and complete list, offer them as choices and put the guess first'
rs_rule "an open answer stays open" 'with the answer left open'
rs_rule "free text survives" 'preserve free-text answers'

# Where to ask.
rs_rule "the session's role and real tools are read first" \
  'read the session.s role and the tools it actually exposes'
rs_rule "a terminal is not proof of a person" \
  'a terminal alone does not prove a person is present'
rs_rule "a background agent asks through the session that started the run" \
  'a background agent in a run asks through the session that started the run, even if a local question tool is exposed'
rs_rule "a present person gets the exposed tool" \
  'use the actual exposed question tool when its supported schema can reach that person'
rs_rule "the tool's own cardinality is followed" 'follow the actual tool cardinality'
rs_rule "free text without choices is used where supported" \
  'if the tool supports free text without choices, use that'
rs_rule "no invented options" 'never invent choices to satisfy a minimum option count'
rs_rule "an unsuitable tool falls back to plain words" \
  'if no supported question tool is available, or its schema cannot express this question, ask in concise plain words'
rs_rule "the fallback keeps the question and the guess" \
  'keep the same question and clearly labelled guess in the fallback'

# What is not an answer.
rs_rule "an empty submission, a cancellation or silence is no answer" \
  'an empty submission, a cancellation, or a preselected option never submitted is no answer, and neither is silence'
rs_rule "no answer or consent is ever invented" 'never invent a human answer or consent'
rs_rule "delivery is not an answer" 'delivery alone is not an answer'
rs_rule "an unattended run opens no question box" \
  'never open a human question box in an unattended run'

# The rule that replaces parking.
rs_rule "nobody there: the question and guess stay on the piece in its sub-state" \
  'leave the exact question and the labelled guess on the piece under `## open question`, and the piece stays in its sub-state'
rs_rule "/shape names it as waiting for the person" \
  '`/shape` names it as waiting for the person'
rs_rule "no guess is ever written as an answer" 'no guess is ever written as an answer'
rs_rule "an unsaved question is never claimed saved" 'never claim it was saved'

# The replay harness and the other rules this must not loosen.
rs_rule "a headless replay asks in plain words" \
  'a headless replay with a scripted plain-text interlocutor uses the plain-words route'
rs_rule "the question stays in the reply for the turn gate" \
  'leave the question in the reply text so the scripted turn gate can see it'
rs_rule "founding's non-gates stay non-gates" \
  'this routing does not turn a founding non-gate into a required answer'
rs_rule "acceptance is still earned" 'earned-acceptance rules still apply'
rs_guard "$CLARIFY" "clarify's question box"

# The old rule set a piece aside. Put back, it would sit beside "stays in its
# sub-state" and the two would disagree with every rule above still present.
rs_require_absent "clarify sets no piece aside in a parked state" "$CLARIFY" 'park'

rs_done
