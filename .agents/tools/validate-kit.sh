#!/usr/bin/env sh
# validate-kit.sh: repository self-validation for ai-build-kit itself.
#
# Checks the kit's own machinery: the skill inventory, frontmatter, internal
# references, build-path vocabulary, generated adapters, shell and config
# syntax, and a set of stale claims this kit has made before and should never
# make again. Run from anywhere; it locates the repository root itself.
#
# This is a maintainer and CI tool. A project built with the kit never runs
# this script; docs/MAINTAINING.md explains why the two are different things.
#
# POSIX sh. Uses python3 for JSON/TOML/YAML parsing when available, and
# degrades to a plain-text sanity check with a printed note when it isn't;
# missing an optional parser reduces how deep that one check goes, it does
# not skip the check's file entirely.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
note() {
  echo "NOTE: $1" >&2
}
pass() {
  echo "ok: $1"
}

SKILLS="$ROOT/.agents/skills"
# A skill only the kit's own maintainers use lives here rather than beside the
# fourteen. A shared skills installer reads .agents/skills/ and .claude/skills/
# and merges what it finds by the name in its frontmatter, so a folder in
# either one is a skill somebody installs. This folder is in neither.
MAINTAINER_SKILLS="$ROOT/.agents/maintainer-skills"

expected_commands="fix
implement
maintain
queue
setup-ai-build-kit
shape
ship
sync
what-now"

expected_disciplines="change-triage
clarify
screen-check
second-opinion
section-builder"

# Every folder under .agents/maintainer-skills/ is a maintainer skill, and the
# list is read off the folder rather than written out here. A written-out list
# is one a new folder is not on: the second maintainer skill was added by
# editing this list by hand, and had that edit been forgotten the folder would
# have been checked by nothing while this script reported success. A folder
# that cannot be read, or holds nothing, is a failure for the same reason.
expected_maintainer_skills=$(find "$MAINTAINER_SKILLS" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
  | while IFS= read -r skill_dir; do basename -- "$skill_dir"; done | sort)
[ -n "$expected_maintainer_skills" ] || \
  fail "$MAINTAINER_SKILLS: no maintainer skill folder could be read, so none was checked"

# Which of those arrived from somewhere else. A vendored copy carries the
# licence it was published under, and dropping that licence is how a borrowed
# skill turns into an uncredited one. A skill written here has no upstream to
# carry a licence from, so demanding one of every maintainer skill would mean
# inventing a file to satisfy a check.
vendored_maintainer_skills="humanizer"

# ---------------------------------------------------------------------------
echo "== Issue references =="

# A tracked file never cites an issue or a pull request by number. Those numbers
# belong in the issues and pull requests themselves, and in a changelog. In a
# document or a comment a bare number is a pointer the reader cannot follow, and
# once this material is public it points at an unrelated issue in whatever
# numbering that repository happens to have.
#
# So say the thing instead. "The contradiction this check exists to hold shut"
# survives a move; a number does not.
#
# The pattern is built from a variable so this check does not report itself, and
# a character before the hash rules out a shell expansion that trims a prefix.
hash_char='#'
refs=$(git -C "$ROOT" ls-files -- '*.md' '*.sh' '*.yml' '*.json' '*.toml' 2>/dev/null \
  | while IFS= read -r ref_file; do
      grep -HnE "(^|[^A-Za-z0-9\$}])${hash_char}[0-9]{2,4}([^0-9]|\$)" \
        "$ROOT/$ref_file" 2>/dev/null | sed "s|^$ROOT/||"
    done)
if [ -n "$refs" ]; then
  fail "a tracked file cites an issue or pull request by number; say the thing instead:"
  echo "$refs" | sed 's/^/    /' | cut -c1-100
else
  pass "no tracked file cites an issue or pull request by number"
fi

# ---------------------------------------------------------------------------
echo "== Attribution =="

# A tracked file never carries an AI attribution line, and never a link back to
# the session that produced the work. The link is the one that matters: it is a
# personal address on the agent vendor's site, and this repository is public.
#
# The commit-msg hook takes those lines out of a commit message. This check
# covers the other way in, which is somebody pasting a message into a document.
#
# The words are built here rather than written out, so this check does not
# report itself. The rehearsal that drives the hook builds its samples the same
# way, so it needs no exception. One file is left out because carrying the
# words is its job: the hook. Naming it here keeps the exception where a reader
# of the check can see it.
attr_session=$(printf 'claude.ai/code/%s' 'session_')
attr_author=$(printf 'Co-%sed-By: Claude' 'Author')
attr_vendor=$(printf 'noreply@%s.com' 'anthropic')
attr_hits=$(git -C "$ROOT" ls-files 2>/dev/null \
  | grep -v -x -e '.githooks/commit-msg' \
  | while IFS= read -r attr_file; do
      grep -HnIiF -e "$attr_session" -e "$attr_author" -e "$attr_vendor" \
        "$ROOT/$attr_file" 2>/dev/null | sed "s|^$ROOT/||"
    done)
if [ -n "$attr_hits" ]; then
  fail "a tracked file carries an AI attribution line or a session link:"
  echo "$attr_hits" | sed 's/^/    /' | cut -c1-100
else
  pass "no tracked file carries an AI attribution line or a session link"
fi

# The saved mode, not this working copy. A Windows mount reports every file as
# runnable, and the sweep further down does not reach this hook: it skips a
# script the repository hands to sh, which is how the rehearsal drives it.
attr_mode=$(git -C "$ROOT" ls-files -s -- '.githooks/commit-msg' | cut -d' ' -f1)
if [ "$attr_mode" = "100755" ]; then
  pass "the commit-msg hook is saved as a runnable file"
else
  fail ".githooks/commit-msg is missing or not saved as runnable (found mode '$attr_mode')"
fi

# ---------------------------------------------------------------------------
echo "== Stray copies =="

# This repository sits inside ~/Documents, which iCloud syncs. When iCloud has a
# version of something that does not match the one on disk it keeps both, naming
# the newcomer "rule-shape 2.sh". It does that to folders as well, so an empty
# "clarify 2" appears beside the real skill. They arrive in bursts during a
# merge, a checkout or an adapter rebuild, and the numbers climb: 2, then 3.
#
# Nothing said so, which was the real cost. The validator blamed the adapters
# for being out of date and blamed CI for not running a check, because it
# counted ten command files where it demands nine and ten skill folders where
# it demands five. Both accusations pointed at work that was fine.
#
# A stray cannot reach a release, since release-manifest.txt is an allowlist.
# It can be committed by a careless git add -A, and until it is gone every
# later failure reads as something it is not.
#
# Replay results are left out. The harness writes them outside this repository
# now, so the path below normally does not exist; it stays pruned for a run
# pointed back in here by REPLAY_RESULTS. That output is gitignored and is
# rewritten by every pass, so a copy there cannot reach a commit or mislead a
# later check. Failing the validator after every replay run would teach people
# to scroll past this, which is worse than the junk.
strays=$(find "$ROOT" \
  -path "$ROOT/.git" -prune -o \
  -path "$ROOT/node_modules" -prune -o \
  -path "$ROOT/.agents/tests/replay/results" -prune -o \
  \( -type f -o -type d \) \
  \( -name "* [0-9]" -o -name "* [0-9].*" -o -name "* copy" -o -name "* copy.*" \) \
  -print 2>/dev/null \
  | sed "s|^$ROOT/||" | sort)
if [ -n "$strays" ]; then
  fail "copies of files are lying beside the originals; delete them, they are nobody's work:"
  echo "$strays" | sed 's/^/    /'
else
  pass "no copied-and-kept files are lying beside the originals"
fi

# ---------------------------------------------------------------------------
echo "== Skill inventory =="

actual=$(find "$SKILLS" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
expected=$(printf '%s\n%s\n' "$expected_commands" "$expected_disciplines" | sort)

if [ "$actual" != "$expected" ]; then
  fail "skill inventory does not match the canonical nine commands and five disciplines"
  echo "  expected:" >&2
  echo "$expected" | sed 's/^/    /' >&2
  echo "  found:" >&2
  echo "$actual" | sed 's/^/    /' >&2
else
  pass "exactly nine commands and five disciplines, named exactly"
fi

# Each of the fourteen has a SKILL.md. Which of them are commands and which
# are background skills is settled by one setting, and the trigger contract
# further down checks that. Here the question is only that the file exists.
while IFS= read -r name; do
  [ -n "$name" ] || continue
  file="$SKILLS/$name/SKILL.md"
  [ -f "$file" ] || fail "missing $file"
done <<ALLSKILLS
$expected_commands
$expected_disciplines
ALLSKILLS

# The maintainer's own skills sit outside every folder an installer reads, and
# that placement is the whole boundary. There is no marker file and no
# allowlist entry standing between them and a user's project, because a marker
# is this kit's own convention and a shared installer has never heard of it.
# What it does read is a folder, so the check is that the folder is not one.
installer_scanned=".agents/skills
.claude/skills
.claude/commands
.cursor/commands
.gemini/commands"
while IFS= read -r name; do
  [ -n "$name" ] || continue
  file="$MAINTAINER_SKILLS/$name/SKILL.md"
  if [ ! -f "$file" ]; then
    fail "missing $file"
    continue
  fi
  case "
$vendored_maintainer_skills
" in
    *"
$name
"*)
      [ -f "$MAINTAINER_SKILLS/$name/LICENSE" ] || \
        fail "$MAINTAINER_SKILLS/$name/LICENSE: missing vendored skill licence"
      ;;
  esac
  if [ -e "$MAINTAINER_SKILLS/$name/agents/openai.yaml" ]; then
    fail "$MAINTAINER_SKILLS/$name/agents/openai.yaml: a maintainer skill carries no harness policy file"
  fi
  while IFS= read -r scanned; do
    [ -n "$scanned" ] || continue
    for suffix in "" .md .toml; do
      candidate="$scanned/$name$suffix"
      [ ! -e "$ROOT/$candidate" ] || \
        fail "$candidate: a maintainer skill has reached a folder an installer reads, so a project would be offered it as a fifteenth skill"
    done
  done <<SCANNED
$installer_scanned
SCANNED
done <<MAINTAINERSKILLS
$expected_maintainer_skills
MAINTAINERSKILLS

if grep -q '^\.agents/maintainer-skills/' "$ROOT/release-manifest.txt"; then
  fail "release-manifest.txt: the release allowlist carries a maintainer skill, which puts it in a user's project"
else
  pass "every maintainer skill sits outside every folder an installer reads, and outside the release"
fi

# ---------------------------------------------------------------------------
echo "== Harness contracts =="

# Codex reads the canonical .agents/skills/ tree directly, so .codex/skills
# must not exist. A second tree would be a copy nothing refreshes.
if [ -e "$ROOT/.codex/skills" ]; then
  fail ".codex/skills still exists; Codex now reads .agents/skills/ directly"
else
  pass "no .codex/skills adapter tree"
fi

# Claude Code: the five generated background skills are hidden from the user
# command menu. The nine generated commands carry neither setting. A command
# used to carry disable-model-invocation, and a regenerate from a stale builder
# would put it back, so its absence is checked rather than assumed.
while IFS= read -r name; do
  [ -n "$name" ] || continue
  gen="$ROOT/.claude/skills/$name/SKILL.md"
  if [ ! -f "$gen" ]; then
    fail "$gen: missing generated Claude discipline skill"
  elif ! grep -q '^user-invocable:[ \t]*false' "$gen"; then
    fail "$gen: expected user-invocable: false"
  fi
done <<DISCIPLINES2
$expected_disciplines
DISCIPLINES2

while IFS= read -r name; do
  [ -n "$name" ] || continue
  gen="$ROOT/.claude/commands/$name.md"
  if [ ! -f "$gen" ]; then
    fail "$gen: missing generated Claude command"
  elif grep -q '^disable-model-invocation:' "$gen"; then
    fail "$gen: generated commands must not carry disable-model-invocation; the agent may start a command the person asks for"
  elif grep -q '^user-invocable:' "$gen"; then
    fail "$gen: generated commands must not carry user-invocable"
  fi
done <<COMMANDS2
$expected_commands
COMMANDS2

pass "no Codex adapter tree, and Claude skill visibility matches the harness contract"

# CLAUDE.md and GEMINI.md must be exactly the harness import line, so loading
# AGENTS.md never depends on the model choosing to read a prose pointer.
check_exact_file() {
  # $1 = file, $2 = expected exact content (no trailing newline)
  file="$1"
  expected="$2"
  if [ ! -f "$file" ]; then
    fail "$file: missing"
    return
  fi
  actual=$(cat "$file")
  if [ "$actual" != "$expected" ]; then
    fail "$file: expected exactly '$expected' (plus an optional trailing newline), found '$actual'"
  fi
}
check_exact_file "$ROOT/CLAUDE.md" "@AGENTS.md"
check_exact_file "$ROOT/GEMINI.md" "@./AGENTS.md"
pass "CLAUDE.md and GEMINI.md import AGENTS.md deterministically"

# ---------------------------------------------------------------------------
echo "== Trigger contract =="

# One setting decides what a skill is. `user-invocable: false` marks a
# background skill, which the agent loads on its own and nobody types. A skill
# without it is a command, and the agent may start a command when the person
# asks for it in a slash, by name, or in plain words. So a background skill
# must carry the setting and a command must not, and the two generated Claude
# trees are compared as whole listings rather than name by name. The listing
# comparison is deliberately independent of the builder: build-adapters.sh
# --check only proves the committed adapters match what the source generates,
# so a source mistake that generates a wrong but self-consistent tree needs a
# second witness anchored to the expected names.
trigger_ok=1

while IFS= read -r name; do
  [ -n "$name" ] || continue
  file="$SKILLS/$name/SKILL.md"
  [ -f "$file" ] || continue
  if ! grep -q '^user-invocable:[ \t]*false' "$file"; then
    fail "$file: expected user-invocable: false (that setting is what marks a background skill; without it the builder treats the skill as a command)"
    trigger_ok=0
  fi
  if [ -e "$ROOT/.claude/commands/$name.md" ]; then
    fail ".claude/commands/$name.md exists; a background skill must not be reachable as a command"
    trigger_ok=0
  fi
done <<DISCIPLINES3
$expected_disciplines
DISCIPLINES3

while IFS= read -r name; do
  [ -n "$name" ] || continue
  file="$SKILLS/$name/SKILL.md"
  [ -f "$file" ] || continue
  if grep -q '^user-invocable:' "$file"; then
    fail "$file: a command never carries user-invocable; that setting marks a background skill"
    trigger_ok=0
  fi
  if [ -e "$ROOT/.claude/skills/$name" ]; then
    fail ".claude/skills/$name exists; a command must not also be generated as a background skill"
    trigger_ok=0
  fi
done <<COMMANDS3
$expected_commands
COMMANDS3

if [ ! -d "$ROOT/.claude/commands" ]; then
  fail ".claude/commands/ is missing; regenerate the adapters"
  trigger_ok=0
else
  expected_command_files=$(printf '%s\n' "$expected_commands" | sed 's/$/.md/' | sort)
  actual_command_files=$(find "$ROOT/.claude/commands" -mindepth 1 -maxdepth 1 -exec basename {} \; | sort)
  if [ "$actual_command_files" != "$expected_command_files" ]; then
    fail ".claude/commands/ must hold exactly the nine generated command files"
    echo "  expected:" >&2
    echo "$expected_command_files" | sed 's/^/    /' >&2
    echo "  found:" >&2
    echo "$actual_command_files" | sed 's/^/    /' >&2
    trigger_ok=0
  fi
fi

if [ ! -d "$ROOT/.claude/skills" ]; then
  fail ".claude/skills/ is missing; regenerate the adapters"
  trigger_ok=0
else
  expected_skill_dirs=$(printf '%s\n' "$expected_disciplines" | sort)
  actual_skill_dirs=$(find "$ROOT/.claude/skills" -mindepth 1 -maxdepth 1 -exec basename {} \; | sort)
  if [ "$actual_skill_dirs" != "$expected_skill_dirs" ]; then
    fail ".claude/skills/ must hold exactly the five disciplines"
    echo "  expected:" >&2
    echo "$expected_skill_dirs" | sed 's/^/    /' >&2
    echo "  found:" >&2
    echo "$actual_skill_dirs" | sed 's/^/    /' >&2
    trigger_ok=0
  fi
fi

# The Cursor and Gemini trees carry the same nine commands and were covered
# only by the drift comparison, which asks whether the committed adapters match
# what the source generates. A source mistake that generates a wrong but
# self-consistent tree satisfies that and reaches a project. These anchor both
# folders to the expected names, as the two Claude trees already are.
for adapter in ".cursor/commands:.md:Cursor" ".gemini/commands:.toml:Gemini CLI"; do
  dir=${adapter%%:*}
  rest=${adapter#*:}
  ext=${rest%%:*}
  tool=${rest#*:}
  if [ ! -d "$ROOT/$dir" ]; then
    fail "$dir/ is missing; regenerate the adapters"
    trigger_ok=0
    continue
  fi
  expected_files=$(printf '%s\n' "$expected_commands" | sed "s/\$/$ext/" | sort)
  actual_files=$(find "$ROOT/$dir" -mindepth 1 -maxdepth 1 -exec basename {} \; | sort)
  if [ "$actual_files" != "$expected_files" ]; then
    fail "$dir/ must hold exactly the nine generated $tool command files"
    echo "  expected:" >&2
    echo "$expected_files" | sed 's/^/    /' >&2
    echo "  found:" >&2
    echo "$actual_files" | sed 's/^/    /' >&2
    trigger_ok=0
  fi
done

[ "$trigger_ok" -eq 1 ] && pass "background skills carry user-invocable: false and commands do not, and the generated command and skill folders all hold exactly the expected names"

# ---------------------------------------------------------------------------
echo "== Frontmatter =="

seen_names=""
skillfiles=$(find "$SKILLS" -mindepth 2 -maxdepth 2 -name SKILL.md | sort)
while IFS= read -r file; do
  [ -n "$file" ] || continue
  folder=$(basename "$(dirname "$file")")
  fm_name=$(awk '/^---[ \t]*$/{fm++;next} fm==1 && /^name:[ \t]/{sub("^name:[ \t]*","");print;exit}' "$file")
  fm_desc=$(awk '/^---[ \t]*$/{fm++;next} fm==1 && /^description:[ \t]/{sub("^description:[ \t]*","");print;exit}' "$file")

  if [ -z "$fm_name" ]; then
    fail "$file: missing frontmatter name"
  elif [ "$fm_name" != "$folder" ]; then
    fail "$file: frontmatter name '$fm_name' does not match folder '$folder'"
  fi

  if [ -z "$fm_desc" ]; then
    fail "$file: missing or empty frontmatter description"
  fi

  if [ -n "$fm_name" ]; then
    if printf '%s\n' "$seen_names" | grep -qx "$fm_name"; then
      fail "$file: duplicate skill name '$fm_name'"
    fi
    seen_names=$(printf '%s\n%s' "$seen_names" "$fm_name")
  fi
done <<SKILLFILES
$skillfiles
SKILLFILES

pass "frontmatter checked on $(printf '%s\n' "$skillfiles" | grep -c .) SKILL.md files"

# ---------------------------------------------------------------------------
echo "== References =="

# Every local Markdown link resolves.
mdfiles=$(find "$ROOT" -name '*.md' -not -path '*/.git/*' | sort)
while IFS= read -r mdfile; do
  [ -n "$mdfile" ] || continue
  # The public README lives one level down in the maintainer source, then moves
  # to the release root. Resolve its links where readers will open them.
  case "$mdfile" in
    "$ROOT/README.md") dir=$ROOT ;;
    *) dir=$(dirname "$mdfile") ;;
  esac
  matches=$(grep -noE '\[[^]]*\]\([^)]*\)' "$mdfile" || true)
  [ -n "$matches" ] || continue
  while IFS=: read -r lineno full; do
    [ -n "$lineno" ] || continue
    inside="${full#*(}"
    path="${inside%)}"
    case "$path" in
      http://*|https://*|mailto:*|"#"*|"") continue ;;
    esac
    path_noanchor="${path%%#*}"
    [ -n "$path_noanchor" ] || continue
    case "$mdfile:$path_noanchor" in
      *:/*)
        target="$ROOT$path_noanchor"
        ;;
      *)
        target="$dir/$path_noanchor"
        ;;
    esac
    # The public README's links resolve from the release root, where the files
    # it points at sit beside it. They sit beside it here too now, so no detour
    # is needed; the branch is kept because a link may still be written relative
    # to the release rather than to this tree.
    if [ "$mdfile" = "$ROOT/README.md" ] && [ ! -e "$target" ] \
      && [ -e "$ROOT/$path_noanchor" ]; then
      target="$ROOT/$path_noanchor"
    fi
    if [ ! -e "$target" ]; then
      fail "$mdfile:$lineno: broken link -> $path"
    fi
  done <<MATCHES
$matches
MATCHES
done <<MDFILES
$mdfiles
MDFILES

# Every skill/reference/template path named anywhere (including backtick code
# spans, not just markdown links) resolves.
pathrefs=$(grep -rnoE --include='*.md' -- \
  '\.agents/(skills|tests|guard|hooks|tools)/[A-Za-z0-9_./-]+\.(md|sh)' \
  "$ROOT" 2>/dev/null | sort -u || true)
while IFS=: read -r reffile lineno relpath; do
  [ -n "$relpath" ] || continue
  # .agents/hooks/session-start.sh is a project path that start creates from
  # templates/foundation/session-start.sh. It deliberately does not exist in
  # this repository, because the kit's own source must never wire a project
  # session hook into itself. Its real source is asserted separately below.
  # .agents/hooks/state-guard.sh is the same kind of project path, made from
  # templates/foundation/state-guard.sh, and state-guard.sh holds its source.
  case "$relpath" in
    .agents/hooks/session-start.sh|.agents/hooks/state-guard.sh) continue ;;
  esac
  target="$ROOT/$relpath"
  if [ ! -e "$target" ]; then
    fail "$reffile:$lineno: referenced path does not exist -> $relpath"
  fi
done <<PATHREFS
$pathrefs
PATHREFS

pass "markdown links and skill/reference/template paths resolve"

# Bare relative references written inside skill files (references/foo.md,
# templates/foo.md, recipes/foo.md, or the cross-skill sibling form
# other-skill/references/foo.md, other-skill/recipes/foo.md)
# resolve relative to (a) the containing file's own directory, or (b) the
# skills root, whichever exists. The check above only catches references
# already spelled out with a full .agents/... path prefix.
#
# A file in another skill is written as the `other-skill` skill's
# `references/foo.md`, since the skills folder differs from one installation
# to the next. That form is read as other-skill/references/foo.md, including
# when the line breaks between the skill's name and its path.
skillmdfiles=$(find "$SKILLS" -name '*.md' | sort)
relpat='(references|templates|recipes)/[A-Za-z0-9_./-]+[.]md|[a-z][a-z-]*/(references|templates|recipes)/[A-Za-z0-9_./-]+[.]md'
qualifiedpat='[.]agents/(skills|tests|guard|hooks|tools)/[A-Za-z0-9_./-]+[.](md|sh)'
relhits=$(printf '%s\n' "$skillmdfiles" | while IFS= read -r f; do
  [ -n "$f" ] || continue
  awk -v pat="$relpat" -v qualified="$qualifiedpat" -v q="'" '
    BEGIN {
      named = "`[a-z][a-z-]*` skill" q "s `"
      named_at_end = "`[a-z][a-z-]*` skill" q "s[ \t]*$"
    }
    FNR == 1 { carry = "" }
    {
      line = $0
      if (carry != "") {
        sub(/^[ \t]*`/, "`" carry "/", line)
        carry = ""
      }
      while (match(line, named)) {
        name = substr(line, RSTART + 1)
        sub(/`.*$/, "", name)
        line = substr(line, 1, RSTART - 1) "`" name "/" substr(line, RSTART + RLENGTH)
      }
      if (match(line, named_at_end)) {
        carry = substr(line, RSTART + 1)
        sub(/`.*$/, "", carry)
        line = substr(line, 1, RSTART - 1)
      }
      gsub(qualified, "", line)
      rest = line
      while (match(rest, pat)) {
        print FILENAME ":" FNR ":" substr(rest, RSTART, RLENGTH)
        rest = substr(rest, RSTART + RLENGTH)
      }
    }
  ' "$f"
done)
while IFS=: read -r reffile lineno relpath; do
  [ -n "$relpath" ] || continue
  dir=$(dirname "$reffile")
  if [ -e "$dir/$relpath" ] || [ -e "$SKILLS/$relpath" ]; then
    continue
  fi
  fail "$reffile:$lineno: relative reference does not resolve (tried $dir/$relpath and $SKILLS/$relpath) -> $relpath"
done <<RELHITS
$relhits
RELHITS
pass "bare relative skill references (references/*.md, templates/*.md, recipes/*.md, sibling-skill form) resolve"

# Recipes. A recipe is one build stack paired with one place to run it, and
# ship/references/recipe-format.md says what one must hold. The folder is the
# menu, so a file in it is offered to somebody founding a project. Each one
# must have the shape the format asks for and carry real dates. Each must also
# have its own rehearsal that sources the rule-shape helper and names the
# recipe file, because a recipe joins the menu only once offline rehearsals
# guard its rules, and a rehearsal that only exits cleanly guards nothing. The
# blank is held to the same shape so it cannot drift from the format it is
# copied from. Shared parts sit in recipes/parts/, are held to the lines a
# section carries, and are never read as menu entries: the glob below takes
# only the files directly in recipes/. The folder may be empty, since the
# format came before the first recipe.
recipe_checker="$ROOT/.agents/tools/check-recipes.sh"
recipe_blank="$SKILLS/ship/templates/recipe.md"
recipe_ok=1
if [ ! -x "$recipe_checker" ]; then
  fail ".agents/tools/check-recipes.sh is missing or not executable"
  recipe_ok=0
else
  if ! "$recipe_checker" --template "$recipe_blank" >&2; then
    fail "$recipe_blank: the recipe blank does not have the shape the format asks for"
    recipe_ok=0
  fi
  for recipe_part in "$SKILLS"/ship/recipes/parts/*.md; do
    [ -f "$recipe_part" ] || continue
    if ! "$recipe_checker" --part "$recipe_part" >&2; then
      fail "$recipe_part: the shared part does not carry the lines a section needs"
      recipe_ok=0
    fi
  done
  for recipe in "$SKILLS"/ship/recipes/*.md; do
    [ -f "$recipe" ] || continue
    recipe_name=$(basename "$recipe" .md)
    if ! "$recipe_checker" "$recipe" >&2; then
      fail "$recipe: the recipe does not have the shape the format asks for"
      recipe_ok=0
    fi
    if ! "$recipe_checker" --rehearsal "$recipe" "$ROOT/.agents/tests/recipe-$recipe_name.sh" >&2; then
      fail "$recipe: no rehearsal in .agents/tests/recipe-$recipe_name.sh guards it"
      recipe_ok=0
    fi
  done
fi
[ "$recipe_ok" -eq 0 ] || pass "every recipe, shared part and the recipe blank have the shape the format asks for"

# team.md must not exist and must not be referenced anywhere tracked.
if [ -e "$SKILLS/setup-ai-build-kit/templates/team.md" ]; then
  fail "team.md still exists; it was removed from the workflow"
fi
# setup-ai-build-kit/SKILL.md and MAINTAINING.md are excluded: they name team.md only to
# say it's gone (an explicit "do not create this" and a description of this
# very check), not to describe it as part of the live workflow.
teamrefs=$(grep -rln --include='*.md' --include='*.sh' --include='*.toml' -- 'team\.md' "$ROOT" 2>/dev/null \
  | grep -v '/\.git/' \
  | grep -v '\.agents/tools/validate-kit\.sh$' \
  | grep -v '\.agents/skills/setup-ai-build-kit/SKILL\.md$' \
  | grep -v 'docs/MAINTAINING\.md$' \
  || true)
if [ -n "$teamrefs" ]; then
  fail "team.md is referenced in: $(printf '%s' "$teamrefs" | tr '\n' ' ')"
else
  pass "no stray team.md references"
fi

# ---------------------------------------------------------------------------
echo "== Record matches machinery =="

# The maintainer AGENTS.md is the written record of the checks this repository
# runs, and the promise that the documents are the asset only holds while that
# record stays true. The CI matrix is already kept level with the tests folder
# further down. This is the other half: a check that gets added and wired into
# CI but never written into AGENTS.md is caught here rather than drifting
# unnoticed, which is how grader-recovery.sh once slipped the record. mutate.sh
# audits the suite rather than being one of the checks, the same carve-out the
# matrix comparison makes.
agentsmd="$ROOT/AGENTS.md"
if [ ! -f "$agentsmd" ]; then
  fail "$agentsmd: missing"
else
  rec_ok=1
  for testscript in "$ROOT"/.agents/tests/*.sh; do
    [ -f "$testscript" ] || continue
    base=$(basename "$testscript")
    [ "$base" != "mutate.sh" ] || continue
    if ! grep -qF ".agents/tests/$base" "$agentsmd"; then
      fail "AGENTS.md does not name the maintainer check .agents/tests/$base"
      rec_ok=0
    fi
  done
  [ "$rec_ok" -eq 1 ] && pass "AGENTS.md names every maintainer check under .agents/tests/"
fi

# Keep the project template short enough to read every session. The maintainer's
# own AGENTS.md has a different job and is outside this ceiling.
#
# The ceiling applies to the file a project ends up with, not to the template.
# Founding writes the project line, the capability profile, the stack section
# and its recipe line, and a framework's own starter may append its rules block
# too. A template of 196 lines passed here while a fresh founding came out at
# 219, so the template must leave room for a fixed budget of founding's lines:
# the 23 that founding measured on the recipe campaign, and the 10 of the
# Next.js starter's block, with a margin of 5 more under the ceiling.
founding_budget=33
founding_margin=5
foundation_agents="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
if [ ! -f "$foundation_agents" ]; then
  fail "$foundation_agents: missing"
else
  foundation_lines=$(awk 'END { print NR }' "$foundation_agents")
  if [ $((foundation_lines + founding_budget + founding_margin)) -lt 200 ]; then
    pass "the foundation instructions leave room for founding under 200 lines ($foundation_lines + $founding_budget + $founding_margin)"
  else
    fail "the foundation instructions have $foundation_lines lines; with founding's $founding_budget and a margin of $founding_margin they reach 200"
  fi
fi

# The tie-breaker between a written instruction and an automatic check lives in
# the project's standing instructions, so a session that finds the two in
# conflict trusts the check rather than the stale rule. Checked where a project
# receives it, the foundation AGENTS.md template.
tiebreaker="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
if [ ! -f "$tiebreaker" ]; then
  fail "$tiebreaker: missing"
elif ! tr '\n' ' ' < "$tiebreaker" | grep -qF -- "an instruction can fall out"; then
  fail "$tiebreaker: does not tell a session to trust the check when an instruction and a check disagree"
else
  pass "the foundation instructions make the check the tie-breaker over a stale instruction"
fi

# ---------------------------------------------------------------------------
echo "== Fit-check contract =="

fitcheck="$SKILLS/setup-ai-build-kit/references/fit-check.md"
if [ ! -f "$fitcheck" ]; then
  fail "$fitcheck: missing"
else
  fc_ok=1
  for needle in "Explore privately" "Build and run it" "Build with care" \
    "### 1. Build with care" "### 2. Build and run it" "### 3. Explore privately"; do
    if ! grep -qF "$needle" "$fitcheck"; then
      fail "$fitcheck: missing expected text '$needle'"
      fc_ok=0
    fi
  done
  [ "$fc_ok" -eq 1 ] && pass "fit-check.md carries the three canonical paths and the decision-order headings"
fi

# The build-path block has one owner. fit-check.md defines the fields and the
# masterplan template carries them, so a field added to one and forgotten in the
# other would leave a project recording something the fit check never writes, or
# writing something the template has no room for.
mpt="$SKILLS/setup-ai-build-kit/templates/masterplan.md"
if [ ! -f "$mpt" ] || [ ! -f "$fitcheck" ]; then
  fail "cannot compare the build-path block: fit-check.md or the masterplan template is missing"
else
  bp_ok=1
  for field in Path Why "Sensitive areas" Accepted "Recheck when" "Last checked"; do
    grep -q "^$field:" "$mpt" || { fail "$mpt: build-path block is missing '$field:'"; bp_ok=0; }
    grep -q "^$field:" "$fitcheck" || { fail "$fitcheck: build-path block is missing '$field:'"; bp_ok=0; }
  done
  [ "$bp_ok" -eq 1 ] && \
    pass "the masterplan template and fit-check.md agree on the build-path fields, including Accepted"
fi

# ---------------------------------------------------------------------------
echo "== Pieces contract =="

# A piece's shape has one owner, pieces.md, and one form a project fills in.
# The two are written separately and read by different audiences, so nothing
# stops them drifting apart except this.
pieces="$SKILLS/setup-ai-build-kit/references/pieces.md"
pieceform="$SKILLS/setup-ai-build-kit/templates/foundation/piece-issue.yml"
if [ ! -f "$pieces" ] || [ ! -f "$pieceform" ]; then
  fail "the pieces contract is incomplete: expected $pieces and $pieceform"
else
  pc_ok=1
  # The body sections, spelled the same in both places.
  for section in "So that" "Done when" "Evidence" "Not in this piece" "Decided"; do
    grep -qF "## $section" "$pieces" || \
      { fail "$pieces: does not define the '$section' section"; pc_ok=0; }
    grep -qF "label: $section" "$pieceform" || \
      { fail "$pieceform: has no field for '$section'"; pc_ok=0; }
  done
  # The subject labels, which decide evidence and save route, so a label the
  # skills do not know about is worse than a missing one. Matched on the table
  # row rather than the whole file: each label is also named in the prose that
  # explains it, so a loose search keeps passing after the row itself changed.
  for label in visual "how it works" data "accounts and permissions" \
               finance "external service" "background automation"; do
    grep -qF "| \`$label\` |" "$pieces" || \
      { fail "$pieces: the subject table does not define '$label'"; pc_ok=0; }
  done
  # A piece is allowed to be about more than one thing. Where that is unwritten
  # the agent picks the closest single subject and silently drops the evidence
  # the other one required, which is the fault this vocabulary replaced.
  grep -qF "A piece carries every subject label that fits it" "$pieces" || \
    { fail "$pieces: does not say a piece carries every subject that fits"; pc_ok=0; }
  # Matched against the definition list rather than the whole file. A state
  # label is also mentioned in the prose that explains it, so a loose search
  # keeps passing after the definition itself has been renamed.
  # The four states, the six shaping sub-states and the three types, each a
  # definition line. The gate script creates the same set, and gate-script.sh
  # reads it back from a stand-in GitHub.
  for label in state:shaping state:ready state:building state:in-review \
               shaping:raw shaping:research shaping:clarify shaping:prototype \
               shaping:spec shaping:check type:feature type:bug type:chore; do
    grep -qF -- "- \`$label\`," "$pieces" || \
      { fail "$pieces: the state label list does not define '$label'"; pc_ok=0; }
  done
  # The form applies no label. A form-opened issue has no state until the
  # gate's report names it and /shape takes it in through the gate, and a
  # default subject would be chosen before anybody read the piece.
  if grep -q '^labels:' "$pieceform"; then
    fail "$pieceform: applies a label by default; a form-opened issue carries none"
    pc_ok=0
  fi
  [ "$pc_ok" -eq 1 ] && \
    pass "pieces.md and the issue form agree on the sections and the label set"
fi

# The issues are shared, so people assign, close and relabel them by hand. Where
# that behaviour is unwritten, each skill invents its own answer and the answers
# disagree, which is how an agent ends up undoing somebody's deliberate change.
if [ -f "$pieces" ]; then
  dg_ok=1
  grep -qF "## When somebody acts on GitHub" "$pieces" || \
    { fail "$pieces: does not say what happens when a person acts on GitHub"; dg_ok=0; }
  # Matched on the claim rather than the heading, because the heading can
  # survive a rewrite that drops the rule underneath it.
  grep -qF "A person's action wins." "$pieces" || \
    { fail "$pieces: does not state that a person's action wins"; dg_ok=0; }
  grep -qF "Absence is not a decision" "$pieces" || \
    { fail "$pieces: does not state that absence is not a decision"; dg_ok=0; }
  grep -qF "The agent says what it found." "$pieces" || \
    { fail "$pieces: does not state that the agent says what it found"; dg_ok=0; }
  # The four cases an agent is most likely to quietly correct on its own.
  for act in "Assigns somebody else" "Puts two subject labels" \
             "Uses milestones or a project board" "Deletes an issue"; do
    grep -qF "$act" "$pieces" || \
      { fail "$pieces: no answer for what happens when a person does this: $act"; dg_ok=0; }
  done
  [ "$dg_ok" -eq 1 ] && \
    pass "pieces.md answers what happens when a person acts on GitHub directly"
fi

# Anybody can open an issue in half a sentence, so the list has entries nobody
# sized. Built as though they were finished pieces, the agent guesses what done
# means, which is the one thing a piece exists to stop. Shaping lives in /shape.
shapefile="$SKILLS/shape/SKILL.md"
whatnowfile="$SKILLS/what-now/SKILL.md"
refresh="$SKILLS/setup-ai-build-kit/templates/foundation/plan-refresh.sh"
if [ -f "$pieces" ] && [ -f "$shapefile" ] && [ -f "$whatnowfile" ] && [ -f "$refresh" ]; then
  nr_ok=1
  grep -qF "## An issue somebody typed by hand" "$pieces" || \
    { fail "$pieces: does not say that a hand-typed issue is a request"; nr_ok=0; }
  # Shape rather than the label, so an unlabelled note is still caught.
  grep -qF 'An issue with no `## Done when` has not been sized' "$pieces" || \
    { fail "$pieces: does not make the missing 'Done when' section the test"; nr_ok=0; }
  grep -qF "original words underneath" "$shapefile" || \
    { fail "$shapefile: does not keep the person's own words through refining"; nr_ok=0; }
  # The way out has to be offered with the shaping. Mentioned afterwards, the
  # command becomes a trap for somebody who only wanted something built.
  grep -qF '"not now"' "$shapefile" || \
    { fail "$shapefile: offers no way out of the build offer"; nr_ok=0; }
  grep -qF "still notes rather than pieces" "$whatnowfile" || \
    { fail "$whatnowfile: does not say how many entries are still notes"; nr_ok=0; }
  grep -qF "still a note" "$refresh" || \
    { fail "$refresh: the printout does not mark the entries that are still notes"; nr_ok=0; }
  [ "$nr_ok" -eq 1 ] && \
    pass "a hand-typed issue is treated as a request, with a way out of the interview"
fi

# what-now voices the signals it already reads: a failing check, an open
# review finding, and a setup step left half-done each get named rather than
# hidden under "nothing is blocked", and the answer closes with a plain recap of
# recent work. The read step gathered these all along; the contract is that the
# say step speaks them.
if [ -f "$whatnowfile" ]; then
  wn_ok=1
  grep -qF "### Failing check" "$whatnowfile" || \
    { fail "$whatnowfile: no recovery route names a failing check"; wn_ok=0; }
  grep -qF "### Open review finding" "$whatnowfile" || \
    { fail "$whatnowfile: no recovery route names an open review finding"; wn_ok=0; }
  grep -qF "### Unfinished setup step" "$whatnowfile" || \
    { fail "$whatnowfile: no recovery route names an unfinished setup step"; wn_ok=0; }
  grep -qF "short recap of where the tool has got to" "$whatnowfile" || \
    { fail "$whatnowfile: does not close with a recap of recent work"; wn_ok=0; }
  [ "$wn_ok" -eq 1 ] && \
    pass "what-now voices a failing check, an open finding, an unfinished setup step, and a recap"
fi

# The command split: shape prepares work and moves a piece to `state:ready`; implement
# builds only ready pieces and refuses to shape, sending an unready piece back to
# shape rather than guessing past its open question.
implementfile="$SKILLS/implement/SKILL.md"
if [ -f "$implementfile" ] && [ -f "$shapefile" ] && [ -f "$pieces" ]; then
  split_ok=1
  grep -qF '`state:ready`, shaped and checked' "$pieces" || \
    { fail "$pieces: does not define the ready label"; split_ok=0; }
  grep -qF "it does not shape" "$implementfile" || \
    { fail "$implementfile: does not say it builds rather than shapes"; split_ok=0; }
  grep -qF "does not settle the question" "$implementfile" || \
    { fail "$implementfile: does not send an unready piece to shape instead of settling it"; split_ok=0; }
  grep -qF "Shape itself never builds" "$shapefile" || \
    { fail "$shapefile: does not say shape never builds"; split_ok=0; }
  grep -qF 'label it `ready`' "$shapefile" || \
    { fail "$shapefile: does not mark a shaped piece ready"; split_ok=0; }
  [ "$split_ok" -eq 1 ] && \
    pass "shape prepares and marks ready; implement builds only ready pieces and redirects the rest"
fi

# The layered piece: a plain surface that stays comprehensive about the
# product, a collapsed "under the hood" tier the builder reads, a self-sufficiency
# bar before an unwatched auto run, and groundwork kept to a vertical slice.
layer_sbfile="$SKILLS/section-builder/SKILL.md"
if [ -f "$pieces" ] && [ -f "$implementfile" ] && [ -f "$layer_sbfile" ]; then
  layer_ok=1
  grep -qF "## The two layers of a piece" "$pieces" || \
    { fail "$pieces: does not describe the surface / under-the-hood layers"; layer_ok=0; }
  grep -qF "<details><summary>Under the hood</summary>" "$pieces" || \
    { fail "$pieces: the piece template has no collapsed under-the-hood section"; layer_ok=0; }
  grep -qF "self-sufficient enough to build without a person present" "$implementfile" || \
    { fail "$implementfile: auto mode does not require a piece self-sufficient without a person"; layer_ok=0; }
  grep -qF "expand-then-contract sequence that keeps the checks green" "$layer_sbfile" || \
    { fail "$layer_sbfile: does not constrain groundwork to a vertical slice or expand-then-contract"; layer_ok=0; }
  [ "$layer_ok" -eq 1 ] && \
    pass "the piece is layered: plain surface, under-the-hood build tier, a self-sufficiency bar for auto, and vertical-only groundwork"
fi

# GitHub issues are the only record: plan.md is retired, and a missing GitHub
# tool is a guided, required setup step rather than a file-based fallback.
capfile="$SKILLS/setup-ai-build-kit/references/capability-check.md"
if [ -f "$pieces" ] && [ -f "$capfile" ]; then
  gh_ok=1
  grep -qF "only record of what is left" "$pieces" || \
    { fail "$pieces: does not say the issues are the only record"; gh_ok=0; }
  if grep -qF "plan.md" "$pieces"; then
    fail "$pieces: still refers to the retired plan.md record"; gh_ok=0
  fi
  grep -qF "required setup step" "$capfile" || \
    { fail "$capfile: does not make the GitHub tool a required setup step"; gh_ok=0; }
  if grep -qF "working fallback" "$capfile"; then
    fail "$capfile: still calls a missing GitHub tool a working fallback"; gh_ok=0
  fi
  [ "$gh_ok" -eq 1 ] && \
    pass "GitHub issues are the only record; a missing tool is a guided setup step"
fi

# Sub-issues for a piece made of parts: the rule that keeps a part
# (same outcome) apart from a blocked-by piece (different outcome), a container
# parent /implement does not build directly, and a printout that reads the parts.
refreshtool="$SKILLS/setup-ai-build-kit/templates/foundation/plan-refresh.sh"
if [ -f "$pieces" ] && [ -f "$implementfile" ] && [ -f "$refreshtool" ]; then
  sub_ok=1
  grep -qF "Same outcome means a sub-issue; a different outcome" "$pieces" || \
    { fail "$pieces: does not give the sub-issue versus blocked-by rule"; sub_ok=0; }
  grep -qF "A piece with open parts is a container" "$implementfile" || \
    { fail "$implementfile: does not skip a parent with open parts"; sub_ok=0; }
  grep -qF "Made of parts" "$refreshtool" || \
    { fail "$refreshtool: does not show a parent as made of parts"; sub_ok=0; }
  [ "$sub_ok" -eq 1 ] && \
    pass "a piece made of parts uses sub-issues, the parent is a container, and the printout reads the parts"
fi

# A project founded before the /shape and /implement split needs migrating: its
# issues carry no `ready` label, so /maintain backfills it, and moves a leftover
# plan.md into issues where one survives from the old fallback.
maintfile="$SKILLS/maintain/SKILL.md"
if [ -f "$maintfile" ]; then
  mig_ok=1
  grep -qF 'Backfill the `ready` label' "$maintfile" || \
    { fail "$maintfile: does not backfill the ready label for a pre-split project"; mig_ok=0; }
  grep -qF 'Move a `plan.md` into issues' "$maintfile" || \
    { fail "$maintfile: does not move a leftover plan.md into issues"; mig_ok=0; }
  grep -qF 'Remove a stale `start` skill' "$maintfile" || \
    { fail "$maintfile: does not tidy a stale start skill after the setup-ai-build-kit rename"; mig_ok=0; }
  grep -qF 'Remove a stale `plan` skill' "$maintfile" || \
    { fail "$maintfile: does not tidy a stale plan skill after the shape rename"; mig_ok=0; }
  grep -qF 'the update removed the old skill without adding the new' "$maintfile" || \
    { fail "$maintfile: the rename migration cannot recover a project whose update removed the old skill without adding the new one"; mig_ok=0; }
  [ "$mig_ok" -eq 1 ] && \
    pass "maintain migrates a project founded before /shape and /implement, and before the setup-ai-build-kit and shape renames"
fi

# Every release asks what an existing user must do to upgrade (real users since
# v0.5): MAINTAINING.md carries that standing check when a release is cut.
mfile="$ROOT/docs/MAINTAINING.md"
if [ -f "$mfile" ]; then
  grep -qF "what an existing user must do to upgrade" "$mfile" || \
    fail "$mfile: the release checklist does not ask what an existing user must do to upgrade"
fi

# Shape stays shaping: the build offer points at a fresh session for every piece
#, and clarify records a settled term on the piece rather than committing
# the masterplan mid-plan, so a planning session opens no pull request.
clarifyfile="$SKILLS/clarify/SKILL.md"
if [ -f "$shapefile" ] && [ -f "$clarifyfile" ]; then
  pp_ok=1
  grep -qF "A fresh session is the offer for every piece" "$shapefile" || \
    { fail "$shapefile: build offer does not point at a fresh session for every piece"; pp_ok=0; }
  grep -qF "Planning records and stops; writing to the masterplan is a build" "$clarifyfile" || \
    { fail "$clarifyfile: clarify still writes the masterplan mid-plan instead of recording on the piece"; pp_ok=0; }
  [ "$pp_ok" -eq 1 ] && \
    pass "plan offers a fresh session and never writes the masterplan mid-plan"
fi

# Build mechanics and pull-request hygiene: a piece starts from up-to-date main
#; a new issue is unassigned until pickup; a direct push to main is
# blocked and merged branches auto-delete; the agent opens the pull
# request and stops, leaving the merge to a person.
sbfile="$SKILLS/section-builder/SKILL.md"
blocked="$SKILLS/setup-ai-build-kit/references/blocked-commands.md"
settings="$SKILLS/setup-ai-build-kit/templates/foundation/claude-settings.json"
startfile="$SKILLS/setup-ai-build-kit/SKILL.md"
shapefile="$SKILLS/shape/SKILL.md"
if [ -f "$sbfile" ] && [ -f "$blocked" ] && [ -f "$settings" ] && [ -f "$startfile" ] && [ -f "$shapefile" ]; then
  mech_ok=1
  grep -qF "save route including the checkpoint route" "$sbfile" || \
    { fail "$sbfile: does not start every piece from up-to-date main"; mech_ok=0; }
  # The one exception: a piece in a run that stacks on a piece built earlier in
  # that run starts from that piece's branch, so the stack merges in order.
  grep -qF "A piece in a run that stacks on another piece built in that run" "$sbfile" || \
    { fail "$sbfile: does not start a stacked piece in a run from the branch it stacks on"; mech_ok=0; }
  grep -qF "starts unassigned" "$shapefile" || \
    { fail "$shapefile: does not say a new issue starts unassigned"; mech_ok=0; }
  grep -qF 'never push a change directly to `main`' "$blocked" || \
    { fail "$blocked: does not block a direct push to main"; mech_ok=0; }
  grep -qF "git push * main" "$settings" || \
    { fail "$settings: deny list does not block a direct push to main"; mech_ok=0; }
  grep -qF "delete_branch_on_merge" "$startfile" || \
    { fail "$startfile: does not enable auto-deletion of merged branches"; mech_ok=0; }
  # Whether the pull-request route may merge is the one merge step's rule, in
  # section-builder's references/merge.md, and one-merge-step.sh guards it.
  [ "$mech_ok" -eq 1 ] && \
    pass "pieces start from fresh main or the branch they stack on in a run, new issues are unassigned, main is push-guarded, and merged branches auto-delete"
fi

# Machine-check-first evidence: where a machine can check a piece, that
# check runs and must pass before the piece is called done. The softer proofs
# are for the claims a machine cannot judge, not a way around one it could.
if [ -f "$sbfile" ]; then
  mc_ok=1
  grep -qF "a substitute for a check that was available and skipped" "$sbfile" || \
    { fail "$sbfile: does not forbid a softer proof standing in for an available machine check"; mc_ok=0; }
  grep -qF "machine check run and green" "$sbfile" || \
    { fail "$sbfile: 'Done when' does not name the available machine check as run and green"; mc_ok=0; }
  [ "$mc_ok" -eq 1 ] && \
    pass "an available machine check runs and must pass before a piece is called done"
fi

# The plan migration is deleted and stays deleted. No project needs it, and a
# route nobody exercises would ship untested while reading as supported.
syncfile="$SKILLS/sync/SKILL.md"
if [ -f "$syncfile" ]; then
  if grep -qF "Moving an existing plan into issues" "$syncfile"; then
    fail "$syncfile: the plan migration route is back; it ships untested"
  else
    pass "sync carries no plan migration route"
  fi
fi

# ---------------------------------------------------------------------------
echo "== Plain-language onboarding contract =="

startfile="$SKILLS/setup-ai-build-kit/SKILL.md"
if [ ! -f "$startfile" ]; then
  fail "$startfile: missing"
else
  ob_ok=1
  for needle in "## 1. Orientation" "## Conversation contract" \
    "Finishing an internal step is not a user-facing result by itself" \
    "Routine reading, research, setup, and checking happen quietly" \
    "Do not announce that a confirmation might appear later" \
    "references/completion-report.md"; do
    if ! tr '\n' ' ' < "$startfile" | grep -qFi -- "$needle"; then
      fail "$startfile: missing expected text '$needle' (progressive onboarding contract)"
      ob_ok=0
    fi
  done
  [ "$ob_ok" -eq 1 ] && pass "setup-ai-build-kit/SKILL.md carries an opening orientation and a plain-language completion report"
fi

capfile="$SKILLS/setup-ai-build-kit/references/capability-check.md"
if [ ! -f "$capfile" ]; then
  fail "$capfile: missing"
else
  cap_ok=1
  for needle in "A suitable name and email label are configured for saving project versions." \
    "Online authentication works, when uploads, pull requests, or online checks"; do
    if ! tr '\n' ' ' < "$capfile" | grep -qFi -- "$needle"; then
      fail "$capfile: missing expected text '$needle' (save identity must stay separate from remote authentication)"
      cap_ok=0
    fi
  done
  [ "$cap_ok" -eq 1 ] && pass "capability-check.md records save identity separately from remote authentication"
fi

# GitHub puts nine labels on a new repository and the kit uses none of them.
# Founding is the one moment they can go, because no issue exists yet to be
# wearing one. Both halves are checked: the deletion, and the sentence that
# keeps it from reading as a licence to remove somebody's own labels later.
if [ -f "$startfile" ] && [ -f "$pieces" ] && [ -f "$capfile" ]; then
  gl_ok=1
  for label in bug documentation duplicate "good first issue" "help wanted" \
               invalid question wontfix enhancement; do
    grep -qF "\`$label\`" "$startfile" || \
      { fail "$startfile: does not name GitHub's '$label' label among the ones founding removes"; gl_ok=0; }
  done
  grep -qF "delete the labels GitHub made by itself" "$startfile" || \
    { fail "$startfile: founding does not delete the labels GitHub made by itself"; gl_ok=0; }
  grep -qF "Say which ones went" "$startfile" || \
    { fail "$startfile: founding removes labels without saying which"; gl_ok=0; }
  grep -qF "After founding they are somebody's to keep" "$pieces" || \
    { fail "$pieces: does not limit the label clearout to founding"; gl_ok=0; }
  grep -qF "cannot create or delete labels" "$capfile" || \
    { fail "$capfile: says nothing about an account that cannot delete a label"; gl_ok=0; }
  [ "$gl_ok" -eq 1 ] && \
    pass "founding clears GitHub's own labels, says which went, and stops there"
fi

manualfile="$SKILLS/setup-ai-build-kit/references/manual-setup.md"
if [ ! -f "$manualfile" ]; then
  fail "$manualfile: missing"
elif ! tr '\n' ' ' < "$manualfile" | grep -qFi -- "Never copy the latest repository author"; then
  fail "$manualfile: missing the rule against copying the latest repository author's identity"
else
  pass "manual-setup.md prohibits copying the latest author identity"
fi

# Only the fenced example shape counts as "shown to the user" here; the
# surrounding translation table legitimately names npm/Git internals, the
# same way AGENTS.md's own banned-word list has to contain the words it bans.
completionfile="$SKILLS/setup-ai-build-kit/references/completion-report.md"
if [ ! -f "$completionfile" ]; then
  fail "$completionfile: missing"
else
  shape=$(awk '/^```md$/{p=1;next} /^```$/{p=0} p' "$completionfile")
  leaked_phrases="npm test
npm start
ahead of the remote
working tree is clean"
  leak_found=0
  while IFS= read -r phrase; do
    [ -n "$phrase" ] || continue
    if printf '%s\n' "$shape" | tr '\n' ' ' | grep -qFi -- "$phrase"; then
      fail "$completionfile: unexplained technical phrase '$phrase' inside the user-facing report shape"
      leak_found=1
    fi
  done <<LEAKED
$leaked_phrases
LEAKED
  [ "$leak_found" -eq 1 ] || pass "the user-facing report shape in completion-report.md keeps npm/Git internals out"
fi

# start ends on a clean cut, not an in-session build offer: the empty
# project is named as expected, the work is said to be saved, and the person is
# pointed at a fresh session with /implement rather than offered a build here.
cc_ok=1
for needle in "which is how it should look at this point" \
              "start a fresh chat" \
              "/implement"; do
  if ! tr '\n' ' ' < "$completionfile" | tr -s ' ' | grep -qF -- "$needle"; then
    fail "$completionfile: missing '$needle' (clean-cut ending)"
    cc_ok=0
  fi
done
# The in-session build offer an earlier release shipped must be gone: it was
# reversed on purpose.
if tr '\n' ' ' < "$completionfile" | tr -s ' ' | grep -qF -- "so you finish with something you can see"; then
  fail "$completionfile: still contains the in-session build offer that was removed on purpose"
  cc_ok=0
fi
[ "$cc_ok" -eq 1 ] && pass "start ends on a clean cut naming /implement, and frames the empty project as normal"

starteragents="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
scenarios="$ROOT/.agents/tests/scenarios.md"
quiet_ok=1
for item in \
  "$starteragents|Keep progress updates tied to a decision, blocker, or visible outcome" \
  "$starteragents|Immediately before a technical confirmation" \
  "$scenarios|## 25. Quiet /setup-ai-build-kit stand-up" \
  "$scenarios|Harness-generated technical text is outside the kit's control"; do
  file=${item%%|*}
  needle=${item#*|}
  if ! tr '\n' ' ' < "$file" | grep -qFi -- "$needle"; then
    fail "$file: missing expected text '$needle' (quiet onboarding contract)"
    quiet_ok=0
  fi
done
[ "$quiet_ok" -eq 1 ] && pass "start keeps routine technical activity behind the scenes across harnesses"

syncfile="$SKILLS/sync/SKILL.md"
# The project check is the job the capability profile records, which is an
# adopted project's own CI where it has one, so sync names that record rather
# than a fixed job.
if ! grep -qF 'update the job the capability profile'"'"'s `Project check:` line records' "$syncfile"; then
  fail "$syncfile: does not identify the standalone project check"
elif grep -qF 'both `if:` conditions' "$syncfile"; then
  fail "$syncfile: still treats private source conditions as part of every project"
else
  pass "sync updates the standalone project check while preserving older layouts"
fi

# ---------------------------------------------------------------------------
echo "== Interview question shape =="

# A machine cannot judge whether an interview felt like a conversation, so this
# only proves the rule is still written down where the interview reads it. The
# guided interview review in scenarios.md is what proves the behaviour.
grillfile="$SKILLS/clarify/SKILL.md"
scenariofile="$ROOT/.agents/tests/scenarios.md"
shape_ok=1
for item in \
  "$grillfile|Match the question to the shape of its answer" \
  "$grillfile|narrate is asked in plain words" \
  "$startfile|Ask every question in the shape clarify's" \
  "$scenariofile|## 26. Interview question shape"; do
  file=${item%%|*}
  needle=${item#*|}
  if ! tr '\n' ' ' < "$file" | grep -qFi -- "$needle"; then
    fail "$file: missing expected text '$needle' (interview question shape contract)"
    shape_ok=0
  fi
done
[ "$shape_ok" -eq 1 ] && pass "clarify says which questions may be offered as choices and which are asked in plain words"

# ---------------------------------------------------------------------------
echo "== First-use plain language =="

# When start names a tool the person must act on, it says what the tool is in
# the same breath, and manual setup does the same. A throwaway prototype is
# built to look like the real thing rather than narrating in its own interface
# that it is a prototype. These prove the rules stay written where the skills
# read them.
fu_ok=1
for item in \
  "$startfile|say what it is in one plain sentence at the same moment" \
  "$manualfile|say what that is in one plain sentence too" \
  "$SKILLS/clarify/references/decision-prototype.md|not like a labelled prototype"; do
  file=${item%%|*}
  needle=${item#*|}
  if ! tr '\n' ' ' < "$file" | tr -s ' ' | grep -qF -- "$needle"; then
    fail "$file: missing expected text '$needle' (first-use plain-language contract)"
    fu_ok=0
  fi
done
[ "$fu_ok" -eq 1 ] && pass "a named tool is explained in one sentence, and a throwaway prototype is not labelled as one"

# ---------------------------------------------------------------------------
echo "== Ship control-flow contract =="

# Operational readiness and go-live belong inside the path branches that use
# them (Build and run it, Build with care), never as a shared section after
# all three branches; that shape is what let Explore privately be read as
# reaching launch instructions despite its own branch saying to stop. The
# anchor is the last branch heading, so a rename of that heading without a
# matching change here would let the check pass on nothing.
shipfile="$SKILLS/ship/SKILL.md"
if [ ! -f "$shipfile" ]; then
  fail "$shipfile: missing"
else
  leaked=$(awk '
    /^### Build with care/ { seen=1; next }
    seen && /^## [^#]/ {
      low = tolower($0)
      if (low ~ /go live/ || low ~ /operational readiness/) print NR ": " $0
    }
  ' "$shipfile")
  if [ -n "$leaked" ]; then
    fail "$shipfile: a go-live or operational-readiness heading appears after all three path branches, so every path reaches it: $leaked"
  else
    pass "ship/SKILL.md keeps go-live and operational-readiness steps inside their path branches"
  fi

  # The recipe's checks move work to a live address, so they sit inside Build
  # and run it, which Build with care follows for everything outside its
  # areas. Placed after the last branch, they would be a shared step that
  # Explore privately could be read as reaching.
  recipe_at=$(awk '
    /^### Build and run it/ { inrun=1; next }
    /^### / { inrun=0 }
    /^#+ On a recipe/ { print (inrun ? "inside" : "outside"); exit }
  ' "$shipfile")
  if [ "$recipe_at" = inside ]; then
    pass "ship/SKILL.md keeps the recipe's checks inside Build and run it"
  else
    fail "$shipfile: the 'On a recipe' checks are ${recipe_at:-missing}, not inside Build and run it"
  fi
fi

# ---------------------------------------------------------------------------
echo "== Codex adapter claims =="

# Codex has never had a generated adapter tree; it reads .agents/skills/
# directly. scenarios.md and MAINTAINING.md are maintainer-only and already
# excluded by the same convention as the team.md check below.
codex_docs=$(find "$ROOT" -name '*.md' -not -path '*/.git/*' | sort \
  | grep -v '\.agents/tests/scenarios\.md$' \
  | grep -v 'docs/MAINTAINING\.md$' || true)

# A 3-line sliding window catches the stale phrasing even if it's soft-wrapped,
# without joining the whole file (which would false-positive on any document
# that simply discusses all four tools in separate paragraphs, in order).
codex_group_hits=$(printf '%s\n' "$codex_docs" | while IFS= read -r f; do
  [ -n "$f" ] || continue
  awk '
    { buf[NR] = $0; window = $0
      if (NR > 1) window = buf[NR-1] " " window
      if (NR > 2) window = buf[NR-2] " " window
      if (window ~ /[.]claude\// && window ~ /[.]cursor\// && window ~ /[.]gemini\// && window ~ /[.]codex\//) {
        print FILENAME ":" NR
      }
    }
  ' "$f"
done)
if [ -n "$codex_group_hits" ]; then
  fail ".codex/ still listed alongside the generated adapter trees, as if it were one, in: $(printf '%s' "$codex_group_hits" | tr '\n' ' ')"
fi

codex_active_hits=$(printf '%s\n' "$codex_docs" | while IFS= read -r f; do
  [ -n "$f" ] || continue
  grep -noE '.{0,40}\.codex/skills.{0,40}' "$f" 2>/dev/null | sed "s#^#$f:#"
done | while IFS=: read -r ffile lineno rest; do
  [ -n "$lineno" ] || continue
  # Keep a case block out of this $(...) pipeline: the older /bin/sh shipped
  # by macOS mistakes its closing pattern for the command substitution's end.
  if printf '%s\n' "$rest" | grep -qE 'does not exist|no longer exists|not exist'; then
    :
  else
    echo "$ffile:$lineno: $rest"
  fi
done)
if [ -n "$codex_active_hits" ]; then
  fail ".codex/skills mentioned without saying it doesn't exist: $(printf '%s' "$codex_active_hits" | tr '\n' ' | ')"
fi

if [ -z "$codex_group_hits" ] && [ -z "$codex_active_hits" ]; then
  pass "no document describes .codex/ as generated or .codex/skills as active"
fi

# ---------------------------------------------------------------------------
echo "== Build-path vocabulary =="

canonical_paths="Explore privately
Build and run it
Build with care"

# Checked per file, with the lineno:content split done by parameter
# expansion rather than `read`, because `read` silently drops a trailing
# field delimiter (a line that is exactly "Path:" would otherwise lose its
# colon and misparse as the value "Path").
pathfiles=$(grep -rlE --include='*.md' -- '^Path:' \
  "$ROOT/.agents" "$ROOT/AGENTS.md" 2>/dev/null || true)
while IFS= read -r pf; do
  [ -n "$pf" ] || continue
  matches=$(grep -nE '^Path:' "$pf")
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    lineno=${entry%%:*}
    content=${entry#*:}
    value=${content#Path:}
    # trim leading spaces/tabs
    while [ "${value# }" != "$value" ]; do value=${value# }; done
    while [ "${value#	}" != "$value" ]; do value=${value#	}; done
    [ -n "$value" ] || continue
    if ! printf '%s\n' "$canonical_paths" | grep -qx "$value" \
      && ! printf '%s' "$value" | grep -qE '^<.*>$'; then
      fail "$pf:$lineno: non-canonical build path value '$value'"
    fi
  done <<MATCHES
$matches
MATCHES
done <<PATHFILES
$pathfiles
PATHFILES

# The gate names went with the redesign that made the kit stop refusing. What
# it does now is give a risk notice the person can accept on the record, so a
# stray "expert gate" would describe a barrier that no longer exists. The two
# paths named for who you had to hire went the same way, with the field that
# recorded the hiring level and the brief written for the hire.
stale_terms="six questions
six outcomes
stakes section
Verdict:
build it and run it yourself
fix the design first
have it built for you
expert gate
expert-gated
Build with expert help
Professional-led
Required controls:
Outside help:
help level
expert brief
four build paths
levels of outside help"
had_stale=0
while IFS= read -r term; do
  [ -n "$term" ] || continue
  hits=$(grep -rlFi --include='*.md' -- "$term" "$ROOT/.agents" "$ROOT/docs" \
    "$ROOT/README.md" "$ROOT/WORKFLOW.md" "$ROOT/AGENTS.md" "$ROOT/starter" 2>/dev/null \
    | grep -v '/\.git/' \
    | grep -v '\.agents/tests/scenarios\.md$' \
    | grep -v 'docs/MAINTAINING\.md$' \
    | grep -v '\.agents/skills/maintain/SKILL\.md$' \
    || true)
  # maintain/SKILL.md is excluded because its migration has to name the old
  # fields and paths it recognises on disk; nothing else may use them.
  if [ -n "$hits" ]; then
    fail "retired vocabulary '$term' found in: $(printf '%s' "$hits" | tr '\n' ' ')"
    had_stale=1
  fi
done <<STALETERMS
$stale_terms
STALETERMS
[ "$had_stale" -eq 1 ] || pass "only canonical build-path names appear"

# ---------------------------------------------------------------------------
echo "== Adapter generation =="

if [ -x "$ROOT/.agents/tools/build-adapters.sh" ]; then
  if "$ROOT/.agents/tools/build-adapters.sh" --check; then
    pass "generated adapters match .agents/skills/, no drift, no stale adapter files"
  else
    fail "generated adapters are out of date; run .agents/tools/build-adapters.sh and commit the result"
  fi
else
  fail ".agents/tools/build-adapters.sh is missing or not executable"
fi

# ---------------------------------------------------------------------------
echo "== Session start contract =="

session_template="$SKILLS/setup-ai-build-kit/templates/foundation/session-start.sh"
session_settings="$SKILLS/setup-ai-build-kit/templates/foundation/claude-settings.json"
maintenance_template="$SKILLS/setup-ai-build-kit/templates/maintenance-record"
ss_ok=1

[ -f "$session_template" ] || { fail "$session_template: missing"; ss_ok=0; }
[ -f "$maintenance_template" ] || { fail "$maintenance_template: missing"; ss_ok=0; }

# The saved mode is what a project receives, so check the saved mode rather
# than this working copy, which may sit on a disk that does not keep one.
session_mode=$(git -C "$ROOT" ls-files -s -- \
  ".agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh" | cut -d' ' -f1)
if [ "$session_mode" != "100755" ]; then
  fail "$session_template: must be saved as a runnable file (found mode '$session_mode')"
  ss_ok=0
fi

# This repository maintains the kit and is not a project built with it.
[ ! -e "$ROOT/.agents/hooks/session-start.sh" ] || \
  { fail "the maintainer source contains a project session-start hook"; ss_ok=0; }
if grep -qF 'SessionStart' "$ROOT/.claude/settings.json"; then
  fail "the maintainer source wired a project session-start hook into its own settings"
  ss_ok=0
fi

grep -qF 'SessionStart' "$session_settings" || \
  { fail "$session_settings: does not wire the project session hook"; ss_ok=0; }
grep -qF '.agents/hooks/session-start.sh' "$session_settings" || \
  { fail "$session_settings: session-start wiring does not name the project hook"; ss_ok=0; }

for entry in \
  "$SKILLS/setup-ai-build-kit/scripts/bootstrap-project.sh|session-start.sh|.agents/hooks/session-start.sh" \
  "$SKILLS/setup-ai-build-kit/SKILL.md|templates/maintenance-record" \
  "$SKILLS/maintain/SKILL.md|.ai-build-kit-maintenance" \
  "$SKILLS/maintain/SKILL.md|last-light-pass" \
  "$SKILLS/maintain/SKILL.md|last-full-pass" \
  "$SKILLS/what-now/SKILL.md|.ai-build-kit-maintenance" \
  "$ROOT/WORKFLOW.md|maintain writes the date of each visit" \
  "$ROOT/docs/COMPATIBILITY.md|Said automatically when a session opens" \
  "$scenarios|## 27. Session opens on a project past its check-up cadence"; do
  file=${entry%%|*}
  needle=${entry#*|}
  if ! tr '\n' ' ' < "$file" | grep -qF -- "$needle"; then
    fail "$file: missing expected text '$needle' (session-start contract)"
    ss_ok=0
  fi
done

[ "$ss_ok" -eq 1 ] && pass "the check-up reminder is a project hook, wired from start's template and absent from this source"

# A founded project's settings carry the state guard: a hook that refuses a
# direct change to a state:, shaping: or review: label, and deny rules for the
# same. This repository's own issues keep today's labels until the release, so
# its own settings carry neither. state-guard.sh runs this block on its own,
# on a copy with the hook or a rule planted, so keep it between its markers.
# --- own settings carry no state guard: begin
if grep -qE 'state-guard|(state|shaping|review):|issues/\*/labels' "$ROOT/.claude/settings.json"; then
  fail "the maintainer source carries the state guard hook or its deny rules in its own settings"
else
  pass "this repository's own settings carry neither the state guard hook nor its deny rules"
fi
# --- own settings carry no state guard: end

# ---------------------------------------------------------------------------
echo "== Release boundary =="

release_check="$ROOT/.agents/tests/release-builder.sh"
if [ -x "$release_check" ]; then
  if "$release_check"; then
    pass "starter assembles repeatably from the declared allowlist"
  else
    fail "starter release boundary check failed"
  fi
else
  fail ".agents/tests/release-builder.sh is missing or not executable"
fi

rehearsal_check="$ROOT/.agents/tests/starter-rehearsal.sh"
if [ -x "$rehearsal_check" ]; then
  if "$rehearsal_check"; then
    pass "starter stands up as a new saved project with founding templates"
  else
    fail "disposable starter rehearsal failed"
  fi
else
  fail ".agents/tests/starter-rehearsal.sh is missing or not executable"
fi

publication_check="$ROOT/.agents/tests/release-publication.sh"
if [ -x "$publication_check" ]; then
  if "$publication_check"; then
    pass "starter publication handles first and later releases"
  else
    fail "starter publication rehearsal failed"
  fi
else
  fail ".agents/tests/release-publication.sh is missing or not executable"
fi

session_check="$ROOT/.agents/tests/session-start.sh"
if [ -x "$session_check" ]; then
  if "$session_check"; then
    pass "the check-up reminder behaves across install routes and cadences"
  else
    fail "session-start rehearsal failed"
  fi
else
  fail ".agents/tests/session-start.sh is missing or not executable"
fi

# Every `[ -x ... ]` guard in this file is unreliable on a disk that reports
# each file as runnable, which is what a Windows mount does. A script saved
# without its runnable bit passes here and fails on the hosted checks, or worse
# reaches a project that was told to run it by path. The saved mode is the only
# honest answer, so it is checked directly.
# A named list of scripts goes stale the moment somebody adds one, which is how
# three files under .agents/tests/ came to be run by path while saved as
# ordinary text. Every tracked file that opens with a shebang is asked instead.
# A file this repository only ever sources, or only ever hands to sh, is invoked
# a different way and does not need the bit.
mode_ok=1
git -C "$ROOT" ls-files -s | while read -r saved _ _ script; do
  [ -f "$ROOT/$script" ] || continue
  [ "$(head -c 2 "$ROOT/$script" 2>/dev/null)" = '#!' ] || continue
  base=${script##*/}
  if git -C "$ROOT" grep -qE \
    "(^|[[:space:];&|(])(\.|source)[[:space:]]+[^[:space:];)]*$base" -- . 2>/dev/null; then
    continue
  fi
  if git -C "$ROOT" grep -qE \
    "(^|[[:space:];&|(])(sh|bash|dash|zsh)[[:space:]]+[^[:space:];)]*$base" -- . 2>/dev/null; then
    continue
  fi
  [ "$saved" = "100755" ] || \
    printf '%s\n' "$script: is run by path but is not saved as runnable (found mode '$saved')"
done > /tmp/validate-kit-modes.$$
if [ -s /tmp/validate-kit-modes.$$ ]; then
  while IFS= read -r offender; do
    fail "$offender"
  done < /tmp/validate-kit-modes.$$
  mode_ok=0
fi
rm -f /tmp/validate-kit-modes.$$
[ "$mode_ok" -eq 1 ] && pass "every script the kit runs by path is saved as runnable"

printout_check="$ROOT/.agents/tests/plan-printout.sh"
if [ -x "$printout_check" ]; then
  if "$printout_check" >/dev/null 2>&1; then
    pass "the printout groups a repair, a claim, a block, and says why a piece waits"
  else
    fail "plan printout check failed; run .agents/tests/plan-printout.sh to see why"
  fi
else
  fail ".agents/tests/plan-printout.sh is missing or not executable"
fi

recovery_check="$ROOT/.agents/tests/grader-recovery.sh"
if [ -x "$recovery_check" ]; then
  if "$recovery_check" >/dev/null 2>&1; then
    pass "the grader parser recovers a missing final brace and still refuses a mid-truncation"
  else
    fail "grader recovery check failed; run .agents/tests/grader-recovery.sh to see why"
  fi
else
  fail ".agents/tests/grader-recovery.sh is missing or not executable"
fi

state_check="$ROOT/.agents/tests/replay-state.sh"
if [ -x "$state_check" ]; then
  if "$state_check" >/dev/null 2>&1; then
    pass "the replay harness grades the world, and the acceptance-record assertion fails when it should"
  else
    fail "replay state-grading check failed; run .agents/tests/replay-state.sh to see why"
  fi
else
  fail ".agents/tests/replay-state.sh is missing or not executable"
fi

# The contract parser is a machine check that existed but never ran here, which
# is how the /setup scenarios' cases were wired while the parser still demanded a
# risk notice they do not carry. Running it on every push is the rule
# that a check which exists must run and pass.
parser_check="$ROOT/.agents/tests/replay/check-parser.sh"
if [ -f "$parser_check" ]; then
  if sh "$parser_check" >/dev/null 2>&1; then
    pass "the replay harness reads every scenario contract, and the risk pair is required together"
  else
    fail "replay contract parser failed; run .agents/tests/replay/check-parser.sh to see why"
  fi
else
  fail ".agents/tests/replay/check-parser.sh is missing"
fi

# Several rules live as prose a coding agent reads, watched by hand rather than
# replayed, and each is guarded by a check that reads its source and proves it
# fails on a copy with the rule removed. They share the scaffolding in
# .agents/tests/lib/rule-shape.sh, so they are found by that rather than by a
# list here, and a new one is covered from the moment it is written.
shape_ok=1
shape_count=0
for shape_check in "$ROOT"/.agents/tests/*.sh; do
  [ -f "$shape_check" ] || continue
  grep -qF 'lib/rule-shape.sh' "$shape_check" || continue
  shape_name=$(basename "$shape_check")
  shape_count=$((shape_count + 1))
  if [ ! -x "$shape_check" ]; then
    fail ".agents/tests/$shape_name is not executable"
    shape_ok=0
  elif ! "$shape_check" >/dev/null 2>&1; then
    fail "written-rule check failed; run .agents/tests/$shape_name to see why"
    shape_ok=0
  fi
done
if [ "$shape_count" -eq 0 ]; then
  fail "no written-rule checks were found; they source .agents/tests/lib/rule-shape.sh"
elif [ "$shape_ok" -eq 1 ]; then
  pass "$shape_count written rules still hold, and each check catches a weakened copy"
fi

claude_plugin_check="$ROOT/.agents/tests/claude-plugin.sh"
if [ ! -x "$claude_plugin_check" ]; then
  fail ".agents/tests/claude-plugin.sh is missing or not executable"
elif command -v claude >/dev/null 2>&1; then
  if "$claude_plugin_check"; then
    pass "Claude plugin exposes the nine commands, prepares a project, recovers, updates, and uninstalls in isolation"
  else
    fail "Claude plugin rehearsal failed"
  fi
else
  note "Claude Code is unavailable; skipped the isolated plugin rehearsal"
fi

agent_plugin_check="$ROOT/.agents/tests/agent-plugin.sh"
if [ -x "$agent_plugin_check" ]; then
  if "$agent_plugin_check"; then
    pass "the Agent Plugins folder matches the standard and stands a project up on its own"
  else
    fail "Agent Plugins rehearsal failed"
  fi
else
  fail ".agents/tests/agent-plugin.sh is missing or not executable"
fi

# ---------------------------------------------------------------------------
echo "== Shell and configuration =="

shfiles=$(find "$ROOT/.agents" -name '*.sh' | sort)
while IFS= read -r shfile; do
  [ -n "$shfile" ] || continue
  if sh -n "$shfile" 2>/tmp/validate-kit-shcheck.$$; then
    :
  else
    fail "$shfile: sh -n reported a syntax error: $(cat /tmp/validate-kit-shcheck.$$)"
  fi
  rm -f /tmp/validate-kit-shcheck.$$
done <<SHFILES
$shfiles
SHFILES
pass "shell syntax checked on $(printf '%s\n' "$shfiles" | grep -c .) scripts"

jsonfiles="$ROOT/.claude/settings.json
$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json
$ROOT/.claude-plugin/plugin.json
$ROOT/.claude-plugin/marketplace.json
$ROOT/agent-plugin/plugin.json"
if command -v python3 >/dev/null 2>&1; then
  while IFS= read -r jsonfile; do
    [ -n "$jsonfile" ] || continue
    if python3 -c "import json; json.load(open('$jsonfile'))" 2>/tmp/validate-kit-json.$$; then
      :
    else
      fail "$jsonfile failed to parse as JSON: $(cat /tmp/validate-kit-json.$$)"
    fi
    rm -f /tmp/validate-kit-json.$$
  done <<JSONFILES
$jsonfiles
JSONFILES
  pass "Claude settings and plugin metadata parse as JSON"
else
  note "python3 not available; skipped JSON parse of Claude settings and plugin metadata"
fi

plugin_manifest="$ROOT/.claude-plugin/plugin.json"
plugin_marketplace="$ROOT/.claude-plugin/marketplace.json"
plugin_contract_ok=yes
for literal in \
  '"name": "ai-build-kit"' \
  '"./.claude/commands/fix.md"' \
  '"./.claude/commands/implement.md"' \
  '"./.claude/commands/maintain.md"' \
  '"./.claude/commands/shape.md"' \
  '"./.claude/commands/ship.md"' \
  '"./.claude/commands/setup-ai-build-kit.md"' \
  '"./.claude/commands/sync.md"' \
  '"./.claude/commands/what-now.md"' \
  '"./.claude/skills/change-triage"' \
  '"./.claude/skills/clarify"' \
  '"./.claude/skills/screen-check"' \
  '"./.claude/skills/second-opinion"' \
  '"./.claude/skills/section-builder"'; do
  if ! grep -qF "$literal" "$plugin_manifest"; then
    fail "Claude plugin manifest is missing: $literal"
    plugin_contract_ok=no
  fi
done
for literal in \
  '"name": "ai-build-kit"' \
  '"source": "./"'; do
  if ! grep -qF "$literal" "$plugin_marketplace"; then
    fail "Claude plugin marketplace is missing: $literal"
    plugin_contract_ok=no
  fi
done
maintain_skill="$ROOT/.agents/skills/maintain/SKILL.md"
for literal in \
  'claude plugin marketplace update ai-build-kit' \
  'claude plugin update ai-build-kit@ai-build-kit --scope <scope>' \
  'npx skills add gwpicard/ai-build-kit' \
  'For an Agent Plugins installation'; do
  if ! grep -qF "$literal" "$maintain_skill"; then
    fail "maintain does not preserve the installation route: $literal"
    plugin_contract_ok=no
  fi
done
if [ "$plugin_contract_ok" = "yes" ]; then
  pass "Claude plugin identity, source, and update routes match the contract"
fi

agent_plugin_manifest="$ROOT/agent-plugin/plugin.json"
agent_plugin_ok=yes
if [ ! -f "$agent_plugin_manifest" ]; then
  fail "the Agent Plugins manifest is missing: agent-plugin/plugin.json"
  agent_plugin_ok=no
else
  for literal in \
    '"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"' \
    '"name": "ai-build-kit"'; do
    if ! grep -qF "$literal" "$agent_plugin_manifest"; then
      fail "Agent Plugins manifest is missing: $literal"
      agent_plugin_ok=no
    fi
  done
  for forbidden in '"displayName"' '"commands"' '"skills"' '.claude/'; do
    if grep -qF "$forbidden" "$agent_plugin_manifest"; then
      fail "Agent Plugins manifest carries something the standard does not define: $forbidden"
      agent_plugin_ok=no
    fi
  done
fi
if [ "$agent_plugin_ok" = "yes" ]; then
  pass "the Agent Plugins manifest declares the 1.0.0 schema and keeps to its permitted fields"
fi

# ---------------------------------------------------------------------------
echo "== Version-bearing files =="

# Three files tell an installation which version it is, and both installers read
# whichever branch they are pointed at. Each was pinned to the development
# placeholder on its own, and nothing compared them, so a half-stamped tree was
# invisible: one file could say v0.11.0 while the other two still said
# development, and every check passed.
#
# So check the thing that matters. All three agree, and the value is either the
# placeholder, which is what an unreleased branch carries, or a plain version,
# which is what a released one carries. `stamp-version.sh` is what moves them
# between those two states, together.
version_files_ok=yes
claude_version=$(sed -nE 's/^[[:space:]]*"version": "([^"]*)".*/\1/p' "$plugin_manifest")
agent_version=$(sed -nE 's/^[[:space:]]*"version": "([^"]*)".*/\1/p' "$agent_plugin_manifest")
maintain_version=$(cat "$ROOT/.agents/skills/maintain/VERSION" 2>/dev/null || echo "")

for counted in "$plugin_manifest:$claude_version" "$agent_plugin_manifest:$agent_version"; do
  counted_file=${counted%:*}
  counted_value=${counted#*:}
  # `grep -c` prints 0 and exits 1 when nothing matches. `|| echo 0` would append
  # a second line, and the comparison below would then error rather than fire,
  # so a reformatted manifest would pass validation and fail at release time.
  found=$(grep -cE '^[[:space:]]*"version": "[^"]*",?$' "$counted_file" 2>/dev/null || true)
  [ -n "$found" ] || found=0
  if [ "$found" -ne 1 ]; then
    fail "${counted_file#"$ROOT"/}: expected exactly one version field, found $found; the release stamp would match nothing and ship a stale number"
    version_files_ok=no
  elif [ -z "$counted_value" ]; then
    fail "${counted_file#"$ROOT"/}: the version field is empty"
    version_files_ok=no
  fi
done

if [ "$claude_version" != "$agent_version" ]; then
  fail "the two plugin manifests disagree about the version: '$claude_version' and '$agent_version'"
  version_files_ok=no
fi
if [ "$maintain_version" != "v$claude_version" ]; then
  fail ".agents/skills/maintain/VERSION says '$maintain_version' while the plugin manifests say '$claude_version'"
  version_files_ok=no
fi
case "$claude_version" in
  0.0.0-development) ;;
  *)
    if ! printf '%s\n' "$claude_version" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'; then
      fail "the version-bearing files carry '$claude_version', which is neither the development placeholder nor a stable version"
      version_files_ok=no
    fi
    ;;
esac

stamper="$ROOT/.agents/tools/stamp-version.sh"
if [ ! -x "$stamper" ]; then
  fail ".agents/tools/stamp-version.sh is missing or not executable"
  version_files_ok=no
fi

if [ "$version_files_ok" = "yes" ]; then
  pass "the three version-bearing files agree, at '$claude_version'"
fi

# tomllib arrived in python3.11. tomli is the same parser backported, and is
# what a machine on 3.10 is likely to have, so try both before giving up. This
# matters more than it looks: the note below is easy to scroll past, and a
# machine that always prints it is running a quietly smaller check than the
# hosted one while reporting the same "all checks passed".
toml_reader=""
if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import tomllib' >/dev/null 2>&1; then
    toml_reader=tomllib
  elif python3 -c 'import tomli' >/dev/null 2>&1; then
    toml_reader=tomli
  fi
fi
if [ -n "$toml_reader" ]; then
  tomlfiles=$(find "$ROOT/.gemini" -name '*.toml' 2>/dev/null | sort)
  while IFS= read -r tomlfile; do
    [ -n "$tomlfile" ] || continue
    if ! python3 -c "import $toml_reader as t; t.load(open('$tomlfile','rb'))" 2>/tmp/validate-kit-toml.$$; then
      fail "$tomlfile failed to parse as TOML: $(cat /tmp/validate-kit-toml.$$)"
    fi
    rm -f /tmp/validate-kit-toml.$$
  done <<TOMLFILES
$tomlfiles
TOMLFILES
  pass "TOML command files parsed, using $toml_reader"
else
  note "neither tomllib nor tomli is available; skipped TOML parse, adapter --check still covers content drift"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' >/dev/null 2>&1; then
  github_yaml_files=$(find "$ROOT/.github" \
    \( -name '*.yml' -o -name '*.yaml' \) | sort)
  while IFS= read -r github_yaml_file; do
    [ -n "$github_yaml_file" ] || continue
    if ! python3 -c "import yaml; yaml.safe_load(open('$github_yaml_file'))" 2>/tmp/validate-kit-yaml.$$; then
      fail "$github_yaml_file failed to parse as YAML: $(cat /tmp/validate-kit-yaml.$$)"
    fi
    rm -f /tmp/validate-kit-yaml.$$
  done <<GITHUBYAMLFILES
$github_yaml_files
GITHUBYAMLFILES
  pass "GitHub configuration files parse as YAML"

  # Parsing is not the same as being the right shape. A run block written as a
  # literal scalar ends the moment a line is indented less than the block, and
  # what follows becomes a top-level key. The document still parses, and a check
  # that reads `jobs` still finds it, so nothing local complains. GitHub rejects
  # the workflow outright and reports a nought-second failure against the push.
  #
  # That happened to the workflow this check sits beside. So the keys are named,
  # and anything else is a run block that ended early. `on` is absent from the
  # list because YAML reads it as the boolean true.
  for wf in "$ROOT"/.github/workflows/*.yml "$ROOT"/.github/workflows/*.yaml; do
    [ -f "$wf" ] || continue
    stray=$(python3 - "$wf" <<'STRAYKEYS'
import sys, yaml
known = {"name", True, "on", "permissions", "concurrency", "jobs", "env",
         "defaults", "run-name"}
doc = yaml.safe_load(open(sys.argv[1])) or {}
print(" ".join(repr(k) for k in doc if k not in known))
STRAYKEYS
)
    if [ -n "$stray" ]; then
      fail "$(basename "$wf") has a top-level key that is not a workflow key, which is what a run block ending early looks like: $stray"
    fi
  done
  pass "no workflow has a stray top-level key from a run block ending early"

  # Structural contract: private source validation and the public starter's
  # deliberately failing project check are separate workflows, and every
  # rehearsal in .agents/tests/ runs on a pull request here.
  py_script=/tmp/validate-kit-workflow.$$
  cat > "$py_script" <<'PYEOF'
import os, sys, yaml
errors = []

source_doc = yaml.safe_load(open(sys.argv[1]))
source_jobs = source_doc.get("jobs") or {}
if set(source_jobs.keys()) != {"source-kit-validation", "rehearsal"}:
    errors.append("source workflow must contain source-kit-validation and rehearsal")
sk = source_jobs.get("source-kit-validation") or {}
# The kit is kept in two repositories while the old one keeps the history, so
# the gate names both, and nothing else.
gate = "github.repository == 'gwpicard/ai-build-kit' || github.repository == 'gwpicard/ai-loop-kit'"
if sk.get("if") != gate:
    errors.append("source-kit-validation.if is wrong: %r" % sk.get("if"))
sk_runs = " ".join(step.get("run", "") for step in (sk.get("steps") or []) if isinstance(step, dict))
if "build-adapters.sh --check" not in sk_runs:
    errors.append("source-kit-validation is missing a build-adapters.sh --check step")
if "validate-kit.sh" not in sk_runs:
    errors.append("source-kit-validation is missing a validate-kit.sh step")

# A rehearsal nobody runs proves nothing. One hosted job for each rehearsal
# named a failure on the checks list, but each job was billed a whole minute
# to do a few seconds of work. They run in one job now, through a runner that
# reads the folder, so a rehearsal cannot be added without being run.
rehearsal = source_jobs.get("rehearsal") or {}
if rehearsal.get("if") != gate:
    errors.append("rehearsal.if is wrong: %r" % rehearsal.get("if"))
rehearsal_runs = " ".join(step.get("run", "") for step in (rehearsal.get("steps") or []) if isinstance(step, dict))
if ".agents/tests/run-all.sh" not in rehearsal_runs:
    errors.append("rehearsal does not run .agents/tests/run-all.sh")

tests_dir = sys.argv[3]
runner = os.path.join(tests_dir, "run-all.sh")
if not os.path.isfile(runner):
    errors.append("the rehearsal runner .agents/tests/run-all.sh is missing")
elif not os.access(runner, os.X_OK):
    errors.append(".agents/tests/run-all.sh is not executable")
else:
    runner_text = open(runner).read()
    # The folder is the list. Reading a glob rather than a written-out set is
    # what makes an unrun rehearsal impossible rather than merely checked for.
    if ".agents/tests/*.sh" not in runner_text:
        errors.append("run-all.sh must read .agents/tests/*.sh, so the folder is the list")
    # mutate.sh audits the suite rather than passing or failing, so it is
    # deliberately not a rehearsal.
    if "mutate" not in runner_text:
        errors.append("run-all.sh must skip mutate.sh, which audits rather than passes or fails")
    # One failure must never hide another, which is what fail-fast: false gave
    # the matrix. Whether the loop still holds that is a question only running
    # it can settle, so rehearsal-runner.sh runs it against stub scripts.
    if 'failed="$failed' not in runner_text:
        errors.append("run-all.sh must collect every failure rather than stopping at one")

project_doc = yaml.safe_load(open(sys.argv[2]))
project_jobs = project_doc.get("jobs") or {}
if set(project_jobs.keys()) != {"project-check"}:
    errors.append("starter workflow must contain only project-check")
pc = project_jobs.get("project-check") or {}
if "if" in pc:
    errors.append("starter project-check must not depend on a repository identity")
pc_runs = " ".join(step.get("run", "") for step in (pc.get("steps") or []) if isinstance(step, dict))
if "This check is still the placeholder" not in pc_runs:
    errors.append("project-check no longer carries the deliberately failing placeholder")
if errors:
    sys.stderr.write("\n".join(errors) + "\n")
    sys.exit(1)
PYEOF
  if python3 "$py_script" \
    "$ROOT/.github/workflows/source-checks.yml" \
    "$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml" \
    "$ROOT/.agents/tests" \
    2>/tmp/validate-kit-workflow-out.$$; then
    pass "private source validation and public project checks stay separate"
  else
    fail "source and starter workflow structure: $(cat /tmp/validate-kit-workflow-out.$$)"
  fi
  rm -f "$py_script" /tmp/validate-kit-workflow-out.$$
else
  workflow_files=$(find "$ROOT/.github/workflows" \
    -name '*.yml' -o -name '*.yaml' | sort)
  while IFS= read -r workflow_file; do
    [ -n "$workflow_file" ] || continue
    if ! grep -q '^on:' "$workflow_file" || ! grep -q '^jobs:' "$workflow_file"; then
      fail "$workflow_file is missing expected top-level keys (on:, jobs:)"
    fi
  done <<WORKFLOWFILES
$workflow_files
WORKFLOWFILES
  note "no PyYAML available; did a basic top-level-key check on GitHub workflows instead of a full parse"
  source_checks="$ROOT/.github/workflows/source-checks.yml"
  project_checks="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml"
  # The whole gate expression, not a bare repository name. The retired name
  # contained this one as a prefix, so a grep for the shorter name would pass
  # against the longer one and guard nothing.
  for literal in "source-kit-validation:" \
    "rehearsal:" \
    ".agents/tests/run-all.sh" \
    "if: github.repository == 'gwpicard/ai-build-kit'"; do
    if ! grep -qF "$literal" "$source_checks"; then
      fail "source checks: missing expected line '$literal' (no PyYAML available)"
    fi
  done
  runner="$ROOT/.agents/tests/run-all.sh"
  if [ ! -x "$runner" ]; then
    fail "the rehearsal runner .agents/tests/run-all.sh is missing or not executable"
  elif ! grep -qF ".agents/tests/*.sh" "$runner" || ! grep -qF 'failed="$failed' "$runner"; then
    fail "run-all.sh must read the tests folder and collect every failure (no PyYAML available)"
  fi
  if ! grep -qF "project-check:" "$project_checks" || \
     grep -qF "github.repository" "$project_checks"; then
    fail "starter project check is missing or depends on a repository identity"
  fi
fi

# Hosted maintainer validation normally runs on pull requests. A maintainer-only
# non-main push fallback also covers repositories where GitHub accepts the
# branch update but does not create the pull_request run.
branch_checks="$ROOT/.github/workflows/maintainer-branch-check.yml"
fallback_ok=yes
if [ ! -f "$branch_checks" ]; then
  fail "maintainer-only non-main branch check is missing"
  fallback_ok=no
elif ! awk '
  $0 == "on:" { in_on=1; next }
  in_on && /^[^ ]/ { in_on=0; in_push=0 }
  in_on && /^  [^ ]/ { in_push=($0 == "  push:") }
  in_push && $0 == "    branches-ignore:" { in_ignored_branches=1; next }
  in_push && in_ignored_branches && $0 == "      - main" { ignores_main=1 }
  END { exit !ignores_main }
' "$branch_checks"; then
  fail "maintainer branch check must run on non-main branch pushes"
  fallback_ok=no
elif ! awk '
  $0 == "permissions:" { in_permissions=1; next }
  in_permissions && /^[^ ]/ { in_permissions=0 }
  in_permissions && $0 == "  contents: read" { read_only_contents=1 }
  $0 == "      - uses: actions/checkout@v6" { in_checkout=1; next }
  in_checkout && $0 == "        with:" { in_checkout_options=1; next }
  in_checkout_options && $0 == "          persist-credentials: false" { drops_credential=1 }
  in_checkout && /^      - / { in_checkout=0; in_checkout_options=0 }
  END { exit !(read_only_contents && drops_credential) }
' "$branch_checks"; then
  fail "maintainer branch check must be read-only and must not retain its checkout credential"
  fallback_ok=no
fi
if [ -f "$branch_checks" ]; then
  for literal in \
    "if: github.repository == 'gwpicard/ai-build-kit'" \
    "uses: actions/checkout@v6" \
    "run: .agents/tools/build-adapters.sh --check" \
    "run: .agents/tools/validate-kit.sh"; do
    if ! grep -qF "$literal" "$branch_checks"; then
      fail "maintainer branch check is missing: $literal"
      fallback_ok=no
    fi
  done
fi
if [ "$fallback_ok" = "yes" ]; then
  pass "maintainer-only non-main branch validation fallback matches the contract"
fi

# Deny-list parity: permissions.deny must be exactly the set of entries that
# mirror .agents/guard/blocked-commands.md's mechanically enforceable
# patterns (git reset --hard, git push --force/-f, git clean -f/-fd, rm -rf).
# An exact set comparison catches a missing OR an unexplained extra entry,
# not just a missing substring. Both this repository's own Claude settings and
# the settings start gives a project are checked. A project's also carry the
# session-start wiring and the state guard hook, which this source must not.
deny_jsonfiles="$ROOT/.claude/settings.json
$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json"
expected_deny="Bash(git reset --hard:*)
Bash(git push --force:*)
Bash(git push -f:*)
Bash(git clean -f:*)
Bash(git clean -fd:*)
Bash(rm -rf:*)"
# A project the kit founds also blocks a direct push to main, which keeps
# changes flowing through a pull request. This maintainer repository's own
# settings deliberately do not carry that entry, so the two sets differ here.
# A founded project also refuses a recursive delete in every spelling the deny
# list can see, and the two Git commands that clear its recovery history. The
# maintainer's own settings are left as they are.
# A founded project also refuses a direct change to a state:, shaping: or
# review: label, which only the gate script makes. Each of those rules ends in
# a doubled star. A rule ending in `:*` is Claude Code's older prefix form,
# where the colon stands for a space, so `state:*` would never match
# `state:ready`. The doubled star keeps the colon as written. This
# repository's own issues keep today's labels until the release, so its own
# settings carry none of these.
expected_deny_project="$expected_deny
Bash(rm -r:*)
Bash(rm -R:*)
Bash(rm -fr:*)
Bash(rm -Rf:*)
Bash(rm -fR:*)
Bash(rm --recursive:*)
Bash(git reflog expire:*)
Bash(git gc*--prune*)
Bash(git push * main)
Bash(git push * main *)
Bash(git push * +main)
Bash(git push * +main *)
Bash(git push *:main)
Bash(git push *:main *)
Bash(git push *refs/heads/main)
Bash(git push *refs/heads/main *)
Bash(gh issue edit * --add-label state:**)
Bash(gh issue edit * --remove-label state:**)
Bash(gh issue create * --label state:**)
Bash(gh label create state:**)
Bash(gh label edit state:**)
Bash(gh label delete state:**)
Bash(gh issue edit * --add-label shaping:**)
Bash(gh issue edit * --remove-label shaping:**)
Bash(gh issue create * --label shaping:**)
Bash(gh label create shaping:**)
Bash(gh label edit shaping:**)
Bash(gh label delete shaping:**)
Bash(gh issue edit * --add-label review:**)
Bash(gh issue edit * --remove-label review:**)
Bash(gh issue create * --label review:**)
Bash(gh label create review:**)
Bash(gh label edit review:**)
Bash(gh label delete review:**)
Bash(gh api *issues/*/labels*)"
deny_ok=1
if command -v python3 >/dev/null 2>&1; then
  py_script=/tmp/validate-kit-deny.$$
  cat > "$py_script" <<'PYEOF'
import json, sys
expected = set(sys.argv[2].splitlines())
actual = set(json.load(open(sys.argv[1])).get("permissions", {}).get("deny", []))
missing = expected - actual
extra = actual - expected
errors = []
if missing:
    errors.append("missing: %s" % sorted(missing))
if extra:
    errors.append("unexpected extra: %s" % sorted(extra))
if errors:
    sys.stderr.write("; ".join(errors) + "\n")
    sys.exit(1)
PYEOF
  while IFS= read -r deny_json; do
    [ -n "$deny_json" ] || continue
    case "$deny_json" in
      */templates/foundation/claude-settings.json) exp="$expected_deny_project" ;;
      *) exp="$expected_deny" ;;
    esac
    if ! python3 "$py_script" "$deny_json" "$exp" 2>/tmp/validate-kit-deny-out.$$; then
      fail "$deny_json permissions.deny does not exactly match the expected set: $(cat /tmp/validate-kit-deny-out.$$)"
      deny_ok=0
    fi
    rm -f /tmp/validate-kit-deny-out.$$
  done <<DENYFILES
$deny_jsonfiles
DENYFILES
  rm -f "$py_script"
  [ "$deny_ok" -eq 0 ] || \
    pass "both Claude deny lists are exactly the mechanically enforceable blocked commands"
else
  note "python3 not available; falling back to a substring check on permissions.deny"
  while IFS= read -r deny_json; do
    [ -n "$deny_json" ] || continue
    for pattern in "git reset --hard" "git push --force" "git clean -f" "rm -rf"; do
      if ! grep -qF "$pattern" "$deny_json"; then
        fail "$deny_json permissions.deny is missing mechanical enforcement for '$pattern'"
      fi
    done
  done <<DENYFILES
$deny_jsonfiles
DENYFILES
fi

# ---------------------------------------------------------------------------
echo "== Command lists in shipped documents =="

# A count and a list are two claims, and only the count was guarded. A release
# shipped a document reading "Nine are commands you type" above a list of eight
# names, because raising the number is a search-and-replace and adding the name
# to every list somewhere else is not. The founded project's own instructions
# were one of those documents, so a new project was told about a command it
# never learned the name of.
#
# So the list is compared with the inventory rather than with a number. These
# are the shipped documents that name the commands one by one; a document that
# mentions one command in passing is not a list and is not checked.
#
# The loop reads a here-document rather than a pipe. A pipeline runs its body in
# a subshell, where fail sets the failure flag on a copy and the validator exits
# zero having printed FAIL. That is worse than no check, and it is how the first
# version of this one behaved.
command_lists="$ROOT/docs/COMPATIBILITY.md
$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"

list_ok=1
while IFS= read -r list_file; do
  [ -n "$list_file" ] || continue
  if [ ! -f "$list_file" ]; then
    fail "missing $list_file"
    list_ok=0
    continue
  fi
  # The run of backticked names that starts at setup-ai-build-kit, joined onto
  # one line first so a list wrapped across lines is read whole.
  listed=$(tr '\n' ' ' < "$list_file" \
    | grep -oE '`setup-ai-build-kit`[^.]*' \
    | head -1 \
    | grep -oE '`[a-z-]+`' \
    | tr -d '`' \
    | sort -u)
  expected=$(printf '%s\n' "$expected_commands" | sort)
  if [ "$listed" != "$expected" ]; then
    fail "$(basename "$list_file") names the commands one by one and the list does not match the inventory"
    echo "  expected:" >&2
    echo "$expected" | sed 's/^/    /' >&2
    echo "  found:" >&2
    echo "$listed" | sed 's/^/    /' >&2
    list_ok=0
  fi
done <<COMMANDLISTS
$command_lists
COMMANDLISTS

[ "$list_ok" -eq 1 ] && pass "every shipped document that lists the commands names all of them"

# ---------------------------------------------------------------------------
echo "== Stale-claim checks =="

# docs/MAINTAINING.md is deliberately excluded: it is maintainer-only and the
# release allowlist keeps it out of the starter. It legitimately quotes these
# exact banned phrases while documenting this script's own rules.
project_docs="$ROOT/README.md
$ROOT/WORKFLOW.md
$ROOT/AGENTS.md
$ROOT/README.md
$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md
$ROOT/docs/PHILOSOPHY.md
$ROOT/docs/COMPATIBILITY.md
$ROOT/docs/SOURCES.md"
project_docs="$project_docs
$(find "$SKILLS" -name '*.md' | sort)"

check_claim() {
  # $1 = human label, $2 = fixed string to search for, $3 = optional file to
  # exclude (an explicit, legitimate "this is gone" reference)
  # Lines are joined with spaces before searching, so a claim that happens
  # to be soft-wrapped across a line break (a real case this once missed)
  # is still caught.
  hits=$(printf '%s\n' "$project_docs" | while IFS= read -r f; do
    [ -f "$f" ] || continue
    [ -n "${3:-}" ] && [ "$f" = "${3:-}" ] && continue
    if tr '\n' ' ' < "$f" | grep -qFi -- "$2"; then
      echo "$f"
    fi
  done)
  if [ -n "$hits" ]; then
    fail "stale claim ($1) found in: $(printf '%s' "$hits" | tr '\n' ' ')"
  fi
}

check_claim "all markdown" "all markdown"
check_claim "seven skills" "seven skills"
# The command count is written out in words in a dozen documents. The inventory
# check above knows how many commands there really are; nothing else did, so a
# document could keep the old number after the count moved and no check would
# say so.
check_claim "eight commands" "eight commands"
check_claim "four project documents" "four project documents"
check_claim "four project records" "four project records"
check_claim "four documents" "four documents hold"
check_claim "four records" "four records"
check_claim "team.md" "team.md" "$SKILLS/setup-ai-build-kit/SKILL.md"
check_claim "mandatory fresh session" "Always a fresh session"
check_claim "universal pull-request claim" "which is not finished until its check is green"
check_claim "universal test-first claim" "Test first, and show the test failing before building"
check_claim "obsolete automatic-rebuild rule" "rebuilds the piece from the masterplan, which is usually quicker and cleaner"
check_claim "absolute discipline-visibility claim" "so they never appear in that list"
check_claim "incorrect Claude invocation semantics" "can't be launched by slash either"
# Every command description once ended "it never starts on its own". The agent
# may now start a command the person asks for in plain words, so a document
# that says otherwise describes a kit that no longer exists.
check_claim "a command that never starts on its own" "never starts on its own"
check_claim "everything is markdown claim" "everything here is plain markdown"
# The seven commands were called "the seven words" until August 2026. The old
# name reads like a fantasy novel rather than a tool, and half the register
# problem in the person-facing writing came from it. These catch it coming back
# one phrase at a time, which is how it would come back.
check_claim "the old seven-words name" "seven words"
check_claim "the old seven-word name" "seven-word"
check_claim "a command called a word" "which word comes next"
check_claim "the other commands called words" "six words"
# These two survived the rename in docs/SOURCES.md, where the ceiling is
# described rather than counted, so none of the counting phrases above matched.
check_claim "the ceiling counted in words" "how many words"
check_claim "an ability arriving inside a word" "a word that already exists"

[ "$FAIL" -eq 0 ] && echo "ok: no stale claims found"

# ---------------------------------------------------------------------------
echo "== Maintainer writing contract =="

if grep -qF '.agents/maintainer-skills/humanizer/SKILL.md' "$ROOT/AGENTS.md" && \
   grep -qF '.agents/maintainer-skills/humanizer/SKILL.md' "$ROOT/docs/MAINTAINING.md" && \
   grep -qF 'metadata:' "$MAINTAINER_SKILLS/humanizer/SKILL.md" && \
   grep -qF 'version: "2.9.1"' "$MAINTAINER_SKILLS/humanizer/SKILL.md"; then
  pass "maintainer prose loads the pinned local Humanizer skill"
else
  fail "maintainer Humanizer skill or writing instructions are incomplete"
fi

# ---------------------------------------------------------------------------
if [ "$FAIL" -ne 0 ]; then
  echo
  echo "validate-kit.sh: FAILED" >&2
  exit 1
fi

echo
echo "validate-kit.sh: all checks passed"
