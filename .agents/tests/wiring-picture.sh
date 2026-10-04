#!/usr/bin/env sh
# wiring-picture.sh: guard the picture of what the tool reaches outside itself.
#
# A person who has not read the code cannot tell what their tool talks to. The
# masterplan now carries a simple picture of it, confirmed at founding and
# redrawn when a piece changes a connection. Two failures matter:
# the picture disappearing, and the picture going stale, which is worse than no
# picture because the team believes it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Wiring-picture checks"
rs_exists "$TEMPLATE" "$SETUP" "$BUILDER" "$WORKFLOW"

rs_rule "the section exists" '## what it connects to'
rs_rule "it covers where the data lives and each outside service" \
  'each outside service'
rs_rule "it leaves the inside of the tool out" 'nothing internal'
rs_rule "it is drawn as a picture, not a list" 'draw it as a mermaid flowchart'
rs_rule "every line says what flows and which way" 'what flows and which way'
rs_rule "it is read back at founding" 'read it back at founding'
rs_rule "it is kept true when a connection changes" 'update it whenever a piece adds'
rs_guard "$TEMPLATE" "the masterplan template"

# A template's example is copied more often than its prose is read, so an
# example showing screens or code would teach the opposite of the rule.
example=$(sed -n '/```mermaid/,/```/p' "$TEMPLATE")
[ -n "$example" ] && r=yes || r=no
rs_report "the template shows an example picture" "$r"

printf '%s' "$example" | grep -qiE 'screen|button|page|component|api route' && \
  r=no || r=yes
rs_report "the example draws nothing from inside the tool" "$r"

rs_require "founding reads the picture back and waits for confirmation" \
  "$SETUP" 'confirm each outside connection'
# Without the redraw the picture goes stale in silence, which is worse than
# having none, because the team believes it.
rs_require_load_bearing "a piece that changes a connection redraws the picture" \
  "$BUILDER" "update the masterplan's connections picture"
rs_require "and says what the tool now reaches, so the person can object" \
  "$BUILDER" 'say whether it should'
rs_require "WORKFLOW.md explains it in plain words" \
  "$WORKFLOW" 'picture of everything outside the tool'

rs_done
