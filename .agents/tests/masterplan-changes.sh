#!/usr/bin/env sh
# masterplan-changes.sh: guard the record that a finished piece leaves on the
# masterplan. A missing change or a mark advanced past unread work can make a
# stale page look current, so each rule must fail when removed.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

RECORD="$ROOT/.agents/skills/setup-ai-build-kit/references/masterplan-changes.md"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
FORM="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/piece-issue.yml"
TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
COVERAGE="$ROOT/.agents/skills/setup-ai-build-kit/references/coverage-read.md"

rs_init "Masterplan change checks"

rs_rule "every build path carries the record" 'these rules apply on every build path'
rs_rule "save applies the recorded change to checked behaviour" 'at save time, read the piece.*apply it to the named section, checking it against the behaviour that was actually built'
rs_rule "nothing leaves the page alone" 'a value of "nothing" leaves the prose alone'
rs_rule "a blocked capability is never described as live" 'a safely blocked capability stays described as waiting'
rs_rule "recovery reads landed pieces including closed ones" 'pieces whose work landed, including closed pieces'
rs_rule "recovery applies only the missing change" 'apply only what is still missing'
rs_rule "later changes take precedence" 'follow landing order and the current tool'
rs_rule "repeating recovery cannot duplicate or restore removed behaviour" 'repeating /sync must not add the same line twice or restore something deliberately removed'
rs_rule "a missing old field is not nothing" 'recover its change from that work rather than treating absence as "nothing"'
rs_rule "the mark records the checked code state" 'one `trued against: <full commit hash>` line beside the masterplan'
rs_rule "the person never maintains the mark" 'never ask the person to understand or maintain it'
rs_rule "the mark never skips unread changes" 'never move it past work that has not been checked'
rs_rule "dirty work cannot advance the mark" 'or past uncommitted work that /sync must leave alone'
rs_rule "building saves the checked code before its mark" 'saves the checked code, then writes that saved commit into the mark'
rs_rule "record save stays on the piece's route" 'both commits belong to the same piece and pull request'
rs_rule "sync marks the saved state it reconciled" 'sync uses the current saved commit it has just reconciled'
rs_rule "the mark cannot contain its own future hash" 'neither tries to write the hash of the commit that will contain the mark'
rs_rule "drift reads the shared branch" 'read the mark on the current shared branch'
rs_rule "merged work counts once" 'count each change once along the first-parent history'
rs_rule "saving the mark cannot create drift" 'leave records-only commits out'
rs_rule "unmerged work does not count as landed" 'do not include unmerged work'
rs_rule "the count follows code subjects, including moved paths" 'data, permissions or connections sections\. follow renamed paths'
rs_rule "the map is optional on other paths" 'do not require one on the other build paths'
rs_rule "several files do not multiply one subject change" 'count a change once for each subject it touched'
rs_rule "non-zero subject counts earn one line and sync" 'when any subject count is non-zero, give one line with the total and the affected subjects, then offer /sync in that same line'
rs_rule "zero subject counts stay quiet" 'stay quiet when all three counts are zero'
rs_rule "missing history cannot become a guessed count" 'available history is incomplete, do not invent a count or reset the mark'
rs_rule "maintenance never marks work as checked" 'maintenance reports the gap; it never moves the mark itself'
rs_guard "$RECORD" "the masterplan change rules"

rs_reset
rs_rule "the field is always plain and on the surface" '`## masterplan change` is always on the surface, in plain words'
rs_rule "a piece names what the page gains, changes or loses" 'name the section and what it gains, changes or loses when this piece lands'
rs_rule "most pieces may say nothing" 'most pieces say "nothing"'
rs_rule "writing the change does not apply it early" 'writing it does not apply it early'
# A replayed piece that sorted a list wrote "nothing", because the masterplan
# already promised the list. The rule never reached the page, and nothing
# downstream could notice, since save applies the field exactly as written.
rs_rule "nothing is tested line by line against the page" 'read each line of `## done when` against the masterplan alone, and write "nothing" only when the masterplan already says it'
rs_rule "a narrower checkable rule is still a change" 'is a change even when it narrows a promise the masterplan already makes'
rs_guard "$PIECES" "the piece shape"

rs_reset
rs_rule "the issue form carries the field" 'id: masterplan-change'
rs_rule "the form asks for plain words and allows nothing" 'in plain words, name the section and what it gains, changes or loses when this lands\. write "nothing"'
rs_rule "the form requires the field" 'placeholder: what it does gains a weekly summary email\. validations: required: true'
rs_guard "$FORM" "the issue form"

rs_require_load_bearing "a new page starts honestly unchecked" "$TEMPLATE" 'trued against: not yet checked'
rs_require_load_bearing "shape writes the field before ready" "$SHAPE" 'write `## masterplan change` on the surface before marking it ready'
rs_require_load_bearing "shape reads the change back in plain words" "$SHAPE" 'when this lands, the masterplan gains a weekly summary email'
rs_require_load_bearing "shape writes nothing only after the test" "$SHAPE" 'write "nothing" only when the masterplan already says every line of `## done when`'
rs_require_load_bearing "shape reads the change back where the piece is reported" "$SHAPE" 'read it back in the reply that reports the piece'
rs_require_load_bearing "the issue form says a new rule is a change" "$FORM" 'a new rule, such as a sort order, is a change'
rs_require_load_bearing "WORKFLOW says a checkable rule is a change" "$ROOT/WORKFLOW.md" 'a new rule you could check, such as a list now sorted by name, counts as a change'
rs_require_load_bearing "building applies it before saving on every route" "$BUILDER" 'before saving on any route, apply the piece'
rs_require_load_bearing "building updates the mark using its owner" "$BUILDER" 'update the trued-against mark as the `setup-ai-build-kit` skill.s `references/masterplan-changes\.md` describes'
rs_require_load_bearing "sync recovers unapplied changes and moves the mark" "$SYNC" 'merge each landed piece.*that has not yet been applied, and move the trued-against mark'
rs_require_load_bearing "a current changelog cannot hide an older mark" "$SYNC" 'read from the older of that mark and the last changelog entry'
rs_require_load_bearing "monthly maintenance reads the count rules" "$MAINTAIN" 'count landed changes since it using the `setup-ai-build-kit` skill.s `references/masterplan-changes\.md`'
rs_require_load_bearing "monthly maintenance offers sync in one line" "$MAINTAIN" 'report the count and offer /sync in one line'
rs_require_load_bearing "coverage reads the recorded change" "$COVERAGE" 'read each piece.*masterplan change.*alongside its promised result'
rs_require_load_bearing "coverage does not turn unapplied work into a new piece" "$COVERAGE" 'it must not be offered as a new piece'
rs_require_load_bearing "WORKFLOW explains what the person sees" "$ROOT/WORKFLOW.md" 'each piece says what it changes in the masterplan'
rs_require_load_bearing "WORKFLOW explains the monthly count" "$ROOT/WORKFLOW.md" 'the monthly visit uses that point to say how much work has since touched'

rs_done
