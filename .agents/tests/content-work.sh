#!/usr/bin/env sh
# content-work.sh: guard how the kit handles a request to use the tool on
# content, rather than to change the tool.
#
# Some tools exist to turn content into something: a report generator, a site
# builder, an importer. In one project, "I got a document I want to test on
# this" produced a new report, a branch, two changelog entries and a recorded
# output, all outside any piece. The branch was never pushed, so its changelog
# entry never reached `main` and the project's history does not mention that
# report. The kit had routes for changing the tool and none for using it.
#
# change-triage names the intent and routes it: the run happens in the main
# folder with no piece, no branch and no changelog file, and the output and the
# person's input land in a folder git ignores, so the next build's clean-tree
# check is not stopped. Content the person asks to keep goes through the build
# path's save route with its own changelog file, never onto a branch nobody
# pushes. section-builder step 9 points kept content at that save, and
# WORKFLOW.md tells it.
#
# The second half is a rehearsal. It founds a throwaway project from the
# shipped gitignore, writes an input and an output where change-triage says
# they go, and finds `git status --porcelain` empty. The same files written to
# a folder git does not ignore show up, so the rehearsal can fail. An older
# project whose gitignore lacks `.agents/tmp/` fails the `git check-ignore` the
# skill runs first, which is what sends its output outside the project.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
TRIAGE="$SKILLS/change-triage/SKILL.md"
BUILDER="$SKILLS/section-builder/SKILL.md"
GITIGNORE="$SKILLS/setup-ai-build-kit/templates/foundation/gitignore"
FOUNDED_AGENTS="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Content-work checks"
rs_exists "$TRIAGE" "$BUILDER" "$GITIGNORE" "$FOUNDED_AGENTS" "$WORKFLOW"

# change-triage: the intent, its route, where the output goes, keeping it, and
# the cases that are not the normal one.
rs_rule "Step 2 names the intent" \
  'work on this computer outside the project; using the tool on content;'
rs_rule "Step 4 lists the route" 'using the tool on content, done without a piece'
rs_rule "the section exists" '### using the tool on content'
rs_rule "what counts: running the tool on the person's material" \
  'running the tool on the person.s material to produce an output, or to see how it handles that material'
rs_rule "with no change to the tool" \
  'with no change to the tool.s code, checks or records'
rs_rule "the run happens in the main folder" 'run the tool on the content in the main folder'
rs_rule "the output is handed over with where it is" \
  'hand the output to the person and say where it is'
rs_rule "no piece, no branch, no changelog file" \
  'it gets no piece, no branch and no changelog file'
rs_rule "the output stays out of git unless kept" \
  'the output stays out of git unless the person asks to keep it'
rs_rule "an ignored output folder is used as it is" \
  'where the tool writes its output to a folder git already ignores, it stays there'
rs_rule "otherwise the dated content folder" \
  'otherwise it goes to `\.agents/tmp/content/<yyyy-mm-dd>-<short name>/`'
rs_rule "git ignoring the folder is checked first" \
  'check first with `git check-ignore -q \.agents/tmp/content/`'
rs_rule "where it is not ignored, a temporary folder outside the project" \
  'write to a folder made with `mktemp -d` outside the project instead'
rs_rule "and an offer to ignore it" \
  'offer once to add `\.agents/tmp/` to `\.gitignore` as a small saved change'
rs_rule "the person's input goes there too" \
  'the person.s own input files go to the same place unless they are already in the project'
rs_rule "git status is unchanged" \
  '`git status` is as clean after the run as before it'
rs_rule "kept content goes through the build path's save route" \
  'save it through the save route the build path uses, following section-builder.s save and record steps yourself'
rs_rule "with its own changelog file" \
  'as a small change with its own changelog file'
rs_rule "and its own pull request on that route" \
  'on the pull-request route, its own pull request'
rs_rule "never on a branch left unpushed" 'never on a branch that is left unpushed'
rs_rule "a fault the content shows is said in one line" \
  'shows a problem in the tool, because it fails or the output is wrong, say so in one line'
rs_rule "and becomes a repair or a piece" \
  'it becomes a repair through `/fix` or a new piece through this triage'
rs_rule "the content run itself is not a repair" 'the content run itself is not a repair'
rs_rule "changing the tool for the content is not content work" \
  'a request that changes the tool so it can handle the content is not content work'
rs_rule "confidential content: points at the founded rule" \
  'the confidential-files rule in agents\.md applies'
rs_rule "nothing of it committed, even when kept" \
  'nothing of it or its output is committed, even when the person asks to keep it'
rs_rule "a person who leaves: nothing committed" \
  'leaves before saying whether to keep it, nothing is committed'
rs_rule "the output stays where the reply said" \
  'the output stays where it was written, and the reply named that place'
rs_rule "a tool that cannot run here: say so and stop" \
  'cannot run on this computer, say so and stop'
rs_guard "$TRIAGE" "the change-triage skill"

rs_require_order "the section follows the own-computer section" "$TRIAGE" \
  '^### Work on this computer outside the project' '^### Using the tool on content'
rs_require_order "and comes before Step 5" "$TRIAGE" \
  '^### Using the tool on content' '^## Step 5'
rs_require "triage still gives a request exactly one route" "$TRIAGE" \
  'the request has exactly one route'
rs_require "the founded confidential-files rule it points at still exists" \
  "$FOUNDED_AGENTS" 'never stage, commit, print, or copy their contents'

# section-builder step 9: kept content takes the save route and its own file.
rs_reset
rs_rule "kept content is saved by this skill too" \
  'content the person asks to keep after using the tool on it'
rs_rule "on the build path's save route, with its own changelog file" \
  'is saved through the build path.s save route with its own changelog file'
rs_rule "never left on a branch nobody pushes" 'never left on a branch nobody pushes'
rs_guard "$BUILDER" "the section-builder skill"

rs_require_order "the pointer sits in step 9" "$BUILDER" \
  '^## 9\. Sync the records' 'Content the person asks to keep'
rs_require_order "and before the excuses" "$BUILDER" \
  'Content the person asks to keep' '^## Excuses'

# WORKFLOW.md tells it in Day to day.
rs_reset
rs_rule "using the tool on your material needs no piece" \
  'using the tool on your own material, such as running a document through it to see what it makes, needs no piece'
rs_rule "the output goes where the project does not save it" \
  'the output goes to a folder the project does not save, and the reply says where'
rs_rule "kept content is saved like any other change" \
  'ask to keep it and it is saved like any other change, with its own changelog entry'
rs_rule "a fault it shows becomes a fix or a piece" \
  'if the run shows the tool getting something wrong, that becomes a /fix or a new piece'
rs_guard "$WORKFLOW" "WORKFLOW.md"

rs_require_order "WORKFLOW.md says it in Day to day" "$WORKFLOW" \
  '^## 5\. Day to day' 'Using the tool on your own material'
rs_require_order "and before Evidence" "$WORKFLOW" \
  'Using the tool on your own material' '^## 6\. Evidence'

# The rehearsal: the place change-triage names is one the shipped gitignore
# ignores, so a content run leaves `git status` as it was.
[ -n "${RS_LIST:-}" ] && exit 0

folder=$(grep -oE '`\.agents/tmp/content/<YYYY-MM-DD>-<short name>/`' "$TRIAGE" | head -1 | tr -d '`')
[ -n "$folder" ] || rs_fail "change-triage names no content folder"
folder=$(printf '%s' "$folder" | sed 's/<YYYY-MM-DD>/2026-10-01/; s/<short name>/sample-report/')

project="$rs_dir/project"
mkdir -p "$project"
cp "$GITIGNORE" "$project/.gitignore"
printf '# Sample\n' > "$project/README.md"
git -C "$project" init -q
git -C "$project" add .gitignore README.md
git -C "$project" -c user.name=Rehearsal -c user.email=rehearsal@example.invalid \
  commit -q -m "Found the sample project"

before=$(git -C "$project" status --porcelain)
[ -z "$before" ] || rs_fail "the throwaway project was not clean before the run"

mkdir -p "$project/$folder"
printf 'the person'"'"'s document\n' > "$project/$folder/input.txt"
printf 'the report the tool made\n' > "$project/$folder/report.html"
after=$(git -C "$project" status --porcelain)
rs_report "a content run in $folder leaves git status empty" \
  "$([ -z "$after" ] && echo yes || echo no)"

# The control: the same files where git does not ignore them do show.
mkdir -p "$project/content"
cp "$project/$folder/report.html" "$project/content/report.html"
shown=$(git -C "$project" status --porcelain)
rs_report "the same output in a folder git does not ignore shows in git status" \
  "$([ -n "$shown" ] && echo yes || echo no)"

# An older project whose gitignore predates `.agents/tmp/`: the check the
# skill names tells the two apart, so the run goes outside the project there.
rs_report "git check-ignore accepts the content folder in a project founded today" \
  "$(git -C "$project" check-ignore -q .agents/tmp/content/ && echo yes || echo no)"
older="$rs_dir/older"
mkdir -p "$older"
grep -v '^\.agents/tmp/$' "$GITIGNORE" > "$older/.gitignore"
git -C "$older" init -q
rs_report "and refuses it in a project whose gitignore does not carry .agents/tmp/" \
  "$(git -C "$older" check-ignore -q .agents/tmp/content/ && echo no || echo yes)"

rs_done
