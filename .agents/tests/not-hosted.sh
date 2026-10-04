#!/usr/bin/env sh
# not-hosted.sh: guard the third way a tool goes live, which is not at all.
#
# The masterplan's `Goes live:` line had two values: a merge reaches a preview
# and /ship promotes it, or the host puts every merge live. Two projects built
# with the kit had no live address at all. One was a skill library people
# install straight from the repository, the other a report generator run on the
# person's own computer. For them the merge step had no right answer. It asked
# whether merging puts the tool live and treated the merge as going live until
# told otherwise, and on `on every merge` it took the first merge for a first
# launch: a hosting request, a wait for an address that would never come, and a
# rollback line. A run's pre-approved merges were held back for the same reason.
#
# So a tool with no live address records `not hosted`. A merge there is never a
# launch, and what /ship makes for it is a release: a Git tag with a GitHub
# release. The rules are prose a coding agent reads, so this reads them back and
# proves each one load-bearing by removing it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
MERGE="$SKILLS/section-builder/references/merge.md"
SHIP="$SKILLS/ship/SKILL.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
MASTERPLAN="$SKILLS/setup-ai-build-kit/templates/masterplan.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Not hosted checks"
rs_exists "$MERGE" "$SHIP" "$SETUP" "$MASTERPLAN" "$WORKFLOW"

# --- the merge step -----------------------------------------------------------

rs_rule "the third value is defined" \
  '`not hosted` means no server runs the tool for people to reach: people install it, copy it, or run it on their own computer'
rs_rule "a merge on it is never a launch" 'on `not hosted`, a merge is never a launch'
rs_rule "the ask never says this goes live now" 'the ask never says "this goes live now", and no first-launch checks run'
rs_rule "its launch is a release /ship makes" 'what goes live for such a tool is a release, which `/ship` makes'
rs_rule "a recipe wins over not hosted" \
  'where agents\.md names a recipe and the line says `not hosted`, the recipe wins, since a recipe is a place the tool runs'
rs_rule "the recipe's going-live section decides then" \
  'where it says a change to `main` goes live, treat the merge as `on every merge`, and otherwise as `through /ship`'
rs_rule "a missing line asks which of the three" \
  'ask, in the reply that asks for the merge, which of the three it is: the merge reaches a preview, the merge goes live, or nothing is hosted'
rs_rule "condition 6 counts not hosted as not going live" \
  '6\. its merge would not go live: the `goes live:` line says `through /ship` or `not hosted`'
rs_rule "pre-approval covers a not-hosted merge" \
  'a merge on a tool that is `not hosted` puts nothing live, so pre-approval covers it too'
rs_guard "$MERGE" "the merge step"

# --- /ship --------------------------------------------------------------------

rs_reset
rs_rule "Build and run it hands a not-hosted tool to the release" \
  'where the `goes live:` line says `not hosted` and no recipe is named, going live is a release\. follow "releasing a tool that is not hosted" below, which says when steps 1 and 2 run, in place of steps 3 and 4'
rs_rule "Build with care hands a not-hosted tool to the release too" \
  'on a tool that is `not hosted`, with no recipe named, readiness and going live give way to the release, inside the named areas as well as outside them'
rs_rule "each area's caution still comes first, with no go-live of its own" \
  'give each area.s caution or risk notice as below, then make one release as "releasing a tool that is not hosted" says, with no readiness check and no go-live step of its own for any area'
rs_rule "each later /ship is another release" \
  'on a tool that is not hosted, each later /ship is another release'
rs_rule "the release section is there" '#### releasing a tool that is not hosted'
rs_rule "a release is a tag with a github release" 'going live means cutting a release: a git tag with a github release'
rs_rule "with a recipe too, say so once and follow the recipe" \
  'where a recipe is named as well, the two disagree\. say so once, follow the recipe, since a recipe is a place the tool runs, and leave this section out'
rs_rule "it names each change since the last release tag" \
  'name what the release holds: each change since the last release tag, one plain line each'
rs_rule "read from changes/ and the changelog above the newest Released line" \
  'read from the files in `changes/` and the lines of changelog\.md above its newest `released` line, or every line when there is none'
rs_rule "nothing changed means no release" 'where nothing changed since the last release, say so and make no release'
rs_rule "the evidence run and the review come first" \
  'run the checks this path requires before the release: the evidence run and the review'
rs_rule "no request record check or monitoring caution" \
  'leave out the request record check and the monitoring caution, since nothing serves requests'
rs_rule "no hosting request, no address, no rollback line" \
  'write no hosting request, wait for no address, and write no rollback line'
rs_rule "the tags github holds are read too" 'read the tags github holds with `git fetch --tags`'
rs_rule "the next minor version is proposed" \
  'propose the next minor version after the newest tag of the form `vx\.y\.z`: `v1\.4\.2` gives `v1\.5\.0`'
rs_rule "no such tag gives v0.1.0" 'where no tag has that form, propose `v0\.1\.0`'
rs_rule "another form is named and the newest vX.Y.Z still counts" \
  'where the newest tag has another form, name the tag you found in one line, and still count from the newest one of the form `vx\.y\.z`'
rs_rule "the person may name another tag" 'the person may name another tag in their reply'
rs_rule "an existing tag is named and nothing is created" \
  'where the tag already exists, because somebody made it by hand, name it and ask for another, and create nothing until the person names one'
rs_rule "the yes names the release" 'say yes to release v1\.5\.0 with these three changes\.'
rs_rule "release only on that yes" 'release only on that yes'
rs_rule "a merge yes does not cover the release" 'a yes to a merge does not cover the release'
rs_rule "a no leaves everything as it was" 'a no leaves everything as it was'
rs_rule "the release command" \
  '`gh release create <tag> --target main --title <tag> --notes-file <file>`'
rs_rule "an unreachable github makes no release" \
  'where github cannot be reached, no release is made: say in one line that the release waits and can be asked for again once github answers'
rs_rule "no repository or the checkpoint route makes a local tag" \
  'where the project has no github repository, or saves on the checkpoint route, the release is a local annotated tag instead, made on the same named yes with `git tag -a <tag> -m "<tag>" main`'
rs_rule "and says nothing was published" 'say that the tag stays on this computer and nothing was published'
rs_rule "the launch record reads Released and the tag" 'the launch record in changelog\.md reads `released <tag>`'
rs_rule "a not-hosted tool has nothing to promote" \
  'on `not hosted`, there is nothing to promote either: going live is a release'
rs_rule "the Goes live line written at a launch may say not hosted" \
  'write one, from the recipe.s going-live section or from what the person says: `through /ship`, `on every merge` or `not hosted`'
rs_guard "$SHIP" "the ship skill"
rs_require_order "the release section sits before Merging and deploying" "$SHIP" \
  '^#### Releasing a tool that is not hosted$' '^#### Merging and deploying$'

# --- the masterplan template --------------------------------------------------

rs_require_load_bearing "the template defines not hosted beside the other two" "$MASTERPLAN" \
  'or `not hosted`, where no server runs the tool for people to reach, because people install it, copy it, or run it on their own computer'
rs_require_load_bearing "the template says a merge there is never a launch" "$MASTERPLAN" \
  'on `not hosted`, a merge is never a launch, and /ship makes a release instead'

# --- founding -----------------------------------------------------------------

rs_reset
rs_rule "founding writes the line before the first checkpoint" \
  'write the masterplan.s `goes live:` line in "how it stays running" before the first checkpoint'
rs_rule "from answers it already has, with no new question" \
  'from answers founding already has, and ask nothing new for it'
rs_rule "on a recipe, from its going-live section" \
  'on a recipe, write what its going-live section says, read as the `section-builder` skill.s `references/merge\.md` reads it'
rs_rule "off a recipe, not hosted when nothing is hosted" \
  'off a recipe, write `goes live: not hosted` where the interview or the two questions above say nothing is hosted'
rs_rule "otherwise no line, and the first merge asks" 'otherwise write no line, and the first merge asks'
rs_guard "$SETUP" "the founding skill"

# --- WORKFLOW.md --------------------------------------------------------------

rs_reset
rs_rule "WORKFLOW names the third value" 'a tool with no live address, such as a library people install or a program they run on their own computer, records `not hosted` instead'
rs_rule "WORKFLOW says its merges are never a launch" 'its merges are never a launch, and a run may merge them'
rs_rule "WORKFLOW says the first merge asks once" 'if the masterplan does not say, the first merge asks which of the three it is, once'
rs_rule "WORKFLOW says going live is a release" 'on a tool that is not hosted, going live is a release'
rs_rule "WORKFLOW says what /ship does for it" \
  '/ship names each change since the last release, runs the evidence run and the review, proposes the next version, such as v1\.5\.0 after v1\.4\.2, and makes a github release on your yes naming it'
rs_rule "WORKFLOW says there is no hosting request, address or rollback" \
  'there is no hosting request, no address and no rollback line'
rs_rule "WORKFLOW says main still reaches people installing from it" \
  'anyone who installs straight from `main` still gets each merge the moment it lands'
rs_guard "$WORKFLOW" "WORKFLOW.md"

rs_done
