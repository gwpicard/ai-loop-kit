#!/usr/bin/env sh
# frozen-bar-rehearsal.sh: drive the gate script against the replay harness's
# stand-in GitHub and prove a piece is built against the bar it was made ready
# with.
#
# When the gate makes a piece ready it posts the contract's hash on the issue,
# with the commit that holds the acceptance checks. Before every attempt, and
# again before the piece goes to review, the gate reads the contract again. A
# contract that changed while the piece was being built sends it back to spec.
# At the move to review the gate runs the bar guard and refuses a change to the
# bar the piece did not name, and it places every changed path in the area
# map, so a change outside the piece's boundary goes to the person. Then it
# runs every check itself, on the commit as it stands and, for a build piece,
# at the spec commit too, and records each run in a chained evidence record. A
# gate that let any of that through would look the same as one that works,
# until a piece passed a bar it had lowered itself.
#
# Nothing here reaches the network. The stand-in keeps its state in a file, and
# each project is a throwaway Git folder with a bare repository as its origin.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation"
SCRIPTS="$ROOT/.agents/skills/section-builder/scripts"
FAKE="$ROOT/.agents/tests/replay/fake-github"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$FOUNDATION" "$SCRIPTS" "$FAKE" "$WORK" <<'PY'
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

FOUNDATION, SCRIPTS, FAKE, WORK = sys.argv[1:5]

failures = []


def fail(message):
    failures.append(message)
    print("FAIL: " + message, file=sys.stderr)


def expect(condition, message, detail=""):
    if condition:
        print("ok: " + message)
    else:
        fail(message + ((" -- " + detail) if detail else ""))


for path in (os.path.join(FOUNDATION, "gate.py"), os.path.join(SCRIPTS, "bar-guard.sh"),
             os.path.join(SCRIPTS, "test-guard.sh"), os.path.join(FOUNDATION, "area-map.py")):
    if not os.path.isfile(path):
        print("FAIL: missing %s" % path, file=sys.stderr)
        sys.exit(1)

# The gate runs from a folder laid out as founding leaves .agents/tools: the
# gate, the bar guard and the test guard it wraps, the area map script, and a
# stand-in ready-gate lint that passes. The lint has its own rehearsal.
TOOLS = os.path.join(WORK, "tools")
os.makedirs(TOOLS)
for source in (os.path.join(FOUNDATION, "gate.py"), os.path.join(FOUNDATION, "area-map.py"),
               os.path.join(SCRIPTS, "bar-guard.sh"), os.path.join(SCRIPTS, "test-guard.sh")):
    shutil.copy(source, TOOLS)
# The stand-in is the real lint with its command replaced, since the gate also
# reads the lint's test-command reader and runner reports when it runs checks.
with open(os.path.join(FOUNDATION, "ready-lint.py")) as handle:
    real_lint = handle.read()
COMMAND = 'if __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))'
if COMMAND not in real_lint:
    print("FAIL: the ready-gate lint no longer ends with its command line", file=sys.stderr)
    sys.exit(1)
with open(os.path.join(TOOLS, "ready-lint.py"), "w") as handle:
    handle.write(real_lint.replace(COMMAND, 'if __name__ == "__main__":\n'
                                            '    print("Ready-gate lint: no gaps.")'))
GATE = os.path.join(TOOLS, "gate.py")

STATE = os.path.join(WORK, "gh-state.json")
LOG = os.path.join(WORK, "gh.log")
ENV = dict(os.environ, GIT_AUTHOR_NAME="R", GIT_AUTHOR_EMAIL="r@example.invalid",
           GIT_COMMITTER_NAME="R", GIT_COMMITTER_EMAIL="r@example.invalid",
           FAKE_GH_STATE=STATE, FAKE_GH_LOG=LOG)
ENV["PATH"] = FAKE + os.pathsep + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
# The gate runs the piece's checks with the project's Test command, which here
# is pytest. Where this computer has none, it goes into a throwaway environment.
if subprocess.run(["python3", "-m", "pytest", "--version"], capture_output=True,
                  env=ENV).returncode != 0:
    print("  pytest is not here, installing it into a throwaway environment")
    venv = os.path.join(WORK, "venv")
    subprocess.run([sys.executable, "-m", "venv", venv], check=True)
    subprocess.run([os.path.join(venv, "bin", "pip"), "install", "--quiet", "pytest"], check=True)
    ENV["PATH"] = FAKE + os.pathsep + os.path.join(venv, "bin") + os.pathsep + os.environ["PATH"]


def git(repo, *args):
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=ENV)
    if done.returncode != 0:
        raise SystemExit("git %s failed: %s" % (" ".join(args), done.stderr))
    return done.stdout.strip()


def write(repo, files):
    for path, text in files.items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as handle:
            handle.write(text)


# The project's own instructions name the command that runs its tests, and its
# gitignore keeps out what a test run leaves behind and what the gate records.
AGENTS = ("# AGENTS.md\n\n## Stack, and how to run and check it\n\n"
          "Test command: python3 -m pytest -q -p no:cacheprovider\n")
GITIGNORE = "__pycache__/\n.agents/pieces/\n.agents/worktrees/\n"

# The acceptance check fails on its assertion until the refund returns 10,
# whether or not the refund's module exists yet.
REFUND_CHECK = ("import importlib\n\n\ndef test_refund():\n    try:\n"
                "        module = importlib.import_module('app.billing.refund')\n"
                "    except ImportError:\n        module = None\n"
                "    assert module is not None and module.refund() == 10\n")
REFUND = {"app/billing/refund.py": "def refund():\n    return 10\n"}

AREAS = ("# Working rules\n\n## Areas\n\n- billing: app/billing\n- shop: app/shop\n"
         "- tests: tests\n- project records: docs\n")


def seed(name, first_upload, check=None):
    """A project whose origin/main holds the first upload, with an acceptance
    branch cut from it holding one check, checked out in the project folder."""
    repo = os.path.join(WORK, name)
    remote = os.path.join(WORK, name + ".git")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    write(repo, first_upload)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "first upload")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
    git(repo, "remote", "add", "origin", remote)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "spec/12-refunds")
    write(repo, check or {"tests/test_refund.py": REFUND_CHECK})
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the check")
    git(repo, "push", "-q", "origin", "spec/12-refunds")
    git(repo, "fetch", "-q", "origin")
    return repo


SEED = seed("seed", {
    "README.md": "A shop.\n",
    "AGENTS.md": AGENTS,
    ".gitignore": GITIGNORE,
    "docs/working-rules.md": AREAS,
    "app/billing/refund.py": "def refund():\n    return 0\n",
    "app/shop/cart.py": "def cart():\n    return []\n",
    "tests/test_orders.py": "def test_orders():\n    assert True\n",
    "jest.config.js": "module.exports = {};\n",
})
SPEC_TIP = git(SEED, "rev-parse", "origin/spec/12-refunds")

copies = [0]


def project(source=SEED):
    copies[0] += 1
    repo = os.path.join(WORK, "project-%d" % copies[0])
    shutil.copytree(source, repo, symlinks=True)
    return repo


def build(repo, files, message="build"):
    write(repo, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


# --- the piece -------------------------------------------------------------------

READY = ("## Readiness\n2026-10-05, checked by a session that did not shape it: Ready\n"
         "- NOTE 3: the totals are rounded.\n")


def piece_body(hood="Build the refund beside the order total.",
               loop="Loop module: build\nAcceptance branch: spec/12-refunds",
               works="A refund returns the whole amount. Check: tests/test_refund.py"):
    return ("## So that\nA shop owner can refund an order.\n\n"
            "## Done when\n### Works\n- %s\n\n"
            "## Loop\n%s\n\n"
            "## Reach\nBoundary: billing, tests\nReaches: none\n\n"
            "<details><summary>Under the hood</summary>\n\n%s\n\n</details>\n\n"
            "%s" % (works, loop, hood, READY))


def fresh(issues, pulls=(), faults=None):
    state = {"repo": "rehearsal/project", "next": 900, "issues": issues,
             "pull_requests": list(pulls)}
    if faults:
        state["faults"] = faults
    with open(STATE, "w") as handle:
        json.dump(state, handle)
    if os.path.exists(LOG):
        os.remove(LOG)


def issue(number, labels, body, comments=(), assignees=()):
    return {"number": number, "title": "Refunds", "body": body, "state": "open",
            "labels": list(labels), "assignees": list(assignees), "blocked_by": [],
            "sub_issues": [], "comments": list(comments)}


def load():
    with open(STATE) as handle:
        return json.load(handle)


def find(number):
    return next(i for i in load()["issues"] if i["number"] == number)


def labels_of(number):
    return sorted(find(number)["labels"])


def comments_of(number):
    return [c if isinstance(c, str) else c.get("body", "") for c in find(number).get("comments", [])]


def set_faults(faults):
    state = load()
    state["faults"] = faults
    with open(STATE, "w") as handle:
        json.dump(state, handle)


def set_body(number, body):
    state = load()
    for item in state["issues"]:
        if item["number"] == number:
            item["body"] = body
    with open(STATE, "w") as handle:
        json.dump(state, handle)


def calls():
    if not os.path.exists(LOG):
        return []
    with open(LOG) as handle:
        return [line.split("\t", 1)[1].strip() for line in handle if line.startswith("CALL\t")]


def gate(repo, *args):
    done = subprocess.run([sys.executable, GATE, *args], cwd=repo, env=ENV,
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


CONTRACT = re.compile(r"<!-- loop:contract sha256=([0-9a-f]+) commit=(\S+) -->")


def contract_comments(number):
    return [m.groups() for c in comments_of(number) for m in CONTRACT.finditer(c)]


def expected_hash(body):
    """The hash as the gate's help describes it: the body without the sections
    the system writes later and without the comment markers, each line's
    trailing spaces dropped, and blank lines at either end dropped. A heading
    inside a fenced code block is not a heading."""
    kept = []
    skipping = False
    fence = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        heading = None if fence else re.match(r"^(#{1,3})\s+(.*?)\s*$", line)
        if heading:
            skipping = heading.group(2).lower() in ("kickback", "readiness", "learned")
        if skipping or re.match(r"^\s*<!-- loop:[a-z-]+.*-->\s*$", line):
            continue
        kept.append(line.rstrip())
    text = "\n".join(kept).strip("\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SHAPED = ["state:shaping", "shaping:check", "type:feature", "loop:build"]


def made_ready(repo, body, number=12, loop_label="loop:build"):
    """The piece made ready by the gate and claimed, as a build starts."""
    labels = ["state:shaping", "shaping:check", "type:feature", loop_label]
    fresh([issue(number, labels, body)],
          pulls=[{"number": 1, "title": "Refunds", "body": "Closes #%d" % number,
                  "head": "spec/12-refunds", "base": "main", "state": "OPEN"}])
    ready = gate(repo, "move", str(number), "ready")
    claim = gate(repo, "move", str(number), "building", "--assignee", "me")
    return ready, claim


# --- the hash posted at ready ----------------------------------------------------

repo = project()
body = piece_body()
fresh([issue(12, SHAPED, body)])
code, out, err = gate(repo, "move", "12", "ready")
posted = contract_comments(12)
expect(code == 0 and labels_of(12) == ["loop:build", "state:ready", "type:feature"],
       "the move to ready passes", "exit %s out %r err %r" % (code, out, err))
expect(len(posted) == 1 and re.fullmatch(r"[0-9a-f]{64}", posted[0][0]) is not None,
       "the move to ready posts one loop:contract comment with a sha256 hash", repr(posted))
expect(posted and posted[0][1] == SPEC_TIP,
       "its commit= value is the tip of the acceptance branch", repr(posted))
expect(posted and posted[0][0] == expected_hash(find(12)["body"]),
       "the hash covers the body without Kickback, Readiness, Learned and the markers",
       repr(posted))
order = [c.split(" ")[0] + " " + c.split(" ")[1] for c in calls()
         if c.startswith(("issue comment", "issue edit"))]
expect(order[:2] == ["issue comment", "issue edit"],
       "the hash comment is posted before the labels move", repr(order))

# A piece with no acceptance branch, such as a goal piece, says commit=none.
repo = project()
fresh([issue(13, ["state:shaping", "shaping:check", "type:feature", "loop:goal"],
             piece_body(loop="Loop module: goal\nMeasured by: tests/test_speed.py"))])
code, out, err = gate(repo, "move", "13", "ready")
posted = contract_comments(13)
expect(code == 0 and len(posted) == 1 and posted[0][1] == "none",
       "a piece with no acceptance branch gets commit=none", "%r %r %r" % (posted, out, err))

# A comment GitHub refuses leaves the piece where it was, so no ready piece
# ever goes without its hash.
repo = project()
fresh([issue(12, SHAPED, body)], faults={"refuse_comment": True})
code, out, err = gate(repo, "move", "12", "ready")
expect(code != 0 and labels_of(12) == sorted(SHAPED) and not contract_comments(12),
       "a refused hash comment refuses the move, and the labels stay",
       "exit %s out %r err %r" % (code, out, err))

# --- check-contract ---------------------------------------------------------------

repo = project()
body = piece_body()
made_ready(repo, body)
code, out, err = gate(repo, "check-contract", "12")
expect(code == 0 and len([l for l in out.splitlines() if l.strip()]) == 1,
       "check-contract passes in one line on an unchanged contract",
       "exit %s out %r err %r" % (code, out, err))

# The sections the system writes during a build, and the markers, are left out.
for what, changed in (
        ("a Kickback section added",
         body + "\n## Kickback\nTried twice; the rounding needs a decision.\n"),
        ("the Readiness section rewritten",
         body.replace("the totals are rounded", "the totals are rounded to pence")),
        ("a Learned section added", body + "\n## Learned\nRefunds round down.\n"),
        ("a marker line added",
         body + "\n<!-- loop:gate sub-state=spec since=2026-10-05 answer=abc -->\n")):
    set_body(12, changed)
    code, out, err = gate(repo, "check-contract", "12")
    expect(code == 0 and labels_of(12) == ["loop:build", "state:building", "type:feature"],
           "check-contract passes with %s" % what, "exit %s out %r err %r" % (code, out, err))
set_body(12, body)

# Two hash comments after a kickback and a second ready: the newest is read.
state = load()
state["issues"][0]["comments"].insert(0, {"id": 5, "body":
                                          "<!-- loop:contract sha256=%s commit=none -->"
                                          % ("0" * 64)})
with open(STATE, "w") as handle:
    json.dump(state, handle)
code, out, err = gate(repo, "check-contract", "12")
expect(code == 0, "with two hash comments, check-contract reads the newest",
       "exit %s out %r err %r" % (code, out, err))

# A contract that changed while the piece was being built goes back to spec,
# with a Kickback section saying so, and its branch stays.
set_body(12, body.replace("returns the whole amount", "returns half the amount"))
code, out, err = gate(repo, "check-contract", "12")
now = find(12)["body"]
expect(code != 0 and labels_of(12) == ["loop:build", "shaping:spec", "state:shaping",
                                        "type:feature"],
       "a contract changed mid-build is moved by the gate to shaping:spec",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))
expect("## Kickback" in now and "The contract changed while it was being built" in now,
       "and it carries a Kickback section saying the contract changed", repr(now[-300:]))
expect("spec/12-refunds" in git(repo, "branch", "--list", "spec/12-refunds"),
       "and its branch is kept")

# A piece made ready before the hash existed: the hash is recorded now.
repo = project()
fresh([issue(12, ["state:building", "type:feature", "loop:build"], body, assignees=["me"])])
code, out, err = gate(repo, "check-contract", "12")
said = [l for l in (out + err).splitlines() if l.strip()]
expect(code == 0 and len(said) == 1 and "record" in said[0].lower()
       and len(contract_comments(12)) == 1,
       "a contract with no hash comment has it recorded now, said in one line",
       "exit %s said %r" % (code, said))

# GitHub out of reach: the gate refuses and says so, and never reads a missing
# hash as unchanged.
set_faults({"offline": True})
code, out, err = gate(repo, "check-contract", "12")
expect(code != 0 and "github" in (out + err).lower(),
       "check-contract with GitHub out of reach refuses and says GitHub could not be reached",
       "exit %s out %r err %r" % (code, out, err))
fresh([issue(12, SHAPED, body)], faults={"offline": True})
code, out, err = gate(repo, "move", "12", "ready")
expect(code != 0 and "github" in (out + err).lower(),
       "the move to ready with GitHub out of reach refuses and says so",
       "exit %s out %r err %r" % (code, out, err))

# --- the move to review ---------------------------------------------------------


def forced(repo, number=12):
    path = os.path.join(repo, ".agents", "pieces", str(number), "forced.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


IN_REVIEW = ["loop:build", "review:person", "state:in-review", "type:feature"]
BUILDING = ["loop:build", "state:building", "type:feature"]

# A build inside its boundary, with nothing guarded changed, moves and forces
# nothing. A changelog file and a file at the root are inside every boundary.
repo = project()
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n",
             "changes/12-refunds.md": "- Refunds return the whole amount.\n",
             "NOTES.md": "notes\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code == 0 and labels_of(12) == IN_REVIEW and forced(repo) == [],
       "a build inside its boundary moves to review and forces nothing",
       "exit %s labels %r forced %r out %r err %r" % (code, labels_of(12), forced(repo), out, err))

# A settings change the piece did not name is refused, naming the file and
# saying to put it back.
repo = project()
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n",
             "jest.config.js": "module.exports = { bail: false };\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "jest.config.js" in out + err
       and "put" in (out + err).lower() and "back" in (out + err).lower(),
       "an unnamed settings change is refused, naming the file and saying to put it back",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))

# The same change named on a Changes the bar line passes the guard and forces
# the person's review, with the reason recorded and posted.
repo = project()
made_ready(repo, piece_body(hood="Build the refund.\nChanges the bar: jest.config.js, because "
                                 "the refund tests need a longer timeout."))
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n",
             "jest.config.js": "module.exports = { testTimeout: 10000 };\n"})
code, out, err = gate(repo, "move", "12", "in-review")
lines = forced(repo)
expect(code == 0 and labels_of(12) == IN_REVIEW,
       "a named settings change moves to review with review:person",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))
expect(any(l.get("reason") == "guard_change" and "jest.config.js" in l.get("detail", "")
           and l.get("source") for l in lines),
       "forced.jsonl records the named change as guard_change, with its source", repr(lines))
expect(any("jest.config.js" in c for c in comments_of(12) if "loop:contract" not in c),
       "the reasons are posted on the issue as one comment", repr(comments_of(12)))

# An existing test, edited without being named, is refused; named, it passes
# and forces the person's review.
repo = project()
made_ready(repo, piece_body())
build(repo, {"tests/test_orders.py": "def test_orders():\n    pass\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_orders.py" in out + err,
       "an unnamed edit to an existing test is refused, naming it",
       "exit %s out %r err %r" % (code, out, err))
repo = project()
made_ready(repo, piece_body(hood="Build the refund.\nChanges the bar: tests/test_orders.py, "
                                 "because orders now subtract refunds."))
build(repo, dict(REFUND, **{"tests/test_orders.py": "def test_orders():\n    assert 1 == 1\n"}))
code, out, err = gate(repo, "move", "12", "in-review")
expect(code == 0 and labels_of(12) == IN_REVIEW and any(
    l.get("reason") == "guard_change" and "tests/test_orders.py" in l.get("detail", "")
    for l in forced(repo)),
       "a named edit to an existing test moves and forces the person's review",
       "exit %s forced %r out %r err %r" % (code, forced(repo), out, err))

# An acceptance check edited by the build is refused.
repo = project()
made_ready(repo, piece_body())
build(repo, {"tests/test_refund.py": "def test_refund():\n    assert True\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_refund.py" in out + err,
       "an acceptance check the build edited is refused", "exit %s out %r err %r"
       % (code, out, err))

# A path in another area and one in no area each force the person's review,
# with the path and its area, and never refuse. The map is read from the base.
repo = project()
made_ready(repo, piece_body())
build(repo, dict(REFUND, **{"app/shop/cart.py": "def cart():\n    return [1]\n",
                         "lib/util.py": "def util():\n    return 1\n",
                         "docs/working-rules.md": AREAS + "- library: lib\n"}))
code, out, err = gate(repo, "move", "12", "in-review")
lines = [l for l in forced(repo) if l.get("reason") == "outside_boundary"]
expect(code == 0 and labels_of(12) == IN_REVIEW,
       "a build outside its boundary still moves to review", "exit %s out %r err %r"
       % (code, out, err))
expect(any("app/shop/cart.py" in l["detail"] and "shop" in l["detail"] for l in lines),
       "a path in another area is forced with its area", repr(lines))
expect(any("lib/util.py" in l["detail"] and "unclaimed" in l["detail"] for l in lines),
       "a path in no area at the base is forced as unclaimed, whatever the branch's map says",
       repr(lines))
expect(not any("app/billing" in l["detail"] for l in lines),
       "a path inside the boundary is not forced", repr(lines))
expect(any("cart.py" in c and "lib/util.py" in c for c in comments_of(12)),
       "the boundary reasons are posted on the issue", repr(comments_of(12)))

# The contract changed during the build: the move to review sends the piece
# back to spec instead.
repo = project()
body = piece_body()
made_ready(repo, body)
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n"})
set_body(12, body.replace("returns the whole amount", "returns nothing"))
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and "shaping:spec" in labels_of(12),
       "a contract changed during the build is caught again at the move to review",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))

# --- not the normal case ------------------------------------------------------------

# A goal piece with no acceptance branch: the guard runs without a spec commit,
# so a test file the build adds is not an acceptance check, and the piece moves.
repo = project()
goal = piece_body(loop="Loop module: goal\nMeasured by: tests/test_speed.py")
ready, claim = made_ready(repo, goal, loop_label="loop:goal")
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n",
             "tests/test_speed.py": "def test_speed():\n    assert True\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(contract_comments(12) and contract_comments(12)[-1][1] == "none" and code == 0
       and "state:in-review" in labels_of(12),
       "a goal piece is recorded with commit=none and moves to review",
       "ready %r exit %s out %r err %r" % (ready, code, out, err))

# A project with no code yet: origin/main holds only the first upload, and the
# acceptance branch is cut from it as on any project.
NOCODE = seed("nocode", {"README.md": "A shop, to be.\n", "docs/working-rules.md": AREAS,
                         "AGENTS.md": AGENTS, ".gitignore": GITIGNORE})
repo = project(NOCODE)
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(contract_comments(12)[0][1] == git(NOCODE, "rev-parse", "origin/spec/12-refunds")
       and code == 0 and labels_of(12) == IN_REVIEW,
       "a project whose origin/main holds only the first upload is measured from it",
       "comments %r exit %s out %r err %r" % (contract_comments(12), code, out, err))

# --- the evidence record ------------------------------------------------------------
#
# The gate runs a check itself and records what happened, in the main folder's
# .agents/pieces/<number>/evidence.jsonl. Before a piece goes to review it runs
# every check again on the commit as it stands, and the acceptance checks at
# the spec commit too, so what the builder says counts for nothing.

PYTEST = "python3 -m pytest -q -p no:cacheprovider"
FIELDS = ("command", "exit", "commit", "clean", "time", "phase")


def evidence(main, number=12):
    path = os.path.join(main, ".agents", "pieces", str(number), "evidence.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        found = []
        for line in handle:
            try:
                found.append(json.loads(line))
            except ValueError:
                found.append({"unreadable": line})
        return found


def evidence_path(main, number=12):
    return os.path.join(main, ".agents", "pieces", str(number), "evidence.jsonl")


def head(repo):
    return git(repo, "rev-parse", "HEAD")


def run_lines(lines, phase=None, check=None):
    return [l for l in lines if "command" in l and (phase is None or l.get("phase") == phase)
            and (check is None or check in l.get("command", ""))]


# gate.py evidence runs the command in the folder that has the piece's branch,
# and appends one line with the command, its exit code, the commit, whether
# the tree was clean, the time and the phase.
repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
code, out, err = gate(repo, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "tests/test_refund.py")
lines = evidence(repo)
expect(code == 0 and len(lines) == 1 and all(f in lines[0] for f in FIELDS),
       "gate.py evidence appends one line with the command, exit code, commit, clean tree, "
       "time and phase", "exit %s lines %r out %r err %r" % (code, lines, out, err))
expect(lines and lines[0]["exit"] == 0 and lines[0]["commit"] == head(repo)
       and lines[0]["clean"] is True and lines[0]["phase"] == "after"
       and "tests/test_refund.py" in lines[0]["command"],
       "the line records the check passing on the current commit with a clean tree, phase after",
       repr(lines))
expect(lines and len(json.dumps(lines[0])) < 1000,
       "the line stays short, with the command's output kept in a file", repr(lines))

# A dirty tree is recorded as not clean.
with open(os.path.join(repo, "app", "billing", "refund.py"), "a") as handle:
    handle.write("# a change nobody saved\n")
code, out, err = gate(repo, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "tests/test_refund.py")
lines = evidence(repo)
expect(code == 0 and len(lines) == 2 and lines[1]["clean"] is False,
       "a run on a tree with unsaved changes is recorded as not clean", repr(lines))
git(repo, "checkout", "--", "app/billing/refund.py")

# The before phase runs at the spec commit, where the check fails.
code, out, err = gate(repo, "evidence", "12", "--phase", "before", "--", "python3", "-m",
                      "pytest", "-q", "-p", "no:cacheprovider", "tests/test_refund.py")
lines = evidence(repo)
expect(code == 0 and lines and lines[-1]["phase"] == "before"
       and lines[-1]["commit"] == SPEC_TIP and lines[-1]["exit"] != 0,
       "a before run is made at the spec commit and records the check failing there",
       "exit %s lines %r out %r err %r" % (code, lines[-1:], out, err))

# A line changed by hand is refused: each line carries a hash chained to the
# one before it, and the gate writes nothing more on a record it did not write.
path = evidence_path(repo)
os.makedirs(os.path.dirname(path), exist_ok=True)
text = open(path).read() if os.path.exists(path) else '{"exit": 0}\n'
first = json.loads(text.splitlines()[0])
forged = text.replace('"exit": %d' % first["exit"], '"exit": 7', 1)
with open(path, "w") as handle:
    handle.write(forged)
code, out, err = gate(repo, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "tests/test_refund.py")
expect(code != 0 and "evidence.jsonl" in out + err and "not written by the gate" in out + err,
       "a line edited by hand is refused as one the gate did not write",
       "exit %s out %r err %r" % (code, out, err))
with open(path) as handle:
    expect(handle.read() == forged, "and the refused record is left as it was")
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "not written by the gate" in out + err,
       "the move to review refuses on a record holding a line the gate did not write",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))

# A cut-off last line is an interrupted write, not a forged one.
repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
gate(repo, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
     "tests/test_refund.py")
os.makedirs(os.path.dirname(evidence_path(repo)), exist_ok=True)
with open(evidence_path(repo), "a") as handle:
    handle.write('{"command": "python3 -m pyte')
code, out, err = gate(repo, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "tests/test_refund.py")
lines = evidence(repo)
expect(code == 0 and "interrupted" in (out + err).lower() and len(lines) == 2,
       "a cut-off last line is set aside as an interrupted write and the record carries on",
       "exit %s lines %r out %r err %r" % (code, lines, out, err))

# Run from a run's worktree, the record still lands in the main folder, so a
# worktree never holds it and never counts it as unsaved work.
repo = project()
made_ready(repo, piece_body())
git(repo, "checkout", "-q", "main")
tree = os.path.join(repo, ".agents", "worktrees", "12-refunds")
git(repo, "worktree", "add", "-q", tree, "spec/12-refunds")
build(tree, REFUND)
code, out, err = gate(tree, "evidence", "12", "--", "python3", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "tests/test_refund.py")
lines = evidence(repo)
expect(code == 0 and len(lines) == 1 and lines[0]["commit"] == head(tree)
       and lines[0]["exit"] == 0,
       "gate.py evidence run from a worktree runs there and records in the main folder",
       "exit %s lines %r out %r err %r" % (code, lines, out, err))
expect(not os.path.exists(os.path.join(tree, ".agents", "pieces")),
       "and the worktree holds no record of its own")

# --- the gate runs the checks itself before review --------------------------------

# A passing piece moves, and the record holds the gate's own runs: the
# acceptance check on the current commit, the Test command, the check at the
# spec commit failing, and a line saying the type check and linter are left
# to the project check on GitHub.
repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
code, out, err = gate(repo, "move", "12", "in-review")
lines = evidence(repo)
now = head(repo)
expect(code == 0 and labels_of(12) == IN_REVIEW,
       "a piece whose checks pass when the gate runs them moves to review",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))
expect(any(l.get("phase") == "after" and "tests/test_refund.py" in l.get("command", "")
           and l.get("exit") == 0 and l.get("commit") == now and l.get("clean") is True
           for l in lines),
       "the gate ran the acceptance check on the current commit with a clean tree", repr(lines))
expect(any(l.get("phase") == "after" and l.get("command", "").strip() == PYTEST
           and l.get("exit") == 0 and l.get("commit") == now for l in lines),
       "the gate ran the project's Test command on the current commit", repr(lines))
expect(any(l.get("phase") == "before" and "tests/test_refund.py" in l.get("command", "")
           and l.get("exit") not in (0, None) and l.get("commit") == SPEC_TIP for l in lines),
       "the gate ran the acceptance check at the spec commit and saw it fail", repr(lines))
expect(any("type check" in str(l.get("note", "")).lower() for l in lines),
       "the record says the type check and linter are left to the project check on GitHub",
       repr(lines))

# A builder that claims done with one check red is refused, and no hook runs
# here: the gate's own run holds the rule.
repo = project()
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 5\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_refund.py" in out + err
       and "next:" in err,
       "with no hook, a piece whose acceptance check is red is refused, naming the check "
       "and the next action", "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))
expect(any("tests/test_refund.py" in l.get("command", "") and l.get("exit") not in (0, None)
           for l in run_lines(evidence(repo), "after")),
       "and the red run is in the record", repr(evidence(repo)))

# A guard check named under Reaches is run too, and a red one refuses.
CART = seed("cart", {
    "README.md": "A shop.\n", "AGENTS.md": AGENTS, ".gitignore": GITIGNORE,
    "docs/working-rules.md": AREAS, "app/billing/refund.py": "def refund():\n    return 0\n",
    "app/shop/cart.py": "def cart():\n    return []\n",
    "tests/test_cart.py": "from app.shop.cart import cart\n\n\n"
                          "def test_cart():\n    assert cart() == []\n"})
repo = project(CART)
made_ready(repo, piece_body().replace(
    "Reaches: none", "Reaches: shop: guarded by `tests/test_cart.py`"))
build(repo, dict(REFUND, **{"app/shop/cart.py": "def cart():\n    return [1]\n"}))
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_cart.py" in out + err,
       "a red guard check named under Reaches refuses the move, naming it",
       "exit %s out %r err %r" % (code, out, err))

# The tree must be clean: a change nobody saved is refused, never run.
repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
with open(os.path.join(repo, "app", "billing", "refund.py"), "a") as handle:
    handle.write("# not saved\n")
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "clean" in (out + err).lower()
       and "app/billing/refund.py" in out + err,
       "a tree with unsaved changes is refused at the move to review, naming the file",
       "exit %s out %r err %r" % (code, out, err))

# A check the piece names that is not there is refused as missing.
repo = project()
made_ready(repo, piece_body(works="A refund returns the whole amount. Check: "
                                  "tests/test_refund.py\n- Credit is kept. Check: "
                                  "tests/test_credit.py"))
build(repo, REFUND)
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_credit.py" in out + err
       and "missing" in (out + err).lower(),
       "a check the piece names and the branch does not hold is refused as missing",
       "exit %s out %r err %r" % (code, out, err))

# A check that passes only on a retry is recorded as a failure, never a pass.
repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
flag = os.path.join(WORK, "flaky-once")
flaky = ("test -f %s || { touch %s; exit 1; }; %s tests/test_refund.py" % (flag, flag, PYTEST))
gate(repo, "evidence", "12", "--", "sh", "-c", flaky)
gate(repo, "evidence", "12", "--", "sh", "-c", flaky)
lines = run_lines(evidence(repo), "after", "tests/test_refund.py")
expect([l["exit"] for l in lines] == [1, 0],
       "a check that fails and then passes on the same commit is recorded as both runs",
       repr(lines))
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "retry" in (out + err).lower()
       and "tests/test_refund.py" in out + err,
       "a check that passed only on a retry refuses the move to review",
       "exit %s out %r err %r" % (code, out, err))

# At the spec commit a build piece's check must fail on its assertion. One
# that fails on a missing module is refused by name, and so is one that passes.
IMPORTING = seed("importing", {
    "README.md": "A shop.\n", "AGENTS.md": AGENTS, ".gitignore": GITIGNORE,
    "docs/working-rules.md": AREAS, "app/billing/refund.py": "def refund():\n    return 0\n"},
    check={"tests/test_refund.py": "from app.billing.credit import credit\n\n\n"
                                   "def test_refund():\n    assert credit() == 10\n"})
repo = project(IMPORTING)
made_ready(repo, piece_body())
build(repo, {"app/billing/credit.py": "def credit():\n    return 10\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "tests/test_refund.py" in out + err
       and "not on its assertion" in out + err,
       "a check that fails at the spec commit on a failed import is refused, naming it",
       "exit %s out %r err %r" % (code, out, err))
PASSING = seed("passing", {
    "README.md": "A shop.\n", "AGENTS.md": AGENTS, ".gitignore": GITIGNORE,
    "docs/working-rules.md": AREAS, "app/billing/refund.py": "def refund():\n    return 10\n"})
repo = project(PASSING)
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 10  # unchanged\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels_of(12) == BUILDING and "passes at the spec commit" in out + err,
       "a check that already passes at the spec commit is refused",
       "exit %s out %r err %r" % (code, out, err))

# A goal piece has no before run, and its record says so in one line.
repo = project()
made_ready(repo, piece_body(loop="Loop module: goal\nMeasured by: tests/test_speed.py"),
           loop_label="loop:goal")
build(repo, REFUND)
code, out, err = gate(repo, "move", "12", "in-review")
lines = evidence(repo)
notes = [l for l in lines if l.get("phase") == "before"]
expect(code == 0 and len(notes) == 1 and "command" not in notes[0]
       and "no before run" in str(notes[0].get("note", "")),
       "a goal piece has no before run, and its record says so in one line",
       "exit %s lines %r out %r err %r" % (code, lines, out, err))

# A build piece made ready with no acceptance branch: the checks written first
# count from the commit that holds them, and the before run uses that commit.
repo = project()
git(repo, "checkout", "-q", "-b", "build/14-totals", "main")
no_branch = piece_body(loop="Loop module: build",
                       works="The total adds the refund. Check: tests/test_total.py")
fresh([issue(14, ["state:shaping", "shaping:check", "type:feature", "loop:build"], no_branch)],
      pulls=[{"number": 2, "title": "Totals", "body": "Closes #%d" % 14,
              "head": "build/14-totals", "base": "main", "state": "OPEN"}])
gate(repo, "move", "14", "ready")
gate(repo, "move", "14", "building", "--assignee", "me")
build(repo, {"tests/test_total.py": "from app.billing.refund import refund\n\n\n"
                                    "def test_total():\n    assert refund() + 1 == 11\n"},
      "the checks, first")
checks_commit = head(repo)
build(repo, REFUND)
code, out, err = gate(repo, "move", "14", "in-review")
before = [l for l in evidence(repo, 14) if l.get("phase") == "before" and "command" in l]
expect(code == 0 and before and before[0]["commit"] == checks_commit and before[0]["exit"] != 0,
       "a build piece with no acceptance branch runs its before check at the commit that "
       "holds the checks", "exit %s before %r out %r err %r" % (code, before, out, err))

# The same piece, with its check edited after the commit that first holds it:
# the gate gives the bar guard that commit, so the edit is refused as an
# acceptance check edit, just as it would be on an acceptance branch.
repo = project()
git(repo, "checkout", "-q", "-b", "build/14-totals", "main")
fresh([issue(14, ["state:shaping", "shaping:check", "type:feature", "loop:build"], no_branch)],
      pulls=[{"number": 2, "title": "Totals", "body": "Closes #%d" % 14,
              "head": "build/14-totals", "base": "main", "state": "OPEN"}])
gate(repo, "move", "14", "ready")
gate(repo, "move", "14", "building", "--assignee", "me")
build(repo, {"tests/test_total.py": "from app.billing.refund import refund\n\n\n"
                                    "def test_total():\n    assert refund() + 1 == 11\n"},
      "the checks, first")
build(repo, REFUND)
build(repo, {"tests/test_total.py": "def test_total():\n    assert True\n"}, "loosen")
code, out, err = gate(repo, "move", "14", "in-review")
expect(code != 0 and labels_of(14) == BUILDING
       and "acceptance-check: tests/test_total.py" in out + err,
       "a build piece with no acceptance branch whose check is edited after the commit that "
       "first holds it is refused as an acceptance check edit",
       "exit %s labels %r out %r err %r" % (code, labels_of(14), out, err))

# A goal piece is unaffected: the guard still runs without a spec commit, so a
# test the build added and then changed is not an acceptance check.
repo = project()
made_ready(repo, piece_body(loop="Loop module: goal\nMeasured by: tests/test_speed.py"),
           loop_label="loop:goal")
build(repo, {"tests/test_speed.py": "def test_speed():\n    assert 1 + 1 == 2\n"}, "measure")
build(repo, dict(REFUND, **{"tests/test_speed.py": "def test_speed():\n    assert True\n"}))
code, out, err = gate(repo, "move", "12", "in-review")
expect(code == 0 and "state:in-review" in labels_of(12),
       "a goal piece whose test changed after its own commit still moves to review",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))

# --- a breakage of the changed code, run through the gate -------------------------
#
# Once the checks pass, the build breaks the code it changed on purpose, saves
# each breakage as a patch and has the gate run a check against it. The gate
# applies the patch in a temporary worktree at the commit as it stands, so the
# piece's own folder never holds broken code, and records the run.


def worktrees(repo):
    return [l for l in git(repo, "worktree", "list", "--porcelain").splitlines()
            if l.startswith("worktree ")]


repo = project()
made_ready(repo, piece_body())
build(repo, REFUND)
with open(os.path.join(repo, "app", "billing", "refund.py"), "w") as handle:
    handle.write("def refund():\n    return 0\n")
patch = os.path.join(WORK, "refund-zero.patch")
with open(patch, "w") as handle:
    handle.write(git(repo, "diff") + "\n")
git(repo, "checkout", "--", "app/billing/refund.py")
before_trees = worktrees(repo)
code, out, err = gate(repo, "evidence", "12", "--breakage", patch, "--", PYTEST,
                      "tests/test_refund.py")
lines = [l for l in evidence(repo) if l.get("phase") == "breakage"]
with open(patch, "rb") as handle:
    patch_hash = hashlib.sha256(handle.read()).hexdigest()
expect(code == 0 and len(lines) == 1 and lines[0].get("patch") == patch_hash
       and lines[0].get("exit") not in (0, None) and lines[0].get("commit") == head(repo),
       "a breakage run is one line with phase breakage, the patch's hash, the exit code and the "
       "current commit", "exit %s lines %r out %r err %r" % (code, lines, out, err))
expect(git(repo, "status", "--porcelain") == "" and worktrees(repo) == before_trees,
       "the breakage ran in a temporary worktree that is gone again, and the piece's folder "
       "is untouched", "%r %r" % (git(repo, "status", "--porcelain"), worktrees(repo)))

# A patch that does not apply at the commit as it stands is refused by name,
# and nothing is recorded.
stale = os.path.join(WORK, "stale.patch")
with open(stale, "w") as handle:
    handle.write("--- a/app/billing/refund.py\n+++ b/app/billing/refund.py\n"
                 "@@ -1,2 +1,2 @@\n def refund():\n-    return 99\n+    return 98\n")
count = len(evidence(repo))
code, out, err = gate(repo, "evidence", "12", "--breakage", stale, "--", PYTEST,
                      "tests/test_refund.py")
expect(code != 0 and "stale.patch" in out + err and "does not apply" in out + err
       and "next:" in err and len(evidence(repo)) == count and worktrees(repo) == before_trees,
       "a breakage patch that does not apply is refused by name, and nothing is recorded",
       "exit %s out %r err %r" % (code, out, err))

# --- whose hash comment counts ----------------------------------------------------
#
# Anybody who can comment on the issue can post a loop:contract line. Only the
# account that added state:ready to the piece is trusted, read from the issue's
# label events, so a later hash posted by somebody else cannot move the bar.

repo = project()
body = piece_body()
made_ready(repo, body)
state = load()
state["issues"][0]["comments"].append({"id": 98, "author": "intruder", "body":
                                       "<!-- loop:contract sha256=%s commit=none -->"
                                       % ("0" * 64)})
with open(STATE, "w") as handle:
    json.dump(state, handle)
code, out, err = gate(repo, "check-contract", "12")
expect(code == 0 and labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "a later hash comment by another account is ignored, and the trusted one is read",
       "exit %s labels %r out %r err %r" % (code, labels_of(12), out, err))

repo = project()
fresh([issue(12, ["state:building", "type:feature", "loop:build"], body, assignees=["me"],
             comments=[{"id": 97, "author": "intruder", "body":
                        "<!-- loop:contract sha256=%s commit=none -->" % expected_hash(body)}])])
state = load()
state["issues"][0]["events"] = [{"id": 1, "event": "labeled", "actor": "replay-person",
                                 "label": "state:ready"}]
with open(STATE, "w") as handle:
    json.dump(state, handle)
code, out, err = gate(repo, "check-contract", "12")
said = [l for l in (out + err).splitlines() if l.strip()]
expect(code == 0 and len(said) == 1 and "record" in said[0].lower()
       and len(contract_comments(12)) == 2,
       "a piece whose only hash comment is by another account is treated as having none, and "
       "one is recorded now", "exit %s said %r comments %r" % (code, said, comments_of(12)))

# --- the evidence folder stays on this computer ---------------------------------

with open(os.path.join(FOUNDATION, "gitignore")) as handle:
    ignored = handle.read().splitlines()
expect(".agents/pieces/" in ignored, "a founded project's gitignore keeps .agents/pieces/ out")

if failures:
    print("frozen-bar-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("frozen-bar-rehearsal.sh: all checks passed")
PY
