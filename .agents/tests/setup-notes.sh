#!/usr/bin/env sh
# setup-notes.sh: guard the working notes the founding interview keeps.
#
# /setup-ai-build-kit interviews for a long time before masterplan.md exists, so
# each agreed answer is written to .agents/tmp/setup-notes.md as it is given and
# the file is deleted once the masterplan carries the same answers.
# Nothing in a replayed conversation can prove that cheaply, because the file is
# deliberately invisible to the person. This check guards the source instead,
# then stands up a throwaway project to show that a file written under
# .agents/tmp/ really does stay out of a commit.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILL="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
IGNORE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/gitignore"

rs_init "Setup working-notes checks"
rs_exists "$SKILL" "$IGNORE"

rs_rule "names the working notes" \
  'write each answer into .{0,2}\.agents/tmp/setup-notes\.md'
rs_rule "writes each answer before the next question" \
  'as it is agreed, before asking the next question'
rs_rule "keeps the notes out of every commit" 'carries .{0,2}\.agents/tmp/'
rs_rule "resumes from the saved answers" 'carrying on from those answers'
rs_rule "clears the notes once the masterplan exists" \
  'delete .{0,2}\.agents/tmp/setup-notes\.md'
rs_guard "$SKILL" "the shipped setup skill"

# --- the notes really do stay out of a commit -----------------------------
PROJECT="$rs_dir/project"
mkdir -p "$PROJECT/.agents/tmp"
git init -q "$PROJECT"
cp "$IGNORE" "$PROJECT/.gitignore"
printf 'Who uses it: the shop manager.\n' > "$PROJECT/.agents/tmp/setup-notes.md"

untracked=$(git -C "$PROJECT" status --porcelain --untracked-files=all | \
  grep -c 'setup-notes\.md' || true)
[ "$untracked" -eq 0 ] && r=yes || r=no
rs_report "working notes stay out of a project's tracked work" "$r"

# The control: without the ignore line the same file would show up, so the check
# above is reading the ignore rule rather than an empty folder.
grep -v '^\.agents/tmp/$' "$PROJECT/.gitignore" > "$PROJECT/.gitignore.new"
mv "$PROJECT/.gitignore.new" "$PROJECT/.gitignore"
untracked=$(git -C "$PROJECT" status --porcelain --untracked-files=all | \
  grep -c 'setup-notes\.md' || true)
[ "$untracked" -eq 1 ] && r=yes || r=no
rs_report "without the ignore line the same file would be offered for commit" "$r"

rs_done
