#!/usr/bin/env sh
# screen-rules.sh: guard the rules applied when a build touches a screen.
#
# A checklist can make an agent sound certain without earning that certainty.
# The costly version is a report that calls a screen accessible, compliant, or
# good after reading code and applying a few rules. A person may rely on that
# claim and skip the keyboard, screen-reader, or colleague check that would
# have found the problem.
#
# This check reads the screen skill back, proves the refusal is load-bearing,
# and checks the two build-time routes that call it. Conversation quality still
# needs a person to judge it. The shell check owns the quieter failure where the
# limiting rule disappears while the rest of the skill still reads well.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SCREEN="$ROOT/.agents/skills/screen-check/SKILL.md"
SECTION="$ROOT/.agents/skills/section-builder/SKILL.md"
SECOND="$ROOT/.agents/skills/second-opinion/SKILL.md"
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Screen-rule checks"
rs_exists "$SCREEN" "$SECTION" "$SECOND" "$FOUNDATION" "$WORKFLOW"

rs_rule "the skill stays out of founding, shaping, and ship" \
  'do not run at founding, shaping, or ./ship.'
rs_rule "a build with no screen does nothing" \
  'do nothing when the piece and the change have no screen'
rs_rule "project design rules win where they conflict" \
  'wins where it conflicts with a house rule'
rs_rule "the check adds no run-time dependency" \
  'do not fetch, download, install, or call a service'

rs_rule "spacing uses one scale" 'one spacing scale based on multiples of 4 or 8'
rs_rule "space groups content before boxes do" \
  'group related things with space before adding a box'
rs_rule "colour never carries meaning alone" \
  'colour is never the only carrier of meaning'
rs_rule "type stays productive and bounded" \
  'one productive type scale and no more than two weights'
rs_rule "empty, loading, and error states come before completion" \
  'empty, loading, and error states before calling the happy path finished'
rs_rule "loading treatment follows the expected wait" \
  'spinner for work expected to take 2 to 9 seconds and a real percentage after 10 seconds'
rs_rule "fields keep visible labels" 'put a visible label above every field'
rs_rule "validation waits for a filled field to lose focus" \
  'validate after focus leaves a filled field'
rs_rule "submit errors receive focus" 'move focus to an error summary'
rs_rule "errors preserve entered values" 'keep the person.s entry after an error'
rs_rule "like records use a list or table" \
  'use a list or table for like records, not a set of cards'
rs_rule "numbers align for comparison" 'right-align numbers and use tabular figures'
rs_rule "a screen has one primary action" 'each screen one primary action'
rs_rule "undo comes before confirmation" 'prefer undo to confirmation'
rs_rule "destructive buttons name outcomes" \
  'buttons that name the outcome, such as .delete. and .keep.'
rs_rule "keyboard use and focus are required" \
  'everything works from a keyboard. focus stays visible and unobscured'
rs_rule "dialogs close and return focus" \
  'escape closes a dialog and returns focus'
rs_rule "targets have a minimum size" 'targets are at least 24 pixels'
rs_rule "text contrast keeps its threshold" 'body text has at least 4.5:1 contrast'
rs_rule "control contrast keeps its threshold" 'have at least 3:1 contrast'
rs_rule "the narrow screen does not scroll in two directions" \
  'works at 400 pixels wide without scrolling in two directions'
rs_rule "button and link copy names the action" \
  'button labels use a verb and a noun. links do not say .click here.'
rs_rule "the same thing stays consistent" \
  'same thing looks and works the same way throughout the tool'
rs_rule "errors stay beside what failed" 'put an error beside the thing that failed'
rs_rule "a toast never carries an error" 'do not hide it in a toast that vanishes'
rs_rule "a modal is not an error report" 'not for reporting an error'

rs_rule "the refuse list rejects gradients" 'gradients and gradient text'
rs_rule "the refuse list rejects decorative glass" 'glass or blur used as decoration'
rs_rule "the refuse list rejects text icons" 'emoji or text glyphs used as icons'
rs_rule "the refuse list rejects nested cards" 'cards inside cards'
rs_rule "the refuse list rejects product-page hero habits" \
  'all-caps eyebrow labels and hero headings on a product screen'
rs_rule "the refuse list rejects repeated entrance motion" \
  'same entrance animation on every section'
rs_rule "the refuse list protects focus outlines" \
  '.outline: none. without a visible replacement'
rs_rule "the refuse list protects paste and zoom" 'blocked paste or disabled zoom'
rs_rule "the refuse list rejects placeholder labels" \
  'placeholder used as a label'
rs_rule "the refuse list rejects error toasts" 'toast used for an error'
rs_rule "the refuse list rejects vague confirmation" \
  'confirmation that asks only .are you sure..'

rs_rule "the skill refuses an accessibility, compliance, or quality claim" \
  'never call a screen accessible, compliant, or good'
rs_rule "following a rule proves only that rule was applied" \
  'a rule followed is evidence only that the rule was applied'
rs_rule "the report separates applied rules from unchecked ones" \
  'say which rules you applied, which you could not check'
rs_rule "the report names what a person still has to try" \
  'what a person still has to try'
rs_rule "the remaining checks include a screen reader" 'a screen reader'
rs_rule "the remaining checks include a real keyboard pass" \
  'a real keyboard pass'
rs_rule "the remaining checks include a colleague who uses the tool" \
  'a colleague who uses the tool'
rs_guard "$SCREEN" "the screen-check skill's claim boundary"

rs_require "section-builder fires for a visual piece" \
  "$SECTION" 'piece carries .visual.'
rs_require "section-builder also fires from a screen file" \
  "$SECTION" 'change touches a screen file'
rs_require_order "screen rules run before the guided manual check" \
  "$SECTION" 'load and follow .screen-check.' 'screen.s guided manual check'
rs_require "a screen fault in fix gets the rules and another fault does not" \
  "$SECTION" 'a fault on a screen gets the rules and any other fault does not'

rs_require "second-opinion checks screens during a build review" \
  "$SECOND" 'during a build review'
rs_require "second-opinion keeps the two report headings" \
  "$SECOND" 'inside the two existing report headings'
rs_require "second-opinion leaves masterplan and ship reviews alone" \
  "$SECOND" 'does not run on a masterplan review or the whole-build review during ./ship.'
rs_require_absent "second-opinion does not add a screen report heading" \
  "$SECOND" '## screen'

rs_require "project instructions name the fifth background skill" \
  "$FOUNDATION" 'screen-check'
rs_require "WORKFLOW explains when the rules run" \
  "$WORKFLOW" 'screen rules'

rs_done
