#!/usr/bin/env sh
# masterplan-edges.sh: guard ownership facts, deferred terms and the length
# offer. Each can disappear quietly while the records still look complete.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
CLARIFY="$ROOT/.agents/skills/clarify/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Masterplan edge checks"

rs_rule "the fit check owns present running facts" 'the fit check owns the present ownership facts in "how it stays running"'
rs_rule "the changelog records the check without its answers" 'the changelog records only that the ownership check ran and when, without copying its answers'
rs_rule "a later read returns changed facts to the same owner" 'a later ownership check reads that section and returns any missing or changed fact to this rule'
rs_guard "$FIT" "the fit check's ownership rule"

rs_reset
rs_rule "setup uses the fit check's ownership rule" 'record, following fit-check\.md.s ownership rule'
rs_rule "setup keeps the same owner for present facts" 'the fit check owns the present facts in "how it stays running"'
rs_rule "setup records only that the check ran and when" 'the changelog records only that this ownership check ran and when'
rs_rule "setup never copies answers into the history" 'do not copy the answers into the changelog'
rs_guard "$SETUP" "the founding ownership check"

rs_reset
rs_rule "planning gives the term a durable place on the piece" 'record the term in `## decided` and put the key-terms update in `## masterplan change`'
rs_rule "closing or reshaping keeps the term until it is used or changed" 'keep that settled term on the piece when it is reshaped or closed as not planned, until it reaches the masterplan or the person explicitly changes the decision'
rs_rule "the piece records why the term stays there" 'add this reason on the piece: "the term stays here while this is planned; the coverage read checks it even if this piece is closed as not planned\."'
rs_rule "planning still records and stops" 'planning records and stops; writing to the masterplan is a build'
rs_rule "clarify points to the coverage read that catches missed terms" 'setup-ai-build-kit/references/coverage-read\.md catches a settled term left behind on a piece'
rs_guard "$CLARIFY" "the settled-term rules"

rs_reset
rs_rule "length is measured on every path" 'on every build path, count the words in the masterplan.s core sections'
rs_rule "the measure excludes optional records and markup" 'leave out `build path`, the optional `key terms` and `how it stays running` sections, headings, comments and diagram source'
rs_rule "roughly two pages has a stated measure" 'more than 1,000 words is the working measure for roughly two pages'
rs_rule "an overlong page earns one line once" 'above that, give one line once in this run'
rs_rule "the line offers to move piece detail" 'the masterplan is longer than roughly two pages\. shall i move the detail about individual pieces onto those pieces\?'
rs_rule "moving detail needs agreement" 'move detail only with a yes'
rs_rule "the present plan keeps its promises and decisions" 'keeping every present promise and decision on the masterplan'
rs_rule "no agreement leaves the page intact and sync continues" 'otherwise, leave it intact and carry on'
rs_rule "a short page stays quiet" 'at or below the measure, say nothing'
rs_rule "shortening moves technical design to its concept file" 'lasting technical design goes to its `docs/<concept>\.md`'
rs_rule "shortening never creates a catch-all document" 'never into a new catch-all document'
rs_guard "$SYNC" "the masterplan length offer"

rs_require_load_bearing "WORKFLOW explains the length offer" "$WORKFLOW" 'when the core masterplan grows beyond roughly two pages, /sync says so once and offers to move detail'
rs_require_load_bearing "the closed-term rehearsal asks for the shaping decision" "$ROOT/.agents/tests/replay/cases/48.txt" 'a borrower is the person using an item'
rs_require_load_bearing "the rehearsal closes that piece as not planned before sync" "$ROOT/.agents/tests/replay/cases/48.txt" 'close the piece we just shaped as not planned'
rs_require_order "the rehearsal closes the term's piece before reconciliation" "$ROOT/.agents/tests/replay/cases/48.txt" 'Close the piece' '^/sync'
rs_require_load_bearing "the rehearsal judges the missing term rather than a new feature" "$ROOT/.agents/tests/scenarios.md" 'the coverage read names the missing borrower definition even though its piece was closed as not planned'
rs_require_absent "clarify no longer names parked" "$CLARIFY" 'parked'

rs_done
