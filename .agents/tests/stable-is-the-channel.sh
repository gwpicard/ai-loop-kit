#!/usr/bin/env sh
# stable-is-the-channel.sh: guard the branch the world installs from, and the
# one visit that tells a project which version it actually holds.
#
# The fault this closes was silent in the worst way. Two of the three
# installation routes clone the repository with no ref, which takes the default
# branch, and that branch was `main`. So a project installing between two
# releases received the last release's version label with unreleased work
# behind it, and /maintain read the same label and said the project was up to
# date. Nothing errored. A user reported it after receiving v0.15.0 together
# with changes merged after v0.15.0 went out.
#
# Two halves fix it, and this checks both.
#
# The channel. A release moves `stable`, and only after `verify release` has
# rebuilt the published tag and found it matching the reviewed archive. The
# write itself lives in .agents/tools/promote-stable.sh and is driven here
# against a stand-in for the GitHub CLI, so the create, the update, the
# refusals and the read-back are all exercised without an account. What cannot
# be rehearsed anywhere local is the real write from inside GitHub Actions; the
# first published release is the first time that runs.
#
# The permission shape of that workflow, the read-only top level and the single
# writing job, is guarded next door in release-publication.sh, where the rest
# of the "nothing here may rewrite a repository" family lives.
#
# The visit. /maintain asks `/repos/gwpicard/ai-build-kit/releases/latest` and
# no other endpoint, because that is the only one that cannot answer with a
# draft or a prerelease, and says both numbers out loud. The rules that keep
# that honest are prose a coding agent reads, so they are read back here and
# each one is proved load-bearing by removing it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

PROMOTE="$ROOT/.agents/tools/promote-stable.sh"
VERIFY="$ROOT/.github/workflows/verify-release.yml"
BRANCHCHECK="$ROOT/.github/workflows/maintainer-branch-check.yml"
MAINTAIN="$ROOT/.agents/skills/maintain/SKILL.md"
WHATNOW="$ROOT/.agents/skills/what-now/SKILL.md"
MAINTAINING="$ROOT/docs/MAINTAINING.md"
STAMP="$ROOT/.agents/tools/stamp-version.sh"
CONTRIBUTING="$ROOT/CONTRIBUTING.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Stable-is-the-channel checks"

# --- the tool that moves the branch ---------------------------------------
#
# Skipped when the rule set is only being listed, because the mutation audit
# asks every one of this family which rules it guards and a temporary
# repository per question would cost it minutes for nothing.

if [ -z "${RS_LIST:-}" ]; then
  [ -x "$PROMOTE" ] || rs_fail "$PROMOTE is not executable"

  WORK=$(mktemp -d)
  trap 'rm -rf "$rs_dir" "$WORK"' EXIT
  mkdir -p "$WORK/bin" "$WORK/refs"

  # A stand-in for the GitHub CLI. It answers the four calls the tool makes and
  # refuses anything else by name, so a call the tool grows later shows up here
  # as a failure rather than passing unnoticed.
  #
  # STUB_TAG_VERSION and STUB_TAG_SHA are the published tag it knows about.
  # STUB_NOOP makes the write succeed and change nothing, which is the fault a
  # read-back exists to catch.
  cat > "$WORK/bin/gh" <<'STUB'
#!/usr/bin/env sh
printf 'gh %s\n' "$*" >> "$STUB_LOG"
[ "${1:-}" = api ] || { echo "stub gh: only api is stubbed" >&2; exit 1; }
shift
METHOD=GET
ENDPOINT=""
JQ=""
FIELDS=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --method) METHOD=$2; shift 2 ;;
    --jq) JQ=$2; shift 2 ;;
    -f|-F) FIELDS="$FIELDS $2"; shift 2 ;;
    *) ENDPOINT=$1; shift ;;
  esac
done
field() {
  for pair in $FIELDS; do
    case "$pair" in "$1"=*) printf '%s\n' "${pair#"$1"=}"; return 0 ;; esac
  done
}
case "$METHOD:$ENDPOINT" in
  GET:*/commits/*)
    asked=${ENDPOINT##*/commits/}
    [ "$asked" = "$STUB_TAG_VERSION" ] || { echo "stub gh: 404 no commit" >&2; exit 1; }
    printf '%s\n' "$STUB_TAG_SHA"
    ;;
  GET:*/git/ref/heads/*)
    branch=${ENDPOINT##*/git/ref/heads/}
    [ -s "$STUB_REFS/$branch" ] || { echo "stub gh: 404 no ref" >&2; exit 1; }
    if [ "$JQ" = ".object.sha" ]; then cat "$STUB_REFS/$branch"; fi
    ;;
  POST:*/git/refs)
    ref=$(field ref)
    case "$ref" in
      refs/heads/?*) ;;
      *) echo "stub gh: 422 bad ref '$ref'" >&2; exit 1 ;;
    esac
    branch=${ref#refs/heads/}
    if [ -s "$STUB_REFS/$branch" ]; then
      echo "stub gh: 422 already exists" >&2
      exit 1
    fi
    [ -n "${STUB_NOOP:-}" ] || field sha > "$STUB_REFS/$branch"
    ;;
  PATCH:*/git/refs/heads/*)
    branch=${ENDPOINT##*/git/refs/heads/}
    [ -s "$STUB_REFS/$branch" ] || { echo "stub gh: 404 no ref" >&2; exit 1; }
    [ -n "${STUB_NOOP:-}" ] || field sha > "$STUB_REFS/$branch"
    ;;
  *)
    echo "stub gh: unexpected call $METHOD $ENDPOINT" >&2
    exit 1
    ;;
esac
STUB
  chmod +x "$WORK/bin/gh"

  OLD=1111111111111111111111111111111111111111
  NEW=2222222222222222222222222222222222222222

  # run <description> <expect-pass|expect-fail> <version> <commit>
  # The environment is rebuilt for each one, so no case can be set up by the
  # one before it.
  attempt=0
  run() {
    attempt=$((attempt + 1))
    want=$2
    STUB_LOG="$WORK/log.$attempt"
    : > "$STUB_LOG"
    if PATH="$WORK/bin:$PATH" \
       GITHUB_REPOSITORY=gwpicard/ai-build-kit \
       STUB_LOG="$STUB_LOG" STUB_REFS="$WORK/refs" \
       STUB_TAG_VERSION="${TAG_VERSION:-v0.16.0}" STUB_TAG_SHA="${TAG_SHA:-$NEW}" \
       "$PROMOTE" "$3" "$4" > "$WORK/out.$attempt" 2>&1; then
      got=pass
    else
      got=pass_not
    fi
    if [ "$want" = expect-pass ]; then
      rs_report "$1" "$([ "$got" = pass ] && echo yes || echo no)"
    else
      rs_report "$1" "$([ "$got" = pass_not ] && echo yes || echo no)"
    fi
    LOG="$STUB_LOG"
    OUT="$WORK/out.$attempt"
  }

  echo "  -- it creates the branch, then moves it --"

  # `stable` does not exist yet. The release that carries this is the one that
  # brings it into being, so the first call has to create rather than update.
  run "a missing stable is created at the release commit" expect-pass v0.16.0 "$NEW"
  rs_report "the created ref is refs/heads/stable" \
    "$(grep -qF 'ref=refs/heads/stable' "$LOG" && echo yes || echo no)"
  rs_report "and it holds the release commit" \
    "$([ "$(cat "$WORK/refs/stable")" = "$NEW" ] && echo yes || echo no)"
  rs_report "the run says it is creating the branch" \
    "$(grep -qi 'creating stable' "$OUT" && echo yes || echo no)"

  # Now it exists, so the next release updates it. A create aimed at an
  # existing ref is refused by GitHub, so a tool that only ever created would
  # work once and then fail every release after it.
  printf '%s\n' "$OLD" > "$WORK/refs/stable"
  run "an existing stable is moved to the new release" expect-pass v0.16.0 "$NEW"
  rs_report "the move is a forced update rather than a create" \
    "$(grep -qF 'force=true' "$LOG" && echo yes || echo no)"
  rs_report "stable now holds the new commit" \
    "$([ "$(cat "$WORK/refs/stable")" = "$NEW" ] && echo yes || echo no)"

  echo "  -- it writes one ref and no other --"

  # The branch name is written into the tool. Nothing a caller passes can
  # redirect the write, which is the property that makes a repository write
  # from a workflow acceptable at all.
  rs_report "no call named any branch but stable" \
    "$(grep -E 'heads/[a-z]+' "$WORK"/log.* | grep -qv 'heads/stable' && echo no || echo yes)"
  rs_report "main was never written to" \
    "$([ -e "$WORK/refs/main" ] && echo no || echo yes)"

  echo "  -- what it refuses --"

  # The tag decides the commit. A commit no published tag names cannot be
  # promoted, so the tool cannot be talked into pointing stable at an
  # arbitrary tree even by somebody who can start the job.
  printf '%s\n' "$OLD" > "$WORK/refs/stable"
  run "a commit the published tag does not name is refused" expect-fail v0.16.0 \
    3333333333333333333333333333333333333333
  rs_report "and stable was left where it was" \
    "$([ "$(cat "$WORK/refs/stable")" = "$OLD" ] && echo yes || echo no)"

  run "a version with no published tag is refused" expect-fail v9.9.9 "$NEW"
  rs_report "and stable was left where it was" \
    "$([ "$(cat "$WORK/refs/stable")" = "$OLD" ] && echo yes || echo no)"

  # A preview must never become the branch every installer reads, the same rule
  # the stamp enforces.
  run "a preview version is refused" expect-fail v0.16.0-rc1 "$NEW"
  run "a short object name is refused" expect-fail v0.16.0 2222222
  run "a branch name in place of a commit is refused" expect-fail v0.16.0 main

  echo "  -- the read-back --"

  # The fault worth the extra call: an API write that answers cheerfully and
  # changes nothing leaves stable a release behind while the run goes green.
  printf '%s\n' "$OLD" > "$WORK/refs/stable"
  attempt=$((attempt + 1))
  if PATH="$WORK/bin:$PATH" GITHUB_REPOSITORY=gwpicard/ai-build-kit \
     STUB_LOG="$WORK/log.$attempt" STUB_REFS="$WORK/refs" STUB_NOOP=1 \
     STUB_TAG_VERSION=v0.16.0 STUB_TAG_SHA="$NEW" \
     "$PROMOTE" v0.16.0 "$NEW" >/dev/null 2>&1; then
    rs_report "a write that changed nothing is reported as a failure" no
  else
    rs_report "a write that changed nothing is reported as a failure" yes
  fi

  # Without a repository there is nothing to write to, and guessing one is how
  # a tool ends up writing to somebody else's fork.
  attempt=$((attempt + 1))
  if PATH="$WORK/bin:$PATH" STUB_LOG="$WORK/log.$attempt" STUB_REFS="$WORK/refs" \
     STUB_TAG_VERSION=v0.16.0 STUB_TAG_SHA="$NEW" \
     env -u GITHUB_REPOSITORY "$PROMOTE" v0.16.0 "$NEW" >/dev/null 2>&1; then
    rs_report "an unnamed repository is refused rather than guessed" no
  else
    rs_report "an unnamed repository is refused rather than guessed" yes
  fi
fi

# --- the reasons the tool carries -----------------------------------------

rs_rule "the ref is written out rather than taken from an argument" \
  'the ref is written out here'
rs_rule "so nothing a caller passes can redirect the write" \
  'passes can redirect the write to .main. or anywhere else'
rs_rule "a commit no published tag names is refused" \
  'a commit that no published tag names is refused'
rs_rule "the write goes through the api with the run's own token" \
  'it writes through the github api with the run.s own token'
rs_rule "nothing mints a credential to do it" \
  'nothing here mints a credential'
rs_rule "the ref is read back afterwards" \
  'it reads the ref back afterwards'
rs_rule "because a call can answer cheerfully and change nothing" \
  'an api call that answers cheerfully and'
rs_rule "create or update, because stable does not exist until the first release" \
  'does not exist until the first release'
rs_guard "$PROMOTE" "the tool that moves stable"

# --- the visit that names both versions -----------------------------------

rs_reset
rs_rule "the latest published release is asked for by that endpoint" \
  'releases/latest --jq \.tag_name'
rs_rule "and no other endpoint is used" \
  'ask that endpoint and no other'
rs_rule "because it is the only one that cannot answer with a draft" \
  'cannot answer with a draft or a prerelease'
rs_rule "while the release list puts an unpublished draft first" \
  'puts an unpublished draft in its first row'
rs_rule "both numbers are said every visit, whichever way they compare" \
  'say both numbers, every visit, whichever way they compare'
rs_rule "a difference is said plainly rather than left to the person" \
  'where they differ, say so plainly'
rs_rule "a match is said too" \
  'the project is on the latest published release'
rs_rule "a failed call is never reported as up to date" \
  'never say the project is up to date on the strength of a call that failed'
rs_rule "the confirmation after an update reads the same answer back" \
  'now matches the version step 1 read from .releases/latest.'
rs_guard "$MAINTAIN" "the maintain skill"

# /what-now names a newer release too, and asks the same endpoint for the same
# reason: a draft or a prerelease is never named as published.
rs_reset
rs_rule "/what-now asks the latest published release by that endpoint" \
  'releases/latest --jq \.tag_name'
rs_rule "and no other endpoint, the one /maintain asks" \
  'ask that endpoint and no other, the one ./maintain. asks'
rs_rule "because it never answers with a draft or a prerelease" \
  'never answers with a draft or a prerelease'
rs_guard "$WHATNOW" "the /what-now skill"

# --- the wiring that makes it happen --------------------------------------

rs_require "the release workflow has a job that moves stable" \
  "$VERIFY" 'promote-stable:'
rs_require "it runs only after verification has passed" \
  "$VERIFY" 'needs: verify'
rs_require "it calls the bounded tool rather than writing inline" \
  "$VERIFY" 'run: \.agents/tools/promote-stable\.sh'
rs_require "it promotes the commit verification checked" \
  "$VERIFY" 'commit: \$\{\{ steps\.release-ref\.outputs\.commit \}\}'
rs_require "the branch check leaves stable alone" \
  "$BRANCHCHECK" 'branches-ignore: - main - stable'

# --- the documents no longer call the gap unavoidable ---------------------

rs_require "MAINTAINING.md says only a release moves stable" \
  "$MAINTAINING" 'only a release moves it'
rs_require "and that a failed verification leaves it where it was" \
  "$MAINTAINING" 'fails verification leaves .stable. where it was'
rs_require "and says why stable cannot require a pull request" \
  "$MAINTAINING" 'rejects a ref update whoever makes it'
rs_require "and names the gap that leaves, rather than implying none" \
  "$MAINTAINING" 'fast-forward push to .stable. by somebody with write access is not refused'
rs_require "and warns that a default-branch pointer takes its rules with it" \
  "$MAINTAINING" 'follows the default branch when it moves'
rs_require "and says to ask each branch rather than read the ruleset list" \
  "$MAINTAINING" 'ask each branch what applies to it'
rs_require "and keeps the check for a stable that has to be rebuilt" \
  "$MAINTAINING" 'confirm it against the published tag'
rs_require_absent "MAINTAINING.md no longer calls the gap unclosable" \
  "$MAINTAINING" 'gap cannot be closed'
rs_require "the stamp says the stamped number is what an installation gets" \
  "$STAMP" 'the number of the tree an installation actually gets'
rs_require_absent "and no longer calls the drift unavoidable" \
  "$STAMP" 'that is unavoidable once the branch is where the work happens'
rs_require "CONTRIBUTING.md tells a contributor to target main" \
  "$CONTRIBUTING" 'target .main.'
rs_require "and says what to do with a pull request based on anything else" \
  "$CONTRIBUTING" 'change it before asking for a review'
rs_require "WORKFLOW.md explains the two numbers in plain words" \
  "$WORKFLOW" 'names two numbers, the version your project holds'
rs_require "and that an update gives a published release" \
  "$WORKFLOW" 'never work nobody has released yet'

rs_done
