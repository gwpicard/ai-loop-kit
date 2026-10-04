#!/usr/bin/env sh
# stamp-version.sh: write a released version into the three files that carry
# one, or check that they already carry it.
#
# Why this exists. Three files tell an installation which version it is:
#
#   .claude-plugin/plugin.json        read by the Claude plugin route
#   agent-plugin/plugin.json          read by an Agent Plugins client
#   .agents/skills/maintain/VERSION   read by /maintain, every visit
#
# While the released kit lived in a separate repository, those files held
# `0.0.0-development` here and the release builder wrote the real number into
# the packaged copy. That worked because the public repository was the packaged
# copy, so an installer reading it read a real version.
#
# One repository ends that. Both installers read the default branch, so the
# default branch is what they see. Left unstamped, every project would install
# `v0.0.0-development`, and /maintain compares that file with the latest public
# Release: it would announce an update that is already installed, apply it, and
# then report that it did not take. Every visit, for everybody.
#
# So a release stamps the branch. It goes in through an ordinary reviewed pull
# request rather than a workflow push, because branch protection binds
# administrators and a pushing workflow would need a bypass, which is the
# privileged actor that retiring the publication credential removed.
#
# Between releases `main` carries the last released version while its contents
# move ahead of it. That used to be what a project received, and it is not any
# more. Installers read the repository's default branch, and that branch is
# `stable`, which only a verified release moves. So the number stamped here is
# the number of the tree an installation actually gets, and the two cannot
# drift apart while work merges.
#
# `main` is still the thing that gets stamped, because the stamp is what
# `prepare release` checks and what the release is assembled from. A
# version-bearing file on `main` between releases is an internal fact about
# what the next release will say, rather than a promise made to anybody.
#
# Usage:
#   stamp-version.sh vX.Y.Z            write that version into all three files
#   stamp-version.sh --check vX.Y.Z    confirm all three already carry it
#
# `prepare release` calls --check, so "stamped" has one definition rather than
# two that can drift apart.
#
# POSIX sh.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

fail() {
  echo "error: $1" >&2
  exit 1
}

CHECK=0
case "${1:-}" in
  --check)
    CHECK=1
    shift
    ;;
esac

[ "$#" -eq 1 ] || fail "usage: $0 [--check] <vMAJOR.MINOR.PATCH>"
VERSION=$1

# Stable versions only. A preview must never reach the branch every installer
# reads, because an installation would then claim a version with no Release
# behind it.
printf '%s\n' "$VERSION" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' || \
  fail "the version must be stable and look like v0.1.0"

PLAIN=${VERSION#v}

CLAUDE_MANIFEST="$ROOT/.claude-plugin/plugin.json"
AGENT_MANIFEST="$ROOT/agent-plugin/plugin.json"
MAINTAIN_VERSION="$ROOT/.agents/skills/maintain/VERSION"

for required in "$CLAUDE_MANIFEST" "$AGENT_MANIFEST" "$MAINTAIN_VERSION"; do
  [ -f "$required" ] || fail "a version-bearing file is missing: ${required#"$ROOT"/}"
done

# One version field, or nothing is stamped and the release ships carrying
# somebody else's number. A manifest whose field was renamed or reformatted
# would otherwise turn the stamp into a silent no-op.
# `grep -c` prints 0 and exits 1 when nothing matches. Under `set -e` a bare
# assignment from it kills the script, so the named error below never prints and
# the operator gets a bare exit on the one fault this file exists to catch.
manifest_version_count() {
  count=$(grep -cE '^[[:space:]]*"version": "[^"]*",?$' "$1" 2>/dev/null || true)
  [ -n "$count" ] || count=0
  printf '%s\n' "$count"
}

for manifest in "$CLAUDE_MANIFEST" "$AGENT_MANIFEST"; do
  found=$(manifest_version_count "$manifest")
  [ "$found" -eq 1 ] || \
    fail "expected exactly one version field in ${manifest#"$ROOT"/}, found $found"
done

if [ "$CHECK" -eq 1 ]; then
  stamped_ok=yes
  for manifest in "$CLAUDE_MANIFEST" "$AGENT_MANIFEST"; do
    if ! grep -qF "\"version\": \"$PLAIN\"" "$manifest"; then
      echo "not stamped for $VERSION: ${manifest#"$ROOT"/}" >&2
      stamped_ok=no
    fi
  done
  if [ "$(cat "$MAINTAIN_VERSION")" != "$VERSION" ]; then
    echo "not stamped for $VERSION: ${MAINTAIN_VERSION#"$ROOT"/}" >&2
    stamped_ok=no
  fi
  [ "$stamped_ok" = "yes" ] || \
    fail "main does not carry $VERSION; stamp it and merge that before preparing the release"
  echo "main carries $VERSION in all three version-bearing files"
  exit 0
fi

for manifest in "$CLAUDE_MANIFEST" "$AGENT_MANIFEST"; do
  tmp="$manifest.tmp"
  sed -E "s/^([[:space:]]*)\"version\": \"[^\"]*\"/\1\"version\": \"$PLAIN\"/" \
    "$manifest" > "$tmp"
  mv "$tmp" "$manifest"
done
printf '%s\n' "$VERSION" > "$MAINTAIN_VERSION"

echo "Stamped $VERSION into:"
for stamped in "$CLAUDE_MANIFEST" "$AGENT_MANIFEST" "$MAINTAIN_VERSION"; do
  echo "  ${stamped#"$ROOT"/}"
done
