#!/usr/bin/env sh
# session-start.sh: prove that a session opening on a released project reports
# an overdue check-up, prints nothing at any other time, and stays silent
# inside the kit's own source.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -x "$BUILDER" ] || fail "release builder is missing or not executable"

SCRATCH=$(mktemp -d)
PACK="$SCRATCH/pack"
PROJECT="$SCRATCH/project"
SOURCELIKE="$SCRATCH/sourcelike"
OUT="$SCRATCH/out"
cleanup() {
  rm -R "$SCRATCH"
}
trap cleanup EXIT

# --- this repository is never reminded ------------------------------------
[ ! -e "$ROOT/.agents/hooks/session-start.sh" ] || \
  fail "the maintainer source carries a project session-start hook"
if grep -qF 'SessionStart' "$ROOT/.claude/settings.json"; then
  fail "the maintainer source wired a project session hook into its own settings"
fi

# The build loop's Stop hook is wired into the settings a project receives,
# never into this repository's own. Here nothing builds a piece, so a hook that
# ran the gate's stop check would only ever find nothing to do, and a session
# working on the kit must not be sent back by a project's checks.
for stop_event in '"Stop"' '"SubagentStop"'; do
  if grep -qF "$stop_event" "$ROOT/.claude/settings.json"; then
    fail "the maintainer source wired a $stop_event hook into its own settings"
  fi
  grep -qF "$stop_event" \
    "$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json" || \
    fail "the settings a project receives carry no $stop_event hook"
done
grep -qF 'stop-check' \
  "$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json" || \
  fail "the settings a project receives do not run the gate's stop check"

"$BUILDER" v0.3.0 "$PACK" >/dev/null

TEMPLATE="$PACK/.agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh"
[ -x "$TEMPLATE" ] || fail "the released setup-ai-build-kit skill has no executable session-start template"
[ -f "$PACK/.agents/skills/setup-ai-build-kit/templates/maintenance-record" ] || \
  fail "the released setup-ai-build-kit skill has no check-up date template"
[ ! -e "$PACK/.agents/hooks/session-start.sh" ] || \
  fail "the released starter ships a project hook that start should place itself"

# A folder that looks like the kit's own source stays silent. It is given a
# masterplan and a long-overdue visit on purpose. Without them the hook has
# nothing to report and stays quiet whatever the source guard does, so this
# check used to pass even with the guard removed.
mkdir -p "$SOURCELIKE/.agents/hooks" "$SOURCELIKE/.agents/tests"
printf '%s\n' "# allowlist" > "$SOURCELIKE/release-manifest.txt"
printf '%s\n' "# Masterplan" > "$SOURCELIKE/masterplan.md"
printf '%s\n' "founded|2020-01-01" > "$SOURCELIKE/.ai-build-kit-maintenance"
cp "$TEMPLATE" "$SOURCELIKE/.agents/hooks/session-start.sh"
"$SOURCELIKE/.agents/hooks/session-start.sh" > "$OUT" 2>&1 || \
  fail "the session hook failed inside a maintainer-shaped folder"
[ ! -s "$OUT" ] || fail "the session hook spoke inside a maintainer-shaped folder"

# Take the source markers away and the same folder must speak. That is what
# proves the silence above came from the source guard rather than from the hook
# having nothing to say.
rm -f "$SOURCELIKE/release-manifest.txt"
"$SOURCELIKE/.agents/hooks/session-start.sh" > "$OUT" 2>&1 || \
  fail "the session hook failed in an overdue project"
[ -s "$OUT" ] || \
  fail "the maintainer-source check proves nothing: silent even without the source markers"
printf '%s\n' "# allowlist" > "$SOURCELIKE/release-manifest.txt"

# --- the released starter wires it ---------------------------------------
grep -qF 'SessionStart' "$PACK/.claude/settings.json" || \
  fail "the released starter does not wire the session hook"
grep -qF '.agents/hooks/session-start.sh' "$PACK/.claude/settings.json" || \
  fail "the released session wiring does not name the project hook"
cmp -s "$PACK/.claude/settings.json" \
  "$PACK/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json" || \
  fail "the released Claude settings differ from start's foundation template"
[ ! -e "$PACK/.ai-build-kit-maintenance" ] || \
  fail "the released starter carries a project check-up file"

# --- the shared installer route ends up with both files ------------------
mkdir -p "$PROJECT/.agents"
cp -R "$PACK/.agents/skills" "$PROJECT/.agents/skills"
(cd "$PROJECT" && .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh >/dev/null) || \
  fail "the installed setup-ai-build-kit skill could not prepare a blank project"
HOOK="$PROJECT/.agents/hooks/session-start.sh"
[ -x "$HOOK" ] || fail "project bootstrap did not install an executable session hook"
grep -qF 'SessionStart' "$PROJECT/.claude/settings.json" || \
  fail "project bootstrap did not wire the session hook"
[ ! -e "$PROJECT/.ai-build-kit-maintenance" ] || \
  fail "project bootstrap created a check-up file before start founded the project"

# An existing Claude settings file, and an adjusted hook, are never rewritten.
printf '%s\n' '{ "permissions": {} }' > "$PROJECT/.claude/settings.json"
printf '%s\n' '#!/usr/bin/env sh' > "$HOOK"
(cd "$PROJECT" && .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh >/dev/null) || \
  fail "project bootstrap could not be rerun"
if grep -qF 'SessionStart' "$PROJECT/.claude/settings.json"; then
  fail "project bootstrap rewrote a Claude settings file that already existed"
fi
[ "$(cat "$HOOK")" = '#!/usr/bin/env sh' ] || \
  fail "project bootstrap replaced a session hook the project had already changed"
cp "$PACK/.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json" \
  "$PROJECT/.claude/settings.json"
cp "$TEMPLATE" "$HOOK"

run_hook() {
  ( cd "$PROJECT" && AI_BUILD_KIT_TODAY="$1" .agents/hooks/session-start.sh ) > "$OUT" 2>&1 || \
    fail "the session hook exited non-zero on $1"
}

# --- a project with no masterplan -----------------------------------------
run_hook 2026-03-01
[ ! -s "$OUT" ] || fail "a project with no masterplan was not silent"

# --- a founded project ----------------------------------------------------
git -C "$PROJECT" init -q
git -C "$PROJECT" config user.name "AI Build Kit rehearsal"
git -C "$PROJECT" config user.email "rehearsal@example.invalid"
git -C "$PROJECT" config commit.gpgsign false
cp "$PACK/.agents/skills/setup-ai-build-kit/templates/masterplan.md" "$PROJECT/masterplan.md"
cp "$PACK/.agents/skills/setup-ai-build-kit/templates/maintenance-record" \
  "$PROJECT/.ai-build-kit-maintenance"
git -C "$PROJECT" add -A
git -C "$PROJECT" commit -q -m "Found the project"

write_record() {
  {
    printf '%s\n' "founded|$1"
    printf '%s\n' "last-light-pass|$2"
    printf '%s\n' "last-full-pass|"
  } > "$PROJECT/.ai-build-kit-maintenance"
}

# Within cadence: 34 days after the recorded visit, nothing at all is printed.
write_record 2026-01-01 2026-02-01
run_hook 2026-03-07
[ ! -s "$OUT" ] || fail "a project inside its check-up cadence was not silent"

# At cadence: 35 days, the reminder appears once, with the action beside it.
run_hook 2026-03-08
grep -qF '35 days since the last check-up' "$OUT" || \
  fail "a project past its check-up cadence was not told, counted from the recorded visit"
grep -qF 'Type /maintain when you have ten minutes.' "$OUT" || \
  fail "the check-up reminder did not name the command to type"
[ "$(grep -c 'since the last check-up' "$OUT")" -eq 1 ] || \
  fail "the check-up reminder appeared more than once"

# The file also carries the kit line and the recipe lines founding and
# maintain write. The hook reads its dates by key, so those lines change
# nothing, even placed first.
{
  printf '%s\n' "kit|v0.19.2|fd0780a26d9a3a8bb5e9212b12452eb86173610a"
  printf '%s\n' "founding-menu|2025-12-01|a-recipe.md,b-recipe.md"
  printf '%s\n' "recipe-move-declined|2025-12-15|a-recipe.md|a-recipe.md"
  printf '%s\n' "founded|2026-01-01"
  printf '%s\n' "last-light-pass|2026-02-01"
  printf '%s\n' "last-full-pass|"
} > "$PROJECT/.ai-build-kit-maintenance"
run_hook 2026-03-07
[ ! -s "$OUT" ] || fail "the kit and recipe lines in the check-up file broke the cadence count"
run_hook 2026-03-08
grep -qF '35 days since the last check-up' "$OUT" || \
  fail "the kit and recipe lines in the check-up file changed the date the visit is counted from"

# Never visited, inside one window since founding: nothing is said.
write_record 2026-03-01 ""
run_hook 2026-03-20
[ ! -s "$OUT" ] || fail "a newly founded project was told a check-up was overdue"

# Never visited, past one window since founding: it is told, and told why.
run_hook 2026-04-10
grep -qF 'has had no check-up yet' "$OUT" || \
  fail "a project past one cadence window since founding was not told"

# No check-up file at all: the founding date comes from the first save of
# masterplan.md, so today's project is never flagged.
rm "$PROJECT/.ai-build-kit-maintenance"
run_hook "$(git -C "$PROJECT" log --reverse --diff-filter=A --format=%cd \
  --date=short -- masterplan.md | head -n 1)"
[ ! -s "$OUT" ] || fail "a project founded today was flagged with no check-up file present"
run_hook 2099-01-01
grep -qF 'check-up' "$OUT" || \
  fail "a long-untouched project with no check-up file was not flagged"

# A damaged file still reports the overdue visit and still never fails.
printf '%s\n' "nonsense" > "$PROJECT/.ai-build-kit-maintenance"
run_hook 2099-01-01
grep -qF 'check-up' "$OUT" || fail "a damaged check-up file suppressed the reminder"

# --- Claude Code hook mode ------------------------------------------------
write_record 2026-01-01 2026-02-01
( cd "$PROJECT" && AI_BUILD_KIT_TODAY=2026-03-08 \
  .agents/hooks/session-start.sh --claude-hook < /dev/null ) > "$OUT" || \
  fail "the session hook exited non-zero in Claude hook mode"
[ "$(wc -l < "$OUT" | tr -d ' ')" -eq 1 ] || \
  fail "Claude hook mode did not produce one line of output"
grep -qF '"hookEventName":"SessionStart"' "$OUT" || \
  fail "Claude hook mode did not name the session-start event"
grep -qF 'since the last check-up' "$OUT" || \
  fail "Claude hook mode dropped the check-up reminder"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$OUT" <<'PYEOF' || fail "Claude hook mode did not produce valid JSON carrying the reminder"
import json, sys
data = json.load(open(sys.argv[1]))
assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
assert "since the last check-up" in data["systemMessage"]
assert "check-up is overdue" in data["hookSpecificOutput"]["additionalContext"]
PYEOF
else
  echo "NOTE: python3 unavailable; skipped the JSON parse of Claude hook output" >&2
fi

# Nothing to say means no output at all, rather than an empty message.
( cd "$PROJECT" && AI_BUILD_KIT_TODAY=2026-03-07 \
  .agents/hooks/session-start.sh --claude-hook < /dev/null ) > "$OUT" || \
  fail "the session hook exited non-zero in Claude hook mode inside its cadence"
[ ! -s "$OUT" ] || fail "Claude hook mode spoke with nothing to say"

# A compaction is not a session opening.
printf '%s' '{"source":"compact"}' | ( cd "$PROJECT" && \
  .agents/hooks/session-start.sh --claude-hook ) > "$OUT" || \
  fail "the session hook exited non-zero on a compaction payload"
[ ! -s "$OUT" ] || fail "the session hook spoke again after a compaction"

# --- it also counts the work landed since the last visit -----------------
# A busy project can do a month's work in a few days. The reminder speaks once
# 20 changes have landed on the default branch since the last visit, however
# few days that took. Each change here is a commit with a fixed date, so the
# count is exact whatever day the rehearsal runs.
COUNTED="$SCRATCH/counted"
REMOTE="$SCRATCH/remote.git"
mkdir -p "$COUNTED/.agents/hooks"
cp "$TEMPLATE" "$COUNTED/.agents/hooks/session-start.sh"
printf '%s\n' "# Masterplan" > "$COUNTED/masterplan.md"
git -C "$COUNTED" init -q -b main
git -C "$COUNTED" config user.name "AI Build Kit rehearsal"
git -C "$COUNTED" config user.email "rehearsal@example.invalid"
git -C "$COUNTED" config commit.gpgsign false

dated_commit() {
  # dated_commit <ISO date and time> <message>
  ( cd "$COUNTED" && GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1" \
    git commit -q --allow-empty -m "$2" ) || fail "could not save a dated change"
}

count_record() {
  {
    printf '%s\n' "founded|$1"
    printf '%s\n' "last-light-pass|$2"
    printf '%s\n' "last-full-pass|"
  } > "$COUNTED/.ai-build-kit-maintenance"
}

run_counted() {
  ( cd "$COUNTED" && AI_BUILD_KIT_TODAY="$1" .agents/hooks/session-start.sh ) \
    > "$OUT" 2>&1 || fail "the session hook exited non-zero in the counted project on $1"
}

# Founding, then three changes before the visit. None of these may count.
( cd "$COUNTED" && git add masterplan.md && \
  GIT_AUTHOR_DATE=2026-04-01T09:00:00Z GIT_COMMITTER_DATE=2026-04-01T09:00:00Z \
  git commit -q -m "Found the project" ) || fail "could not found the counted project"
for n in 1 2 3; do
  dated_commit "2026-04-1${n}T09:00:00Z" "Change before the visit $n"
done
count_record 2026-04-01 2026-05-01

# After the visit: 17 plain changes and one merged pull request carrying three
# commits of its own. On the first-parent line that is 18 changes, not 21.
n=1
while [ "$n" -le 17 ]; do
  dated_commit "2026-05-02T10:$(printf '%02d' "$n"):00Z" "Change after the visit $n"
  n=$((n + 1))
done
git -C "$COUNTED" checkout -q -b piece
for n in 1 2 3; do
  dated_commit "2026-05-03T09:0${n}:00Z" "Piece commit $n"
done
git -C "$COUNTED" checkout -q main
( cd "$COUNTED" && GIT_AUTHOR_DATE=2026-05-03T10:00:00Z \
  GIT_COMMITTER_DATE=2026-05-03T10:00:00Z \
  git merge -q --no-ff -m "Merge the piece" piece ) || fail "could not merge the piece"
run_counted 2026-05-10
[ ! -s "$OUT" ] || \
  fail "the hook spoke at 18 changes, or counted the commits inside a merged pull request"

dated_commit 2026-05-04T10:00:00Z "Change after the visit 18"
run_counted 2026-05-10
[ ! -s "$OUT" ] || \
  fail "the hook spoke at 19 changes since the visit, or counted changes saved before it"

dated_commit 2026-05-04T11:00:00Z "Change after the visit 19"
TIP=$(git -C "$COUNTED" rev-parse HEAD)
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "the hook did not speak at 20 changes since the visit"
grep -qxF 'Type /maintain when you have ten minutes.' "$OUT" || \
  fail "the change count did not name the command to type"
if grep -qF 'days since' "$OUT"; then
  fail "the hook gave the day reminder 9 days after the visit"
fi
[ "$(wc -l < "$OUT" | tr -d ' ')" -eq 2 ] || \
  fail "the change count was not one line followed by the command"

# Never visited: counted from founding, and said so.
count_record 2026-04-01 ""
run_counted 2026-04-20
grep -qxF '24 changes have landed since founding.' "$OUT" || \
  fail "a project never visited did not count its changes from founding"

# A damaged check-up file: the founding date comes from Git, and the count
# still uses it.
printf '%s\n' "nonsense" > "$COUNTED/.ai-build-kit-maintenance"
run_counted 2026-04-20
grep -qxF '24 changes have landed since founding.' "$OUT" || \
  fail "a damaged check-up file stopped the count from founding"

# Both due: the day line first, the count line under it, the command once.
count_record 2026-04-01 2026-05-01
run_counted 2026-06-10
day_at=$(grep -n 'days since the last check-up' "$OUT" | head -n 1 | cut -d: -f1)
count_at=$(grep -n 'changes have landed since the last check-up' "$OUT" | head -n 1 | cut -d: -f1)
[ -n "$day_at" ] && [ -n "$count_at" ] && [ "$day_at" -lt "$count_at" ] || \
  fail "with both due, the day line and then the count line were not both said"
[ "$(grep -c 'Type /maintain' "$OUT")" -eq 1 ] || \
  fail "with both due, the command was not said exactly once"
( cd "$COUNTED" && AI_BUILD_KIT_TODAY=2026-06-10 \
  .agents/hooks/session-start.sh --claude-hook < /dev/null ) > "$OUT" || \
  fail "the session hook exited non-zero in Claude hook mode with both due"
[ "$(wc -l < "$OUT" | tr -d ' ')" -eq 1 ] || \
  fail "Claude hook mode with both due did not produce one line"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$OUT" <<'PYEOF' || fail "Claude hook mode with both due did not produce one valid JSON object carrying both lines"
import json, sys
data = json.load(open(sys.argv[1]))
message = data["systemMessage"]
assert "days since the last check-up" in message
assert "20 changes have landed since the last check-up." in message
assert message.index("days since") < message.index("changes have landed")
PYEOF
fi

# The default branch is read from origin/HEAD first, from what this computer
# already holds. The remote itself holds only ten of the changes, so a hook
# that fetched would see ten and stay quiet. The local main holds ten too, so
# a hook that read main first would also stay quiet.
TENTH=$(git -C "$COUNTED" rev-list --first-parent --reverse main | sed -n '14p')
git init -q --bare "$REMOTE"
git -C "$COUNTED" remote add origin "$REMOTE"
git -C "$COUNTED" push -q origin "$TENTH:refs/heads/main" 2>/dev/null || \
  fail "could not fill the rehearsal remote"
git -C "$COUNTED" update-ref refs/remotes/origin/main "$TIP"
git -C "$COUNTED" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git -C "$COUNTED" checkout -q -b work "$TENTH"
git -C "$COUNTED" branch -q -f main "$TENTH"
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "the count did not read origin/HEAD first, or fetched from the remote"
[ "$(git -C "$COUNTED" rev-parse refs/remotes/origin/main)" = "$TIP" ] || \
  fail "the hook fetched and moved what this computer knew of the remote"

# With no remote, main comes next, ahead of the branch checked out.
git -C "$COUNTED" remote remove origin
git -C "$COUNTED" branch -q -f main "$TIP"
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "with no remote, the count did not fall back to main"

# Then master. Kept at ten changes beside main first, so a hook that read
# master ahead of main would stay quiet.
git -C "$COUNTED" branch -q master "$TENTH"
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "with no remote, the count read master ahead of main"
git -C "$COUNTED" branch -q -D master
git -C "$COUNTED" branch -q -m main master
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "with no main, the count did not fall back to master"

# Then the branch checked out.
git -C "$COUNTED" branch -q -m master trunk
run_counted 2026-05-10
[ ! -s "$OUT" ] || \
  fail "with no main or master, the count did not read the branch checked out"
git -C "$COUNTED" checkout -q trunk
run_counted 2026-05-10
grep -qxF '20 changes have landed since the last check-up.' "$OUT" || \
  fail "with no main or master, the count did not fall back to the branch checked out"

# A folder that is not a Git repository, and one with no saved changes: the
# count is skipped, the day rule stands, and the hook still exits 0.
for kind in plain empty; do
  BARE_PROJECT="$SCRATCH/no-history-$kind"
  mkdir -p "$BARE_PROJECT/.agents/hooks"
  cp "$TEMPLATE" "$BARE_PROJECT/.agents/hooks/session-start.sh"
  printf '%s\n' "# Masterplan" > "$BARE_PROJECT/masterplan.md"
  printf '%s\n' "founded|2026-01-01" "last-light-pass|2026-02-01" \
    > "$BARE_PROJECT/.ai-build-kit-maintenance"
  [ "$kind" = plain ] || git -C "$BARE_PROJECT" init -q
  ( cd "$BARE_PROJECT" && AI_BUILD_KIT_TODAY=2026-03-07 .agents/hooks/session-start.sh ) \
    > "$OUT" 2>&1 || fail "the session hook failed in a $kind folder with no history"
  [ ! -s "$OUT" ] || fail "the session hook spoke inside its cadence in a $kind folder with no history"
  ( cd "$BARE_PROJECT" && AI_BUILD_KIT_TODAY=2026-03-08 .agents/hooks/session-start.sh ) \
    > "$OUT" 2>&1 || fail "the session hook failed in a $kind folder with no history"
  grep -qF '35 days since the last check-up' "$OUT" || \
    fail "the day reminder did not stand in a $kind folder with no history"
done

# --- it changes nothing ---------------------------------------------------
git -C "$PROJECT" checkout -q -- .ai-build-kit-maintenance
[ -z "$(git -C "$PROJECT" status --porcelain)" ] || \
  fail "the session hook changed project files"
[ ! -e "$PROJECT/.agents/tmp" ] || \
  fail "the session hook wrote a working file into the project"

echo "session-start.sh: all checks passed"
