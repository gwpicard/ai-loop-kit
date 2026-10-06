#!/usr/bin/env sh
# check-skills.sh: prove that kit/scripts/check-skills.py holds the skill principles.
#
# The lint is the check, so the check must be able to fail. The good fixture in
# tests/fixtures/skills/good/ must pass. Then each rule gets one mutation of a
# copy: the copy must fail, and the lint must name that rule and no other. A
# mutation that the lint passes means the rule does not hold.
#
# Also checked: the plugin manifest and the glossary exist and carry what the
# lint reads, and `claude plugin validate` runs when `claude` is installed. It
# never starts a session. Without `claude`, a visible "skipped" line is printed,
# and the skip is not counted as a pass.
#
# Everything runs in a throwaway directory. No network, no account, no model.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"

LINT="$ROOT/kit/scripts/check-skills.py"
GOOD="$ROOT/tests/fixtures/skills/good"
MANIFEST="$ROOT/kit/.claude-plugin/plugin.json"
GLOSSARY="$ROOT/kit/glossary.md"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

rs_init "Skills lint checks"
rs_exists "$LINT" "$GOOD/shape/SKILL.md" "$MANIFEST" "$GLOSSARY"
WORK="$rs_dir"

# --- helpers ---------------------------------------------------------------

fresh() {
  # fresh: a new copy of the good fixture in a new folder, named by $M.
  M=$(mktemp -d "$WORK/m.XXXXXX")
  cp -R "$GOOD/." "$M/"
}

edit() {
  # edit <file> <python statement over the text `t`>: change a file in the copy.
  python3 - "$M/$1" "$2" <<'PY'
import sys
path, code = sys.argv[1], sys.argv[2]
t = open(path, encoding="utf-8").read()
scope = {"t": t}
exec(code, scope)
open(path, "w", encoding="utf-8").write(scope["t"])
PY
}

lint() {
  # lint <dir>: run the lint, keep the output and the exit code.
  set +e
  python3 "$LINT" --json --glossary "$GLOSSARY" "$1" > "$WORK/out" 2> "$WORK/err"
  LINT_CODE=$?
  set -e
}

rules_in() {
  # rules_in <key>: the sorted rule ids under "findings" or "warnings".
  python3 - "$WORK/out" "$1" <<'PY'
import json, sys
body = json.load(open(sys.argv[1]))
print(" ".join(sorted({f["rule"] for f in body.get(sys.argv[2], [])})))
PY
}

expect_fail() {
  # expect_fail <rule id> <description>: the copy in $WORK/m must fail on that rule alone.
  lint "$M"
  if [ "$LINT_CODE" -eq 0 ]; then
    cat "$WORK/out"
    rs_fail "the lint passed a copy with this fault: $2"
  fi
  got=$(rules_in findings)
  if [ "$got" != "$1" ]; then
    cat "$WORK/out"
    rs_fail "the lint refused '$2' for '$got', not for '$1'"
  fi
  rs_ok "$2 is refused ($1)"
}

expect_warn() {
  # expect_warn <rule id> <description>: a warning, and still a pass.
  lint "$M"
  if [ "$LINT_CODE" -ne 0 ]; then
    cat "$WORK/out"
    rs_fail "the lint refused a copy that should only warn: $2"
  fi
  got=$(rules_in warnings)
  if [ "$got" != "$1" ]; then
    cat "$WORK/out"
    rs_fail "the lint warned '$got' for '$2', not '$1'"
  fi
  rs_ok "$2 warns ($1)"
}

# --- the good fixture passes -------------------------------------------------

lint "$GOOD"
if [ "$LINT_CODE" -ne 0 ]; then
  cat "$WORK/out"
  rs_fail "the lint refused the good fixture"
fi
[ -z "$(rules_in warnings)" ] || { cat "$WORK/out"; rs_fail "the good fixture has a warning"; }
rs_ok "the good fixture passes with no finding and no warning"

# --- principle 3: size ------------------------------------------------------

fresh
edit shape/SKILL.md 't += "".join("- Filler line %d.\n" % i for i in range(150))'
expect_fail P3-lines "a SKILL.md over 150 lines"

fresh
edit shape/SKILL.md 't += "- " + "word " * 2000 + "\n"'
expect_fail P3-words "a SKILL.md over 2,000 words"

fresh
edit shape/SKILL.md 't = t.replace("a spec the gate can check.", "a spec the gate can check" + ", and more" * 30 + ".")'
expect_fail P3-description "a description over 300 characters"

fresh
edit shape/references/spec-shape.md 't += "".join("Line %d of the filler.\n" % i for i in range(300))'
edit shape/references/spec-shape.md 't = t.replace("# Spec shape", "# Spec shape\n\n## Contents\n- Shape\n", 1)'
expect_fail P3-reference-lines "a reference over 300 lines"

# --- principle 1: held by -----------------------------------------------------

fresh
edit shape/SKILL.md 't = t.replace(" Held by: the gate refuses a move to ready without a spec that passes the spec lint.", "")'
expect_fail P1-held-by "a stop with no Held by line"

# --- principle 2: do not restate the gate --------------------------------------

fresh
edit shape/SKILL.md 't += "\n- A ready piece carries the state:ready label.\n"'
expect_fail P2-gate-copy "a copied gate label name"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Exit codes: 0 ok, 1 failed, 3 refused.\n\n## Gotchas")'
expect_fail P2-gate-copy "a copied exit code list"

fresh
edit shape/references/questions.md 't += "\n| from | to |\n| --- | --- |\n| state:shaping | state:ready |\n"'
expect_fail P2-gate-copy "a copied row of the gate table"

# --- principle 4: order ----------------------------------------------------------

fresh
edit shape/SKILL.md '''
head, rest = t.split("## Steps", 1)
steps, tail = rest.split("## Gotchas", 1)
gotchas, more = tail.split("## When to read more", 1)
t = head + "## Gotchas" + gotchas + "## Steps" + steps + "## When to read more" + more
'''
expect_fail P4-order "sections out of order"

fresh
edit shape/SKILL.md 't = t.replace("## Stops", "## Halts")'
expect_fail P4-order "a skill with no Stops section"

# --- principle 5: who invokes ----------------------------------------------------

fresh
edit run/SKILL.md 't = t.replace("disable-model-invocation: true\n", "")'
expect_fail P5-disable "the run skill without disable-model-invocation"

fresh
edit setup/SKILL.md 't = t.replace("disable-model-invocation: true\n", "")'
expect_fail P5-disable "the setup skill without disable-model-invocation"

fresh
mkdir -p "$M/maintain/evals"
cp "$M/setup/SKILL.md" "$M/maintain/SKILL.md"
cp "$M/setup/evals/"* "$M/maintain/evals/"
edit maintain/SKILL.md 't = t.replace("name: setup", "name: maintain").replace("disable-model-invocation: true\n", "").replace("# Setup", "# Maintain")'
edit maintain/SKILL.md 't = t.replace("Installs the kit into a project.", "Keeps the kit and the project tidy.")'
expect_fail P5-disable "the maintain skill without disable-model-invocation"

fresh
edit shape/SKILL.md 't = t.replace("Use when the person", "Handy when the person")'
expect_fail P5-use-when "a model-invoked description with no Use when clause"

# --- principle 6: one level of references -------------------------------------------

fresh
edit shape/references/spec-shape.md 't += "\nRead `references/questions.md` when the question has no guess.\n"'
expect_fail P6-nested "a reference that points at another reference"

fresh
mkdir -p "$M/shape/references/deep"
printf '# Deep\nA file under a folder in references.\n' > "$M/shape/references/deep/more.md"
expect_fail P6-nested "a reference in a nested folder"

fresh
printf '# Orphan\nNo skill reads this.\n' > "$M/shape/references/orphan.md"
expect_fail P6-orphan "a reference no SKILL.md names"

fresh
edit shape/SKILL.md 't = t.replace("Read `references/spec-shape.md` when the spec has more than three sections.", "See `references/spec-shape.md`.")'
expect_fail P6-condition "a link line with no condition word"

fresh
edit shape/references/questions.md 't += "".join("A plain line number %d.\n" % i for i in range(105))'
expect_fail P6-contents "a reference over 100 lines with no contents list"

# --- principle 7: freedom matches fragility ------------------------------------------

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "```sh\nset -e\ncd here\nmake it\nrun it\n```\n\n## Gotchas")'
expect_fail P7-long-block "a shell block over three lines"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "```sh\ngh issue list | xargs gh issue close\n```\n\n## Gotchas")'
expect_fail P7-pipe "a pipe into a state change"

# --- principle 9: do not shout --------------------------------------------------------

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "You MUST ask first.\n\n## Gotchas")'
expect_fail P9-emphasis "capitalised emphasis"

fresh
edit shape/SKILL.md 't = t.replace("## When to read more", "- Do not guess the answer.\n\n## When to read more")'
expect_warn P9-warn "a do-not with no positive instruction"

# --- principle 10: gotchas -------------------------------------------------------------

fresh
edit run/SKILL.md 't = t.split("## Gotchas")[0]'
expect_fail P10-gotchas "a skill with no Gotchas section"

# --- principle 11: one home, one word ---------------------------------------------------

fresh
python3 - "$M" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
shape = (root / "shape/SKILL.md").read_text(encoding="utf-8")
para = shape.split("\n")[5]  # the intro paragraph
assert len(para.split()) >= 40, len(para.split())
now = root / "what-now/SKILL.md"
now.write_text(now.read_text(encoding="utf-8").replace("## Gotchas", para + "\n\n## Gotchas"), encoding="utf-8")
PY
expect_fail P11-repeat "a paragraph repeated in two skills"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Each ticket is one issue.\n\n## Gotchas")'
expect_fail P11-banned "a banned synonym (ticket)"

fresh
edit run/SKILL.md 't = t.replace("## Gotchas", "Each stage is one label.\n\n## Gotchas")'
expect_fail P11-banned "a banned synonym (stage)"

# --- principle 12: done conditions -------------------------------------------------------

fresh
edit shape/SKILL.md 't = t.replace("   Done when: the person has answered, or has said \"you choose\".\n", "")'
expect_fail P12-done-when "a step with no Done when line"

# --- principle 13: live state -------------------------------------------------------------

fresh
edit what-now/SKILL.md 't = t.replace("!`python3 kit/scripts/gate.py report --json --brief`", "Run the report.")'
expect_fail P13-now "what-now without the injected report line"

fresh
edit run/SKILL.md 't = t.replace("If the line above shows a disabled marker, run that command by hand first.\n", "")'
expect_fail P13-now "run without the fallback line"

fresh
edit run/SKILL.md 't = t.replace("gate.py report --json --brief", "gate.py report")'
expect_fail P13-now "run with a different report command"

# --- principle 15: evals --------------------------------------------------------------------

fresh
rm -- "$M/setup/evals/edge.md"
expect_fail P15-evals "a skill with two eval cases"

fresh
rm -- "$M/shape/evals/"*
rmdir "$M/shape/evals"
expect_fail P15-evals "a skill with no evals folder"

# --- principle 16: timeless --------------------------------------------------------------------

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Written on 5 October 2026.\n\n## Gotchas")'
expect_fail P16-timeless "a date in words"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Checked on 2026-10-05.\n\n## Gotchas")'
expect_fail P16-timeless "a numeric date"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Needs version 2.1.219 or later.\n\n## Gotchas")'
expect_fail P16-timeless "a version number"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Tuned for Sonnet.\n\n## Gotchas")'
expect_fail P16-timeless "a model name"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "See issue #" "42 for the reason.\n\n## Gotchas")'
expect_fail P16-timeless "an issue number"

fresh
edit shape/SKILL.md 't = t.replace("## Gotchas", "Fixed in commit 5b808b1.\n\n## Gotchas")'
expect_fail P16-timeless "a commit hash"

# --- principle 17: a guard is not the skill's own frontmatter ---------------------------------------

fresh
edit shape/SKILL.md 't = t.replace("Held by: `kit/scripts/spec.py` exits non-zero on a bad spec.", "Held by: the allowed-tools list in this skill\x27s frontmatter.")'
expect_fail P17-guard "a guard held only by the skill's frontmatter"

fresh
edit shape/SKILL.md 't = t.replace("Held by: `kit/scripts/spec.py` exits non-zero on a bad spec.", "Held by: care.")'
expect_fail P17-guard "a Held by line that names no holder"

# --- the lint reads its own arguments -----------------------------------------------------------------

set +e
python3 "$LINT" --json "$WORK/does-not-exist" > "$WORK/out" 2> "$WORK/err"
code=$?
set -e
[ "$code" -eq 4 ] || rs_fail "a missing folder should exit 4, got $code"
grep -q '^next:' "$WORK/err" || rs_fail "a missing folder should print a next: line"
rs_ok "a missing folder is refused with exit 4 and a next: line"

# --- the manifest and the glossary -----------------------------------------------------------------------

python3 - "$MANIFEST" <<'PY' || rs_fail "plugin.json is not valid or lacks a name and description"
import json, sys
body = json.load(open(sys.argv[1]))
assert body["name"] == "ai-loop-kit"
assert body["description"]
PY
rs_ok "plugin.json is valid JSON with a name and a description"

rs_require "the glossary bans a synonym for piece" "$GLOSSARY" 'banned: ticket'
rs_require "the glossary bans a synonym for state" "$GLOSSARY" 'banned: stage'

# --- the standard's validator, when claude is installed --------------------------------------------------

if command -v claude > /dev/null 2>&1; then
  if claude plugin validate "$ROOT/kit" > "$WORK/validate.out" 2>&1; then
    rs_ok "claude plugin validate accepts kit/"
  else
    cat "$WORK/validate.out"
    rs_fail "claude plugin validate refused kit/"
  fi
else
  echo "  skipped: claude is not installed, so claude plugin validate did not run"
fi

# --- the real skills --------------------------------------------------------------------------------------

python3 "$LINT" --json --glossary "$GLOSSARY" > "$WORK/out" 2> "$WORK/err" || {
  cat "$WORK/out"
  rs_fail "the lint refused the skills under kit/skills/"
}
rs_ok "the skills under kit/skills/ pass the lint"

rs_done
