#!/usr/bin/env sh
# check-tooling.sh: check what the setup tooling report says and when it stops.
#
# The report is what catches a missing tool before founding leans on it, so the
# thing that matters is the exit code: it stops with a non-zero result when a
# tool that blocks founding is absent, and returns cleanly when they are all
# ready. A grep over the script cannot judge that. This runs it against a set of
# throwaway PATHs and reads what it does.
#
# The report never uses the person's own GitHub sign-in. With no App it asks
# GitHub nothing at all, so a stand-in for the GitHub command line tool that
# logs every call shows an empty log. With the stand-in App, the repository is
# read through loop/github.py, as the App, with the full GitHub stand-in.
#
# Everything here runs in a throwaway directory. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/kit/scripts/check-tooling.sh"

FAIL=0
fail() {
  echo "FAIL: $1" >&2
  FAIL=1
}
pass() {
  echo "ok: $1"
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

# A bin holding only the tools each case is meant to have. Git, python3, and the
# shell are the real ones, reached through a symlink, so the controlled PATH
# still resolves the shebang and the report's own commands, and only the GitHub
# command line tool is ever the stand-in. Dropping gh from this bin is what makes
# it genuinely missing.
mkdir -p "$WORK/bin"
ln -s "$(command -v git)" "$WORK/bin/git"
ln -s "$(command -v python3)" "$WORK/bin/python3"
ln -s "$(command -v sh)" "$WORK/bin/sh"
ln -s "$(command -v openssl)" "$WORK/bin/openssl"

# A stand-in that logs every call and answers as a signed-in account would.
# The report must never call it, so the log is the evidence.
write_gh() {
  cat >"$WORK/bin/gh" <<SH
#!/usr/bin/env sh
echo "\$*" >> "$WORK/gh.log"
case "\$1 \$2" in
  "auth status") exit 0 ;;
  "repo view") echo '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}' ;;
  *) echo '{}' ;;
esac
SH
  chmod +x "$WORK/bin/gh"
}
gh_untouched() {
  [ ! -s "$WORK/gh.log" ]
}

run_check() {
  # Run the report with PATH set to the controlled bin alone, so a tool left out
  # of it is genuinely missing. The report reads `origin`, so it runs from a
  # folder of its own: run from this repository, it would find the kit's own
  # repository and rightly skip the checks these cases are about.
  (cd "$WORK/plain" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" 2>&1)
}
mkdir -p "$WORK/plain"
git -C "$WORK/plain" init -q
git init -q --bare "$WORK/plain-origin.git"
git -C "$WORK/plain" remote add origin "$WORK/plain-origin.git"

NOTICE="The GitHub App is not set up yet, so this report does not look at GitHub"

echo "== Everything ready, no App =="

write_gh
: > "$WORK/gh.log"
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "the report returns cleanly when every tool is ready" \
  || fail "a clean setup returned $code"
printf '%s\n' "$out" | grep -q "Every tool the kit needs" \
  && pass "it says the tools are ready" \
  || fail "the ready summary is missing"
printf '%s\n' "$out" | grep -qF "$NOTICE" \
  && pass "with no App it prints the one notice" \
  || fail "the no-App notice is missing: $out"
gh_untouched \
  && pass "with no App the report starts no gh at all, so it never uses the person's sign-in" \
  || fail "the report called gh with no App: $(cat "$WORK/gh.log")"
printf '%s\n' "$out" | grep -q "gh auth status" \
  && pass "it names gh auth status for the person to run, and does not run it" \
  || fail "the report does not name gh auth status for the person"

out=$(cd "$WORK/plain" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" --for-run 2>&1) && code=0 || code=$?
[ "$code" -eq 0 ] && gh_untouched \
  && pass "--for-run with no App passes and starts no gh" \
  || fail "--for-run with no App returned $code or called gh: $(cat "$WORK/gh.log")"

echo "== openssl missing =="

# The App key is made and read with openssl, so a run cannot start without it.
rm -f "$WORK/bin/openssl"
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "a missing openssl stops the report" \
  || fail "a missing openssl did not stop the report"
printf '%s\n' "$out" | grep -q "openssl is missing" \
  && pass "it names openssl" \
  || fail "the missing openssl line is missing"
ln -s "$(command -v openssl)" "$WORK/bin/openssl"

echo "== The GitHub command line tool missing =="

# Before the App exists a project shapes and runs locally, so a missing gh is
# named and blocks nothing, in either mode.
rm -f "$WORK/bin/gh"
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "a missing GitHub command line tool does not stop founding" \
  || fail "a missing GitHub command line tool returned $code"
printf '%s\n' "$out" | grep -q "GitHub command line tool is missing" \
  && pass "it names the missing tool" \
  || fail "the missing-tool line is missing"
out=$(cd "$WORK/plain" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" --for-run 2>&1) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "--for-run with no gh and no App still starts a local run" \
  || fail "--for-run with no gh returned $code"

echo "== Signed out, offline or refused: never asked =="

# A gh that fails every call, as one signed out or offline does. The report
# never calls it, so nothing about the sign-in sets blocked.
cat >"$WORK/bin/gh" <<SH
#!/usr/bin/env sh
echo "\$*" >> "$WORK/gh.log"
echo 'HTTP 401: Requires authentication' >&2
exit 1
SH
chmod +x "$WORK/bin/gh"
: > "$WORK/gh.log"
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] && gh_untouched \
  && pass "a signed-out gh is never asked and stops nothing" \
  || fail "a signed-out gh returned $code or was called: $(cat "$WORK/gh.log")"
write_gh

echo "== With the App: the repository is read as the App =="

# The full GitHub stand-in, a stand-in App key, and the App's settings in the
# project. The bin holds the stand-in gh beside the real tools.
APP_BIN="$WORK/app-bin"
mkdir -p "$APP_BIN"
for tool in git python3 sh openssl; do
  ln -s "$(command -v "$tool")" "$APP_BIN/$tool"
done
ln -s "$ROOT/tests/stand-ins/fake-github/gh" "$APP_BIN/gh"
APP_KEY=$("$ROOT/tests/stand-ins/fake-app/make-key.sh" "$WORK/app-key")
APP_PROJECT="$WORK/app-project"
git init -q --bare "$WORK/app-origin.git"
git -C "$WORK/app-origin.git" symbolic-ref HEAD refs/heads/main
git init -q "$APP_PROJECT"
git -C "$APP_PROJECT" remote add origin "$WORK/app-origin.git"
mkdir -p "$APP_PROJECT/.agents/loop"
python3 - "$ROOT/tests/stand-ins/fake-app/app.json" "$APP_KEY" "$APP_PROJECT/.agents/loop/local.json" <<'PY'
import json, sys
app = json.load(open(sys.argv[1]))
json.dump({"github_app": {"app_id": app["app_id"], "installation_id": app["installation_id"],
                          "slug": app["slug"], "key_file": sys.argv[2]}}, open(sys.argv[3], "w"))
PY
app_check() {
  # app_check <state json> [args...]
  printf '%s\n' "$1" > "$WORK/app-state.json"
  shift
  : > "$WORK/app-gh.log"
  (cd "$APP_PROJECT" && PATH="$APP_BIN" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" \
    FAKE_GH_STATE="$WORK/app-state.json" FAKE_GH_LOG="$WORK/app-gh.log" FAKE_APP_KEY="$APP_KEY" \
    "$CHECK" "$@" 2>&1)
}
out=$(app_check '{"repo": "someone/project", "next": 1, "issues": []}') && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "with the App the report returns cleanly" \
  || fail "with the App the report returned $code: $out"
printf '%s\n' "$out" | grep -q "Issues are switched on" \
  && pass "it reports issues switched on, read as the App" \
  || fail "the issues-on line is missing: $out"
printf '%s\n' "$out" | grep -q "Labels can be put in order" \
  && pass "it reports the labels can be put in order" \
  || fail "the labels line is missing: $out"
printf '%s\n' "$out" | grep -qF "$NOTICE" \
  && fail "the no-App notice was printed with the App set up" \
  || pass "with the App there is no no-App notice"
grep -q "APP-TOKEN" "$WORK/app-gh.log" && grep -q "^AS	ai-loop-kit-stand-in\[bot\]" "$WORK/app-gh.log" \
  && pass "the repository facts come through the App's token" \
  || fail "the repository was not read as the App: $(cat "$WORK/app-gh.log")"
grep -q "auth status" "$WORK/app-gh.log" \
  && fail "the report asked for the person's sign-in" \
  || pass "the report never asks for the person's sign-in"

out=$(app_check '{"repo": "someone/project", "next": 1, "issues": [], "has_issues": false, "viewer_permission": "READ"}') && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "issues off and read-only access do not stop founding" \
  || fail "a soft repository state returned $code"
printf '%s\n' "$out" | grep -q "Issues are switched off" \
  && pass "it reports issues switched off" \
  || fail "the issues-off line is missing"
printf '%s\n' "$out" | grep -q "cannot create or delete labels" \
  && pass "it reports the labels cannot be put in order" \
  || fail "the no-labels line is missing"

out=$(app_check '{"repo": "someone/project", "next": 1, "issues": []}' --for-run) && code=0 || code=$?
[ "$code" -eq 0 ] && ! grep -q "repo view" "$WORK/app-gh.log" \
  && pass "--for-run checks only that gh is installed, and reads no repository" \
  || fail "--for-run with the App returned $code or read the repository: $(cat "$WORK/app-gh.log")"

rm -f "$APP_BIN/gh"
out=$(app_check '{"repo": "someone/project", "next": 1, "issues": []}') && code=0 || code=$?
[ "$code" -eq 0 ] && printf '%s\n' "$out" | grep -q "GitHub command line tool is missing" \
  && pass "with the App and no gh, the report names gh and still founds" \
  || fail "with the App and no gh the report returned $code: $out"
ln -s "$ROOT/tests/stand-ins/fake-github/gh" "$APP_BIN/gh"

echo "== A Git older than worktrees =="

# A run on Claude Code gives each piece its own worktree and removes it with
# `git worktree remove`, which Git has had since 2.17. An older Git still
# founds and builds, one piece after another in one folder, so the report
# names the version and blocks nothing.
write_gh
out=$(run_check) && code=0 || code=$?
printf '%s\n' "$out" | grep -q "older than 2.17" \
  && fail "a current Git was reported as older than 2.17" \
  || pass "a current Git gets no version line"
real_git=$(command -v git)
rm -f "$WORK/bin/git"
cat >"$WORK/bin/git" <<SH
#!/usr/bin/env sh
[ "\$1" = "--version" ] && { echo "git version 2.16.4"; exit 0; }
exec "$real_git" "\$@"
SH
chmod +x "$WORK/bin/git"
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "an older Git does not stop founding" \
  || fail "an older Git returned $code"
printf '%s\n' "$out" | grep -q "Git is version 2.16.4, older than 2.17" \
  && pass "it names the older Git's version" \
  || fail "the older-Git line is missing"
rm -f "$WORK/bin/git"
ln -s "$real_git" "$WORK/bin/git"

echo "== The App, no repository yet =="

# A fresh project has no repository, so the issue and label checks wait.
git -C "$APP_PROJECT" remote remove origin
out=$(app_check '{"repo": "someone/project", "next": 1, "issues": []}') && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "a fresh project with no repository still returns cleanly" \
  || fail "no repository returned $code"
printf '%s\n' "$out" | grep -q "No GitHub repository is set up yet" \
  && pass "it says the repository checks wait until one exists" \
  || fail "the no-repository line is missing: $out"
git -C "$APP_PROJECT" remote add origin "$WORK/app-origin.git"

echo "== A whole copy that still points at the kit's own repository =="

# Founding from a whole copy of the kit can keep the kit's `origin`. The GitHub
# tool would then open the person's pieces on the kit's repository, so the
# report says so, and founding asks for their own. It does not stop founding.
# A fork under another owner is the person's own and is left alone. `origin`
# is read with Git alone. The stand-in logs every call, so a GitHub call made
# anyway shows.
kit_case() {
  # kit_case <description> <origin url> <kit|not-kit>
  project="$WORK/copy-$(printf '%s' "$1" | tr -c 'a-z' '-')"
  mkdir -p "$project"
  git -C "$project" init -q
  git -C "$project" remote add origin "$2"
  : > "$WORK/gh.log"
  out=$(cd "$project" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" 2>&1) && code=0 || code=$?
  [ "$code" -eq 0 ] || fail "$1: the report stopped founding with $code"
  if [ "$3" = kit ]; then
    printf '%s\n' "$out" | grep -q "still points at the kit's own repository, gwpicard/ai-loop-kit: no piece is opened there and nothing is pushed there" \
      && ! printf '%s\n' "$out" | grep -q "Issues are switched\|Labels can" \
      && pass "$1: the report names the kit's repository and skips its lookups" \
      || fail "$1: the kit's repository was not caught"
  else
    printf '%s\n' "$out" | grep -q "kit's own repository" \
      && fail "$1: a repository of the person's own was taken for the kit's" \
      || pass "$1: the person's own repository is left alone"
  fi
  gh_untouched \
    && pass "$1: the report asks GitHub nothing" \
    || fail "$1: the report called gh: $(cat "$WORK/gh.log")"
}
kit_case "an https origin" "https://github.com/gwpicard/ai-loop-kit.git" kit
kit_case "an ssh origin in capitals" "git@github.com:GWPicard/AI-Loop-Kit.git" kit
kit_case "an origin with no .git" "https://github.com/gwpicard/ai-loop-kit" kit
kit_case "a fork under another owner" "https://github.com/someone/ai-loop-kit.git" not-kit
kit_case "a name that only starts like the kit's" "https://github.com/gwpicard/ai-loop-kit-notes.git" not-kit

# Asked for a run (--for-run), the kit's own repository is a refusal, with its
# own exit code, and a project of the person's own is not.
kit_project="$WORK/run-on-kit"
mkdir -p "$kit_project"
git -C "$kit_project" init -q
git -C "$kit_project" remote add origin "https://github.com/gwpicard/ai-loop-kit.git"
out=$(cd "$kit_project" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" --for-run 2>&1) && code=0 || code=$?
[ "$code" -eq 3 ] \
  && pass "--for-run refuses a project that points at the kit's own repository (exit 3)" \
  || fail "--for-run on the kit's repository returned $code"
out=$(cd "$WORK/plain" && PATH="$WORK/bin" HOME="$HOME" AI_LOOP_KIT_DATA="$WORK/data" "$CHECK" --for-run 2>&1) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "--for-run passes a project of the person's own" \
  || fail "--for-run on the person's own repository returned $code"

echo "== The tools a recipe's checks run =="

# A recipe names the command-line tools its launch checks run. They are asked
# for only when a recipe is named, and a missing one never stops founding, since
# a project that uses no recipe needs none of them. The real recipes are read
# where they are, on the menu or still waiting for their real run.
write_gh
out=$(run_check) && code=0 || code=$?
printf '%s\n' "$out" | grep -q "launch checks" \
  && fail "a project that names no recipe was asked about recipe tools" \
  || pass "with no recipe named, no recipe tool is asked about"

printf '%s\n' 'Fits: a test' 'Command-line tools: git, stand-in-deploy-tool' > "$WORK/recipe.md"
out=$(PATH="$WORK/bin" HOME="$HOME" "$CHECK" --recipe "$WORK/recipe.md" 2>&1) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "a missing recipe tool does not stop founding" \
  || fail "a missing recipe tool returned $code"
printf '%s\n' "$out" | grep -q "^git is ready: the recipe's launch checks run it" \
  && pass "it reports a recipe tool that is ready" \
  || fail "the ready recipe tool line is missing"
printf '%s\n' "$out" | grep -q "^stand-in-deploy-tool is missing: .*before the first /ship. It does not stop founding" \
  && pass "it names a missing recipe tool as needed before the first launch" \
  || fail "the missing recipe tool line is missing"

rm -f "$WORK/bin/openssl"
out=$(PATH="$WORK/bin" HOME="$HOME" "$CHECK" --recipe "$WORK/recipe.md" 2>&1) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "naming a recipe does not excuse a missing founding tool" \
  || fail "a recipe hid the missing openssl"
ln -s "$(command -v openssl)" "$WORK/bin/openssl"

for name in nextjs-supabase-on-vercel nextjs-supabase-on-coolify; do
  recipe="$ROOT/kit/recipes/$name.md"
  [ -f "$recipe" ] || fail "$name is not in kit/recipes"
  out=$(PATH="$WORK/bin" HOME="$HOME" "$CHECK" --recipe "$recipe" 2>&1) && code=0 || code=$?
  [ "$code" -eq 0 ] || fail "$name's tools stopped founding"
  for tool in supabase docker psql curl git; do
    printf '%s\n' "$out" | grep -q "^$tool is \(ready\|missing\)" || fail "$name's report says nothing about $tool"
  done
  pass "$name's tools are each reported, and none stops founding"
done

echo "== What the walk-through can look with =="

# The walk-through turns a PDF, a document or an SVG into pictures, and takes a
# screenshot with Playwright where the coding agent has no browser tool. Each
# renderer is reported as ready or missing, a missing one prints the install
# line for this platform, and none of them ever stops founding. The kit prints
# the line and never runs it. The platform is read from files, as the report
# reads it, so the case holds on a Mac and on the hosted Ubuntu machine.
if [ -f /System/Library/CoreServices/SystemVersion.plist ]; then
  want_pdf="brew install poppler"
  want_office="brew install --cask libreoffice"
  want_svg="brew install imagemagick"
elif [ -f /etc/debian_version ]; then
  want_pdf="sudo apt install poppler-utils"
  want_office="sudo apt install libreoffice"
  want_svg="sudo apt install imagemagick"
else
  want_pdf="package manager"
  want_office="package manager"
  want_svg="package manager"
fi
want_playwright="npm install --save-dev playwright && npx playwright install --with-deps chromium"

stub() {
  # stub <name> <exit code>: a command that answers with that code.
  printf '#!/bin/sh\nexit %s\n' "$2" > "$WORK/bin/$1"
  chmod +x "$WORK/bin/$1"
}
eyes_line() {
  printf '%s\n' "$out" | grep -F -- "$1" >/dev/null
}

write_gh
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "with no renderer at all, founding is not stopped" \
  || fail "missing renderers returned $code"
eyes_line "pdftoppm is missing" && eyes_line "$want_pdf" \
  && pass "a missing pdftoppm is named with its install line" \
  || fail "the missing pdftoppm line or its install line is missing"
eyes_line "soffice is missing" && eyes_line "$want_office" \
  && pass "a missing soffice is named with its install line" \
  || fail "the missing soffice line or its install line is missing"
eyes_line "magick is missing" && eyes_line "$want_svg" \
  && pass "a missing magick is named with its install line" \
  || fail "the missing magick line or its install line is missing"
eyes_line "Playwright is missing" && eyes_line "$want_playwright" \
  && pass "a missing Playwright is named with its install line" \
  || fail "the missing Playwright line or its install line is missing"
eyes_line "It does not stop founding" \
  && pass "each missing renderer says it does not stop founding" \
  || fail "the missing renderers do not say founding goes on"

# npx here, but Playwright not: npx --no-install fails, as it does in a project
# without Playwright.
stub npx 1
out=$(run_check) && code=0 || code=$?
eyes_line "Playwright is missing" \
  && pass "npx that cannot find Playwright counts as Playwright missing" \
  || fail "npx without Playwright was taken for Playwright"

stub pdftoppm 0
stub soffice 0
stub magick 0
stub npx 0
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "with every renderer ready, the report still returns cleanly" \
  || fail "every renderer ready returned $code"
for tool in pdftoppm soffice magick Playwright; do
  eyes_line "$tool is ready" \
    && pass "$tool is reported as ready" \
    || fail "$tool is not reported as ready"
done
printf '%s\n' "$out" | grep -q "brew install\|apt install\|package manager" \
  && fail "an install line was printed with nothing missing" \
  || pass "no install command appears when every renderer is ready"

# The other names the same tools go by: libreoffice for soffice, and the older
# ImageMagick's convert for magick.
rm -f "$WORK/bin/soffice" "$WORK/bin/magick"
stub libreoffice 0
stub convert 0
out=$(run_check) && code=0 || code=$?
eyes_line "soffice is ready" \
  && pass "libreoffice counts as soffice" \
  || fail "libreoffice was not taken for soffice"
eyes_line "magick is ready" \
  && pass "an older ImageMagick's convert counts as magick" \
  || fail "convert was not taken for magick"

# A missing founding tool still stops founding with every renderer ready.
rm -f "$WORK/bin/openssl"
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "renderers being ready do not excuse a missing founding tool" \
  || fail "ready renderers hid the missing openssl"
ln -s "$(command -v openssl)" "$WORK/bin/openssl"
rm -f "$WORK/bin/pdftoppm" "$WORK/bin/libreoffice" "$WORK/bin/convert" "$WORK/bin/npx"
write_gh

echo
if [ "$FAIL" -eq 0 ]; then
  echo "check-tooling.sh: all checks passed"
else
  echo "check-tooling.sh: FAILED" >&2
fi
exit "$FAIL"
