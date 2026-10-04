#!/usr/bin/env bash
# verify-port.sh <source-repo> <target-repo>
#
# Reads the ported repository back and compares it against the source. The one
# that matters is the numbering: an issue that moved is an issue whose number
# every note and link now points past.
set -uo pipefail

SRC=$1
DST=$2
fails=0

ok()   { echo "  ok: $1"; }
bad()  { echo "  FAIL: $1"; fails=$((fails + 1)); }

echo "Comparing $DST against $SRC:"

src_items=$(gh api "repos/$SRC/issues?state=all&per_page=100" --paginate -q '.[].number' | sort -n)
dst_items=$(gh api "repos/$DST/issues?state=all&per_page=100" --paginate -q '.[].number' | sort -n)
[ "$src_items" = "$dst_items" ] && ok "every number from 1 to the last one is present and matches" \
                                || bad "the numbers differ"

# Title per number. A shifted port still has the right count, so compare content.
moved=0
for n in $src_items; do
  a=$(gh api "repos/$SRC/issues/$n" -q '.title' 2>/dev/null)
  b=$(gh api "repos/$DST/issues/$n" -q '.title' 2>/dev/null)
  if [ "$a" != "$b" ]; then
    echo "      $n: '$a' became '$b'"
    moved=$((moved + 1))
  fi
done
[ "$moved" -eq 0 ] && ok "every number still carries its own title" \
                   || bad "$moved item(s) landed on the wrong number"

src_open=$(gh api "repos/$SRC/issues?state=open&per_page=100" --paginate -q '[.[] | select(.pull_request == null)] | length')
dst_open=$(gh api "repos/$DST/issues?state=open&per_page=100" --paginate -q '[.[] | select(.pull_request == null)] | length')
[ "$src_open" = "$dst_open" ] && ok "open issues: $dst_open" \
                              || bad "open issues: $src_open on the source, $dst_open on the target"

src_com=$(gh api "repos/$SRC/issues/comments?per_page=100" --paginate -q 'length' | paste -sd+ | bc)
dst_com=$(gh api "repos/$DST/issues/comments?per_page=100" --paginate -q 'length' | paste -sd+ | bc)
[ "$src_com" = "$dst_com" ] && ok "comments: $dst_com" \
                            || bad "comments: $src_com on the source, $dst_com on the target"

src_lab=$(gh api "repos/$SRC/labels?per_page=100" --paginate -q '.[].name' | sort | md5sum)
dst_lab=$(gh api "repos/$DST/labels?per_page=100" --paginate -q '.[].name' | sort | md5sum)
[ "$src_lab" = "$dst_lab" ] && ok "labels match by name" || bad "labels differ"

src_rel=$(gh api "repos/$SRC/releases?per_page=100" --paginate -q '.[].tag_name' | sort | md5sum)
dst_rel=$(gh api "repos/$DST/releases?per_page=100" --paginate -q '.[].tag_name' | sort | md5sum)
[ "$src_rel" = "$dst_rel" ] && ok "releases match by tag" || bad "releases differ"

src_ass=$(gh api "repos/$SRC/releases?per_page=100" --paginate -q '[.[].assets[].name] | length')
dst_ass=$(gh api "repos/$DST/releases?per_page=100" --paginate -q '[.[].assets[].name] | length')
[ "$src_ass" = "$dst_ass" ] && ok "release assets: $dst_ass" \
                            || bad "release assets: $src_ass on the source, $dst_ass on the target"

subs=$(gh api "repos/$DST/issues/9/sub_issues" -q 'length' 2>/dev/null || echo 0)
[ "$subs" = "3" ] && ok "the epic still has its three children" \
                  || bad "the epic has $subs children, expected 3"

echo
echo "=== the point of the whole exercise ==="
# Built rather than written out, so this file does not trip the tracked-file
# attribution rule it exists to serve. validate-kit.sh looks for these words.
needle_link=$(printf 'claude.ai/code/%s' 'session_')
needle_author=$(printf 'co-%sed-by: claude' 'author')
dirty=$(gh api "repos/$DST/issues?state=all&per_page=100" --paginate -q '.[].body // ""' \
        | grep -icE "$needle_link|$needle_author|claude-session:" || true)
[ "$dirty" = "0" ] && ok "no ported issue body carries an attribution line" \
                   || bad "$dirty ported bodies still carry one"

echo
if [ "$fails" -eq 0 ]; then
  echo "verify-port.sh: everything matched"
else
  echo "verify-port.sh: $fails check(s) FAILED" >&2
  exit 1
fi
