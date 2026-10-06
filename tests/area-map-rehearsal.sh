#!/usr/bin/env sh
# area-map-rehearsal.sh: run the area map command, area-map.py, in throwaway Git
# projects and read what it prints.
#
# The map is the file docs/area-map, one `<pattern> <area>` line each, in the
# style of a CODEOWNERS file, last match wins. The command is a thin line over
# kit/scripts/loop/areas.py. Later steps read its JSON: the ready gate takes area
# names from `areas`, and a boundary check takes a path's area from `which`. So
# the output is read as JSON here, and the exit code is read as well. Every red
# case of `check` runs beside a passing control, so a check that went red on
# everything would fail here as surely as one that went red on nothing.
#
# The step in the project check runs the command behind a guard for a runner with
# no Python. That run line is read out of the shipped checks.yml and run as it
# stands, once with Python and once on a PATH without it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCRIPTS="$ROOT/kit/scripts"
SCRIPT="$SCRIPTS/area-map.py"
CHECKS="$ROOT/kit/templates/checks.yml"
TEMPLATE="$ROOT/kit/templates/area-map"

if [ ! -f "$SCRIPT" ]; then
  echo "FAIL: there is no area map script at kit/scripts/area-map.py" >&2
  exit 1
fi

WORK=$(mktemp -d)

PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

python3 - "$SCRIPT" "$CHECKS" "$TEMPLATE" "$WORK" "$SCRIPTS" <<'PY'
import json
import os
import shutil
import subprocess
import sys

SCRIPT, CHECKS, TEMPLATE, WORK, SCRIPTS = sys.argv[1:6]
GIT = shutil.which("git")
GITID = ["-c", "user.name=R", "-c", "user.email=r@example.invalid", "-c", "commit.gpgsign=false"]
failures = []


def expect(condition, message, detail=""):
    if condition:
        print("ok: " + message)
    else:
        failures.append(message)
        print("FAIL: " + message + ((" -- " + detail) if detail else ""), file=sys.stderr)


def git(cwd, *args):
    done = subprocess.run([GIT, "-C", cwd, *GITID, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), done.stderr))
    return done.stdout


def write(folder, files):
    for path, text in files.items():
        full = os.path.join(folder, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)


def run(folder, *args, env=None):
    """Run the command. Returns the exit code, the JSON it printed (or None) and stderr."""
    done = subprocess.run([sys.executable, SCRIPT, *args], cwd=folder, capture_output=True,
                          text=True, env=env)
    try:
        data = json.loads(done.stdout) if done.stdout.strip() else None
    except ValueError:
        data = None
    return done.returncode, data, done.stderr


MAP = """# The areas of the shop. The last matching line wins.

docs/                  project-records
src/                   app
src/billing/           billing
/lib/util.py           shared
lib/more/              shared
*.md                   project-records
**/fixtures/**         test-data
vendor/                vendored
"""

FILES = {
    "README.md": "# A shop\n",
    "docs/area-map": MAP,
    ".agents/tools/gate.py": "print('gate')\n",
    ".github/workflows/checks.yml": "name: checks\n",
    "src/main.py": "print('main')\n",
    "src/billing/charge.py": "CHARGE = 1\n",
    "src/billing/ledger/book.py": "BOOK = 1\n",
    "src/notes.md": "notes\n",
    "src/fixtures/data.json": "{}\n",
    "lib/util.py": "UTIL = 1\n",
    "lib/more/thing.py": "THING = 1\n",
    "vendor/left-pad/index.js": "module.exports = 1;\n",
}

count = 0


def project(name, files=FILES, commit=True):
    global count
    count += 1
    folder = os.path.join(WORK, "%02d-%s" % (count, name))
    os.makedirs(folder)
    subprocess.run([GIT, "init", "-q", folder], check=True)
    git(folder, "checkout", "-q", "-b", "main")
    write(folder, files)
    git(folder, "add", "-A")
    if commit:
        git(folder, "commit", "-q", "-m", "founding")
    return folder


# --- outside a Git work tree -----------------------------------------------------

plain = os.path.join(WORK, "plain")
os.makedirs(plain)
write(plain, {"docs/area-map": MAP})
for args in (["check"], ["which", "src/a.py"], ["areas"]):
    code, data, err = run(plain, *args)
    expect(code == 4 and "next:" in err and "Traceback" not in err,
           "outside a Git work tree, %s exits 4 with a next: line" % " ".join(args),
           "exit %s err=%r" % (code, err))

# --- the passing control ------------------------------------------------------------

good = project("good")
code, data, err = run(good, "check")
expect(code == 0 and data and data["ok"] is True and data["problems"] == []
       and data["areas"] == ["project-records", "app", "billing", "shared", "test-data",
                             "vendored"],
       "a map that claims every file passes, and names its areas", "exit %s %r %r" % (code, data, err))

code, data, err = run(good, "areas")
expect(code == 0 and data["areas"] == ["project-records", "app", "billing", "shared",
                                       "test-data", "vendored"],
       "areas prints each area once, in the order of the map", repr(data))

WHICH = {
    "lib/util.py": "shared",                    # a rule fixed to the root
    "src/billing/ledger/book.py": "billing",    # the last matching rule wins
    "src/main.py": "app",
    "src/notes.md": "project-records",          # a later rule beats an earlier one
    "src/fixtures/data.json": "test-data",      # ** crosses folders
    "docs/overview.txt": "project-records",
    "lib/more/thing.py": "shared",
    "elsewhere/x.py": "unclaimed",              # in no area
    "changes/x.txt": "exempt",
    ".agents/tools/gate.py": "exempt",
    "Makefile": "exempt",
    "./src/main.py": "app",                     # given with ./
    "src/nowhere/new.py": "app",                # a path that does not exist yet
}
code, data, err = run(good, "which", *WHICH)
expect(code == 0 and data["paths"] == WHICH,
       "which names the area of each path, and exempt or unclaimed otherwise",
       repr(data))

# --- an unclaimed file -------------------------------------------------------------

unclaimed = project("unclaimed", {
    "docs/area-map": "src/billing/ billing\ndocs/ records\n",
    "src/billing/charge.py": "CHARGE = 1\n",
    "src/reports/sum.py": "SUM = 1\n",
})
code, data, err = run(unclaimed, "check")
expect(code == 1 and "src/reports/sum.py" in err and "src/billing" not in err.split("next:")[0]
       and data["problems"] and "next:" in err,
       "a file no area claims turns the check red, naming the file and only it",
       "exit %s err=%r" % (code, err))

# --- an area that matches no file ----------------------------------------------------

ghost = project("ghost", {
    "docs/area-map": "src/ app\n\nghost/ ghosts\ndocs/ records\n",
    "src/a.py": "A = 1\n",
})
code, data, err = run(ghost, "check")
expect(code == 1 and "line 3" in err and "ghosts" in err and "src/" not in err.split("next:")[0],
       "an area that matches no file turns the check red, naming its line", repr(err))

# --- a staged file counts as tracked ---------------------------------------------------

staged = project("staged", {"docs/area-map": "docs/ records\n"}, commit=False)
write(staged, {"app/page.ts": "export const page = 1;\n"})
code, _, err = run(staged, "check")
expect(code == 0, "a file that is not staged is not yet tracked", repr(err))
git(staged, "add", "app/page.ts")
code, _, err = run(staged, "check")
expect(code == 1 and "app/page.ts" in err, "once Git's index holds the file, it counts", repr(err))

# --- lines the command cannot read, for every action ------------------------------------

def unreadable(name, text, line):
    files = dict(FILES)
    files["docs/area-map"] = text
    folder = project(name, files)
    for args in (["check"], ["which", "src/main.py"], ["areas"]):
        code, data, err = run(folder, *args)
        expect(code == 1 and ("line %d" % line) in err and "next:" in err
               and "Traceback" not in err,
               "%s: %s exits 1 and names line %d" % (name, " ".join(args), line),
               "exit %s err=%r" % (code, err))


unreadable("a line of prose", "src/ app\nthe docs folder holds the records\n", 2)
unreadable("a line with one word", "src/ app\ndocs/\n", 2)
unreadable("an area name with a colon", "src/ app:main\n", 1)

# --- the map's own file -----------------------------------------------------------------

missing = project("no-map", {"src/main.py": "print('main')\n"})
for args in (["check"], ["areas"], ["which", "src/main.py"]):
    code, data, err = run(missing, *args)
    expect(code == 1 and "docs/area-map" in err and "kit/templates/area-map" in err,
           "with no docs/area-map, %s names the file and the template" % args[0], repr(err))

# --- the template every project starts from ----------------------------------------------

with open(TEMPLATE, encoding="utf-8") as handle:
    template = handle.read()
fresh = project("from-the-template", {"docs/area-map": template, "docs/README.md": "# docs\n",
                                      "README.md": "# A tool\n"})
code, data, err = run(fresh, "check")
expect(code == 0 and data["areas"] == ["project-records"],
       "a project founded from the template passes on day one", repr((data, err)))

# --- a piece's changelog file, before and after the fold ---------------------------------

folded = project("changes-and-fold")
git(folded, "checkout", "-q", "-b", "piece")
write(folded, {"changes/12-refunds.txt": "- Refunds.\n"})
git(folded, "add", "-A")
git(folded, "commit", "-q", "-m", "a piece with its changelog file")
code, _, err = run(folded, "check")
expect(code == 0, "a piece's branch carrying changes/<file> passes", repr(err))

# --- the step in the project check ---------------------------------------------------------

line = None
with open(CHECKS, encoding="utf-8") as handle:
    lines = handle.read().splitlines()
for i, text in enumerate(lines):
    if text.strip() == "- name: Check the area map" and i + 1 < len(lines):
        following = lines[i + 1].strip()
        if following.startswith("run: "):
            line = following[len("run: "):]
expect(line is not None, "checks.yml has a step named Check the area map with a run line")
if line:
    placed = project("placed-script")
    tools = os.path.join(placed, ".agents", "tools")
    os.makedirs(tools, exist_ok=True)
    shutil.copy(SCRIPT, os.path.join(tools, "area-map.py"))
    shutil.copytree(os.path.join(SCRIPTS, "loop"), os.path.join(tools, "loop"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    done = subprocess.run(["/bin/sh", "-c", line], cwd=placed, capture_output=True, text=True)
    expect(done.returncode == 0, "the step's run line passes",
           "exit %s out=%r err=%r" % (done.returncode, done.stdout, done.stderr))
    empty = os.path.join(WORK, "empty-path")
    os.makedirs(empty)
    done = subprocess.run(["/bin/sh", "-c", line], cwd=placed, capture_output=True, text=True,
                          env={"PATH": empty})
    said = [x for x in (done.stdout + done.stderr).splitlines() if x.strip()]
    expect(done.returncode == 2 and said == [
        "Check the area map needs Python 3, which this runner does not have. Add a step "
        "that installs Python 3 before this one."],
           "with no python3, the step prints its one line and exits 2",
           "exit %s out=%r err=%r" % (done.returncode, done.stdout, done.stderr))

if failures:
    print("\narea-map-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("\narea-map-rehearsal.sh: all checks passed")
PY
