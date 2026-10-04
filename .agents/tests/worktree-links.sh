#!/usr/bin/env sh
# worktree-links.sh: guard the ignored build files a run's worktree links, and
# the rule that the kit touches only its own worktrees.
#
# A run builds each piece in a worktree, and until now only the main folder's
# .env files reached it. On a project whose build needs a file git ignores,
# such as a licensed font kept out of the repository, every piece in a run
# failed for want of it. One project copied the fonts into each worktree by
# hand, and in the end committed them. So founding asks once which ignored
# files a build needs and writes them to a `worktree-links` line, and
# worktree.sh links them. The rules that matter are the refusals: a
# confidential folder, an env file, a tracked file, a path outside the project
# and a missing one are never linked, and a link is never a copy.
#
# Separately, people run the kit inside worktrees another tool made. The kit
# must touch only its own, and a run started inside another tool's worktree
# must keep its state and its pieces' worktrees in the main folder.
#
# kit-owns-worktrees-rehearsal.sh runs the script on disk. This check reads
# the written rules back, in running-longer.md, founding, /maintain, the
# maintenance record's header and WORKFLOW.md, and proves each one
# load-bearing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
LONGER="$SKILLS/implement/references/running-longer.md"
SCRIPT="$SKILLS/implement/scripts/worktree.sh"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
RECORD="$SKILLS/setup-ai-build-kit/templates/maintenance-record"
MAINTAIN="$SKILLS/maintain/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Worktree link checks"
rs_exists "$LONGER" "$SCRIPT" "$SETUP" "$RECORD" "$MAINTAIN" "$WORKFLOW"

# running-longer.md: the links, the refusals, and other tools' worktrees.
rs_rule "the worktree-links line lists the ignored build files" \
  'the `worktree-links` line in `\.ai-build-kit-maintenance` lists them'
rs_rule "each is linked as a relative symbolic link, never a copy" \
  'a relative symbolic link, never a copy'
rs_rule "the link's folder is made first where it is missing" \
  'making the link.s folder in the worktree first where it is missing'
rs_rule "a path in or holding a confidential folder is refused" \
  'sits in or holds a folder on a `confidential` line'
rs_rule "an env file is refused" \
  'is named `\.env` or starts with `\.env\.`'
rs_rule "a tracked path is refused" 'is tracked by git'
rs_rule "a path outside the project is refused" 'lies outside the project'
rs_rule "a path missing from the main folder is refused" \
  'or is not in the main folder'
rs_rule "with no line, only the env files are linked" \
  'with no `worktree-links` line, only the `\.env` files are linked'
rs_rule "a piece missing a listed file goes on, flagged" \
  'flag the piece .built without <path>.'
rs_rule "a copy already at a listed path is named and flagged" \
  'where a copy already sits at a listed path, the script names it and leaves it'
rs_rule "a link is never unsaved work" 'a link is never unsaved work'
rs_rule "removal leaves the main folder's file" \
  'removing the worktree leaves the main folder.s file in place'
rs_rule "the kit touches only its own worktrees" \
  'opens, tidies, lists and removes only the worktrees under the main folder.s `\.agents/worktrees/`'
rs_rule "another tool's worktree is never touched" \
  'never touches a worktree another tool made'
rs_rule "the main folder is the first worktree git lists" \
  'the main folder is always the first worktree git lists'
rs_rule "a run started elsewhere keeps its state in the main folder" \
  'keeps its run state in the main folder.s `\.agents/runs/`'
rs_rule "and says where in one line" 'says so in one line when it starts'
rs_rule "a run never checks main out" 'never checks `main` out'
rs_guard "$LONGER" "running-longer.md"

# Every session finds the run in the main folder, wherever it sits.
rs_require_load_bearing "/implement keeps the run state in the main folder" "$SKILLS/implement/SKILL.md" \
  'the run keeps its state in the main folder.s `\.agents/runs/`, the first worktree git lists, even when this session sits in another tool.s worktree'
rs_require_load_bearing "/sync reads the main folder's run state" "$SKILLS/sync/SKILL.md" \
  'read each run.s state file under the main folder.s `\.agents/runs/`'
rs_require_load_bearing "/what-now reads the main folder's run state" "$SKILLS/what-now/SKILL.md" \
  '`\.agents/runs/` of the main folder'
rs_require_load_bearing "running-longer says every session finds the same run" "$LONGER" \
  'always the main folder.s `\.agents/runs/`, the first worktree git lists, even when the session sits in another tool.s worktree'

# The script links the line and lists the candidates founding asks about.
rs_require_load_bearing "worktree.sh reads the worktree-links line" "$SCRIPT" \
  'worktree-links\|'
rs_require_load_bearing "worktree.sh reads the confidential line" "$SCRIPT" \
  'confidential\|'
rs_require_load_bearing "worktree.sh lists the candidates" "$SCRIPT" \
  'candidates\) cmd_candidates'

# Founding, step 11.
rs_require_load_bearing "founding lists the ignored candidates with the script" "$SETUP" \
  'the `implement` skill.s `scripts/worktree\.sh` with `candidates`'
rs_require_load_bearing "founding asks once which a build needs" "$SETUP" \
  'ask once which of them a build or a walk-through needs'
rs_require_load_bearing "the question carries a best guess" "$SETUP" \
  'with your best guess attached'
rs_require_load_bearing "founding writes the confirmed paths" "$SETUP" \
  'write the paths the person confirms to a `worktree-links\|<path> ; <path>` line'
rs_require_load_bearing "founding asks nothing when nothing qualifies" "$SETUP" \
  'where it lists nothing, write no line and ask nothing'
rs_require_load_bearing "the question never ends the turn on its own" "$SETUP" \
  'the question never ends the turn on its own'
rs_require_load_bearing "an unanswered question writes no line" "$SETUP" \
  'where founding ends with no answer, write no line'
rs_require_load_bearing "founding writes the confidential line" "$SETUP" \
  'write `confidential\|<folder>` to `\.ai-build-kit-maintenance`'
rs_require_load_bearing ".worktreeinclude is for Claude Code's own worktrees" "$SETUP" \
  'that list is for claude code.s own worktrees\. the kit.s run worktrees read the `worktree-links` line instead'

# The maintenance record's header names both lines and who writes them. Its
# lines are comments, so a folded line break leaves a `# ` between words.
rs_require_load_bearing "the header names the worktree-links line" "$RECORD" \
  'setup-ai-build-kit writes a (# )?worktree-links (# )?line'
rs_require_load_bearing "the header names the confidential line" "$RECORD" \
  'and a confidential (# )?line (# )?naming (# )?the (# )?confidential (# )?folder'
rs_require_load_bearing "the header names the declined line" "$RECORD" \
  'maintain writes a (# )?worktree-links (# )?line (# )?too, (# )?or (# )?a (# )?worktree-links-declined'

# /maintain: the offer to a project founded before the links.
rs_reset
rs_rule "the monthly visit runs the offer" \
  '19\. run "linking ignored build files into run worktrees" below'
rs_rule "a project with the line hears nothing" \
  'where `\.ai-build-kit-maintenance` already has a `worktree-links` line, say nothing'
rs_rule "the offer lists the candidates with the script" \
  'run `sh <installed implement skill>/scripts/worktree\.sh candidates`'
rs_rule "the confidential folder AGENTS.md records is left out" \
  'leave out the folder agents\.md records as confidential'
rs_rule "an earlier no stands until a new path appears" \
  'where every path it lists is already on a `worktree-links-declined` line, the earlier no stands'
rs_rule "the offer is made once, with a guess" \
  'ask once which of them a build or a walk-through needs, with your best guess attached'
rs_rule "a yes writes the confirmed paths" \
  'on a yes, write the paths the person confirms'
rs_rule "a yes writes the confidential line too" \
  'write the `confidential\|<folder>` line too'
rs_rule "a no is recorded" \
  '`worktree-links-declined\|<yyyy-mm-dd>\|<the paths offered, separated by " ; ">`'
rs_rule "the offer returns only for a new path" \
  'offers again only when a new ignored path appears that the line does not list'
rs_rule "the leftover list leaves other tools' worktrees alone" \
  'it leaves alone every worktree another tool made'
rs_guard "$MAINTAIN" "the maintain skill"
rs_require_order "the offer comes before recording the visit" "$MAINTAIN" \
  '^19\. Run "Linking ignored build files' '^21\. Record the visit'

# WORKFLOW.md tells it.
rs_require_load_bearing "WORKFLOW says ignored build files are linked" "$WORKFLOW" \
  'a file your build needs that git ignores and that holds no secret, such as a licensed font, is linked into each copy'
rs_require_load_bearing "WORKFLOW says other tools' worktrees are left alone" "$WORKFLOW" \
  'the kit never touches a worktree another tool made'

rs_done
