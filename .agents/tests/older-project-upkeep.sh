#!/usr/bin/env sh
# older-project-upkeep.sh: guard what the monthly visit brings to an older project.
#
# Four things an update never reaches, because it refreshes skills and nothing
# else. A plan.md left from before pieces became issues, which used to be
# offered only on the one visit that first brought in /shape and /implement,
# so a project that missed it kept the file for good. Pointers in AGENTS.md and
# the masterplan that name a skill's file by a folder a Claude-Code-only or
# plugin install does not have. And the reminder script, which a visit copied
# in even after the person asked for no kit updates. And the labels on the
# project's issues, which a project founded before the piece states still
# carries in the old form.
#
# The pointer rewrite runs a shipped script, so its half of this check runs it:
# an old project is offered the rewrite and a current one gets nothing, and a
# pattern too broad would rewrite a project's own skill or a passing mention.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
SCRIPT="$ROOT/.agents/skills/maintain/scripts/old-skill-pointers.py"
WORKFLOW="$ROOT/WORKFLOW.md"
TEMPLATES="$ROOT/.agents/skills/setup-ai-build-kit/templates"

rs_init "Older-project upkeep rules"
rs_exists "$MAINTAIN" "$SCRIPT" "$WORKFLOW" "$TEMPLATES/foundation/AGENTS.md" "$TEMPLATES/masterplan.md"

# Both are decided by what is on disk, every visit.
rs_rule "the monthly step runs both on what is on disk" 'on every visit, run "pointing the records at a skill by name" below, and whenever a `plan\.md` is at the project root, run "moving a plan\.md into issues" below'
rs_rule "plan.md is offered for as long as it is there" 'run this on any visit that finds a `plan\.md` at the project root, for as long as it is there'
rs_rule "the shape migration points to it" 'move a `plan\.md` into issues, as "moving a plan\.md into issues" below says'
rs_rule "a plan.md of the person's own is left alone" 'where the file is plainly something else of the person.s, such as their own notes, leave it and say nothing'
rs_rule "plan.md is removed only after the move" 'name what moved, and only then remove `plan\.md`'
rs_rule "a no to the move comes back next visit" 'nothing records the no, so the offer comes back on the next visit that still finds the file'

# The pointer rewrite.
rs_rule "the pointer step runs every visit" 'pointing the records at a skill by name run this on every visit'
rs_rule "it runs the shipped script" 'scripts/old-skill-pointers\.py'
rs_rule "nothing to change says nothing" 'when it prints nothing, say nothing'
rs_rule "the rewrite waits for a yes" 'as one the person may want to change by hand\. wait for the person.s yes'
rs_rule "the rewrite is read back" 'run it again without, and carry on only once no line it prints ends in a new form'
rs_rule "a former skill name is found" 'under today.s name or one it had before, such as `start` for `setup-ai-build-kit`'
rs_rule "only a pointer that stands alone is rewritten" 'the pointer stands alone, as a whole code span or a bare path, and the skill still has the file'
rs_rule "a line left as written is never rewritten" 'a line ending in `left as written:` gives the reason it cannot, such as a pointer inside a code block, a command or a link, where a rewrite would break the line\. those are never rewritten'
rs_rule "a rewrite changes nothing else" 'a rewrite changes the pointers and nothing else in the file, line endings included'
rs_rule "lines only left as written get one line, not an offer" 'where the script finds only lines left as written, offer nothing: say in one line how many there are and in which file'
rs_rule "the person hears which lines were left" 'name each line left as written, with its reason, as one the person may want to change by hand'
rs_rule "no rewrite by hand when the script cannot run" 'where the harness cannot run the script, leave the files as they are and say that the check did not run'
rs_rule "a no changes nothing" 'where the person says no, leave both files as they are\. the offer comes back on the next visit that still finds an old pointer'

# The reminder script after a no to kit updates.
rs_rule "the hook is skipped after no kit updates" 'unless the person asked during this visit to leave kit updates alone'
rs_rule "the request is read, not matched" 'read what they asked, not a fixed phrase'
rs_rule "a skipped hook is said in one sentence" 'i left out the script that reminds a session when a visit is due, since you asked for no kit updates'
rs_rule "the visit is still said to be recorded" 'where you skipped the script, say instead: "i have recorded today.s visit\.'

# The move onto the piece states. An update refreshes skills and never the
# issues, so a project founded before the states keeps labels no board can be
# drawn from until a visit moves them. The offer is made once, applied only on
# a yes, and a second visit finds nothing to move, so it says nothing.
rs_rule "the monthly step runs the move" 'run "moving the pieces onto the states" below'
rs_rule "a project already on the states hears nothing" \
  'the project is already on the states: say nothing'
rs_rule "a second visit after a yes changes nothing" \
  'that is also what a second visit finds after a yes, so it changes nothing'
rs_rule "an earlier no to the same states stands" \
  'where it lists the same six states pieces\.md lists today, the earlier no stands'
rs_rule "a waiting piece gains shaping" \
  'an open piece with a `needs-` label and no `shaping` gains `shaping`'
rs_rule "a piece with no state gains idea" 'an open piece with no state label gains `idea`'
rs_rule "the check also looks at the pieces, not only the labels" \
  'no open piece carries a `needs-` label without `shaping`, the project is already on the states'
rs_rule "because the labels alone do not settle it" 'the labels alone do not settle it'
rs_rule "a piece made of parts gains no state" \
  'except a piece made of parts, which carries no state of its own'
rs_rule "blocked used as a dependency hint loses the label and stays buildable" \
  'a `blocked` piece with a blocked-by link and no written reason was using the old label as a hint'
rs_rule "that piece keeps or gains ready" 'so it loses `blocked` and keeps `ready`, or gains it'
rs_rule "any other blocked becomes parked with its reason" \
  'any other `blocked` piece becomes `parked`, losing `blocked` and any `ready` or `building` beside it, with its reason kept'
rs_rule "a missing reason is written as not recorded" \
  'labelled blocked before the piece states; reason not recorded'
rs_rule "closed issues, a parked idea above all, are left alone" \
  'closed issues are left alone, and a closed `parked` idea above all'
rs_rule "the offer says what it reaches" 'say how many pieces each change reaches'
rs_rule "nothing changes without a yes" 'on a yes, create the missing labels with `gh label create`'
rs_rule "a no is recorded with the states offered" \
  'states-declined\|<yyyy-mm-dd>\|idea,shaping,ready,building,to check,parked'
rs_rule "the offer returns only when the states change" \
  'offers again only when a release changes the states'

# The move onto the index. An update refreshes skills and never the project's
# AGENTS.md or its copied check, so a project founded before the index keeps a
# long file and a check with no ceiling. The move is offered once, comes with
# the ceiling step, loses no fact, and a second visit finds nothing to do.
rs_rule "the monthly step runs the index move" 'run "moving the instructions onto the index" below'
rs_rule "a project on the index hears nothing" 'the project is already on the index: say nothing'
rs_rule "a second visit after a yes finds the move done" 'a second visit after a yes finds both and says nothing'
rs_rule "the move reads the installed template" 'from the installed `setup-ai-build-kit` skill.s `templates/foundation/agents\.md`'
rs_rule "no fact is lost in the move" 'every fact that leaves agents\.md lands in its home'
rs_rule "design moves to concept files" 'lasting technical design moves into `docs/<concept>\.md`, one concept to a file'
rs_rule "dates, issue numbers and code names leave AGENTS.md" 'dates, issue numbers and code names leave agents\.md'
rs_rule "the ceiling step comes with the move" 'the ceiling step comes with the move'
rs_rule "a file already past the ceiling hears why they come together" 'where agents\.md is already above 200 lines, say that the step alone would turn the check red'
rs_rule "the move is offered once" 'offer the move onto the index once, in one reply'
rs_rule "nothing moves without a yes" 'on a yes, make the move and add the ceiling step'
rs_rule "a no is recorded with the template's headings" 'index-declined\|<yyyy-mm-dd>\|<the template.s section headings'
rs_rule "a no is not asked again until the template changes" 'the offer does not come back until a release changes those headings, and then it comes back once'
rs_rule "the no stands only while the headings match" 'the section headings it lists are the ones the installed template has today, the earlier no stands'
rs_rule "a file still past the ceiling hears which sections remain" 'where it is still above 200 lines, name the sections that remain large and offer the trim'
rs_rule "concept files are listed in docs/README.md" 'each file listed with what it owns in `docs/readme\.md`'
rs_rule "on the index, the trim moves facts to their homes" 'on a project already on the index, the trim is a move, never a cut'
rs_rule "the trim takes dates, issue numbers and code names out" 'history to a file in `changes/`, product facts to the masterplan, and dates, issue numbers and code names leave agents\.md'

rs_guard "$MAINTAIN" "the maintain skill"

rs_require_load_bearing "WORKFLOW says plan.md is offered until moved" "$WORKFLOW" 'any visit that finds an older `plan\.md` list offers to move it into your project.s issues, and keeps offering until it is moved'
rs_require_load_bearing "WORKFLOW says the pointers are rewritten on a yes" "$WORKFLOW" 'offers to name the skill instead, changing only those lines, and only on your yes'
rs_require_load_bearing "WORKFLOW says an older project gets one offer to move onto the states" "$WORKFLOW" 'gets one offer to move onto them'
rs_require_load_bearing "WORKFLOW says an older project gets one offer to move onto the index" "$WORKFLOW" 'offers once to move it onto the index'
rs_require_load_bearing "WORKFLOW says the reminder is skipped after a no" "$WORKFLOW" 'if you ask a visit to leave kit updates alone, it does not add that reminder either, and says so'

# --- the script, run --------------------------------------------------------

WORK="$rs_dir/projects"
mkdir -p "$WORK/old" "$WORK/current" "$WORK/own"

# An old project, in the form the templates once wrote.
cat > "$WORK/old/AGENTS.md" <<'EOF'
When a skill says to run another skill, load that installed skill and follow
it. If native discovery is unavailable, open `.agents/skills/<name>/SKILL.md`
directly. Skills live in `.agents/skills/`.
The remaining work lives in this project's issues, one per piece, in the shape
`.agents/skills/setup-ai-build-kit/references/pieces.md` describes.
Our own deploy notes are in `.agents/skills/deploy-notes/SKILL.md`.
EOF
cat > "$WORK/old/masterplan.md" <<'EOF'
<!-- Rewritten only by re-running the fit check, which lives at
.agents/skills/setup-ai-build-kit/references/fit-check.md. The agent reads this section
first, every session. -->
EOF
cp "$WORK/old/AGENTS.md" "$WORK/old/AGENTS.before"

found=$(python3 "$SCRIPT" "$WORK/old")
rs_report "an old project's two pointers are both found" \
  "$([ "$(printf '%s\n' "$found" | grep -c .)" = 2 ] && echo yes || echo no)"
rs_report "each finding names its file, line and new form" \
  "$(printf '%s\n' "$found" | grep -qF "masterplan.md:2	.agents/skills/setup-ai-build-kit/references/fit-check.md	the \`setup-ai-build-kit\` skill's \`references/fit-check.md\`" && echo yes || echo no)"
rs_report "listing changes nothing" \
  "$(cmp -s "$WORK/old/AGENTS.md" "$WORK/old/AGENTS.before" && echo yes || echo no)"

python3 "$SCRIPT" --apply "$WORK/old" >/dev/null
rs_report "the rewrite gives the form the templates use now" \
  "$(grep -qF "the \`setup-ai-build-kit\` skill's \`references/pieces.md\` describes." "$WORK/old/AGENTS.md" && echo yes || echo no)"
rs_report "a placeholder, the folder and the project's own skill are left alone" \
  "$(grep -qF '`.agents/skills/<name>/SKILL.md`' "$WORK/old/AGENTS.md" \
     && grep -qF 'Skills live in `.agents/skills/`.' "$WORK/old/AGENTS.md" \
     && grep -qF '`.agents/skills/deploy-notes/SKILL.md`' "$WORK/old/AGENTS.md" && echo yes || echo no)"
rs_report "only the pointer lines changed" \
  "$([ "$(diff "$WORK/old/AGENTS.before" "$WORK/old/AGENTS.md" | grep -c '^<')" = 1 ] && echo yes || echo no)"
rs_report "a second run finds nothing" \
  "$([ -z "$(python3 "$SCRIPT" "$WORK/old")" ] && echo yes || echo no)"

# A project founded on the earliest releases, whose pointers name the founding
# skill by its first name. The rename migration removes that folder, so these
# open nothing on any route, and they are the ones a visit most needs to find.
mkdir -p "$WORK/first"
cat > "$WORK/first/AGENTS.md" <<'EOF'
The restrictions in `.agents/skills/start/references/blocked-commands.md` always apply.
EOF
cat > "$WORK/first/masterplan.md" <<'EOF'
<!-- Rewritten only by re-running the fit check, which lives at
.agents/skills/start/references/fit-check.md. The agent reads this section
first, every session. -->
EOF
python3 "$SCRIPT" --apply "$WORK/first" >/dev/null
rs_report "a pointer under the founding skill's first name is rewritten to today's" \
  "$(grep -qF "The restrictions in the \`setup-ai-build-kit\` skill's \`references/blocked-commands.md\` always apply." "$WORK/first/AGENTS.md" \
     && grep -qF "the \`setup-ai-build-kit\` skill's \`references/fit-check.md\`. The agent reads this section" "$WORK/first/masterplan.md" && echo yes || echo no)"

# Lines where a rewrite would break what the person wrote. Each is listed with
# its reason and left exactly as it was, and a line with two standalone
# pointers has both rewritten.
mkdir -p "$WORK/awkward"
cat > "$WORK/awkward/AGENTS.md" <<'EOF'
Run `python3 .agents/skills/maintain/scripts/old-skill-pointers.py` monthly.
See [pieces](.agents/skills/setup-ai-build-kit/references/pieces.md) for more.
Folder `.agents/skills/ship/recipes/` holds recipes.
Anchor .agents/skills/setup-ai-build-kit/references/pieces.md#shape here.
Prefixed ./.agents/skills/setup-ai-build-kit/references/pieces.md here.
Gone `.agents/skills/setup-ai-build-kit/references/no-such-file.md` here.
Two: `.agents/skills/ship/templates/handover.md` and `.agents/skills/start/references/pieces.md`.
EOF
head -6 "$WORK/awkward/AGENTS.md" > "$WORK/awkward/untouched"
listed_awkward=$(python3 "$SCRIPT" "$WORK/awkward")
python3 "$SCRIPT" --apply "$WORK/awkward" >/dev/null
rs_report "a pointer inside a command, a link, a longer path, or to a missing file is listed with its reason" \
  "$([ "$(printf '%s\n' "$listed_awkward" | grep -c 'left as written: ')" = 6 ] && echo yes || echo no)"
rs_report "and each of those lines is left exactly as it was" \
  "$(head -6 "$WORK/awkward/AGENTS.md" | cmp -s - "$WORK/awkward/untouched" && echo yes || echo no)"
rs_report "two standalone pointers on one line are both rewritten" \
  "$(grep -qF "Two: the \`ship\` skill's \`templates/handover.md\` and the \`setup-ai-build-kit\` skill's \`references/pieces.md\`." "$WORK/awkward/AGENTS.md" && echo yes || echo no)"
rs_report "after the rewrite, nothing is left to rewrite" \
  "$([ -z "$(python3 "$SCRIPT" "$WORK/awkward" | grep -v 'left as written: ')" ] && echo yes || echo no)"

# A second review found three more ways to break a line: a command in a fenced
# or indented code block has no backticks on its own line, a pointer between
# double backticks sat in a span the first check did not see, and a file with
# Windows line endings came back with every line changed. Each of those lines
# stays exactly as it was, and the rewrite keeps the file's line endings.
mkdir -p "$WORK/blocks"
cat > "$WORK/blocks/AGENTS.md" <<'EOF'
```sh
cat .agents/skills/setup-ai-build-kit/references/pieces.md
```
    cat .agents/skills/ship/templates/handover.md
Double `` .agents/skills/setup-ai-build-kit/references/pieces.md `` here.
Folder .agents/skills/ship/recipes here.
Read the `.agents/skills/setup-ai-build-kit/references/fit-check.md` file.
EOF
head -6 "$WORK/blocks/AGENTS.md" > "$WORK/blocks/untouched"
blocks_listed=$(python3 "$SCRIPT" "$WORK/blocks")
python3 "$SCRIPT" --apply "$WORK/blocks" >/dev/null
rs_report "a pointer in a code block, in double backticks, or naming a folder is listed with its reason" \
  "$(printf '%s\n' "$blocks_listed" | grep -q 'left as written: it sits inside a code block' \
     && [ "$(printf '%s\n' "$blocks_listed" | grep -c 'left as written: it sits inside a code block')" = 2 ] \
     && printf '%s\n' "$blocks_listed" | grep -q 'left as written: it sits inside a code span in double backticks' \
     && printf '%s\n' "$blocks_listed" | grep -q 'left as written: it names a folder, not a file' && echo yes || echo no)"
rs_report "and those lines are left exactly as they were" \
  "$(head -6 "$WORK/blocks/AGENTS.md" | cmp -s - "$WORK/blocks/untouched" && echo yes || echo no)"
rs_report "a sentence that already says the gets no second one" \
  "$(grep -qF "Read the \`setup-ai-build-kit\` skill's \`references/fit-check.md\` file." "$WORK/blocks/AGENTS.md" && echo yes || echo no)"

# A third review found a fence of four backticks closed by the first line of
# three, which is how a code block is shown inside a code block. The command
# inside was rewritten, and every line after it read the wrong way round. A
# fence closes only on a run of the same mark at least as long as its opener.
mkdir -p "$WORK/nested"
cat > "$WORK/nested/AGENTS.md" <<'EOF'
````markdown
```
cat .agents/skills/shape/SKILL.md
```
````
After `.agents/skills/setup-ai-build-kit/references/pieces.md` here.
~~~
```
cat .agents/skills/shape/SKILL.md
~~~
Then `.agents/skills/setup-ai-build-kit/references/fit-check.md` too.
EOF
nested=$(python3 "$SCRIPT" "$WORK/nested")
rs_report "a block shown inside a longer fence stays a code block, and prose after it is read as prose" \
  "$([ "$(printf '%s\n' "$nested" | grep -c 'left as written: it sits inside a code block')" = 2 ] \
     && [ "$(printf '%s\n' "$nested" | grep -c "skill's \`references/")" = 2 ] && echo yes || echo no)"

mkdir -p "$WORK/crlf" "$WORK/unreadable"
printf 'line one\r\nSee `.agents/skills/setup-ai-build-kit/references/pieces.md`.\r\nlast\r\n' > "$WORK/crlf/AGENTS.md"
printf "line one\r\nSee the \`setup-ai-build-kit\` skill's \`references/pieces.md\`.\r\nlast\r\n" > "$WORK/crlf/expected"
python3 "$SCRIPT" --apply "$WORK/crlf" >/dev/null
rs_report "a file with Windows line endings keeps them, and only the pointer changes" \
  "$(cmp -s "$WORK/crlf/AGENTS.md" "$WORK/crlf/expected" && echo yes || echo no)"
printf 'ok\n\377\376 not text\n' > "$WORK/unreadable/AGENTS.md"
unreadable=$(python3 "$SCRIPT" "$WORK/unreadable" 2>&1) && code=0 || code=$?
rs_report "a file that is not readable text gets one line, not a crash" \
  "$([ "$code" = 0 ] && printf '%s\n' "$unreadable" | grep -q 'left as written: it is not readable text' && echo yes || echo no)"

# A project founded today, from the shipped templates, gets nothing.
cp "$TEMPLATES/foundation/AGENTS.md" "$WORK/current/AGENTS.md"
cp "$TEMPLATES/masterplan.md" "$WORK/current/masterplan.md"
rs_report "a project founded from today's templates gets no offer" \
  "$([ -z "$(python3 "$SCRIPT" "$WORK/current")" ] && echo yes || echo no)"

# A project whose only matching folder is its own skill gets nothing either.
printf '%s\n' 'See `.agents/skills/deploy-notes/SKILL.md`.' > "$WORK/own/AGENTS.md"
rs_report "a project's own skill is never offered" \
  "$([ -z "$(python3 "$SCRIPT" "$WORK/own")" ] && echo yes || echo no)"

# The script's list of the kit's skills has to be the kit's skills, or a
# renamed or added skill's pointers would be missed without a word.
listed=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$SCRIPT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("p", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print("\n".join(sorted(module.KIT_SKILLS)))
PY
)
shipped=$(ls "$ROOT/.agents/skills" | sort)
rs_report "the script names exactly the kit's fourteen skills" \
  "$([ "$listed" = "$shipped" ] && [ "$(printf '%s\n' "$listed" | grep -c .)" = 14 ] && echo yes || echo no)"

rs_done
