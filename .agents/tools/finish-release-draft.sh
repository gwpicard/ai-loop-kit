#!/usr/bin/env sh
# finish-release-draft.sh: attach one checked starter to the current draft Release.

set -eu

GH_COMMAND=${GH_COMMAND:-gh}
VERSION=${1:-}
ARCHIVE=${2:-}
TARGET=${3:-}

fail() {
  echo "Release preparation stopped: $1" >&2
  exit 1
}

printf '%s\n' "$VERSION" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' || \
  fail "the version must be stable and look like v0.1.0"
[ -f "$ARCHIVE" ] || fail "the checked starter archive does not exist"
[ -n "$TARGET" ] || fail "the reviewed main-branch commit is missing"

expected_asset="ai-build-kit-$VERSION.tar.gz"
[ "$(basename "$ARCHIVE")" = "$expected_asset" ] || \
  fail "the starter archive name does not match $VERSION"

draft_tags=$("$GH_COMMAND" release list --limit 100 --json tagName,isDraft \
  --jq '.[] | select(.isDraft) | .tagName') || \
  fail "the existing draft Releases could not be checked"
for draft_tag in $draft_tags; do
  [ "$draft_tag" = "$VERSION" ] || \
    fail "the current draft uses $draft_tag; prepare that version or refresh the draft first"
done

if "$GH_COMMAND" release view "$VERSION" >/dev/null 2>&1; then
  is_draft=$("$GH_COMMAND" release view "$VERSION" --json isDraft --jq '.isDraft') || \
    fail "$VERSION could not be checked"
  [ "$is_draft" = "true" ] || \
    fail "$VERSION already has a published Release"

  "$GH_COMMAND" release edit "$VERSION" \
    --target "$TARGET" \
    --title "AI Build Kit $VERSION"
  "$GH_COMMAND" release upload "$VERSION" \
    "$ARCHIVE#AI Build Kit starter" \
    --clobber

  assets=$("$GH_COMMAND" release view "$VERSION" --json assets \
    --jq '.assets[].name') || fail "the draft's starter archives could not be checked"
  for asset in $assets; do
    case "$asset" in
      ai-build-kit-v*.tar.gz)
        if [ "$asset" != "$expected_asset" ]; then
          "$GH_COMMAND" release delete-asset "$VERSION" "$asset" --yes
        fi
        ;;
    esac
  done
else
  fail "no draft Release exists for $VERSION; run the update release draft workflow, then prepare it again"
fi

echo "Prepared the checked $VERSION starter on its draft Release"
