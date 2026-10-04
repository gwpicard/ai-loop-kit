#!/usr/bin/env sh
# notice-is-owed-by-the-refusal.sh: guard what triggers the risk notice after a
# repair has failed three times.
#
# The wording used to hang the notice on the route taken after stopping: three of
# the six escalation routes carried it and the others did not. Measured runs show
# what that costs. In five runs of five, driven by sonnet, the kit did the hard
# part correctly and stopped short of a fourth patch, and in none of them did the
# notice arrive. It reached a route that owed nothing: it decided the cause was
# established after all, or that there was no evidence for a cause worth patching.
# Both are conclusions about the work, and the person was left with a refusal and
# no reason.
#
# So the trigger is the refusal, not the route. That was the first rule here, and
# on its own it changed nothing: a second five runs held 0 of 5 too. The reason
# is upstream of the route. The kit never agreed it had reached three attempts.
# It counted the fixes it considered to have counted, not the fault surviving,
# and said so plainly: "it's not actually three tries, it's one fix, made once,
# and it has never been merged", and later "we are not at that point".
#
# That reasoning is defensible, which is what makes this the interesting case.
# One fix sat unmerged and the tool everyone used was unchanged, so the kit was
# right about the facts and still left the person with a refusal and no reason.
# Being right about the count is not a reason to withhold the notice, because
# the person is relying on something broken either way.
#
# So two rules are guarded here: the refusal owes the notice whichever route
# follows, and the threshold is the fault surviving rather than the kit's own
# tally.
#
# The kit no longer stops for good after the notice. Declining the fourth attempt
# is a pause: if the person carries on after hearing the notice, the attempt goes
# ahead with their acceptance on the record. The notice is still owed at the
# pause, which is what this guards; acceptance-is-earned.sh guards the record.
#
# The same runs show two timing failures worth their own rules: who is exposed
# named early, as a general worry about the bug, and the notice given only after
# the person had asked again for the work. A notice that arrives after the
# decision cannot change it.
#
# The same scenario holds 4 of 5 driven by opus on the same kit, so nothing here
# can be proved by a run on the stronger model. That is the reason it is written
# down as a rule rather than left to the rate.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIX="$ROOT/.agents/skills/fix/SKILL.md"

rs_init "Notice trigger checks"
rs_exists "$FIX"

rs_rule "the refusal owes the notice, not the route chosen after it" \
  'declining the fourth attempt is what owes the notice, not the route'
rs_rule "it goes in the same reply that declines" \
  'in the same reply that declines'
rs_rule "every route owes it" 'every route owes it'
rs_rule "including the route that concludes the cause is established" \
  'the cause is established after all'
rs_rule "a conclusion about the work changes nothing about what is said" \
  'changes nothing about what the person is told'
rs_rule "three failures is when that conclusion is least reliable" \
  'least reliable moment to trust your own conclusion'
rs_rule "a refusal without it leaves a refusal and no reason" \
  'a refusal and no reason'
rs_rule "naming the exposed early does not discharge it" \
  'is not this notice and does not discharge it'
rs_rule "giving it after they ask again is too late" \
  'they have decided without it'

rs_rule "three is counted by the fault surviving" \
  'count the fault surviving, not your own tally'
rs_rule "an unmerged or differently-tried attempt still counts" \
  'whether or not each attempt was merged, deployed, or tried the way you'
rs_rule "disputing the count does not postpone the notice" \
  'correcting it does not postpone the notice'
rs_rule "the correction and the notice go in the same reply" \
  'give the notice in the same reply'
rs_rule "a correction alone leaves them with nothing to decide" \
  'told they are wrong, with nothing to decide'

# Stopping short of a fourth attempt is a pause for the person, not a refusal
# they cannot get past. The notice says what they can do, and carrying on after
# it is theirs to choose.
rs_rule "stopping is a pause for the person to decide" \
  'stopping here is a pause for the person to decide'
rs_rule "carrying on after the notice lets the next attempt go ahead" \
  'if they carry on after it, the next attempt goes ahead on the record'
rs_rule "one more go after the notice is carrying on" \
  'asking for one more go after hearing the notice is the person carrying on'

rs_guard "$FIX" "the fix skill's escalation notice"

# The notice is worth nothing if it is withdrawn the moment somebody objects, so
# the paragraph that holds it has to survive beside the one above.
rs_require "the notice is held against pressure" "$FIX" \
  'none of them is a reason the fault is now understood'

# The contract the replay grades against still asks for the same notice at the
# same moment. If these two ever disagree, the skill has been rewritten to pass
# a test rather than to behave.
rs_require "the contract still expects the notice when the area is named as sensitive" \
  "$ROOT/.agents/tests/scenarios.md" \
  'raised once the route names the area as sensitive'

rs_done
