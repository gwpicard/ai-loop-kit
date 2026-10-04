#!/usr/bin/env sh
# pre-release-run.sh: guard the written pre-release run in docs/MAINTAINING.md.
#
# The run itself needs real accounts and a person, so it cannot be rehearsed
# here. What can be checked offline is that the written steps still work as
# written: the paths they name exist, the builder accepts the preview version
# they give, the installer lines are the two that worked, the teardown removes
# everything the run creates, and the prose rules that keep the run safe are
# still there. A section whose commands drifted from the tools would only be
# found out on the day of a release, which is the worst day to find it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

DOC="$ROOT/docs/MAINTAINING.md"
HEADING='## Trying unreleased work as a person would'

rs_init "Pre-release run checks"
rs_exists "$DOC"

SECTION="$rs_dir/section.md"
awk -v h="$HEADING" '
  $0 == h { on = 1; print; next }
  on && /^## / { exit }
  on { print }
' "$DOC" > "$SECTION"
[ -s "$SECTION" ] || rs_fail "MAINTAINING.md has no section headed '$HEADING'"
rs_ok "the section exists"

rs_require "the release section points at the run" \
  "$DOC" 'the next section says how to try one'

# Every repository path the section names has to exist, or a maintainer
# following it on release day meets a missing file.
paths=$(grep -oE '\.agents/[A-Za-z0-9_./-]*[A-Za-z0-9_-]/?' "$SECTION" | sort -u)
[ -n "$paths" ] || rs_fail "the section names no repository path"
for p in $paths; do
  [ -e "$ROOT/$p" ] || rs_fail "the section names $p, which does not exist"
done
rs_ok "every repository path the section names exists"

# The builder's own argument check decides the version form. It checks the
# version before the output folder, so an output under a missing parent tells
# an accepted version from a refused one without building anything.
build_line=$(grep -E '^ *\.agents/tools/build-release\.sh ' "$SECTION" || true)
[ "$(printf '%s\n' "$build_line" | grep -c .)" -eq 1 ] \
  || rs_fail "the section should give exactly one build command"
version=$(printf '%s\n' "$build_line" | awk '{print $2}' | sed 's/N$/7/')
output=$(printf '%s\n' "$build_line" | awk '{print $3}')
case "$output" in
  /private/tmp/*) rs_ok "the preview is built outside the repository" ;;
  *) rs_fail "the preview output should sit under /private/tmp, not $output" ;;
esac
probe() {
  sh "$ROOT/.agents/tools/build-release.sh" "$1" "$rs_dir/no-such-parent/out" 2>&1 || true
}
case "$(probe "$version")" in
  *"output parent does not exist"*) rs_ok "build-release.sh accepts the version form $version" ;;
  *) rs_fail "build-release.sh refuses the version the section gives: $version" ;;
esac
case "$(probe "v0.0.0.preview")" in
  *"version must look like"*) rs_ok "the probe tells a refused version apart" ;;
  *) rs_fail "the version probe cannot tell a refused version from an accepted one" ;;
esac

# The two installer lines are the ones that worked in a real run: the local
# build folder, every skill, no prompt, and the coding agents named.
preview=$output
one="npx skills add $preview -a claude-code -s '*' -y"
two="npx skills add $preview -a claude-code -a codex -s '*' -y"
grep -qF "$one" "$SECTION" || rs_fail "missing the Claude Code install line: $one"
rs_ok "installs for Claude Code alone from the built folder"
grep -qF "$two" "$SECTION" || rs_fail "missing the Claude Code and Codex install line: $two"
rs_ok "installs for Claude Code and Codex from the built folder"
[ "$(grep -c 'npx skills add' "$SECTION")" -eq 2 ] \
  || rs_fail "the section should give exactly two install lines"
rs_ok "exactly two install lines"

# The builder copies the working tree, so the build starts from a clean main,
# checked by the commands a maintainer can read the answer from.
for cmd in 'git switch main' 'git branch --show-current' 'git status --short' 'git pull --ff-only'; do
  grep -qE "^ *$cmd\$" "$SECTION" || rs_fail "the build step does not run: $cmd"
done
first_git=$(grep -nE '^ *git (switch main|pull --ff-only)$' "$SECTION" | head -1)
case "$first_git" in
  *'git switch main') rs_ok "the build switches to main and checks it is clean before pulling" ;;
  *) rs_fail "the build pulls before switching to main" ;;
esac

# Teardown has to remove everything the run creates.
grep -qE '^ *gh auth refresh -h github\.com -r delete_repo$' "$SECTION" || rs_fail "teardown leaves the delete_repo scope on the token"
remove_at=$(grep -nE '^ *gh auth refresh -h github\.com -r delete_repo$' "$SECTION" | cut -d: -f1)
delete_at=$(grep -nE '^ *gh repo delete ' "$SECTION" | cut -d: -f1)
[ "$remove_at" -gt "$delete_at" ] || rs_fail "the delete_repo scope is removed before the repository is deleted"
rs_ok "teardown takes the delete_repo scope off again after the delete"
for cmd in 'vercel project ls' 'gh repo view <owner>/abk-try-N' 'ls /private/tmp/abk-\*' 'ls ~/.config/abk-try-N' 'ls ~/Backups/abk-try-N' 'ls ~/.abk-try-N-start'; do
  grep -qE "^ *$cmd\$" "$SECTION" || rs_fail "teardown does not check with: $cmd"
done
grep -qF '"Could not resolve"' "$SECTION" || rs_fail "teardown does not say what a deleted repository answers"
rs_ok "teardown checks that each item is gone"
grep -qE '^ *vercel project rm abk-try-N$' "$SECTION" || rs_fail "teardown does not remove the Vercel project"
rs_ok "teardown removes the Vercel project"
grep -qE '^ *gh auth refresh -h github\.com -s delete_repo$' "$SECTION" || rs_fail "teardown does not ask for the delete_repo scope"
rs_ok "teardown asks for the delete_repo scope"
grep -qE '^ *gh repo delete <owner>/abk-try-N --yes$' "$SECTION" || rs_fail "teardown does not delete the repository"
rs_ok "teardown deletes the repository"
trash_line=$(grep -E '^ *trash .*abk-try-N-claude' "$SECTION" || true)
for f in /private/tmp/abk-try-N-claude /private/tmp/abk-try-N-both "$preview" '~/.config/abk-try-N' '~/Backups/abk-try-N'; do
  case " $trash_line " in
    *" $f "*) ;;
    *) rs_fail "teardown does not move $f to the Trash" ;;
  esac
done
rs_ok "teardown moves both projects, the build, the password folder and the backups to the Trash"

# Supabase's create form marks a lowercase hex password as not secure enough,
# so the password line is the mixed-case one that passed in a real run.
pw_line="(umask 077 && openssl rand -base64 48 | tr -d '/+=\\n' | cut -c1-40 > ~/.config/abk-try-N/db.pw)"
grep -qF "$pw_line" "$SECTION" || rs_fail "missing the password line the create form accepts: $pw_line"
if grep -qF 'openssl rand -hex' "$SECTION"; then
  rs_fail "the section still makes a hex password, which the create form marks as not secure"
fi
rs_ok "the password line makes mixed-case letters and digits"
grep -qE '^ *gh auth status$' "$SECTION" || rs_fail "teardown does not show the token's scopes before adding one"
rs_ok "teardown shows the token's scopes first"

# The kit's temporary files have names nobody can list in advance, and other
# sessions write to /private/tmp too, so the run's files are the ones newer
# than a marker left at the start. A newest-first listing cut to a fixed
# length can pass while the run's files are still there.
grep -qE '^ *touch ~/\.abk-try-N-start$' "$SECTION" || rs_fail "step 1 does not leave the start marker"
touch_at=$(grep -nE '^ *touch ~/\.abk-try-N-start$' "$SECTION" | cut -d: -f1)
build_at=$(grep -nE '^ *\.agents/tools/build-release\.sh ' "$SECTION" | cut -d: -f1)
[ "$touch_at" -lt "$build_at" ] || rs_fail "the start marker is left after the preview is built"
rs_ok "the start marker is left before anything is made"
grep -qE '^ *find /private/tmp -maxdepth 1 -newer ~/\.abk-try-N-start$' "$SECTION" \
  || rs_fail "teardown does not list the temporary files newer than the marker"
find_at=$(grep -nE '^ *find /private/tmp -maxdepth 1 -newer ' "$SECTION" | cut -d: -f1)
mark_trash_at=$(grep -nE '^ *trash ~/\.abk-try-N-start$' "$SECTION" | cut -d: -f1)
[ -n "$mark_trash_at" ] || rs_fail "teardown does not move the start marker to the Trash"
[ "$mark_trash_at" -gt "$find_at" ] || rs_fail "the start marker goes before the listing that needs it"
rs_ok "teardown lists the run's temporary files by the marker, then trashes the marker"
if grep -qF 'head -20' "$SECTION"; then
  rs_fail "the section still lists temporary files by a fixed count"
fi
rs_ok "no listing is cut to a fixed count"
if grep -qE 'rm +-[a-z]*r[a-z]*f|rm +-[a-z]*f[a-z]*r' "$SECTION"; then
  rs_fail "the section uses a recursive forced delete"
fi
rs_ok "the section never uses a recursive forced delete"

rs_rule "when it is due" 'before any release that touches founding or `/ship`'
rs_rule "what it asks of the person" 'one github click'
rs_rule "the lockfile records a local source" '"sourcetype": "local"'
rs_rule "a local install cannot update" 'cannot update later'
rs_rule "maintain can fail there" 'visit there can fail once that folder is gone'
rs_rule "the menu check" 'marked one recipe as recommended'
rs_rule "the Recipe line check" "grep '\\^recipe:' agents\\.md"
rs_rule "the founding-menu check" 'grep founding-menu \.ai-build-kit-maintenance'
rs_rule "a failure is filed, not fixed in place" 'do not fix it in the throwaway project'
rs_rule "the password file is private" 'umask 077'
rs_rule "the password is copied without printing" 'pbcopy < ~/\.config/abk-try-n/db\.pw'
rs_rule "secrets stay out of the chat" 'a secret never goes into the chat'
rs_rule "Supabase is deleted in the dashboard" 'delete the supabase project in the dashboard'
rs_rule "what the log records" 'the commit it was built from'
rs_rule "the release waits" 'the release waits'
rs_rule "names the repository at founding" 'name it `abk-try-n` in the first folder'
rs_rule "names the Vercel project in the ship request" 'asking for a vercel project named `abk-try-n`'
rs_rule "GitHub asks for a passkey first" 'asks for a passkey or password'
rs_rule "the clipboard is emptied" 'pbcopy < /dev/null'
rs_rule "the Vercel app keeps its selection" 'add `abk-try-n` to that selection, and never replace or clear it'
rs_rule "the Vercel app stays installed" 'so leave the app installed'
rs_rule "only an app installed for the run goes" 'only if it was installed for this run, uninstall it'
rs_rule "the person runs the scope refreshes" 'which an agent cannot give, so the person runs it'
rs_rule "the scope comes off even if it was there before" 'even when it was there before the run'
rs_rule "an unknown item is left alone" 'if you cannot tell who made an item, leave it'
rs_rule "a scope already there is not added" 'already there from an earlier run, skip the first refresh'
rs_rule "why the password mixes case" 'marks a lowercase hex password as not secure enough'
rs_rule "the password is random" '40 letters and digits drawn at random, in mixed case'
rs_rule "the stale form message" 'check the project list rather than the form'
rs_rule "the backups are named" '~/backups/abk-try-n` holds the database'
rs_rule "the kit's temporary files are named" 'restore-test folders and logs'
rs_rule "only the run's temporary files go" 'newer than the marker from step 1, trash what the run made'
rs_rule "a clean main is required" 'the status must print nothing'

# The rules are read from the extracted section, so a copy of a phrase
# elsewhere in MAINTAINING.md cannot hide its removal here. The mutation audit
# lists them against the real document, since that is the file it edits, and
# the section is gone by the time it reads the list.
if [ -n "${RS_LIST:-}" ]; then
  rs_guard "$DOC" "MAINTAINING.md's pre-release run"
else
  rs_guard "$SECTION" "the pre-release run section"
fi

rs_done
