#!/usr/bin/env sh
# first-upload-asks.sh: guard the yes the project's first upload waits for.
#
# Founding tells the person nothing will be uploaded, and that is true of
# founding. In a real run the first piece built afterwards then pushed the
# whole project to GitHub with no question, straight after the person had
# heard that nothing was uploaded. So the first push of a project's code asks
# first, naming the repository and whether it is public or private, and it asks
# once for each project.
#
# "Once" is read off the remote rather than kept in a record: the code is
# online only when a remote branch shares history with the local main. A
# listing that failed is never read as an empty repository. A record could disagree
# with the remote, and the remote is what the question is about.
#
# Each rule here is prose an agent reads. Its absence would not show until the
# next first build uploaded a project nobody agreed to put online.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

BUILDER="$ROOT/.agents/skills/section-builder/SKILL.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
SYNC="$ROOT/.agents/skills/sync/SKILL.md"
SHIP="$ROOT/.agents/skills/ship/SKILL.md"
SHAPE="$ROOT/.agents/skills/shape/SKILL.md"
BLOCKED="$ROOT/.agents/skills/setup-ai-build-kit/references/blocked-commands.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "First upload checks"
rs_exists "$BUILDER" "$SETUP" "$SYNC" "$SHIP" "$SHAPE" "$BLOCKED" "$WORKFLOW"

# The ask, and when it is due.
rs_rule "the first push waits for a yes" 'the first push of the project.s code waits for their yes'
# A project founded from a whole copy of the kit can still point at the kit.
rs_rule "origin is checked first" 'before any push, check where `origin` points'
rs_rule "a project never goes to the kit's own repository" 'where it is the kit.s own repository, `gwpicard/ai-build-kit`, push nothing: say plainly that the project still points at the kit.s repository, and ask for their own\. never push a project there'
# A listing that failed must never read as an empty repository.
rs_rule "the listing is read by its exit code" 'run `git ls-remote --exit-code --heads origin` and read its exit code'
rs_rule "exit 2 means the first upload" 'exit 2 means the repository has no branch: nothing from this project is online yet, and this push is the first upload'
rs_rule "any other failure is the route that cannot run, never empty" 'any exit other than 0 or 2 means the listing could not be read, because there is no `origin`, github cannot be reached, or the tool is not signed in\. that is the route the project cannot perform right now, with its one-line note, and never an empty repository'
# A branch on the remote is not enough: it has to be this project's history.
rs_rule "branches count only when they share history with main" 'the code is already online only when a remote branch shares history with the local `main`, so that `git merge-base` finds a commit they share\. then push without asking'
rs_rule "unrelated branches push nothing and ask" 'where the repository has branches but none shares history with `main`, push nothing'
rs_rule "the person is told it holds something else" 'name `owner/name`, say it holds something else, and ask the person what to do'
# How "once" is known.
rs_rule "once for each project, known from the remote, with no record" 'that is how you know the question was answered: it is asked once for each project, and no record is kept'
rs_rule "an empty remote earns no unreachable note" 'a remote with nothing on it has no `main` to bring up to date, and that needs no note'

# The build finishes; only the push waits.
rs_rule "the piece is still built and checked" 'build and check the piece first\. only the push waits'
rs_rule "the ask names the upload" 'ask for a yes that names the upload'
rs_rule "it names the repository" 'the repository as `owner/name`'
rs_rule "and whether it is public or private, read from github" 'whether it is public or private, read with `gh repo view --json visibility`'
rs_rule "an unreadable visibility is said, not guessed" 'where you cannot read that, say so rather than guess'

# What a yes does. The settings refuse a push to main, so the one way main is
# created is written down rather than left for an agent to improvise.
rs_rule "a yes creates main at the commit the branch was cut from" 'create `main` on github at the commit the branch was cut from, `git merge-base main <piece branch>`'
rs_rule "and makes it the default branch" 'make it the default branch'
rs_rule "the default-branch change is told" 'tell the person in one clause that github now starts from their project.s main copy'
rs_rule "the one time main is written other than by a merge" 'this is the one time `main` is written other than by a merge'

# A no, and nobody there.
rs_rule "a no keeps the piece on its own branch here" 'on a no, keep the piece on its own branch on this computer'
rs_rule "a no is the route the project cannot perform, with its note" 'that is the route the project cannot perform right now, with its one-line note'
rs_rule "the next piece asks again" 'the next piece that pushes asks again'
rs_rule "an unattended run never uploads" 'in an unattended run nobody is there to say yes, so never upload on the person.s behalf: keep the work local and note it on the piece'
rs_guard "$BUILDER" "section-builder's first upload rules"

rs_require_order "the rules sit in the safe start, before the piece is labelled" "$BUILDER" '^\*\*The first upload\.\*\*' 'Label the piece `building`'
rs_require_load_bearing "the save step points back at the ask" "$BUILDER" 'the project.s first upload waits for the yes in step 1'

# The other commands that push follow the same rule.
rs_require_load_bearing "sync's save follows the first upload rule" "$SYNC" 'the project.s first upload waits for the yes section-builder.s "the first upload" describes'
rs_require_load_bearing "ship's records follow the first upload rule" "$SHIP" 'the project.s first upload waits for the yes section-builder.s "the first upload" describes'
# An acceptance saved in shaping travels on a records pull request, which can be
# the first thing a project ever pushes.
rs_require_load_bearing "shape's acceptance pull request follows the first upload rule" "$SHAPE" \
  'pushing that pull request is the project.s first upload, which waits for the yes section-builder.s "the first upload" describes'
rs_require_load_bearing "the push-to-main rule names its one narrow exception" "$BLOCKED" 'the one exception is the project.s first upload: after the person.s yes, and only when the remote lists no branch, `main` is created through the github api at the commit the piece.s branch was cut from'
rs_require_load_bearing "and main is never written by a git push" "$BLOCKED" 'it is never written by a `git push`'

# Founding's promise stays true, and says what comes next.
rs_require_load_bearing "founding says the first piece asks before the code goes online" "$SETUP" 'where the online repository holds none of the code yet, the code stays on this computer until the first piece that pushes asks the person first'

# Founding opens issues before any piece pushes, so the kit's own repository
# has to be caught there too, or the pieces land on it before the first upload
# rule is ever reached. check-tooling.sh runs the report that finds it.
rs_require_load_bearing "founding checks the repository before the first issue" "$SETUP" 'before the first issue, check which repository the project points at'
rs_require_load_bearing "founding changes nothing on the kit's repository" "$SETUP" 'where it does, change nothing there: open no issue, make or remove no label, change no setting, and push nothing'
rs_require_load_bearing "founding asks for the person's own" "$SETUP" 'say in one line that the project still points at the kit.s repository, and ask for the person.s own'
rs_require_load_bearing "a new repository gets the report again" "$SETUP" 'point `origin` at it, run the report again, and carry on with what it finds'
rs_require_load_bearing "founding carries on with none, pieces waiting" "$SETUP" 'with none, save everything else and say plainly that the pieces are created once the project has a repository of its own'
rs_require_order "the check comes before the pieces become issues" "$SETUP" 'Before the first issue, check which repository' 'Each piece becomes an issue, written to the shape'

# WORKFLOW.md tells it.
rs_require_load_bearing "WORKFLOW says the first upload is asked" "$WORKFLOW" 'on either route, the first time anything pushes your project.s code online, the agent asks you first, naming the repository and whether it is public or private'
rs_require_load_bearing "WORKFLOW says it is asked once for each project" "$WORKFLOW" 'it asks once for each project: once the code is on github, it does not ask again'
rs_require_load_bearing "WORKFLOW says a no or nobody there keeps the piece local" "$WORKFLOW" 'if you say no, or nobody is there to answer, the piece is still built and checked, and it waits on its own branch on your computer until you say yes'
rs_require_load_bearing "WORKFLOW says an unrelated or kit repository gets nothing" "$WORKFLOW" 'if the repository already holds something that is not your project, or still points at the kit.s own repository, nothing is pushed and the agent asks you what to do'
rs_require_load_bearing "WORKFLOW's founding story says the first build asks" "$WORKFLOW" 'if none of your code is online yet, it stays there until your first build asks you before putting it online'

rs_done
