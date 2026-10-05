#!/usr/bin/env sh
# loop-first-ground.sh: guard the ground the loop-first redesign stands on.
#
# A real project ran for six weeks with parallel worktrees, batch runs and
# records written for agents, while the philosophy still rejected worktrees,
# treated every record as written for a person, and presented every coding
# agent as equal. Every later change in the redesign points back at these
# documents, so a quiet edit that put the old ground back would leave those
# changes resting on nothing.
#
# It holds the principle the v1 design rests on: the work is shaping the
# work, and looping is the consequence. It holds the two zones, the guides and
# sensors that every gate is one of, and the list of what the loop kit leaves
# out. It holds the audience, the agent-first records, the worktree, loop,
# two-layer piece and loop module worked examples with all five answers, the
# narrower checks-first rule, the reason the kit is allowed to grow, and the
# Claude Code first line on the compatibility page. The README and WORKFLOW.md
# each state the principle in one sentence, SOURCES.md credits the loop words
# and the guide and sensor split without a link into the design notes, which
# do not ship, and the root AGENTS.md entry names all of it. Two old sentences
# must stay gone: the worktree rejection and the promise that the kit shrinks
# as often as it grows. Each is put back on a copy to prove the check notices.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PHILOSOPHY="$ROOT/docs/PHILOSOPHY.md"
README="$ROOT/README.md"
WORKFLOW="$ROOT/WORKFLOW.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"
SOURCES="$ROOT/docs/SOURCES.md"
AGENTS="$ROOT/AGENTS.md"

rs_init "Loop-first ground checks"
rs_exists "$PHILOSOPHY" "$README" "$WORKFLOW" "$COMPAT" "$SOURCES" "$AGENTS"

# --- the principle, the two zones, guides and sensors ---------------------

rs_rule "PHILOSOPHY.md has a section for the principle" \
  '## the principle'
rs_rule "the first sentence of the principle" \
  'the work is shaping the work\.'
rs_rule "the second sentence of the principle" \
  'looping is the consequence\.'
rs_rule "the kit is named a loop kit" \
  'the kit is a loop kit'
rs_rule "the four loop modules are named" \
  'fix, build, goal and gauntlet'
rs_rule "a loop that needs a person sends the piece back to shaping" \
  'goes back to be shaped again'
rs_rule "shaping is where the person and the system make every decision" \
  'every decision'
rs_rule "review never stops the loop" \
  'review never stops the loop'
rs_rule "a rule the agent would have to remember is held by a script" \
  'held by a script'
rs_rule "a guide makes up for what models cannot yet do" \
  'a guide, which makes up for something models cannot yet do'
rs_rule "a sensor guards against the builder's incentives" \
  'a sensor, which guards against the builder.s incentives'

# --- the loop module and exclusion worked examples ------------------------

rs_rule "the loop module example is added" \
  'loop modules, added\.'
rs_rule "the exclusion example is rejected" \
  'things the loop kit leaves out, rejected\.'
rs_rule "it leaves out a permanent model judge" \
  'a permanent model judge'
rs_rule "it leaves out agent hierarchies" \
  'agent hierarchies'
rs_rule "it leaves out specs that code is regenerated from" \
  'specs that code is regenerated from'
rs_rule "it leaves out the same ceremony for every piece" \
  'the same ceremony for every piece'
rs_rule "it leaves out a coverage or mutation score as a gate" \
  'a coverage or mutation score as a gate'
rs_rule "it leaves out debate between agents" \
  'debate between agents'
rs_rule "it leaves out a stored code graph or index until the pilot measures it" \
  'a stored code graph or index'
rs_rule "it leaves out prescribed test-first steps inside a loop" \
  'prescribed test-first steps inside a loop'

# --- the ground the earlier redesign laid ---------------------------------

rs_rule "the kit is for technical builders who direct agents" \
  'the kit is for technical builders who direct agents'
rs_rule "git, branches and pull requests are assumed familiar" \
  'assumes git, branches and pull requests are familiar'
rs_rule "the workflow still never requires reading code" \
  'the workflow never requires reading code'
rs_rule "records are written for agents first" \
  '## records are written for agents first'
rs_rule "a record carries a short human header" \
  'a short header at the top says in plain words'
rs_rule "public documents meant for people stay human-first" \
  'public documents meant for people, such as the readme, stay human-first'
rs_rule "the worktree example is added" \
  'separate worktrees for parallel pieces, added'
rs_rule "the kit owns each worktree's life" \
  'the kit owns each worktree from start to finish'
rs_rule "universal test-first is still rejected" \
  'universal test-first, rejected'
rs_rule "each machine check exists and fails before the code" \
  'each machine check exists and fails on today.s code before the code is written'
rs_rule "the loop example is added" \
  'the loop, added: ./queue. plans and ./implement. runs'
rs_rule "the new growth sentence" \
  'growth has to replace work that was already happening without the kit; anything else should make the kit smaller'
rs_rule "why this growth is accepted" \
  'replaces improvisation that already happened, with its safety built in'
# --- the count of commands ----------------------------------------------

# /fix was a shaping route plus a loop module: a bug is shaped like any other
# piece and built by the fix loop. The count paragraph says so, and the worked
# examples that answered "type /fix" answer /shape.
rs_rule "the vocabulary is eight commands" \
  'eight commands, each named after a moment a person actually reaches for'
rs_rule "the count paragraph says why nine became eight" \
  'nine became eight when `/fix` was found to be a shaping route plus a loop module'
rs_rule "the bug reproduction example fits under /shape and the fix loop" \
  'tight bug reproduction before a fix, added\. it fits under /shape and the fix loop'
rs_guard "$PHILOSOPHY" "PHILOSOPHY.md"
rs_require_absent "PHILOSOPHY.md no longer counts nine commands" "$PHILOSOPHY" 'nine commands'
rs_require_absent "PHILOSOPHY.md no longer says the count stays at nine" "$PHILOSOPHY" 'count stays at nine'
rs_require_absent "no worked example sends the person to /fix" "$PHILOSOPHY" '(type|under|to|tell) /fix'

# The principle comes first, before who the kit is for. Read on folded text,
# so rewrapping cannot break it.
if [ -z "${RS_LIST:-}" ]; then
  ph_order=$(rs_fold "$PHILOSOPHY" | awk '{
    a = index($0, "## the principle")
    b = index($0, "## who it is for")
    print (a > 0 && b > 0 && a < b) ? "yes" : "no"
  }')
  rs_report "the principle section sits before who the kit is for" "$ph_order"
fi

# --- the two sentences that must stay gone -------------------------------

OLD_REJECTION='parallel agents on separate worktrees, rejected'
OLD_GROWTH='the kit should get smaller as often as it gets bigger'

rs_require_absent "the worktree rejection is gone" "$PHILOSOPHY" "$OLD_REJECTION"
rs_require_absent "the old growth sentence is gone" "$PHILOSOPHY" "$OLD_GROWTH"

# Prove each absence rule can fail: put the old sentence back on a copy and run
# the same rs_require_absent against it, in a subshell so its failure exits the
# subshell only. It has to refuse the copy.
absence_catches() {
  # absence_catches <description> <restored-copy> <pattern>
  if ( rs_require_absent "$1" "$2" "$3" ) >/dev/null 2>&1; then
    rs_fail "restoring $1 was not caught"
  fi
  rs_ok "restoring $1 is caught"
}

if [ -z "${RS_LIST:-}" ]; then
  restored="$rs_dir/philosophy-restored.md"
  # Put each old sentence back where its replacement now stands.
  sed 's/^Separate worktrees for parallel pieces, added\./Parallel agents on separate worktrees, rejected./' \
    "$PHILOSOPHY" > "$restored"
  absence_catches "the worktree rejection" "$restored" "$OLD_REJECTION"
  sed 's/^Growth has to replace work that was already happening without the kit; anything$/The kit should get smaller as often as it gets bigger. Growth has to replace/' \
    "$PHILOSOPHY" > "$restored"
  absence_catches "the old growth sentence" "$restored" "$OLD_GROWTH"
fi

# --- each new worked example answers all five questions ------------------

# example_block <file> <opening-pattern>: the worked example that opens with
# the pattern, up to the next worked example or heading, folded and lowered.
example_block() {
  awk -v start="$2" '
    BEGIN { on = 0; prev = "" }
    {
      line = tolower($0)
      if (on && ($0 ~ /^#/ || (prev == "" && line ~ /, (added|rejected)[.:]/))) exit
      if (!on && prev == "" && index(line, start) == 1) on = 1
      if (on) print
      prev = $0
    }
  ' "$1" | tr '\n' ' ' | tr -s ' ' | tr '[:upper:]' '[:lower:]'
}

# The five answers, one marker each: the command it fits under, what the
# person sees, the one sentence, what they do when it goes wrong, and what they
# never need to learn. The fourth has to name a command the person types before
# the sentence ends, because "check the logs" is not an answer and neither is
# the kit acting with nobody told.
FIVE='fits under
sees
the sentence is
when [a-z ]{0,30}goes wrong
never need to'

five_missing() {
  # five_missing <folded-text>: prints each marker the text lacks.
  printf '%s\n' "$FIVE" | while IFS= read -r marker; do
    printf '%s' "$1" | grep -qE "$marker" || echo "$marker"
  done
}

check_five() {
  # check_five <label> <opening-pattern>
  [ -z "${RS_LIST:-}" ] || return 0
  block=$(example_block "$PHILOSOPHY" "$2")
  [ -n "$block" ] || rs_fail "$1: the worked example was not found"
  missing=$(five_missing "$block")
  if [ -n "$missing" ]; then
    printf '%s\n' "$missing" | sed 's/^/  missing answer: /'
    rs_fail "$1 does not answer all five questions"
  fi
  rs_ok "$1 answers all five questions"
  # Prove each answer is load-bearing: remove it and require a miss. The loop
  # reads a here-document rather than a pipe, because a pipeline runs its body
  # in a subshell where rs_fail would exit the subshell and nothing else.
  while IFS= read -r marker; do
    [ -n "$marker" ] || continue
    mutant=$(printf '%s' "$block" | sed -E "s@$marker@@g")
    if [ -z "$(five_missing "$mutant")" ]; then
      rs_fail "$1: removing the answer marked '$marker' was not caught"
    fi
  done <<FIVEMARKERS
$FIVE
FIVEMARKERS
  rs_ok "$1: removing any one answer is caught"
}

check_five "the worktree example" 'separate worktrees for parallel pieces, added'
check_five "the loop example" 'the loop, added'
check_five "the two-layer piece example" 'a piece written in two layers, added'
check_five "the loop module example" 'loop modules, added'

# Contract v2 puts the loop module and the reach on every piece, so the
# two-layer example names both among what the agent layer carries. Read inside
# the example's own block, so a mention elsewhere in the file cannot stand in.
if [ -z "${RS_LIST:-}" ]; then
  block=$(example_block "$PHILOSOPHY" 'a piece written in two layers, added')
  for marker in 'the loop module' 'the reach line'; do
    printf '%s' "$block" | grep -qF "$marker" \
      || rs_fail "the two-layer example does not name $marker"
    rs_ok "the two-layer example names $marker"
    if printf '%s' "$block" | sed "s@$marker@@g" | grep -qF "$marker"; then
      rs_fail "removing $marker from the two-layer example was not caught"
    fi
    rs_ok "removing $marker from the two-layer example is caught"
  done
fi

# --- the other documents say the same ------------------------------------

rs_require_load_bearing "the README's audience line names technical builders who direct agents" \
  "$README" '\| who it is for \| technical builders who direct agents'
PRINCIPLE='you shape the work; the kit builds it in loops and checks it against a bar fixed before the build\.'
rs_require_load_bearing "the README's opening states the principle in one sentence" \
  "$README" "$PRINCIPLE"
rs_require_load_bearing "WORKFLOW.md's opening names technical builders who direct agents" \
  "$WORKFLOW" 'technical builders who direct agents'
rs_require_load_bearing "WORKFLOW.md's opening states the principle in one sentence" \
  "$WORKFLOW" "$PRINCIPLE"
# The order is read on folded text, so rewrapping the opening cannot break it.
# The audience comes first, then the principle, then the command table.
if [ -z "${RS_LIST:-}" ]; then
  wf_order=$(rs_fold "$WORKFLOW" | awk '{
    a = index($0, "technical builders who direct agents")
    p = index($0, "you shape the work; the kit builds it in loops")
    b = index($0, "## 1. commands")
    print (a > 0 && p > 0 && b > 0 && a < p && p < b) ? "yes" : "no"
  }')
  rs_report "and says both in its opening, audience then principle, before the command table" "$wf_order"
fi
rs_require_load_bearing "COMPATIBILITY says Claude Code comes first" \
  "$COMPAT" 'claude code comes first'
rs_require_load_bearing "COMPATIBILITY names what other coding agents get" \
  "$COMPAT" 'other coding agents get the one-at-a-time core'

# --- the credits ----------------------------------------------------------

rs_require "SOURCES.md credits the words loop engineering" \
  "$SOURCES" 'loop engineering'
rs_require "SOURCES.md credits the inner loop and the outer loop" \
  "$SOURCES" 'inner loop'
rs_require "SOURCES.md credits Birgitta Böckeler" \
  "$SOURCES" 'birgitta böckeler'
rs_require "SOURCES.md credits the split into guides and sensors" \
  "$SOURCES" 'guides and sensors'
# The design notes do not ship, so a link into them would be dead in every
# installed copy.
DESIGN_LINK='design/agentic-loop'
rs_require_absent "SOURCES.md links to no design note" "$SOURCES" "$DESIGN_LINK"
if [ -z "${RS_LIST:-}" ]; then
  linked="$rs_dir/sources-linked.md"
  { cat "$SOURCES"; echo '| [The design note](design/agentic-loop-research.md) | A borrowed idea |'; } > "$linked"
  absence_catches "a link to a design note in SOURCES.md" "$linked" "$DESIGN_LINK"
fi

# --- the maintainer's entry for this check --------------------------------

rs_require "AGENTS.md names the principle" \
  "$AGENTS" 'the work is shaping the work'
rs_require "AGENTS.md names the two zones" \
  "$AGENTS" 'two zones'
rs_require "AGENTS.md names guides and sensors" \
  "$AGENTS" 'guides and sensors'
rs_require "AGENTS.md names the loop module example" \
  "$AGENTS" 'loop modules, added'
rs_require "AGENTS.md names the exclusion example" \
  "$AGENTS" 'leaves out, rejected'

rs_done
