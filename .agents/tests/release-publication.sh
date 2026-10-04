#!/usr/bin/env sh
# release-publication.sh: rehearse preparing a release, and prove that nothing
# in this repository can rewrite a repository's tree.
#
# There is one repository now. A release is prepared and published where the
# work happens, so nothing is copied anywhere and no credential reaches outside
# the run. What used to be rehearsed here was a publisher that made an assembled
# starter the exact tree of a second repository's main branch. Pointed at this
# repository that code would destroy the source, so it is gone rather than
# gated, and the assertions that guarded it now guard its absence.
#
# Nothing here contacts an online service.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"
DRAFT_FINISHER="$ROOT/.agents/tools/finish-release-draft.sh"
PREPARE_WORKFLOW="$ROOT/.github/workflows/prepare-release.yml"
VERIFY_WORKFLOW="$ROOT/.github/workflows/verify-release.yml"
DRAFT_WORKFLOW="$ROOT/.github/workflows/release-drafter.yml"
DRAFT_CONFIG="$ROOT/.github/release-drafter.yml"
GATE="github.repository == 'gwpicard/ai-build-kit'"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -x "$BUILDER" ] || fail "release builder is missing or not executable"
[ -x "$DRAFT_FINISHER" ] || fail "draft Release finisher is missing or not executable"
[ -f "$PREPARE_WORKFLOW" ] || fail "prepare-release workflow is missing"
[ -f "$VERIFY_WORKFLOW" ] || fail "release verification workflow is missing"
[ ! -e "$ROOT/.github/release.yml" ] || \
  fail "native generated-note configuration can expose private pull request numbers"
[ -f "$DRAFT_WORKFLOW" ] || fail "merge-driven release draft workflow is missing"
[ -f "$DRAFT_CONFIG" ] || fail "merge-driven release draft configuration is missing"

SCRATCH=$(mktemp -d)
FAKE_DRAFT_GH="$SCRATCH/fake-draft-gh"
FAKE_DRAFT_RELEASE="$SCRATCH/fake-draft-release"
cleanup() {
  rm -R "$SCRATCH"
}
trap cleanup EXIT

cat > "$FAKE_DRAFT_GH" <<'FAKEDRAFTGH'
#!/usr/bin/env sh
set -eu

state=${FAKE_DRAFT_STATE:?}
command=$1
action=$2
shift 2

[ "$command" = "release" ] || exit 2

case "$action" in
  list)
    for release in "$state"/v*; do
      [ -d "$release" ] || continue
      [ "$(cat "$release/draft")" = "true" ] || continue
      basename "$release"
    done
    ;;
  view)
    version=$1
    shift
    [ -d "$state/$version" ] || exit 1
    json=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --json) json=$2; shift 2 ;;
        --jq) shift 2 ;;
        *) exit 2 ;;
      esac
    done
    case "$json" in
      "") ;;
      isDraft) cat "$state/$version/draft" ;;
      assets)
        for asset in "$state/$version/assets"/*; do
          [ -f "$asset" ] || continue
          basename "$asset"
        done
        ;;
      *) exit 2 ;;
    esac
    ;;
  create)
    version=$1
    labelled_archive=$2
    shift 2
    archive=${labelled_archive%%#*}
    [ ! -e "$state/$version" ] || exit 1
    draft=false
    generated=false
    target=""
    title=""
    notes=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --draft) draft=true; shift ;;
        --generate-notes) generated=true; shift ;;
        --target) target=$2; shift 2 ;;
        --title) title=$2; shift 2 ;;
        --notes) notes=$2; shift 2 ;;
        *) exit 2 ;;
      esac
    done
    [ "$draft" = "true" ] || exit 2
    [ "$generated" = "true" ] || exit 2
    [ -n "$target" ] || exit 2
    [ -n "$title" ] || exit 2
    [ -n "$notes" ] || exit 2
    mkdir -p "$state/$version/assets"
    printf '%s\n' "true" > "$state/$version/draft"
    printf '%s\n' "$target" > "$state/$version/target"
    printf '%s\n' "$title" > "$state/$version/title"
    printf '%s\n' "$notes" > "$state/$version/body"
    cp "$archive" "$state/$version/assets/$(basename "$archive")"
    ;;
  edit)
    version=$1
    shift
    [ -d "$state/$version" ] || exit 1
    target=""
    title=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --target) target=$2; shift 2 ;;
        --title) title=$2; shift 2 ;;
        *) exit 2 ;;
      esac
    done
    [ -n "$target" ] || exit 2
    [ -n "$title" ] || exit 2
    printf '%s\n' "$target" > "$state/$version/target"
    printf '%s\n' "$title" > "$state/$version/title"
    ;;
  upload)
    version=$1
    labelled_archive=$2
    shift 2
    archive=${labelled_archive%%#*}
    [ -d "$state/$version" ] || exit 1
    [ "${1:-}" = "--clobber" ] || exit 2
    mkdir -p "$state/$version/assets"
    cp "$archive" "$state/$version/assets/$(basename "$archive")"
    ;;
  delete-asset)
    version=$1
    asset=$2
    shift 2
    [ "${1:-}" = "--yes" ] || exit 2
    rm "$state/$version/assets/$asset"
    ;;
  *) exit 2 ;;
esac
FAKEDRAFTGH
chmod +x "$FAKE_DRAFT_GH"
mkdir -p "$FAKE_DRAFT_RELEASE"

DRAFT_V030="$SCRATCH/ai-build-kit-v0.3.0.tar.gz"
printf '%s\n' "checked v0.3.0 starter" > "$DRAFT_V030"
if FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.3.0 "$DRAFT_V030" reviewed-commit-1 >/dev/null 2>&1; then
  fail "preparation created a draft without reviewed Release Drafter notes"
fi
mkdir -p "$FAKE_DRAFT_RELEASE/v0.3.0/assets"
printf '%s\n' "true" > "$FAKE_DRAFT_RELEASE/v0.3.0/draft"
printf '%s\n' "Reviewed public notes" > "$FAKE_DRAFT_RELEASE/v0.3.0/body"
FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.3.0 "$DRAFT_V030" reviewed-commit-1 >/dev/null
[ "$(cat "$FAKE_DRAFT_RELEASE/v0.3.0/draft")" = "true" ] || \
  fail "preparation changed the existing draft Release state"
[ "$(cat "$FAKE_DRAFT_RELEASE/v0.3.0/target")" = "reviewed-commit-1" ] || \
  fail "first preparation did not target reviewed main"
cmp -s "$DRAFT_V030" \
  "$FAKE_DRAFT_RELEASE/v0.3.0/assets/ai-build-kit-v0.3.0.tar.gz" || \
  fail "first preparation did not attach the checked starter"

# Release Drafter can raise the suggested version after another merge. Its
# existing assets keep their old names, so preparation must remove that stale
# starter after attaching the newly checked one.
mv "$FAKE_DRAFT_RELEASE/v0.3.0" "$FAKE_DRAFT_RELEASE/v0.4.0"
DRAFT_V040="$SCRATCH/ai-build-kit-v0.4.0.tar.gz"
printf '%s\n' "checked v0.4.0 starter" > "$DRAFT_V040"
FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.4.0 "$DRAFT_V040" reviewed-commit-2 >/dev/null
[ "$(cat "$FAKE_DRAFT_RELEASE/v0.4.0/target")" = "reviewed-commit-2" ] || \
  fail "later preparation did not update the draft target"
[ ! -e "$FAKE_DRAFT_RELEASE/v0.4.0/assets/ai-build-kit-v0.3.0.tar.gz" ] || \
  fail "later preparation left an old starter attached"
cmp -s "$DRAFT_V040" \
  "$FAKE_DRAFT_RELEASE/v0.4.0/assets/ai-build-kit-v0.4.0.tar.gz" || \
  fail "later preparation did not attach the new checked starter"

mkdir -p "$FAKE_DRAFT_RELEASE/v0.5.0/assets"
printf '%s\n' "true" > "$FAKE_DRAFT_RELEASE/v0.5.0/draft"
if FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.4.0 "$DRAFT_V040" reviewed-commit-2 >/dev/null 2>&1; then
  fail "preparation accepted two competing draft versions"
fi
rm -R "$FAKE_DRAFT_RELEASE/v0.5.0"

printf '%s\n' "false" > "$FAKE_DRAFT_RELEASE/v0.4.0/draft"
if FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.4.0 "$DRAFT_V040" reviewed-commit-2 >/dev/null 2>&1; then
  fail "preparation changed a published Release"
fi
printf '%s\n' "true" > "$FAKE_DRAFT_RELEASE/v0.4.0/draft"

FAKE_DRAFT_STATE="$FAKE_DRAFT_RELEASE" GH_COMMAND="$FAKE_DRAFT_GH" \
  "$DRAFT_FINISHER" v0.4.0 "$DRAFT_V040" reviewed-commit-2 >/dev/null
[ "$(find "$FAKE_DRAFT_RELEASE/v0.4.0/assets" -type f | wc -l | tr -d ' ')" -eq 1 ] || \
  fail "retry left duplicate starter archives on the draft"


grep -qF 'workflow_dispatch:' "$PREPARE_WORKFLOW" || \
  fail "release preparation is not manually started"
grep -qF '.agents/tools/finish-release-draft.sh' "$PREPARE_WORKFLOW" || \
  fail "release preparation does not use the rehearsed draft finisher"
grep -qF 'release list --limit 100 --json tagName,isDraft' "$DRAFT_FINISHER" || \
  fail "release preparation can create a competing draft version"
grep -qF 'release upload "$VERSION"' "$DRAFT_FINISHER" || \
  fail "release preparation does not attach the checked starter to an existing draft"
grep -qF 'release delete-asset "$VERSION"' "$DRAFT_FINISHER" || \
  fail "release preparation can leave an old starter archive attached"
grep -qF 'isDraft' "$DRAFT_FINISHER" || \
  fail "release preparation can replace a published release"
grep -qF 'git ls-remote --exit-code --tags origin' "$PREPARE_WORKFLOW" || \
  fail "release preparation does not reject an existing tag"
if grep -qF -- '--generate-notes' "$DRAFT_FINISHER"; then
  fail "release preparation can fall back to notes that expose private pull request numbers"
fi
grep -qF 'run the update release draft workflow' "$DRAFT_FINISHER" || \
  fail "missing draft notes do not give the maintainer a recovery action"
grep -qF 'types: [published]' "$VERIFY_WORKFLOW" || \
  fail "release verification does not run when a release is published"
grep -qF 'git merge-base --is-ancestor' "$VERIFY_WORKFLOW" || \
  fail "release verification does not require a tag from reviewed main"
grep -qF 'ref: ${{ steps.release-ref.outputs.commit }}' "$VERIFY_WORKFLOW" || \
  fail "released source is not checked out by its verified commit"
grep -qF 'gh release download' "$VERIFY_WORKFLOW" || \
  fail "release verification does not retrieve the reviewed starter"
grep -qF 'diff -qr' "$VERIFY_WORKFLOW" || \
  fail "release verification does not compare its rebuild with the reviewed starter"
if grep -q '^concurrency:' "$PREPARE_WORKFLOW" "$VERIFY_WORKFLOW"; then
  fail "release workflows use a queue that can silently cancel pending releases"
fi
grep -qF 'push:' "$DRAFT_WORKFLOW" || \
  fail "release draft is not refreshed after main changes"
grep -qF '      - main' "$DRAFT_WORKFLOW" || \
  fail "release draft workflow is not limited to main"
grep -qF 'release-drafter/release-drafter@34d80673e067bdc0c24568d3af899c216adcfaa9 # v7.7.0' "$DRAFT_WORKFLOW" || \
  fail "release draft workflow does not pin the reviewed Release Drafter version"
grep -qF 'contents: write' "$DRAFT_WORKFLOW" || \
  fail "release draft workflow cannot update a draft Release"
grep -qF 'pull-requests: read' "$DRAFT_WORKFLOW" || \
  fail "release draft workflow cannot read merged pull requests"
grep -qF "$GATE" "$DRAFT_WORKFLOW" || \
  fail "release draft workflow can run outside the repository the kit is kept in"
grep -qF "github.ref == 'refs/heads/main'" "$DRAFT_WORKFLOW" || \
  fail "release draft workflow can use an unreviewed branch"
grep -qF 'commitish: main' "$DRAFT_WORKFLOW" || \
  fail "Release Drafter does not explicitly read reviewed main-branch work"
grep -qF 'group: release-draft-main' "$DRAFT_WORKFLOW" || \
  fail "overlapping merges can update the draft at the same time"
grep -qF 'cancel-in-progress: true' "$DRAFT_WORKFLOW" || \
  fail "a superseded draft refresh can overwrite a newer one"
grep -qF 'tag-template: "v$RESOLVED_VERSION"' "$DRAFT_CONFIG" || \
  fail "release draft does not suggest a stable version"
grep -qF 'label: release-major' "$DRAFT_CONFIG" || \
  fail "release draft has no explicit major-version route"
grep -qF 'label: release-minor' "$DRAFT_CONFIG" || \
  fail "release draft has no explicit minor-version route"
grep -qF 'label: release-patch' "$DRAFT_CONFIG" || \
  fail "release draft has no explicit patch-version route"
grep -qF 'label: skip-release-notes' "$DRAFT_CONFIG" || \
  fail "release draft cannot omit internal-only pull requests"
grep -qF 'The notes below explain what changed.' "$DRAFT_CONFIG" || \
  fail "merge-driven release notes do not begin with a plain introduction"
grep -qF 'change-template: "- $TITLE"' "$DRAFT_CONFIG" || \
  fail "merge-driven release notes expose private pull request numbers"
if grep -qF '$NUMBER' "$DRAFT_CONFIG"; then
  fail "merge-driven release notes still include private pull request numbers"
fi

# --- nothing here may rewrite a repository -----------------------------
#
# The deleted publisher took an assembled starter and made it the exact tree of
# a repository's main branch. That was safe only while the repository it
# rewrote was a generated copy of this one. There is no second repository now,
# so the same code aimed here would replace the source with a packaged release.
# These four guards are the teeth the removed assertions used to carry, pointed
# at the hazard rather than at a repository that no longer exists.

# A push is looked for where it would be run, not where it is written about.
# Comments and quoted strings come out first, because the validator quotes
# `git push` inside the deny list it enforces, and that mention is the rule
# rather than a breach of it. What is left has to be a command: `git` in
# command position, any options, then `push`. That shape catches
# `git -C <folder> push` too, which is how the removed publisher wrote it.
pushes=$(for workflow_or_tool in "$ROOT"/.github/workflows/*.yml \
  "$ROOT"/.github/workflows/*.yaml "$ROOT"/.agents/tools/*.sh; do
  [ -f "$workflow_or_tool" ] || continue
  sed -e 's/#.*//' -e 's/"[^"]*"//g' "$workflow_or_tool" \
    | grep -nE '(^|[[:space:]]|[;&|]|\$\()git([[:space:]]+[^[:space:];&|]+)*[[:space:]]+push([[:space:]]|$)' \
    | sed "s|^|${workflow_or_tool##*/}:|"
done)
if [ -n "$pushes" ]; then
  echo "$pushes" >&2
  fail "a workflow or tool pushes to a repository; this repository's tree changes only through a reviewed pull request"
fi
if find "$ROOT/.github/workflows" "$ROOT/.agents/tools" -name '*publish-starter*' | grep -q .; then
  fail "the cross-repository starter publisher is back"
fi
if grep -RqE 'create-github-app-token|STARTER_APP_|x-access-token' "$ROOT/.github/workflows"; then
  fail "a workflow can mint a credential that writes outside the run's own token"
fi
# GitHub accepts .yaml as readily as .yml, so both are swept. A guard that reads
# the folder is only as good as its idea of what a workflow file is called.
# Only the two workflows that edit a Release, and the one job that moves
# `stable`, may write at all.
#
# Verification is the reason that last one is a job rather than a file. It
# earned its write by moving one branch to a release it has just verified, and
# the verification beside it still needs to read and nothing more. So the
# permission is asserted where it sits rather than merely allowed to exist
# somewhere in the file: nothing at the top level, where it would reach every
# job, and exactly one job carrying it. Written as a file-wide exemption, the
# rehearsal would pass a verify-release.yml that handed the write to everything
# in it, which is the mistake worth catching.
VERIFY_JOB_WRITE='^      contents: write$'
for workflow in "$ROOT"/.github/workflows/*.yml "$ROOT"/.github/workflows/*.yaml; do
  [ -f "$workflow" ] || continue
  case "${workflow##*/}" in
    prepare-release.yml | release-drafter.yml) continue ;;
    verify-release.yml)
      # The top-level block, read as the lines under `permissions:` at column
      # zero and stopping at the next thing written there.
      top=$(awk '/^permissions:/{seen=1;next} /^[^[:space:]]/{seen=0} seen' "$workflow")
      printf '%s\n' "$top" | grep -qx '  contents: read' || \
        fail "verify-release.yml does not keep its top-level permissions read-only"
      if printf '%s\n' "$top" | grep -qF 'contents: write'; then
        fail "verify-release.yml hands the repository write to every job in it"
      fi
      writers=$(grep -cE "$VERIFY_JOB_WRITE" "$workflow" || true)
      [ "${writers:-0}" -eq 1 ] || \
        fail "verify-release.yml has ${writers:-0} jobs that can write, and exactly one may"
      # Comments come out first. This file explains its own gate in prose
      # above the job, and a grep that reads the explanation as the gate would
      # pass a workflow whose comment survived while the line it describes was
      # deleted. That is exactly how a careless edit removes one.
      declared=$(sed 's/#.*//' "$workflow")
      printf '%s\n' "$declared" | grep -qE '^    needs: verify$' || \
        fail "the job that moves stable does not wait for verification to pass"
      printf '%s\n' "$declared" \
        | grep -qE '^ +run: \.agents/tools/promote-stable\.sh' || \
        fail "verify-release.yml writes to the repository without the bounded tool"
      continue
      ;;
  esac
  if grep -qF 'contents: write' "$workflow"; then
    fail "${workflow##*/} can write to the repository"
  fi
done

# Every job carries the gate, read off the folder rather than a list, so a
# workflow written tomorrow is covered from the moment it is saved. Without one
# it would run in anybody's fork.
#
# Per job, not per file. A file-wide grep is satisfied by one gated job while a
# second job beside it runs ungated, and that second job is the one nobody is
# watching.
if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
  ungated=$(GATE="$GATE" python3 - "$ROOT/.github/workflows" <<'UNGATED'
import glob, os, sys, yaml
gate = os.environ["GATE"]
folder = sys.argv[1]
for path in sorted(glob.glob(os.path.join(folder, "*.yml")) +
                   glob.glob(os.path.join(folder, "*.yaml"))):
    doc = yaml.safe_load(open(path)) or {}
    for job, body in (doc.get("jobs") or {}).items():
        if not isinstance(body, dict) or gate not in str(body.get("if", "")):
            print(f"{os.path.basename(path)}:{job}")
UNGATED
)
  if [ -n "$ungated" ]; then
    echo "$ungated" >&2
    fail "a workflow job has no repository gate, so it would run in a fork"
  fi
else
  # Without a parser this can only ask whether the gate appears at all, which a
  # second ungated job would satisfy. Say so rather than reporting a pass that
  # means less than it looks.
  echo "NOTE: python3 with PyYAML is unavailable, so the repository gate was checked per file rather than per job" >&2
  for workflow in "$ROOT"/.github/workflows/*.yml "$ROOT"/.github/workflows/*.yaml; do
    [ -f "$workflow" ] || continue
    grep -qF "$GATE" "$workflow" || \
      fail "${workflow##*/} has no repository gate, so it would run in a fork"
  done
fi

echo "release-publication.sh: all checks passed"
