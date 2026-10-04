#!/usr/bin/env sh
# check-tooling.sh: say whether the tools the kit itself needs are ready, before
# setup leans on them.
#
# The kit keeps a project's pieces as GitHub issues and prints them with a small
# Python filter, so three tools have to be here before the pieces can be founded:
# Git, the GitHub command line tool, and python3. This reports which are ready
# and which are not, in plain words, and stops with a non-zero result when one
# that blocks founding is missing, so a gap is caught here rather than at the
# later step that creates the issues.
#
# It changes nothing. It reaches no further than the sign-in and repository
# lookups the report needs.
#
# jq is not required. The kit filters JSON with python3 on purpose, which is
# also what lets the test harness stand in for the GitHub command line tool.
#
# Run from anywhere inside the project. With --recipe <recipe file>, it also
# reports the command-line tools that recipe's launch checks run. Those never
# stop founding. Nor do the tools the walk-through looks with, which it always
# reports, with the install command for each one missing.

set -eu

recipe=""
if [ "${1:-}" = "--recipe" ]; then
  recipe=${2:-}
  [ -n "$recipe" ] || { echo "usage: check-tooling.sh [--recipe <recipe file>]" >&2; exit 2; }
fi

blocked=0

# 1. The tools the kit's own scripts run.
if command -v git >/dev/null 2>&1; then
  echo "Git is ready: the kit saves each project version with it."
  # A run on Claude Code builds each piece in its own worktree, and clears it
  # away with `git worktree remove`, which Git has offered since 2.17. An
  # older Git still founds and builds one piece at a time, so this says so and
  # blocks nothing. The version is read with the
  # shell alone, since the report may run with nothing else on its PATH.
  git_version=$(git --version 2>/dev/null || true)
  git_version=${git_version#git version }
  git_major=${git_version%%.*}
  git_rest=${git_version#*.}
  git_minor=${git_rest%%[!0-9]*}
  case "$git_major$git_minor" in
    '' | *[!0-9]*) ;;
    *)
      if [ "$git_major" -lt 2 ] || { [ "$git_major" -eq 2 ] && [ "$git_minor" -lt 17 ]; }; then
        echo "Git is version $git_version, older than 2.17: a run cannot give each piece its own worktree, so it builds them one after another in this folder. Updating Git lifts that."
      fi
      ;;
  esac
else
  echo "Git is missing: install it so the kit can save project versions. See manual-setup.md."
  blocked=1
fi

if command -v python3 >/dev/null 2>&1; then
  echo "python3 is ready: the kit reads the issue list with it to print your pieces."
else
  echo "python3 is missing: install it so the kit can print your pieces. See manual-setup.md."
  blocked=1
fi

gh_ready=no
if command -v gh >/dev/null 2>&1; then
  if gh_status=$(gh auth status 2>&1); then
    echo "The GitHub command line tool is ready: your pieces are kept as issues, and you are signed in."
    gh_ready=yes
  else
    # Do not print auth status: it may include credential diagnostics. A failed
    # network check is not evidence that the account has signed out.
    case "$gh_status" in
      *"error connecting"* | *"Could not resolve host"* | *"dial tcp"* | *"timed out"*)
        echo "The GitHub command line tool cannot reach GitHub: network access may be blocked or unavailable. Request GitHub access for this session, then run this report again." ;;
      *"HTTP 403"* | *"Resource not accessible"* | *"permission denied"*)
        echo "The GitHub command line tool was refused permission: check this session's GitHub access and the signed-in account's permissions, then run this report again." ;;
      *"HTTP 401"* | *"Bad credentials"* | *"Failed to log in"*)
        echo "The GitHub command line tool could not authenticate: compare GH_TOKEN and GITHUB_TOKEN presence and gh auth status in this session and your terminal before signing in again. A sandbox may not read your stored login." ;;
      *)
        echo "The GitHub command line tool is installed but nobody is signed in, or the sign-in could not be verified: run gh auth login if signed out. Check this session's GitHub access otherwise. See manual-setup.md." ;;
    esac
    blocked=1
  fi
else
  echo "The GitHub command line tool is missing: install it and sign in, because the pieces are kept as issues. See manual-setup.md."
  blocked=1
fi

# 2. Whether this project still points at the kit's own repository. A project
# founded from a whole copy of the kit can keep the kit's `origin`, and then the
# GitHub tool would open the project's pieces as issues there, and a later push
# would aim the person's code at it. `origin` is read with Git alone, so this
# answers whether or not the GitHub tool is ready, and the name GitHub reports is
# compared too. It does not stop founding, which carries on as it does with no
# repository.
KIT_REPOSITORY=gwpicard/ai-build-kit
# GitHub reads owner and name in any case. The pattern spells both cases out
# with the shell alone, so the report needs nothing beyond the tools it checks.
KIT_PATTERN='[Gg][Ww][Pp][Ii][Cc][Aa][Rr][Dd]/[Aa][Ii]-[Bb][Uu][Ii][Ll][Dd]-[Kk][Ii][Tt]'
is_kit_repository() {
  case $1 in
    $KIT_PATTERN | *[Gg][Ii][Tt][Hh][Uu][Bb].[Cc][Oo][Mm][:/]$KIT_PATTERN | \
    *[Gg][Ii][Tt][Hh][Uu][Bb].[Cc][Oo][Mm][:/]$KIT_PATTERN.git | \
    *[Gg][Ii][Tt][Hh][Uu][Bb].[Cc][Oo][Mm][:/]$KIT_PATTERN/) return 0 ;;
  esac
  return 1
}
kit_origin=no
origin_url=$(git remote get-url origin 2>/dev/null || true)
if [ -n "$origin_url" ] && is_kit_repository "$origin_url"; then
  kit_origin=yes
fi

# 3. What the signed-in account can do on this repository, once one is set up.
# These need a repository and python3, so they run only when both are here. On a
# fresh project with no repository yet, they wait until one exists.
if [ "$gh_ready" = yes ] && command -v python3 >/dev/null 2>&1 && [ "$kit_origin" = no ]; then
  repo_json=$(gh repo view --json nameWithOwner,hasIssuesEnabled,viewerPermission 2>/dev/null || true)
  read_field() {
    printf '%s' "$repo_json" \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null \
      || true
  }
  if [ -n "$repo_json" ] && is_kit_repository "$(read_field nameWithOwner)"; then
    kit_origin=yes
  elif [ -n "$repo_json" ]; then
    issues_on=$(read_field hasIssuesEnabled)
    perm=$(read_field viewerPermission)

    if [ "$issues_on" = "True" ]; then
      echo "Issues are switched on for this repository."
    else
      echo "Issues are switched off for this repository: say so and offer to switch them on, and do not switch them on yourself."
    fi

    case "$perm" in
      ADMIN | MAINTAIN | WRITE)
        echo "Labels can be put in order: the signed-in account can create and delete labels here." ;;
      *)
        echo "Labels cannot be put in order: the signed-in account cannot create or delete labels here. Say which labels could not be made; a missing label costs a little clarity, it stops nothing." ;;
    esac
  else
    echo "No GitHub repository is set up yet, so the issue and label checks wait until one exists."
  fi
fi

if [ "$kit_origin" = yes ]; then
  echo "This project still points at the kit's own repository, $KIT_REPOSITORY: no piece is opened there and nothing is pushed there. Ask for the person's own repository, or carry on with none."
fi

# 4. The tools a recipe's checks run, only when a recipe is named. A recipe
# lists them on its "Command-line tools:" line. They are needed before the
# first launch, not before founding, so a missing one never sets blocked: a
# project that uses no recipe needs none of them.
if [ -n "$recipe" ]; then
  if [ -f "$recipe" ]; then
    # Read with the shell alone, so the report needs nothing beyond the tools
    # it is checking for.
    recipe_tools=""
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in
        "Command-line tools: "*) recipe_tools=${line#Command-line tools: } ;;
      esac
    done < "$recipe"
    saved_ifs=$IFS
    IFS=', '
    set -f
    set -- $recipe_tools
    set +f
    IFS=$saved_ifs
    for tool in "$@"; do
      case "$tool" in
        none) continue ;;
        *[!a-z0-9-]*) echo "The recipe names a tool this report cannot read, $tool, so it was skipped."; continue ;;
      esac
      if command -v "$tool" >/dev/null 2>&1; then
        echo "$tool is ready: the recipe's launch checks run it."
      else
        echo "$tool is missing: the recipe's launch checks run it, so install it before the first /ship. It does not stop founding."
      fi
    done
  else
    echo "The recipe file $recipe was not found, so the tools its checks run were not looked for."
  fi
fi

# 5. What the walk-through can look with. Before a piece is saved the agent
# walks through it and looks at what the person would see: a web page through a
# browser, and a PDF, a document or a drawing turned into pictures it reads.
# These tools make that possible. A missing one never sets blocked, since the
# walk-through then names what it could not see and the piece waits for the
# person. For each missing one the report prints the install command for this
# platform. The kit never runs it: installing is the person's choice.
if [ -f /System/Library/CoreServices/SystemVersion.plist ]; then
  platform=mac
elif [ -f /etc/debian_version ]; then
  platform=debian
else
  platform=other
fi
install_line() {
  # install_line <Homebrew formula> <apt package>
  case "$platform" in
    mac) printf 'brew install %s' "$1" ;;
    debian) printf 'sudo apt install %s' "$2" ;;
    *) printf 'install %s with your system%ss package manager' "$2" "'" ;;
  esac
}
eyes_missing() {
  # eyes_missing <tool> <what it is for> <install command>
  echo "$1 is missing: $2. To add it, run: $3. It does not stop founding."
}

if command -v pdftoppm >/dev/null 2>&1; then
  echo "pdftoppm is ready: the walk-through turns each page of a PDF into a picture with it."
else
  eyes_missing pdftoppm "without it the walk-through cannot look at a PDF" "$(install_line poppler poppler-utils)"
fi
if command -v soffice >/dev/null 2>&1 || command -v libreoffice >/dev/null 2>&1; then
  echo "soffice is ready: the walk-through turns a Word, PowerPoint, Excel or OpenDocument file into a PDF with it."
else
  eyes_missing soffice "without it the walk-through cannot look at a Word, PowerPoint, Excel or OpenDocument file" "$(install_line '--cask libreoffice' libreoffice)"
fi
# An older ImageMagick, which some Linux releases still ship, names the same
# command convert.
if command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1; then
  echo "magick is ready: the walk-through turns an SVG drawing into a picture with it."
else
  eyes_missing magick "without it the walk-through cannot look at an SVG drawing" "$(install_line imagemagick imagemagick)"
fi
# --no-install asks only what is already here, so the report downloads nothing.
if command -v npx >/dev/null 2>&1 && npx --no-install playwright --version >/dev/null 2>&1; then
  echo "Playwright is ready: the walk-through takes a screenshot of a web page with it where the coding agent has no browser tool of its own."
else
  eyes_missing Playwright "without it, and without a browser tool in the coding agent, the walk-through cannot take a screenshot of a web page" "npm install --save-dev playwright && npx playwright install --with-deps chromium"
fi

if [ "$blocked" -ne 0 ]; then
  echo "A tool the kit needs to found your pieces is not ready. Set it up before going on." >&2
  exit 1
fi

echo "Every tool the kit needs to found your pieces is ready."
exit 0
