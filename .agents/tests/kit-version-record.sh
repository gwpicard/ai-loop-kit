#!/usr/bin/env sh
# kit-version-record.sh: guard the record of which kit release a project holds,
# and the line that tells the person when a newer one is out.
#
# Two external projects could not tell which kit they held. One carried an
# older release's label with a newer release's files, and nothing in the
# project named the release or the commit it came from, so nobody could compare
# the files against it. The other stayed six releases behind for weeks, since
# nothing mentioned a newer release until somebody typed /maintain. When its
# person did update, they used the installer's obvious command, a bare
# `npx skills update`, which dropped a renamed skill and never added its
# replacement. The repair took about an hour.
#
# So founding writes a `kit` line naming the version and its tag's commit,
# /maintain keeps it current, /what-now names a newer published release in one
# line, and the founded blocked-commands list says the kit is updated only
# through /maintain. These are prose a coding agent reads, so this reads the
# source: each rule is still there, and removing it breaks the check.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
RECORD="$SKILLS/setup-ai-build-kit/templates/maintenance-record"
MAINTAIN="$SKILLS/maintain/SKILL.md"
WHATNOW="$SKILLS/what-now/SKILL.md"
BLOCKED="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Kit version record checks"
rs_exists "$SETUP" "$RECORD" "$MAINTAIN" "$WHATNOW" "$BLOCKED" "$WORKFLOW"

# Founding writes the line, and names the same release in its first changelog
# entry.
rs_rule "founding writes a kit line with the version and the commit" \
  'kit\|<version>\|<commit>'
rs_rule "the version comes from the installed maintain skill's VERSION" \
  'take the version from the installed .maintain. skill.s .version. file'
rs_rule "a whole copy of the kit falls back to .ai-build-kit-version" \
  '.\.ai-build-kit-version. at the project root gives the version'
rs_rule "the commit is the one the release's tag points at" \
  'git/ref/tags/<version> --jq .\.object\.type, \.object\.sha.'
rs_rule "an annotated tag is recognised by its type" \
  'where the type it prints is .tag. rather than .commit.'
rs_rule "and followed once to reach the commit" \
  'read .\.object\.url. once'
rs_rule "a failed lookup writes unknown and founding carries on" \
  'write the commit as .unknown. and carry on founding'
rs_rule "a resumed founding keeps a kit line already there" \
  'finds a .kit. line already there keeps it'
rs_rule "and writes the changelog entry no second time" \
  'already holds that entry writes it no second time'
rs_rule "the first changelog entry names the same version and commit" \
  'first entry under today.s date, naming the same version and commit'
rs_guard "$SETUP" "the /setup-ai-build-kit skill"

# The record's own header says what the line is and who writes it. Its lines
# are comments, so a phrase that wraps carries a '#' and the patterns stop short
# of a line end.
rs_reset
rs_rule "the template documents the kit line" \
  'writes a kit line, as .kit\|<version>\|<commit>.'
rs_rule "and says the commit is unknown when the lookup failed" \
  'or .unknown. when that lookup failed'
rs_rule "and that maintain rewrites it after an update" \
  'maintain rewrites the kit line after an'
rs_rule "and adds it where it is missing" \
  'adds it where it is missing'
rs_guard "$RECORD" "the maintenance record template"

# /maintain keeps the line current.
rs_reset
rs_rule "a confirmed update rewrites the kit line" \
  'rewrite the .kit. line in .\.ai-build-kit-maintenance. with the new version'
rs_rule "a missing or disagreeing line is written on the visit" \
  'has no .kit. line, or its version differs from this skill.s .version.'
rs_guard "$MAINTAIN" "the maintain skill"

# /what-now reads the files, asks the published release, and says one line.
rs_reset
rs_rule "it reads the installed maintain skill's VERSION" \
  'the installed .maintain. skill.s .version. file'
rs_rule "a whole copy of the kit falls back to .ai-build-kit-version" \
  '.\.ai-build-kit-version. at the project root where that file is missing'
rs_rule "the files win over a kit line that disagrees" \
  'even where the .kit. line in .\.ai-build-kit-maintenance. names another version'
rs_rule "a difference is said in one line naming both and /maintain" \
  'this project holds v0\.20\.0, and v0\.21\.0 is published\. /maintain updates it\.'
rs_rule "a match or a failed call says nothing about the version" \
  'where they match, or the call fails, say nothing about the version'
rs_rule "the version line does not count against the cap of three" \
  'the version line is not one of the three things'
rs_guard "$WHATNOW" "the /what-now skill"

# The founded list of commands never to run says how the kit is updated.
rs_reset
rs_rule "never a bare npx skills update for the kit" \
  'never update the kit with a bare .npx skills update.'
rs_rule "because it can drop a renamed skill" \
  'which can drop a renamed skill'
rs_rule "the kit is updated only through /maintain" \
  'the kit is updated only through ./maintain.'
rs_rule "a request for an update runs /maintain" \
  'where the person asks for an update, run ./maintain.'
rs_guard "$BLOCKED" "the founded blocked-commands list"

# WORKFLOW.md tells the person.
rs_require_load_bearing "WORKFLOW.md says the project records its release" \
  "$WORKFLOW" 'records which ai build kit release it holds'
rs_require_load_bearing "WORKFLOW.md says /what-now names a newer release" \
  "$WORKFLOW" 'a newer release is out, /what-now says so in one line'
rs_require_load_bearing "WORKFLOW.md says to update only through /maintain" \
  "$WORKFLOW" 'update the kit only through /maintain'

rs_done
