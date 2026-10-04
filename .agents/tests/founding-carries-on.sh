#!/usr/bin/env sh
# founding-carries-on.sh: guard the ending of the step that tries to talk the
# person out of building.
#
# Testing the need for software is a real step and a good one. Saving a team a
# project it does not need is worth more than the project. The step used to end
# "say so, say what would do instead, and stop", and it had no clause for the
# person who hears the case and wants the tool anyway.
#
# So the kit invented an ending for itself, differently each time. Measured
# across five runs of an ordinary internal booking tool: the runs that held made
# the case and then proceeded, one ending "I'm not refusing to build this". The
# runs that failed asked the same question again, three and four turns running,
# after the person had said "Can you just get it set up so I can start
# building?". Founding never completed, so nothing was ever saved.
#
# The rules below are that missing ending. They are prose a coding agent reads,
# so this reads the source: the rule is still there, and removing it breaks the
# check. What the kit then does with it is measured by the replay harness, not
# here.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Founding carries on checks"
rs_exists "$SETUP" "$WORKFLOW"

# The case is still made. A check that only forbade stopping would delete the
# step, and the step is the point.
rs_rule "the cheaper option is still named" 'say what would'
rs_rule "and the case is made once" 'say so once, plainly'
rs_rule "in one reply, at this step" 'the case is made in one reply'

# The ending that was missing.
rs_rule "wanting it anyway is a decision, not a fault" \
  'that is their decision and not'
rs_rule "the cheaper option and the choice are recorded" \
  'record the cheaper option and the choice'
rs_rule "and founding carries on" 'the masterplan, and carry on founding'
rs_rule "the case does not end the turn" 'do not end the turn on it'
rs_rule "and does not ask which way they want to go" \
  'do not ask which way they want to go'
rs_rule "nor wait for an answer" 'do not wait for an answer'
rs_rule "naming the cheaper product is the whole of it" \
  'naming a product they might already have is enough'
rs_rule "nobody is sent to an administrator" 'turns a remark into an errand'
rs_rule "the question is not asked again" 'do not ask the question again'
rs_rule "the interview is not held open for it" 'do not hold the interview open'
rs_rule "and no answer is a condition of founding" \
  'never make an answer a condition of founding'

rs_guard "$SETUP" "the /setup-ai-build-kit skill"

# The same shape for anything else founding would like to know but does not
# need. This lived inside step 4 for one run, which is where it was measured
# failing: the rule was right, and it governed the step it sat in rather than
# the skill, so founding sailed past it and stalled five steps later on the
# ownership check instead. It is a standing rule now, and rs_require_order below
# is what keeps it one.
rs_reset
rs_rule "no step is a gate" 'none of them is a gate'
rs_rule "founding is finished when the project exists and is saved" \
  'the project exists and a checkpoint is saved'
rs_rule "and that outranks any answer still missing" \
  'outranks any answer still outstanding'
rs_rule "an unneeded answer becomes an open question with a guess beside it" \
  'your best guess recorded beside it'
rs_rule "asked later, once there is a project to change" \
  'once there is a project to change'
rs_rule "a step that says to check something is not an interview question" \
  'is a check, not an interview question'
rs_rule "a step that says to answer from the masterplan is answered there" \
  'answer from the masterplan, answer from the masterplan'
rs_rule "a gap found that way is recorded, not asked about" \
  'told what was recorded rather than asked to fill it in'
rs_rule "get on with it answers everything at once" \
  'answered everything outstanding at once'
rs_rule "the assumptions are said in one line and the project stood up" \
  'say in one line what you assumed'
rs_rule "because founding that stands nothing up has helped nobody" \
  'has helped nobody'
rs_rule "and every answer can be changed later, an unfounded project cannot" \
  'an unfounded project cannot'
rs_guard "$SETUP" "the standing founding rule"
rs_reset

# The same shape again, one step later. Founding fills in README.md's
# placeholders, and where the kit arrived as a whole copy there are none: the
# kit's own read-me is sitting at that path. Without a clause for that, the kit
# reaches the last step of founding, finds real documentation where it expected
# a blank, and stops to ask permission it was never going to need.
rs_reset
rs_rule "a read-me without placeholders is somebody's real file" \
  'holds no such placeholders'
rs_rule "a whole-copy install is named as how that happens" \
  'arrived as a whole copy of the kit'
rs_rule "it is left exactly as it is" 'leave it exactly as it is'
rs_rule "the description goes to the masterplan and AGENTS.md instead" \
  'going into masterplan.md and agents.md instead'
rs_rule "and founding carries on" 'instead, and carry on'
rs_rule "it is never overwritten" 'never overwrite it'
rs_rule "and founding never stops to ask about it" \
  'never stop to ask which the person would prefer'
rs_rule "because the read-me is the cheap thing and the founding is not" \
  'cheapest thing in the project to change later'
rs_guard "$SETUP" "the read-me step"
rs_reset

# The founding save. A measured run built the whole tool, committed it, pushed
# it and opened a pull request, because a remote happened to be reachable and
# section-builder's route taxonomy reads a tool twenty people will share as
# pull-request work. That taxonomy is about the pieces built afterwards. The
# founding commit stands an initial state up, and founding has already promised
# the person nothing will be uploaded.
rs_reset
rs_rule "the founding save is always the checkpoint route" \
  'always the checkpoint route'
rs_rule "whatever the tool later becomes" 'whatever the tool will grow into'
rs_rule "because it stands up a state rather than changing a live one" \
  'rather than changing anything anybody relies on'
rs_rule "it is not pushed" 'do not push it'
rs_rule "no pull request is opened for it" 'do not open a pull request for it'
rs_rule "and a reachable remote is not a reason to" \
  'reachable as a reason to use one'
rs_rule "the promise made earlier in founding is kept" \
  'nothing will be uploaded., and that has to stay true'
rs_rule "the route taxonomy is scoped to the pieces after it" \
  'about the work, not about this'
rs_guard "$SETUP" "the founding save step"

# The masterplan review. It used to stop founding until the review had happened,
# with no exit where there was nobody to ask, and two measured runs lost their
# whole founding to it.
rs_reset
rs_rule "the build path decides whether the review runs" \
  'decides whether it runs'
rs_rule "it runs where somebody else will be relied on" \
  'somebody other than the builder is going to be relied on'
rs_rule "and is skipped for an ordinary internal tool" \
  'on build and run it, skip it'
rs_rule "because a review nobody needed is a wait nobody asked for" \
  'costs the person a wait they did not ask for'
rs_rule "the skip is said and recorded" 'say in one line that it was skipped'
rs_rule "so a project that later moves up knows it never happened" \
  'knows this never happened'
rs_rule "no independent method is a recorded gap, not a stop" \
  'record it in the changelog as a setup gap'
rs_rule "and founding carries on" 'carry on founding. do not wait'
rs_rule "the unbounded wait is named as what it was" 'a wait that never ends'
rs_rule "and weighed against what it cost" \
  'never stood up is not worth trading for it'
rs_guard "$SETUP" "the masterplan review step"
rs_reset

# Where founding is standing. A fresh installation leaves the kit's own files in
# the project root, so the folder reads exactly like the kit's source, and two
# measured runs refused to interview at all until they were told which folder to
# use. Guessing from how the folder looks is the fault; there is a marker that
# settles it, and it is checked rather than described.
rs_reset
rs_rule "a folder holding only the kit is the normal place to found" \
  'not a reason to stop'
rs_rule "and looking like the source is not evidence" \
  'the answer is not to guess from how it looks'
rs_rule "the release marker settles it" 'look for ..ai-build-kit-version'
rs_rule "which the source never carries" 'the kit.s source never does'
rs_rule "so founding happens there without asking" 'found here without asking'
rs_rule "the one place it does not belong is named by its own files" \
  'release-manifest.txt., ..agents/tests/. and .docs/maintaining.md'
rs_rule "and only those justify stopping" 'only where those are present'
rs_rule "a location is never what founding waits on" \
  'never make a location the thing founding waits on'
rs_rule "because the wrong folder costs a move and no folder costs everything" \
  'a project never founded costs everything'
rs_guard "$SETUP" "the where-am-I step"

# The save identity. It asked before saving, and two measured runs lost their
# checkpoint to the question. The rule it protects, never invent a real
# identity, is untouched: a neutral project-only label is not an identity.
rs_reset
rs_rule "no real identity is ever invented" 'never invent a real identity'
rs_rule "nor the last author copied" "never copy the latest commit's author"
rs_rule "a missing one does not stop the save" 'do not stop for one'
rs_rule "the neutral label is used instead" 'local project user'
rs_rule "the person is told which label and that it can change" \
  'that it can be changed'
rs_rule "and the real identity becomes an open question" \
  'record the real identity as an open question'
rs_rule "the reason the label is allowed is stated" \
  'a neutral label is not an invented identity'
rs_rule "and what waiting would have cost" 'costs the whole founding'
rs_guard "$SETUP" "the save-identity step"
rs_reset

# Placement is the whole point of this one. A rule that sits inside a numbered
# step governs that step; the same words above the steps govern all of them.
# That difference was measured, so it is asserted rather than trusted.
# rs_require_order reads the file as written rather than folded and lowered, so
# these two patterns keep their capitals where every other pattern here drops
# them.
rs_require_order "the standing rule is stated above the numbered steps" \
  "$SETUP" '^## Founding ends with something stood up' '^## 0\.'

# The person reads WORKFLOW.md, not the skill. A rule the kit follows and the
# person cannot predict is a surprise, and this one changes what they see.
rs_require "WORKFLOW.md says the case is made once" \
  "$WORKFLOW" 'it makes that case once'
rs_require_load_bearing "and that founding carries on when they still want it" \
  "$WORKFLOW" 'gets on with founding rather than asking again'

rs_done
