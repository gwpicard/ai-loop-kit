#!/usr/bin/env sh
# test-strength-rehearsal.sh: show a weak test missing a real boundary error,
# and the gate reading what the breakages showed.
#
# The first half breaks a throwaway project's code by hand and reads the
# one-line report the shipped rule gives. The second half runs the gate a
# founded project receives, against the replay harness's stand-in GitHub. Once
# a piece's acceptance checks pass, the build breaks the code it changed on
# purpose and runs each breakage through `gate.py evidence --breakage`. At the
# move to review the gate reads those runs: an acceptance check that failed on
# none of them sends the piece to the person, a project with a runner and no
# breakage recorded is refused, and a project with no runner gets one line
# saying its checks were not tested that way.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

node - "$ROOT" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = process.argv[2];
const project = fs.mkdtempSync(path.join(os.tmpdir(), 'test-strength-'));
const sourceFile = path.join(project, 'delivery.cjs');
const testFile = path.join(project, 'delivery.test.cjs');
const pieceFile = path.join(project, 'piece.md');
const original = 'module.exports = total => total >= 50;\n';
const breakages = [
  {
    source: 'module.exports = total => total > 50;\n',
    miss: 'An order of exactly 50 lost free delivery, and the tests still passed.',
  },
  {
    source: 'module.exports = total => total < 50;\n',
    miss: 'Free delivery was given to small orders instead of larger ones.',
  },
];

function runTest() {
  const result = spawnSync(process.execPath, [testFile], {
    cwd: project,
    encoding: 'utf8',
    timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'a stopped run must not count as a catch');
  return result;
}

try {
  fs.writeFileSync(sourceFile, original);
  fs.writeFileSync(testFile, [
    "const assert = require('node:assert/strict');",
    "const hasFreeDelivery = require('./delivery.cjs');",
    'assert.equal(hasFreeDelivery(49), false);',
    'assert.equal(hasFreeDelivery(51), true);',
    '',
  ].join('\n'));
  assert.equal(runTest().status, 0, 'the unchanged behaviour must pass');

  let caught = 0;
  const misses = [];
  for (const breakage of breakages) {
    fs.writeFileSync(sourceFile, breakage.source);
    const syntax = spawnSync(process.execPath, ['--check', sourceFile]);
    assert.equal(syntax.status, 0, 'each deliberate breakage must be valid code');
    const result = runTest();
    if (result.status === 0) {
      misses.push(breakage.miss);
      const boundary = spawnSync(process.execPath, ['-e',
        "process.stdout.write(String(require('./delivery.cjs')(50)))"], {
        cwd: project, encoding: 'utf8',
      });
      assert.equal(boundary.status, 0);
      assert.equal(boundary.stdout, 'false', 'the missed change must damage behaviour');
    } else {
      assert.equal(result.status, 1);
      assert.match(result.stderr, /AssertionError/);
      caught += 1;
    }
  }
  assert.equal(caught, 1, 'the tests must catch one deliberate breakage');
  assert.equal(misses.length, 1, 'the weak test must miss the boundary error');

  fs.writeFileSync(pieceFile, '# Check free delivery\n\n## Worth knowing\n\n'
    + misses.map(miss => `- ${miss}`).join('\n') + '\n');
  assert.match(fs.readFileSync(pieceFile, 'utf8'), /exactly 50 lost free delivery/);

  fs.writeFileSync(sourceFile, original);
  assert.equal(runTest().status, 0, 'the intact code must still pass afterwards');
  console.log('test-strength-rehearsal.sh: weak-test miss and observed report passed');
} finally {
  for (const file of [sourceFile, testFile, pieceFile]) {
    if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  fs.rmdirSync(project);
}
NODE

FOUNDATION="$ROOT/kit/scripts"
SCRIPTS="$ROOT/kit/scripts"
FAKE="$ROOT/tests/stand-ins/fake-github"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$FOUNDATION" "$SCRIPTS" "$FAKE" "$WORK" <<'PY'
import json
import os
import shutil
import subprocess
import sys

FOUNDATION, SCRIPTS, FAKE, WORK = sys.argv[1:5]
failures = []


def expect(condition, message, detail=""):
    if condition:
        print("ok: " + message)
    else:
        failures.append(message)
        print("FAIL: " + message + ((" -- " + detail) if detail else ""), file=sys.stderr)


# The gate runs from a folder laid out as founding leaves .agents/tools, with
# the real ready-gate lint, whose readers the gate uses, made to pass.
TOOLS = os.path.join(WORK, "tools")
os.makedirs(TOOLS)
for source in (os.path.join(FOUNDATION, "gate.py"), os.path.join(FOUNDATION, "area-map.py"),
               os.path.join(SCRIPTS, "bar-guard.sh"), os.path.join(SCRIPTS, "test-guard.sh")):
    shutil.copy(source, TOOLS)
with open(os.path.join(FOUNDATION, "ready-lint.py")) as handle:
    lint = handle.read()
COMMAND = 'if __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))'
if COMMAND not in lint:
    print("FAIL: the ready-gate lint no longer ends with its command line", file=sys.stderr)
    sys.exit(1)
with open(os.path.join(TOOLS, "ready-lint.py"), "w") as handle:
    handle.write(lint.replace(COMMAND, 'if __name__ == "__main__":\n'
                                       '    print("Ready-gate lint: no gaps.")'))
GATE = os.path.join(TOOLS, "gate.py")
STATE = os.path.join(WORK, "gh-state.json")
ENV = dict(os.environ, GIT_AUTHOR_NAME="R", GIT_AUTHOR_EMAIL="r@example.invalid",
           GIT_COMMITTER_NAME="R", GIT_COMMITTER_EMAIL="r@example.invalid",
           FAKE_GH_STATE=STATE, FAKE_GH_LOG=os.path.join(WORK, "gh.log"),
           PYTHONDONTWRITEBYTECODE="1")
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


# Free delivery from 50. The acceptance check is weak: it tries 49 and 51 and
# never 50, so it fails at the spec commit on its assertion and passes once the
# rule is built, yet it cannot tell >= 50 from > 50.
CHECK = ("const test = require('node:test');\nconst assert = require('node:assert/strict');\n"
         "const free = require('../src/delivery.cjs');\n\n"
         "test('free delivery from 50', () => {\n  assert.equal(free(49), false);\n"
         "  assert.equal(free(51), true);\n});\n")
BUILT = "module.exports = total => total >= 50;\n"
BOUNDARY = "module.exports = total => total > 50;\n"
BACKWARDS = "module.exports = total => total < 50;\n"
CHECK_PATH = "tests/delivery.test.cjs"
RUN_CHECK = "node --test " + CHECK_PATH


def seed(name, runner):
    """A project on origin/main, with an acceptance branch holding the check."""
    repo = os.path.join(WORK, name)
    remote = repo + ".git"
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    package = {"name": "shop", "private": True, "scripts": {"test": "node --test"}}
    if runner:
        package["devDependencies"] = {"@stryker-mutator/core": "^8.0.0"}
    write(repo, {
        "package.json": json.dumps(package, indent=2) + "\n",
        "AGENTS.md": "# AGENTS.md\n\n## Stack, and how to run and check it\n\n"
                     "Test command: node --test\n",
        ".gitignore": ".agents/pieces/\n.agents/worktrees/\nnode_modules/\n",
        "docs/working-rules.md": "# Working rules\n\n## Areas\n\n- delivery: src\n"
                                 "- tests: tests\n- project records: docs\n",
        "src/delivery.cjs": "module.exports = total => false;\n",
    })
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "first upload")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
    git(repo, "remote", "add", "origin", remote)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "spec/12-delivery")
    write(repo, {CHECK_PATH: CHECK})
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the check")
    git(repo, "push", "-q", "origin", "spec/12-delivery")
    git(repo, "fetch", "-q", "origin")
    return repo


BODY = ("## So that\nA big order ships free.\n\n"
        "## Done when\n### Works\n- An order of 50 or more ships free. Check: %s\n\n"
        "## Loop\nLoop module: build\nAcceptance branch: spec/12-delivery\n\n"
        "## Reach\nBoundary: delivery, tests\nReaches: none\n\n"
        "<details><summary>Under the hood</summary>\n\nChange the delivery rule.\n\n"
        "</details>\n\n## Readiness\n2026-10-05: Ready\n" % CHECK_PATH)


def gate(repo, *args):
    done = subprocess.run([sys.executable, GATE, *args], cwd=repo, env=ENV,
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def built_piece(name, runner):
    """The piece made ready, claimed and built, with its check passing."""
    repo = seed(name, runner)
    with open(STATE, "w") as handle:
        json.dump({"repo": "rehearsal/shop", "next": 900, "pull_requests": [
            {"number": 1, "title": "Free delivery", "body": "Closes #%d" % 12,
             "head": "spec/12-delivery", "base": "main", "state": "OPEN"}],
            "issues": [{"number": 12, "title": "Free delivery", "body": BODY,
                        "state": "open", "assignees": [], "blocked_by": [],
                        "sub_issues": [], "comments": [], "labels": [
                            "state:shaping", "shaping:check", "type:feature",
                            "loop:build"]}]}, handle)
    for move in (("move", "12", "ready"), ("move", "12", "building", "--assignee", "me")):
        code, out, err = gate(repo, *move)
        if code != 0:
            raise SystemExit("could not set the piece up: %s %s" % (out, err))
    write(repo, {"src/delivery.cjs": BUILT})
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "free delivery from 50")
    return repo


def break_as(repo, source, name):
    """Save one breakage of the changed code as a patch, and put the code back."""
    write(repo, {"src/delivery.cjs": source})
    patch = os.path.join(WORK, name)
    with open(patch, "w") as handle:
        handle.write(git(repo, "diff") + "\n")
    git(repo, "checkout", "--", "src/delivery.cjs")
    return patch


def labels():
    with open(STATE) as handle:
        return sorted(json.load(handle)["issues"][0]["labels"])


def read_jsonl(repo, name):
    path = os.path.join(repo, ".agents", "pieces", "12", name)
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


BUILDING = ["loop:build", "state:building", "type:feature"]
IN_REVIEW = ["loop:build", "review:person", "state:in-review", "type:feature"]

# A project with a runner and no breakage recorded on the current commit is
# refused, and the refusal names the next action.
repo = built_piece("no-breakage", runner=True)
code, out, err = gate(repo, "move", "12", "in-review")
expect(code != 0 and labels() == BUILDING and "--breakage" in err and "next:" in err,
       "a project with a runner and no breakage line on the current commit is refused, "
       "naming the next action", "exit %s labels %r out %r err %r" % (code, labels(), out, err))

# The weak check run against the boundary breakage passes, so it failed on
# none of the breakages: the gate writes a weak_check line naming it, and the
# piece goes to the person.
repo = built_piece("weak", runner=True)
patch = break_as(repo, BOUNDARY, "boundary.patch")
code, out, err = gate(repo, "evidence", "12", "--breakage", patch, "--", RUN_CHECK)
broken = [l for l in read_jsonl(repo, "evidence.jsonl") if l.get("phase") == "breakage"]
expect(code == 0 and len(broken) == 1 and broken[0].get("exit") == 0,
       "the weak check passes with the boundary broken, and the run is recorded as a breakage",
       "exit %s lines %r out %r err %r" % (code, broken, out, err))
code, out, err = gate(repo, "move", "12", "in-review")
weak = [l for l in read_jsonl(repo, "forced.jsonl") if l.get("reason") == "weak_check"]
expect(code == 0 and labels() == IN_REVIEW,
       "the piece still moves to review: a missed breakage forces the person's review and "
       "never refuses", "exit %s labels %r out %r err %r" % (code, labels(), out, err))
expect(len(weak) == 1 and CHECK_PATH in weak[0].get("detail", "")
       and weak[0].get("source") == "evidence",
       "forced.jsonl names the acceptance check that missed the boundary error, as weak_check "
       "from evidence", repr(read_jsonl(repo, "forced.jsonl")))

# The same check with a second breakage it does catch failed on one of them,
# so nothing is forced.
repo = built_piece("caught", runner=True)
for source, name in ((BOUNDARY, "boundary-2.patch"), (BACKWARDS, "backwards.patch")):
    gate(repo, "evidence", "12", "--breakage", break_as(repo, source, name), "--", RUN_CHECK)
code, out, err = gate(repo, "move", "12", "in-review")
expect(code == 0 and not [l for l in read_jsonl(repo, "forced.jsonl")
                          if l.get("reason") == "weak_check"],
       "a check that failed on one of the breakages forces nothing",
       "exit %s forced %r out %r err %r" % (code, read_jsonl(repo, "forced.jsonl"), out, err))

# With neither StrykerJS nor mutmut among the project's dependencies, the gate
# writes one breakage line saying the checks were not tested that way, and
# nothing is forced.
repo = built_piece("no-runner", runner=False)
code, out, err = gate(repo, "move", "12", "in-review")
notes = [l for l in read_jsonl(repo, "evidence.jsonl") if l.get("phase") == "breakage"]
expect(code == 0 and labels() == IN_REVIEW, "with no runner the piece moves to review",
       "exit %s out %r err %r" % (code, out, err))
expect(len(notes) == 1 and "command" not in notes[0]
       and "not tested by breaking the code" in str(notes[0].get("note", "")),
       "the record holds one breakage line saying the checks were not tested by breaking "
       "the code", repr(notes))
expect(not read_jsonl(repo, "forced.jsonl"), "and nothing is forced",
       repr(read_jsonl(repo, "forced.jsonl")))

if failures:
    print("test-strength-rehearsal.sh: %d gate check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("test-strength-rehearsal.sh: the gate read every breakage as the rule says")
PY
