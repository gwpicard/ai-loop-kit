#!/usr/bin/env sh
# worktree.sh: open, check and clear away the worktree each piece in a run is
# built in.
#
# A worktree is a second working copy of the project, on its own branch, in a
# folder of its own. Each piece in a run on Claude Code gets one at
# .agents/worktrees/<issue number>-<short name>, so the main folder never
# moves off its branch. This script is the only thing that opens or removes
# one, so the rules hold whichever session runs it:
#
#   open [--resume] <name> <branch> <base>
#       Make .agents/worktrees/<name> on <branch>, cut from <base> when the
#       branch does not exist yet. Write a .env of throwaway values into it,
#       under the kit's marker line, from the project's .env.example. The real
#       env files never reach a worktree, by link or by copy. Link each path on
#       the worktree-links line of .agents/loop/worktree-links.txt, refusing the
#       ones below. Reuse a worktree already at that path only when it is on
#       the same branch and holds no unsaved work; with --resume, only when it
#       holds no uncommitted change. A branch this call created is deleted
#       again if the worktree cannot be made. Exit 1 to skip the piece, 3 when
#       the disk is full, 4 when Git is older than 2.17.
#   unsaved <path>
#       Say whether a worktree holds unsaved work. Exit 1 when it does.
#   tidy
#       Remove each worktree whose pull request has merged or closed and that
#       holds no unsaved work. Keep and name one that holds some. A worktree
#       on no branch is never tidied; leftovers lists it.
#   leftovers
#       List each worktree with no open pull request that no unfinished run is
#       building, and each on no branch. Change nothing.
#   remove <path>
#       Remove one worktree, at the end of a run or on the person's yes. It
#       refuses unless the worktree is under .agents/worktrees/, no unfinished
#       run is building it, its pull requests could be read and none is open,
#       and nothing in it is unsaved.
#   port <issue number>
#       Print a port nothing listens on, on 127.0.0.1 or ::1.
#   candidates
#       List the files and folders at the main folder's top two levels that
#       git ignores and a build might need, for founding and /maintain to ask
#       about. Dependency and build folders, env files, .agents/, .claude/
#       and every confidential folder are left out.
#
# The throwaway .env starts with the marker line the guard hook knows, so the
# hook lets a builder read it and nothing else named .env. It is written only
# when git ignores .env, so it never shows as a new file to save. A .env already
# in the worktree is never overwritten: one that lacks the marker line, or is a
# link, is named and the piece is flagged. A throwaway .env counts as no unsaved
# work.
#
# The worktree-links line names ignored files a build needs that hold no
# secret, such as a licensed font: `worktree-links|<path> ; <path>`, each path
# relative to the project root. Each is linked, never copied. A path is
# refused, and the reason named, when it sits in or holds a folder on a
# `confidential|<folder>` line, is an env file, is tracked by git, lies outside
# the project, is not in the main folder, or is not ignored by git.
#
# The kit touches only the worktrees under the main folder's
# .agents/worktrees/. A worktree another tool made is never listed, changed or
# removed, wherever it sits, and a run started inside one works from the main
# folder all the same.
#
# Unsaved work is an uncommitted change, counting a new file git does not
# ignore; a file git ignores that is a real file rather than a link and sits
# outside a dependency or build folder; or a commit no remote branch holds. A
# worktree is removed with `git worktree remove`, never forced, and no branch
# that existed before is ever deleted. It needs Git 2.17, the first with
# `git worktree remove`.
#
# Run it from anywhere inside the project. It needs git, and python3 and the
# GitHub command line tool for the steps that read pull requests.

set -eu

say() { printf '%s\n' "$*"; }
die() { printf 'worktree.sh: %s\n' "$*" >&2; exit 2; }

# The main folder is the first worktree git lists. Every path below comes from
# that same listing, so a folder reached through a symbolic link still matches.
MAIN=$(git worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')
[ -n "$MAIN" ] || die "run this from inside a git project"
# The folder this was run from, which may be another tool's worktree.
STARTED=$(git rev-parse --show-toplevel 2>/dev/null || true)
cd "$MAIN"
WT_DIR="$MAIN/.agents/worktrees"
RECORD="$MAIN/.agents/loop/worktree-links.txt"
# The first line of a throwaway .env. kit/hooks/guard.py holds the same text as
# THROWAWAY_MARKER, and the rehearsal checks that the two match.
MARKER="# ai-loop-kit: throwaway values. Nothing in this file is a real secret."

# git_error <output>: the line git gave its reason on, rather than a hint.
git_error() {
  line=$(printf '%s\n' "$1" | grep -E '^(fatal|error):' | sed -n '1p')
  [ -n "$line" ] || line=$(printf '%s\n' "$1" | sed -n '1p')
  printf '%s' "$line"
}

# too_old: true when Git predates `git worktree remove`, which 2.17 added.
too_old() {
  version=$(git --version 2>/dev/null || true)
  version=${version#git version }
  major=${version%%.*}
  rest=${version#*.}
  minor=${rest%%[!0-9]*}
  case "$major$minor" in '' | *[!0-9]*) return 1 ;; esac
  [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 17 ]; }
}

# listed: each worktree under .agents/worktrees/, as "<path><tab><branch>".
listed() {
  git worktree list --porcelain | awk -v pre="$WT_DIR/" '
    function emit() { if (p != "" && index(p, pre) == 1) print p "\t" b }
    /^worktree / { emit(); p = substr($0, 10); b = ""; next }
    /^branch / { b = substr($0, 8); sub("^refs/heads/", "", b) }
    END { emit() }'
}

# relative <path>: the path from the main folder, as the run state records it.
relative() { printf '%s' "${1#"$MAIN"/}"; }

# find_listed <path>: the listed worktree at <path>, however it was written.
find_listed() {
  want=$(cd "$1" 2>/dev/null && pwd -P) || return 1
  listed | while IFS="$(printf '\t')" read -r lpath lbranch; do
    if [ "$(cd "$lpath" 2>/dev/null && pwd -P)" = "$want" ]; then
      printf '%s\t%s\n' "$lpath" "$lbranch"
      break
    fi
  done
}

# count: the number of lines on stdin, with no padding.
count() { awk 'END { print NR }'; }

# rebuilt <path>: true for a path in a dependency or build folder, which an
# install or a build makes again.
rebuilt() {
  case "/$1/" in
    */node_modules/* | */.next/* | */dist/* | */build/* | */out/* | \
    */.venv/* | */venv/* | */__pycache__/* | */target/* | \
    */coverage/* | */.turbo/* | */.cache/*) return 0 ;;
  esac
  return 1
}

# ignored_paths [dir]: each path git ignores, as git status names it, one per
# line. The -z form keeps a name with a space in it unquoted.
ignored_paths() {
  git -C "${1:-.}" status --porcelain -z --ignored 2>/dev/null | tr '\000' '\n' \
    | sed -n 's/^!! //p'
}

# ignored_work <worktree>: each file git ignores that can still be work: a
# note, a screenshot, a key typed into a copy. Links, such as the .env links
# and the worktree-links links, and dependency or build folders are left out.
# An ignored folder counts only for the real files in it, since the folder a
# listed link needed may hold nothing but that link.
ignored_work() {
  ignored_paths "$1" | while IFS= read -r f; do
    f=${f%/}
    [ -L "$1/$f" ] && continue
    throwaway "$1/$f" && continue
    rebuilt "$f" && continue
    if [ -d "$1/$f" ]; then
      (cd "$1" && find "./$f" -type f -print 2>/dev/null) | sed 's|^\./||' \
        | while IFS= read -r g; do
            rebuilt "$g" || printf '%s\n' "$g"
          done
    else
      printf '%s\n' "$f"
    fi
  done
}

# throwaway <file>: true for a file whose first line is the kit's marker line.
throwaway() {
  [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sed -n '1p' "$1")" = "$MARKER" ]
}

# clean_path <path>: the path without spaces around it, a leading ./ or a
# trailing /.
clean_path() {
  p=$(printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
  while :; do
    case $p in ./*) p=${p#./} ;; */) p=${p%/} ;; *) break ;; esac
  done
  printf '%s' "$p"
}

# confidential_folders: each folder on a confidential line, one per line.
confidential_folders() {
  [ -f "$RECORD" ] || return 0
  sed -n 's/^confidential|//p' "$RECORD" | while IFS= read -r c; do
    c=$(clean_path "$c")
    [ -z "$c" ] || printf '%s\n' "$c"
  done
}

# confidential_reason <path>: why a path touches a confidential folder, or
# nothing.
confidential_reason() {
  confidential_folders | while IFS= read -r c; do
    case $1 in
      "$c" | "$c"/*) printf 'it sits in the confidential folder %s' "$c"; break ;;
    esac
    case $c in
      "$1"/*) printf 'it holds the confidential folder %s' "$c"; break ;;
    esac
  done
}

# link_paths: each path on the last worktree-links line, one per line.
link_paths() {
  [ -f "$RECORD" ] || return 0
  line=$(grep '^worktree-links|' "$RECORD" | tail -n 1)
  [ -n "$line" ] || return 0
  printf '%s\n' "${line#worktree-links|}" \
    | awk '{ n = split($0, part, / ; /); for (i = 1; i <= n; i++) print part[i] }' \
    | while IFS= read -r p; do
        p=$(clean_path "$p")
        [ -z "$p" ] || printf '%s\n' "$p"
      done
}

# refusal <path>: why a listed path is not linked, or nothing.
refusal() {
  case $1 in
    /* | .. | ../* | */../* | */..)
      printf 'it lies outside the project'; return ;;
  esac
  case ${1##*/} in
    .env | .env.*)
      printf 'it is an env file, and the .env rule covers those'; return ;;
  esac
  why=$(confidential_reason "$1")
  if [ -n "$why" ]; then
    printf "%s, which never reaches a run's worktree" "$why"
    return
  fi
  # A folder is checked entry by entry, so only a tracked file itself is
  # refused here, and a folder keeping one tracked placeholder still links.
  if [ "$(git ls-files -- ":(literal)$1" 2>/dev/null | sed -n '1p')" = "$1" ]; then
    printf 'git tracks it, so the worktree already has it'; return
  fi
  if [ ! -e "$MAIN/$1" ] && [ ! -L "$MAIN/$1" ]; then
    printf 'it is not in the main folder. Flag the piece: built without %s' "$1"; return
  fi
  # A path that is itself a link, or sits under one, is judged by where it
  # leads.
  real=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$MAIN/$1" 2>/dev/null || true)
  top=$(pwd -P)
  if [ -n "$real" ]; then
    case $real in
      "$top" | "$top"/*) ;;
      *) printf 'it leads outside the project'; return ;;
    esac
    inner=${real#"$top"}
    inner=${inner#/}
    if [ -n "$inner" ] && [ "$inner" != "$1" ]; then
      why=$(confidential_reason "$inner")
      if [ -n "$why" ]; then
        printf "it leads to %s: %s, which never reaches a run's worktree" "$inner" "$why"
        return
      fi
    fi
  fi
  # A folder's own entries are each checked, since `fonts/*` beside a kept
  # `!fonts/.gitkeep` ignores the files and not the folder.
  if { [ ! -d "$MAIN/$1" ] || [ -L "$MAIN/$1" ]; } && ! git check-ignore -q -- "$1" 2>/dev/null; then
    printf 'git does not ignore it, so its link would show as a new file to save'
  fi
}

# link_one <worktree> <path>: link one path, adding it to $linked or saying
# why not. The link is relative, so it still leads to the main folder's file
# however the project folder is reached.
link_one() {
  if [ -L "$1/$2" ]; then
    linked="$linked${linked:+, }$2"
    return
  fi
  if [ -e "$1/$2" ]; then
    say "A copy of $2 already sits in this worktree: it was not linked, and it is a copy outside the main folder. Flag the piece."
    return
  fi
  slashes=$(printf '%s' "$2" | tr -cd /)
  up="../../../"
  i=0
  while [ "$i" -lt "${#slashes}" ]; do
    up="../$up"
    i=$((i + 1))
  done
  if mkdir -p "$1/$(dirname "$2")" 2>/dev/null && ln -s "$up$2" "$1/$2" 2>/dev/null && [ -L "$1/$2" ]; then
    # A link git does not ignore would be a new file for the piece to save.
    if git -C "$1" check-ignore -q -- "$2" 2>/dev/null; then
      linked="$linked${linked:+, }$2"
      return
    fi
    rm -f "$1/$2"
    say "Not linked $2: git in the worktree does not ignore the link, so it would show as a new file to save. Flag the piece: built without $2."
    return
  fi
  say "The link to $2 could not be made here. Flag the piece: built without $2. Never copy it instead."
}

# link_listed <worktree>: link each path on the worktree-links line. A folder
# is made as a real folder in the worktree and each thing in it linked, since
# git reads a link as a file and a rule that ignores a folder, such as
# `fonts/`, does not cover a link of that name.
link_listed() {
  linked=""
  paths=$(link_paths)
  [ -n "$paths" ] || return 0
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    why=$(refusal "$p")
    if [ -n "$why" ]; then
      say "Not linked $p: $why."
      continue
    fi
    if [ ! -d "$MAIN/$p" ] || [ -L "$MAIN/$p" ]; then
      link_one "$1" "$p"
      continue
    fi
    if [ -L "$1/$p" ]; then
      linked="$linked${linked:+, }$p"
      continue
    fi
    if [ -e "$1/$p" ] && [ ! -d "$1/$p" ]; then
      say "A copy of $p already sits in this worktree: it was not linked, and it is a copy outside the main folder. Flag the piece."
      continue
    fi
    for entry in "$MAIN/$p"/* "$MAIN/$p"/.[!.]* "$MAIN/$p"/..?*; do
      [ -e "$entry" ] || [ -L "$entry" ] || continue
      e="$p/${entry##*/}"
      why=$(refusal "$e")
      if [ -n "$why" ]; then
        say "Not linked $e: $why."
        continue
      fi
      link_one "$1" "$e"
    done
  done <<EOF
$paths
EOF
  if [ -n "$linked" ]; then
    say "Linked $linked to the main folder's own, as the worktree-links line lists, so each stays one file."
  fi
}

# unsaved_reason <worktree> [commit]: what is unsaved, or nothing. A commit
# given here is saved too: the head of a merged pull request, which counts
# even after its branch has gone from the remote.
unsaved_reason() {
  changes=$(git -C "$1" status --porcelain | count)
  kept=$(ignored_work "$1" | count)
  saved_too=""
  if [ -n "${2:-}" ] && git -C "$1" cat-file -e "$2^{commit}" 2>/dev/null; then
    saved_too=$2
  fi
  # shellcheck disable=SC2086
  commits=$(git -C "$1" rev-list HEAD --not --remotes $saved_too | count)
  reason=""
  [ "$changes" -eq 0 ] || reason="$changes uncommitted change(s)"
  if [ "$kept" -ne 0 ]; then
    [ -z "$reason" ] || reason="$reason and "
    reason="$reason$kept ignored file(s) that exist only in this worktree"
  fi
  if [ "$commits" -ne 0 ]; then
    [ -z "$reason" ] || reason="$reason and "
    reason="$reason$commits commit(s) missing from every remote branch"
  fi
  printf '%s' "$reason"
}

# pr_state <branch>: open, merged <head commit>, closed or none. Fails when the
# pull requests cannot be read.
pr_state() {
  command -v gh >/dev/null 2>&1 || return 1
  json=$(gh pr list --head "$1" --state all --json state,headRefOid 2>/dev/null </dev/null) || return 1
  printf '%s' "$json" | python3 -c '
import json, sys
pulls = json.load(sys.stdin)
states = [p.get("state", "") for p in pulls]
if "OPEN" in states:
    print("open")
elif "MERGED" in states:
    print("merged " + next(p.get("headRefOid", "") for p in pulls if p.get("state") == "MERGED"))
elif "CLOSED" in states:
    print("closed")
else:
    print("none")
' 2>/dev/null || return 1
}

# being_built <path> <branch>: true when an unfinished run lists a piece in
# this worktree, or on this branch, as waiting or building.
being_built() {
  [ -d "$MAIN/.agents/runs" ] || return 1
  python3 - "$MAIN" "$(relative "$1")" "$2" <<'PY' 2>/dev/null
import glob, json, os, sys
main, rel, branch = sys.argv[1:4]
for path in glob.glob(os.path.join(main, ".agents", "runs", "*", "*.json")):
    if os.path.basename(path) not in ("state.json", "run.json"):
        continue
    try:
        run = json.load(open(path))
    except Exception:
        continue
    for piece in run.get("pieces", []):
        if piece.get("state") not in ("waiting", "building"):
            continue
        if piece.get("worktree") == rel or (branch and piece.get("branch") == branch):
            sys.exit(0)
sys.exit(1)
PY
}

# throwaway_env <worktree>: give the worktree a .env of throwaway values. They
# come from the project's .env.example, the first of the usual example names,
# under the kit's marker line. The main folder's real env files are never read.
throwaway_env() {
  if [ -L "$1/.env" ] || { [ -e "$1/.env" ] && ! throwaway "$1/.env"; }; then
    say "A .env already sits in this worktree and does not start with the kit's marker line: it was left as it is, and it may hold real values. Flag the piece."
    return
  fi
  if [ -e "$1/.env" ]; then
    return
  fi
  example=""
  for name in .env.example .env.sample .env.template .env.dist; do
    if [ -f "$1/$name" ] && [ ! -L "$1/$name" ]; then
      example=$name
      break
    fi
  done
  if [ -z "$example" ]; then
    say "No .env.example in the project, so the worktree has no .env."
    return
  fi
  # A file git does not ignore would show as a new file to save.
  if ! git -C "$1" check-ignore -q .env 2>/dev/null; then
    say "Git does not ignore .env here, so no throwaway .env was written: it would show as a new file to save. Flag the piece."
    return
  fi
  if { printf '%s\n' "$MARKER"; cat "$1/$example"; } > "$1/.env" 2>/dev/null; then
    say "Wrote .env with throwaway values from $example, under the kit's marker line. The real env files stay in the main folder."
  else
    say "The throwaway .env could not be written here. Flag the piece: it runs without an .env."
  fi
}

# ignore_folder: make sure git ignores .agents/worktrees/ before anything is
# made in it, so nothing tracked changes.
ignore_folder() {
  git check-ignore -q ".agents/worktrees/$1" 2>/dev/null && return 0
  mkdir -p "$WT_DIR"
  printf '*\n' >> "$WT_DIR/.gitignore"
}

cmd_open() {
  resume=no
  if [ "${1:-}" = "--resume" ]; then
    resume=yes
    shift
  fi
  [ $# -eq 3 ] || die "usage: worktree.sh open [--resume] <name> <branch> <base>"
  name=$1 branch=$2 base=$3
  case $name in
    '' | */* | .*) die "the name must be <issue number>-<short name>, with no slash" ;;
  esac
  wt="$WT_DIR/$name"
  rel=".agents/worktrees/$name"
  ignore_folder "$name"
  started_at=""
  [ -z "$STARTED" ] || started_at=$(cd "$STARTED" 2>/dev/null && pwd -P || true)
  # The kit's own worktree folder may not exist yet.
  kit_worktrees="$(pwd -P)/.agents/worktrees"
  if [ -n "$started_at" ] && [ "$started_at" != "$(pwd -P)" ] && \
    case "$started_at/" in "$kit_worktrees"/*) false ;; *) true ;; esac; then
    say "This session is in $STARTED, another worktree. The run's state and its pieces' worktrees live in the main folder, $MAIN."
  fi

  if [ -e "$wt" ]; then
    found=$(find_listed "$wt" || true)
    if [ -z "$found" ]; then
      say "Skip this piece: $rel already exists and is not a worktree of this project."
      exit 1
    fi
    on=${found#*"$(printf '\t')"}
    if [ "$on" != "$branch" ]; then
      say "Skip this piece: $rel already exists on branch ${on:-none}, not $branch."
      exit 1
    fi
    reason=$(unsaved_reason "$wt")
    if [ "$resume" = yes ]; then
      changes=$(git -C "$wt" status --porcelain | count)
      if [ "$changes" -ne 0 ]; then
        say "Skip this piece: $rel holds $changes uncommitted change(s) from an earlier session. It is kept as it is."
        exit 1
      fi
    elif [ -n "$reason" ]; then
      say "Skip this piece: $rel already exists and holds unsaved work: $reason. It is kept as it is."
      exit 1
    fi
    say "Reused $rel: it is already on branch $branch."
    throwaway_env "$wt"
    link_listed "$wt"
    exit 0
  fi

  mkdir -p "$WT_DIR" 2>/dev/null || true
  added=yes
  created=""
  if ! git show-ref --verify -q "refs/heads/$branch"; then
    # --no-track: a branch cut from origin/main would otherwise track it, and a
    # plain pull would bring main in. The branch gets its own upstream when
    # it is pushed.
    err=$(git branch --no-track "$branch" "$base" 2>&1 >/dev/null) || added=no
    [ "$added" = no ] || created=$(git rev-parse "refs/heads/$branch")
  fi
  if [ "$added" = yes ]; then
    err=$(git worktree add "$wt" "$branch" 2>&1 >/dev/null) || added=no
  fi
  if [ "$added" = no ]; then
    # Delete only the branch this call made, and only while it still points
    # where it was made, so no existing branch or later work is ever lost.
    if [ -n "$created" ]; then
      git update-ref -d "refs/heads/$branch" "$created" >/dev/null 2>&1 || true
    fi
    case $err in
      *"No space left"* | *"no space left"* | *"Disk quota"*)
        say "The disk is full, so $rel could not be made. Stop the run before the next piece, and give this as the reason in the report."
        exit 3 ;;
      *"missing but"* | *"prune"*)
        say "Skip this piece: git still lists $rel though its folder is gone. Running git worktree prune clears that record, and /maintain offers it."
        exit 1 ;;
    esac
    say "Skip this piece: $rel could not be made: $(git_error "$err")"
    exit 1
  fi
  say "Opened $rel on branch $branch, from $base."
  throwaway_env "$wt"
  link_listed "$wt"
}

cmd_unsaved() {
  [ $# -eq 1 ] || die "usage: worktree.sh unsaved <path>"
  found=$(find_listed "$1" || true)
  [ -n "$found" ] || die "$1 is not a worktree under .agents/worktrees/"
  wt=${found%%"$(printf '\t')"*}
  reason=$(unsaved_reason "$wt")
  if [ -n "$reason" ]; then
    say "$(relative "$wt") holds unsaved work: $reason."
    exit 1
  fi
  say "$(relative "$wt") holds no unsaved work."
}

cmd_tidy() {
  listed | while IFS="$(printf '\t')" read -r wt branch; do
    rel=$(relative "$wt")
    if [ ! -d "$wt" ]; then
      say "$rel is gone from this computer, and git still lists it. Running git worktree prune clears that record."
      continue
    fi
    # A worktree on no branch has no pull request to ask about, so it is
    # never tidied. The leftover list names it.
    [ -n "$branch" ] || continue
    being_built "$wt" "$branch" && continue
    state=$(pr_state "$branch") || {
      say "Could not read the pull requests, so no worktree was removed."
      break
    }
    case $state in
      open* | none) continue ;;
    esac
    how=${state%% *}
    head=""
    [ "$how" != merged ] || head=${state#merged }
    reason=$(unsaved_reason "$wt" "$head")
    if [ -n "$reason" ]; then
      say "Kept $rel: its pull request $how, but it holds unsaved work: $reason."
      continue
    fi
    if err=$(git worktree remove "$wt" 2>&1); then
      say "Removed $rel: its pull request $how and nothing in it was unsaved. Its branch $branch is kept."
    else
      say "Kept $rel: git would not remove it: $(git_error "$err")"
    fi
  done
}

cmd_leftovers() {
  listed | while IFS="$(printf '\t')" read -r wt branch; do
    rel=$(relative "$wt")
    if [ ! -d "$wt" ]; then
      say "$rel is gone from this computer, and git still lists it. Running git worktree prune clears that record."
      continue
    fi
    being_built "$wt" "$branch" && continue
    if [ -z "$branch" ]; then
      reason=$(unsaved_reason "$wt")
      if [ -n "$reason" ]; then
        say "$rel: it is on no branch, and it holds unsaved work: $reason."
      else
        say "$rel: it is on no branch, and nothing in it is unsaved."
      fi
      continue
    fi
    state=$(pr_state "$branch") || {
      say "Could not read the pull requests, so no leftover worktree can be named."
      break
    }
    case $state in
      open*) continue ;;
      none) what="there is no pull request from its branch $branch" ; head="" ;;
      merged*) what="its pull request merged" ; head=${state#merged } ;;
      *) what="its pull request closed" ; head="" ;;
    esac
    reason=$(unsaved_reason "$wt" "$head")
    if [ -n "$reason" ]; then
      say "$rel: $what, and it holds unsaved work: $reason."
    else
      say "$rel: $what, and nothing in it is unsaved."
    fi
  done
}

cmd_remove() {
  [ $# -eq 1 ] || die "usage: worktree.sh remove <path>"
  found=$(find_listed "$1" || true)
  if [ -z "$found" ]; then
    say "Refused: $1 is not a worktree under .agents/worktrees/."
    exit 1
  fi
  wt=${found%%"$(printf '\t')"*}
  branch=${found#*"$(printf '\t')"}
  rel=$(relative "$wt")
  if being_built "$wt" "$branch"; then
    say "Kept $rel: an unfinished run is still building it."
    exit 1
  fi
  state=none
  if [ -n "$branch" ]; then
    state=$(pr_state "$branch") || {
      say "Kept $rel: the pull requests could not be read, so whether one is open is unknown."
      exit 1
    }
  fi
  case $state in
    open*)
      say "Kept $rel: its pull request is still open."
      exit 1 ;;
  esac
  head=""
  case $state in merged*) head=${state#merged } ;; esac
  reason=$(unsaved_reason "$wt" "$head")
  if [ -n "$reason" ]; then
    say "Kept $rel: it holds unsaved work: $reason."
    exit 1
  fi
  if err=$(git worktree remove "$wt" 2>&1); then
    if [ -n "$branch" ]; then
      say "Removed $rel. Its branch $branch is kept."
    else
      say "Removed $rel."
    fi
  else
    say "Kept $rel: git would not remove it: $(git_error "$err")"
    exit 1
  fi
}

cmd_candidates() {
  ignored_paths | while IFS= read -r f; do
    f=${f%/}
    case $f in */*/*) continue ;; esac
    rebuilt "$f" && continue
    case $f in .agents | .agents/* | .claude | .claude/*) continue ;; esac
    case ${f##*/} in .env | .env.* | .DS_Store | Thumbs.db) continue ;; esac
    [ -z "$(confidential_reason "$f")" ] || continue
    printf '%s\n' "$f"
  done
}

cmd_port() {
  [ $# -eq 1 ] || die "usage: worktree.sh port <issue number>"
  case $1 in '' | *[!0-9]*) die "the issue number must be a number" ;; esac
  python3 - "$1" <<'PY'
import errno, socket, sys

def answers(family, host, port):
    probe = socket.socket(family)
    probe.settimeout(0.2)
    try:
        return probe.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        probe.close()

def taken(family, host, port):
    try:
        listener = socket.socket(family)
    except OSError:
        return False
    try:
        listener.bind((host, port))
        return False
    except OSError as error:
        # No IPv6 on this computer means nothing can listen on ::1 either.
        return error.errno != errno.EADDRNOTAVAIL
    finally:
        listener.close()

start = 4000 + int(sys.argv[1]) % 1000
for port in list(range(start, 5000)) + list(range(4000, start)):
    if answers(socket.AF_INET, "127.0.0.1", port) or answers(socket.AF_INET6, "::1", port):
        continue
    if taken(socket.AF_INET, "127.0.0.1", port) or taken(socket.AF_INET6, "::1", port):
        continue
    print(port)
    sys.exit(0)
sys.exit("no free port between 4000 and 4999")
PY
}

sub=${1:-}
[ $# -eq 0 ] || shift
case $sub in
  open | tidy | remove)
    if too_old; then
      say "Git is version $version, older than 2.17, which has no git worktree remove. Build this run in one checkout, one piece after another."
      exit 4
    fi ;;
esac
case $sub in
  open) cmd_open "$@" ;;
  unsaved) cmd_unsaved "$@" ;;
  tidy) cmd_tidy ;;
  leftovers) cmd_leftovers ;;
  remove) cmd_remove "$@" ;;
  port) cmd_port "$@" ;;
  candidates) cmd_candidates ;;
  *) die "usage: worktree.sh open|unsaved|tidy|leftovers|remove|port|candidates ..." ;;
esac
