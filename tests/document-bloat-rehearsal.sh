#!/usr/bin/env sh
# document-bloat-rehearsal.sh: run the shipped document-bloat script against a
# throwaway project carrying each kind of bloat, and against a clean one.
#
# The project holds a paragraph repeated in two documents and a note nothing
# names. Both have to be found. Just as much, the things that look like bloat
# and are not have to be left alone: a README nothing links to, the project
# records and the kit's own files, a short sentence two documents share, and a
# page naming files the project no longer has, which the document read in
# /sync reports one name at a time, and a changelog file waiting in
# `changes/`. A clean project produces nothing, and the script writes nothing.
#
# Leaving those alone is the half that matters. A tidy-up offered for a note
# somebody wanted, or for a sentence that belongs in both places, teaches the
# person to say no to all of them.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCRIPT="$ROOT/kit/scripts/document-bloat.py"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -x "$SCRIPT" ] || fail "the document-bloat script is missing or not runnable"
command -v python3 >/dev/null 2>&1 || fail "python3 is needed to run this rehearsal"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PROJECT="$WORK/project"
mkdir -p "$PROJECT/docs" "$PROJECT/src"
cd "$PROJECT"

save() {
  git add -A
  git -c user.name=Rehearsal -c user.email=rehearsal@example.invalid \
    commit -q -m "$1"
}

PARAGRAPH="To release the tool, first make sure the environment file holds the database address and the payment key. Then run the release script from the project root, wait for the health check to pass, and tell the team in the channel that the new version is live. If the health check fails, roll back to the previous release."

git init -q
# The script lives inside the project, as it does once the kit is installed, so
# anything it wrote beside itself would show as a change in the project.
mkdir -p .agents/skills/maintain/scripts
cp "$SCRIPT" .agents/skills/maintain/scripts/
SCRIPT="$PROJECT/.agents/skills/maintain/scripts/document-bloat.py"
printf '%s\n' '{"name":"shop","scripts":{"dev":"node src/index.js"}}' > package.json
printf '%s\n' 'console.log(1);' > src/index.js
printf '%s\n' 'export const pay = 1;' > src/pay.js
printf '%s\n' 'export const ship = 1;' > src/ship.js
# Records and kit files: never read, whatever they contain.
printf '# Masterplan\n\n%s\n' "$PARAGRAPH" > masterplan.md
printf '# Agents\n\nThe guide is `docs/guide.md`. It names nothing else.\n' > AGENTS.md
printf '# How this project runs\n\nNothing names this file.\n' > WORKFLOW.md
cat > README.md <<'EOF'
# Shop

It sells things. Run `npm run dev` to start it.
EOF
cat > docs/guide.md <<'EOF'
# Guide

The entry point is `src/index.js`. Payments are in `src/pay.js`, shipping in
`src/ship.js`, and old refunds lived in `src/refunds.js`. Always check the
total before you pay.
EOF
save "A tidy project"

# --- a clean project --------------------------------------------------------

out=$(python3 "$SCRIPT")
[ -z "$out" ] || fail "a tidy project should produce nothing, got: $out"
echo "  ok: a tidy project produces nothing"
echo "  ok: a README nothing links to is left alone"
echo "  ok: the records and the kit's own files are not read, though they repeat and are unnamed"
[ -z "$(git status --porcelain)" ] || fail "the script wrote into the project"
echo "  ok: the script writes nothing"

# --- one of each finding ----------------------------------------------------

printf '# Shop\n\nIt sells things.\n\n%s\n\nSee [releasing](docs/release.md) and [legacy](docs/legacy.md).\n' "$PARAGRAPH" > README.md
printf '# Releasing\n\nA short introduction.\n\n%s\n\nAlways check the total before you pay.\n' "$PARAGRAPH" > docs/release.md
printf '# Legacy\n\nStart with `src/old.js`, then `src/older.js`, and run `npm run legacy`.\nThe entry point is `src/index.js`.\n' > docs/legacy.md
printf '# Scratch\n\nSome notes nobody links to.\n' > docs/scratch.md
# A piece's changelog file waits in changes/ until a fold. Nothing names it
# and its sentence may repeat the pull request, but it is part of the
# changelog, never bloat.
mkdir -p changes
printf '%s\n' "$PARAGRAPH" > changes/7-release.md
save "The documents grow"

out=$(python3 "$SCRIPT")
printf '%s\n' "$out" | sed 's/^/    /'

has() {
  printf '%s\n' "$out" | grep -qF "$(printf '%s' "$1")" || fail "$2"
  echo "  ok: $3"
}
has "$(printf 'repeated\tREADME.md:5\tdocs/release.md:5')" \
  "the repeated paragraph was not found at both places" \
  "the paragraph repeated in two documents is named at both lines"
has "$(printf 'unreferenced\tdocs/scratch.md')" \
  "the note nothing names was not found" \
  "the note nothing names is found"

[ "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" = 2 ] ||
  fail "expected exactly two findings, got: $out"
echo "  ok: the short sentence two documents share is not called a repeat"
printf '%s\n' "$out" | grep -qE 'masterplan|AGENTS|WORKFLOW|guide\.md|legacy\.md|changes/' &&
  fail "a record, a kit file, a live document or the stale-names page was reported"
echo "  ok: a page naming files the project no longer has is left to the sync read"
echo "  ok: a changelog file waiting in changes/ is neither unreferenced nor a repeat"
echo "  ok: nothing else is reported"
printf '%s\n' "$out" | grep -qE '[0-9]+ *%|score|grade' && fail "a score reached the output"
echo "  ok: no score, grade or percentage"
[ -z "$(git status --porcelain)" ] || fail "the script wrote into the project"
echo "  ok: the script still writes nothing"

echo
echo "document-bloat-rehearsal.sh: each kind of bloat found, everything else left alone"
