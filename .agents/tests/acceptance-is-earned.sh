#!/usr/bin/env sh
# acceptance-is-earned.sh: guard what has to be true before flagged work is built.
#
# The kit refuses nothing, and where the person can judge a risk it no longer
# stops either. It gives the risk notice once, in full, and if the person carries
# on, that is the acceptance: the kit writes the `Accepted:` line with their
# words and the date, and the work goes ahead.
#
# That used to be the opposite rule. "Try something else" and "just build it"
# were read as instructions about the work rather than decisions about the risk,
# so a run that gave the notice then waited for a cleaner yes. The maintainer
# decided the person who has heard who is exposed has decided, whatever words
# they use. So this guards the new definition, and it guards the two things that
# still earn the acceptance: the notice came first, and the line is on the record
# before the work starts. Silence is not carrying on, and an instruction given
# before the notice is not either.
#
# The read-back stays. Measured runs gave the notice correctly and built with
# nothing recorded, because the rule said to do the steps in order and a run
# believes it did. Reading the line back is what tells it whether it did.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIX="$ROOT/.agents/skills/fix/SKILL.md"
FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"

rs_init "Acceptance checks"
rs_exists "$FIX" "$FIT"

rs_rule "the notice is given once, in full, before the next attempt" \
  'give the notice once, in full, in one reply'
rs_rule "carrying on after the notice is the acceptance" \
  'take carrying on as the acceptance'
rs_rule "any instruction to go on counts" \
  'any instruction to go on with the work after the notice counts'
rs_rule "silence does not count, nor an instruction before the notice" \
  'silence does not, and neither does a question or an instruction given before the notice'
rs_rule "the acceptance is recorded before the work starts" \
  'build-path section before the replacement starts, with the date and the person.s own words'
rs_rule "and one collected afterwards is not an acceptance" \
  'a note about something that already happened'
rs_rule "the masterplan is read back before building" \
  'read the masterplan back before the replacement starts'
rs_rule "and the line being there decides whether building happens" \
  'let the .accepted:. line being there decide'
rs_rule "a missing line means it was not recorded, whatever was said" \
  'was not recorded whatever was said'
rs_rule "and the work waits until it is written" 'and the work waits until it is written'
rs_rule "the believed-versus-read distinction is stated" \
  'is what a run believes it did'
rs_rule "no second question for a cleaner yes" \
  'do not ask again for a cleaner yes'
rs_rule "a reply that asks for no work leaves the notice standing" \
  'leaves the work waiting and the notice standing'
rs_rule "the line is written and the work started in the same reply" \
  'start the replacement in the reply that answers them'
rs_rule "no lock is kept that only waits for the skipped caution" \
  'keep no lock that only waits for the skipped caution'
# A real acceptance was written from a choice form that came back with no
# option selected, and the line named a team's approval the person never
# mentioned. So the repair's acceptance carries the same three rules as
# fit-check.md: an empty form answer is not carrying on, the line quotes what
# the person typed or chose, and the masterplan stops contradicting it.
rs_rule "a form answer with no option selected is not carrying on" \
  'a form or menu answer with no option selected'
rs_rule "the line quotes the typed words exactly" \
  'quoted exactly as typed, in quotation marks'
rs_rule "the line names only people the person named" \
  'names only people the person named'
rs_rule "the line says when the answer was a selected option" \
  'says so when the answer was a selected option'
rs_rule "untrue masterplan sentences are corrected in the same save" \
  'correct every masterplan sentence the acceptance makes untrue in the same save'
rs_rule "the reply names the corrected sentences" \
  'name those sentences in one line'
rs_guard "$FIX" "the fix skill"

# fit-check.md is where every skill reads the rule from, so the definition has
# to hold there too.
rs_reset
rs_rule "the notice says what the person can do" \
  'what the person can do: have that done first, take the flagged thing out of scope, or carry on'
rs_rule "the notice is given once, in full, in one reply" \
  'give it once, in full, in one reply'
rs_rule "an accepted area gets no second notice" \
  'once an acceptance is recorded for an area, do not give the notice for that area again'
rs_rule "carrying on is accepting" \
  'any instruction to go on with the flagged work is the person accepting the named risk'
rs_rule "no second question for a cleaner yes" \
  'do not ask a second question to get a cleaner yes'
rs_rule "silence is not carrying on" \
  'silence, or a reply that does not ask for the flagged work'
rs_rule "an instruction before the notice is not acceptance" \
  'a person who has not been told cannot have accepted'
rs_rule "other work is not the flagged work" \
  'going on with the work outside the area is not going on with the area'
rs_rule "the line carries the date and the person's words" \
  'with the date and their own words'
rs_rule "the record goes in before the work starts" \
  'add both before the flagged work starts, not after it lands'
rs_rule "the line is read back before the work starts" \
  'let the line being there decide whether the work starts'
rs_rule "then the work goes ahead without asking again" \
  'then build what was asked for, without asking again'
rs_rule "an acceptance is never the caution done" \
  'an acceptance is never the caution done'
# A measured run recorded an acceptance and built on it after referring to "my
# earlier message" that named the options, when no reply had named who was
# exposed. Carrying on only counts after a notice the kit can point to.
rs_rule "the notice is found in a reply before anything is written" \
  'find the notice in one of your own replies'
rs_rule "remembering the notice is not finding it" \
  'remembering that you meant to give it is not finding it'
# Measured runs recorded the acceptance correctly and then asked for a further
# yes before the flagged part switched on: the plan kept a rule that stayed off
# until somebody signed, and the acceptance was read as not reaching it. That
# second question is a stop by another name, so the three rules below hold it
# shut, and the rule that silence and a question do not count stays beside them.
rs_rule "recording and starting happen in the reply that answers the person" \
  'all of this happens in the reply that answers the person carrying on'
rs_rule "that reply does not ask the person's permission again" \
  'do not end that reply on a question that asks their permission again'
rs_rule "a further question is the second question in other words" \
  'the second question in other words'
rs_rule "the acceptance reaches what the notice named in that area" \
  'the acceptance reaches what that notice named, in that area, and nothing else'
# The acceptance has an outer edge. Without these three limits, "carry on"
# could be read as switching on something nobody warned about, as settling a
# second area that never got its notice, or as the check itself being done.
rs_rule "it switches on nothing the notice did not name" \
  'it does not switch on anything the notice did not name'
rs_rule "it does not settle another area's caution" \
  'it does not settle another area.s caution, which needs its own notice'
rs_rule "the named person has still not looked, and the record says accepted" \
  'the named person has still not looked, and the record still says accepted, never done'
rs_rule "a lock whose only purpose is this caution is opened" \
  'a lock whose only purpose is to wait for this caution'
rs_rule "a real scope question may still be asked" \
  'a real question about scope, whose answer changes what gets built, may still be asked'
rs_rule "no further yes is asked to open it" \
  'do not keep the lock and ask for a further yes to open it'
# An external project recorded an acceptance from a choice form that returned
# "(no option selected)", and wrote that another team had given its approval
# when nobody had said so. A later acceptance let licensed files in while the
# masterplan's own section still said they were kept out. The rules below hold
# the empty answer out, keep the line to what the person typed or chose, and
# make the masterplan say one thing about the area once the line is written.
rs_rule "there are four things that are not carrying on" \
  'four things are not carrying on'
rs_rule "a form that came back with no option is not carrying on" \
  'a choice form or menu that came back with no option selected'
rs_rule "nor one with only a note that does not ask for the work" \
  'or with only a note that does not ask for the flagged work'
rs_rule "a selected option that asks for the work counts" \
  'a selected option whose words ask for the flagged work counts, as a typed reply does'
rs_rule "their own words are what they typed, quoted exactly" \
  'the words the person typed in this conversation, quoted exactly, in quotation marks'
rs_rule "no paraphrase and no summary" \
  'do not paraphrase them or sum them up'
rs_rule "the line names only people the person named" \
  'name only people the person named'
rs_rule "a selected option is quoted and said to be one" \
  'quote the option.s words and say it was a selected option'
rs_rule "over several messages, quote the one that asks for the work" \
  'quote the one that asks for the flagged work'
rs_rule "a secret or personal detail is cut and marked" \
  'quote the rest and mark the cut with .\[removed\].'
rs_rule "the cut points at the secrets rule" \
  'the project.s secrets rule already says a secret is never written down'
rs_rule "every sentence the acceptance makes untrue is found" \
  'every sentence the acceptance makes untrue'
rs_rule "which sentences those are" \
  'excluded, off, kept out, or waiting for the caution'
rs_rule "each is corrected in the present tense, saying the risk was accepted" \
  'correct each one to match, in the present tense, and say the risk was accepted'
rs_rule "in the same save as the line" \
  'in the same save as the .accepted:. line'
rs_rule "a sentence in another record is corrected too" \
  'a sentence like that in another record, such as agents.md or a concept file'
rs_rule "the reply says in one line which sentences changed" \
  'say in one line which sentences changed'
rs_rule "with nothing untrue, nothing else changes and nothing extra is said" \
  'where no sentence is made untrue, change nothing else and say nothing extra'
rs_guard "$FIT" "the shipped fit-check.md"

# /ship and founding are the other two places the kit used to stop. Each now
# gives the notice and carries on when the person does, and neither may drift
# back to a stop.
SHIP="$ROOT/.agents/skills/ship/SKILL.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"

rs_reset
rs_rule "ship gives the notice once at a person caution" \
  'give the risk notice here, once and in full'
rs_rule "an area already accepted gets no second notice" \
  'where an acceptance is already recorded for the area, give no notice'
rs_rule "carrying on writes the line with words and date" \
  'if the person carries on after the notice, write the .accepted:. line with their words and the date'
rs_rule "the area reads accepted, never done" \
  'line .accepted., never .done.'
rs_rule "silence or other work leaves only that area behind" \
  'silence, a question, or a request for other work is not carrying on'
rs_rule "nor is a form answer with nothing chosen" \
  'nor is a form answer with nothing chosen'
rs_rule "ship goes on in the same reply with no further question" \
  'go on in the same reply, without a further question about that area'
rs_rule "ship opens a lock that only waits for this caution" \
  'a lock whose only purpose is to wait for this caution opens with the acceptance, unless the person asks to keep it'
rs_guard "$SHIP" "ship's Build with care steps"
rs_require_absent "ship no longer stops at a person caution" "$SHIP" 'stop at it'
rs_require_absent "ship no longer halts on an area without a status" "$SHIP" 'do not carry on past one'

rs_reset
rs_rule "founding gives the notice once" \
  'give the risk notice fit-check.md describes, once and in full'
rs_rule "carrying on writes the acceptance with words and date" \
  'if the person carries on after it, write their acceptance'
rs_rule "founding goes on either way" \
  'founding goes on anyway'
rs_rule "founding goes on in the same reply with no further yes" \
  'go on in that same reply. do not ask a further yes'
rs_rule "founding keeps no rule that only waits for the skipped caution" \
  'do not keep a rule in the plan that only waits for the caution they skipped'
rs_guard "$SETUP" "the founding fit-check step"

rs_reset
rs_rule "the project's instructions give the notice once" \
  'give the risk notice once, in full'
rs_rule "carrying on is the acceptance there too" \
  'if the person carries on after the notice, that is their acceptance'
rs_rule "silence is not carrying on" 'silence is not carrying on'
rs_rule "the project builds in the same reply with no further yes" \
  'build in that same reply, with no further yes asked for'
rs_rule "the project opens a lock that only waits for that caution" \
  'a lock that only waits for that caution opens with it, unless the person asks to keep it'
rs_rule "the record never calls the caution done" \
  'accepted, never that the caution was done'
rs_guard "$FOUNDATION" "the project's own AGENTS.md template"
rs_require_absent "the project's instructions no longer stop at a person" "$FOUNDATION" "stop where it is a person"

# /implement builds through section-builder, whose flagged route used to stop
# at the condition whatever the person said. It now gives the notice and builds
# when the person carries on. A run with nobody present still stops, because
# accepting on the person's behalf is the one thing no run may do.
SECTION="$ROOT/.agents/skills/section-builder/SKILL.md"
IMPLEMENT="$ROOT/.agents/skills/implement/SKILL.md"
RUNNING="$ROOT/.agents/skills/implement/references/running-longer.md"

rs_reset
rs_rule "the flagged route gives the notice before building in the area" \
  'before building inside the area, give the risk notice once, in full'
rs_rule "carrying on writes the line and the piece is built" \
  'if the person carries on after it, write the .accepted:. line with their words and the date, read it back, and build and save the piece on the pull-request route'
rs_rule "an unattended run never accepts for the person" \
  'in an unattended run nobody is there to carry on, so never write an acceptance on the person.s behalf'
rs_rule "a recorded acceptance makes it the pull-request route" \
  'where the person carried on and the acceptance is recorded, this is the pull-request route'
rs_rule "a blocked piece waits until the person carries on" \
  'or the person carries on after the notice and the acceptance is recorded'
rs_rule "the flagged route asks no further question before the build" \
  'do this in the reply that answers them, and do not ask a further question before the build'
rs_rule "the flagged route opens a lock that only waits for this caution" \
  'a lock whose only purpose is to wait for this caution opens with the acceptance, unless the person asks to keep it'
rs_guard "$SECTION" "section-builder's flagged route"
rs_require_absent "section-builder no longer requires the condition before merge" "$SECTION" 'must be met before merge or live activation'
rs_require_load_bearing "implement lets a blocked piece go on when the person carries on" "$IMPLEMENT" \
  'until the person carries on after the risk notice and the acceptance is recorded'
rs_require_load_bearing "an unattended run still stops at a sensitive area" "$RUNNING" \
  'at any touch of a named sensitive area'

# The story is told in WORKFLOW.md as well, so a person reading it knows an
# empty form is not a yes and what the line will say.
WORKFLOW="$ROOT/WORKFLOW.md"
rs_require_load_bearing "WORKFLOW.md says an empty form answer is not carrying on" "$WORKFLOW" \
  'nor is a form sent back with nothing chosen'
rs_require_load_bearing "WORKFLOW.md says the line quotes the person exactly" "$WORKFLOW" \
  'your words quoted exactly as you typed them, or the option you chose'
rs_require_load_bearing "WORKFLOW.md says contradicting sentences are corrected" "$WORKFLOW" \
  'any sentence elsewhere that still says the thing is kept out is corrected in the same save'

rs_done
