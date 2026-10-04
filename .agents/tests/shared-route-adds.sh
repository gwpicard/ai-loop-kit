#!/usr/bin/env sh
# shared-route-adds.sh: guard the shared installer route, which has to add a
# skill the kit renamed and not only refresh the ones already there.
#
# The kit renamed `plan` to `shape`. A project on the shared route updated
# across that rename with the installer's `update` command, which refreshes
# only what `skills-lock.json` already lists and drops any other name without a
# word. The update removed `plan`, because it had gone upstream, and never
# installed `shape`, because it was not in the lockfile. The project was left
# with no command for shaping a piece, and the version file said it was up to
# date, because the same update that dropped the skill rewrote the version.
#
# Three rules close that. The route is the installer's `add` command, which
# refreshes an installed skill and adds a missing one. The monthly pass counts
# the lockfile against fourteen, since the count is the only sign a skill is
# missing. And each rename migration fires on what is on disk rather than on
# which update this is, with a branch for the state where the old skill is
# gone and the new one never came. The maintain skill carries the rules and
# this check reads them back, because the installer is somebody else's tool and
# nothing here can watch it run.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"
WORKFLOW="$ROOT/WORKFLOW.md"
SCENARIOS="$ROOT/.agents/tests/scenarios.md"

rs_init "Shared-route-adds checks"
rs_exists "$MAINTAIN" "$COMPAT" "$WORKFLOW" "$SCENARIOS"

# The count, and why the version file cannot stand in for it.
rs_rule "the lockfile is counted against the fourteen names" \
  'count its entries against the fourteen names'
rs_rule "because the update that drops a skill also rewrites the version" \
  'the same update that drops a skill rewrites the version'
rs_rule "a matching version alone is not proof" \
  'a matching version alone is not proof'

# The route, and why the other command is not it.
rs_rule "the person picks the agents the project already uses" \
  'choose the same coding agents the project already uses'
rs_rule "universal is what gives the real folder" \
  'choosing .universal. is what puts the real folder'
rs_rule "the installer's update command is refused for the kit" \
  'do not use .npx skills update. for the kit'
rs_rule "because it drops a name it does not know without a word" \
  'drops any other name without a word'
rs_rule "the add route brings in screen-check for an older installation" \
  'same .npx skills add. command added it'
rs_rule "the visit waits until screen-check is present" \
  'carry on only once it is there'

# The migrations fire on the disk, and recover the neither-present state.
rs_rule "the migrations are decided by what is on disk" \
  'decided by what is on disk rather than by which update this is'
rs_rule "the shape migration fires on plan present or shape absent" \
  'finds a .plan. skill installed, or no .shape. skill'
rs_rule "and adds shape when neither is there" \
  'carry on only once .shape. is there'
rs_rule "the setup migration fires on start present or setup absent" \
  'finds a .start. skill installed, or no .setup-ai-build-kit. skill'
rs_rule "and adds setup-ai-build-kit when neither is there" \
  'carry on only once .setup-ai-build-kit. is there'

# The project's own instructions are brought up to the new name, with approval,
# rather than left to the person.
rs_rule "the reason the kit edits a project-owned file" \
  'made to fix it by hand after every rename will stop updating'
rs_rule "plan becomes shape in the command list" \
  'where it names .plan., replace it with .shape.'
rs_rule "queue is added where it is missing" \
  'where .queue. is missing, add it'
rs_rule "the change is shown and applied on approval" \
  'show the change and apply it on approval'
rs_rule "an unrecognised list is left alone and named" \
  'leave the file alone and say which name needs changing'
rs_rule "the shape migration calls it rather than asking the person" \
  'rather than asking the person to do it'
rs_rule "the setup migration calls it too" \
  'so the person is not left to do it'
rs_guard "$MAINTAIN" "the maintain skill"

# The places a person reads about the route say the same thing.
rs_require "COMPATIBILITY.md gives the add command as the route" \
  "$COMPAT" 'npx skills add gwpicard/ai-build-kit'
rs_require "and says why update is not the route" \
  "$COMPAT" 'refreshes only what the lockfile already lists'
rs_require "WORKFLOW.md says an update adds a renamed skill" \
  "$WORKFLOW" 'adds any skill the kit has renamed or added since'
rs_require "the scenario record says update cannot add" \
  "$SCENARIOS" 'cannot add a skill the kit renamed'
rs_require "WORKFLOW.md says a rename rewrites the command list with approval" \
  "$WORKFLOW" 'rewrites the command list in your agents.md, with your approval'

rs_done
