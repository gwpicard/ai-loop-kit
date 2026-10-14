#!/usr/bin/env sh
# recipes.sh: guard the recipe format and the check that reads recipe files.
#
# A recipe is one build stack paired with one place to run it, and it is the
# only place in the kit, besides the README, allowed to name a service a tool
# runs on. That permission is the risky half. Without the rules around it, a
# recipe becomes a list of product tips that nobody has tried, offered on a menu
# as if the kit could vouch for it. So this check reads the rules that stop that
# back out of the format reference, and proves each one is load-bearing.
#
# The second half runs the shipped shape check against a recipe filled in from
# the blank, then against copies with one part taken away at a time. A check
# that passed a recipe missing its backup section would let one onto the menu
# with a launch step nobody can check. It also drives the rehearsal rule, since
# a rehearsal that only exits cleanly would otherwise count as proof.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$ROOT/tests/lib/rule-shape.sh"

FORMAT="$ROOT/kit/templates/recipe-format.md"
BLANK="$ROOT/kit/templates/recipe.md"
CHECKER="$ROOT/kit/scripts/check-recipes.sh"

rs_init "Recipe format checks"
rs_exists "$FORMAT" "$BLANK" "$CHECKER"

# --- what a recipe is ----------------------------------------------------
rs_rule "a recipe is one stack paired with one place" 'one build stack paired with one place to run it'
rs_rule "two places are two recipes" 'a stack that runs in two places is two recipes'
rs_rule "recipes live in ship/recipes" 'recipes live in .ship/recipes/.'
rs_rule "the folder is the menu" 'the folder is the menu'
rs_rule "a recipe says when it is the one to recommend" 'when founding should recommend this recipe over another that fits the same shape'

# --- what it holds -------------------------------------------------------
rs_rule "a recipe names the command-line tools its checks run" 'the tools the recipe.s checks run on the person.s machine'
rs_rule "a missing recipe tool never stops founding" 'a missing one never stops founding'
rs_rule "the last-checked date moves only on a real read" 'the date moves only when somebody did that'
rs_rule "the eight sections, in order" 'preview, going live, rollback, backup, restore, secrets, logs and health'
rs_rule "each section says who runs its check" 'says who runs that check, and takes one of three'
rs_rule "the kit runs it" '.the kit. when the kit runs the check itself'
rs_rule "a companion or the person runs it, result read back" 'result read back. when the check runs somewhere the kit cannot reach'
rs_rule "a person looks" '.a person looking. when no machine can judge it'
rs_rule "a section with no check is unfinished" 'a section with no check is not finished'

# --- shared parts ----------------------------------------------------------
rs_rule "a shared section is written once, as a part" 'is written once, as a part in .ship/recipes/parts/.'
rs_rule "a part holds the lines a section would" 'a part holds the same three lines a section would'
rs_rule "the parts folder is not on the menu" 'the parts folder is not a menu entry'

# --- the settings the kit can read -------------------------------------------
rs_rule "a recipe may say which settings the kit reads" 'a recipe may carry one more section, .## settings the kit can read., between health and the proven section'
rs_rule "the review reads them rather than asking" 'so the launch review reads them rather than asking the person to look them up'
rs_rule "only a key the browser already has" 'such a read uses only a key the project already sends to the browser'
rs_rule "a secret-key read does not belong" 'a setting that needs a secret key to read does not belong here'
rs_rule "the section gets an outcome line" 'a recipe that carries it gives it an outcome line in its proven section, starting .settings the kit can read:.'

# --- what proven means ---------------------------------------------------
rs_rule "rehearsals guard the rules" 'offline rehearsals guard its rules'
rs_rule "the rehearsal names the recipe" 'a maintainer check names the recipe file'
rs_rule "one real deploy, start to finish" 'one real deploy has been run from an empty project to a live address and through all eight sections'
rs_rule "with the maintainer's approval and accounts" 'with the maintainer.s approval and accounts'
rs_rule "the record lives in the recipe" 'the record lives in the recipe.s own proven section'
rs_rule "one outcome line for each section" 'one outcome line for each of the eight sections'
rs_rule "a changed how-it-works line needs a new real run" 'needs a new real run before the next release'
rs_rule "no draft state" 'there is no draft state'

# --- service names and the project's record ------------------------------
rs_rule "only recipes and the README name a service a tool runs on" 'no other file in the kit names a service a tool runs on'
rs_rule "a skill reads the recipe instead" 'a skill that needs to know how one behaves reads the project.s recipe'
rs_rule "the project records it in the stack section" 'in its own agents\.md, in the stack section'
rs_rule "and not in the build-path block" 'it does not go in the build-path block'
rs_guard "$FORMAT" "recipe-format.md"

rs_require_absent "the format does not promise every check runs by machine" "$FORMAT" \
  'eight sections by machine'

# --- the shape check itself ----------------------------------------------
FILLED="$rs_dir/filled.md"
sed -e 's/YYYY-MM-DD/2024-02-29/' -e 's/^Who runs it: .*/Who runs it: a person looking/' \
  -e 's/<[^>]*>/filled in/g' "$BLANK" > "$FILLED"

"$CHECKER" --template "$BLANK" >/dev/null
rs_ok "the blank has the shape it asks for"

if "$CHECKER" "$BLANK" >/dev/null; then
  rs_fail "an unfilled blank passed as a recipe"
fi
rs_ok "an unfilled blank is refused as a recipe"

"$CHECKER" "$FILLED" >/dev/null
rs_ok "a filled recipe passes, dated on a leap day"

refused() {
  # refused <description> <sed-program>: a copy with that edit must fail.
  sed -e "$2" "$FILLED" > "$rs_dir/mutant.md"
  if cmp -s "$FILLED" "$rs_dir/mutant.md"; then
    rs_fail "the edit for '$1' changed nothing, so it proves nothing"
  fi
  if "$CHECKER" "$rs_dir/mutant.md" >/dev/null; then
    rs_fail "a recipe with $1 passed"
  fi
  rs_ok "a recipe with $1 is refused"
}

for section in Preview "Going live" Rollback Backup Restore Secrets Logs Health Proven; do
  refused "no $section section" "/^## $section\$/d"
done
refused "no Fits line" '/^Fits:/d'
refused "no Recommended when line" '/^Recommended when:/d'
refused "no Build stack line" '/^Build stack:/d'
refused "no Deploy target line" '/^Deploy target:/d'
refused "no Command-line tools line" '/^Command-line tools:/d'
refused "no Last checked line" '/^Last checked:/d'
refused "a Last checked line that is not a date" 's/^Last checked: .*/Last checked: recently/'
refused "a Last checked date in the future" 's/^Last checked: .*/Last checked: 2999-01-01/'
refused "a Last checked date in month nineteen" 's/^Last checked: .*/Last checked: 2025-19-01/'
refused "a Last checked date on day thirty-two" 's/^Last checked: .*/Last checked: 2025-01-32/'
refused "a Last checked date on the thirtieth of February" 's/^Last checked: .*/Last checked: 2025-02-30/'
refused "a leap day in a year without one" 's/^Last checked: .*/Last checked: 2025-02-29/'
refused "no Real run line" '/^Real run:/d'
refused "a Real run line with no date" 's/^Real run: .*/Real run: soon/'
refused "no outcome line for one section" '/^Logs: /d'
refused "an empty outcome line" 's/^Rollback: .*/Rollback: /'
refused "one section that does not say how it works" '/^## Backup$/,/^## /{/^How it works:/d;}'
refused "one section that does not say how it is checked" '/^## Health$/,/^## /{/^How it is checked:/d;}'
refused "one section that does not say who runs it" '/^## Secrets$/,/^## /{/^Who runs it:/d;}'
refused "a Who runs it value outside the three" '/^## Preview$/,/^## /s/^Who runs it: .*/Who runs it: the service/'
refused "two sections out of order" 's/^## Backup$/## TEMP/; s/^## Restore$/## Backup/; s/^## TEMP$/## Restore/'

# The optional Plan terms line. Terms change without notice, so a line that
# does not say when and where it was read cannot be told from a current one.
TERMS="$rs_dir/terms.md"
sed '/^Last checked:/a\
Plan terms: The free plan is for personal use only, so a work team needs the paid plan (read 2024-03-01 at https://example.com/terms)
' "$FILLED" > "$TERMS"
grep -q '^Plan terms:' "$TERMS" || rs_fail "the Plan terms line was not added, so the next checks prove nothing"
"$CHECKER" "$TERMS" >/dev/null
rs_ok "a recipe with a dated Plan terms line passes"
terms_refused() {
  sed -e "$2" "$TERMS" > "$rs_dir/terms-mutant.md"
  if cmp -s "$TERMS" "$rs_dir/terms-mutant.md"; then
    rs_fail "the edit for '$1' changed nothing, so it proves nothing"
  fi
  if "$CHECKER" "$rs_dir/terms-mutant.md" >/dev/null; then
    rs_fail "a recipe with $1 passed"
  fi
  rs_ok "a recipe with $1 is refused"
}
terms_refused "a Plan terms line with no date" 's/ (read 2024-03-01 at https:\/\/example.com\/terms)$//'
terms_refused "a Plan terms line with no source page" 's/ at https:\/\/example.com\/terms)$/)/'
terms_refused "a Plan terms date in the future" 's/(read 2024-03-01/(read 2999-03-01/'
terms_refused "a Plan terms date that is not real" 's/(read 2024-03-01/(read 2025-02-29/'
terms_refused "a Plan terms line with no sentence" 's/^Plan terms: .* (read/Plan terms: (read/'

# --- shared parts ----------------------------------------------------------
mkdir -p "$rs_dir/parts"
printf '%s\n' 'How it works: filled in' 'How it is checked: filled in' 'Who runs it: the kit' \
  > "$rs_dir/parts/whole.md"
cp "$rs_dir/parts/whole.md" "$rs_dir/parts/shared.md"
# The backup section's own lines go, and a link to the part takes their place.
awk '
  /^## / { inbackup = ($0 == "## Backup") }
  inbackup && /^(How it|Who runs it)/ { next }
  { print }
  $0 == "## Backup" { print ""; print "Shared part: [shared](parts/shared.md)" }
' "$FILLED" > "$rs_dir/linked.md"

"$CHECKER" --part "$rs_dir/parts/shared.md" >/dev/null
rs_ok "a shared part with the three lines passes"
"$CHECKER" "$rs_dir/linked.md" >/dev/null
rs_ok "a recipe that links a shared part in place of a section passes"

sed 's#parts/shared.md#parts/missing.md#' "$rs_dir/linked.md" > "$rs_dir/mutant.md"
if "$CHECKER" "$rs_dir/mutant.md" >/dev/null; then
  rs_fail "a recipe linking a part that does not exist passed"
fi
rs_ok "a recipe linking a part that does not exist is refused"

sed '/^Who runs it:/d' "$rs_dir/parts/whole.md" > "$rs_dir/parts/shared.md"
if "$CHECKER" --part "$rs_dir/parts/shared.md" >/dev/null; then
  rs_fail "a shared part with no Who runs it line passed"
fi
if "$CHECKER" "$rs_dir/linked.md" >/dev/null; then
  rs_fail "a recipe linking a part with no Who runs it line passed"
fi
rs_ok "a shared part missing a line is refused, on its own and through the recipe"

sed 's/^Who runs it: .*/Who runs it: nobody/' "$rs_dir/parts/whole.md" > "$rs_dir/parts/shared.md"
if "$CHECKER" "$rs_dir/linked.md" >/dev/null; then
  rs_fail "a recipe linking a part with a Who runs it value outside the three passed"
fi
rs_ok "a shared part with a Who runs it value outside the three is refused"

# --- the settings section --------------------------------------------------
# The one section a recipe may add. It sits between health and the proven
# section and carries the lines the others do, so a read the launch review
# relies on is never a bare claim.
cp "$rs_dir/parts/whole.md" "$rs_dir/parts/shared.md"
awk '
  $0 == "## Proven" { print "## Settings the kit can read"; print ""; print "Shared part: [shared](parts/shared.md)"; print "" }
  { print }
  END { print "Settings the kit can read: filled in" }
' "$FILLED" > "$rs_dir/settings.md"
"$CHECKER" "$rs_dir/settings.md" >/dev/null
rs_ok "a recipe with a settings section after health, and its outcome line, passes"

sed '/^Settings the kit can read: /d' "$rs_dir/settings.md" > "$rs_dir/mutant.md"
if "$CHECKER" "$rs_dir/mutant.md" >/dev/null; then
  rs_fail "a settings section with no outcome line in the proven section passed"
fi
rs_ok "a settings section with no outcome line in the proven section is refused"

sed '/^Who runs it:/d' "$rs_dir/parts/whole.md" > "$rs_dir/parts/shared.md"
if "$CHECKER" "$rs_dir/settings.md" >/dev/null; then
  rs_fail "a settings section whose part has no Who runs it line passed"
fi
rs_ok "a settings section missing a line is refused"
cp "$rs_dir/parts/whole.md" "$rs_dir/parts/shared.md"

awk '
  $0 == "## Health" { print "## Settings the kit can read"; print ""; print "Shared part: [shared](parts/shared.md)"; print "" }
  { print }
' "$FILLED" > "$rs_dir/mutant.md"
if "$CHECKER" "$rs_dir/mutant.md" >/dev/null; then
  rs_fail "a settings section before health passed"
fi
rs_ok "a settings section out of place is refused"

# --- the rehearsal a recipe needs ----------------------------------------
mkdir -p "$rs_dir/recipes"
RECIPE="$rs_dir/recipes/example-pair.md"
cp "$FILLED" "$RECIPE"

printf '%s\n' '#!/usr/bin/env sh' 'exit 0' > "$rs_dir/empty.sh"
if "$CHECKER" --rehearsal "$RECIPE" "$rs_dir/empty.sh" >/dev/null; then
  rs_fail "a rehearsal that only exits cleanly counted"
fi
rs_ok "a rehearsal that only exits cleanly is refused"

printf '%s\n' '#!/usr/bin/env sh' '. "$ROOT/tests/lib/rule-shape.sh"' > "$rs_dir/unnamed.sh"
if "$CHECKER" --rehearsal "$RECIPE" "$rs_dir/unnamed.sh" >/dev/null; then
  rs_fail "a rehearsal that never names its recipe counted"
fi
rs_ok "a rehearsal that never names its recipe is refused"

printf '%s\n' '#!/usr/bin/env sh' 'RECIPE=ship/recipes/example-pair.md' > "$rs_dir/unhelped.sh"
if "$CHECKER" --rehearsal "$RECIPE" "$rs_dir/unhelped.sh" >/dev/null; then
  rs_fail "a rehearsal that does not source the rule-shape helper counted"
fi
rs_ok "a rehearsal that does not source the rule-shape helper is refused"

if "$CHECKER" --rehearsal "$RECIPE" "$rs_dir/absent.sh" >/dev/null; then
  rs_fail "a recipe with no rehearsal at all passed"
fi
rs_ok "a recipe with no rehearsal at all is refused"

printf '%s\n' '#!/usr/bin/env sh' '. "$ROOT/tests/lib/rule-shape.sh"' \
  'RECIPE=ship/recipes/example-pair.md' > "$rs_dir/real.sh"
"$CHECKER" --rehearsal "$RECIPE" "$rs_dir/real.sh" >/dev/null
rs_ok "a rehearsal that sources the helper and names its recipe counts"

# --- every recipe, part and the blank, as the old validator checked them --
# Nothing else runs this loop once the old validator is gone.
# An empty kit/recipes would let the loop below pass with nothing to check, so
# count the recipes first. The plan ships two, but one is enough to be a menu.
set -- "$ROOT"/kit/recipes/*.md
if [ ! -f "$1" ]; then
  rs_fail "kit/recipes holds no recipe, so the loop over the recipes would check nothing"
fi
rs_ok "kit/recipes holds $# recipe(s)"
for recipe in "$ROOT"/kit/recipes/*.md; do
  [ -f "$recipe" ] || continue
  name=$(basename "$recipe" .md)
  "$CHECKER" "$recipe" >/dev/null || rs_fail "$name does not have the shape the format asks for"
  rs_ok "$name has the shape the format asks for"
  "$CHECKER" --rehearsal "$recipe" "$ROOT/tests/recipe-$name.sh" >/dev/null ||
    rs_fail "$name has no rehearsal in tests/recipe-$name.sh that guards it"
  rs_ok "$name has a rehearsal that guards it"
done
for part in "$ROOT"/kit/recipes/parts/*.md; do
  [ -f "$part" ] || continue
  "$CHECKER" --part "$part" >/dev/null ||
    rs_fail "$(basename "$part") does not carry the lines a section needs"
  rs_ok "the part $(basename "$part") carries the lines a section needs"
done
"$CHECKER" --template "$BLANK" >/dev/null || rs_fail "the blank does not have the shape the format asks for"
rs_ok "the blank in kit/templates has the shape the format asks for"

rs_done
