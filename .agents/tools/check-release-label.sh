#!/usr/bin/env sh
# check-release-label.sh: refuse a pull request that nobody has sorted.
#
# The release number is chosen by Release Drafter, which cannot read the change.
# It reads the labels. A pull request carrying `feature` raises the minor part;
# one carrying `bug` raises the patch part; one carrying nothing at all falls
# through to "Other changes", which is also a patch.
#
# That last case is the whole reason this exists. An unlabelled pull request does
# not stop anything or ask anybody. It quietly becomes a patch, and a release
# adding a command goes out with a number promising only repairs. That happened:
# four pull requests merged unlabelled, one of them a ninth command, and the
# repository proposed a patch. A person asking a question in conversation is what
# caught it, an hour after the release was cut.
#
# So this asks one question: did somebody choose? It cannot tell whether they
# chose correctly, because working out that a change adds a command means reading
# the change. It only knows when nobody chose at all, and hands that back to a
# person.
#
# `chore` is accepted even though Release Drafter does not name it. Choosing it
# says the change is maintenance with nothing for a reader, which is a decision
# rather than an omission. The rehearsal beside this proves every label Release
# Drafter does name is accepted here, so the two cannot drift apart in the
# direction that matters.
#
# Usage:
#   check-release-label.sh                one label per line on standard input
#   check-release-label.sh bug feature    or as arguments
#
# Exit 0 when at least one accepted label is present, 1 when none is.
#
# POSIX sh.

set -eu

ACCEPTED="feature
enhancement
bug
documentation
chore
skip-release-notes
release-major
release-minor
release-patch"

if [ "$#" -gt 0 ]; then
  found=$(printf '%s\n' "$@")
else
  found=$(cat)
fi

matched=""
for label in $ACCEPTED; do
  printf '%s\n' "$found" | grep -qxF "$label" && matched="$label"
done

if [ -n "$matched" ]; then
  echo "This pull request carries '$matched', so the release number is somebody's decision."
  exit 0
fi

# The message is read by a person looking at a red check, so it says what to do
# rather than what went wrong.
cat >&2 <<MESSAGE
This pull request has no label saying what kind of change it is, so the release
number would be chosen by default rather than by anybody.

Add one of these, then this check passes:

  feature, enhancement   a new thing people using the kit can do   (minor)
  bug                    a repair                                   (patch)
  documentation          a change to what the kit says              (patch)
  chore                  maintenance, nothing for a reader          (patch)
  skip-release-notes     never shows in the notes, such as a
                         version stamp or maintainer-only material

  release-major, release-minor, release-patch
                         force the version, whatever else is present

Labels found on this pull request: ${found:-none}
MESSAGE
exit 1
