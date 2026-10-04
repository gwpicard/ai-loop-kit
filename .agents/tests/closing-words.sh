#!/usr/bin/env sh
# closing-words.sh: guard the rule that only a pull request's Closes line
# closes a piece.
#
# GitHub closes an issue when a merged pull request or commit puts a closing
# word straight before its number. It reads the word and the number and
# nothing else, so a sentence saying a pull request does not close a piece
# closes it all the same when the word sits next to the number. In one outside
# project a piece was closed twice that way, the second time by the sentence
# written to warn about the first. The kit writes its Closes line on purpose,
# and it also writes prose naming other pieces: the merge order of a stack,
# what a piece builds on. So section-builder carries the rule, and this check
# holds each part of it.
#
# The second half reads the kit's own examples. An example that broke the rule
# would teach it, so every number written in section-builder, the merge step,
# the run's reference and WORKFLOW.md is read, and a closing word straight
# before one fails the check unless it is the `Closes #<number>` line itself.
# The reader is then run on copies carrying a bad sentence, to prove it can
# fail.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
SB="$SKILLS/section-builder/SKILL.md"
MERGE="$SKILLS/section-builder/references/merge.md"
LONGER="$SKILLS/implement/references/running-longer.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Closing word checks"
rs_exists "$SB" "$MERGE" "$LONGER" "$WORKFLOW"

# The rule, in section-builder's save step.
rs_rule "a closing word only on a Closes line, one for each piece finished" 'a closing word appears only on a `closes #<number>` line, one line for each piece the pull request finishes'
rs_rule "the nine closing words" 'close, closes, closed, fix, fixes, fixed, resolve, resolves or resolved'
rs_rule "a negated sentence still closes the piece" 'a sentence saying the pull request does not close a piece still closes it'
rs_rule "the rule covers title, body, commits and changelog files" 'in the pull request.s title and body, in commit messages and in changelog files, no number that names another piece has a closing word before it'
rs_rule "another piece is named by number and title" 'name another piece by its number and its title, with no closing word before the number'
rs_rule "the words to use instead" 'say "after", "builds on" or "merge first"'
rs_rule "a pull request finishing one piece and naming another" 'a pull request that finishes one piece and mentions another carries one `closes` line, for the piece it finishes'
rs_guard "$SB" "section-builder's save step"

# The stack example names its base the safe way.
rs_require_load_bearing "the run's stack example names the base without a closing word" "$LONGER" 'merge #<number>, the date filter, first; this builds on it'

# WORKFLOW.md tells it.
rs_require_load_bearing "WORKFLOW says only the Closes line closes a piece" "$WORKFLOW" 'only the `closes` line closes a piece'

# The examples. A closing word, with an optional colon, straight before a
# number or the `#<number>` placeholder, read on the folded file so a sentence
# wrapped between the word and the number is still seen. The one allowed form
# is the line itself, written as the code span `Closes #<number>`.
WORDS='close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved'
offending() {
  rs_fold "$1" \
    | grep -oE "(^|[^a-z])($WORDS):?[[:space:]]+[\`\"']?#(<number>|[0-9]+)" \
    | grep -vE '^`closes #<number>$' || true
}

for file in "$SB" "$MERGE" "$LONGER" "$WORKFLOW"; do
  found=$(offending "$file")
  name=${file#"$ROOT/"}
  if [ -n "$found" ]; then
    echo "$found" | sed 's/^/    /'
    rs_fail "$name puts a closing word straight before a number"
  fi
  rs_ok "$name names no piece after a closing word, outside the Closes line"
done

# The reader can fail. Each bad sentence is added to a copy of the run's
# reference, and the reader must find it there.
for bad in \
  'This does not close #<number>, the date filter.' \
  'Merge it after the base, which fixes #7.' \
  'It resolves:
#<number> once merged.' \
  'Say merge first; this builds on `Fixes #<number>`.' \
  'The base was Resolved #<number> last week.'
do
  cp "$LONGER" "$rs_dir/copy.md"
  printf '\n%s\n' "$bad" >> "$rs_dir/copy.md"
  if [ -n "$(offending "$rs_dir/copy.md")" ]; then
    rs_ok "the reader catches: $(echo "$bad" | tr '\n' ' ')"
  else
    rs_fail "the reader missed: $bad"
  fi
done

# And it leaves the Closes line alone, so a part's own line never trips it.
cp "$LONGER" "$rs_dir/copy.md"
printf '\n%s\n' 'Each part carries its own `Closes #<number>` line.' >> "$rs_dir/copy.md"
if [ -z "$(offending "$rs_dir/copy.md")" ]; then
  rs_ok "the reader passes the Closes line itself"
else
  rs_fail "the reader flagged the Closes line itself"
fi

rs_done
