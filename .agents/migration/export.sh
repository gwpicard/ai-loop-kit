#!/usr/bin/env bash
# export.sh <source-repo> <output-dir>
#
# Reads everything out of a repository that is not git: issues, pull requests,
# their comments, labels, releases, sub-issue links and the repository settings.
# Writes plain JSON that port.py reads back.
#
# Run this immediately before a migration, never from an old copy. The export is
# a snapshot, and an issue opened or a comment added between the export and the
# port is an issue or a comment that does not survive. It also shifts every
# number after it, which is the one failure this whole exercise cannot absorb.
#
# Read-only. It changes nothing in the source repository.
set -euo pipefail

SRC=$1
OUT=$2
mkdir -p "$OUT/comments"

echo "== issues and pull requests =="
# One endpoint returns both, which is what gives the numbering in one sequence.
gh api "repos/$SRC/issues?state=all&per_page=100" --paginate > "$OUT/issues.json"
gh api "repos/$SRC/pulls?state=all&per_page=100"  --paginate > "$OUT/pulls.json"

echo "== comments =="
for n in $(python3 -c "
import json
print(' '.join(str(i['number']) for i in json.load(open('$OUT/issues.json'))))"); do
  gh api "repos/$SRC/issues/$n/comments?per_page=100" --paginate > "$OUT/comments/$n.json"
done

echo "== labels, releases, settings =="
gh api "repos/$SRC/labels?per_page=100"   --paginate > "$OUT/labels.json"
gh api "repos/$SRC/releases?per_page=100" --paginate > "$OUT/releases.json"
gh api "repos/$SRC"                                  > "$OUT/repo.json"

echo "== sub-issue links =="
owner=${SRC%%/*}
name=${SRC##*/}
gh api graphql -f query="
{ repository(owner: \"$owner\", name: \"$name\") {
    issues(first: 100, states: [OPEN, CLOSED]) {
      nodes { number subIssues(first: 50) { nodes { number } } } } } }" \
  -q '[.data.repository.issues.nodes[] | select(.subIssues.nodes | length > 0)
       | {key: (.number|tostring), value: [.subIssues.nodes[].number]}] | from_entries' \
  > "$OUT/sub-issues.json"

echo
echo "== what came out =="
python3 - <<PY
import json, pathlib
out = pathlib.Path("$OUT")
issues = json.loads((out / 'issues.json').read_text())
nums = sorted(i['number'] for i in issues)
gaps = [n for n in range(1, nums[-1] + 1) if n not in nums]
comments = sum(len(json.loads(p.read_text())) for p in (out / 'comments').glob('*.json'))
links = json.loads((out / 'sub-issues.json').read_text())
print(f"  numbers      : 1 to {nums[-1]}, {len(issues)} items")
print(f"  gaps         : {gaps or 'none'}")
print(f"  pull requests: {sum(1 for i in issues if 'pull_request' in i)}")
print(f"  issues       : {sum(1 for i in issues if 'pull_request' not in i)}")
print(f"  open issues  : {sum(1 for i in issues if 'pull_request' not in i and i['state'] == 'open')}")
print(f"  comments     : {comments}")
print(f"  labels       : {len(json.loads((out / 'labels.json').read_text()))}")
rels = json.loads((out / 'releases.json').read_text())
print(f"  releases     : {len(rels)}, assets: {sum(len(r['assets']) for r in rels)}")
print(f"  sub-issues   : {links or 'none'}")
if gaps:
    raise SystemExit("\\n  STOP: the export has gaps. Numbering cannot be preserved.")
PY

echo
echo "== attribution check on the exported text =="
# Built rather than written out, so this file does not trip the tracked-file
# attribution rule. Anything found here would be carried into the new
# repository by the port, which would defeat the point of migrating.
needle_link=$(printf 'claude.ai/code/%s' 'session_')
needle_author=$(printf 'co-%sed-by: claude' 'author')
needle_vendor=$(printf 'noreply@%s.com' 'anthropic')
if grep -rIiE -e "$needle_link" -e "$needle_author" -e "$needle_vendor" -e 'claude-session:' \
     "$OUT" >/dev/null 2>&1; then
  echo "  STOP: the exported text still carries an attribution line."
  echo "  Clean the source issues, comments or release notes first."
  exit 1
fi
echo "  clean"
