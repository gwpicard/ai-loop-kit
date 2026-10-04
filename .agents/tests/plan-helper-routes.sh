#!/usr/bin/env sh
# plan-helper-routes.sh: prove every installation route leaves a founded
# project with a working plan printout helper, and that /maintain's step adds
# it to a project founded before it shipped. On the same routes, prove every
# pointer to a file inside a skill opens.
#
# The helper used to live in the kit's own tools folder, outside every skill.
# The shared installer and both plugins carry skills and nothing else, so only
# a whole copy of the kit ever had it. Every other project fell back to reading
# the issues by hand, and a hand reading once named a blocked piece as the next
# one to build. Nothing said the helper was missing except the agent, in
# passing, so this is the kind of fault that stays quiet.
#
# Each route is laid out the way its installer leaves a project, from an
# assembled release. The copies stand in for the installers, which need the
# network. The printout then runs against a stand-in for the GitHub CLI, so
# nothing here reaches the network or needs an account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"
TARGET=.agents/tools/plan-refresh.sh
# The gate script travels the same way as the printout helper, and every route
# has to end with a runnable copy identical to the one the skill carries. A
# project without it has no way to move a piece at all.
GATE_TARGET=.agents/tools/gate.py
GATE_TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/gate.py"
# The state guard hook travels the same way. It is what stops the agent moving
# a piece by hand, and the settings run it only when it is there, so a route
# that left it out would fail without a word.
HOOK_TARGET=.agents/hooks/state-guard.sh
HOOK_TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/state-guard.sh"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT INT TERM
PACK="$SCRATCH/pack"
"$BUILDER" v0.1.0 "$PACK" >/dev/null

# --- the stand-in for the GitHub CLI -------------------------------------
# Three pieces: one ready and free, one ready but held up by the first, and
# one still being shaped. Only the first may be named as buildable, and the
# second is under Held up, naming the first.
mkdir -p "$SCRATCH/bin"
cat >"$SCRATCH/issues.json" <<'JSON'
[
  {"number": 1, "title": "Card checkout", "html_url": "http://x/1",
   "body": "## Done when\nA card is charged.", "assignees": [],
   "labels": [{"name": "ready"}]},
  {"number": 2, "title": "Weekly payouts", "html_url": "http://x/2",
   "body": "## Done when\nSellers are paid.", "assignees": [],
   "labels": [{"name": "ready"}],
   "issue_dependencies_summary": {"blocked_by": 1, "total": 1}},
  {"number": 3, "title": "make the calendar nicer", "html_url": "http://x/3",
   "body": "half a sentence", "assignees": [],
   "labels": [{"name": "shaping"}, {"name": "needs-clarification"}]}
]
JSON
cat >"$SCRATCH/bin/gh" <<'SH'
#!/usr/bin/env sh
case "$1 $2" in
  "repo view") echo '{"nameWithOwner":"someone/project"}' ;;
  *) case "$2" in
       *"/issues?"*) cat "$FIXTURE" ;;
       *"/issues/2/dependencies/blocked_by")
         echo '[{"number":1,"title":"Card checkout","state":"open"}]' ;;
       *) echo '[]' ;;
     esac ;;
esac
SH
chmod +x "$SCRATCH/bin/gh"
FIXTURE="$SCRATCH/issues.json"
export FIXTURE
PATH="$SCRATCH/bin:$PATH"
export PATH

section() {
  awk -v want="$2" '$0 == want { f = 1; next } /^[^ ]/ { f = 0 } f' "$1"
}

# Run the printout the way every skill does, with sh, since an installer is not
# promised to keep a file's runnable bit. Then read what it wrote.
prints_the_plan() {
  project=$1
  route=$2
  rm -f "$project/plan.local.md"
  (cd "$project" && sh "$3" >/dev/null 2>&1) || {
    fail "$route: the printout helper did not run"
    return
  }
  out="$project/plan.local.md"
  [ -f "$out" ] || { fail "$route: no printout was written"; return; }
  if section "$out" "To build" | grep "Card checkout" | grep -q "(ready)" && \
     ! section "$out" "To build" | grep -q "Weekly payouts" && \
     section "$out" "Held up" | grep "Weekly payouts" | grep -q "needs Card checkout"; then
    pass "$route: the printout runs, and a held-up piece is kept out of To build"
  else
    fail "$route: the printout does not keep the held-up piece out of To build"
  fi
}

founds_with_helper() {
  project=$1
  route=$2
  bootstrap=$3
  [ -f "${bootstrap%/*}/codex-with-github.py" ] \
    && pass "$route: the portable Codex credential launcher arrived" \
    || fail "$route: the portable Codex credential launcher is missing"
  [ ! -e "$project/$TARGET" ] || \
    fail "$route: the helper was in the project before founding, so founding was not tested"
  (cd "$project" && "$bootstrap" >/dev/null) || {
    fail "$route: founding could not prepare the project"
    return
  }
  if [ -f "$project/$TARGET" ]; then
    pass "$route: founding placed the helper at $TARGET"
  else
    fail "$route: founding left no helper at $TARGET"
    return
  fi
  holds_the_gate "$project" "$route" "${bootstrap%/scripts/*}/templates/foundation/gate.py"
  holds_the_hook "$project" "$route" "${bootstrap%/scripts/*}/templates/foundation/state-guard.sh"
  prints_the_plan "$project" "$route" "$TARGET"
}

# A runnable gate script at the project's path, identical to the template the
# installed skill carries and to the one in this repository.
holds_the_gate() {
  project=$1
  route=$2
  installed=$3
  gate="$project/$GATE_TARGET"
  if [ -f "$gate" ] && [ ! -L "$gate" ] && [ -x "$gate" ] && \
     cmp -s "$gate" "$installed" && cmp -s "$gate" "$GATE_TEMPLATE" && \
     (cd "$project" && "./$GATE_TARGET" --help >/dev/null 2>&1); then
    pass "$route: a runnable $GATE_TARGET identical to the template is in place"
  else
    fail "$route: no runnable $GATE_TARGET identical to the template"
  fi
}

# A runnable state guard hook at the project's path, identical to the template
# the installed skill carries and to the one in this repository. It has to
# answer a command that touches no label by letting it through.
holds_the_hook() {
  project=$1
  route=$2
  installed=$3
  hook="$project/$HOOK_TARGET"
  if [ -f "$hook" ] && [ ! -L "$hook" ] && [ -x "$hook" ] && \
     cmp -s "$hook" "$installed" && cmp -s "$hook" "$HOOK_TEMPLATE" && \
     printf '%s' '{"tool_name":"Bash","tool_input":{"command":"gh issue list"}}' | \
       (cd "$project" && "./$HOOK_TARGET" >/dev/null 2>&1); then
    pass "$route: a runnable $HOOK_TARGET identical to the template is in place"
  else
    fail "$route: no runnable $HOOK_TARGET identical to the template"
  fi
}

echo "== Founding places the helper, on every route =="

# The release no longer carries the maintainer's copy at the project path. If
# it did, a whole copy would keep that one and never receive the skill's.
[ ! -e "$PACK/$TARGET" ] || \
  fail "the release carries $TARGET, so a whole copy would keep that copy"

# A whole copy of the kit.
WHOLE="$SCRATCH/whole"
cp -R "$PACK" "$WHOLE"
founds_with_helper "$WHOLE" "whole copy" \
  "$WHOLE/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"

# The shared installer for several coding agents: the skills in .agents/skills,
# with Claude Code reaching them through links in .claude/skills.
SHARED="$SCRATCH/shared"
mkdir -p "$SHARED/.agents" "$SHARED/.claude/skills"
cp -R "$PACK/.agents/skills" "$SHARED/.agents/skills"
for skill in "$SHARED/.agents/skills"/*; do
  ln -s "../../.agents/skills/$(basename "$skill")" \
    "$SHARED/.claude/skills/$(basename "$skill")"
done
founds_with_helper "$SHARED" "shared installer, several coding agents" \
  "$SHARED/.claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"

# The shared installer for Claude Code alone: every skill in .claude/skills and
# no .agents folder at all until founding makes one.
CLAUDE_ONLY="$SCRATCH/claude-only"
mkdir -p "$CLAUDE_ONLY/.claude"
cp -R "$PACK/.agents/skills" "$CLAUDE_ONLY/.claude/skills"
founds_with_helper "$CLAUDE_ONLY" "shared installer, Claude Code alone" \
  "$CLAUDE_ONLY/.claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
[ ! -e "$CLAUDE_ONLY/.agents/skills" ] || \
  fail "founding a Claude-Code-only project created .agents/skills"

# The Claude Code plugin: the skills stay in the plugin's own folder, which the
# assembled release stands in for, and the project receives none.
CLAUDE_PLUGIN="$SCRATCH/claude-plugin-project"
mkdir -p "$CLAUDE_PLUGIN"
founds_with_helper "$CLAUDE_PLUGIN" "Claude Code plugin" \
  "$PACK/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
[ ! -e "$CLAUDE_PLUGIN/.agents/skills" ] || \
  fail "the Claude Code plugin copied skills into the project"

# The Agent Plugins folder, copied out on its own the way a client installs it.
AGENT_PLUGIN="$SCRATCH/installed/ai-build-kit"
mkdir -p "$SCRATCH/installed"
cp -R "$PACK/agent-plugin" "$AGENT_PLUGIN"
AGENT_PROJECT="$SCRATCH/agent-plugin-project"
mkdir -p "$AGENT_PROJECT"
founds_with_helper "$AGENT_PROJECT" "Agent Plugins folder" \
  "$AGENT_PLUGIN/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"

echo "== Every pointer to a skill's file finds it, on every route =="

# A founded project's AGENTS.md and masterplan, and the skills themselves, name
# files inside other skills: the rules for a piece, the fit check, the trim. They
# once named them at .agents/skills/..., which a project installed for Claude
# Code alone, or through either plugin, does not have. So a pointer names the
# skill and the path inside it, and the coding agent finds the skill wherever it
# was installed. Here each route's own layout resolves every pointer.

# The pointers in a set of files, one "skill|path" per line, read with the lines
# joined so a pointer wrapped across two lines is still found.
pointers_in() {
  for f in "$@"; do tr '\n' ' ' < "$f"; echo; done \
    | tr -s ' ' \
    | grep -oE "\`[a-z-]+\` skill's \`[^\`]+\`" \
    | sed -E "s/^\`([a-z-]+)\` skill's \`([^\`]+)\`$/\1|\2/" \
    | sort -u
}

# Print each pointer whose file is missing from the given skills folder.
missing_pointers() {
  skills=$1
  shift
  pointers_in "$@" | while IFS='|' read -r skill path; do
    [ -f "$skills/$skill/$path" ] || echo "$skill/$path"
  done
}

# A path into a named skill at a fixed project folder is the form this replaced.
fixed_paths_in() {
  grep -nE '\.(agents|claude)/skills/[a-z-]+/' "$@" 2>/dev/null || true
}

pointers_resolve() {
  route=$1
  skills=$2
  project=$3
  masterplan="$SCRATCH/masterplan-$(echo "$route" | tr -c 'a-z' '-').md"
  cp "$skills/setup-ai-build-kit/templates/masterplan.md" "$masterplan"
  docs_found=$(pointers_in "$project/AGENTS.md" "$masterplan" | wc -l | tr -d ' ')
  missing=$(missing_pointers "$skills" "$project/AGENTS.md" "$masterplan")
  fixed=$(fixed_paths_in "$project/AGENTS.md" "$masterplan")
  if [ "$docs_found" -ge 4 ] && [ -z "$missing" ] && [ -z "$fixed" ]; then
    pass "$route: the $docs_found pointers in the founded AGENTS.md and masterplan all open"
  else
    fail "$route: founded documents found $docs_found pointers; missing: $missing; fixed paths: $fixed"
  fi
  skill_files=$(find -L "$skills"/ -name '*.md' -o -name '*.py' | sort)
  # shellcheck disable=SC2086
  skills_found=$(pointers_in $skill_files | wc -l | tr -d ' ')
  # shellcheck disable=SC2086
  missing=$(missing_pointers "$skills" $skill_files)
  # shellcheck disable=SC2086
  fixed=$(fixed_paths_in $skill_files)
  if [ "$skills_found" -ge 10 ] && [ -z "$missing" ] && [ -z "$fixed" ]; then
    pass "$route: the $skills_found pointers between skills all open"
  else
    fail "$route: skills found $skills_found pointers; missing: $missing; fixed paths: $fixed"
  fi
}

pointers_resolve "whole copy" "$WHOLE/.agents/skills" "$WHOLE"
pointers_resolve "shared installer, several coding agents, as Claude Code reads it" \
  "$SHARED/.claude/skills" "$SHARED"
pointers_resolve "shared installer, several coding agents, as the others read it" \
  "$SHARED/.agents/skills" "$SHARED"
pointers_resolve "shared installer, Claude Code alone" "$CLAUDE_ONLY/.claude/skills" "$CLAUDE_ONLY"
pointers_resolve "Claude Code plugin" "$PACK/.agents/skills" "$CLAUDE_PLUGIN"
pointers_resolve "Agent Plugins folder" "$AGENT_PLUGIN/skills" "$AGENT_PROJECT"

# The check has to be able to fail. A pointer to a file no skill has is reported,
# and so is the old fixed path, in a copy of a founded AGENTS.md.
broken="$SCRATCH/broken-AGENTS.md"
cp "$CLAUDE_ONLY/AGENTS.md" "$broken"
printf '%s\n' "Read the \`setup-ai-build-kit\` skill's \`references/no-such-file.md\`." >> "$broken"
[ "$(missing_pointers "$CLAUDE_ONLY/.claude/skills" "$broken")" = \
  "setup-ai-build-kit/references/no-such-file.md" ] && \
  pass "a pointer to a file the skill does not have is reported" || \
  fail "a pointer to a missing file went unreported"
printf '%s\n' 'The rules are in `.agents/skills/setup-ai-build-kit/references/pieces.md`.' >> "$broken"
[ -n "$(fixed_paths_in "$broken")" ] && \
  pass "a pointer at a fixed project folder is reported" || \
  fail "a pointer at a fixed project folder went unreported"

echo "== /maintain adds the helper to a project founded before it shipped =="

PLACE="$CLAUDE_ONLY/.claude/skills/setup-ai-build-kit/scripts/place-plan-helper.sh"
INSTALLED_HELPER="$CLAUDE_ONLY/.claude/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh"

# A project founded before this release: founded, with no helper and no gate.
OLD="$SCRATCH/old"
cp -R "$CLAUDE_ONLY" "$OLD"
rm -f "$OLD/$TARGET" "$OLD/$GATE_TARGET" "$OLD/$HOOK_TARGET" "$OLD/plan.local.md"
PLACE_OLD="$OLD/.claude/skills/setup-ai-build-kit/scripts/place-plan-helper.sh"
printf '%s\n' "# Masterplan" > "$OLD/masterplan.md"

# Until /maintain runs, the skills run the installed skill's own copy. That
# has to work from the project's root folder.
prints_the_plan "$OLD" "a project with no copy, from the installed skill" \
  "$OLD/.claude/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh"

said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill refused a founded project: $said"
case "$said" in
  *added*) pass "the backfill adds the helper to a project that has none" ;;
  *) fail "the backfill did not say it added the helper: $said" ;;
esac
prints_the_plan "$OLD" "after the backfill" "$TARGET"
holds_the_gate "$OLD" "a project founded before the gate, after the backfill" \
  "$OLD/.claude/skills/setup-ai-build-kit/templates/foundation/gate.py"
holds_the_hook "$OLD" "a project founded before the hook, after the backfill" \
  "$OLD/.claude/skills/setup-ai-build-kit/templates/foundation/state-guard.sh"

# Run again, it changes nothing and says so. /maintain runs it on every visit.
before=$(cksum < "$OLD/$TARGET")
gate_before=$(cksum < "$OLD/$GATE_TARGET" 2>/dev/null || echo missing)
hook_before=$(cksum < "$OLD/$HOOK_TARGET" 2>/dev/null || echo missing)
said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill failed on its second run"
case "$said" in
  *"already current"*) pass "a second run changes nothing and says the copy is current" ;;
  *) fail "a second run did not say the copy was current: $said" ;;
esac
[ "$(cksum < "$OLD/$TARGET")" = "$before" ] || fail "a second run changed the helper"
if [ "$(cksum < "$OLD/$GATE_TARGET" 2>/dev/null || echo missing)" = "$gate_before" ] && \
   [ "$gate_before" != missing ] && \
   [ "$(printf '%s\n' "$said" | grep -c "already current")" -ge 2 ]; then
  pass "a second run leaves the gate script as it was and says it is current"
else
  fail "a second run changed the gate script or did not say it was current: $said"
fi
if [ "$(cksum < "$OLD/$HOOK_TARGET" 2>/dev/null || echo missing)" = "$hook_before" ] && \
   [ "$hook_before" != missing ] && \
   [ "$(printf '%s\n' "$said" | grep -c "already current")" -ge 3 ]; then
  pass "a second run leaves the state guard hook as it was and says it is current"
else
  fail "a second run changed the state guard hook or did not say it was current: $said"
fi

# An older gate script is replaced, as the helper is.
printf '%s\n' "# an older gate" >> "$OLD/$GATE_TARGET"
said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill failed on an older gate script"
cmp -s "$OLD/$GATE_TARGET" "$GATE_TEMPLATE" && \
  pass "an older gate script is replaced with the template" || \
  fail "an older gate script was not replaced: $said"

# An older hook is replaced too, and made runnable.
printf '%s\n' "# an older hook" >> "$OLD/$HOOK_TARGET"
chmod 644 "$OLD/$HOOK_TARGET"
said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill failed on an older hook"
cmp -s "$OLD/$HOOK_TARGET" "$HOOK_TEMPLATE" && [ -x "$OLD/$HOOK_TARGET" ] && \
  pass "an older state guard hook is replaced with the template and runnable" || \
  fail "an older state guard hook was not replaced: $said"

# A project founded from a whole copy of an earlier release holds an older copy.
printf '%s\n' "# an older helper" >> "$OLD/$TARGET"
said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill failed on an older copy"
case "$said" in
  *replaced*) pass "an older copy is replaced and the backfill says so" ;;
  *) fail "an older copy was not reported as replaced: $said" ;;
esac
cmp -s "$OLD/$TARGET" "$INSTALLED_HELPER" || \
  fail "the replaced helper does not match the installed skill's copy"
case "$said" in
  *checkpoint*) pass "the replacement says any hand change is in the checkpoint" ;;
  *) fail "the replacement does not say where a hand change went: $said" ;;
esac

# A current copy that lost its runnable bit is fixed, and the fix is reported.
chmod 644 "$OLD/$TARGET"
said=$(cd "$OLD" && sh "$PLACE_OLD" 2>&1) || fail "the backfill failed on a copy that is not runnable"
case "$said" in
  *"made runnable again"*) [ -x "$OLD/$TARGET" ] && \
    pass "a mode fix is made and reported" || fail "the helper was not made runnable" ;;
  *) fail "a mode fix was not reported: $said" ;;
esac

# It writes only into a founded project, and never through a link.
NOT_FOUNDED="$SCRATCH/not-founded"
mkdir -p "$NOT_FOUNDED"
if (cd "$NOT_FOUNDED" && sh "$PLACE" >/dev/null 2>&1); then
  fail "the backfill wrote into a folder with no masterplan"
fi
[ ! -e "$NOT_FOUNDED/.agents" ] && \
  pass "a folder that is not a founded project is refused and left untouched" || \
  fail "the backfill wrote into a folder that is not a founded project"

LINKED="$SCRATCH/linked-helper"
cp -R "$OLD" "$LINKED"
rm -f "$LINKED/$TARGET"
printf '%s\n' "somebody else's file" > "$SCRATCH/elsewhere"
ln -s "$SCRATCH/elsewhere" "$LINKED/$TARGET"
if (cd "$LINKED" && sh "$PLACE_OLD" >/dev/null 2>&1); then
  fail "the backfill wrote through a link"
fi
[ "$(cat "$SCRATCH/elsewhere")" = "somebody else's file" ] && \
  pass "a helper path that is a link is refused, and what it points at is untouched" || \
  fail "the backfill changed a file outside the project"

LINKED_GATE="$SCRATCH/linked-gate"
cp -R "$OLD" "$LINKED_GATE"
rm -f "$LINKED_GATE/$GATE_TARGET"
printf '%s\n' "somebody else's gate" > "$SCRATCH/elsewhere-gate"
ln -s "$SCRATCH/elsewhere-gate" "$LINKED_GATE/$GATE_TARGET"
if (cd "$LINKED_GATE" && sh "$PLACE_OLD" >/dev/null 2>&1); then
  fail "the backfill wrote the gate script through a link"
fi
[ "$(cat "$SCRATCH/elsewhere-gate")" = "somebody else's gate" ] && \
  pass "a gate script path that is a link is refused, and what it points at is untouched" || \
  fail "the backfill changed a gate script outside the project"

# The hook's place holding a link or a folder is refused, as the helper's and
# the gate's are, and nothing else is placed on that run.
LINKED_HOOK="$SCRATCH/linked-hook"
cp -R "$OLD" "$LINKED_HOOK"
rm -f "$LINKED_HOOK/$HOOK_TARGET" "$LINKED_HOOK/$TARGET"
printf '%s\n' "somebody else's hook" > "$SCRATCH/elsewhere-hook"
ln -s "$SCRATCH/elsewhere-hook" "$LINKED_HOOK/$HOOK_TARGET"
if (cd "$LINKED_HOOK" && sh "$PLACE_OLD" >/dev/null 2>&1); then
  fail "the backfill wrote the state guard hook through a link"
fi
[ "$(cat "$SCRATCH/elsewhere-hook")" = "somebody else's hook" ] && [ ! -e "$LINKED_HOOK/$TARGET" ] && \
  pass "a hook path that is a link is refused, what it points at is untouched, and nothing else is placed" || \
  fail "the backfill changed a hook outside the project, or placed the helper beside a refused hook"

FOLDER_HOOK="$SCRATCH/folder-hook"
cp -R "$OLD" "$FOLDER_HOOK"
rm -f "$FOLDER_HOOK/$HOOK_TARGET"
mkdir "$FOLDER_HOOK/$HOOK_TARGET"
if (cd "$FOLDER_HOOK" && sh "$PLACE_OLD" >/dev/null 2>&1); then
  fail "the backfill accepted a folder in the state guard hook's place"
fi
[ -d "$FOLDER_HOOK/$HOOK_TARGET" ] && \
  pass "a folder in the hook's place is refused and left as it was" || \
  fail "the backfill changed a folder in the hook's place"

LINKED_HOOKS="$SCRATCH/linked-hooks-folder"
cp -R "$OLD" "$LINKED_HOOKS"
mkdir "$SCRATCH/elsewhere-hooks"
rm -rf "$LINKED_HOOKS/.agents/hooks"
ln -s "$SCRATCH/elsewhere-hooks" "$LINKED_HOOKS/.agents/hooks"
if (cd "$LINKED_HOOKS" && sh "$PLACE_OLD" >/dev/null 2>&1); then
  fail "the backfill wrote through a hooks folder that is a link"
fi
[ -z "$(ls -A "$SCRATCH/elsewhere-hooks")" ] && \
  pass "a hooks folder that is a link is refused, and nothing is written outside the project" || \
  fail "the backfill wrote into a hooks folder outside the project"

echo "== Every skill names a path a project has =="

# The pointer is the route. A skill naming the old tools path inside the kit,
# or any other path, sends a project to a file it does not have.
bad=$(grep -rn "plan-refresh\.sh" "$ROOT/.agents/skills" \
  | grep -v "\.agents/tools/plan-refresh\.sh" \
  | grep -v "templates/foundation/plan-refresh\.sh" \
  | grep -v "^$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/plan-refresh\.sh:" \
  | grep -v "^$ROOT/.agents/skills/setup-ai-build-kit/scripts/" || true)
[ -z "$bad" ] && pass "every skill names the helper where a project keeps it" || \
  fail "a skill names the helper at a path no project has: $bad"

grep -q "place-plan-helper\.sh" "$ROOT/.agents/skills/maintain/SKILL.md" && \
  pass "/maintain runs the backfill" || \
  fail "/maintain does not run the backfill"

[ "$FAIL" -eq 0 ] || exit 1
echo "plan-helper-routes.sh: all checks passed"
