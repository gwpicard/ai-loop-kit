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
# It holds the audience, the agent-first records, the worktree, loop and
# two-layer piece worked examples with all five answers, the narrower checks-first rule, the reason
# the kit is allowed to grow, and the Claude Code first line on the
# compatibility page. Two old sentences must stay gone: the worktree rejection
# and the promise that the kit shrinks as often as it grows. Each is put back
# on a copy to prove the check notices.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PHILOSOPHY="$ROOT/docs/PHILOSOPHY.md"
README="$ROOT/README.md"
WORKFLOW="$ROOT/WORKFLOW.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"

rs_init "Loop-first ground checks"
rs_exists "$PHILOSOPHY" "$README" "$WORKFLOW" "$COMPAT"

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
rs_guard "$PHILOSOPHY" "PHILOSOPHY.md"

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

# --- the other documents say the same ------------------------------------

rs_require_load_bearing "the README's audience line names technical builders who direct agents" \
  "$README" '\| who it is for \| technical builders who direct agents'
rs_require_load_bearing "WORKFLOW.md's opening names technical builders who direct agents" \
  "$WORKFLOW" 'technical builders who direct agents'
# The order is read on folded text, so rewrapping the opening cannot break it.
if [ -z "${RS_LIST:-}" ]; then
  wf_order=$(rs_fold "$WORKFLOW" | awk '{
    a = index($0, "technical builders who direct agents")
    b = index($0, "## 1. commands")
    print (a > 0 && b > 0 && a < b) ? "yes" : "no"
  }')
  rs_report "and says it in its opening, before the command table" "$wf_order"
fi
rs_require_load_bearing "COMPATIBILITY says Claude Code comes first" \
  "$COMPAT" 'claude code comes first'
rs_require_load_bearing "COMPATIBILITY names what other coding agents get" \
  "$COMPAT" 'other coding agents get the one-at-a-time core'

rs_done
