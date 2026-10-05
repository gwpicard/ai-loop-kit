#!/usr/bin/env sh
# bar-guard-rehearsal.sh: run section-builder's bar guard in throwaway
# repositories and read every line it prints.
#
# A builder working alone can make a red check green without touching the code
# under test: edit the check, skip it, silence the linter on the line it trips,
# loosen a tool's settings, rewrite a snapshot, or change the project check or
# the gate itself. The bar guard lists each of those, one line each, with its
# kind and whether the piece named it on a `Changes the bar:` line. The gate
# refuses a piece with an unnamed one, so a guard that missed a kind would look
# the same as one that works until a weak piece went through.
#
# So each kind is made once here, alone, in a fresh copy of one repository, and
# the line is read back. Each kind is also named once, and the named column is
# read. A clean copy and the changes the guard must leave alone are the
# controls.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SCRIPTS="$ROOT/.agents/skills/section-builder/scripts"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$SCRIPTS" "$WORK" <<'PY'
import os
import re
import shutil
import subprocess
import sys

SCRIPTS, WORK = sys.argv[1], sys.argv[2]
GUARD = os.path.join(SCRIPTS, "bar-guard.sh")
TEST_GUARD = os.path.join(SCRIPTS, "test-guard.sh")

failures = []


def fail(message):
    failures.append(message)
    print("FAIL: " + message, file=sys.stderr)


def expect(condition, message, detail=""):
    if condition:
        print("ok: " + message)
    else:
        fail(message + ((" -- " + detail) if detail else ""))


if not os.path.isfile(GUARD):
    print("FAIL: section-builder carries no scripts/bar-guard.sh", file=sys.stderr)
    sys.exit(1)

ENV = dict(os.environ, GIT_AUTHOR_NAME="R", GIT_AUTHOR_EMAIL="r@example.invalid",
           GIT_COMMITTER_NAME="R", GIT_COMMITTER_EMAIL="r@example.invalid")


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


# --- the repository every case copies --------------------------------------
#
# origin/main holds an existing test of each language, a source file that
# already carries one suppression, the tool settings, a snapshot, the project
# check and the gate. The acceptance branch adds two checks in two commits, the
# second of them carrying a suppression of its own, and the build goes on from
# its tip.

SEED = os.path.join(WORK, "seed")
REMOTE = os.path.join(WORK, "remote.git")
os.makedirs(SEED)
git(SEED, "init", "-q", "-b", "main")
write(SEED, {
    "app/orders.py": "def total():\n    return 10\n",
    "app/legacy.py": "import os  # noqa\n\n\ndef old():\n    return os.sep\n",
    "tests/test_orders.py": "def test_total():\n    assert True\n",
    "web/cart.test.js": "it('adds', () => { expect(1).toBe(1) })\n",
    "pkg/cart_test.go": "package pkg\n\nfunc TestCart(t *testing.T) {}\n",
    "jest.config.js": "module.exports = {\n  testMatch: ['**/*.test.js'],\n};\n",
    "pyproject.toml": "[tool.ruff]\nline-length = 100\nselect = ['E', 'F']\n",
    "web/__snapshots__/cart.test.js.snap": "exports[`cart 1`] = `one`;\n",
    ".github/workflows/checks.yml": "on: pull_request\njobs: {}\n",
    ".agents/tools/gate.py": "print('gate')\n",
    "README.md": "A shop.\n",
})
git(SEED, "add", "-A")
git(SEED, "commit", "-q", "-m", "first upload")
subprocess.run(["git", "init", "-q", "--bare", REMOTE], check=True)
git(SEED, "remote", "add", "origin", REMOTE)
git(SEED, "push", "-q", "origin", "main")
git(SEED, "fetch", "-q", "origin")
BASE = git(SEED, "rev-parse", "origin/main")

git(SEED, "checkout", "-q", "-b", "spec/12-refunds")
write(SEED, {"tests/test_refund.py": "def test_refund():\n    assert refund() == 10\n"})
git(SEED, "add", "-A")
git(SEED, "commit", "-q", "-m", "first check")
FIRST_CHECK = git(SEED, "rev-parse", "HEAD")
write(SEED, {"tests/test_refund_total.py":
             "from app.orders import total  # noqa\n\n\ndef test_refund_total():\n"
             "    assert total() == 0\n"})
git(SEED, "add", "-A")
git(SEED, "commit", "-q", "-m", "second check")
SPEC = git(SEED, "rev-parse", "HEAD")
git(SEED, "push", "-q", "origin", "spec/12-refunds")

PIECE = """## So that
A refund returns the whole amount.

## Done when
- A refund returns the whole amount. Check: tests/test_refund.py

<details><summary>Under the hood</summary>

Build the refund beside the order total.
{hood}

</details>
"""

copies = [0]


def copy():
    copies[0] += 1
    repo = os.path.join(WORK, "case-%d" % copies[0])
    shutil.copytree(SEED, repo, symlinks=True)
    return repo


def guard(repo, hood="", spec=SPEC, base=BASE):
    args = ["sh", GUARD, base, "-"] + ([spec] if spec else [])
    done = subprocess.run(args, cwd=repo, input=PIECE.format(hood=hood),
                          capture_output=True, text=True, env=ENV)
    rows = [tuple(line.split("\t")) for line in done.stdout.splitlines() if line.strip()]
    return done.returncode, rows, done.stderr


def one_case(what, files=None, remove=(), hood="", spec=SPEC, setup=None):
    repo = copy()
    if files:
        write(repo, files)
    for path in remove:
        os.remove(os.path.join(repo, path))
    if setup:
        setup(repo)
    return guard(repo, hood, spec)


# --- the clean control ---------------------------------------------------------

code, rows, err = one_case("clean")
expect(code == 0 and rows == [], "a build that changed nothing guarded lists nothing and exits 0",
       "exit %s rows %r err %r" % (code, rows, err))

# A change to source code alone is not guarded.
code, rows, err = one_case("source", {"app/orders.py": "def total():\n    return 11\n"})
expect(code == 0 and rows == [], "a change to source code alone lists nothing",
       "exit %s rows %r err %r" % (code, rows, err))

# --- each kind, alone, unnamed -------------------------------------------------

KINDS = []


def kind_case(kind, path, what, files=None, remove=(), setup=None):
    code, rows, err = one_case(what, files, remove, setup=setup)
    expect(code == 1 and (kind, path, "not named") in rows,
           "%s: listed as %s, not named, and the guard exits 1" % (what, kind),
           "exit %s rows %r err %r" % (code, rows, err))
    KINDS.append((kind, path, files, remove, setup))
    return code, rows, err


# An acceptance check: the check the first of the two spec commits added is
# edited, and the one the second added is deleted.
kind_case("acceptance-check", "tests/test_refund.py", "a check from the first spec commit edited",
          {"tests/test_refund.py": "def test_refund():\n    assert True\n"})
code, rows, err = one_case("a check from the second spec commit deleted",
                           remove=["tests/test_refund_total.py"])
expect(code == 1 and ("acceptance-check", "tests/test_refund_total.py", "not named") in rows,
       "a check from the second spec commit deleted: listed as acceptance-check",
       "exit %s rows %r" % (code, rows))

# An existing test, edited, deleted or moved.
kind_case("existing-test", "tests/test_orders.py", "an existing test edited",
          {"tests/test_orders.py": "def test_total():\n    pass\n"})
code, rows, err = one_case("an existing test deleted", remove=["pkg/cart_test.go"])
expect(code == 1 and ("existing-test", "pkg/cart_test.go", "not named") in rows,
       "an existing test deleted: listed as existing-test", "exit %s rows %r" % (code, rows))
code, rows, err = one_case("an existing test moved away from a test path",
                           setup=lambda r: git(r, "mv", "tests/test_orders.py", "app/kept.py"))
expect(code == 1 and ("existing-test", "tests/test_orders.py", "not named") in rows
       and "app/kept.py" in err,
       "a test moved away from a test path is listed under its old path, the new one on "
       "standard error", "exit %s rows %r err %r" % (code, rows, err))

# A skip or focus marker added to a test.
kind_case("skip-or-focus", "web/cart.test.js", "a focus marker added to a test",
          {"web/cart.test.js": "it.only('adds', () => { expect(1).toBe(1) })\n"})
for marker, path, text in (
        ("xit(", "web/cart.test.js", "xit('adds', () => { expect(1).toBe(1) })\n"),
        (".skip(", "web/cart.test.js", "it.skip('adds', () => { expect(1).toBe(1) })\n"),
        ("@pytest.mark.skip", "tests/test_orders.py",
         "import pytest\n\n\n@pytest.mark.skip\ndef test_total():\n    assert True\n"),
        ("@unittest.skip", "tests/test_orders.py",
         "import unittest\n\n\n@unittest.skip('later')\ndef test_total():\n    assert True\n"),
        ("t.Skip(", "pkg/cart_test.go",
         "package pkg\n\nfunc TestCart(t *testing.T) { t.Skip(\"later\") }\n")):
    code, rows, err = one_case("the %s marker" % marker, {path: text})
    expect(code == 1 and ("skip-or-focus", path, "not named") in rows,
           "the %s marker added to a test is listed as skip-or-focus" % marker,
           "exit %s rows %r" % (code, rows))

# A lint or type suppression added.
kind_case("suppression", "app/orders.py", "a suppression added to source code",
          {"app/orders.py": "def total():  # type: ignore\n    return 10\n"})
for marker, path, text in (
        ("eslint-disable", "web/cart.js", "// eslint-disable-next-line\nvar a = 1\n"),
        ("@ts-ignore", "web/cart.ts", "// @ts-ignore\nconst a: number = 'x'\n"),
        ("@ts-expect-error", "web/cart.ts", "// @ts-expect-error\nconst a: number = 'x'\n"),
        ("# noqa", "app/orders.py", "import os  # noqa\n\n\ndef total():\n    return 10\n"),
        ("# pylint: disable", "app/orders.py",
         "def total():  # pylint: disable=invalid-name\n    return 10\n"),
        ("//nolint", "pkg/cart.go", "package pkg\n\nvar a = 1 //nolint\n")):
    code, rows, err = one_case("the %s suppression" % marker, {path: text})
    expect(code == 1 and ("suppression", path, "not named") in rows,
           "the %s suppression added is listed as suppression" % marker,
           "exit %s rows %r" % (code, rows))

# A change to a test, lint, type-check or coverage tool's settings.
kind_case("tool-settings", "jest.config.js", "a line added to the Jest settings",
          {"jest.config.js": "module.exports = {\n  testMatch: ['**/*.test.js'],\n"
                             "  testPathIgnorePatterns: ['refund'],\n};\n"})
for path in ("vitest.config.ts", "eslint.config.mjs", ".eslintrc.json", "tsconfig.build.json",
             ".coveragerc", "setup.cfg", "ruff.toml", "mypy.ini"):
    code, rows, err = one_case("a new %s" % path, {path: "ignore = everything\n"})
    expect(code == 1 and ("tool-settings", path, "not named") in rows,
           "a new %s is listed as tool-settings" % path, "exit %s rows %r" % (code, rows))
code, rows, err = one_case("pyproject.toml gains a line",
                           {"pyproject.toml": "[tool.ruff]\nline-length = 100\n"
                                              "select = ['E', 'F']\nignore = ['F401']\n"})
expect(code == 1 and ("tool-settings", "pyproject.toml", "not named") in rows,
       "a line added to pyproject.toml is listed as tool-settings",
       "exit %s rows %r" % (code, rows))

# A settings line taken out, with nothing added, is a change to the settings
# too: taking out `select` loosens the linter as surely as an ignore line.
SETTING_OUT = {"pyproject.toml": "[tool.ruff]\nline-length = 100\n"}
code, rows, err = one_case("a settings line taken out", SETTING_OUT)
expect(code == 1 and rows == [("tool-settings", "pyproject.toml", "not named")],
       "a settings line taken out with nothing added is listed as tool-settings, not named",
       "exit %s rows %r" % (code, rows))
code, rows, err = one_case("a settings line taken out, named", SETTING_OUT,
                           hood="Changes the bar: pyproject.toml, because the rule set moved.")
expect(code == 0 and rows == [("tool-settings", "pyproject.toml", "named")],
       "the same line taken out and named on a Changes the bar line is listed as named",
       "exit %s rows %r" % (code, rows))
code, rows, err = one_case("a settings file deleted", remove=["jest.config.js"])
expect(code == 1 and ("tool-settings", "jest.config.js", "not named") in rows,
       "a settings file deleted is listed as tool-settings", "exit %s rows %r" % (code, rows))

# An updated snapshot: one that existed at the base and changed.
kind_case("snapshot", "web/__snapshots__/cart.test.js.snap", "an existing snapshot rewritten",
          {"web/__snapshots__/cart.test.js.snap": "exports[`cart 1`] = `two`;\n"})

# The project check, a workflow, the gate and its scripts, the hooks and the
# deny rules.
kind_case("guarded-file", ".agents/tools/gate.py", "the gate script changed",
          {".agents/tools/gate.py": "print('gate, but kinder')\n"})
for path in (".github/workflows/checks.yml", ".agents/hooks/state-guard.sh",
             ".githooks/pre-commit", ".husky/pre-push", ".claude/settings.json"):
    code, rows, err = one_case("a change to %s" % path, {path: "changed\n"})
    expect(code == 1 and ("guarded-file", path, "not named") in rows,
           "a change to %s is listed as guarded-file" % path, "exit %s rows %r" % (code, rows))

# --- each kind, named ----------------------------------------------------------
#
# Every listed line says named or not named. An acceptance check is never
# named: it changes only by being reported. The others count as named on a
# Changes the bar line under Under the hood that gives the whole path and a
# reason.

for kind, path, files, remove, setup in KINDS:
    repo = copy()
    if files:
        write(repo, files)
    for gone in remove:
        os.remove(os.path.join(repo, gone))
    if setup:
        setup(repo)
    code, rows, err = guard(repo, hood="Changes the bar: %s, because the case asks for it." % path)
    if kind == "acceptance-check":
        expect(code == 1 and (kind, path, "not named") in rows,
               "an acceptance check named on a Changes the bar line is still not named",
               "exit %s rows %r" % (code, rows))
    else:
        expect(code == 0 and (kind, path, "named") in rows,
               "%s named on a Changes the bar line: listed as named, and the guard exits 0" % kind,
               "exit %s rows %r err %r" % (code, rows, err))

# A Changes the bar line with no reason names nothing, and neither does the
# same path elsewhere in Under the hood, for the kinds the bar guard adds.
SETTINGS = {"jest.config.js": "module.exports = {\n  testMatch: ['**/*.test.js'],\n"
                              "  bail: false,\n};\n"}
for hood, what in (("Changes the bar: jest.config.js", "a Changes the bar line with no reason"),
                   ("It changes `jest.config.js`, because the refund tests need it.",
                    "the path elsewhere in Under the hood")):
    repo = copy()
    write(repo, SETTINGS)
    code, rows, err = guard(repo, hood=hood)
    expect(code == 1 and ("tool-settings", "jest.config.js", "not named") in rows,
           "%s does not name a settings change" % what, "exit %s rows %r" % (code, rows))
# The same line outside Under the hood names nothing either.
repo = copy()
write(repo, SETTINGS)
done = subprocess.run(["sh", GUARD, BASE, "-", SPEC], cwd=repo, env=ENV, capture_output=True,
                      text=True, input=PIECE.format(hood="") +
                      "\nChanges the bar: jest.config.js, because it is outside.\n")
expect(done.returncode == 1 and "tool-settings\tjest.config.js\tnot named" in done.stdout,
       "a Changes the bar line outside Under the hood names nothing", repr(done.stdout))

# An existing test keeps test-guard.sh's naming rule: Under the hood naming it
# by its whole path.
code, rows, err = one_case("an existing test named by test-guard's rule",
                           {"tests/test_orders.py": "def test_total():\n    pass\n"},
                           hood="Changes the bar: tests/test_orders.py, because the total moved.")
expect(code == 0 and ("existing-test", "tests/test_orders.py", "named") in rows,
       "an existing test named in Under the hood is listed as named",
       "exit %s rows %r" % (code, rows))

# --- what the guard leaves alone -----------------------------------------------

# A suppression or a skip marker taken out. A settings line taken out is
# listed, below, since taking out a setting can loosen a tool as surely as
# adding one.
code, rows, err = one_case("a suppression taken out",
                           {"app/legacy.py": "import os\n\n\ndef old():\n    return os.sep\n"})
expect(code == 0 and rows == [], "a suppression taken out is not listed",
       "exit %s rows %r" % (code, rows))
# A line edited beside a suppression it already carried adds none.
code, rows, err = one_case("a line edited beside its suppression",
                           {"app/legacy.py": "import os  # noqa\n\n\ndef old():\n"
                                             "    return os.sep + os.sep\n"})
expect(code == 0 and rows == [], "an edit that keeps an existing suppression is not listed",
       "exit %s rows %r" % (code, rows))
# A new snapshot for a new test is not an updated one.
code, rows, err = one_case("a new snapshot",
                           {"web/__snapshots__/refund.test.js.snap": "exports[`r 1`] = `x`;\n"})
expect(code == 0 and rows == [], "a new snapshot file is not listed",
       "exit %s rows %r" % (code, rows))
# The suppression the acceptance branch itself carries is the bar, not the build.
expect(not any(r[1] == "tests/test_refund_total.py" for r in guard(copy())[1]),
       "a suppression the acceptance branch added is not listed")
# A new test file the build adds changes no existing test.
code, rows, err = one_case("a new test file",
                           {"tests/test_receipt.py": "def test_receipt():\n    assert True\n"})
expect(code == 0 and rows == [], "a new test file the build adds is not listed",
       "exit %s rows %r" % (code, rows))

# --- with no spec commit -------------------------------------------------------
#
# A goal or gauntlet piece has no acceptance branch, so the guard is called
# without one and lists no acceptance-check kind, even where a file the branch
# added has changed.
code, rows, err = one_case("no spec commit",
                           {"tests/test_refund.py": "def test_refund():\n    assert True\n"},
                           spec=None)
# With no spec commit the two checks are files the build added, so neither is an
# existing test. The second carries a suppression of its own, which is then
# listed like any other added suppression, and nothing else is.
expect(code == 1 and rows == [("suppression", "tests/test_refund_total.py", "not named")],
       "called without a spec commit, the guard lists no acceptance check, only the "
       "suppression the second check carries", "exit %s rows %r" % (code, rows))

# --- when it cannot run --------------------------------------------------------

done = subprocess.run(["sh", GUARD, "no-such-base", "-", SPEC], cwd=copy(), env=ENV, input="",
                      capture_output=True, text=True)
expect(done.returncode == 2 and done.stderr.strip(), "a base that is no commit exits 2 and says so",
       repr(done.stderr))
done = subprocess.run(["sh", GUARD, BASE, "-", "no-such-commit"], cwd=copy(), env=ENV, input="",
                      capture_output=True, text=True)
expect(done.returncode == 2, "a spec commit that is no commit exits 2", repr(done.stderr))
done = subprocess.run(["sh", GUARD, BASE], cwd=copy(), env=ENV, input="",
                      capture_output=True, text=True)
expect(done.returncode == 2, "a call with no piece exits 2", repr(done.stderr))
outside = os.path.join(WORK, "not-a-project")
os.makedirs(outside)
done = subprocess.run(["sh", GUARD, BASE, "-"], cwd=outside, env=ENV, input="",
                      capture_output=True, text=True)
expect(done.returncode == 2, "outside a Git folder the guard exits 2", repr(done.stderr))

# --- one rule for a test file --------------------------------------------------
#
# The bar guard decides what a test file is in its own copy of test-guard.sh's
# rule, since a marker counts only in a test. The two copies must not drift.


def is_test_body(path):
    with open(path) as handle:
        text = handle.read()
    match = re.search(r"^is_test\(\) \{\n(.*?)^\}", text, re.S | re.M)
    return match.group(1) if match else None


expect(is_test_body(GUARD) is not None and is_test_body(GUARD) == is_test_body(TEST_GUARD),
       "bar-guard.sh counts a test file exactly as test-guard.sh does")

if failures:
    print("bar-guard-rehearsal.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("bar-guard-rehearsal.sh: all checks passed")
PY
