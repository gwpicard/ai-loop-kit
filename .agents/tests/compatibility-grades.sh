#!/usr/bin/env sh
# compatibility-grades.sh: guard the grade each coding agent carries in
# docs/COMPATIBILITY.md, and the rule that a grade rests on evidence.
#
# The page used to name four agents and present them alike, while the replay
# harness had only ever recorded runs on one of them. A kit that tells a person
# when a green tick is a smaller claim than it looks should not then claim
# support for an agent on the strength of nobody complaining. So each agent the
# page names carries one of three grades, and this check holds two things.
#
# The first is prose: the three grades, what moves an agent up, that an absence
# of complaints is not evidence, and the known limits of anything below the top
# grade. The second is mechanical. An agent graded Tested has to be one the
# replay harness can drive, and a run on it has to be on record. Claude Code is
# the harness's default provider, so a recorded run that names no provider was
# driven on Claude Code. Any other agent needs a run header in the recorded
# baseline with a provider field naming it, a line such as
#
#   - **Provider:** `codex`
#
# before it can be called Tested. A bare mention is not enough, because the
# likeliest sentence to name Codex in that file is one saying no Codex run has
# been recorded. That is the promotion this check exists to refuse: a grade
# raised by editing the page rather than by a run.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

COMPAT="$ROOT/docs/COMPATIBILITY.md"
README="$ROOT/README.md"
PROVIDER="$ROOT/.agents/tests/replay/provider.sh"
RUNNER="$ROOT/.agents/tests/replay/run.sh"
BASELINE="$ROOT/.agents/tests/replay/baseline.md"

rs_init "Compatibility-grade checks"
rs_exists "$COMPAT" "$README" "$PROVIDER" "$RUNNER" "$BASELINE"

rs_rule "Tested means a recorded replay run" \
  '\*\*tested\.\*\* the kit.s replay harness has driven this agent'
rs_rule "Expected to work means nobody has recorded a run" \
  '\*\*expected to work\.\*\* the agent reads the same skill files'
rs_rule "Experimental means only the shape of the files is checked" \
  '\*\*experimental\.\*\* nobody has recorded running the kit'
rs_rule "a quiet issue tracker is not evidence" \
  'a quiet issue tracker is not evidence'
rs_rule "moving to Expected to work needs a run on a published release" \
  'to move from experimental to expected to work, somebody runs a published release'
rs_rule "moving to Tested needs the harness and a recorded rate" \
  'to move from expected to work to tested, the replay harness drives the agent'
rs_rule "Tested describes a rate" \
  'tested describes a rate. the harness runs each conversation'
rs_rule "a Tested run names the agent and a published release" \
  'the record names the agent the harness drove, and it names a published release'
rs_rule "Claude Code's runs were on commits of main, not releases" \
  'every claude code run on record was on a commit of `main` between two releases, not on a published release'
rs_rule "the plugin route's conversations cannot be replayed" \
  'its conversations cannot be replayed'
rs_rule "Codex's known limits are written down" \
  '### known limits of codex'
rs_rule "the known limits of the experimental agents are written down" \
  '### known limits of cursor, gemini cli and github copilot'
rs_guard "$COMPAT" "COMPATIBILITY.md"

rs_require "the README points a person choosing an agent at the grades" \
  "$README" 'compatibility\.md#how-much-has-been-proved-on-each-agent'
rs_require_absent "the README no longer lists four agents as alike" \
  "$README" '\| works with \| claude code, codex, cursor, gemini cli, or any agent'

[ -n "${RS_LIST:-}" ] && exit 0

# --- the mechanical half --------------------------------------------------

# The providers the harness accepts, read from its own case statement, and the
# one it uses when none is named.
providers=$(sed -n '/^provider_check()/,/^}/p' "$PROVIDER" \
  | grep -oE '^    [a-z]+\)' | tr -d ' )')
default_provider=$(grep -oE 'REPLAY_PROVIDER=\$\{REPLAY_PROVIDER:-[a-z]+\}' "$RUNNER" \
  | head -1 | sed -E 's/.*:-([a-z]+)\}/\1/')
[ -n "$providers" ] || rs_fail "could not read the replay providers from provider.sh"
[ -n "$default_provider" ] || rs_fail "could not read the default replay provider from run.sh"

provider_for() {
  case "$1" in
    "Claude Code") echo claude ;;
    "Codex") echo codex ;;
    *) echo "" ;;
  esac
}

# recorded_run <provider> <baseline-file>: succeeds when the baseline carries a
# run header whose provider field names this provider.
recorded_run() {
  grep -qiE "^- \*\*provider:\*\* \`$1\`" "$2"
}

# grade_problems <compatibility-file> [<baseline-file>]: prints one line per
# problem, nothing when the grades hold.
grade_problems() {
  record=${2:-$BASELINE}
  grades=$(grep -E '^\| [^|]+ \| (Tested|Expected to work|Experimental) \|$' "$1" \
    | sed -E 's/^\| ([^|]+) \| ([^|]+) \|$/\1|\2/')
  # Every agent the harness map names needs a grade. Read the map rather than
  # a list written out here, so an agent added to the map is held too.
  sed -n '/^## Harness map/,/^## /p' "$1" \
    | grep -E '^\| [A-Z]' | grep -v '^| Harness |' \
    | sed -E 's/^\| ([^|,]+)[,|].*/\1/' | sed -E 's/ +$//' | sort -u \
    | while IFS= read -r agent; do
        printf '%s\n' "$grades" | grep -qF "$agent|" \
          || echo "$agent is in the harness map with no grade"
      done
  printf '%s\n' "$grades" | while IFS='|' read -r agent grade; do
    [ "$grade" = "Tested" ] || continue
    p=$(provider_for "$agent")
    if [ -z "$p" ] || ! printf '%s\n' "$providers" | grep -qx "$p"; then
      echo "$agent is graded Tested but the replay harness cannot drive it"
      continue
    fi
    if [ "$p" != "$default_provider" ] && ! recorded_run "$p" "$record"; then
      echo "$agent is graded Tested but no recorded run names it (baseline.md needs a run header with - **Provider:** \`$p\`)"
    fi
  done
}

problems=$(grade_problems "$COMPAT")
if [ -z "$problems" ]; then
  rs_ok "every agent in the harness map carries a grade, and each Tested grade has a recorded run"
else
  printf '%s\n' "$problems" | sed 's/^/  /'
  rs_fail "the grades in COMPATIBILITY.md do not rest on the record"
fi

# Prove the mechanical half can fail. Each copy breaks one thing.
copy="$rs_dir/compat-copy.md"

sed -E 's/^\| Codex \| Expected to work \|$/| Codex | Tested |/' "$COMPAT" > "$copy"
if grade_problems "$copy" | grep -q 'Codex is graded Tested but no recorded run names it'; then
  rs_ok "promoting Codex to Tested with no recorded run is caught"
else
  rs_fail "promoting Codex to Tested with no recorded run was not caught"
fi

# A sentence that names Codex only to say it was never run is not a run.
cp "$BASELINE" "$rs_dir/baseline-denial.md"
printf '\nNo Codex run has been recorded. The codex provider has not been driven.\n' \
  >> "$rs_dir/baseline-denial.md"
if grade_problems "$copy" "$rs_dir/baseline-denial.md" \
  | grep -q 'Codex is graded Tested but no recorded run names it'; then
  rs_ok "a baseline that names Codex only to deny a run does not make it Tested"
else
  rs_fail "a baseline that names Codex only to deny a run let Codex be Tested"
fi

# And the guard is not simply refusing everything: a real run header passes.
cp "$BASELINE" "$rs_dir/baseline-run.md"
printf '\n## A Codex run\n\n- **Provider:** `codex`\n' >> "$rs_dir/baseline-run.md"
if grade_problems "$copy" "$rs_dir/baseline-run.md" | grep -q 'Codex is graded Tested'; then
  rs_fail "a recorded Codex run header was not accepted"
else
  rs_ok "a recorded Codex run header is accepted"
fi

sed -E 's/^\| Cursor \| Experimental \|$/| Cursor | Tested |/' "$COMPAT" > "$copy"
if grade_problems "$copy" | grep -q 'Cursor is graded Tested but the replay harness cannot drive it'; then
  rs_ok "promoting an agent the harness cannot drive is caught"
else
  rs_fail "promoting an agent the harness cannot drive was not caught"
fi

grep -vE '^\| GitHub Copilot \| Experimental \|$' "$COMPAT" > "$copy"
if grade_problems "$copy" | grep -q 'GitHub Copilot is in the harness map with no grade'; then
  rs_ok "an agent in the harness map with no grade is caught"
else
  rs_fail "an agent in the harness map with no grade was not caught"
fi

rs_done
