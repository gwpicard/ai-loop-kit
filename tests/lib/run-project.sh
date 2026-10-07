# run-project.sh: build a throwaway project with a ready piece for each entry of $PIECES.
# Source it after setting ROOT, RP_NAME and PIECES ("name:file:area ..."), and after defining
# fail() and ok(). It sets KIT, GATE, RUN, FAKE and TP_*; tests/run-loop.sh has the same steps
# written out, which this file copies so that the run tests of the watch and the mailbox need no
# second set of them. make_piece <name> <file> <area> [issue] prints the piece number. A test
# that wants a question in the spec sets SPEC_QUESTION before it calls make_piece.

tp_new "${RP_NAME:-run-demo}"
FAKE_COMPUTER="$ROOT/tests/stand-ins/fake-computer"
mkdir -p "$TP_BASE/tmp"
TMPDIR="$TP_BASE/tmp"
PATH="$TP_BIN:$FAKE_COMPUTER:$PATH"
export PATH TMPDIR
unset FAKE_COMPUTER_POWER FAKE_COMPUTER_SLEEP FAKE_COMPUTER_FREE_MB FAKE_COMPUTER_DISK_GB \
  FAKE_CLAUDE_VERSION

# --- the kit, as installed, and every guard the pre-run check wants -------------------------
KIT="$TP_BASE/plugin"
cp -R "$ROOT/kit" "$KIT"
CLAUDE_PLUGIN_ROOT="$KIT"
PYTHONPATH="$KIT/scripts"
export CLAUDE_PLUGIN_ROOT PYTHONPATH
GATE="$KIT/scripts/gate.py"
RUN="$KIT/scripts/run.py"
python3 - "$ROOT/kit/scripts/pre-run-check.py" "$KIT" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("pre_run_check", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["pre_run_check"] = module
spec.loader.exec_module(module)
module.write_record(Path(sys.argv[2]))
PY
python3 "$KIT/scripts/merge-settings.py" "$KIT/templates/claude-settings.json" \
  "$TP_ROOT/.claude/settings.json" --set "KIT_DIR=$KIT" >/dev/null 2>&1 \
  || fail "the settings could not be merged"
mkdir -p "$TP_ROOT/.githooks" "$TP_ROOT/.agents/loop"
sed "s#{{KIT_DIR}}#$KIT#g" "$KIT/templates/githooks/pre-push" > "$TP_ROOT/.githooks/pre-push"
chmod +x "$TP_ROOT/.githooks/pre-push"
git -C "$TP_ROOT" config core.hooksPath .githooks
cp "$KIT/templates/policy.json" "$TP_ROOT/.agents/loop/policy.json"
python3 - "$TP_ROOT/.agents/loop/policy.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["test_command"] = "python3 -m pytest tests/test_old.py -q"
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
printf '{"language": "python", "allowedDomains": ["pypi.org", "files.pythonhosted.org", "registry.allowlist-probe.test"]}\n' \
  > "$TP_ROOT/.agents/loop/network-allowlist.json"

# --- the project: a stub and an acceptance test for each piece ------------------------------
cd "$TP_ROOT"
mkdir -p tests/acceptance docs
cat > tests/test_old.py <<'PY'
def test_old_behaviour_holds():
    assert 1 + 1 == 2
PY
: > "$TP_BASE/area-map"
echo "tests/test_old.py records" >> "$TP_BASE/area-map"
echo "docs/ records" >> "$TP_BASE/area-map"
# $PIECES (set by the test) is a list of name:file:area.
for item in $PIECES; do
  name=${item%%:*}; rest=${item#*:}; file=${rest%%:*}; area=${rest#*:}
  printf 'def %s():\n    return None\n' "$name" > "$file"
  echo "/$file $area" >> "$TP_BASE/area-map"
  echo "tests/acceptance/test_$name.py $area" >> "$TP_BASE/area-map"
done
cp "$TP_BASE/area-map" docs/area-map
# The records the integration loop's docs commit keeps right (the run joins what it builds).
mkdir -p .agents/guard .github/workflows
cp "$KIT/templates/blocked-commands.md" .agents/guard/blocked-commands.md
cp "$KIT/templates/AGENTS.md" AGENTS.md
cp "$KIT/templates/CLAUDE.md" CLAUDE.md
cp "$KIT/templates/CHANGELOG.md" CHANGELOG.md
cp "$KIT/templates/docs-README.md" docs/README.md
sed 's/{{KIT_REF}}/main/' "$KIT/templates/checks.yml" > .github/workflows/checks.yml
python3 - "$KIT/templates/overview.md" docs/area-map <<'PY'
import sys

text = open(sys.argv[1]).read().split("| project-records")[0].rstrip("\n")
names = []
for line in open(sys.argv[2]):
    parts = line.split()
    if len(parts) == 2 and not line.startswith("#") and parts[1] not in names:
        names.append(parts[1])
for area in names:
    doc = "docs/README.md" if area == "records" else f"docs/{area}.md"
    text += f"\n| {area} | The {area} area | no | | `{doc}` |"
    if area != "records":
        open(doc, "w").write(f"# {area}\n\n")
open("docs/overview.md", "w").write(text + "\n")
PY
git add -A
git commit -q -m "Add the stubs, an old test and the area map"
git push -q origin main

cat > "$TP_BASE/make-spec.py" <<'PY'
import sys

title, area, source = sys.argv[1:4]
print(title + ".\n")
print("<!-- spec:start version=1 -->")
print("Path: quick\n")
print("## Goal\nThe " + title.lower() + " works, and the edge case is handled.\n")
print("## Expected flow\nFL-1 The user uses the " + title.lower() + " and sees it work.\n")
print("## Edge cases\nEC-1 When the input is empty, then the " + title.lower() + " says so.\n")
print("## Must stay the same\nThe old behaviour still holds.\n"
      "Check: python3 -m pytest tests/test_old.py\n")
held = sys.argv[5] if len(sys.argv) > 5 else ""
line = "Held-out cases: fingerprint " + held + "\n" if held else ""
print("## Judge\nKind: acceptance tests, a single test\n"
      "Command: python3 -m pytest tests/acceptance/test_" + sys.argv[4] + ".py\n"
      "Proves: FL-1, EC-1\n" + line)
print("## Links\nRelies on: " + source + "\nTouches: " + area + "\n")
print("## Decisions\n- must-look: the person wants to read this piece.")
import os
if os.environ.get("SPEC_QUESTION"):
    print("\n## Open questions\n- " + os.environ["SPEC_QUESTION"] + " Why it matters: the "
          "piece depends on it. Recommended: blue. Who: the person.")
print("<!-- spec:end -->")
PY

# make_piece <name> <file> <area> [issue]: capture, branch, commit the judge, and make it ready.
make_piece() {
  name=$1 file=$2 area=$3
  python3 "$TP_BASE/make-spec.py" "Run $name" "$area" "$file" "$name" > "$TP_BASE/spec-$name.md"
  if [ "${4:-}" = issue ]; then
    url=$(gh issue create --title "Run $name" --body "$(cat "$TP_BASE/spec-$name.md")")
    n=${url##*/}
    python3 "$GATE" capture "$n" --json > "$TP_BASE/capture-$name.json" \
      || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  else
    python3 "$GATE" capture --title "Run $name" --body-file "$TP_BASE/spec-$name.md" \
      --type feature --json > "$TP_BASE/capture-$name.json" \
      || fail "capture of $name failed: $(cat "$TP_BASE/capture-$name.json")"
  fi
  number=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["piece"])' \
    "$TP_BASE/capture-$name.json")
  python3 "$GATE" branch "$number" --json >/dev/null || fail "gate.py branch $number failed"
  git checkout -q "piece-$number"
  mkdir -p tests/acceptance
  cat > "tests/acceptance/test_$name.py" <<PY
from $(printf '%s' "${file%.py}") import $name


def test_${name}_works_and_handles_the_edge():
    assert $name() == "$name ok", "FL-1 the $name works; EC-1 the empty input is handled"
PY
  git add "tests/acceptance/test_$name.py"
  git commit -q -m "Add the acceptance test of $name"
  git checkout -q main
  # The hidden cases, outside git, and the fingerprint the spec then names.
  for id in FL-1 EC-1; do
    cat > "$TP_BASE/case-$name-$id.txt" <<PY
# held-out-path: tests/held_out/test_hidden_${name}_$(printf '%s' "$id" | tr -d '-').py
from $(printf '%s' "${file%.py}") import $name


def test_hidden_${name}_$(printf '%s' "$id" | tr -d '-')():
    assert $name() == "$name ok"
PY
  done
  python3 -m loop.heldout store --piece "$number" --case "FL-1=$TP_BASE/case-$name-FL-1.txt" \
    --case "EC-1=$TP_BASE/case-$name-EC-1.txt" --json > "$TP_BASE/held-$name.json" \
    || fail "the held-out store refused the cases of $name: $(cat "$TP_BASE/held-$name.json")"
  print_=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["fingerprint"])' \
    "$TP_BASE/held-$name.json")
  python3 "$TP_BASE/make-spec.py" "Run $name" "$area" "$file" "$name" "$print_" \
    > "$TP_BASE/spec2-$name.md"
  python3 "$GATE" spec "$number" --body-file "$TP_BASE/spec2-$name.md" --json >/dev/null \
    || fail "gate.py spec failed for $name"
  tp_claude_script "$(python3 - "$KIT" <<'PY'
import json, sys
summary = "FL-1: test_works\nEC-1: test_edge"
print(json.dumps({"runs": [["python3", sys.argv[1] + "/scripts/handoff.py", "done",
                            "--summary", summary]]}))
PY
)"
  python3 "$GATE" move "$number" ready --json > "$TP_BASE/ready-$name.json" \
    2> "$TP_BASE/ready-$name.err" \
    || fail "move 2 was refused for $name: $(cat "$TP_BASE/ready-$name.err")"
  echo "$number"
}


state_of() {
  python3 "$GATE" report "$1" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["pieces"][0]["state"])'
}
