#!/usr/bin/env sh
# shaping-sub-states.sh: guard the one route every piece takes through shaping.
#
# A piece is shaped through sub-states, and each one holds a different job:
# raw holds the person's words, research finds facts, clarify asks the person,
# prototype shows them something, spec writes the contract and check runs the
# readiness check. The rules for each live as prose in change-triage and
# /shape, so this reads them back and proves each one load-bearing.
#
# The first part guards triage in raw and the bug fast path. Triage writes the
# type, a guess at the loop module, any overlap and the first open question
# onto the piece, then moves it on. Two failures matter most. A guess written
# as if it were the bar would pass the ready-gate lint as a decided loop
# module. And a bug with a reproduction a person can follow that is still sent
# round the questions makes the person answer what they already said.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

TRIAGE="$ROOT/.agents/skills/change-triage/SKILL.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"

rs_init "Shaping sub-state checks"
rs_exists "$TRIAGE" "$SHAPE"

# --- triage in raw, in change-triage ------------------------------------------

# The report check /fix made before a repair. Without it a wish worded as a
# complaint is shaped as a bug, and the fix loop hunts for a fault nobody made.
rs_rule "a repair of promised behaviour is told from a wish against the masterplan" \
  'behaviour the masterplan promised and the tool does not do is a repair, and becomes `type:bug`'
rs_rule "a wish the masterplan never made becomes type:feature" \
  'behaviour the masterplan never promised is a wish, however it is worded, and becomes `type:feature`'

rs_rule "raw triage writes its findings on the piece before it moves" \
  'triage it and write what it found on the piece, in this order, before it moves'
rs_rule "it writes the type label first" 'its `type:` label, from step 1.s comparison with the masterplan'
rs_rule "the loop module is written as a marked guess" \
  'under `## loop`: `loop module: <module> \(guess, <one line why>\)`'
rs_rule "so the lint never reads a guess as the bar" 'so the lint never reads a guess as the bar'
rs_rule "spec replaces the guess" \
  '`shaping:spec` replaces the line with the module the contract is written for'
rs_rule "overlaps with open and closed pieces are written on the piece" \
  'any piece this one repeats or overlaps, open or closed, completed or not planned, under `## overlaps`'
rs_rule "a not-planned match brings its reason back" \
  'add the reason it was left out'
rs_rule "the first open question is written under Open question" \
  'the first open question, under `## open question`'
rs_rule "the piece moves to the sub-state of that question" \
  'move it through the gate to the sub-state that answers that question'
rs_rule "or to spec when there is none" \
  'with no open question, move it to `shaping:spec`'
rs_rule "the fit check comes before any sub-state" \
  'stops for the fit check before the piece moves to any sub-state'

# The bug fast path. Each route removed sends a bug the wrong way: one with a
# reproduction is asked for it again, one without is specified from a guess.
rs_rule "a bug with a reproduction a person can follow" \
  'a `type:bug` piece with a reproduction a person can follow'
rs_rule "the reproduction is steps, expected result and actual result" \
  'the steps, the expected result and the actual result'
rs_rule "it goes straight from raw to spec" 'it goes from `shaping:raw` straight to `shaping:spec`'
rs_rule "and takes loop:fix" \
  'takes `loop:fix`: write `loop module: fix` under `## loop` with no guess mark'
rs_rule "the fix label is written directly" '`gh issue edit <number> --add-label loop:fix`'
rs_rule "a bug with no clear reproduction goes to clarify with the missing step" \
  'a bug with no clear reproduction goes to `shaping:clarify` with the missing step as its question'
rs_guard "$TRIAGE" "change-triage"

# The capture path still files a note untriaged; the triage waits for /shape.
rs_require_order "triage in raw sits inside the routing step" "$TRIAGE" \
  '^## Step 4: Route' '^### Triage in raw'

# --- /shape -------------------------------------------------------------------

rs_reset
rs_rule "a raw piece is triaged first" \
  'a piece in `shaping:raw` is triaged first, as change-triage.s "triage in raw" says'
# The order is one rule: a piece that needs nobody is taken before one that
# needs the person, and new raw notes come last so half-shaped work finishes.
rs_rule "typed alone, /shape takes pieces in one order" \
  'a piece with a `## kickback` section first, then a piece waiting in `shaping:check`, then `shaping:research`, which needs nobody, then `shaping:clarify` and `shaping:prototype` when the person is there, then `shaping:spec`, then the oldest `shaping:raw`'
rs_rule "a fast-path bug is offered to /implement once ready" \
  'offer `/implement <number>` as soon as it is ready'
rs_rule "spec replaces a guessed loop module" 'replace a guessed `loop module:` line'
rs_rule "and writes the loop label where the piece has none" \
  'where it has none, `gh issue edit <number> --add-label loop:<module>`'
rs_rule "an unreachable GitHub files nothing" \
  'where github cannot be reached when a request would become a piece, nothing is filed'
rs_rule "and the person's words are repeated back" \
  'repeat the person.s words back to them in full'
rs_guard "$SHAPE" "the /shape skill"
rs_require_absent "/shape no longer takes the lowest-numbered piece in shaping" \
  "$SHAPE" 'take the lowest-numbered piece still in shaping'

rs_done
