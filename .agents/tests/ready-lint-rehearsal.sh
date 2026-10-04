#!/usr/bin/env sh
# ready-lint-rehearsal.sh: run the ready-gate lint a founded project receives
# against throwaway repositories and the replay harness's stand-in GitHub.
#
# A ready piece is built with nobody there, so the lint is what a person leans
# on when they leave it: the contract is whole, the bar fits the loop module,
# each acceptance check fails on today's code for the right reason, and the
# piece says what it may change and what it reaches. A lint that let one weak
# piece through would look exactly like one that works, until a build went
# wrong. So every rule is run both ways here, once on a piece that keeps it and
# once on a piece that breaks it, and two real test runners are driven: pytest
# and Node's own runner, with a Vitest project for the install step.
#
# Each project is a real repository with a bare one standing in for its
# remote. Nothing reaches the network except the one Vitest install, and
# pytest's own install into a throwaway environment where this computer has
# none.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
LINT="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/ready-lint.py"

if [ ! -f "$LINT" ]; then
  echo "FAIL: the setup skill carries no ready-gate lint at templates/foundation/ready-lint.py" >&2
  exit 1
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$ROOT" "$LINT" "$WORK" <<'PY'
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT, LINT, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
FAKE = os.path.join(ROOT, ".agents", "tests", "replay", "fake-github")
TEST_GUARD = os.path.join(ROOT, ".agents", "skills", "section-builder", "scripts", "test-guard.sh")
FLOOR = os.path.join(ROOT, ".agents", "skills", "setup-ai-build-kit", "references",
                     "check-floor.md")
DESIGN = os.path.join(ROOT, "docs", "design", "agentic-loop.md")
REAL_GIT = shutil.which("git")

failures = []


def fail(message):
    failures.append(message)
    print("FAIL: " + message, file=sys.stderr)


def ok(message):
    print("ok: " + message)


def expect(condition, message, detail=""):
    if condition:
        ok(message)
    else:
        fail(message + ((" -- " + detail) if detail else ""))


# --- the lint's own tables ---------------------------------------------------

spec = importlib.util.spec_from_file_location("ready_lint", LINT)
lint_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint_module)
PHRASES = list(lint_module.REFUSED_PHRASES)
LIMITS = dict(lint_module.LENGTH_LIMITS)
CAPS = dict(lint_module.CREW_CAPS)
RUNNERS = dict(lint_module.TEST_RUNNERS)

expect(len(PHRASES) == 13, "the lint keeps the thirteen refused phrases", str(PHRASES))
expect(LIMITS == {"type:chore": 80, "type:bug": 120, "type:feature": 250},
       "the length limits are 80 for a chore, 120 for a bug and 250 for a feature", str(LIMITS))
expect(CAPS == {"research": 5, "prototype": 3, "fix": 3, "goal": 3, "gauntlet": 3},
       "the crew steps and caps match the contract's Crew list", str(CAPS))

# The lint keeps the same Test runner table as the check floor.
floor_rows = {}
with open(FLOOR, encoding="utf-8") as handle:
    inside = False
    for line in handle:
        if line.startswith("## "):
            inside = line.strip() == "## Test runner"
            continue
        match = re.match(r"^\| `([^`]+)` \| (\w+) \|", line)
        if inside and match:
            floor_rows[match.group(2).lower()] = match.group(1)
expect(floor_rows and RUNNERS == floor_rows,
       "the lint's Test runner table is the check floor's, row for row",
       "%s against %s" % (RUNNERS, floor_rows))

# The design note's Settled when built list carries the three numbers.
with open(DESIGN, encoding="utf-8") as handle:
    design = handle.read()
settled = design.split("## Settled when built", 1)[1] if "## Settled when built" in design else ""
settled = settled.split("\n## ", 1)[0]
expect(all(re.search(r"\b%d\b" % n, settled) for n in (80, 120, 250))
       and all(word in settled for word in ("chore", "bug", "feature")),
       "the design note's Settled when built list names 80, 120 and 250 lines by type")

# --- the tools -----------------------------------------------------------------

BIN = os.path.join(WORK, "bin")
os.makedirs(BIN)
ENV = dict(os.environ)
ENV["PATH"] = FAKE + os.pathsep + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
if subprocess.run(["python3", "-m", "pytest", "--version"], capture_output=True).returncode != 0:
    print("  pytest is not here, installing it into a throwaway environment")
    venv = os.path.join(WORK, "venv")
    subprocess.run([sys.executable, "-m", "venv", venv], check=True)
    subprocess.run([os.path.join(venv, "bin", "pip"), "install", "--quiet", "pytest"], check=True)
    ENV["PATH"] = FAKE + os.pathsep + os.path.join(venv, "bin") + os.pathsep + os.environ["PATH"]
for tool in ("node", "npm"):
    if not shutil.which(tool, path=ENV["PATH"]):
        print("FAIL: %s is needed to rehearse the Node and Vitest projects" % tool, file=sys.stderr)
        sys.exit(1)

GITID = ["-c", "user.name=R", "-c", "user.email=r@example.invalid", "-c", "commit.gpgsign=false"]


def git(cwd, *args, check=True):
    done = subprocess.run([REAL_GIT, "-C", cwd, *GITID, *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), done.stderr))
    return done.stdout.strip()


def write(folder, files):
    for path, text in files.items():
        full = os.path.join(folder, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)


def agents(stack):
    return ("# AGENTS.md\n\nA rehearsal project.\n\n## Standing rules\n\n"
            "Test command: never read from here\n\n"
            "## Stack, and how to run and check it\n\n" + stack + "\n\n"
            "## Technical design\n\nTest command: nor from here\n")


PLAIN_PATH = ("# Masterplan\n\n## Build path\n\nPath: Build and run it\nWhy: A small shop tool.\n"
              "Sensitive areas: none\nAccepted: none\nRecheck when: payments arrive\n"
              "Last checked: 2026-10-01\n\n## What it does, and for whom\n\nRefunds.\n")


def care_path(stands):
    return ("# Masterplan\n\n## Build path\n\nPath: Build with care\nWhy: It moves money.\n"
            "Sensitive areas:\n"
            "  money: the refund button; caution: the shop's bookkeeper looks before it goes "
            "live; " + stands + "\n"
            "    paths: app/\n"
            "  none: tests/, src/\n"
            "Accepted: none\nRecheck when: payments arrive\nLast checked: 2026-10-01\n\n"
            "## What it does, and for whom\n\nRefunds.\n")


class Project:
    count = 0

    def __init__(self, name, files, stack, masterplan=PLAIN_PATH, push_main=True):
        Project.count += 1
        self.base = os.path.join(WORK, "%02d-%s" % (Project.count, name))
        self.dir = os.path.join(self.base, "project")
        self.origin = os.path.join(self.base, "origin.git")
        self.state = os.path.join(self.base, "gh.json")
        self.log = os.path.join(self.base, "gh.log")
        os.makedirs(self.base)
        subprocess.run([REAL_GIT, "init", "-q", "--bare", self.origin], check=True)
        subprocess.run([REAL_GIT, "init", "-q", self.dir], check=True)
        git(self.dir, "checkout", "-q", "-b", "main")
        git(self.dir, "remote", "add", "origin", self.origin)
        write(self.dir, {"AGENTS.md": agents(stack), "masterplan.md": masterplan,
                         "CHANGELOG.md": "# Changelog\n"})
        write(self.dir, files)
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-q", "-m", "founding")
        if push_main:
            git(self.dir, "push", "-q", "origin", "main")
        self.issues = []

    def head(self, ref="main"):
        return git(self.dir, "rev-parse", ref)

    def branch(self, name, files, start="main", remove=()):
        git(self.dir, "checkout", "-q", "-b", name, start)
        write(self.dir, files)
        for path in remove:
            os.remove(os.path.join(self.dir, path))
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-q", "-m", "checks for " + name)
        git(self.dir, "push", "-q", "origin", name)
        git(self.dir, "checkout", "-q", "main")

    def main_commit(self, files):
        write(self.dir, files)
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-q", "-m", "later work on main")
        git(self.dir, "push", "-q", "origin", "main")

    def lint(self, number, issues, extra_env=None, faults=None, path_first=None):
        state = {"repo": "rehearsal/project", "next": 900, "issues": issues}
        if faults:
            state["faults"] = faults
        with open(self.state, "w") as handle:
            json.dump(state, handle)
        if os.path.exists(self.log):
            os.remove(self.log)
        env = dict(ENV)
        env["FAKE_GH_STATE"] = self.state
        env["FAKE_GH_LOG"] = self.log
        temporary = os.path.join(self.base, "tmp")
        os.makedirs(temporary, exist_ok=True)
        env["TMPDIR"] = temporary
        if path_first:
            env["PATH"] = path_first + os.pathsep + env["PATH"]
        env.update(extra_env or {})
        started = time.time()
        done = subprocess.run([sys.executable, LINT, str(number)], cwd=self.dir, env=env,
                              capture_output=True, text=True)
        self.seconds = time.time() - started
        self.left_in_tmp = os.listdir(temporary)
        self.worktrees = [l for l in git(self.dir, "worktree", "list", "--porcelain").splitlines()
                          if l.startswith("worktree ")]
        return done.returncode, done.stdout, done.stderr


def issue(number, body, labels, title=None, state="open", blocked_by=()):
    return {"number": number, "title": title or "Refund an order", "body": body,
            "state": state, "labels": list(labels), "assignees": [],
            "blocked_by": list(blocked_by), "sub_issues": []}


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


def clean_after(project, what):
    # Only the lint's own folders count. A test runner may keep a cache of its
    # own in the same temporary folder, as Node does.
    mine = [name for name in project.left_in_tmp if name.startswith("ready-lint-")]
    expect(not mine and len(project.worktrees) == 1,
           "%s: no temporary folder or registered checkout is left behind" % what,
           "left %s, worktrees %s" % (mine, project.worktrees))


def passes(project, number, issues, what, extra_env=None, also=None):
    code, out, err = project.lint(number, issues, extra_env)
    said = lines(out)
    good = (code == 0 and said and said[0].startswith("Ready-gate lint: no gaps on ")
            and (also is None or also(out)))
    expect(good, what + ": passes", "exit %s out=%r err=%r" % (code, out, err))
    clean_after(project, what)
    return out


def refused(project, number, issues, what, *needles, extra_env=None, path_first=None):
    code, out, err = project.lint(number, issues, extra_env, path_first=path_first)
    said = out + err
    good = (code == 1 and "next:" in said
            and all(n.lower() in said.lower() for n in needles))
    expect(good, what + ": refused, naming %s" % ", ".join(repr(n) for n in needles),
           "exit %s out=%r err=%r" % (code, out, err))
    clean_after(project, what)
    return said


# --- the pieces --------------------------------------------------------------

def body(loop, reach, works=None, decided=None, extra="", relies=None, must=None,
         evidence=None, not_normal=None, needs=None):
    works = works if works is not None else [
        "A refund of a paid order returns the whole amount. Check: tests/test_refund.py"]
    parts = ["## So that", "A shop owner can refund an order from its page.", "",
             "## Done when", "### Works"]
    parts += ["- " + w for w in works]
    parts += ["### When it is not the normal case",
              not_normal or "- An unpaid order: does not arise, because only paid orders "
                            "show the refund button.", "",
              "## Masterplan change", "nothing", "",
              "## Not in this piece", "Partial refunds, which follow in their own piece.", "",
              "## Decided", decided or "- A refund returns the whole amount, because partial "
                                       "refunds come later.", "",
              "## Data", "None; this piece stores nothing new.", "",
              "## Leaves the tool", "Nothing leaves the tool.", "",
              "## Must still hold", must or "- Order totals stay in whole pence.", "",
              "## Relies on", relies or "- The order total in `app/orders.py`, line 1, "
                                        "confirmed by reading it.", "",
              "## Loop", loop, "",
              "## Reach", reach, "",
              "## Needs from the computer",
              needs or "Heavy: no\nDev server: no\nBrowser: no\nExpected duration: 20 minutes\n"
                       "Cannot share: nothing", "",
              "<details><summary>Under the hood</summary>", "",
              "Build the refund beside the order total.", "", "</details>", "",
              "## Evidence", evidence or "Automated behaviour checks on each Done when line."]
    return "\n".join(parts) + "\n" + extra


def reach(head, boundary="refunds", reaches=None, breaks=None, depends="nothing"):
    return "\n".join([
        "Boundary: " + boundary,
        "Reaches: " + (reaches or "orders, guarded by `tests/test_orders.py`"),
        "If it breaks: " + (breaks or "the owner sees a wrong refund, and a rollback undoes it."),
        "Depends on: " + depends,
        "Reach derived at: " + head])


BUILD = "type:feature"

# --- the pytest project --------------------------------------------------------

PY_FILES = {
    "app/__init__.py": "",
    "app/refunds.py": "def refund(total):\n    return 0\n",
    "app/orders.py": "def order_total():\n    return 10\n",
    "tests/__init__.py": "",
    "tests/test_orders.py": "from app.orders import order_total\n\n\n"
                            "def test_order_total():\n    assert order_total() == 10\n",
    "src/auth/session.ts": "export const session = 1;\n",
}
PY_STACK = ("Recipe: none\n"
            "Test command: python3 -m pytest\n"
            "- Install: nothing to install. Type check `mypy .`, lint `ruff check .`.\n"
            "Test command: false")

py = Project("pytest", PY_FILES, PY_STACK)
REFUND_TEST = ("from app.refunds import refund\n\n\n"
               "def test_refund_returns_whole_amount():\n    assert refund(10) == 10\n")
py.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
py.branch("spec/12-missing-import", {"tests/test_refund.py": (
    "from app.nowhere import refund\n\n\ndef test_refund():\n    assert refund(10) == 10\n")})
py.branch("spec/12-passing", {"tests/test_refund.py": (
    "from app.orders import order_total\n\n\ndef test_total():\n    assert order_total() == 10\n")})
py.branch("spec/12-source", {"tests/test_refund.py": REFUND_TEST,
                             "app/refunds.py": "def refund(total):\n    return total\n"})
py.branch("spec/12-hangs", {"tests/test_refund.py": (
    "import time\n\n\ndef test_refund():\n    time.sleep(120)\n")})
py.branch("spec/13-rounding", {"tests/test_rounding.py": (
    "from app.refunds import refund\n\n\ndef test_rounds_to_whole_pence():\n"
    "    assert refund(7) == 7\n")})
early = py.head()
py.branch("spec/12-early", {"tests/test_refund.py": REFUND_TEST}, start=early)
py.main_commit({"app/orders.py": "def order_total():\n    return 10  # unchanged total\n"})
HEAD = py.head()
spec_only = py.head("spec/12-sign-in")

BUILD_LOOP = "Loop module: build\nAcceptance branch: spec/12-sign-in"
GOOD = body(BUILD_LOOP, reach(HEAD))
LABELS = ["state:shaping", "shaping:check", BUILD, "loop:build"]


def build_piece(text=None, labels=None, **extra):
    return issue(12, text if text is not None else GOOD, labels or LABELS, **extra)


out = passes(py, 12, [build_piece()], "a whole build piece whose check fails on its assertion")
expect(len(lines(out)) == 1 and "Refund an order" in out,
       "a pass prints one line naming the piece", repr(out))
with open(py.log) as handle:
    writes = [l for l in handle if l.startswith("CALL") and re.search(
        r"\b(issue (edit|comment|create|close)|label (create|edit|delete))\b|-X|--method", l)]
expect(not writes, "the lint writes nothing to GitHub", str(writes))
expect(git(py.dir, "status", "--porcelain") == "", "the lint writes nothing into the project")

for branch, what, needles in (
        ("spec/12-missing-import", "a check failing on a missing import", ["tests/test_refund.py", "module"]),
        ("spec/12-passing", "a check that passes on today's code", ["tests/test_refund.py", "passes"]),
        ("spec/12-source", "a spec branch that also changes source code", ["app/refunds.py", "test files"])):
    refused(py, 12, [build_piece(body("Loop module: build\nAcceptance branch: " + branch,
                                      reach(HEAD)))], what, *needles)
passes(py, 12, [build_piece(body("Loop module: build\nAcceptance branch: spec/12-early",
                                 reach(HEAD)))],
       "a spec branch cut before a later commit to main that changed source code")

# The ten-minute limit, lowered so the rehearsal does not wait ten minutes.
refused(py, 12, [build_piece(body("Loop module: build\nAcceptance branch: spec/12-hangs",
                                  reach(HEAD)))],
        "a check that runs past the time limit", "tests/test_refund.py", "limit",
        extra_env={"READY_LINT_TIME_LIMIT": "3"})
expect(py.seconds < 60, "the check past its limit is stopped, not waited for",
       "%.0fs" % py.seconds)

# The first Test command line in the stack section is the one run.
expect(PY_STACK.index("python3 -m pytest") < PY_STACK.index("Test command: false"),
       "the fixture's stack carries a later Test command line the lint must not run")

# A fix piece: the reproduction fails today, on its assertion.
FIX = body("Loop module: fix\nAcceptance branch: spec/13-rounding\n"
           "Reproduction: tests/test_rounding.py\nMust not change: the order totals",
           reach(HEAD, reaches="orders, guarded by `tests/test_orders.py`"),
           works=["A refund of seven pounds returns seven pounds. Check: tests/test_rounding.py"])
FIX_LABELS = ["state:shaping", "shaping:check", "type:bug", "loop:fix"]
passes(py, 12, [issue(12, FIX, FIX_LABELS)], "a whole fix piece")
for field in ("Acceptance branch:", "Reproduction:", "Must not change:"):
    text = "\n".join(l for l in FIX.splitlines() if not l.startswith(field)) + "\n"
    refused(py, 12, [issue(12, text, FIX_LABELS)], "a fix piece with no %s line" % field, field)

# The build bar.
text = "\n".join(l for l in GOOD.splitlines() if not l.startswith("Acceptance branch:")) + "\n"
refused(py, 12, [build_piece(text)], "a build piece with no Acceptance branch", "Acceptance branch:")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), works=[
    "A refund of a paid order returns the whole amount. Check: tests/test_refund.py",
    "The refund shows on the order page."]))],
    "a Works line that names no check of its own", "Check:")
refused(py, 12, [build_piece(body(BUILD_LOOP + "\nMust not change: none", reach(HEAD)))],
        "a field the module does not use, written as none", "Must not change:")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), works=[
    "A refund returns the whole amount. Check: tests/test_absent.py"]))],
    "a Check naming a file the acceptance branch does not hold", "tests/test_absent.py")

# Loop module and label.
refused(py, 12, [build_piece(labels=["state:shaping", "shaping:check", BUILD])],
        "a piece with no loop: label", "loop:")
refused(py, 12, [build_piece(labels=LABELS + ["loop:goal"])], "a piece with two loop: labels", "loop:")
refused(py, 12, [build_piece(labels=["state:shaping", "shaping:check", BUILD, "loop:fix"])],
        "a loop: label that does not match Loop module", "loop:fix")
refused(py, 12, [build_piece(body("Loop module: sprint\nAcceptance branch: spec/12-sign-in",
                                  reach(HEAD)))], "an unknown loop module", "sprint")

# Required sections, each missing and each empty.
for heading in ("So that", "Done when", "Masterplan change", "Not in this piece", "Decided",
                "Data", "Leaves the tool", "Must still hold", "Relies on", "Loop", "Reach",
                "Needs from the computer", "Evidence"):
    kept, skipping = [], False
    for line in GOOD.splitlines():
        if line.startswith("## "):
            skipping = line[3:].strip() == heading
        if not skipping:
            kept.append(line)
    refused(py, 12, [build_piece("\n".join(kept) + "\n")], "a piece with no ## %s" % heading,
            "## " + heading)
emptied = GOOD.replace("## Not in this piece\nPartial refunds, which follow in their own piece.\n",
                       "## Not in this piece\n\n")
refused(py, 12, [build_piece(emptied)], "an empty ## Not in this piece", "## Not in this piece")

# An older piece carrying Touches: and no Loop or Reach.
OLD = ("## So that\nA shop owner can refund an order.\n\n## Done when\n### Works\n"
       "- A refund returns the whole amount. Check: a test\n\n## Masterplan change\nnothing\n\n"
       "## Not in this piece\nPartial refunds.\n\n## Decided\n- Whole amounts only.\n\n"
       "Touches: refunds\n")
refused(py, 12, [build_piece(OLD)], "an older piece carrying Touches: only",
        "## Loop", "## Reach", "Touches:")

# Reach.
for field in ("Boundary:", "Reaches:", "If it breaks:", "Depends on:", "Reach derived at:"):
    text = "\n".join(l for l in GOOD.splitlines() if not l.startswith(field)) + "\n"
    refused(py, 12, [build_piece(text)], "a reach with no %s line" % field, field)
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(
    HEAD, reaches="orders, guarded by `tests/test_gone.py`")))],
    "a Reaches test that is not on origin/main", "tests/test_gone.py")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(
    HEAD, reaches="the receipt, no test covers it, guarded by tests/test_receipt.py")))],
    "a no-test line naming a check the piece does not carry", "no test covers it")
passes(py, 12, [build_piece(body(BUILD_LOOP, reach(
    HEAD, reaches="the receipt, no test covers it, guarded by tests/test_refund.py")))],
    "a no-test line naming the piece's own acceptance check")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach("0123456789abcdef0123456789abcdef01234567")))],
        "a Reach derived at that is not a commit", "Reach derived at:")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(spec_only)))],
        "a Reach derived at that origin/main does not contain", "origin/main")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD, depends="#5"))),
                 issue(5, "x", ["state:ready", BUILD], title="Orders")],
        "a Depends on the blocked-by links do not hold", "Depends on:", "#5")
refused(py, 12, [build_piece(blocked_by=[5]), issue(5, "x", ["state:ready", BUILD], title="Orders")],
        "a blocked-by link Depends on does not name", "Depends on:", "#5")
passes(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD, depends="#5")), blocked_by=[5]),
                issue(5, "x", ["state:ready", BUILD], title="Orders")],
       "a Depends on that matches the blocked-by links")
# The numbers are built rather than written, since a tracked file never cites
# an issue by number.
RING = ["#%d" % n for n in (13, 14)]
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD, depends=RING[0])), blocked_by=[13]),
                 issue(13, "x", ["state:ready", BUILD], title="Orders", blocked_by=[14]),
                 issue(14, "x", ["state:ready", BUILD], title="Stock", blocked_by=[12])],
        "three pieces waiting on each other in a ring", "cycle", *RING)

# The brief rules.
passes(py, 12, [build_piece()], "a Relies on naming a file and a line")
passes(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), works=[
    "POST /api/sign-in answers with the refund. Check: tests/test_refund.py"]))],
    "a Works line naming the route POST /api/sign-in")
passes(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), works=[
    "The app shows the refund. Check: tests/test_refund.py"]))],
    "a Works line using the word app where an app/ folder is tracked")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), works=[
    "The refund is kept in src/auth/session.ts. Check: tests/test_refund.py"]))],
    "a Works line naming the tracked src/auth/session.ts", "src/auth/session.ts")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD), must="- `app/orders.py` keeps its total."))],
        "a file path under Must still hold", "app/orders.py")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD),
                                  decided="- The refund sits after line 12 of the page."))],
        "a line number outside Relies on", "line 12")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD),
                                  decided="- The refund follows app/refunds.py:2."))],
        "a file and line outside Relies on", "app/refunds.py:2")
refused(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD),
                                  decided="1. Write the refund.\n2. Show it on the page."))],
        "a numbered list of build steps", "numbered")
passes(py, 12, [build_piece(body(BUILD_LOOP, reach(HEAD),
                                 evidence="1. The refund check.\n2. The order check."))],
       "a numbered list under Evidence")

# The sensitive area, read from the masterplan on origin/main.
care = Project("care", PY_FILES, PY_STACK, masterplan=care_path("not yet done"))
care.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
refused(care, 12, [build_piece(body(BUILD_LOOP, reach(care.head(), boundary="money")))],
        "a sensitive area under Boundary whose caution is not done", "money")
refused(care, 12, [build_piece(body(BUILD_LOOP, reach(
    care.head(), reaches="Money, guarded by `tests/test_orders.py`")))],
    "a sensitive area under Reaches, in other capitals, whose caution is not done", "money")
cared = Project("cared", PY_FILES, PY_STACK, masterplan=care_path("done 2026-09-30"))
cared.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
passes(cared, 12, [build_piece(body(BUILD_LOOP, reach(cared.head(), boundary="money")))],
       "a sensitive area whose caution is done")
accepted = Project("accepted", PY_FILES, PY_STACK, masterplan=care_path("accepted 2026-09-30"))
accepted.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
passes(accepted, 12, [build_piece(body(BUILD_LOOP, reach(accepted.head(), boundary="money")))],
       "a sensitive area whose caution is accepted")
nopath = Project("no-build-path", PY_FILES, PY_STACK, masterplan="# Masterplan\n\nRefunds.\n")
nopath.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
refused(nopath, 12, [build_piece(body(BUILD_LOOP, reach(nopath.head())))],
        "a masterplan with no build-path section", "build-path")

# The cases the lint refuses before it reads a contract.
for args, what, needle in ((999, "an issue that does not exist", "does not exist"),
                           ("ten", "an argument that is not a number", "not an issue number")):
    code, out, err = py.lint(args, [build_piece()])
    expect(code == 1 and needle in out + err and "next:" in out + err,
           "%s is refused with a next action" % what, repr(out + err))
refused(py, 12, [build_piece(state="closed")], "a closed issue", "closed")
refused(py, 12, [build_piece(labels=["state:shaping", "shaping:check", "loop:build"])],
        "a piece with no type: label", "type:")
refused(py, 12, [build_piece(labels=LABELS + ["type:bug"])], "a piece with two type: labels", "type:")

# GitHub out of reach.
code, out, err = py.lint(12, [build_piece()], faults={"offline": True})
expect(code == 2 and len(lines(out) + lines(err)) == 1,
       "with GitHub out of reach the lint exits 2 and says so in one line", repr(out + err))
expect(git(py.dir, "status", "--porcelain") == "", "and changes nothing in the project")

# The temporary checkout cannot be made: a stand-in git says the disk is full.
with open(os.path.join(BIN, "git"), "w") as handle:
    handle.write("#!/bin/sh\ncase \" $* \" in\n  *\" worktree add \"*) "
                 "echo 'fatal: could not create directory: No space left on device' >&2; "
                 "exit 128 ;;\nesac\nexec %s \"$@\"\n" % REAL_GIT)
os.chmod(os.path.join(BIN, "git"), 0o755)
code, out, err = py.lint(12, [build_piece()], path_first=BIN)
expect(code == 2 and "checkout" in (out + err).lower(),
       "a checkout that cannot be made exits 2 and says so", repr(out + err))
clean_after(py, "a checkout that cannot be made")

# --- the refused phrases, read from the lint's own list ----------------------

GOAL_LOOP = ("Loop module: goal\nMetric: the refund page's load time\n"
             "Measured by: `python3 tools/measure.py`\nTarget: under 300 milliseconds\n"
             "Budget: 5 attempts\nGuard checks: `tests/test_orders.py`\n"
             "Held-out check: `python3 tools/held_out.py` on held-out/20-load-time at 1a2b3c4")
GOAL_LABELS = ["state:shaping", "shaping:check", "type:chore", "loop:goal"]
GOAL_WORKS = ["The refund page loads in under 300 milliseconds. Check: the measured load time"]


def goal(loop=GOAL_LOOP, reach_text=None, **kw):
    kw.setdefault("works", GOAL_WORKS)
    return body(loop, reach_text or reach(HEAD), **kw)


passes(py, 20, [issue(20, goal(), GOAL_LABELS)], "a whole goal piece")
for phrase in PHRASES:
    refused(py, 20, [issue(20, goal(works=[
        "The refund page loads quickly, %s. Check: the measured load time" % phrase]),
        GOAL_LABELS)], "the refused phrase %r in Done when" % phrase, phrase)
for where, kw in (("Decided", {"decided": "- Cache the page, TBD."}),
                  ("Loop", {"loop": GOAL_LOOP + "\nTarget note: decide during build"}),
                  ("Reach", {"reach_text": reach(HEAD, breaks="the page is slow for now.")})):
    refused(py, 20, [issue(20, goal(**kw), GOAL_LABELS)], "a refused phrase under %s" % where,
            "refused phrase")
passes(py, 20, [issue(20, goal(works=[
    "The refund page may show a spinner while it loads. Check: the measured load time"]),
    GOAL_LABELS)], "the word may in a Done when line, which is left to the readiness check")
passes(py, 20, [issue(20, goal(works=[
    "The page keeps its `TBD` marker hidden. Check: the measured load time"]), GOAL_LABELS)],
    "a refused phrase inside a code span")
passes(py, 20, [issue(20, goal(evidence="A few timed runs, for now."), GOAL_LABELS)],
       "a refused phrase outside the four sections it is read in")

# The goal and gauntlet bars.
for field in ("Metric:", "Measured by:", "Target:", "Budget:", "Guard checks:", "Held-out check:"):
    text = "\n".join(l for l in goal().splitlines() if not l.startswith(field)) + "\n"
    refused(py, 20, [issue(20, text, GOAL_LABELS)], "a goal piece with no %s line" % field, field)
for budget, what in (("20000 tokens", "a token budget"), ("5", "a budget with no unit"),
                     ("plenty of attempts", "a budget with no number")):
    refused(py, 20, [issue(20, goal(loop=GOAL_LOOP.replace("5 attempts", budget)), GOAL_LABELS)],
            "%s" % what, "Budget:")
GAUNTLET_LOOP = ("Loop module: gauntlet\n"
                 "Reference: https://example.com/refund-page, approved by the owner on 2026-10-01\n"
                 "Compared by: a blind critic\nBudget: 30 minutes\n"
                 "Guard checks: `tests/test_orders.py`")
GAUNTLET_LABELS = ["state:shaping", "shaping:check", "type:feature", "loop:gauntlet"]
passes(py, 21, [issue(21, goal(loop=GAUNTLET_LOOP), GAUNTLET_LABELS)],
       "a whole gauntlet piece, its Reference a link")
for field in ("Reference:", "Compared by:", "Budget:", "Guard checks:"):
    text = "\n".join(l for l in goal(loop=GAUNTLET_LOOP).splitlines()
                     if not l.startswith(field)) + "\n"
    refused(py, 21, [issue(21, text, GAUNTLET_LABELS)], "a gauntlet piece with no %s line" % field,
            field)
refused(py, 21, [issue(21, goal(loop=GAUNTLET_LOOP.replace(
    "https://example.com/refund-page, approved", "the old refund page, approved")),
    GAUNTLET_LABELS)], "a gauntlet Reference that is not a link", "Reference:")
refused(py, 21, [issue(21, goal(loop=GAUNTLET_LOOP.replace(" on 2026-10-01", "")),
                       GAUNTLET_LABELS)], "a gauntlet Reference with no approval date", "Reference:")

# --- the crew ------------------------------------------------------------------

for step, cap in CAPS.items():
    passes(py, 20, [issue(20, goal(extra="\nCrew: %s %d, because the answer is spread out\n"
                                   % (step, cap)), GOAL_LABELS)], "a %s crew at its cap" % step)
    refused(py, 20, [issue(20, goal(extra="\nCrew: %s %d, because the answer is spread out\n"
                                    % (step, cap + 1)), GOAL_LABELS)],
            "a %s crew one over its cap" % step, "cap")
refused(py, 20, [issue(20, goal(extra="\nCrew: research 2\n"), GOAL_LABELS)],
        "a crew with no reason", "because")
for line, what in (("Crew: builders 2, because the piece is big", "two builders"),
                   ("Crew: build 2, because the piece is big", "the build step"),
                   ("Crew: readiness check 2, because it is long", "the readiness check step"),
                   ("Crew: run 2, because there is a lot", "the run")):
    refused(py, 20, [issue(20, goal(extra="\n" + line + "\n"), GOAL_LABELS)],
            "a crew naming %s" % what, "two writers")

# --- the length limit ------------------------------------------------------------

READINESS = "## Readiness\n" + "".join("- NOTE %d: a note.\n" % n for n in range(1, 31))


def padded(limit, over):
    base = goal()
    count = len(base.rstrip("\n").split("\n"))
    filler = "".join("- Padding row %d.\n" % n for n in range(limit - count + over))
    text = base.replace("## Must still hold\n", "## Must still hold\n" + filler, 1)
    return text + "\n" + READINESS


for label, limit in LIMITS.items():
    labels = ["state:shaping", "shaping:check", label, "loop:goal"]
    passes(py, 20, [issue(20, padded(limit, 0), labels)],
           "a %s at its limit of %d lines, a long Readiness left uncounted" % (label, limit))
    refused(py, 20, [issue(20, padded(limit, 1), labels)],
            "a %s one line over its limit" % label, str(limit))

# --- install, and a runner the lint cannot read ----------------------------------

broken = Project("install-fails", PY_FILES, PY_STACK.replace(
    "- Install: nothing to install.", "- Install `sh -c 'exit 3'`."))
broken.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
code, out, err = broken.lint(12, [build_piece(body(BUILD_LOOP, reach(broken.head())))])
expect(code == 2 and "install" in (out + err).lower(),
       "an install that fails exits 2 naming the install, never a failing check", repr(out + err))
clean_after(broken, "an install that fails")

shell = Project("shell-runner", dict(PY_FILES, **{
    "run-tests.sh": "#!/bin/sh\nexec python3 \"$@\"\n"}),
    "Recipe: none\nTest command: sh run-tests.sh")
shell.branch("spec/12-sign-in", {"tests/check_refund.py": (
    "import sys\nsys.path.insert(0, '.')\nfrom app.refunds import refund\n\n"
    "assert refund(10) == 10\n")})
passes(shell, 12, [build_piece(body(BUILD_LOOP, reach(shell.head()), works=[
    "A refund returns the whole amount. Check: tests/check_refund.py"]))],
    "a runner named only by a shell command, counted by its exit code",
    also=lambda out: "NOTE" in out and "assertion" in out)

# --- a project with no code yet --------------------------------------------------

def no_code(name, stack, runner_line, branch_files=None):
    project = Project(name, {}, stack)
    project.branch("spec/40-first", branch_files or {"tests/test_first.py": (
        "from app.first import first\n\n\ndef test_first():\n    assert first() == 1\n")})
    loop = "Loop module: build\nAcceptance branch: spec/40-first" + runner_line
    text = body(loop, reach(project.head(),
                            reaches="the founding records, no test covers it, guarded by "
                                    "tests/test_first.py"),
                works=["The first page says hello. Check: tests/test_first.py"])
    return project, text


empty, text = no_code("founding-records-only", "Recipe: none\nTest command: none for python",
                      "\nTest runner: pytest")
passes(empty, 40, [issue(40, text, LABELS)],
       "an empty repository holding only the founding records, its acceptance branch of pytest files",
       also=lambda out: "no code yet: checks not run" in out)
nonepy, text = no_code("none-for-python", "Recipe: none\nTest command: none for python\n"
                       "- Type check `mypy .`.", "\nTest runner: pytest")
passes(nonepy, 40, [issue(40, text, LABELS)], "Test command none for python with Test runner pytest",
       also=lambda out: "no code yet: checks not run" in out)
refused(nonepy, 40, [issue(40, text.replace("\nTest runner: pytest", ""), LABELS)],
        "Test command none for python with no Test runner", "Test runner:")
refused(nonepy, 40, [issue(40, text.replace("Test runner: pytest", "Test runner: vitest"), LABELS)],
        "a Test runner the table does not give for the language", "vitest", "python")
refused(nonepy, 40, [issue(40, text.replace(
    "The first page says hello.", "The first page writes data/out.csv."), LABELS)],
    "a path ending in an extension, on a project with no code yet", "data/out.csv")
nonepy.branch("spec/41-source", {"tests/test_first.py": "def test_first():\n    assert False\n",
                                 "app/first.py": "def first():\n    return 1\n"})
refused(nonepy, 40, [issue(40, text.replace("spec/40-first", "spec/41-source"), LABELS)],
        "a spec branch with source code, on a project with no code yet", "app/first.py")
refused(nonepy, 40, [issue(40, text.replace("Check: tests/test_first.py",
                                            "Check: tests/test_second.py"), LABELS)],
        "a Check the branch does not hold, on a project with no code yet", "tests/test_second.py")

unborn = Project("no-origin-main", {}, "Recipe: none\nTest command: none for python",
                 push_main=False)
code, out, err = unborn.lint(40, [issue(40, body(
    "Loop module: build\nAcceptance branch: spec/40-first\nTest runner: pytest",
    reach("1a2b3c4"), works=["The first page says hello. Check: tests/test_first.py"]), LABELS)])
expect(code == 1 and "first-upload question" in out + err and "/shape" in out + err,
       "no origin/main and a build piece: refused, naming the first-upload question in /shape",
       repr(out + err))
code, out, err = unborn.lint(20, [issue(20, goal(reach_text=reach("1a2b3c4")), GOAL_LABELS)])
expect(code == 0 and "no code yet" in out,
       "no origin/main and a goal piece: its checks on main say no code yet, and it passes",
       repr(out + err))

missing = Project("no-test-command", PY_FILES, "Recipe: none\n- Run `python3 -m app`.")
missing.branch("spec/12-sign-in", {"tests/test_refund.py": REFUND_TEST})
refused(missing, 12, [build_piece(body(BUILD_LOOP, reach(missing.head())))],
        "a project with origin/main and no Test command line",
        "add a `Test command:` line to AGENTS.md's stack section")

# --- Node's own test runner --------------------------------------------------------

NODE_FILES = {"package.json": json.dumps({"name": "shop", "private": True, "type": "module",
                                          "scripts": {"test": "node --test"}}) + "\n",
              "lib/refunds.mjs": "export function refund(total) {\n  return 0;\n}\n",
              "test/orders.test.mjs": ("import { test } from \"node:test\";\n"
                                       "import assert from \"node:assert/strict\";\n"
                                       "test(\"orders\", () => assert.equal(1, 1));\n")}
NODE_TEST = ("import { test } from \"node:test\";\nimport assert from \"node:assert/strict\";\n"
             "import { refund } from \"../lib/refunds.mjs\";\n"
             "test(\"refund\", () => assert.equal(refund(10), 10));\n")


def node_project(name, command):
    project = Project(name, NODE_FILES, "Recipe: none\nTest command: " + command)
    project.branch("spec/30-refunds", {"test/refund.test.mjs": NODE_TEST})
    project.branch("spec/31-missing", {"test/refund.test.mjs": NODE_TEST.replace(
        "../lib/refunds.mjs", "../lib/nowhere.mjs")})
    project.branch("spec/32-passing", {"test/refund.test.mjs": NODE_TEST.replace(
        "refund(10), 10", "refund(10), 0")})
    return project


def node_piece(project, branch):
    return [issue(30, body("Loop module: build\nAcceptance branch: " + branch,
                           reach(project.head(), reaches="orders, guarded by "
                                                         "`test/orders.test.mjs`"),
                           works=["A refund returns the whole amount. "
                                  "Check: test/refund.test.mjs"]), LABELS)]


node = node_project("node-test", "node --test")
passes(node, 30, node_piece(node, "spec/30-refunds"),
       "a Node test-runner check failing on its assertion")
refused(node, 30, node_piece(node, "spec/31-missing"), "a Node check failing on a missing import",
        "test/refund.test.mjs")
refused(node, 30, node_piece(node, "spec/32-passing"), "a Node check that passes on today's code",
        "passes")
npm = node_project("npm-test", "npm test")
passes(npm, 30, node_piece(npm, "spec/30-refunds"),
       "a Node project whose Test command is npm test, read through package.json")
refused(npm, 30, node_piece(npm, "spec/31-missing"),
        "an npm test check failing on a missing import", "test/refund.test.mjs")

# --- a Vitest project, whose check needs the install ------------------------------

VITEST_FILES = {
    "package.json": json.dumps({"name": "shop", "private": True, "type": "module",
                                "dependencies": {"refund-maths": "file:vendor/refund-maths"},
                                "devDependencies": {"vitest": "^3"}}) + "\n",
    ".gitignore": "node_modules/\n",
    "vendor/refund-maths/package.json": json.dumps({"name": "refund-maths", "version": "1.0.0",
                                                    "type": "module", "main": "index.js"}) + "\n",
    "vendor/refund-maths/index.js": "export function whole(total) {\n  return total;\n}\n",
    "lib/refunds.js": "export function refund(total) {\n  return 0;\n}\n",
}
vitest = Project("vitest", VITEST_FILES, "Recipe: none\n"
                 "- Install `npm install --no-audit --no-fund`.\nTest command: npx vitest run")
vitest.branch("spec/33-refunds", {"test/refund.test.js": (
    "import { test, expect } from \"vitest\";\nimport { whole } from \"refund-maths\";\n"
    "import { refund } from \"../lib/refunds.js\";\n"
    "test(\"refund\", () => { expect(refund(10)).toBe(whole(10)); });\n")})
passes(vitest, 33, [issue(33, body("Loop module: build\nAcceptance branch: spec/33-refunds",
                                   reach(vitest.head(), reaches="refunds maths, no test covers it, "
                                                                "guarded by test/refund.test.js"),
                                   works=["A refund returns the whole amount. "
                                          "Check: test/refund.test.js"]), LABELS)],
       "a Vitest check importing a dependency, failing on its assertion after the install")

# --- Jest's report, read without running Jest ---------------------------------------

jest_report = os.path.join(WORK, "jest.json")
with open(jest_report, "w") as handle:
    json.dump({"testResults": [
        {"name": "/p/a.test.js", "status": "failed", "message": "", "assertionResults": [
            {"fullName": "a", "status": "failed", "failureMessages": [
                "Error: expect(received).toBe(expected) // Object.is equality\n\nExpected: 2"]}]},
        {"name": "/p/b.test.js", "status": "failed", "assertionResults": [],
         "message": "Cannot find module './nowhere' from 'b.test.js'"}]}, handle)
found = lint_module.read_failures("jest", jest_report)
expect([f["assertion"] for f in found] == [True, False],
       "a Jest report reads an expect failure as an assertion and a missing module as not",
       str(found))

# --- a test file, as test-guard.sh counts one ---------------------------------------

NAMES = ["tests/test_a.py", "test/a.js", "__tests__/a.js", "spec/a.rb", "src/a.test.ts",
         "src/a.spec.js", "src/a_test.go", "src/a_spec.rb", "src/test_a.py", "src/a.py",
         "src/testing.py", "lib/contest.py", "docs/spec.md", "spec.md", "src/latest/a.py",
         "attest/a.py", "nested/tests/deep/a.py", "a.test", "test_"]
guard = os.path.join(WORK, "guard")
os.makedirs(guard)
subprocess.run([REAL_GIT, "init", "-q", guard], check=True)
write(guard, {n: "one\n" for n in NAMES})
git(guard, "add", "-A")
git(guard, "commit", "-q", "-m", "base")
write(guard, {n: "two\n" for n in NAMES})
listed = subprocess.run(["sh", TEST_GUARD, "HEAD", "-"], cwd=guard, input="",
                        capture_output=True, text=True).stdout.split()
by_guard = {n: n in listed for n in NAMES}
by_lint = {n: bool(lint_module.is_test_file(n)) for n in NAMES}
expect(by_guard == by_lint and any(by_guard.values()) and not all(by_guard.values()),
       "the lint counts a test file exactly as test-guard.sh does",
       str({n: (by_guard[n], by_lint[n]) for n in NAMES if by_guard[n] != by_lint[n]}))

# --- done --------------------------------------------------------------------------

for project in (py, node, npm, vitest, shell):
    expect(git(project.dir, "status", "--porcelain") == "" and
           git(project.dir, "rev-parse", "--abbrev-ref", "HEAD") == "main",
           "%s: the lint left the project's folder as it was" % os.path.basename(project.base))

if failures:
    print("ready-lint-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("ready-lint-rehearsal.sh: all checks passed")
PY
