#!/usr/bin/env sh
# queue-groups.sh: guard what /queue is allowed to call safe to build together.
#
# The command exists to stop somebody making a mess by taking on several pieces
# at once, so the one thing it must never do is put two pieces in the same group
# when one is waiting on the other. That safety does not come from /queue
# working anything out. It comes from the printout: a piece with an open blocker
# is never under To build, so everything in that group is free of the others.
# The rule is therefore "read the group", and a version that re-derived safety
# for itself would be the defect this guards against.
#
# The other rules here are the ones a person would notice going: a blocker named
# by number instead of by name, a group printed empty, a command that reports and
# then builds something anyway, and a plan whose last line is not the command
# that runs it.
#
# The groups of pieces that can be built together follow the same rule. The
# printout compares each ready piece's Touches line and prints the groups, and
# /queue reads them. plan-printout.sh proves two pieces naming the same area
# never share a group.
#
# plan-printout.sh proves the printout really behaves that way. This proves the
# skill still says to rely on it.

. "$(dirname -- "$0")/lib/rule-shape.sh"

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SKILL="$ROOT/.agents/skills/queue/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"
PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
IMPLEMENT="$ROOT/.agents/skills/implement/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"

rs_init "Queue grouping checks"

rs_rule "the printout is the only source" 'the only source'
rs_rule "safety is read from the group, not re-derived" \
  'a piece with an open blocker is never under `to build`'
rs_rule "the ready group is what can be built together" \
  'they have no dependency between them'
rs_rule "the waiting group names the piece that releases each one" \
  'saying which piece releases it'
rs_rule "blockers are named, never numbered" 'piece names, never issue numbers'
rs_rule "a stale list still gets shown, with its age" \
  'say when it was written'
rs_rule "a piece waiting on a question is left out of the plan" \
  'leave it out of the plan'
rs_rule "an empty group is not printed" 'rather than printing an empty group'
# Found by reading a real printout rather than by reasoning about one: a piece
# that is shaped but never marked ready is taken by neither /queue nor
# /implement. It used to sit in the buildable group with no marker; since the
# states it sits under Idea. Silence about it is worst when that piece is the
# one holding another up, so its blocker is named wherever it sits.
rs_rule "a sized but unmarked piece is named, not silently dropped" \
  'sized but never marked ready sits under `idea`'
rs_rule "a held-up piece's blocker is named under idea or shaping" \
  'blocker may sit under `idea` or `shaping`, so name it there'
rs_rule "it never asks for a secret in a message" \
  'never ask for a key, a password, or a token in a message'
rs_rule "it reports and does not build" 'this command only ever reports'
rs_rule "it changes nothing on any piece" 'never labels, claims or starts a piece'

# The plan a run would follow. Five parts, in a fixed order, because the person
# reads down to the command and each part is what the next one relies on: the
# order says what comes first, the groups what can go together, the verdicts
# what a run will actually take, the stack what builds on what, and the command
# runs exactly that.
rs_rule "the plan has five parts in a fixed order" 'five parts, in this order'
rs_rule "the order part" '\*\*the order\.\*\*'
rs_rule "the groups part" '\*\*the groups\.\*\*'
rs_rule "the verdict part" '\*\*what a run can do with each\.\*\*'
rs_rule "the stack part" '\*\*the stack\.\*\*'
rs_rule "the command part" '\*\*the command\.\*\*'
rs_rule "the plan takes what /implement queue would take, in blocked-by order" \
  'whose open blockers are all in the plan, all the way down its chain'
# The groups come from the printout, which compares the Touches lines. A /queue
# that grouped the pieces itself would be a second answer to the same question,
# and the two would drift.
rs_rule "the groups are read as printed" 'as the printout wrote them'
rs_rule "the groups are never worked out again" 'never group the pieces yourself'
rs_rule "a piece with no Touches line goes alone, and says why" \
  'its touches line is missing, so it goes alone'
rs_rule "verdict: a run can take it" \
  "a run can take it: none of the above holds, so the readiness section's first line says ready"
rs_rule "on explore privately, only disposable work a machine can check" \
  'on explore privately, say the run.s own condition'
rs_rule "verdict: a piece stacked on one a run cannot take waits for it, with the reason" \
  'waits for the piece it stacks on: the printout marks it'
rs_rule "the verdicts come from the printout's marks" \
  "the printout's marks settle all but the first"
rs_rule "verdict: a sensitive area without acceptance needs the person" \
  'needs you: it lies in a sensitive area'
rs_rule "verdict: an opted-in piece is still taken and stops at to check" \
  'still taken by a run and stops at `to check`'
rs_rule "verdict: not ready, read from its readiness section" \
  'not ready: its `## readiness` section says not ready'
rs_rule "verdict: not yet checked, when it has no readiness section" \
  'not yet checked: it has no `## readiness` section'
rs_rule "a piece that depends on another in the plan stacks on it" \
  'depends on another piece in the plan stacks on it'
rs_rule "the last line is the exact command" 'the last line is the exact command'
rs_rule "the command is /implement queue when a run can take everything" \
  '`/implement queue` when a run can take every piece'
rs_rule "otherwise the command names the pieces by number" \
  '`/implement` followed by the numbers'
rs_rule "with nothing ready, it says what would make something ready and prints no command" \
  'usually `/shape`, and print no command'
rs_rule "with nothing a run can take, the command is left off" \
  'where a run can take none of the pieces in the plan, leave the command off'
rs_rule "the numbers include a not-yet-checked piece and an opted-in piece" \
  'the numbers include a piece not yet checked and a piece that waits for the person.s try'
rs_rule "a piece a run cannot take is never in the numbered command" \
  'or waits for the piece it stacks on is never among them'
# The printout is the only source for the pieces. A /queue that opened each
# piece itself would be a second reading that could disagree with the first.
rs_rule "it never opens the pieces themselves" 'never open the pieces themselves'
rs_rule "an older helper with no groups is named, and /maintain refreshes it" \
  'the next `/maintain` refreshes it, and print no groups and no command'
# A group once promised its pull requests could merge in any order. Two pieces
# that each pass alone can still fail together, so a group says what can be
# built in any order, and each piece still merges one at a time after the
# re-check the merge step makes. A run builds one piece at a time unless the
# person chooses more on Claude Code, which parallel-run.sh guards in the run's
# own rules.
rs_rule "the groups say what can be built in any order" \
  'the pieces of one group can be built at the same time in any order'
rs_rule "each piece in a group still merges one at a time" \
  'so each still merges one at a time'
rs_rule "a run builds one piece at a time unless the person chooses more" \
  '`/implement queue` builds one piece at a time by default, whatever the groups say'

rs_guard "$SKILL" "the /queue skill"

# The parts print in the order the person reads down to the command.
rs_require_order "the order comes before the groups" "$SKILL" \
  '^\*\*The order\.\*\*' '^\*\*The groups\.\*\*'
rs_require_order "the groups come before the verdicts" "$SKILL" \
  '^\*\*The groups\.\*\*' '^\*\*What a run can do with each\.\*\*'
rs_require_order "the verdicts come before the stack" "$SKILL" \
  '^\*\*What a run can do with each\.\*\*' '^\*\*The stack\.\*\*'
rs_require_order "the stack comes before the command" "$SKILL" \
  '^\*\*The stack\.\*\*' '^\*\*The command\.\*\*'

# The house rule is that a behaviour is told in three places or it is not
# finished. The skill above is one. WORKFLOW.md carries the plain explanation
# and the row in the command table, which is the other two.
rs_require_twice "WORKFLOW.md explains /queue and lists it in the table" \
  "$WORKFLOW" "/queue"

rs_require "WORKFLOW.md says what makes the first list safe to take on together" \
  "$WORKFLOW" 'a piece waiting on another piece is never in it'
rs_require "WORKFLOW.md says how to deal with a stale list" \
  "$WORKFLOW" 'type /queue again'
rs_require_load_bearing "WORKFLOW.md says what goes together and why" \
  "$WORKFLOW" 'no two pieces in a group change the same area'
rs_require_load_bearing "WORKFLOW.md says the last line is the command that runs the plan" \
  "$WORKFLOW" 'last line is the command that runs'

# Where the label is defined, the record has to say that ready alone does not
# mean startable. Getting this wrong is the easy mistake: a piece can be fully
# shaped and still be held up by another.
rs_require "pieces.md says ready alone does not mean startable" \
  "$PIECES" 'ready` alone does not mean startable'
rs_require "pieces.md says what /queue actually offers" \
  "$PIECES" 'the printout has already put under `to build`'
rs_require_load_bearing "pieces.md says the groups come from the Touches lines" \
  "$PIECES" 'compares their `touches:` lines'

# /what-now keeps its own job. If it ever grew the whole list, the split that
# justified a ninth command would have been undone and both commands would be
# doing the same thing.
rs_require "what-now still caps itself at three things" \
  "$WHATNOW" 'name at most three things'
# In the real project the person asked "what else can we work on" rather than
# typing /queue, and got an answer that led to no run. The question is the cue.
rs_require_load_bearing "what-now offers /queue when asked what else can be worked on" \
  "$WHATNOW" 'asks what else can be worked on, [^.]*offer /queue'

# The same safety reaches the end of a build. The report there names what can
# be built next, and it once named a piece that was waiting on another, because
# the list had been read by hand. So the next piece comes from the printout's
# To build group, and from nothing else.
rs_reset
rs_rule "the next piece comes from the refreshed printout's ready group" \
  'name only a piece under `to build` marked `\(ready\)`'
rs_rule "the piece just built is never named as next" 'never the piece just built'
rs_rule "with nothing ready, no piece is named as next" 'name no piece as next'
rs_rule "the next piece is never worked out by hand" \
  'never work the next piece out from the issue list'
rs_guard "$IMPLEMENT" "the /implement skill's next-piece rule"

rs_require_load_bearing "section-builder names a next piece only from To build" \
  "$BUILDER" 'name only a piece under its `to build` group'
rs_require_load_bearing "section-builder never works the next piece out by hand" \
  "$BUILDER" 'never work the next piece out from the issue list by hand'
rs_require_load_bearing "pieces.md forbids sorting the pieces by hand" \
  "$PIECES" 'never sort the pieces by reading the issues by hand'

rs_done
