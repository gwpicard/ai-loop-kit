#!/usr/bin/env sh
# kit-owns-worktrees.sh: guard the worktree each piece in a run is built in.
#
# In a real project the person built pieces in worktrees every day, set up by
# hand each time, and the kit said nothing about them. The costs arrived
# anyway: twelve leftover worktrees and over a hundred branches deleted by
# hand, secrets copied into several folders, the main folder left on a feature
# branch, and a forced removal that only Claude Code's own guard stopped.
#
# So the kit owns each worktree from the moment it opens to the moment it is
# cleared away, and the rules live in running-longer.md. The script that does
# the work is rehearsed in kit-owns-worktrees-rehearsal.sh. This check reads
# the rules back and proves each one load-bearing, and holds the places that
# point at them: section-builder's safe start, /implement, /sync, /maintain,
# the foundation's .gitignore, the blocked commands and WORKFLOW.md.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
LONGER="$SKILLS/implement/references/running-longer.md"
IMPLEMENT="$SKILLS/implement/SKILL.md"
SCRIPT="$SKILLS/implement/scripts/worktree.sh"
BUILDER="$SKILLS/section-builder/SKILL.md"
SYNC="$SKILLS/sync/SKILL.md"
MAINTAIN="$SKILLS/maintain/SKILL.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
TEMPLATE="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
IGNORE="$SKILLS/setup-ai-build-kit/templates/foundation/gitignore"
BLOCKED="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
TOOLING="$SKILLS/setup-ai-build-kit/scripts/check-tooling.sh"
WORKFLOW="$ROOT/WORKFLOW.md"
COMPAT="$ROOT/docs/COMPATIBILITY.md"

rs_init "Worktree checks"
rs_exists "$LONGER" "$IMPLEMENT" "$SCRIPT" "$BUILDER" "$SYNC" "$MAINTAIN" \
  "$SETUP" "$TEMPLATE" "$IGNORE" "$BLOCKED" "$TOOLING" "$WORKFLOW" "$COMPAT"

# Who gets a worktree, and the main folder that never moves.
rs_rule "on Claude Code each piece in a run has its own worktree" \
  'on claude code, each piece in a run is built in its own worktree'
rs_rule "a run never switches the main folder's branch" \
  'a run never switches the main folder to a piece.s branch'
rs_rule "other coding agents keep one checkout" \
  'on any other coding agent, or where git is older than 2\.17, the first with `git worktree remove`, a run works in one checkout'
rs_rule "cutting a worktree checks nothing out in the main folder" \
  'nothing here checks out a branch in the main folder'

# Where it lives, and git ignoring it.
rs_rule "the path is named after the piece" \
  '`\.agents/worktrees/<issue number>-<short name>`, on the piece.s branch'
rs_rule "the folder ignores itself where .gitignore has no line" \
  'writes a `\.gitignore` holding `\*` inside `\.agents/worktrees/`, so git ignores the folder'
rs_rule "a harness's own worktree folder is left alone" \
  'a harness.s own worktree folder, such as `\.claude/worktrees/`, is left alone'
rs_rule "the parts of a parent share one worktree" \
  'the parts of one parent\*\* share the parent.s worktree'
rs_rule "the checkpoint route gets no worktree" \
  'the checkpoint route\*\* gets no worktree'

# The .env link.
rs_rule "the .env is a link, never a copy" \
  'the worktree.s `\.env` is a link to the main folder.s `\.env` rather than a copy'
rs_rule "with no .env nothing is linked" \
  'with no `\.env` in the main folder, nothing is linked'
rs_rule "a link that cannot be made means no secrets, said once" \
  'where the link cannot be made on this system, the piece runs without secrets: say so once'
rs_rule "and anything needing a key is flagged" \
  'flag each part of it that needs a key'
rs_rule "never copy the file instead" 'never copy the file instead'

# Dependencies, the port and the hand-over.
rs_rule "dependencies install before the start ritual" \
  'before the start ritual, install them inside the worktree with the install command agents\.md.s stack section records'
rs_rule "a dev server takes a free port" \
  'a dev server started for the piece listens on a free port'
rs_rule "the port is recorded in the run state" 'record it as `port` in the run state'
rs_rule "the walk-through and hand-over name the address" \
  'name that address in the walk-through and the hand-over'
rs_rule "the state file carries the worktree" '"worktree": "\.agents/worktrees/12-invoice-list"'
rs_rule "the state file carries the port" '"port": 4012'
rs_rule "the report says how to start a stopped server again" \
  'say how to start it again rather than give an address'
rs_rule "the server runs until the hand-over and stops at the pull request" \
  'the server keeps running until the hand-over is given, and stops when the piece.s pull request opens'
rs_rule "the checkpoint route needs the main folder on main" \
  'where it is on another branch, the piece stops with that reason'
rs_rule "an ignored real file is unsaved" \
  'a file git ignores counts as unsaved too when it is a real file rather than a link and sits outside a dependency or build folder'
rs_rule "a .env only in a subfolder is named" \
  'a `\.env` found only in a subfolder is named rather than linked'
rs_rule "a copy already there is named and flagged" \
  'where a copy already sits in the worktree, the script names it and leaves it, and the piece is flagged'
rs_rule "the end of a run keeps a worktree holding unsaved work" \
  'a worktree still holding unsaved work is kept, and the report names it with what is unsaved'

# The cases that are not the normal one.
rs_rule "an existing path is reused only on the same branch with nothing unsaved" \
  'reuses it only when it is on the same branch and holds no unsaved work'
rs_rule "otherwise the run names it and skips the piece" \
  'otherwise it names the path and the reason, and the run skips that piece'
rs_rule "a full disk stops the run at the next piece" \
  'fails because the disk is full, the run stops at the next piece'
rs_rule "and the report gives the reason" 'gives the reason in the report'

# The run state never moves into a worktree.
rs_rule "the run state stays in the main folder" \
  'writes `state\.json` and `progress\.md` to the main folder.s `\.agents/runs/`, never inside a worktree'

# What unsaved work is, and clearing a worktree away.
rs_rule "no unsaved work: no uncommitted change" \
  'a worktree holds no unsaved work when it has no uncommitted change'
rs_rule "and no commit only this computer holds" 'no commit that only this computer holds'
rs_rule "a closed pull request clears the worktree at the next run or sync" \
  'when a piece.s pull request has merged or closed, its worktree is removed at the next run.s start or the next `/sync`'
rs_rule "only when it holds no unsaved work" \
  'it removes a worktree only when it holds no unsaved work'
rs_rule "unsaved work is kept and named" \
  'a worktree holding unsaved work is kept, and named with what is unsaved'
rs_rule "an unfinished run's worktree is never touched" \
  'it never touches a worktree an unfinished run is still building'
rs_rule "removal is never forced" 'removal uses `git worktree remove` without force'
rs_rule "removing a worktree never removes the main .env" \
  'takes away the worktree.s link to `\.env` and leaves the main `\.env` alone'
rs_rule "and never deletes a branch" 'it deletes no branch'
rs_rule "leftovers go to /maintain" \
  'is listed by `/maintain`, which removes each on a yes'
rs_rule "a run clears the worktrees of pieces it let go" \
  'remove the worktree this run opened for each piece it kicked back, gave back or skipped'
rs_rule "a piece in to check keeps its worktree" \
  'keeps its worktree until its pull request closes'
rs_rule "a run's start clears closed worktrees" \
  'on claude code, clear away the worktrees whose pull requests have closed'
rs_rule "a resumed piece reuses its worktree" \
  'open its worktree again with `worktree\.sh open --resume`, which reuses the one already there'
rs_rule "uncommitted work left by a dead session is kept and the piece kicked back" \
  'where that worktree holds an uncommitted change, the script keeps it as it is: kick the piece back'

# Outside a run.
rs_rule "a single /implement stays in the main folder unless asked" \
  'a single `/implement` outside a run works in the main folder, as always, unless the person asks for a worktree'
rs_guard "$LONGER" "running-longer.md"

# The script the rules name is there, and removes nothing by force.
rs_require_load_bearing "running-longer.md names the script" "$LONGER" \
  'the `implement` skill.s `scripts/worktree\.sh`'
if grep -nE 'worktree remove[^#]*(--force|[[:space:]]-f([[:space:]]|$))' "$SCRIPT" >/dev/null 2>&1; then
  rs_fail "worktree.sh forces a removal"
fi
rs_ok "worktree.sh never forces a removal"

# section-builder's safe start, which the validator also holds.
rs_require_load_bearing "section-builder starts a piece in a run in its own worktree" "$BUILDER" \
  'on claude code, a piece in a run starts in its own worktree under `\.agents/worktrees/`'
rs_require_load_bearing "section-builder installs dependencies before the start ritual" "$BUILDER" \
  'with its dependencies installed there before its start ritual'
rs_require_load_bearing "section-builder never switches the main folder" "$BUILDER" \
  'the main folder is never switched to the piece.s branch'
rs_require_load_bearing "a stacked piece gets a worktree of its own" "$BUILDER" \
  'starts from that piece.s branch, in a worktree of its own on claude code'
rs_require_load_bearing "the hand-over names the port" "$BUILDER" \
  'the hand-over names that port and that worktree'
# Walk-through pictures go to the main folder, so a worktree whose only
# ignored content was a walk-through is still cleared away. The rehearsal runs
# the lookup these lines name; here they are read back.
rs_require_load_bearing "the walk-through finds the main folder from the porcelain list" "$BUILDER" \
  "find the main folder with this command: \`git worktree list --porcelain \| sed -n '1s/\^worktree //p'\`"
rs_require_load_bearing "that first worktree line is always the main folder" "$BUILDER" \
  'the first `worktree` line, which is always the main folder'
rs_require_load_bearing "the walk-through folder is created when missing" "$BUILDER" \
  'create that folder where it does not exist yet'
rs_require_load_bearing "the hand-over names the full path of the pictures" "$BUILDER" \
  'where the screenshots are, given as the full path of the walk-through folder in the main folder'

# /implement, /sync and /maintain.
rs_require_load_bearing "/implement says a run builds each piece in a worktree" "$IMPLEMENT" \
  'each piece in a run is built in its own worktree under `\.agents/worktrees/`'
rs_require_load_bearing "/implement keeps a single build in the main folder" "$IMPLEMENT" \
  'outside a run, a single piece is built in the main folder, as always, unless the person asks for a worktree'
rs_require_load_bearing "/sync clears worktrees whose pull request closed" "$SYNC" \
  'clear away each one whose pull request has merged or closed, with `sh <installed implement skill>/scripts/worktree\.sh tidy`'
rs_require_load_bearing "/sync passes on a kept worktree" "$SYNC" \
  'a worktree holding unsaved work is kept and named'
rs_require_load_bearing "the monthly visit runs the leftover step" "$MAINTAIN" \
  '18\. run "removing leftover worktrees" below'
rs_require_order "the leftover step comes before recording the visit" "$MAINTAIN" \
  '^18\. Run "Removing leftover worktrees"' '^21\. Record the visit'
rs_require_load_bearing "/maintain lists leftovers" "$MAINTAIN" \
  'worktree\.sh leftovers'
rs_require_load_bearing "/maintain removes each on a yes" "$MAINTAIN" \
  'on a yes to a worktree, remove it with `worktree\.sh remove <path>`'
rs_require_load_bearing "/maintain never forces a removal" "$MAINTAIN" \
  'it uses `git worktree remove` and never forces it'
rs_require_load_bearing "/maintain keeps a worktree holding unsaved work" "$MAINTAIN" \
  'never remove a worktree that holds unsaved work'
rs_require_load_bearing "/maintain offers git worktree prune on a yes" "$MAINTAIN" \
  'offer to run `git worktree prune`, which clears only that record\. run it on a yes'
rs_require_load_bearing "/maintain lists a worktree on no branch" "$MAINTAIN" \
  'or that is on no branch, and that no unfinished run is still building'
rs_require_load_bearing "/maintain never removes a branch here" "$MAINTAIN" \
  'never remove a branch here'

# Founding: the ignore line, the install command, and the git version.
rs_require "the foundation .gitignore ignores the worktrees" "$IGNORE" '\.agents/worktrees/'
rs_require_load_bearing "a run's worktrees do not carry the confidential folder" "$SETUP" \
  'the worktrees the kit opens for a run do not carry that folder, so a piece that needs those files is built with the person present'
rs_require_load_bearing "founding records the install command" "$SETUP" \
  'name the install command among them'
rs_require "the stack section asks for the install command" "$TEMPLATE" \
  'then install, run, test, type check and lint commands'
rs_require_load_bearing "the tooling report names an older Git" "$TOOLING" \
  'older than 2\.17: a run cannot give each piece its own worktree'

# Forced removal stays off limits.
rs_require_load_bearing "the blocked commands refuse a forced worktree removal" "$BLOCKED" \
  'never remove a worktree by force, with `git worktree remove --force`'

# WORKFLOW.md and the compatibility page tell it.
rs_require_load_bearing "WORKFLOW says each piece in a run gets its own copy" "$WORKFLOW" \
  'each piece in a run is built in its own copy of the project'
rs_require_load_bearing "WORKFLOW says the kit clears a copy away" "$WORKFLOW" \
  'the kit clears a copy away once its pull request has merged or closed'
rs_require_load_bearing "WORKFLOW says /maintain removes leftovers on a yes" "$WORKFLOW" \
  '/maintain also lists any worktree a run left behind'
rs_require_load_bearing "the compatibility page keeps other agents on one folder" "$COMPAT" \
  'a run there builds its pieces one after another in one folder'

rs_done
