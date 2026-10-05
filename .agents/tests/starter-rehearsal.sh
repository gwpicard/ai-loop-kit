#!/usr/bin/env sh
# starter-rehearsal.sh: prove that a released starter can become a clean,
# independently saved project with the founding record templates in place.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILDER="$ROOT/.agents/tools/build-release.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -x "$BUILDER" ] || fail "release builder is missing or not executable"

SCRATCH=$(mktemp -d)
PACK="$SCRATCH/pack"
PROJECT="$SCRATCH/project"
PLUGIN_PROJECT="$SCRATCH/plugin-project"
cleanup() {
  rm -R "$SCRATCH"
}
trap cleanup EXIT

"$BUILDER" v0.1.0 "$PACK" >/dev/null

# Rehearse the Claude plugin boundary: Claude runs the same canonical start
# skill from its plugin cache while the project owns only its foundation.
mkdir -p "$PLUGIN_PROJECT"
PLUGIN_BOOTSTRAP="$PACK/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
"$PLUGIN_BOOTSTRAP" "$PLUGIN_PROJECT" >/dev/null || \
  fail "Claude plugin setup-ai-build-kit skill could not prepare a blank project"
[ -f "$PLUGIN_PROJECT/AGENTS.md" ] || \
  fail "Claude plugin setup-ai-build-kit skill did not prepare project instructions"
[ ! -e "$PLUGIN_PROJECT/.agents/skills" ] || \
  fail "Claude plugin bootstrap copied managed skills into the project"

PLUGIN_DUPLICATE="$SCRATCH/plugin-duplicate"
mkdir -p "$PLUGIN_DUPLICATE/.agents"
cp -R "$PACK/.agents/skills" "$PLUGIN_DUPLICATE/.agents/skills"
if "$PLUGIN_BOOTSTRAP" "$PLUGIN_DUPLICATE" >/dev/null 2>&1; then
  fail "Claude plugin bootstrap accepted a second AI Build Kit installation"
fi
[ ! -e "$PLUGIN_DUPLICATE/AGENTS.md" ] || \
  fail "Claude plugin bootstrap wrote project files before reporting the duplicate installation"

# Rehearse the shared skills installer boundary: only skill folders arrive in
# the project. The installed setup-ai-build-kit skill then prepares the project-owned
# foundation without needing the rest of the release repository.
mkdir -p "$PROJECT/.agents"
cp -R "$PACK/.agents/skills" "$PROJECT/.agents/skills"
BOOTSTRAP="$PROJECT/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
[ -x "$BOOTSTRAP" ] || fail "installed setup-ai-build-kit skill has no executable project bootstrap"
(cd "$PROJECT" && "$BOOTSTRAP" >/dev/null) || \
  fail "installed setup-ai-build-kit skill could not prepare a blank project"
[ -x "$PROJECT/.agents/hooks/session-start.sh" ] || \
  fail "installed setup-ai-build-kit skill did not prepare an executable session hook"
[ -x "$PROJECT/.agents/tools/area-map.py" ] || \
  fail "installed setup-ai-build-kit skill did not place the area map script at .agents/tools/area-map.py"
grep -qx '## Areas' "$PROJECT/docs/working-rules.md" 2>/dev/null || \
  fail "installed setup-ai-build-kit skill did not write docs/working-rules.md with an Areas section"

for record in masterplan.md CHANGELOG.md .ai-build-kit-maintenance; do
  [ ! -e "$PROJECT/$record" ] || \
    fail "starter unexpectedly contains founding record $record"
done

for maintainer_only in starter release-manifest.txt docs/MAINTAINING.md \
  .agents/tests .agents/maintainer-skills; do
  [ ! -e "$PROJECT/$maintainer_only" ] || \
    fail "starter contains maintainer-only $maintainer_only"
done

skill_count=$(find "$PROJECT/.agents/skills" -mindepth 2 -maxdepth 2 \
  -name SKILL.md | wc -l | tr -d ' ')
[ "$skill_count" -eq 13 ] || fail "installed project does not contain thirteen skills"

grep -qF '(Project name, written by start)' "$PROJECT/README.md" || \
  fail "project foundation README is not ready for start"
grep -qF '(One line, written by the setup-ai-build-kit skill.)' "$PROJECT/AGENTS.md" || \
  fail "starter instructions are not ready for the founding workflow"
grep -qF '.claude/settings.local.json' "$PROJECT/.gitignore" || \
  fail "project foundation does not keep local Claude plugin state out of Git"

printf '%s\n' "Existing project instructions" > "$PROJECT/AGENTS.md"
(cd "$PROJECT" && "$BOOTSTRAP" >/dev/null) || \
  fail "project bootstrap could not be rerun"
[ "$(cat "$PROJECT/AGENTS.md")" = "Existing project instructions" ] || \
  fail "project bootstrap overwrote existing project instructions"
cp "$PACK/.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md" "$PROJECT/AGENTS.md"

# Rehearse the shared installer with Claude Code chosen alone. It puts every
# skill in .claude/skills and nothing in .agents/skills, and founding has to
# start from there. The copy stands in for the installer, which needs the
# network.
CLAUDE_ONLY="$SCRATCH/claude-only"
mkdir -p "$CLAUDE_ONLY/.claude"
cp -R "$PACK/.agents/skills" "$CLAUDE_ONLY/.claude/skills"
CLAUDE_ONLY_BOOTSTRAP="$CLAUDE_ONLY/.claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh"
(cd "$CLAUDE_ONLY" && "$CLAUDE_ONLY_BOOTSTRAP" >/dev/null) || \
  fail "a Claude-Code-only shared installation could not prepare a blank project"
[ -f "$CLAUDE_ONLY/AGENTS.md" ] || \
  fail "a Claude-Code-only shared installation did not prepare project instructions"
[ -x "$CLAUDE_ONLY/.agents/hooks/session-start.sh" ] || \
  fail "a Claude-Code-only shared installation did not prepare the session hook"
[ ! -e "$CLAUDE_ONLY/.agents/skills" ] || \
  fail "the bootstrap created .agents/skills for a Claude-Code-only installation"

# Several coding agents: the real folder sits in .agents/skills and Claude
# Code reaches it through a link in .claude/skills. Founding started from the
# link is the same installation.
LINKED="$SCRATCH/linked"
mkdir -p "$LINKED/.agents" "$LINKED/.claude/skills"
cp -R "$PACK/.agents/skills" "$LINKED/.agents/skills"
for skill in "$LINKED/.agents/skills"/*; do
  ln -s "../../.agents/skills/$(basename "$skill")" \
    "$LINKED/.claude/skills/$(basename "$skill")"
done
(cd "$LINKED" && .claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh \
  >/dev/null) || \
  fail "founding from a linked .claude/skills folder was refused"

# The installer's copy option writes a second real copy in place of the link.
# Both copies belong to the one installation, so either may start founding.
COPIED="$SCRATCH/copied"
mkdir -p "$COPIED/.agents" "$COPIED/.claude"
cp -R "$PACK/.agents/skills" "$COPIED/.agents/skills"
cp -R "$PACK/.agents/skills" "$COPIED/.claude/skills"
(cd "$COPIED" && .claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh \
  >/dev/null) || \
  fail "founding from one of two copies of the same installation was refused"

# The guard still holds for the new folder. Another installation's skill must
# not prepare a project whose skills sit in .claude/skills, and a plugin beside
# a Claude-Code-only installation is still two installations.
FOREIGN="$SCRATCH/foreign"
mkdir -p "$FOREIGN/.claude"
cp -R "$PACK/.agents/skills" "$FOREIGN/.claude/skills"
if "$CLAUDE_ONLY_BOOTSTRAP" "$FOREIGN" >/dev/null 2>&1; then
  fail "the bootstrap accepted a project that belongs to another installation"
fi
[ ! -e "$FOREIGN/AGENTS.md" ] || \
  fail "the bootstrap wrote project files for another installation"
if "$PLUGIN_BOOTSTRAP" "$FOREIGN" >/dev/null 2>&1; then
  fail "Claude plugin bootstrap accepted a Claude-Code-only installation beside it"
fi
[ ! -e "$FOREIGN/AGENTS.md" ] || \
  fail "Claude plugin bootstrap wrote project files beside a Claude-Code-only installation"

# A second copy that differs from the running one means another coding agent
# reads a different version of the kit. The running skill is whole, so founding
# carries on, and the bootstrap says so once, naming the folder. A copy that
# differs only in a reference file counts, since the whole folder is compared.
MIXED="$SCRATCH/mixed"
mkdir -p "$MIXED/.agents" "$MIXED/.claude"
cp -R "$PACK/.agents/skills" "$MIXED/.agents/skills"
cp -R "$PACK/.agents/skills" "$MIXED/.claude/skills"
printf '%s\n' "An older release." >> \
  "$MIXED/.agents/skills/setup-ai-build-kit/references/pieces.md"
said=$(cd "$MIXED" && \
  .claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh 2>&1 >/dev/null) || \
  fail "the bootstrap stopped founding over a second copy that differs"
[ -f "$MIXED/AGENTS.md" ] || \
  fail "the bootstrap did not prepare the project beside a differing copy"
case "$said" in
  *".agents/skills/setup-ai-build-kit differs"*/maintain*) ;;
  *) fail "the note about a differing copy does not name the folder and /maintain: $said" ;;
esac
[ "$(printf '%s\n' "$said" | grep -c 'differs')" -eq 1 ] || \
  fail "the note about a differing copy was not said exactly once: $said"

# A matching copy says nothing.
said=$(cd "$COPIED" && \
  .claude/skills/setup-ai-build-kit/scripts/bootstrap-project.sh 2>&1 >/dev/null)
[ -z "$said" ] || fail "a matching second copy produced a note: $said"

# An empty folder in the other skill folder is a note, and founding carries on.
EMPTY="$SCRATCH/empty-entry"
mkdir -p "$EMPTY/.agents" "$EMPTY/.claude/skills/setup-ai-build-kit"
cp -R "$PACK/.agents/skills" "$EMPTY/.agents/skills"
said=$(cd "$EMPTY" && \
  .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh 2>&1 >/dev/null) || \
  fail "the bootstrap stopped founding over an empty skill folder"
[ -f "$EMPTY/AGENTS.md" ] || fail "the bootstrap did not prepare the project beside an empty folder"
case "$said" in
  *".claude/skills/setup-ai-build-kit is an empty folder"*) ;;
  *) fail "the note about an empty folder does not name it: $said" ;;
esac

# A link that leads nowhere and a link loop cannot be read at all. Each is
# refused by name before anything is written, never passed over.
refuses_broken_entry() {
  label=$1
  project="$SCRATCH/broken-$2"
  mkdir -p "$project/.agents" "$project/.claude/skills"
  cp -R "$PACK/.agents/skills" "$project/.agents/skills"
  entry="$project/.claude/skills/setup-ai-build-kit"
  case "$2" in
    dangling) ln -s "$project/nowhere" "$entry" ;;
    loop) ln -s "$entry" "$entry" ;;
  esac
  said=$(cd "$project" && \
    .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh 2>&1 >/dev/null) && \
    fail "the bootstrap accepted $label"
  case "$said" in
    *".claude/skills/setup-ai-build-kit is a broken link"*) ;;
    *) fail "the refusal of $label does not name the folder: $said" ;;
  esac
  [ ! -e "$project/AGENTS.md" ] || fail "the bootstrap wrote project files beside $label"
}
refuses_broken_entry "a link that leads nowhere" dangling
refuses_broken_entry "a link loop" loop

REDIRECTED="$SCRATCH/redirected"
OUTSIDE="$SCRATCH/outside"
mkdir -p "$REDIRECTED/.agents" "$OUTSIDE"
cp -R "$PACK/.agents/skills" "$REDIRECTED/.agents/skills"
ln -s "$OUTSIDE" "$REDIRECTED/.github"
if (cd "$REDIRECTED" && \
  .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh >/dev/null 2>&1); then
  fail "project bootstrap accepted a redirected foundation folder"
fi
[ ! -e "$REDIRECTED/AGENTS.md" ] || \
  fail "project bootstrap wrote partial foundation before rejecting a redirect"
[ ! -e "$OUTSIDE/copilot-instructions.md" ] || \
  fail "project bootstrap wrote outside the project"

BROAD="$SCRATCH/broad"
mkdir -p "$BROAD/.agents"
cp -R "$PACK/.agents/skills" "$BROAD/.agents/skills"
if "$BROAD/.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh" "$SCRATCH" \
  >/dev/null 2>&1; then
  fail "project bootstrap accepted a parent workspace"
fi
[ ! -e "$SCRATCH/AGENTS.md" ] || \
  fail "project bootstrap wrote foundation files into a parent workspace"

git -C "$PROJECT" init -q
git -C "$PROJECT" config user.name "AI Build Kit rehearsal"
git -C "$PROJECT" config user.email "rehearsal@example.invalid"
git -C "$PROJECT" config commit.gpgsign false
git -C "$PROJECT" add .
git -C "$PROJECT" commit -q -m "Start from AI Build Kit"

for record in masterplan.md CHANGELOG.md; do
  cp "$PROJECT/.agents/skills/setup-ai-build-kit/templates/$record" "$PROJECT/$record"
done

git -C "$PROJECT" add masterplan.md CHANGELOG.md
git -C "$PROJECT" commit -q -m "Create founding project records"

[ "$(git -C "$PROJECT" rev-list --count HEAD)" -eq 2 ] || \
  fail "disposable project did not save both expected checkpoints"
[ -z "$(git -C "$PROJECT" status --short)" ] || \
  fail "disposable project is not clean after its founding records were saved"

# The area map founding writes passes the check, and a folder the stand-up makes
# is named until founding claims it. A folder counts once Git's index holds a
# file in it, so the file is added before the check runs, as founding adds the
# files its checkpoint will save.
area_check() {
  (cd "$1" && python3 .agents/tools/area-map.py check 2>&1)
}
said=$(area_check "$PROJECT") || \
  fail "the area map founding wrote does not pass its check: $said"
mkdir -p "$PROJECT/app"
printf '%s\n' 'export const page = 1;' > "$PROJECT/app/page.ts"
git -C "$PROJECT" add app/page.ts
said=$(area_check "$PROJECT") && fail "the check passed with app/ claimed by no area"
case "$said" in
  *"app is a folder no area claims"*) ;;
  *) fail "the check did not name the unclaimed app folder: $said" ;;
esac
printf '%s\n' '- app: app/' >> "$PROJECT/docs/working-rules.md"
said=$(area_check "$PROJECT") || fail "the check stayed red once founding claimed app/: $said"
git -C "$PROJECT" add docs/working-rules.md
git -C "$PROJECT" commit -q -m "Claim the folder the stand-up made"

# A whole copy of the kit founded in place carries docs/ and agent-plugin/.
# Founding adds the area line its skill gives for agent-plugin/, and the
# template already claims docs/.
WHOLE="$SCRATCH/whole"
cp -R "$PACK" "$WHOLE"
git -C "$WHOLE" init -q
git -C "$WHOLE" add -A
(cd "$WHOLE" && .agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh >/dev/null) || \
  fail "a whole copy of the kit could not prepare itself in place"
kit_line=$(grep -o '`- kit installation: agent-plugin/`' \
  "$WHOLE/.agents/skills/setup-ai-build-kit/SKILL.md" | head -n 1 | tr -d '`')
[ -n "$kit_line" ] || fail "the setup skill gives no area line for agent-plugin/ in a whole copy"
printf '%s\n' "$kit_line" >> "$WHOLE/docs/working-rules.md"
git -C "$WHOLE" add -A
said=$(area_check "$WHOLE") || fail "a whole copy founded in place fails the area check: $said"
claimed=$(cd "$WHOLE" && python3 .agents/tools/area-map.py which docs agent-plugin)
[ "$claimed" = "$(printf 'docs\tproject records\nagent-plugin\tkit installation')" ] || \
  fail "a whole copy does not claim docs/ and agent-plugin/: $claimed"

# Founding opens the pieces as issues. It replays here the commands the installed
# setup skill names in its step for cutting the plan, against the replay
# harness's stand-in GitHub, so a step dropped from the skill or a command the
# gate would refuse fails here rather than in somebody's first project. Each
# piece must end with one state, one sub-label where its state has them, and
# one type label, and the gate's own report must find nothing out of order.
python3 - "$PROJECT" "$ROOT/.agents/tests/replay/fake-github" "$SCRATCH" <<'PY' || \
  fail "founding's commands did not leave every piece in one state with one type"
import json
import os
import re
import shlex
import subprocess
import sys

project, fake, scratch = sys.argv[1], sys.argv[2], sys.argv[3]
skill = os.path.join(project, ".agents", "skills", "setup-ai-build-kit", "SKILL.md")
state_file = os.path.join(scratch, "founding-gh.json")
env = dict(os.environ, PATH=fake + os.pathsep + os.environ["PATH"],
           FAKE_GH_STATE=state_file, FAKE_GH_LOG=os.path.join(scratch, "founding-gh.log"))
problems = []


def stop(message):
    print("FAIL: " + message, file=sys.stderr)
    sys.exit(1)


# The commands in the code blocks of the step that cuts the plan.
text = open(skill, encoding="utf-8").read()
step = re.search(r"^## 10\. Cut the plan\n(.*?)^## ", text, re.S | re.M)
if not step:
    stop("the setup skill has no step headed '## 10. Cut the plan'")
commands = [line.strip() for block in re.findall(r"```[a-z]*\n(.*?)```", step.group(1), re.S)
            for line in block.splitlines() if line.strip()]


def template(needle, what):
    found = [c for c in commands if needle in c]
    if not found:
        stop("the setup skill's plan step names no command for %s (looked for %r)"
             % (what, needle))
    return found[0]


LABELS = template("gate.py labels", "creating the labels")
DELETE = template("gh label delete", "deleting GitHub's own labels")
CAPTURE = template("gate.py capture --title", "opening a piece through the gate")
TYPE = template('--add-label "type:', "the piece's one type label")
SUBJECT = template('--add-label "<subject>"', "the piece's subject labels")
MOVE = template("gate.py move <number>", "moving a piece through the gate")


def run(command, **values):
    for key, value in values.items():
        command = command.replace("<%s>" % key, value)
    if re.search(r"<[a-z|' -]+>", command):
        stop("a placeholder was left unfilled in %r" % command)
    done = subprocess.run(shlex.split(command), cwd=project, env=env,
                          capture_output=True, text=True)
    if done.returncode != 0:
        stop("%r failed: %s%s" % (command, done.stdout, done.stderr))
    return done.stdout


run(LABELS)
for name in ("bug", "documentation", "duplicate", "enhancement", "good first issue",
             "help wanted", "invalid", "question", "wontfix"):
    run(DELETE, label=name)

# Three pieces, each left where founding leaves one: one still holding a
# question for /shape, and two shaped as far as `shaping:spec`. Founding takes
# no piece further, because writing the acceptance checks pushes a branch and
# founding uploads no code, and the move to ready asks the ready-gate lint for
# a whole contract that only /shape writes.
SHAPED = ("## So that\nGuests can book a night.\n\n## Done when\n### Works\n"
          "- A booking is saved. Check: a test.\n")
pieces = [
    ("Guests can see free nights", "## So that\nGuests see what is free.\n\n"
     "## Open question\nShould a half-booked night show as free?\n", "feature", "visual",
     ["clarify"]),
    ("Guests can book a night", SHAPED, "feature", "data", ["spec"]),
    ("Double bookings stop", SHAPED.replace("book a night", "never double book"), "bug",
     "how it works", ["spec"]),
]
numbers = []
for title, words, kind, subject, moves in pieces:
    path = os.path.join(scratch, "words-%d.md" % len(numbers))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(words)
    said = run(CAPTURE, title=title, file=path)
    match = re.search(r"#(\d+) captured", said)
    if not match:
        stop("capture did not name the issue it opened: %r" % said)
    number = match.group(1)
    numbers.append(int(number))
    run(TYPE.replace("<feature|bug|chore>", kind), number=number)
    run(SUBJECT, number=number, subject=subject)
    for target in moves:
        run(MOVE, number=number, target=target)

shaped, also_shaped = numbers[1], numbers[2]

data = json.load(open(state_file))
left = [l["name"] for l in data.get("labels", [])]
if any(n in left for n in ("bug", "enhancement", "wontfix")):
    problems.append("GitHub's own labels are still there: %s" % ", ".join(left))
expected = {numbers[0]: ("state:shaping", "shaping:clarify"),
            shaped: ("state:shaping", "shaping:spec"),
            also_shaped: ("state:shaping", "shaping:spec")}
for item in data["issues"]:
    names = item["labels"]
    states = [n for n in names if n.startswith("state:")]
    subs = [n for n in names if n.startswith("shaping:")]
    reviews = [n for n in names if n.startswith("review:")]
    types = [n for n in names if n.startswith("type:")]
    want_state, want_sub = expected[item["number"]]
    if states != [want_state]:
        problems.append("#%d carries %s, expected %s" % (item["number"], states, want_state))
    if subs != ([want_sub] if want_sub else []) or reviews:
        problems.append("#%d carries sub-labels %s" % (item["number"], subs + reviews))
    if len(types) != 1:
        problems.append("#%d carries %d type labels" % (item["number"], len(types)))

report = subprocess.run(["python3", ".agents/tools/gate.py", "report"], cwd=project, env=env,
                        capture_output=True, text=True)
if report.returncode != 0 or not report.stdout.startswith("report: every open piece"):
    problems.append("the gate's report found something: %s%s" % (report.stdout, report.stderr))

for problem in problems:
    print("FAIL: " + problem, file=sys.stderr)
sys.exit(1 if problems else 0)
PY
[ -z "$(git -C "$PROJECT" status --short)" ] || \
  fail "founding's issue commands left files in the project"

echo "starter-rehearsal.sh: all checks passed"
