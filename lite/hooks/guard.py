#!/usr/bin/env python3
"""The guard: a Claude Code PreToolUse hook that warns early about hard rules.

It reads the tool call as JSON on stdin. Exit 2 refuses the call and prints
`refused:` and `next:` lines on stderr. Exit 0 lets it through, and so does
any input it cannot parse: the guard never blocks on its own error.

Everywhere: no push to main, master or the default branch (LITE_DEFAULT_BRANCH
names it), no force push, no recursive delete, no secret shape in written
content. When LITE_ROLE is set, also: no git push, merge, checkout, switch,
restore, apply or branch -f, no gh, no write to a path in LITE_LOCKED (newline
separated) or to a tracked test file, and the reviewer role writes nothing (the pass role writes only under .lite/pass/).

Known limits: this is a regular-expression check on the raw command, so it can
be routed around (a script, an alias, an unusual spelling). It is an early
warning, not the line. The real lines are the diff check in merge.py and
branch protection on the default branch. A bare `git push` from main is not
caught, because the guard does not ask git which branch is checked out.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys

SECRETS = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bghp_[A-Za-z0-9]{20,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b"
    r"|\bsk-ant-[A-Za-z0-9_-]{10,}|\bxox[bp]-[A-Za-z0-9-]{10,}")
GIT = r"\bgit(?:\s+(?:-C\s+\S+|-c\s+\S+|--\S+))*\s+"
DELETE = re.compile(r"\brm\s+(?:-\S+\s+)*(?:-\w*[rR]|--recursive)|\bfind\b.*-delete|\brmtree\b")
PUSH = re.compile(GIT + r"push\b([^;&|\n]*)")
FORCE = re.compile(r"(?:^|\s)(?:-[a-zA-Z]*f[a-zA-Z]*|--force\S*|--mirror|--all|\+\S*)(?=\s|$)")
ROLE_GIT = re.compile(GIT + r"(?:push|merge|checkout|switch|restore|apply|branch\s+(?:-\w*f|--force))\b")
GH = re.compile(r"(?<![\w.-])gh\b")
REDIRECT = re.compile(r"\d*>>?\|?\s*([^\s;&|<>()]+)|\btee\s+(?:-\S+\s+)*([^\s;&|<>()]+)")
TEST_NAMES = ["test_*", "*_test.*", "*.test.*", "*.spec.*"]
TEST_DIRS = {"tests", "test", "__tests__"}


class Refuse(Exception):
    def __init__(self, reason, step):
        super().__init__(reason)
        self.reason, self.step = reason, step


def git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                           text=True, timeout=10)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def check_everyone(command):
    if DELETE.search(command):
        raise Refuse("a recursive delete is not allowed",
                     "delete named files one at a time, or report it")
    branches = "|".join(["main", "master"] + [
        re.escape(b) for b in [os.environ.get("LITE_DEFAULT_BRANCH", "")] if b])
    protected = re.compile(r"(?:^|[\s:'\"=]|refs/heads/)(?:%s)(?=[\s'\"]|$)" % branches)
    for m in PUSH.finditer(command):
        if FORCE.search(m.group(1)):
            raise Refuse("a force, mirror or all-branch push is not allowed",
                         "push a normal fast-forward of your own branch")
        if protected.search(m.group(1)):
            raise Refuse("a push to the default branch is not allowed",
                         "push a feature branch and open a pull request")


def is_test_path(rel):
    parts = rel.split("/")
    return (any(fnmatch.fnmatch(parts[-1], p) for p in TEST_NAMES)
            or any(p in TEST_DIRS for p in parts[:-1]))


def check_path(path, role, cwd):
    code, top = git(["rev-parse", "--show-toplevel"], cwd)
    top = os.path.realpath(top if code == 0 and top else cwd)
    full = os.path.realpath(os.path.join(cwd, path))
    rel = os.path.relpath(full, top)
    if role == "reviewer" or (role == "pass" and not rel.startswith(".lite/pass/")):
        raise Refuse("the %s edits nothing%s" % (role, " outside .lite/pass/" if role == "pass" else ""),
                     "describe the change in the review instead")
    for locked in os.environ.get("LITE_LOCKED", "").splitlines():
        lfull = os.path.realpath(os.path.join(top, locked.strip()))
        if locked.strip() and (full == lfull or full.startswith(lfull + "/")):
            raise Refuse("%s is a locked test file" % rel,
                         "make the code pass the test; do not change the test")
    if is_test_path(rel) and git(["ls-files", "--error-unmatch", "--", full], cwd)[0] == 0:
        raise Refuse("%s is an existing test file" % rel,
                     "leave existing tests alone; add a new test file if needed")


def check_role_command(command, role, cwd):
    if ROLE_GIT.search(command) or GH.search(command):
        raise Refuse("git push, merge, branch changes and gh are not allowed in a %s session" % role,
                     "commit on your branch; the loop pushes and merges")
    for m in REDIRECT.finditer(command):
        target = (m.group(1) or m.group(2)).strip("'\"")
        if target and target != "/dev/null" and not target.startswith("&"):
            check_path(target, role, cwd)


def check(data):
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    cwd, role = data.get("cwd") or os.getcwd(), os.environ.get("LITE_ROLE", "")
    if tool == "Bash":
        command = inp.get("command") or ""
        check_everyone(command)
        if role:
            check_role_command(command, role, cwd)
        return
    if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return
    texts = [inp.get("content"), inp.get("new_string"), inp.get("new_source")]
    texts += [e.get("new_string") for e in inp.get("edits") or []]
    if any(isinstance(t, str) and SECRETS.search(t) for t in texts):
        raise Refuse("the content holds a secret shape",
                     "read the secret from the environment instead")
    if role:
        check_path(inp.get("file_path") or inp.get("notebook_path") or "", role, cwd)


def main():
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            check(data)
    except Refuse as r:
        sys.stderr.write("refused: %s\nnext: %s\n" % (r.reason, r.step))
        return 2
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
