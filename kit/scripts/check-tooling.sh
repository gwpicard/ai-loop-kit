#!/usr/bin/env sh
# check-tooling.sh: say whether the tools the kit itself needs are ready, before
# setup leans on them.
#
# Three tools have to be here before the pieces can be founded: Git, python3 and
# openssl. The kit saves versions with Git, reads JSON with python3 and signs
# the GitHub App's token request with openssl. The report says which are ready
# and which are not, in plain words. It stops with a non-zero result when one of
# them is missing, so a gap is caught here and not at a later step. The GitHub
# command line tool is reported too. Before the App is set up a project shapes
# and runs locally, so a missing gh does not stop founding.
#
# It changes nothing. It never uses the person's own GitHub sign-in. With the
# gate's GitHub App set up, it reads the repository as the App, through
# loop/github.py. With no App it does not look at GitHub, and says so once.
#
# openssl makes and reads the key of the GitHub App the gate acts as.
#
# jq is not required. The kit filters JSON with python3 on purpose, which is
# also what lets the test harness stand in for the GitHub command line tool.
#
# Run from anywhere inside the project. With --for-run, which the pre-run check
# passes, a project whose origin is the kit's own repository stops with exit
# code 3 instead of carrying on, since a run would push there. With --recipe
# <recipe file>, it also
# reports the command-line tools that recipe's launch checks run. Those never
# stop founding. Nor do the tools the walk-through looks with, which it always
# reports, with the install command for each one missing.

set -eu

recipe=""
for_run=no
while [ $# -gt 0 ]; do
  case "$1" in
    --recipe)
      recipe=${2:-}
      [ -n "$recipe" ] || { echo "usage: check-tooling.sh [--for-run] [--recipe <recipe file>]" >&2; exit 2; }
      shift 2
      ;;
    --for-run)
      for_run=yes
      shift
      ;;
    -h | --help)
      sed -n '2,/^set -eu/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
      echo "exit codes: 0 ready, 1 a tool is missing, 2 usage, 3 refused (the kit's own repository, with --for-run)"
      exit 0
      ;;
    *)
      echo "usage: check-tooling.sh [--for-run] [--recipe <recipe file>]" >&2
      exit 2
      ;;
  esac
done

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

if command -v openssl >/dev/null 2>&1; then
  echo "openssl is ready: the kit makes and reads the GitHub App key with it."
else
  echo "openssl is missing: install it so the kit can make and read the GitHub App key. See manual-setup.md."
  blocked=1
fi

# The GitHub command line tool. The report checks only that it is installed. It
# never runs it with the person's own sign-in, so it never reads that sign-in.
# Before the GitHub App is set up a project shapes and runs locally, so a
# missing gh blocks nothing.
gh_here=no
if command -v gh >/dev/null 2>&1; then
  gh_here=yes
  echo "The GitHub command line tool is installed: the gate acts on GitHub with it, as its GitHub App. This report does not use your own sign-in. To see it, run gh auth status yourself."
else
  echo "The GitHub command line tool is missing: the gate needs it to act on GitHub once its App is set up. Install it from https://cli.github.com. It does not stop founding."
fi

# 2. Whether this project still points at the kit's own repository. A project
# founded from a whole copy of the kit can keep the kit's `origin`, and then the
# GitHub tool would open the project's pieces as issues there, and a later push
# would aim the person's code at it. `origin` is read with Git alone, so this
# answers whether or not the GitHub tool is ready. With the App, the name GitHub
# reports is compared too. It does not stop founding, which carries on as it
# does with no repository. With --for-run it stops the run, with exit code 3.
KIT_REPOSITORY=gwpicard/ai-loop-kit
# GitHub reads owner and name in any case. The pattern spells both cases out
# with the shell alone, so the report needs nothing beyond the tools it checks.
KIT_PATTERN='[Gg][Ww][Pp][Ii][Cc][Aa][Rr][Dd]/[Aa][Ii]-[Ll][Oo][Oo][Pp]-[Kk][Ii][Tt]'
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

# 3. The repository on GitHub, read as the gate's GitHub App through
# loop/github.py beside this report. With no App the door starts no program
# and exits 3, and the report prints one notice. --for-run reads nothing here:
# a run needs only the tools above. Nothing in this part sets blocked.
# The folder is found with the shell alone, since the report may run with
# nothing else on its PATH.
case "$0" in
  */*) scripts=${0%/*} ;;
  *) scripts=. ;;
esac
scripts=$(CDPATH= cd -- "$scripts" && pwd)
NO_APP="The GitHub App is not set up yet, so this report does not look at GitHub. The gate queues its GitHub writes for you to send with gate.py sync."
if [ "$for_run" = no ] && [ "$kit_origin" = no ]; then
  if ! command -v python3 >/dev/null 2>&1 || [ ! -f "$scripts/loop/github.py" ] \
    || ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "$NO_APP"
  else
    repo_code=0
    repo_json=$(PYTHONPATH="$scripts" python3 -m loop.github repo-view 2>/dev/null </dev/null) \
      || repo_code=$?
    read_field() {
      printf '%s' "$repo_json" \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null \
        || true
    }
    if [ "$repo_code" -eq 3 ]; then
      echo "$NO_APP"
    elif [ -z "$origin_url" ]; then
      echo "No GitHub repository is set up yet, so the issue and label checks wait until one exists."
    elif [ "$repo_code" -ne 0 ]; then
      if [ "$gh_here" = no ]; then
        echo "The GitHub App is set up, but the GitHub command line tool is missing, so the App cannot read the repository. Install gh, then run this report again."
      else
        echo "The gate's GitHub App could not read this repository: check the network and the App's access, then run this report again. It does not stop founding."
      fi
    elif is_kit_repository "$(read_field nameWithOwner)"; then
      kit_origin=yes
    else
      if [ "$(read_field hasIssuesEnabled)" = "True" ]; then
        echo "Issues are switched on for this repository."
      else
        echo "Issues are switched off for this repository: say so and offer to switch them on, and do not switch them on yourself."
      fi
      case "$(read_field viewerPermission)" in
        ADMIN | MAINTAIN | WRITE)
          echo "Labels can be put in order: the gate's App can create and delete labels here." ;;
        *)
          echo "Labels cannot be put in order: the gate's App cannot create or delete labels here. Say which labels could not be made; a missing label costs a little clarity, it stops nothing." ;;
      esac
    fi
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
# Read installed executables, never npm's registry or package cache. A separate process
# group bounds discovery as well as execution. Its leader stays unreaped until cleanup,
# so cleanup cannot signal a reused process-group identifier.
playwright_ready() {
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - <<'PY' >/dev/null 2>&1
import os
import select
import signal
import subprocess
import sys
import time

worker = r'''
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

signal.signal(signal.SIGTERM, signal.SIG_IGN)
passed = False
try:
    folder = Path.cwd()
    installed = None
    for parent in (folder, *folder.parents):
        candidate = parent / "node_modules" / ".bin" / "playwright"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            installed = str(candidate)
            break
    if installed is None:
        installed = shutil.which("playwright")
    if installed is not None:
        passed = subprocess.run([installed, "--version"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                check=False).returncode == 0
except OSError:
    pass
os.write(sys.stdout.fileno(), b"0\n" if passed else b"1\n")
while True:
    signal.pause()
'''

process = subprocess.Popen([sys.executable, "-c", worker], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           start_new_session=True)
passed = False
try:
    assert process.stdout is not None
    if select.select([process.stdout], [], [], 2)[0]:
        passed = os.read(process.stdout.fileno(), 3) == b"0\n"
finally:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        if sig == signal.SIGTERM:
            time.sleep(.1)
    try:
        process.wait(timeout=.2)
    except subprocess.TimeoutExpired:
        passed = False
    if process.stdout is not None:
        process.stdout.close()
sys.exit(0 if passed else 1)
PY
}
if playwright_ready; then
  echo "Playwright is ready: the walk-through takes a screenshot of a web page with it where the coding agent has no browser tool of its own."
else
  eyes_missing Playwright "without it, and without a browser tool in the coding agent, the walk-through cannot take a screenshot of a web page" "npm install --save-dev playwright && npx playwright install --with-deps chromium"
fi

if [ "$blocked" -ne 0 ]; then
  echo "A tool the kit needs to found your pieces is not ready. Set it up before going on." >&2
  echo "next: install the missing tool, then run check-tooling.sh again" >&2
  exit 1
fi

if [ "$for_run" = yes ] && [ "$kit_origin" = yes ]; then
  echo "A run would push to the kit's own repository, $KIT_REPOSITORY, so it will not start." >&2
  echo "next: git remote set-url origin <your own repository>, then run check-tooling.sh --for-run again" >&2
  exit 3
fi

echo "Every tool the kit needs to found your pieces is ready."
exit 0
