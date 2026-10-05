#!/usr/bin/env sh
# frozen-bar.sh: guard the words that tell the frozen bar and the gate's own
# run of the checks.
#
# frozen-bar-rehearsal.sh shows the gate holding the bar. A person learns what
# it holds from WORKFLOW.md's section 6, "Evidence", and a maintainer from the
# design note. Neither is read by a machine, so a sentence could drift or go
# without any run noticing. Each is read back here and proved load-bearing:
# that the bar is fixed at ready, what the gate refuses, what sends a piece to
# the person, and that "done" is the gate running the checks rather than the
# agent saying so.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

WORKFLOW="$ROOT/WORKFLOW.md"
NOTE="$ROOT/docs/design/agentic-loop.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"

rs_init "Frozen bar words"
rs_exists "$WORKFLOW" "$NOTE" "$BUILDER"

# --- WORKFLOW.md, section 6 --------------------------------------------------

rs_rule "the bar is fixed at ready" \
  'the bar a piece is built against is fixed when it is made ready'
rs_rule "the fingerprint leaves out what the kit writes during a build" \
  'leaving out the sections the kit writes during a build'
rs_rule "a contract changed mid-build goes back to shaping with its branch kept" \
  'a contract that changed while the piece was being built sends it back to shaping, and its branch stays'
rs_rule "what the gate refuses" \
  'a change the piece did not name on a `changes the bar:` line is refused, and the refusal names each file and says to put it back'
rs_rule "an acceptance check is never named" 'an acceptance check can never be named'
rs_rule "what forces the person's review" \
  'what forces your review: a change the piece did name, a changed file outside the piece.s boundary in the area map, and an acceptance check that noticed none of the deliberate breakages'
rs_rule "done is the gate running the checks" 'done is the gate running the checks'
rs_rule "the gate runs them itself on the saved commit" \
  'the gate itself runs every acceptance check, every guard check and the project.s test command on the saved commit'
rs_rule "the agent's word counts for nothing" \
  'what the agent says about its checks counts for nothing'
rs_rule "the record is one only the gate writes" \
  '`\.agents/pieces/<number>/evidence\.jsonl` on your computer, which only the gate writes'
rs_guard "$WORKFLOW" "WORKFLOW.md's Evidence section"

# Each of those sits in section 6 itself, so a sentence moved to another
# section, where a reader looking for evidence would not find it, is caught.
section="$rs_dir/evidence-section"
awk '/^## 6\. Evidence$/ { inside = 1; next } /^## / { inside = 0 } inside' "$WORKFLOW" \
  | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | sed -E 's/[[:space:]]+/ /g' > "$section"
[ -s "$section" ] || rs_fail "WORKFLOW.md has no '## 6. Evidence' section"
while IFS="$(printf '\t')" read -r desc pattern; do
  [ -n "$pattern" ] || continue
  rs_report "section 6 itself says: $desc" \
    "$(grep -qE "$pattern" "$section" && echo yes || echo no)"
done < "$rs_dir/rules"

# --- the design note -------------------------------------------------------------

rs_reset
rs_rule "the hash leaves out what the system writes during a build" \
  'the hash leaves out the sections the system writes during a build'
rs_rule "test-strength runs without an offer once green" \
  'test-strength runs without an offer once the build is green'
rs_rule "the frozen bar row names the bar guard and the hash" \
  '[|] the frozen bar [|] the gate script.s bar guard and the contract hash [|]'
rs_rule "the Fresh evidence row says the gate alone holds it until the Stop hook" \
  '[|] fresh evidence [|][^|]*until slice 7: build and fix loop modules adds the stop hook, the gate alone holds fresh evidence [|]'
rs_guard "$NOTE" "the design note's frozen bar"

# --- section-builder -------------------------------------------------------------

# Every attempt asks the gate whether the contract changed before it builds;
# checks-first.sh holds the sentence, and this holds that the gate's own run
# before review is told where the builder reads it.
rs_require_load_bearing "section-builder says the gate runs the checks itself before review" \
  "$BUILDER" 'runs every acceptance check, every guard check and the test command itself on the saved commit'
rs_require_load_bearing "section-builder runs check-contract at the start of every attempt" \
  "$BUILDER" 'at the start of every attempt, run `python3 \.agents/tools/gate\.py check-contract <number>`'

rs_done
