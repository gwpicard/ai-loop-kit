#!/usr/bin/env sh
# sensitive-area-map.sh: guard the map that ties named areas to live code.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

FIT="$ROOT/.agents/skills/setup-ai-build-kit/references/fit-check.md"
MASTER="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
SHIP="$ROOT/.agents/skills/ship/SKILL.md"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
CHECK="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/check-sensitive-areas.sh"
BOOTSTRAP="$ROOT/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
CHECKS="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Sensitive-area map rules"
rs_exists "$FIT" "$MASTER" "$SETUP" "$BUILDER" "$SHIP" "$MAINTAIN" "$CHECK" "$BOOTSTRAP" "$CHECKS" "$WORKFLOW"

rs_rule "the map exists only on Build with care" 'keep this map absent on the other two build paths'
rs_rule "each area lists paths" 'the next line lists the paths where that area lives'
rs_rule "an area has at most one boundary" 'may name one boundary'
rs_rule "every source folder is assigned or none" 'every top-level source folder is listed under an area or on a `none:` line'
rs_rule "the map moves with the code" 'same save as any code move'
rs_rule "a missing path fails" 'check fails when a listed path has gone'
rs_rule "an unassigned folder fails" 'new top-level source folder has no area or `none` line'
rs_rule "the founding read-back is plain" 'money is the refund button, and it lives in the billing folder'
rs_rule "Bearer is optional" 'the scan is optional'
rs_rule "Bearer names its licence" 'elastic license 2\.0 and is not open source'
rs_guard "$FIT" "fit-check.md"

rs_require "the masterplan carries the map shape" "$MASTER" 'paths:.*boundary:'
rs_require "setup writes and checks the map" "$SETUP" 'sensitive-area check installed by the bootstrap step'
rs_require "the builder compares reach with the map" "$BUILDER" 'compare the reached paths and crossed boundaries'
rs_require "the builder uses the fixed review line" "$BUILDER" 'this change reaches <area>, so a review is running'
rs_require "the builder checks the boundary with the available reader" "$BUILDER" 'sentrux or dependency-cruiser'
rs_require "ship walks the map" "$SHIP" 'walk its `paths`'
rs_require "maintain runs the check monthly" "$MAINTAIN" 'sensitive-area check installed during founding'
rs_require "bootstrap installs the check" "$BOOTSTRAP" 'check-sensitive-areas\.sh\|\.agents/hooks/check-sensitive-areas\.sh'
rs_require "the project check runs the map check" "$CHECKS" 'sh \.agents/hooks/check-sensitive-areas\.sh'
rs_require "WORKFLOW explains the held-shut map" "$WORKFLOW" 'a check keeps that list true'

project="$rs_dir/project"
mkdir -p "$project/.agents/hooks" "$project/src/billing"
cp "$CHECK" "$project/.agents/hooks/check-sensitive-areas.sh"
printf '%s\n' 'export const charge = true' > "$project/src/billing/charge.ts"
printf '%s\n' \
  '# Masterplan' \
  '## Build path' \
  'Path: Build with care' \
  'Sensitive areas:' \
  '  money: refunds; caution: checked; done 2026-09-18' \
  '    paths: src/billing/' \
  '    boundary: reached only through src/billing/charge.ts' \
  > "$project/masterplan.md"

if sh "$project/.agents/hooks/check-sensitive-areas.sh" > "$rs_dir/out" 2>&1; then
  pass=yes
else
  pass=no
fi
rs_report "a current map passes" "$pass"

mv "$project/src/billing" "$project/src/payments"
if sh "$project/.agents/hooks/check-sensitive-areas.sh" > "$rs_dir/out" 2>&1; then
  moved=no
else
  moved=yes
fi
rs_report "a moved listed folder fails" "$moved"
grep -Fq 'src/billing/ is listed but does not exist' "$rs_dir/out" && named=yes || named=no
rs_report "the failure names the moved path" "$named"

sed 's@src/billing/@src/payments/@g' "$project/masterplan.md" > "$rs_dir/masterplan"
cp "$rs_dir/masterplan" "$project/masterplan.md"
mkdir -p "$project/services"
printf '%s\n' 'export const send = true' > "$project/services/send.ts"
if sh "$project/.agents/hooks/check-sensitive-areas.sh" > "$rs_dir/out" 2>&1; then
  unassigned=no
else
  unassigned=yes
fi
rs_report "an unassigned source folder fails" "$unassigned"
grep -Fq 'services is a source folder with no area or none line' "$rs_dir/out" && named=yes || named=no
rs_report "the failure names the unassigned folder" "$named"

sed 's/Path: Build with care/Path: Build and run it/' "$project/masterplan.md" > "$rs_dir/masterplan"
cp "$rs_dir/masterplan" "$project/masterplan.md"
if [ -z "$(sh "$project/.agents/hooks/check-sensitive-areas.sh" 2>&1)" ]; then
  silent=yes
else
  silent=no
fi
rs_report "the check is silent on another build path" "$silent"

rs_done
