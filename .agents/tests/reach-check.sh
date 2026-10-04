#!/usr/bin/env sh
# reach-check.sh: guard the live reach check and its engine fallback.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

REACH="$ROOT/.agents/skills/section-builder/references/reach-check.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
FIX="$ROOT/.agents/skills/fix/SKILL.md"
CAPABILITY="$ROOT/.agents/skills/setup-ai-build-kit/references/capability-check.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Reach-check rules"
rs_exists "$REACH" "$BUILDER" "$SHAPE" "$FIX" "$CAPABILITY" "$SETUP" "$MAINTAIN" "$WORKFLOW"

rs_rule "asks what else the change reaches" 'what else does the change reach'
rs_rule "asks which existing tests cover it" 'which existing tests cover it'
rs_rule "runs the covered tests first" 'run those tests first'
rs_rule "keeps the full project check" 'full project check still runs'
rs_rule "prefers a live language server" "harness's language server, or serena"
rs_rule "uses project related-test commands next" "project's related-test or affected-code command"
rs_rule "uses an installed graph only after live routes" 'graph tool the person already installed'
rs_rule "falls back to reading imports and callers" 'read the changed files.*imports and callers directly'
rs_rule "treats an index as a lead rather than a record" 'a written index is a lead to verify'
rs_rule "derives the result each time" 'derive it again for each change'
rs_rule "uses the fixed visible line" 'this change also reaches <part>, and the <count> tests that cover it passed'
rs_rule "stays silent when nothing else is reached" 'say nothing when nothing else is reached'
rs_guard "$REACH" "the shared reach-check reference"

rs_require "section-builder runs it before save" "$BUILDER" 'references/reach-check\.md'
rs_require "section-builder runs covered tests first" "$BUILDER" 'run those tests first'
rs_require "shape uses it for under-the-hood notes" "$SHAPE" 'references/reach-check\.md'
rs_require_order "fix uses it before ranking causes" "$FIX" \
  'references/reach-check\.md' '^## 4\. Rank causes$'
rs_require "the capability check records the engine" "$CAPABILITY" 'a reach-check engine is recorded'
rs_require "setup writes the engine to the profile" "$SETUP" 'the reach-check engine'
rs_require "maintain re-reads the engine monthly" "$MAINTAIN" "re-read the capability profile's reach-check engine"
rs_require "WORKFLOW explains the visible behaviour" "$WORKFLOW" 'checks what else the change touches'

rs_done
