#!/usr/bin/env sh
# the-runner.sh: guard how /implement runs a plan of ready pieces with nobody
# watching.
#
# In a real project the person built several pieces at a time in almost every
# session, often overnight. The kit's route for that allowed only pieces a
# machine could prove, on one branch and one pull request, and only after three
# clean pieces. So the agent built its own loop four times, with its rules and
# its state in temporary files and memory notes. Twice it skipped the gate on
# which pieces a run may take, once building a piece that touched personal data
# overnight, and resuming a dead session depended on what the agent remembered.
#
# So the run is written down: which pieces it may take, the steps each piece
# goes through in order, the state file a new session resumes from, and the
# report it ends with. A machine cannot watch a run without paying a model, and
# the replay of one is a separate rehearsal, so this check reads the rules back
# and proves each one load-bearing. The per-piece steps are also held in order,
# since a claim made after the build is no claim at all.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
LONGER="$SKILLS/implement/references/running-longer.md"
IMPLEMENT="$SKILLS/implement/SKILL.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
WHATNOW="$SKILLS/what-now/SKILL.md"
SYNC="$SKILLS/sync/SKILL.md"
EVIDENCE="$SKILLS/ship/references/evidence-run.md"
IGNORE="$SKILLS/setup-ai-build-kit/templates/foundation/gitignore"
VALIDATE="$ROOT/.agents/tools/validate-kit.sh"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Runner checks"
rs_exists "$LONGER" "$IMPLEMENT" "$BUILDER" "$WHATNOW" "$SYNC" "$EVIDENCE" \
  "$IGNORE" "$VALIDATE" "$WORKFLOW"

# How a run starts, and which pieces it may take. Eligibility is per piece; the
# three-clean-pieces rule is gone.
rs_rule "several numbers or queue runs a plan" 'loaded when `/implement` is given several issue numbers, or `queue`'
rs_rule "auto is another name for queue" '`auto` is another name for `queue`'
rs_rule "eligibility is per piece, never earned" 'eligibility is decided piece by piece, never earned by the project'
rs_rule "an eligible piece passed the readiness check" 'a `## readiness` section whose first line says ready'
rs_rule "no waiting-on-you step other than try it" 'no `## waiting on you` step other than `try it`'
rs_rule "a sensitive area needs a recorded acceptance" 'unless that area carries an `accepted:` line covering it'
rs_rule "a sensitive piece without one is never taken" 'a piece in a sensitive area without a recorded acceptance is never taken'
rs_rule "a run never accepts for the person" 'a run never writes an acceptance on the person.s behalf'
rs_rule "explore privately takes only disposable work" 'on explore privately, a run takes only disposable work'
rs_rule "a piece with no readiness section is checked before the claim" 'run the readiness check on it before claiming it'
rs_rule "not ready sends it back to shaping" 'not ready sends it back to shaping with each blocking gap written on it'
rs_rule "an opted-in piece stops at to check" 'stops at `to check` with a line in its pull request saying it waits for the person.s try'
rs_rule "an opted-in piece is never merged under pre-approval" 'and it is never merged under pre-approval'
rs_rule "pre-approval is asked once, before the run" 'then ask once whether pieces that pass may be merged during the run'

# The state file a new session resumes from.
rs_rule "the run folder" '`\.agents/runs/<run name>/`'
rs_rule "the folder ignores itself in an older project" 'so the folder ignores itself'
rs_rule "the state file is what a new session resumes from" '`state\.json` is the record a new session resumes from'
rs_rule "field: merge_preapproved" '"merge_preapproved": false'
rs_rule "field: state" '"state": "to check"'
rs_rule "field: branch" '"branch": "12-invoice-list"'
rs_rule "field: pull request" '"pull_request": 31'
rs_rule "field: attempts" '"attempts": 1'
rs_rule "field: flags" '"flags": \['
rs_rule "merge_preapproved is the answer before the run" '`merge_preapproved` is the person.s answer before the run'
rs_rule "the states a piece can hold in a run" '`state` is one of `waiting` \(not started\), `building`, `to check`, `merged`, `parked`, `shaping`'
rs_rule "the reason names the merge condition failed" 'naming the condition it failed in the `section-builder` skill.s `references/merge\.md`'
rs_rule "the state is written after every step" 'write the state file after every step that changes a piece, before the next step starts'
rs_rule "progress.md is a short log" '`progress\.md`, beside it, is a short log'
rs_rule "a live page is published from the state file" 'publish a live progress page from the state file'
rs_rule "an unpublished page is said once and the run carries on" 'where the page cannot be published, say so once, and carry on with the state file as the record'

# Each piece's steps, in order.
rs_rule "step: claim it" '1\. \*\*claim it\.\*\*'
rs_rule "step: branch it" '2\. \*\*branch it\.\*\*'
rs_rule "step: the start ritual" '3\. \*\*run the start ritual\.\*\*'
rs_rule "step: checks first" '4\. \*\*write the checks first\*\*'
rs_rule "step: build" '5\. \*\*build it\*\*'
rs_rule "step: walk-through" '6\. \*\*walk through it\*\*'
rs_rule "step: independent review" '7\. \*\*run the independent review\*\*'
rs_rule "step: open its pull request" '8\. \*\*open its pull request\*\*'
rs_rule "step: its changelog file" '9\. \*\*write its changelog file\*\*'
rs_rule "step: to check" '10\. \*\*move it to `to check`\.\*\*'
rs_rule "step: update the run state" '11\. \*\*update the run state\*\*'
rs_rule "the ritual reads the state, starts the tool and runs a smoke check" 'read the run state, start the tool, and run a smoke check'
rs_rule "the ritual confirms Relies on still holds" 'confirm each of the piece.s relies on lines still holds'

# The claim, and two runs at once.
rs_rule "the claim refuses a piece already building" 'a piece that already carries `building` is being built somewhere else: the claim refuses it'
rs_rule "the claim is read back" 'then read the claim back'
rs_rule "another claim makes the run back off" 'back off that piece'
rs_rule "a piece that cannot be claimed is never started" 'a piece that cannot be claimed is never started'

# Stacks and parts.
rs_rule "a dependent piece stacks on the branch it depends on" 'stacks on it\. its branch is cut from that piece.s branch'
rs_rule "a stacked pull request names the merge order" 'the pull request says which to merge first'
rs_rule "the parts of one parent share a pull request" 'the parts of one parent share one branch and one pull request'

# An open choice, split by how hard it is to undo.
rs_rule "a hard choice stops the piece" 'a hard choice, about the shape of stored data, how records sync, or what leaves the tool, stops that piece'
rs_rule "an easy choice takes the most reversible option" 'takes the most reversible option'
rs_rule "a flagged piece is never merged under pre-approval" 'a flagged piece is never merged under pre-approval'
rs_rule "either way the run moves on" 'either way the run moves on to the next unblocked piece'

# A hard choice the run can see before it claims a piece. Judged not
# self-sufficient, such a piece was skipped and left ready, so every later run
# planned it and skipped it again, and nothing on it told the person a question
# was waiting. It goes back to shaping instead, as one met while building does.
rs_rule "a hard choice seen at the plan or the claim goes back to shaping" 'where the run can see one when it plans or claims a piece, send it back to shaping before claiming it'
rs_rule "the plan-time send-back takes ready off" 'with no claim to undo: `gh issue edit <number> --add-label shaping --add-label needs-clarification --remove-label ready`'
rs_rule "no branch and no claim for a piece sent back at the plan" 'cut no branch and write no claim, since nothing was built'
rs_rule "the plan names it as going back, with its question" 'the plan names it as going back, with its question'
rs_rule "an easy choice at the plan leaves the piece eligible" 'an easy open choice seen at the plan leaves the piece eligible'
rs_rule "a missing fact alone is still skipped and stays ready" 'with no open choice in it, is skipped with the reason and stays `ready`'
rs_rule "a hard choice wins over a missing fact" 'the hard choice wins, and it goes back to shaping'
rs_rule "the claim step sends a visible hard choice back" 'a piece whose text shows a hard open choice goes back to shaping unclaimed'

# Failure, and a blocking failure.
rs_rule "three failed attempts park the piece" 'after the third, park it'
# A piece whose build needs software installed on this computer, outside the
# project folder, waits for a yes nobody is there to give in a run. Installing
# it anyway is how a person's machine got changed without a word.
rs_rule "a piece needing software outside the project is parked" 'a piece whose build needs software installed outside the project folder is parked with that reason'
rs_rule "and the run never installs it" 'the run never installs it, since nobody is there to say yes, and takes the next piece'
rs_rule "one missing tool that stops every piece left ends the run" 'where the same missing tool would stop every piece left, it is a blocking failure'
rs_rule "a blocking failure stops only what relies on it" 'a blocking failure never stops the whole run unless it touches something every later piece relies on'

# Resuming, and the end of the run.
rs_rule "a new session resumes from the state file" 'a new session resumes from the state file, never from memory'
rs_rule "a piece left building continues from its last commit" 'continues from its last commit'
rs_rule "resuming keeps the run's pre-approval" 'resuming is the same run, so its `merge_preapproved` stands'
rs_rule "/sync removes a finished run's folder" '`/sync` removes a run.s folder once every piece in it is merged, closed or parked'
rs_rule "the run never idles when nothing is left" 'the run ends at once with its report, and never waits'
rs_rule "the report leads with what was parked" 'what was parked and why'
rs_rule "the report gives each pull request in merge order" 'each piece with its pull request and its state, in the merge order'
rs_rule "the report gives each flagged choice" 'under each piece, its flagged choices'
rs_rule "the report names the condition a piece failed" 'the merge condition it failed, in the words of'

# What review of the first draft found. Each is a way a run could go wrong
# quietly: a stack that never forms, a race nobody wins, a run that ends with
# pieces stranded in `building`, a parent whose pull request never opens, and
# pre-approved merges that never happen because the check was still running.
rs_rule "the plan takes held-up pieces whose blockers are all in it" 'the plan also takes each piece under `held up` whose open blockers are all in the same plan'
rs_rule "the earliest claim comment wins" 'the earliest `claimed by run` comment on the piece wins'
rs_rule "the later claimant deletes its own comment" 'delete this run.s own comment'
rs_rule "only the later claimant backs off" 'only the later claimant backs off, so a piece is never left `building` with no run behind it'
rs_rule "the run name carries seconds" '`<yyyy-mm-dd>-<hhmmss>`'
rs_rule "the page's reach is said and can be declined" 'publishes the pieces. titles and progress to the coding agent.s page service, and offer to run without it'
rs_rule "pre-approval carries into a resumed run" 'carries into the run when it is resumed'
rs_rule "a resumed run reuses an open pull request" 'look first for a pull request already open from its branch'
rs_rule "the checkpoint route in a run" 'steps 8 to 10 become the checkpoint commit and closing the piece'
rs_rule "a stacked smoke failure skips only the unbuilt pieces" 'skips only the pieces on that stack not yet built'
rs_rule "a built base stays in to check" 'a base already built stays in `to check`'
rs_rule "a squash-merged base is taken in at the merge, never rebased" 'takes in `main` at its own merge, as the `section-builder` skill.s `references/merge\.md` describes, never by a rebase'
rs_rule "a stacked piece whose base goes back is skipped" 'a stacked piece whose base goes back to shaping, or is parked, is skipped'
rs_rule "a parent's pull request opens after its last finished part" 'the pull request opens after the last part that finishes its build'
rs_rule "a finished part waits for the parent's pull request" 'waits in `building` with the reason `waiting for the parent.s pull request`'
rs_rule "the parts' changelog files follow the pull request" 'each part.s changelog file is written once it opens'
rs_rule "no finished part, no pull request" 'where no part finishes, nothing opens'
rs_rule "a piece sent back loses the run's assignee" 'needs-clarification --remove-label building --remove-assignee'
rs_rule "a sent-back piece's branch is pushed" 'push the branch and keep it'
rs_rule "a parked piece loses the run's assignee" '<number> --add-label parked --remove-label building --remove-assignee'
rs_rule "a sensitive area stops the piece, not the run" 'the run goes on; only that piece stops'
rs_rule "a goal mode stops the piece, never the run" 'stops the piece that touches it, never the run'
rs_rule "every way a run ends leaves final states" 'however it ends, whether it ran out of pieces, the smoke check failed on `main`, github could not be reached, or the build path would change'
rs_rule "waiting pieces become skipped at the end" 'every `waiting` piece becomes `skipped`, with the reason the run ended'
rs_rule "an unbuilt piece in hand goes back to ready" 'where nothing was built on it yet, move it back to `ready`'
rs_rule "a built piece in hand is parked" 'where something was built, push the branch and park it with the reason'
rs_rule "a finished run is never offered for resuming" 'a run whose every piece is in a final state is finished, and is never offered for resuming'
rs_rule "two unfinished runs: the newest is offered" 'where two runs are unfinished, offer the newest and name the other'
rs_rule "pre-approved merges are swept at the end, bases first" 'sweep the pieces in `to check` before the report, bases first'
rs_rule "the sweep merges only what meets all six" 'meets all six conditions'
rs_guard "$LONGER" "running-longer.md"

rs_require_order "the claim comes before the branch" "$LONGER" '^1\. \*\*Claim it' '^2\. \*\*Branch it'
rs_require_order "the branch comes before the start ritual" "$LONGER" '^2\. \*\*Branch it' '^3\. \*\*Run the start ritual'
rs_require_order "the ritual comes before the checks" "$LONGER" '^3\. \*\*Run the start ritual' '^4\. \*\*Write the checks first'
rs_require_order "the checks come before the build" "$LONGER" '^4\. \*\*Write the checks first' '^5\. \*\*Build it'
rs_require_order "the build comes before the walk-through" "$LONGER" '^5\. \*\*Build it' '^6\. \*\*Walk through it'
rs_require_order "the walk-through comes before the review" "$LONGER" '^6\. \*\*Walk through it' '^7\. \*\*Run the independent review'
rs_require_order "the review comes before the pull request" "$LONGER" '^7\. \*\*Run the independent review' '^8\. \*\*Open its pull request'
rs_require_order "the pull request comes before the changelog file" "$LONGER" '^8\. \*\*Open its pull request' '^9\. \*\*Write its changelog file'
rs_require_order "the changelog file comes before to check" "$LONGER" '^9\. \*\*Write its changelog file' '^10\. \*\*Move it to'
rs_require_order "to check comes before the state update" "$LONGER" '^10\. \*\*Move it to' '^11\. \*\*Update the run state'

# The old route is gone.
rs_require_absent "running-longer.md no longer earns a run after three pieces" "$LONGER" 'three normal pieces'
rs_require_absent "a run no longer ends as one pull request" "$LONGER" 'ends as one pull request'
rs_require_absent "/implement no longer earns a run after three pieces" "$IMPLEMENT" 'three normal pieces'
rs_require_absent "/implement no longer calls a run earned" "$IMPLEMENT" 'it is earned, not default'
rs_require_absent "WORKFLOW no longer earns a run after three pieces" "$WORKFLOW" 'three normal pieces'
rs_require_absent "the evidence run no longer belongs to implement auto" "$EVIDENCE" 'implement auto'

# /implement starts a run and resumes one.
rs_require_load_bearing "/implement runs several numbers or queue as a plan" "$IMPLEMENT" \
  'given several issue numbers, or `queue`, this command runs them as a plan'
rs_require_load_bearing "/implement loads the run's rules" "$IMPLEMENT" \
  'load `references/running-longer\.md` before the run starts and follow it'
rs_require_load_bearing "/implement offers to resume an unfinished run" "$IMPLEMENT" \
  'where an unfinished run.s state file is in `\.agents/runs/`, offer to resume it'

# section-builder starts a stacked piece from the branch it stacks on, and the
# validator holds the same wording.
rs_require_load_bearing "section-builder allows a stacked start in a run" "$BUILDER" \
  'a piece in a run that stacks on another piece built in that run and not yet merged starts from that piece.s branch'
rs_require_load_bearing "section-builder points at the run" "$BUILDER" \
  'the `implement` skill.s `references/running-longer\.md`'
rs_require "the validator's step 1 assertion names the stacked start" "$VALIDATE" \
  'grep -qf "a piece in a run that stacks on another piece built in that run'

# /what-now and /sync offer to resume, and /sync tidies a finished run.
rs_require_load_bearing "/what-now reads the run state" "$WHATNOW" 'a run.s state file in `\.agents/runs/`'
rs_require_load_bearing "/what-now offers to resume an unfinished run" "$WHATNOW" '### an unfinished run'
rs_require_load_bearing "/sync offers to resume an unfinished run" "$SYNC" 'an unfinished run in `\.agents/runs/`'
rs_require_load_bearing "/sync removes a finished run's folder" "$SYNC" 'remove the folder of a run whose every piece is merged, closed or parked'

# A founded project ignores the run folder.
rs_require "the foundation gitignore ignores the run folder" "$IGNORE" '\.agents/runs/'

# WORKFLOW.md tells it.
rs_require_load_bearing "WORKFLOW says a run gives each piece its own pull request" "$WORKFLOW" \
  'each piece arrives as its own pull request'
rs_require_load_bearing "WORKFLOW says a new session picks the run up" "$WORKFLOW" \
  'a new session picks the run up from its state file'
rs_require_load_bearing "WORKFLOW says a sensitive piece is never taken without an acceptance" "$WORKFLOW" \
  'a piece in a sensitive area is taken only once your acceptance is on the record'
rs_require_load_bearing "WORKFLOW says a goal mode stops only the piece" "$WORKFLOW" \
  'a named sensitive area stops the piece that touches it, never the run'
rs_require_absent "WORKFLOW no longer calls autonomy earned" "$WORKFLOW" 'autonomy is earned'
rs_require_load_bearing "WORKFLOW says a hard choice seen before the build goes back first" "$WORKFLOW" \
  'a hard choice the run can already see in a piece sends it back the same way before any branch is cut'
rs_require_load_bearing "/implement says the run sends it back whether seen at the plan or met while building" "$IMPLEMENT" \
  'a hard open choice, seen at the plan or met while building, sends a piece back to shaping'

rs_done
