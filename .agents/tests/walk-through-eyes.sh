#!/usr/bin/env sh
# walk-through-eyes.sh: guard what the walk-through can look at, and where its
# pictures go.
#
# The walk-through stands in for the person's try, so it is only as good as
# what the agent can see. Step 6 once said to take a screenshot "where the
# coding agent can take one" and nothing more. On a tool whose output was a PDF,
# that left two bad outcomes: the agent read the file's bytes and called it
# checked, or it said it could not see anything. And the screenshots went inside
# the piece's worktree, where they counted as unsaved work and kept the
# worktree after its pull request closed.
#
# So step 6 names the means for each kind of output in order, the limit on a
# long PDF, and a folder in the main folder. Founding records which means the
# machine has. Each rule is prose an agent reads, so this check reads it back
# and proves each one load-bearing. The tooling report's half runs, and is
# driven in check-tooling.sh.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
BUILDER="$SKILLS/section-builder/SKILL.md"
CAPABILITY="$SKILLS/setup-ai-build-kit/references/capability-check.md"
SETUP="$SKILLS/setup-ai-build-kit/SKILL.md"
TEMPLATE="$SKILLS/setup-ai-build-kit/templates/foundation/AGENTS.md"
REQUIRED="$SKILLS/setup-ai-build-kit/references/required-tools.md"
TOOLING="$SKILLS/setup-ai-build-kit/scripts/check-tooling.sh"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Walk-through eyes checks"
rs_exists "$BUILDER" "$CAPABILITY" "$SETUP" "$TEMPLATE" "$REQUIRED" \
  "$TOOLING" "$WORKFLOW"

# --- section-builder step 6 ------------------------------------------------

# The means, in the order they are tried. A web page first through the coding
# agent's own tool, then Playwright only where it is already there.
rs_rule "the profile's line says what the machine can use" \
  'read the capability profile.s `walk-through eyes:` line'
rs_rule "a project founded earlier checks at that moment and says so once" \
  'check each tool below with `command -v` now and say once what you found'
rs_rule "a web page: the coding agent's own browser tool first" \
  'the coding agent.s own browser tool where it has one'
rs_rule "otherwise Playwright's screenshot of the whole page" \
  'npx --no-install playwright screenshot --full-page <address> <file>'
rs_rule "only where Playwright is already there" \
  'where the project or the machine already has playwright'
rs_rule "the kit never installs a browser" 'the kit never installs a browser'
rs_rule "a PDF: one image a page, the first 30 pages" \
  'pdftoppm -png -r 80 -f 1 -l 30 <file> <folder>/page'
# A long PDF read only in part must not pass as seen whole.
rs_rule "pages past the thirtieth are named as not seen" \
  'pages past the thirtieth are named as not seen'
rs_rule "an office file becomes a PDF first" \
  'soffice --headless --convert-to pdf --outdir <folder> <file>'
rs_rule "then goes the PDF route" 'then the pdf route'
rs_rule "an image is read directly" 'png, jpeg, gif or webp: read it directly'
# The picture goes to the folder too. Written beside the SVG, it would land in
# the piece's worktree whenever the SVG is there.
rs_rule "an SVG is turned into a PNG in the pictures folder" \
  'magick <file> <folder>/<name>\.png'
rs_rule "the page count says whether pages were left unseen" \
  '`pdfinfo <file>`, from the same package, gives the page count'
rs_rule "each image is opened with the file reader" \
  'open each image with your file reader'
# The risk the issue names: a model judges the picture, so the report says
# what it held the picture up against.
rs_rule "and the report says what each showed and what it was compared with" \
  'record what each one showed and what you compared it against'

# Where the pictures go.
rs_rule "every picture goes to the main folder's walkthrough folder" \
  'in the main folder.s `\.agents/tmp/walkthrough/<issue number>/`'
rs_rule "never a folder inside a worktree" 'never a folder inside a worktree'
rs_rule "each walk-through has its own folder" \
  'walk-throughs running side by side never overwrite each other'

# When looking fails.
rs_rule "a renderer failing is a finding about the piece" \
  'record that as a finding about the piece, expected versus actual'
rs_rule "never put down to the renderer without saying why" \
  'treat it as the renderer.s fault only when you can say why'
rs_rule "an agent that cannot read images says it could not look" \
  'or the coding agent cannot read images, record that you could not look'
rs_rule "and the piece goes to to check with what was not seen" \
  'goes to `to check` and the pull request names what was not seen'
rs_guard "$BUILDER" "section-builder"

# The old wording put the folder wherever the build was running, which on a
# run is the piece's worktree.
rs_require_absent "an SVG's picture is never written beside the SVG" \
  "$BUILDER" 'magick <file> <file>\.png'
rs_require_absent "section-builder no longer keeps pictures in a folder relative to the build" \
  "$BUILDER" 'keep them in `\.agents/tmp/walkthrough'

# --- founding records the eyes ---------------------------------------------

rs_reset
rs_rule "the capability check writes the Walk-through eyes line" \
  'record a `walk-through eyes:` line in the capability profile'
rs_rule "it names the browser tool, or none" \
  'the browser tool the coding agent offers, or `none`'
rs_rule "whether Playwright is there" 'playwright present or not'
rs_rule "and each renderer" \
  'each of `pdftoppm`, `soffice` and `magick` present or not'
rs_rule "the tooling report is the machine check behind it" \
  'the machine check behind items 3, 11, 15, and 16'
rs_guard "$CAPABILITY" "capability-check.md"
rs_require_absent "the old browser-or-preview item is gone" \
  "$CAPABILITY" 'a browser or preview can be reached'

rs_require "founding records the eyes in the profile" "$SETUP" 'the walk-through.s eyes'
rs_require_absent "founding no longer records browser or preview access" \
  "$SETUP" 'browser or preview access'
rs_require "the founded AGENTS.md names the line" "$TEMPLATE" '`walk-through eyes:`'
rs_require_absent "and no longer names browser availability" \
  "$TEMPLATE" 'browser availability'
rs_require_load_bearing "required-tools.md says a missing renderer never stops founding" \
  "$REQUIRED" 'a missing one never stops founding either, and the kit never installs it'

# The report's own lines are driven in check-tooling.sh. Here only that the
# section exists and sets nothing that stops founding.
rs_require "the tooling report has an eyes section" "$TOOLING" 'what the walk-through can look with'

# --- WORKFLOW.md -----------------------------------------------------------

rs_reset
rs_rule "the walk-through looks at what you would see" \
  'the walk-through looks at what you would see'
rs_rule "a PDF, a document or an image becomes pictures it reads" \
  'for a pdf, a document or an image, it turns each page into a picture and reads it'
rs_rule "up to the first 30 pages" 'up to the first 30 pages'
rs_rule "how to give it more eyes" 'to give the walk-through more eyes'
rs_rule "the kit never installs them" 'the kit never installs them'
rs_rule "the pictures stay in the main folder" \
  'in the main folder.s `\.agents/tmp/walkthrough/<issue number>/`'
rs_guard "$WORKFLOW" "WORKFLOW.md"
rs_require_absent "WORKFLOW.md no longer keeps pictures relative to the build" \
  "$WORKFLOW" 'keeps them in `\.agents/tmp/walkthrough'

rs_done
