#!/usr/bin/env sh
# speaks-for-the-person.sh: guard the yes the kit waits for before it speaks
# for the person to anyone else.
#
# In a project where colleagues file issues, the person asked the agent what it
# would recommend about a colleague's proposal. The agent then posted a comment
# under the person's GitHub account, addressed to that colleague, and changed
# the title and scope of the colleague's issue, all before the person had said
# to go ahead. The colleague read it as the person speaking. The kit already
# asked before anything that changes a live service, but a comment or an edit
# on GitHub was not named, so nothing stopped it.
#
# The rule lives in pieces.md, with what counts, what is bookkeeping and how the
# author is read. /shape carries the part it meets while reshaping somebody
# else's issue, the founded blocked-commands.md carries the restriction every
# session reads, and WORKFLOW.md tells it for a team. The exemptions matter as
# much as the rule: without them a run with nobody watching could not write its
# claim comment or move a label on a colleague's piece, and the runner would
# stop on every team project.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PIECES="$ROOT/.agents/skills/setup-ai-build-kit/references/pieces.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
BLOCKED="$ROOT/.agents/skills/setup-ai-build-kit/references/blocked-commands.md"
WORKFLOW="$ROOT/WORKFLOW.md"
FOUNDED="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md"

rs_init "Speaks-for-the-person checks"
rs_exists "$PIECES" "$SHAPE" "$BLOCKED" "$WORKFLOW" "$FOUNDED"

# pieces.md: the rule, what counts, the exemptions and how the author is read.
rs_rule "the section exists" '## speaking for the person'
rs_rule "posting under the person's account waits for a yes on the words" \
  'waits for a yes that covers those exact words'
rs_rule "the words are shown before the question" 'show the words first, then ask'
rs_rule "a comment or a reply counts" 'a comment or a reply on an issue or a pull request'
rs_rule "a review counts" 'a review of a pull request'
rs_rule "a mention counts, because GitHub tells them" \
  'a mention of someone by their github name'
rs_rule "a message in another channel counts" \
  'a message in any other channel the agent can reach'
rs_rule "changing another account's title, So that, Done when or scope needs the same yes" \
  'the same yes is needed before changing the title, the `## so that`, the `## done when` or the scope'
rs_rule "of an issue or pull request another account opened" \
  'of an issue or a pull request that another account opened'
rs_rule "the author is read from the issue" 'gh issue view <number> --json author'
rs_rule "and compared with the signed-in account" 'gh api user --jq \.login'
rs_rule "an author that cannot be read counts as another person's" \
  'treat it as another person.s and ask'
rs_rule "bookkeeping says nothing in the person's voice" \
  'say nothing in the person.s voice, so they need no yes'
rs_rule "exempt: state and needs- labels" 'state labels and `needs-` labels'
rs_rule "exempt: the claim comment" 'the claim comment a run writes'
rs_rule "exempt: the one conflict comment a merge leaves" \
  'the one comment naming the conflicting files when a merge from `main`'
rs_rule "exempt: the kit's own pull request text" \
  'the title and body of a pull request the kit opens for a piece'
rs_rule "adding shaped sections over the kept original is not a change" \
  'adding the shaped sections above the original, kept whole, is not such'
rs_rule "capture on a colleague's matching issue stays exempt" \
  'such as capture adding them to a matching issue, whoever opened it'
rs_rule "the kept original has a name /shape can point to" \
  'underneath, under "original report"'
rs_rule "exempt: a Closes line" 'a `closes #<number>` line'
rs_rule "exempt: the send-back question" \
  'the question a run or `/shape` writes on a piece it sends back to shaping'
rs_rule "exempt: the readiness gaps and section" \
  'the readiness check.s gaps and its `## readiness` section'
rs_rule "exempt: shaped sections above a kept original" \
  'the shaped sections added above a kept original'
rs_rule "exempt: the person's own words when they asked for exactly that" \
  'the person.s own words added as a comment when they asked for exactly that'
rs_rule "'tell them X' is the yes for those words" 'that is the yes for those words'
rs_rule "their own words are posted without a second question" \
  'post them with no second question'
rs_rule "words the agent added or changed are asked about" \
  'where you add or change words, ask about the new version'
rs_rule "a no posts nothing" 'when the person says no, post nothing'
rs_rule "and the person is given the words to post themselves" \
  'give them the words, so they can post them themselves'
rs_rule "a run with nobody watching posts nothing in the person's voice" \
  'a run with nobody watching posts nothing in the person.s voice'
rs_rule "and changes no title or scope on another account's issue" \
  'changes no title or scope on an issue or a pull request another account opened'
rs_rule "while its bookkeeping still goes on" 'its bookkeeping still goes on'
rs_guard "$PIECES" "the shipped pieces.md"

rs_require_order "the section follows 'When somebody acts on GitHub'" "$PIECES" \
  '^## When somebody acts on GitHub' '^## Speaking for the person'

# /shape: the part it meets while reshaping somebody else's issue.
rs_reset
rs_rule "it reads the author before it shapes" 'read its author first'
rs_rule "and points to the rule" 'under "speaking for the person"'
rs_rule "keeps that person's words whole under Original report" \
  'keep their words whole under "original report"'
rs_rule "names the author in its reply" 'name the author in your reply'
rs_rule "asks before saving a changed title or scope" \
  'ask before saving a changed title or scope'
rs_rule "adding shaped sections over the kept original is not a change of scope" \
  'with the original kept whole, is not a change of scope'
rs_guard "$SHAPE" "the /shape skill"

# The founded blocked-commands.md, which the founded AGENTS.md says always applies.
rs_reset
rs_rule "never post in the person's name to anyone else" \
  'never post in the person.s name to anyone else'
rs_rule "or change another account's title or scope" \
  'or change the title or scope of an issue or a pull request another account opened'
rs_rule "without a yes covering the words" 'without a yes that covers the words'
rs_rule "and pieces.md says what counts" \
  '`references/pieces.md` says what counts, under "speaking for the person"'
rs_guard "$BLOCKED" "the shipped blocked-commands.md"

# WORKFLOW.md tells it to a team.
rs_reset
rs_rule "nothing goes to a colleague in your name until you have seen the words" \
  'nothing goes to a colleague in your name until you have seen the words and said yes'
rs_rule "and a colleague's issue keeps its title and scope" \
  'keeps its title and scope unless you agree to the change'
rs_guard "$WORKFLOW" "WORKFLOW.md"

rs_require_order "WORKFLOW.md says it in Team use" "$WORKFLOW" \
  '^## 11\. Team use' 'in your name until you have seen'
rs_require_order "and before the section after it" "$WORKFLOW" \
  'in your name until you have seen' '^## 12\. '

# The founded AGENTS.md sits at its line budget and is not changed for this;
# the restriction reaches every session through blocked-commands.md, which it
# already says always applies. standing-instructions.sh holds the budget.

rs_done
