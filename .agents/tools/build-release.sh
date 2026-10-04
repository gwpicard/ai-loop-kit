#!/usr/bin/env sh
# build-release.sh: assemble a user-ready AI Build Kit starter from the
# maintainer source. It writes only to a new destination outside the source and
# never edits an existing output.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
MANIFEST="$ROOT/release-manifest.txt"

fail() {
  echo "error: $1" >&2
  exit 1
}

if [ "$#" -ne 2 ]; then
  fail "usage: build-release.sh <vMAJOR.MINOR.PATCH> <new-output-folder>"
fi

VERSION=$1
OUTPUT=$2

if ! printf '%s\n' "$VERSION" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$'; then
  fail "version must look like v0.1.0 or v1.2.3-preview.1"
fi

[ -f "$MANIFEST" ] || fail "release-manifest.txt is missing"

output_parent=$(dirname -- "$OUTPUT")
output_name=$(basename -- "$OUTPUT")
[ -d "$output_parent" ] || fail "output parent does not exist: $output_parent"
case "$output_name" in
  ""|.|..) fail "output must name a new folder" ;;
esac
output_parent=$(CDPATH= cd -- "$output_parent" && pwd -P)
OUTPUT="$output_parent/$output_name"
case "$OUTPUT" in
  "$ROOT"|"$ROOT"/*) fail "output must be outside the maintainer source" ;;
esac
[ ! -e "$OUTPUT" ] || fail "output already exists: $OUTPUT"

check_path() {
  path=$1
  label=$2
  case "$path" in
    ""|/*|.|..|../*|*/../*|*/..)
      fail "$label path is not a safe repository-relative path: $path"
      ;;
  esac
}

# Validate the complete packing list before creating any output.
seen_destinations="
"
while IFS='|' read -r source destination extra; do
  case "$source" in
    ""|'#'*) continue ;;
  esac
  [ -z "${extra:-}" ] || fail "manifest line has too many fields: $source"
  [ -n "$destination" ] || destination=$source
  check_path "$source" "source"
  check_path "$destination" "destination"
  [ -e "$ROOT/$source" ] || fail "manifest source does not exist: $source"
  if [ -d "$ROOT/$source" ]; then
    tracked=$(git -C "$ROOT" ls-files -- "$source")
    [ -n "$tracked" ] || fail "manifest directory contains no tracked files: $source"
    while IFS= read -r tracked_file; do
      [ -n "$tracked_file" ] || continue
      [ -e "$ROOT/$tracked_file" ] || fail "tracked release file is missing: $tracked_file"
    done <<TRACKEDFILES
$tracked
TRACKEDFILES
  fi
  case "$seen_destinations" in
    *"
$destination
"*) fail "manifest destination appears twice: $destination" ;;
  esac
  seen_destinations="$seen_destinations$destination
"
done < "$MANIFEST"

umask 022
mkdir -p "$OUTPUT"

while IFS='|' read -r source destination extra; do
  case "$source" in
    ""|'#'*) continue ;;
  esac
  [ -n "$destination" ] || destination=$source
  source_path="$ROOT/$source"
  destination_path="$OUTPUT/$destination"
  mkdir -p "$(dirname -- "$destination_path")"
  if [ -d "$source_path" ]; then
    tracked=$(git -C "$ROOT" ls-files -- "$source")
    while IFS= read -r tracked_file; do
      [ -n "$tracked_file" ] || continue
      suffix=${tracked_file#"$source"/}
      tracked_destination="$destination_path/$suffix"
      mkdir -p "$(dirname -- "$tracked_destination")"
      cp -p "$ROOT/$tracked_file" "$tracked_destination"
    done <<TRACKEDFILES
$tracked
TRACKEDFILES
  else
    cp -p "$source_path" "$destination_path"
  fi
done < "$MANIFEST"

printf '%s\n' "$VERSION" > "$OUTPUT/.ai-build-kit-version"
plugin_version=${VERSION#v}

# The source once always carried the `0.0.0-development` placeholder, so this
# looked for that exact string. It cannot any more: a release now stamps the
# branch as well, so the second release would find the first release's number
# sitting there and stop.
#
# What the old check was really guarding is still guarded, and by a stronger
# rule. A renamed or reformatted version field would make the substitution
# match nothing and ship the release carrying somebody else's number, silently.
# So count the field instead: exactly one, or stop.
stamp_plugin_version() {
  manifest=$1
  [ -f "$manifest" ] || fail "a plugin manifest to stamp is missing: $manifest"
  # `grep -c` prints 0 and exits 1 when nothing matches, and this script runs
  # under `set -e`, so without the guard the build would die here with no
  # message instead of naming the manifest it could not stamp.
  found=$(grep -cE '^[[:space:]]*"version": "[^"]*",?$' "$manifest" 2>/dev/null || true)
  [ -n "$found" ] || found=0
  [ "$found" -eq 1 ] || \
    fail "expected exactly one version field to stamp in $manifest, found $found"
  manifest_tmp="$manifest.tmp"
  sed -E "s/^([[:space:]]*)\"version\": \"[^\"]*\"/\1\"version\": \"$plugin_version\"/" \
    "$manifest" > "$manifest_tmp"
  mv "$manifest_tmp" "$manifest"
}

stamp_plugin_version "$OUTPUT/.claude-plugin/plugin.json"
stamp_plugin_version "$OUTPUT/agent-plugin/plugin.json"

for version_marker in \
  "$OUTPUT/.agents/skills/maintain/VERSION" \
  "$OUTPUT/agent-plugin/skills/maintain/VERSION"; do
  [ -f "$version_marker" ] || fail "a version marker is missing: $version_marker"
  printf '%s\n' "$VERSION" > "$version_marker"
done

echo "Built AI Build Kit $VERSION starter at $OUTPUT"
