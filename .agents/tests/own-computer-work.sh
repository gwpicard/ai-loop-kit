#!/usr/bin/env sh
# own-computer-work.sh: guard how the kit handles work on the person's own
# computer rather than on the project.
#
# In one project, "fix the gh pr edit thing" led the agent to download a newer
# GitHub CLI and install it into the person's home folder without asking. In
# another, most of a first day went into repairing an editor's install on the
# person's machine: a large download, a rewritten system service, a deleted
# application. None of it went through triage, and the agent wrote facts about
# that machine into the project and opened a pull request with them. The person
# then had to ask what had changed in the repository, and have every trace
# taken out.
#
# The project's own folder is the line, since it is the one boundary an agent
# can check without judgement. change-triage names the intent and routes it
# apart, with no piece, no branch, no changelog entry and nothing written into a
# tracked file. Anything installed, replaced, downloaded to run or removed
# outside the folder waits for a yes naming what, where and how to undo it. The
# founded blocked-commands.md carries that as a standing restriction, since the
# founded AGENTS.md says it always applies and the template sits at its line
# budget. section-builder points to it where a build finds a tool missing, a
# run parks such a piece (the-runner.sh holds that), and WORKFLOW.md tells it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
TRIAGE="$SKILLS/change-triage/SKILL.md"
BLOCKED="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Own-computer-work checks"
rs_exists "$TRIAGE" "$BLOCKED" "$BUILDER" "$WORKFLOW"

# change-triage: the intent, its route, the yes, the requirement and the two
# cases that are not the normal one.
rs_rule "Step 2 names the intent" \
  'setup or operational task; work on this computer outside the project;'
rs_rule "Step 4 lists the route" 'work on this computer, done apart from the project'
rs_rule "the section exists" '### work on this computer outside the project'
rs_rule "the project's folder is the line" 'the project.s own folder is the line'
rs_rule "what counts: software" 'installing, updating, repairing or removing software'
rs_rule "what counts: settings" 'changing system or shell settings'
rs_rule "what counts: files outside the folder" 'tidying files outside the project folder'
rs_rule "no piece, no branch, no changelog entry" \
  'it gets no piece, no branch and no changelog entry'
rs_rule "nothing written into any tracked file" \
  'nothing about it is written into any tracked file of the project'
rs_rule "the person is told in the reply" 'tell the person what was done in your reply'
rs_rule "the project's own dependencies stay project work" \
  'installing the project.s own dependencies inside its folder'
rs_rule "the yes names what, where and how to undo it" \
  'name what it is, where it goes and how to undo it, and wait for a yes'
rs_rule "the yes covers install, replace, download to run and remove" \
  'installed, replaced, downloaded to run, or removed outside the project folder'
rs_rule "in every command, a build included" \
  'this holds in every command, including a build that finds a tool missing or too old'
rs_rule "administrator rights go to the person" \
  'a command that needs administrator rights is given to the person to run'
rs_rule "a recursive delete goes to the person" \
  'a removal that needs a recursive delete is given to the person'
rs_rule "a needed fact goes to the stack section as a requirement" \
  'write it into agents\.md.s stack section as a requirement of the project'
rs_rule "never as a record of the machine" \
  'never write it as a record of what was done to this machine'
rs_rule "a mixed request is two requests" \
  'is two requests, each with exactly one route\. say so in one line'
rs_rule "the computer part is asked for and done apart" \
  'ask about the computer part and do it apart, then triage the project part as usual'
rs_rule "project files touched by accident are named, not committed" \
  'name them to the person and do not commit them'
rs_rule "a setup step outside the folder is computer work, with the yes first" \
  'a setup step that would install, replace or remove software outside the project folder is work on this computer, below, so the yes it needs comes before you do it'
rs_guard "$TRIAGE" "the change-triage skill"

rs_require "triage still gives a request exactly one route" "$TRIAGE" \
  'the request has exactly one route'

# The founded blocked-commands.md, which the founded AGENTS.md says always applies.
rs_reset
rs_rule "never install, replace, download to run, or remove software outside the folder" \
  'never install, replace, download to run, or remove software outside the project folder'
rs_rule "without a yes naming what, where and how to undo it" \
  'without a yes that names what it is, where it goes and how to undo it'
rs_rule "a recursive delete defers to the refused-command rule" \
  'a removal that needs a recursive delete is the person.s to run, as the refused-command rule at the top says'
rs_rule "and change-triage says how it is kept apart" \
  'under "work on this computer outside the project"'
rs_guard "$BLOCKED" "the shipped blocked-commands.md"

rs_require_order "the restriction follows the speaking-for-the-person item" "$BLOCKED" \
  'never post in the person.s name' 'never install, replace, download to run'
rs_require_order "and sits in the standing list, before its closing line" "$BLOCKED" \
  'never install, replace, download to run' '^Save a checkpoint before sweeping work'

# section-builder: where the project's commands first run.
rs_reset
rs_rule "a tool missing or too old stops that step" \
  'shows a tool missing from this computer, or too old, stop that step'
rs_rule "and waits for a yes naming it" \
  'name the tool, where it would go and how to undo it, and wait for a yes'
rs_rule "pointing to change-triage" \
  'as the `change-triage` skill says under "work on this computer outside the project"'
rs_rule "a run parks the piece instead" \
  'in a run with nobody watching, park the piece instead'
rs_guard "$BUILDER" "the section-builder skill"

rs_require_order "the pointer sits in step 4, where the commands first run" "$BUILDER" \
  '^## 4\. Write the checks first' 'shows a tool missing from this computer'
rs_require_order "and before step 5" "$BUILDER" \
  'shows a tool missing from this computer' '^## 5\. Build one vertical slice'

# WORKFLOW.md tells it in Day to day.
rs_reset
rs_rule "work on your own computer is kept apart" \
  'work on your own computer rather than on the tool, such as installing or repairing a program, is kept apart from the project'
rs_rule "nothing installed outside the folder without a yes" \
  'nothing is installed, replaced or removed outside the project.s folder until you have said yes'
rs_rule "nothing about the computer is written into the project" \
  'nothing about your computer is written into the project'
rs_guard "$WORKFLOW" "WORKFLOW.md"

rs_require_order "WORKFLOW.md says it in Day to day" "$WORKFLOW" \
  '^## 5\. Day to day' 'Work on your own computer rather than on the tool'
rs_require_order "and before Evidence" "$WORKFLOW" \
  'Work on your own computer rather than on the tool' '^## 6\. Evidence'

# The founded AGENTS.md sits at its line budget and is not changed for this;
# the restriction reaches every session through blocked-commands.md, which it
# already says always applies. standing-instructions.sh holds the budget.

rs_done
