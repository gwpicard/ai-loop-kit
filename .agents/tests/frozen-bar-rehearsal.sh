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
# map, so a change outside the piece's boundary goes to the person. A gate that
# let any of that through would look the same as one that works, until a piece
# passed a bar it had lowered itself.
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
with open(os.path.join(TOOLS, "ready-lint.py"), "w") as handle:
    handle.write("print('Ready-gate lint: no gaps.')\n")
GATE = os.path.join(TOOLS, "gate.py")

STATE = os.path.join(WORK, "gh-state.json")
LOG = os.path.join(WORK, "gh.log")
ENV = dict(os.environ, GIT_AUTHOR_NAME="R", GIT_AUTHOR_EMAIL="r@example.invalid",
           GIT_COMMITTER_NAME="R", GIT_COMMITTER_EMAIL="r@example.invalid",
           FAKE_GH_STATE=STATE, FAKE_GH_LOG=LOG)
ENV["PATH"] = FAKE + os.pathsep + ENV["PATH"]


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


AREAS = ("# Working rules\n\n## Areas\n\n- billing: app/billing\n- shop: app/shop\n"
         "- tests: tests\n- project records: docs\n")


def seed(name, first_upload):
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
    write(repo, {"tests/test_refund.py": "def test_refund():\n    assert False\n"})
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the check")
    git(repo, "push", "-q", "origin", "spec/12-refunds")
    git(repo, "fetch", "-q", "origin")
    return repo


SEED = seed("seed", {
    "README.md": "A shop.\n",
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
build(repo, {"tests/test_orders.py": "def test_orders():\n    assert 1 == 1\n"})
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
build(repo, {"app/shop/cart.py": "def cart():\n    return [1]\n",
             "lib/util.py": "def util():\n    return 1\n",
             "docs/working-rules.md": AREAS + "- library: lib\n"})
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
NOCODE = seed("nocode", {"README.md": "A shop, to be.\n", "docs/working-rules.md": AREAS})
repo = project(NOCODE)
made_ready(repo, piece_body())
build(repo, {"app/billing/refund.py": "def refund():\n    return 10\n"})
code, out, err = gate(repo, "move", "12", "in-review")
expect(contract_comments(12)[0][1] == git(NOCODE, "rev-parse", "origin/spec/12-refunds")
       and code == 0 and labels_of(12) == IN_REVIEW,
       "a project whose origin/main holds only the first upload is measured from it",
       "comments %r exit %s out %r err %r" % (contract_comments(12), code, out, err))

# --- the evidence folder stays on this computer ---------------------------------

with open(os.path.join(FOUNDATION, "gitignore")) as handle:
    ignored = handle.read().splitlines()
expect(".agents/pieces/" in ignored, "a founded project's gitignore keeps .agents/pieces/ out")

if failures:
    print("frozen-bar-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("frozen-bar-rehearsal.sh: all checks passed")
PY
