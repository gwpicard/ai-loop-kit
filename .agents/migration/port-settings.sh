#!/usr/bin/env bash
# port-settings.sh <source-repo> <target-repo>
#
# Carries across the parts of a repository that are neither git nor issues:
# the release tarballs people actually download, the merge and branch settings,
# the description, and the branch ruleset.
#
# The social preview image is not here. It can only be uploaded through the web
# interface, so it stays a job for a person.
set -euo pipefail

SRC=$1
DST=$2
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== description and settings =="
desc=$(gh api "repos/$SRC" -q '.description // ""')
gh api -X PATCH "repos/$DST" --input - >/dev/null <<JSON
{
  "description": $(printf '%s' "$desc" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "has_issues": true,
  "has_projects": $(gh api "repos/$SRC" -q '.has_projects'),
  "has_wiki": $(gh api "repos/$SRC" -q '.has_wiki'),
  "allow_squash_merge": $(gh api "repos/$SRC" -q '.allow_squash_merge'),
  "allow_merge_commit": $(gh api "repos/$SRC" -q '.allow_merge_commit'),
  "allow_rebase_merge": $(gh api "repos/$SRC" -q '.allow_rebase_merge'),
  "allow_auto_merge": $(gh api "repos/$SRC" -q '.allow_auto_merge'),
  "delete_branch_on_merge": $(gh api "repos/$SRC" -q '.delete_branch_on_merge'),
  "squash_merge_commit_title": "$(gh api "repos/$SRC" -q '.squash_merge_commit_title')",
  "squash_merge_commit_message": "$(gh api "repos/$SRC" -q '.squash_merge_commit_message')"
}
JSON
echo "   settings applied"

echo "== topics =="
topics=$(gh api "repos/$SRC" -q '{names: .topics}')
if [ "$(printf '%s' "$topics" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["names"]))')" -gt 0 ]; then
  printf '%s' "$topics" | gh api -X PUT "repos/$DST/topics" --input - >/dev/null
  echo "   topics applied"
else
  echo "   none set on the source"
fi

echo "== release assets =="
count=0
for tag in $(gh api "repos/$SRC/releases?per_page=100" --paginate \
             -q '.[] | select((.assets|length)>0) | .tag_name'); do
  rm -rf "$WORK/$tag"; mkdir -p "$WORK/$tag"
  gh release download "$tag" --repo "$SRC" --dir "$WORK/$tag" --clobber
  for f in "$WORK/$tag"/*; do
    [ -f "$f" ] || continue
    gh release upload "$tag" "$f" --repo "$DST" --clobber
    count=$((count + 1))
    echo "   $tag <- $(basename "$f")"
  done
done
echo "   $count asset(s) uploaded"

echo "== branch ruleset =="
# Rebuilt rather than copied: a ruleset carries ids that belong to the source.
gh api -X POST "repos/$DST/rulesets" --input - >/dev/null <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "source-kit-validation" },
          { "context": "rehearsal" }
        ]
      } }
  ]
}
JSON
echo "   ruleset created, enforcement active"

echo
echo "Left for a person: the social preview image, which is web interface only."
