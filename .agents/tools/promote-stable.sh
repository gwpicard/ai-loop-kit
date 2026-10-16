#!/usr/bin/env sh
# Run after release verification and the maintainer's approval.
# Usage: GITHUB_REPOSITORY=owner/repo promote-stable.sh vX.Y.Z <full commit>
set -eu
fail() { echo "error: $1" >&2; exit 1; }
[ "$#" -eq 2 ] || fail "usage: $0 <vMAJOR.MINOR.PATCH> <commit>"
VERSION=$1
COMMIT=$2
REPO=${GITHUB_REPOSITORY:-}
printf '%s\n' "$VERSION" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' ||
  fail "the version must be a stable release such as v1.3.0"
printf '%s\n' "$COMMIT" | grep -Eq '^[0-9a-f]{40}$' ||
  fail "the commit must be a full forty-character object name"
[ -n "$REPO" ] || fail "GITHUB_REPOSITORY is not set"

published=$(gh api "repos/$REPO/releases/tags/$VERSION" \
  --jq '.draft == false and .prerelease == false and .published_at != null') ||
  fail "$VERSION has no published release"
[ "$published" = true ] || fail "$VERSION is not a published stable release"
tagged=$(gh api "repos/$REPO/commits/refs/tags/$VERSION" --jq '.sha') ||
  fail "$VERSION has no tag commit"
[ "$tagged" = "$COMMIT" ] || fail "$VERSION does not name $COMMIT"

# stable already exists. Refuse a divergent update rather than overwrite work.
gh api --method PATCH "repos/$REPO/git/refs/heads/stable" \
  -f "sha=$COMMIT" -F force=false >/dev/null || fail "stable could not be moved"
landed=$(gh api "repos/$REPO/git/ref/heads/stable" --jq '.object.sha') ||
  fail "stable could not be read back"
[ "$landed" = "$COMMIT" ] || fail "stable reads back as $landed instead of $COMMIT"
echo "stable now points at $VERSION ($COMMIT)."
