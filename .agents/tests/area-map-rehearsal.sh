#!/usr/bin/env sh
# area-map-rehearsal.sh: run the area map script a founded project receives,
# area-map.py, in throwaway Git projects and read what it prints.
#
# Later steps read its output by machine: the ready-gate lint takes area names
# from `areas`, and a boundary check takes a path's area from `which`. So the
# output is read here byte for byte, not searched for a word. Every red case of
# `check` runs beside a passing control, so a check that went red on
# everything would fail here as surely as one that went red on nothing.
#
# The step in the project check runs the script behind a guard for a runner
# with no Python. That run line is read out of the shipped checks.yml and run
# as it stands, once with Python and once on a PATH without it.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation"
SCRIPT="$FOUNDATION/area-map.py"
CHECKS="$FOUNDATION/checks.yml"
RULES_TEMPLATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/working-rules.md"

if [ ! -f "$SCRIPT" ]; then
  echo "FAIL: the setup skill carries no area map script at templates/foundation/area-map.py" >&2
  exit 1
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$SCRIPT" "$CHECKS" "$RULES_TEMPLATE" "$WORK" <<'PY'
import os
import shutil
import subprocess
import sys

SCRIPT, CHECKS, RULES_TEMPLATE, WORK = sys.argv[1:5]
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
    done = subprocess.run([sys.executable, SCRIPT, *args], cwd=folder, capture_output=True,
                          text=True, env=env)
    return done.returncode, done.stdout, done.stderr


def one_line(out, err):
    said = [line for line in (out + err).splitlines() if line.strip()]
    return said[0] if len(said) == 1 else None


MASTERPLAN = ("# Masterplan\n\n## Build path\n\nPath: Build with care\nWhy: It moves money.\n"
              "Sensitive areas:\n"
              "  money: the refund button; caution: the owner checks the first refunds; "
              "not yet done\n"
              "Accepted: none\nRecheck when: payments arrive\nLast checked: 2026-10-01\n")

MAP = """# Working rules

## Areas

<!-- A comment the script never reads: - nothing: here -->

- billing: src/billing/
  sensitive: money
  boundary: reached only through src/billing/charge.py
- Order History: ./src/receipt
- app: src/
- project records: docs/
- shared code: lib/util.py, lib/more/
- vendored libraries: vendor
- reports later: none yet

## Another section

- not an area: nowhere/
"""

FILES = {
    "README.md": "# A shop\n",
    "masterplan.md": MASTERPLAN,
    "docs/working-rules.md": MAP,
    ".agents/tools/gate.py": "print('gate')\n",
    ".github/workflows/checks.yml": "name: checks\n",
    "src/main.py": "print('main')\n",
    "src/billing/charge.py": "CHARGE = 1\n",
    "src/billing/ledger/book.py": "BOOK = 1\n",
    "src/receipt/print.py": "PRINT = 1\n",
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
write(plain, {"docs/working-rules.md": MAP, "src/a.py": "A = 1\n"})
NO_GIT = ("area-map.py needs a Git repository; run it from the project folder after founding "
          "has saved its first checkpoint, or after git init.")
for args in (["check"], ["which", "src/a.py"], ["areas"]):
    code, out, err = run(plain, *args)
    expect(code == 1 and one_line(out, err) == NO_GIT and "Traceback" not in out + err,
           "outside a Git work tree, %s exits 1 with the one line" % " ".join(args),
           "exit %s out=%r err=%r" % (code, out, err))

# --- the passing control ------------------------------------------------------------

good = project("good")
code, out, err = run(good, "check")
expect(code == 0 and one_line(out, err) is not None and "7 areas" in out,
       "a map claiming every folder passes, in one line naming its areas",
       "exit %s out=%r err=%r" % (code, out, err))

code, out, err = run(good, "areas")
expect(code == 0 and err == "" and out == (
    "billing\tmoney\nOrder History\t-\napp\t-\nproject records\t-\nshared code\t-\n"
    "vendored libraries\t-\nreports later\t-\n"),
    "areas prints each area and its sensitive name or -, in file order", repr(out + err))

WHICH = [
    ("lib/util.py", "shared code"),            # a listed file
    ("src/billing/ledger/book.py", "billing"),  # nested: the more specific area wins
    ("src/main.py", "app"),
    ("elsewhere/x.py", "unclaimed"),           # in no area
    ("changes/x.md", "exempt"),
    (".agents/tools/gate.py", "exempt"),
    ("README.md", "exempt"),
    ("src/billing/refunds.py", "billing"),     # a new file under a listed folder
    ("./src/receipt/print.py", "Order History"),  # an area name with a space, given with ./
    ("src/receipt", "Order History"),          # listed without a trailing slash
    ("lib/more", "shared code"),
    ("vendor/left-pad/index.js", "vendored libraries"),
]
code, out, err = run(good, "which", *[path for path, _ in WHICH])
expect(code == 0 and err == "" and out == "".join("%s\t%s\n" % pair for pair in WHICH),
       "which prints one line per path, in the order given, with the path as given",
       repr(out + err))
code, out, err = run(good, "which", "src/nowhere/new.py")
expect(code == 0 and out == "src/nowhere/new.py\tapp\n",
       "which places a path that does not exist yet by its listed prefix", repr(out + err))

# --- an unclaimed folder -------------------------------------------------------------

unclaimed = project("unclaimed", {
    "docs/working-rules.md": "# Working rules\n\n## Areas\n\n- billing: src/billing/\n"
                             "- project records: docs/\n",
    "src/billing/charge.py": "CHARGE = 1\n",
    "src/reports/sum.py": "SUM = 1\n",
})
code, out, err = run(unclaimed, "check")
expect(code == 1 and "src/reports is a folder no area claims. Say which area it belongs to in "
       "the Areas section of docs/working-rules.md." in (out + err).splitlines()
       and "src/billing" not in out + err,
       "a folder no area claims turns the check red, naming the folder and only it",
       "exit %s out=%r err=%r" % (code, out, err))

# A folder whose every child is claimed in turn is claimed itself, and so passes.
claimed = project("claimed-in-turn", {
    "docs/working-rules.md": "# Working rules\n\n## Areas\n\n- billing: src/billing/\n"
                             "- reports: src/reports/sum.py\n- project records: docs/\n",
    "src/billing/charge.py": "CHARGE = 1\n",
    "src/reports/sum.py": "SUM = 1\n",
})
code, out, err = run(claimed, "check")
expect(code == 0, "a folder whose every child is claimed in turn passes",
       "exit %s out=%r err=%r" % (code, out, err))

# A staged file counts as tracked, before any commit.
staged = project("staged", commit=False)
write(staged, {"app/page.ts": "export const page = 1;\n"})
code, out, err = run(staged, "check")
expect(code == 0, "a folder holding only an unstaged file is not yet tracked",
       "exit %s out=%r err=%r" % (code, out, err))
git(staged, "add", "app/page.ts")
code, out, err = run(staged, "check")
expect(code == 1 and "app is a folder no area claims" in out + err,
       "once Git's index holds a file in it, the folder counts and is named",
       "exit %s out=%r err=%r" % (code, out, err))


# --- the red cases on the map's lines, each beside the control -----------------------

def map_case(name, old, new, needle, line=None, masterplan=None):
    files = dict(FILES)
    files["docs/working-rules.md"] = MAP.replace(old, new) if old else MAP + new
    if masterplan is not None:
        if masterplan == "missing":
            del files["masterplan.md"]
        else:
            files["masterplan.md"] = masterplan
    folder = project(name, files)
    code, out, err = run(folder, "check")
    said = out + err
    named = line is None or ("line %d" % line) in said
    expect(code == 1 and needle in said and named and "Traceback" not in said,
           "%s turns the check red, naming %s" % (name, "line %d" % line if line else needle),
           "exit %s out=%r err=%r" % (code, out, err))


# Line numbers count from the top of docs/working-rules.md. The billing area is
# on line 7, its sensitive line on 8, and the last area on line 15.
map_case("a listed path that does not exist", "- reports later: none yet",
         "- reports later: src/reports/", "src/reports", line=15)
map_case("a path listed under two areas", "- reports later: none yet",
         "- reports later: src/billing", "src/billing", line=15)
map_case("a sensitive name with no masterplan line", "  sensitive: money",
         "  sensitive: secrets", "secrets", line=8)
map_case("a masterplan line no area points at", "  sensitive: money\n", "", "money",
         masterplan=MASTERPLAN)
map_case("a sensitive line when the masterplan says none", None, "", "money",
         masterplan=MASTERPLAN.replace("Sensitive areas:\n  money: the refund button; caution: "
                                       "the owner checks the first refunds; not yet done\n",
                                       "Sensitive areas: none\n"), line=8)
map_case("a sensitive line when the masterplan has no Sensitive areas line", None, "", "money",
         masterplan="# Masterplan\n\nRefunds.\n", line=8)
map_case("a sensitive line when there is no masterplan", None, "", "money",
         masterplan="missing", line=8)
map_case("an area name with a comma", "- reports later: none yet",
         "- reports, later: none yet", "comma", line=15)
map_case("an area name with a colon", "- reports later: none yet",
         "- reports: later: none yet", "colon", line=15)


# --- lines the script cannot read, for every action -----------------------------------

def unreadable(name, old, new, line):
    files = dict(FILES)
    files["docs/working-rules.md"] = MAP.replace(old, new)
    folder = project(name, files)
    for args in (["check"], ["which", "src/main.py"], ["areas"]):
        code, out, err = run(folder, *args)
        said = one_line(out, err)
        expect(code == 1 and said is not None and ("line %d" % line) in said
               and "Traceback" not in out + err,
               "%s: %s exits 1 with one line naming line %d" % (name, " ".join(args), line),
               "exit %s out=%r err=%r" % (code, out, err))


unreadable("a line with no colon", "- reports later: none yet", "- reports later none yet", 15)
unreadable("an empty area name", "- reports later: none yet", "- : none yet", 15)
unreadable("an indented line under no area", "<!-- A comment the script never reads: - "
           "nothing: here -->", "  sensitive: money", 5)
unreadable("a second sensitive line", "  boundary: reached only",
           "  sensitive: money\n  boundary: reached only", 9)
unreadable("a second boundary line", "- Order History:",
           "  boundary: reached a second way\n- Order History:", 10)

# --- the map's own file -----------------------------------------------------------------

missing = project("no-working-rules", {"src/main.py": "print('main')\n"})
for args in (["check"], ["areas"]):
    code, out, err = run(missing, *args)
    said = one_line(out, err) or ""
    expect(code == 1 and "docs/working-rules.md" in said and "setup-ai-build-kit" in said,
           "with no docs/working-rules.md, %s names the file and the founding step" % args[0],
           "exit %s out=%r err=%r" % (code, out, err))
nosection = project("no-areas-section", {"docs/working-rules.md": "# Working rules\n\nRules.\n",
                                         "masterplan.md": MASTERPLAN.replace(
                                             "not yet done", "not yet done\n    paths: src/")})
code, out, err = run(nosection, "check")
said = one_line(out, err) or ""
expect(code == 1 and "## Areas" in said and "setup-ai-build-kit" in said,
       "with no Areas section, the check names the section and the founding step, and never "
       "falls back to the masterplan's paths", "exit %s out=%r err=%r" % (code, out, err))

# --- the template every project starts from ----------------------------------------------

fresh = project("from-the-template", {"docs/working-rules.md": open(RULES_TEMPLATE).read(),
                                      "README.md": "# A tool\n"})
code, out, err = run(fresh, "check")
expect(code == 0, "a project founded from the template passes on day one",
       "exit %s out=%r err=%r" % (code, out, err))
code, out, err = run(fresh, "areas")
expect(code == 0 and out == "project records\t-\n",
       "the template names one area, the project records", repr(out + err))

# --- a piece's changelog file, before and after the fold ---------------------------------

folded = project("changes-and-fold")
git(folded, "checkout", "-q", "-b", "piece")
write(folded, {"changes/12-refunds.md": "- Refunds.\n"})
git(folded, "add", "-A")
git(folded, "commit", "-q", "-m", "a piece with its changelog file")
code, out, err = run(folded, "check")
expect(code == 0, "a piece's branch carrying changes/<file>.md passes",
       "exit %s out=%r err=%r" % (code, out, err))
git(folded, "checkout", "-q", "main")
git(folded, "merge", "-q", "--no-ff", "piece", "-m", "merge")
git(folded, "rm", "-q", "changes/12-refunds.md")
git(folded, "commit", "-q", "-m", "fold")
code, out, err = run(folded, "check")
expect(code == 0 and not os.path.exists(os.path.join(folded, "changes")),
       "main after the fold, with changes/ gone, passes",
       "exit %s out=%r err=%r" % (code, out, err))

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
    os.makedirs(os.path.join(placed, ".agents", "tools"), exist_ok=True)
    shutil.copy(SCRIPT, os.path.join(placed, ".agents", "tools", "area-map.py"))
    done = subprocess.run(["/bin/sh", "-c", line], cwd=placed, capture_output=True, text=True)
    expect(done.returncode == 0 and one_line(done.stdout, done.stderr) is not None,
           "the step's run line passes and prints one line",
           "exit %s out=%r err=%r" % (done.returncode, done.stdout, done.stderr))
    empty = os.path.join(WORK, "empty-path")
    os.makedirs(empty)
    done = subprocess.run(["/bin/sh", "-c", line], cwd=placed, capture_output=True, text=True,
                          env={"PATH": empty})
    expect(done.returncode == 2 and one_line(done.stdout, done.stderr) ==
           "Check the area map needs Python 3, which this runner does not have. Add a step "
           "that installs Python 3 before this one.",
           "with no python3, the step prints its one line and exits 2",
           "exit %s out=%r err=%r" % (done.returncode, done.stdout, done.stderr))

if failures:
    print("\narea-map-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("\narea-map-rehearsal.sh: all checks passed")
PY
