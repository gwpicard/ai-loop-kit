#!/usr/bin/env sh
# check-tooling.sh: check what the setup tooling report says and when it stops.
#
# The report is what catches a missing tool before founding leans on it, so the
# thing that matters is the exit code: it stops with a non-zero result when a
# tool that blocks founding is absent, and returns cleanly when they are all
# ready. A grep over the script cannot judge that. This runs it against a set of
# throwaway PATHs and reads what it does.
#
# A stand-in for the GitHub command line tool supplies the sign-in and the
# repository. The report asks gh for JSON and filters it with python3, which is
# what makes that substitution honest.
#
# Everything here runs in a throwaway directory. No network, no account.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHECK="$ROOT/skills/setup-ai-build-kit/scripts/check-tooling.sh"

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

# A stand-in that answers only the sign-in and the repository lookup the report
# makes, with echo alone so it needs nothing else on the controlled PATH.
write_gh() {
  cat >"$WORK/bin/gh" <<SH
#!/usr/bin/env sh
case "\$1 \$2" in
  "auth status") exit $1 ;;
  "repo view") echo '$2' ;;
  *) echo '{}' ;;
esac
SH
  chmod +x "$WORK/bin/gh"
}

run_check() {
  # Run the report with PATH set to the controlled bin alone, so a tool left out
  # of it is genuinely missing. The report reads `origin`, so it runs from a
  # folder of its own: run from this repository, it would find the kit's own
  # repository and rightly skip the checks these cases are about.
  (cd "$WORK/plain" && PATH="$WORK/bin" HOME="$HOME" "$CHECK" 2>&1)
}
mkdir -p "$WORK/plain"

echo "== Everything ready =="

write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "the report returns cleanly when every tool is ready" \
  || fail "a clean setup returned $code"
printf '%s\n' "$out" | grep -q "Every tool the kit needs" \
  && pass "it says the tools are ready" \
  || fail "the ready summary is missing"
printf '%s\n' "$out" | grep -q "Issues are switched on" \
  && pass "it reports issues switched on" \
  || fail "the issues-on line is missing"
printf '%s\n' "$out" | grep -q "Labels can be put in order" \
  && pass "it reports the account can manage labels" \
  || fail "the labels line is missing"

echo "== The GitHub command line tool missing =="

rm -f "$WORK/bin/gh"
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "a missing GitHub command line tool stops founding" \
  || fail "a missing GitHub command line tool did not stop the report"
printf '%s\n' "$out" | grep -q "GitHub command line tool is missing" \
  && pass "it names the missing tool" \
  || fail "the missing-tool line is missing"

echo "== Installed but signed out =="

write_gh 1 '{}'
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "nobody signed in stops founding" \
  || fail "signed out did not stop the report"
printf '%s\n' "$out" | grep -q "nobody is signed in" \
  && pass "it says nobody is signed in" \
  || fail "the signed-out line is missing"

echo "== Access failures are not called signed out =="

for reason in network permission; do
  case "$reason" in
    network) message='error connecting to api.github.com' ;;
    permission) message='HTTP 403: Resource not accessible by integration' ;;
  esac
  cat >"$WORK/bin/gh" <<SH
#!/usr/bin/env sh
echo '$message' >&2
exit 1
SH
  chmod +x "$WORK/bin/gh"
  out=$(run_check) && code=0 || code=$?
  [ "$code" -ne 0 ] && printf '%s\n' "$out" | grep -q "$reason" \
    && ! printf '%s\n' "$out" | grep -q 'nobody is signed in' \
    && pass "$reason failure blocks founding with the correct recovery" \
    || fail "$reason failure was called signed out or did not block founding: $out"
done

echo "== Authentication cannot be verified inside the session =="
cat >"$WORK/bin/gh" <<'SH'
#!/usr/bin/env sh
echo 'HTTP 401: Requires authentication' >&2
exit 1
SH
chmod +x "$WORK/bin/gh"
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] && printf '%s\n' "$out" | grep -q 'GH_TOKEN' \
  && ! printf '%s\n' "$out" | grep -q 'nobody is signed in' \
  && pass "authentication refusal asks about credential sources without claiming sign-out" \
  || fail "authentication refusal skipped credential diagnosis: $out"

echo "== Signed in, but a soft repository state =="

# Issues off and a read-only account do not block founding: the report says so
# and returns cleanly, because the pieces still become issues.
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":false,"viewerPermission":"READ"}'
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "issues off and read-only access do not stop founding" \
  || fail "a soft repository state returned $code"
printf '%s\n' "$out" | grep -q "Issues are switched off" \
  && pass "it reports issues switched off" \
  || fail "the issues-off line is missing"
printf '%s\n' "$out" | grep -q "cannot create or delete labels" \
  && pass "it reports the account cannot manage labels" \
  || fail "the no-labels line is missing"

echo "== A Git older than worktrees =="

# A run on Claude Code gives each piece its own worktree and removes it with
# `git worktree remove`, which Git has had since 2.17. An older Git still
# founds and builds, one piece after another in one folder, so the report
# names the version and blocks nothing.
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
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

echo "== Signed in, no repository yet =="

# A fresh project has no repository, so the issue and label checks wait.
write_gh 0 ''
out=$(run_check) && code=0 || code=$?
[ "$code" -eq 0 ] \
  && pass "a fresh project with no repository still returns cleanly" \
  || fail "no repository returned $code"
printf '%s\n' "$out" | grep -q "No GitHub repository is set up yet" \
  && pass "it says the repository checks wait until one exists" \
  || fail "the no-repository line is missing"

echo "== A whole copy that still points at the kit's own repository =="

# Founding from a whole copy of the kit can keep the kit's `origin`. The GitHub
# tool would then open the person's pieces on the kit's repository, so the
# report says so and skips the lookups, and founding asks for their own. It
# does not stop founding. A fork under another owner is the person's own and
# is left alone. The stand-in logs every call, so a lookup made anyway shows.
write_logging_gh() {
  cat >"$WORK/bin/gh" <<SH
#!/usr/bin/env sh
echo "\$*" >> "$WORK/gh.log"
case "\$1 \$2" in
  "auth status") exit 0 ;;
  "repo view") echo '$1' ;;
  *) echo '{}' ;;
esac
SH
  chmod +x "$WORK/bin/gh"
}
kit_case() {
  # kit_case <description> <origin url> <what gh reports> <kit|not-kit>
  project="$WORK/copy-$(printf '%s' "$1" | tr -c 'a-z' '-')"
  mkdir -p "$project"
  git -C "$project" init -q
  [ -z "$2" ] || git -C "$project" remote add origin "$2"
  write_logging_gh "$3"
  : > "$WORK/gh.log"
  out=$(cd "$project" && PATH="$WORK/bin" HOME="$HOME" "$CHECK" 2>&1) && code=0 || code=$?
  [ "$code" -eq 0 ] || fail "$1: the report stopped founding with $code"
  if [ "$4" = kit ]; then
    printf '%s\n' "$out" | grep -q "still points at the kit's own repository, gwpicard/ai-build-kit: no piece is opened there and nothing is pushed there" \
      && ! printf '%s\n' "$out" | grep -q "Issues are switched\|Labels can" \
      && pass "$1: the report names the kit's repository and skips its lookups" \
      || fail "$1: the kit's repository was not caught"
    # Where `origin` names the kit, the report must not ask GitHub at all.
    if [ -n "$2" ]; then
      grep -q "repo view" "$WORK/gh.log" \
        && fail "$1: the report asked GitHub about the kit's repository anyway" \
        || pass "$1: the report asks GitHub nothing about it"
    fi
  else
    printf '%s\n' "$out" | grep -q "kit's own repository" \
      && fail "$1: a repository of the person's own was taken for the kit's" \
      || pass "$1: the person's own repository is left alone"
  fi
}
KIT_JSON='{"nameWithOwner":"gwpicard/ai-build-kit","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
OWN_JSON='{"nameWithOwner":"someone/ai-build-kit","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
# Where the origin names the kit, the stand-in reports a neutral name, so only
# the origin match can catch it. The one case with no origin is the only one
# that leans on the name GitHub reports.
NEUTRAL_JSON='{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
kit_case "an https origin" "https://github.com/gwpicard/ai-build-kit.git" "$NEUTRAL_JSON" kit
kit_case "an ssh origin in capitals" "git@github.com:GWPicard/AI-Build-Kit.git" "$NEUTRAL_JSON" kit
kit_case "an origin with no .git" "https://github.com/gwpicard/ai-build-kit" "$NEUTRAL_JSON" kit
kit_case "a name only GitHub reports" "" "$KIT_JSON" kit
kit_case "a fork under another owner" "https://github.com/someone/ai-build-kit.git" "$OWN_JSON" not-kit
kit_case "a name that only starts like the kit's" "https://github.com/gwpicard/ai-build-kit-notes.git" '{"nameWithOwner":"gwpicard/ai-build-kit-notes","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}' not-kit
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'

echo "== The tools a recipe's checks run =="

# A recipe names the command-line tools its launch checks run. They are asked
# for only when a recipe is named, and a missing one never stops founding, since
# a project that uses no recipe needs none of them. The real recipes are read
# where they are, on the menu or still waiting for their real run.
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
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

rm -f "$WORK/bin/gh"
out=$(PATH="$WORK/bin" HOME="$HOME" "$CHECK" --recipe "$WORK/recipe.md" 2>&1) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "naming a recipe does not excuse a missing founding tool" \
  || fail "a recipe hid the missing GitHub command line tool"
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'

for name in nextjs-supabase-on-vercel nextjs-supabase-on-coolify; do
  recipe="$ROOT/skills/ship/recipes/$name.md"
  [ -f "$recipe" ] || recipe="$ROOT/tests/recipes-awaiting-run/$name.md"
  [ -f "$recipe" ] || { fail "$name is neither on the menu nor waiting"; continue; }
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

write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'
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
rm -f "$WORK/bin/gh"
out=$(run_check) && code=0 || code=$?
[ "$code" -ne 0 ] \
  && pass "renderers being ready do not excuse a missing founding tool" \
  || fail "ready renderers hid the missing GitHub command line tool"
rm -f "$WORK/bin/pdftoppm" "$WORK/bin/libreoffice" "$WORK/bin/convert" "$WORK/bin/npx"
write_gh 0 '{"nameWithOwner":"someone/project","hasIssuesEnabled":true,"viewerPermission":"ADMIN"}'

echo
if [ "$FAIL" -eq 0 ]; then
  echo "check-tooling.sh: all checks passed"
else
  echo "check-tooling.sh: FAILED" >&2
fi
exit "$FAIL"
