#!/usr/bin/env sh
# attribution-scrub.sh: drive the commit-msg hook and read what it wrote.
#
# The hook exists because this repository went public carrying a session link
# in nineteen commit messages and in thirteen pull request descriptions. A
# session link is a personal address on the agent vendor's site. Taking them
# out meant rewriting every commit and force-pushing a branch other people had
# already cloned, which is a thing to do once.
#
# A setting turns the lines off at the source, and this hook is the guard
# behind it, for the session that overrides the setting and the clone that
# never had it. So the hook is the thing worth testing, and it is testable:
# a message goes in, a message comes out, and a machine can judge it.
#
# The case that matters most is the last one. The kit is built with Claude,
# Cursor and Gemini and writes about them in almost every commit. A hook that
# went after the word rather than the attribution line would quietly gut those
# messages, and nobody would notice until the history was unreadable.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
HOOK="$ROOT/.githooks/commit-msg"

[ -f "$HOOK" ] || { echo "FAIL: missing $HOOK" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

passes=0

echo "Attribution scrub checks:"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

ok() {
  echo "  ok: $1"
  passes=$((passes + 1))
}

# scrub <message>: run the real hook over a message, print the result.
scrub() {
  printf '%s\n' "$1" > "$WORK/msg"
  sh "$HOOK" "$WORK/msg"
  cat "$WORK/msg"
}

# gone <what> <message> <needle>: the needle must not survive the hook.
gone() {
  if scrub "$2" | grep -qiF -- "$3"; then
    fail "$1"
  fi
  ok "$1"
}

# kept <what> <message> <needle>: the needle must survive the hook.
kept() {
  if scrub "$2" | grep -qF -- "$3"; then
    ok "$1"
  else
    fail "$1"
  fi
}

# The attribution words are built from pieces rather than written out. The
# validator refuses a tracked file carrying them, and a sample built this way
# gives it nothing to find, so this file needs no exemption. A real line pasted
# in here by mistake is still caught.
session=$(printf 'claude.ai/code/%s' 'session_')
coauthor=$(printf 'Co-%sed-By: Claude' 'Author')
vendor=$(printf 'noreply@%s.com' 'anthropic')

session_trailer="Say the thing

Claude-Session: https://${session}0000000000000000000000"

coauthor_trailer="Say the thing

$coauthor Opus 5 (1M context) <$vendor>"

squashed="Say the thing

Some body text.

---------

$coauthor <$vendor>"

# The same squash merge with another trailer below the removed one. The dashes
# are no longer the last line, and they are still stranded.
squashed_signed="Say the thing

Some body text.

---------

$coauthor <$vendor>
Signed-off-by: A Person <a.person@example.com>"

# A row of dashes with a kept line under it is not stranded.
dashes_kept='Say the thing

---------

Signed-off-by: A Person <a.person@example.com>'

footer='Say the thing

🤖 Generated with [Claude Code](https://claude.com/claude-code)'

plain_footer='Say the thing

🤖 Generated with Claude Code'

about_the_tools='Rename the command that shapes a piece

Claude Code now carries a /plan of its own, which starts its read-only plan
mode. The command is now /shape, and it reads the same in Claude, Cursor and
Gemini alike.'

bare_link="Say the thing

https://${session}0000000000000000000000"

# A sentence that names the tool is not the footer, even when it uses the
# footer's words.
footer_words_in_prose='Say the thing

The first draft was generated with Claude Code and then rewritten by hand.'

plain='Say the thing

A body with nothing to take out of it.'

gone "the session link goes" "$session_trailer" "$session"
gone "the co-author trailer goes" "$coauthor_trailer" "$coauthor"
gone "the vendor address goes with it" "$coauthor_trailer" "$vendor"
gone "the pull request footer goes" "$footer" 'Generated with [Claude Code]'
gone "the footer without its link goes" "$plain_footer" 'Generated with Claude Code'
kept "a sentence using the footer's words stays" "$footer_words_in_prose" 'generated with Claude Code and then'
gone "a bare session link goes" "$bare_link" "$session"

# A squash merge writes a row of dashes above the trailer it folds in. Take the
# trailer and leave the dashes, and every rewritten message ends on punctuation
# with nothing after it.
gone "the stranded squash separator goes too" "$squashed" '---------'
kept "the body above the separator stays" "$squashed" 'Some body text.'
gone "the separator goes when another trailer follows" "$squashed_signed" '---------'
kept "and that other trailer stays" "$squashed_signed" 'Signed-off-by: A Person'
kept "a separator with a kept line under it stays" "$dashes_kept" '---------'

# The subject line is the one part of a message that is always read.
kept "the subject line survives" "$session_trailer" 'Say the thing'

# The rule the hook is most likely to get wrong.
kept "prose about the tools survives" "$about_the_tools" 'reads the same in Claude, Cursor and'
kept "so does a slash command named in prose" "$about_the_tools" '/shape'

# A message with nothing to remove must come back byte for byte, or the hook is
# editing every commit in the repository rather than the ones it was written for.
printf '%s\n' "$plain" > "$WORK/before"
cp "$WORK/before" "$WORK/msg"
sh "$HOOK" "$WORK/msg"
if cmp -s "$WORK/before" "$WORK/msg"; then
  ok "a clean message is returned unchanged"
else
  fail "a clean message was edited"
fi

# The samples above are built from pieces so that the validator can read this
# file like any other. An exemption by path would let a real line pasted in here
# pass unseen, so require that the validator names no such exemption.
if grep -qF '.agents/tests/attribution-scrub.sh' "$ROOT/.agents/tools/validate-kit.sh"; then
  fail "the validator still leaves this file out of its attribution scan"
fi
ok "the validator reads this file like any other"

# The control. A check that cannot fail proves nothing, so take the rule out of
# a copy of the hook and require the run to notice.
#
# The message here is the bare link rather than the trailer. Two rules catch a
# Claude-Session trailer, the one that reads the key and the one that reads the
# address, so removing either still left the trailer caught and the control
# passed while proving nothing. The bare link is reached by one rule only.
sed '/claude.ai\/code\/session_/d' "$HOOK" > "$WORK/hook-without-the-rule"
printf '%s\n' "$bare_link" > "$WORK/msg"
sh "$WORK/hook-without-the-rule" "$WORK/msg"
if grep -qF "$session" "$WORK/msg"; then
  ok "removing the session rule is caught"
else
  fail "the hook still removed the session link without its rule, so nothing here is guarded"
fi

echo
echo "attribution-scrub.sh: all $passes checks passed"
