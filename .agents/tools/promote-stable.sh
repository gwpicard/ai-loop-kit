#!/usr/bin/env sh
# promote-stable.sh: point `stable` at a release that has just been verified.
#
# Why this exists. Two of the three installation routes read the repository's
# default branch, and that is the branch where work merges. So a project that
# installed between two releases received the last release's version label with
# unreleased work sitting behind it, and /maintain told it that it was up to
# date. `stable` is the branch a release moves and nothing else touches, so the
# default branch can be a released tree rather than a working one.
#
# This runs from `verify release`, after verification has passed, so a release
# that failed verification never becomes the channel the world installs from.
#
# What bounds the write. This is the one place in the repository where a
# workflow changes a branch, so the limits matter more than the mechanism:
#
#   - The ref is written out here. No argument names it, so nothing a caller
#     passes can redirect the write to `main` or anywhere else.
#   - The commit has to be the commit of the published tag, asked of GitHub
#     rather than believed. A commit that no published tag names is refused,
#     so the tool cannot be told to point `stable` at an arbitrary tree.
#   - It writes through the GitHub API with the run's own token rather than
#     pushing. Nothing here mints a credential, and the repository's tree still
#     changes only through a reviewed pull request.
#   - It reads the ref back afterwards. An API call that answers cheerfully and
#     changes nothing is the one fault that would leave `stable` a release
#     behind while the run went green.
#
# Create or update, because `stable` does not exist until the first release
# moves it. The update forces, because a release cut from a commit that is not
# a descendant of the last one would otherwise leave `stable` stuck on the
# older version. The commit is already proved to be reviewed main-branch work
# by the job that calls this, so forcing cannot reach unreviewed material.
#
# Usage:
#   promote-stable.sh vX.Y.Z <commit>
#
# Needs GITHUB_REPOSITORY and a `gh` that can write to it.
#
# POSIX sh.

set -eu

fail() {
  echo "error: $1" >&2
  exit 1
}

BRANCH=stable

[ "$#" -eq 2 ] || fail "usage: $0 <vMAJOR.MINOR.PATCH> <commit>"
VERSION=$1
COMMIT=$2

# Stable versions only, the same shape the stamp and the verification accept. A
# preview must never become the branch every installer reads.
printf '%s\n' "$VERSION" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' || \
  fail "the version must be stable and look like v0.1.0"

printf '%s\n' "$COMMIT" | grep -Eq '^[0-9a-f]{40}$' || \
  fail "the commit must be a full forty-character object name"

REPO=${GITHUB_REPOSITORY:-}
[ -n "$REPO" ] || fail "GITHUB_REPOSITORY is not set, so there is no repository to write to"

command -v gh >/dev/null 2>&1 || fail "the GitHub CLI is not available"

# The tag decides the commit. Passing one in is a convenience for the job that
# already worked it out; it is not authority.
tagged=$(gh api "repos/$REPO/commits/$VERSION" --jq '.sha' 2>/dev/null || true)
[ -n "$tagged" ] || \
  fail "$VERSION has no commit on $REPO, so there is no published release to promote"
[ "$tagged" = "$COMMIT" ] || \
  fail "$VERSION points at $tagged, not at $COMMIT; $BRANCH was left where it was"

if gh api "repos/$REPO/git/ref/heads/$BRANCH" >/dev/null 2>&1; then
  echo "Moving $BRANCH to $VERSION."
  gh api --method PATCH "repos/$REPO/git/refs/heads/$BRANCH" \
    -f "sha=$COMMIT" -F force=true >/dev/null
else
  echo "Creating $BRANCH at $VERSION. This is the release that brings it into being."
  gh api --method POST "repos/$REPO/git/refs" \
    -f "ref=refs/heads/$BRANCH" -f "sha=$COMMIT" >/dev/null
fi

landed=$(gh api "repos/$REPO/git/ref/heads/$BRANCH" --jq '.object.sha' 2>/dev/null || true)
[ "$landed" = "$COMMIT" ] || \
  fail "$BRANCH reads back as ${landed:-nothing} rather than $COMMIT, so the move did not happen"

echo "$BRANCH now points at $VERSION ($COMMIT)."
