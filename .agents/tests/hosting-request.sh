#!/usr/bin/env sh
# hosting-request.sh: guard the hosting request /ship writes on a first launch.
#
# A tool that runs on a server somebody else runs gets its address from that
# server, and the kit never contacts it. The person carries a short request
# there by hand. The rules that matter most are the ones whose loss would be
# silent: that the request carries names and never a value, that the kit never
# contacts the server, and that a later launch reads the request back rather
# than asking the person again. The skills outside the recipes also stay free of
# any hosting, data or deploy product name, because a skill that needs to know
# how one behaves reads the project's recipe instead.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SHIP="$ROOT/.agents/skills/ship/SKILL.md"
HOSTING="$ROOT/.agents/skills/ship/references/hosting-request.md"
SETUP="$ROOT/.agents/skills/setup-ai-build-kit/SKILL.md"
MASTERPLAN="$ROOT/.agents/skills/setup-ai-build-kit/templates/masterplan.md"
WORKFLOW="$ROOT/WORKFLOW.md"
README="$ROOT/README.md"
SOURCES="$ROOT/docs/SOURCES.md"

rs_init "Hosting request rules"
rs_exists "$SHIP" "$HOSTING" "$SETUP" "$MASTERPLAN" "$WORKFLOW" "$README" "$SOURCES"

# When it applies.
rs_rule "it applies to a server this session cannot reach" 'where the tool will run on a server this session cannot reach'
rs_rule "the kit never contacts the server" 'the kit never contacts that server'
rs_rule "the person carries it by hand" 'the person carries a short request there by hand'

# The first launch.
rs_rule "it is written into How it stays running" 'on a first launch, read the masterplan.s "how it stays running" section\. when it holds no hosting request, write one there'
rs_rule "the skill points at the request's own file" 'write one there, as `references/hosting-request\.md` says'

# The launch waits for an answer. The wait belongs to the launch, so it stays in
# the skill, while how the answer is recorded lives with the request.
rs_rule "the launch waits for an address" 'the first launch is not finished until an address is recorded under the request'
rs_rule "the person hears it is not live yet" 'tell the person plainly that the tool is not live yet and is waiting on the server.s answer'
rs_rule "it is not recorded as live meanwhile" 'do not write it into changelog\.md as live'
rs_guard "$SHIP" "ship's hosting request"

# The request itself, its answer and a later launch live in one reference file
# the skill points at, since they are one procedure used only when a server
# this session cannot reach runs the tool.
rs_reset
rs_rule "the request lives in How it stays running" 'the request lives in the masterplan.s "how it stays running" section'
rs_rule "it is filled from the project, not by asking" 'filled from the project itself rather than by asking the person'
rs_rule "the repo and branch field" 'repo: +<url>, branch <branch>'
rs_rule "the lane field" 'lane: +internal \(private network\) \| public \(internet\)'
rs_rule "the port field" 'port: +<port the tool listens on>'
rs_rule "the env var field" 'env vars: +<names only>'
rs_rule "the persisted paths field" 'persist: +<paths that must survive a restart, or none>'
rs_rule "the health check field" 'healthcheck: +<path, or none>'
rs_rule "the build field" 'build: +dockerfile at root, image has curl or wget \| lock file or requirements\.txt, plus a procfile \| neither yet'
rs_rule "the bind field" 'bind: +0\.0\.0\.0 \| reads host and port \| 127\.0\.0\.1 \(not hostable yet\)'
rs_rule "build and bind are read from the code" 'take build from the files at the project.s root, and bind from the address the server listens on when it starts'
rs_rule "a tool bound to 127.0.0.1 is named once" 'a tool that listens only on 127\.0\.0\.1 cannot be reached from outside its container: say so once, and record it'
rs_rule "the lane comes from the fit check" 'take the lane from the fit check'
rs_rule "values are entered on the server" 'values are entered on the server'
rs_rule "no secret value is written" 'never write a value, key, password or token into the request'
rs_rule "an unknown field is none, not a guess" 'write `none` rather than guess'
rs_rule "on a recipe the health check is always filled" 'a project on a recipe always has a health route, because the recipe.s health section names one, so there healthcheck is that path and never .none.'
rs_rule "the block is printed for pasting" 'print the same block in the reply, so the person can paste it'
rs_rule "the one line the person hears" 'this tool needs a home\. take this request to whoever runs the server\.'

# The answer is recorded whenever it arrives, not only in the session that
# wrote the request. A person often carries the request away and comes back
# days later, in a new session.
rs_rule "an answer is recorded in any session" 'whenever the person pastes an answer, in this session or a later one, record its address and names under the request'
rs_rule "a secret in the answer is left out" 'leave out any secret value it carries'

# A later launch.
rs_rule "a later launch reads it back" 'on a later /ship, read the recorded hosting request back instead of asking again'
rs_rule "a missing answer is noticed" 'where no address is recorded under it, the request went out and no answer came back'
rs_rule "a missing answer is said and the request printed again" 'say so plainly, print the request again for the person to carry, and ask them to paste the answer here when it arrives'
rs_rule "a changed field is updated and printed again" 'where the project has changed a field since, update that line from the project and print the request again'
rs_guard "$HOSTING" "the hosting request's own file"

# Only the live paths. Explore privately never moves work to a live address, so
# the pointer to the request must sit after that branch ends and before Build
# with care begins.
rs_require_order "the request sits after Explore privately" "$SHIP" \
  '^### Build and run it' 'references/hosting-request\.md'
rs_require_order "the request sits inside Build and run it" "$SHIP" \
  'references/hosting-request\.md' '^### Build with care'

# The skills name no hosting, data or deploy product. A recipe file and the
# shared parts it links are the one place in the skills that may, since naming
# those services is their whole job, so everything under ship/recipes/ is left
# out. Every other file under the skills is read. The screen rules link Vercel's
# interface guidelines, which is a design guide rather than a place a tool runs,
# so that one link is set aside before the read.
PRODUCTS='coolify|vercel|supabase|netlify|heroku|railway|railpack|fly\.io|hetzner|hostinger|firebase|digitalocean'
products_named() {
  # products_named <skills folder>: each file and line that names a product.
  find "$1" -type f ! -path '*/ship/recipes/*' | sort | while IFS= read -r pn_file; do
    tr '[:upper:]' '[:lower:]' < "$pn_file" \
      | sed -e 's#vercel web interface guidelines##g' \
            -e 's#github\.com/vercel-labs/web-interface-guidelines##g' \
      | grep -nE "$PRODUCTS" | sed "s#^#$pn_file:#" || true
  done
}
if [ -z "${RS_LIST:-}" ]; then
  named=$(products_named "$ROOT/.agents/skills")
  if [ -n "$named" ]; then
    printf '%s\n' "$named" >&2
    rs_fail "a skill file outside the recipes names a hosting, data or deploy product"
  fi
  rs_ok "no skill file outside the recipes names a hosting, data or deploy product"

  # The read has to notice a name, keep the exemption narrow, and leave the
  # recipes alone, or it proves nothing.
  mkdir -p "$rs_dir/skills/ship/recipes/parts" "$rs_dir/skills/screen-check" "$rs_dir/skills/ship/references"
  grep -i 'web interface guidelines' "$ROOT/.agents/skills/screen-check/SKILL.md" > "$rs_dir/skills/screen-check/SKILL.md"
  printf '%s\n' 'Runs on Vercel with a Supabase database.' > "$rs_dir/skills/ship/recipes/on-vercel.md"
  printf '%s\n' 'Backups on Supabase.' > "$rs_dir/skills/ship/recipes/parts/backup.md"
  [ -z "$(products_named "$rs_dir/skills")" ] ||
    rs_fail "the guidelines link, a recipe or a part was counted as a product name"
  rs_ok "the guidelines link, a recipe and a part are left alone"
  printf '%s\n' 'Deploy it to Vercel.' > "$rs_dir/skills/ship/references/steps.md"
  [ -n "$(products_named "$rs_dir/skills")" ] ||
    rs_fail "a skill file naming a hosting product was not noticed"
  rs_ok "a skill file naming a hosting product is noticed"
  printf '%s\n' 'Vercel is fast.' 'The Vercel Web Interface Guidelines' > "$rs_dir/skills/ship/references/steps.md"
  [ -n "$(products_named "$rs_dir/skills")" ] ||
    rs_fail "the guidelines exemption hid a product named elsewhere in the same file"
  rs_ok "the guidelines exemption hides nothing else in the same file"
fi

rs_require_load_bearing "setup step 11 names the hand-off" "$SETUP" \
  'where a hosting companion or whoever runs the server will host it, /ship writes the hosting request on the first launch'
rs_require_load_bearing "the masterplan template has a place for it" "$MASTERPLAN" \
  '/ship writes a hosting request here on the first launch'
rs_require "the masterplan template keeps it to names" "$MASTERPLAN" 'names only, never a value'
rs_require "WORKFLOW tells the story" "$WORKFLOW" 'so /ship writes a hosting request into the masterplan'
rs_require "WORKFLOW says it holds names only" "$WORKFLOW" 'it holds names only, never a password or key'
rs_require "WORKFLOW says a later launch reads it back" "$WORKFLOW" 'on a later launch /ship reads the request back'
rs_require "the README FAQ answers where it runs" "$README" 'where does the tool run once it is built\?'
rs_require "the README says the companion is a separate install" "$README" 'it is a separate install, made by somebody else'
rs_require_absent "the README does not put the companion on the server" "$README" 'separate install on the server'
rs_require "SOURCES credits the hosting request" "$SOURCES" 'kasperhonore/coolify-devops'

rs_done
