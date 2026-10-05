#!/usr/bin/env sh
# area-map.sh: guard the written rules around the area map, the Areas section of
# a founded project's docs/working-rules.md that names an area for every
# folder.
#
# A piece's Boundary: and Reaches: lines name areas, and a run plans from them.
# An area that names no real place in the code makes both lines guesses. So
# the map covers the whole project on every build path, the project check runs
# area-map.py on it, and every skill that used to read the masterplan's
# sensitive-area paths by hand reads the map through that script instead.
# area-map-rehearsal.sh runs the script. This half reads back the words that
# send each step to it, and proves each rule is load-bearing.
#
# It replaces the check that guarded the older map, which lived in the
# masterplan and only on Build with care, so it also carries that check's
# rules: the optional Bearer scan and its licence, the map moving in the same
# save as the code, the plain read-back at founding, the builder's fixed
# review line, and the boundary reader it names.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
SETUP_SKILL="$SKILLS/setup-ai-build-kit"
FIT="$SETUP_SKILL/references/fit-check.md"
RULES_TEMPLATE="$SETUP_SKILL/templates/working-rules.md"
MASTER="$SETUP_SKILL/templates/masterplan.md"
FOUNDATION="$SETUP_SKILL/templates/foundation"
INSTRUCTIONS="$FOUNDATION/AGENTS.md"
CHECKS="$FOUNDATION/checks.yml"
SCRIPT="$FOUNDATION/area-map.py"
SETUP="$SETUP_SKILL/SKILL.md"
PIECES="$SETUP_SKILL/references/pieces.md"
BOUNDARY="$SETUP_SKILL/references/boundary-rules.md"
PROJECT_CHECK="$SETUP_SKILL/references/project-check.md"
CHANGES="$SETUP_SKILL/references/masterplan-changes.md"
BOOTSTRAP="$SETUP_SKILL/scripts/bootstrap-project.sh"
PLACE="$SETUP_SKILL/scripts/place-plan-helper.sh"
SHAPE="$SKILLS/shape/SKILL.md"
REACH="$SKILLS/section-builder/references/reach-check.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
STRENGTH="$SKILLS/section-builder/references/test-strength.md"
MAINTAIN="$SKILLS/maintain/SKILL.md"
SHIP="$SKILLS/ship/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Area map rules"
rs_exists "$FIT" "$RULES_TEMPLATE" "$MASTER" "$INSTRUCTIONS" "$CHECKS" "$SCRIPT" \
  "$SETUP" "$PIECES" "$BOUNDARY" "$PROJECT_CHECK" "$CHANGES" "$BOOTSTRAP" "$PLACE" \
  "$SHAPE" "$REACH" "$BUILDER" "$STRENGTH" "$MAINTAIN" "$SHIP" "$WORKFLOW"

# --- the fit check: what the map is, and where it lives ----------------------

rs_rule "the map lives in working-rules, and a sensitive area points into it" \
  'the map lives in the areas section of `docs/working-rules\.md`, outside the masterplan; a sensitive area points into it by name'
rs_rule "a sensitive area's line carries no paths" 'the line carries no paths'
rs_rule "the map covers the whole project on every build path" \
  'the map covers the whole project and exists on every build path'
rs_rule "each area is one line" 'each area is one line in the `## areas` section'
rs_rule "an area not yet in the code is none yet" \
  'an area whose folder does not exist yet is written `- <name>: none yet`'
rs_rule "an area name holds no comma and no colon" 'an area name holds no comma and no colon'
rs_rule "at most one sensitive line" 'at most one indented `sensitive: <name>` line'
rs_rule "at most one boundary line" 'at most one indented `boundary:` line names one boundary'
rs_rule "every tracked folder belongs to an area" 'every tracked folder belongs to an area'
rs_rule "nothing is exempt beyond the three" \
  'there is no exempt list beyond hidden top-level folders, root files and `changes/`'
rs_rule "vendored code is listed under an area named for what it is" \
  'a folder the map cannot sensibly own, such as vendored code, is listed under an area named for what it is'
rs_rule "the founding read-back is plain" 'billing is the refund button, and it lives in the billing folder'
rs_rule "Bearer is optional" 'the scan is optional'
rs_rule "Bearer names its licence" 'elastic license 2\.0 and is not open source'
rs_rule "the map moves with the code" 'write the map in the same save as any code move that changes it'
rs_rule "the check names the folder or the line" \
  'turns red, naming the folder or the line, on a folder no area claims'
rs_guard "$FIT" "fit-check.md"
rs_require_absent "the fit check keeps no map on one build path only" "$FIT" \
  'keep this map absent on the other two build paths'

# --- the template every founded project receives -----------------------------

rs_reset
rs_rule "the Areas heading" '## areas <!-- every folder of the project belongs to one named area'
rs_rule "an area line's shape" '`- <name>: <path>, <path>`'
rs_rule "none yet" '`- <name>: none yet`'
rs_rule "the sensitive line's shape" 'indented `sensitive: <name>` line'
rs_rule "the boundary line's shape" 'indented `boundary:` line'
rs_rule "the example carries a sensitive line" ' sensitive: money '
rs_rule "the example carries a boundary line" ' boundary: reached only through src/billing/charge\.ts'
rs_rule "the project records area" '[-] project records: docs/'
rs_guard "$RULES_TEMPLATE" "templates/working-rules.md"

rs_require_absent "the masterplan template carries no paths: line" "$MASTER" 'paths:'
rs_require_absent "the masterplan template carries no none: line" "$MASTER" 'none:'
rs_require_load_bearing "the founded AGENTS.md names the section" "$INSTRUCTIONS" \
  '### areas and sensitive areas'
rs_require_load_bearing "the founded AGENTS.md points at the map" "$INSTRUCTIONS" \
  'the areas section of `docs/working-rules\.md`'
rs_require_absent "the old section name is gone" "$INSTRUCTIONS" '### sensitive areas '

# --- the project check -------------------------------------------------------

rs_require_load_bearing "the project check names the step" "$CHECKS" '[-] name: check the area map'
rs_require_load_bearing "the step's run line guards for Python and runs the check" "$CHECKS" \
  "run: command -v python3 >/dev/null 2>.1 [|][|] [{] echo 'check the area map needs python 3, which this runner does not have\. add a step that installs python 3 before this one\.'; exit 2; [}]; python3 \.agents/tools/area-map\.py check"
rs_require_absent "the old step is gone" "$CHECKS" 'check sensitive-area map'
if [ -e "$FOUNDATION/check-sensitive-areas.sh" ]; then
  rs_fail "the foundation still carries check-sensitive-areas.sh"
fi
rs_ok "the foundation no longer carries check-sensitive-areas.sh"
rs_require_load_bearing "the project-check record names the step" "$PROJECT_CHECK" \
  '`check the area map` and `check the agents\.md ceiling`'
rs_require_absent "the project-check record drops the old step" "$PROJECT_CHECK" \
  'check sensitive-area map'

# --- placing the script and writing the file --------------------------------

rs_require_load_bearing "bootstrap places the script beside the gate" "$BOOTSTRAP" \
  'area-map\.py[|]\.agents/tools/area-map\.py'
rs_require_load_bearing "bootstrap writes docs/working-rules.md" "$BOOTSTRAP" \
  'docs/working-rules\.md'
rs_require_absent "bootstrap no longer installs the old hook" "$BOOTSTRAP" 'check-sensitive-areas'
rs_require_load_bearing "the placement step carries the script" "$PLACE" \
  'area-map\.py[|]\.agents/tools/area-map\.py[|]area map script'

# --- founding ---------------------------------------------------------------

rs_require_load_bearing "founding writes the map on every build path, from code or description" "$SETUP" \
  'write the `## areas` section of `docs/working-rules\.md` on every build path, from the code where code exists and from the masterplan.s own description where none does'
rs_require_load_bearing "founding reads each area back in plain words" "$SETUP" \
  'read each area and its home back in plain words'
rs_require_load_bearing "a whole copy claims agent-plugin" "$SETUP" \
  '`- kit installation: agent-plugin/`'
rs_require_absent "founding no longer leaves the map out on two paths" "$SETUP" \
  'leave the map absent'
rs_require_order "the stand-up comes before the index" "$SETUP" \
  '^## 11\. Stand the project up' 'to Git.s index'
rs_require_order "the index comes before the claim" "$SETUP" \
  'to Git.s index' 'every folder the stand-up created'
rs_require_order "the claim comes before the check" "$SETUP" \
  'every folder the stand-up created' 'Then run `python3 \.agents/tools/area-map\.py check`'
rs_require_order "the check comes before the checkpoint" "$SETUP" \
  'Then run `python3 \.agents/tools/area-map\.py check`' 'When the setup is ready to save, say so before saving'

# --- the piece's area names --------------------------------------------------

rs_require_load_bearing "Boundary is a comma-separated list" "$PIECES" \
  '`boundary:` is a comma-separated list of area names on one line'
rs_require_load_bearing "Reaches entries begin with an area name and a colon" "$PIECES" \
  'each entry under `reaches:` begins with an area name followed by a colon'
rs_require_load_bearing "names are matched whole against the map" "$PIECES" \
  'a name is matched whole, ignoring case and surrounding spaces, against the names `area-map\.py areas` prints'

# --- reading the map in place of the masterplan -------------------------------

rs_require_load_bearing "research maps each hit through the script" "$SHAPE" \
  'map each hit to a named area of the project with `python3 \.agents/tools/area-map\.py which`'
rs_require_load_bearing "research names only areas the map holds" "$SHAPE" \
  'name only areas `area-map\.py areas` prints'
rs_require_absent "research no longer reads areas from the masterplan" "$SHAPE" \
  'taken from the masterplan and the sensitive-area map'
rs_require_load_bearing "the reach check names the area of each part" "$REACH" \
  '`python3 \.agents/tools/area-map\.py which`'
rs_require_order "the builder's review reads the map through the script" "$BUILDER" \
  'run `python3 \.agents/tools/area-map\.py which` on the changed paths' '^## 8\. Save'
rs_require_order "the review step comes before it" "$BUILDER" \
  '^## 7\. Run required review' 'run `python3 \.agents/tools/area-map\.py which` on the changed paths'
rs_require_order "the save step names the shared save" "$BUILDER" \
  '^## 8\. Save' 'A code move and its map change share one save'
rs_require_order "inside the save step" "$BUILDER" \
  'A code move and its map change share one save' '^## 9\. '
rs_require_load_bearing "the builder uses the fixed review line" "$BUILDER" \
  'this change reaches <area>, so a review is running'
rs_require_load_bearing "the builder checks the boundary with the available reader" "$BUILDER" \
  'sentrux or dependency-cruiser'
rs_require_absent "the builder no longer reads the masterplan's map" "$BUILDER" \
  'sensitive-area map in the masterplan'
rs_require_load_bearing "test strength reads the map through the script" "$STRENGTH" \
  'area-map\.py which'
rs_require_absent "test strength no longer reads the masterplan's map" "$STRENGTH" \
  "masterplan's sensitive-area map"
rs_require_load_bearing "the masterplan change count reads the map through the script" "$CHANGES" \
  'area-map\.py which'
rs_require_absent "the masterplan change count drops the old map" "$CHANGES" \
  'use a sensitive-area map where one exists'
rs_require_load_bearing "ship walks the map through the script" "$SHIP" \
  'run `python3 \.agents/tools/area-map\.py check` and walk the `## areas` section of `docs/working-rules\.md`'
rs_require_absent "ship no longer walks masterplan paths" "$SHIP" 'walk its `paths`'

# --- the monthly visit --------------------------------------------------------

rs_require_load_bearing "maintain runs the check on every visit and path" "$MAINTAIN" \
  'run `python3 \.agents/tools/area-map\.py check` on every visit, on every build path'
rs_require_load_bearing "maintain asks before changing the map" "$MAINTAIN" \
  'ask which area each named folder belongs to, and change the map only after the person answers'
rs_require_load_bearing "maintain gives the no-Python line" "$MAINTAIN" \
  'check the area map needs python 3, which this runner does not have\. add a step that installs python 3 before this one\.'
rs_require_absent "maintain drops the old step" "$MAINTAIN" 'sensitive-area check installed during founding'

# --- the documents ------------------------------------------------------------

rs_require_load_bearing "a boundary line sits under its area" "$BOUNDARY" \
  'a boundary line sits under its area in `docs/working-rules\.md`'
rs_require_load_bearing "WORKFLOW says the map covers the whole project" "$WORKFLOW" \
  'the map covers the whole project'
rs_require_load_bearing "WORKFLOW says it exists on every build path" "$WORKFLOW" \
  'it exists on every build path'
rs_require_absent "WORKFLOW drops the one-path map" "$WORKFLOW" 'the map exists only on build with care'

rs_done
