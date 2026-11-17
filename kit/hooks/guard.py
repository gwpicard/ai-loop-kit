#!/usr/bin/env python3
"""The guard: a Claude Code PreToolUse hook that warns early about hard rules.

It reads the tool call as JSON on stdin. Exit 2 refuses the call and prints
`refused:` and `next:` lines on stderr. Exit 0 lets it through, and so does
any input it cannot parse: the guard never blocks on its own error. A Codex
session (LITE_AGENT=codex) is the exception: it sends shell commands and
apply_patch calls, and the guard refuses a payload or an error it cannot parse.

Everywhere: no push to main, master or the default branch (LITE_DEFAULT_BRANCH
names it), no force push, no recursive delete, no secret shape in written
content. When LITE_ROLE is set, also: no git push, merge, checkout, switch,
restore, apply or branch -f, no gh, no write to a path in LITE_LOCKED (newline
separated) or to a tracked test file (except an exact path in LITE_ALLOWED, for the builder only, that the stops list does not cover), and the reviewer role writes nothing in the project (scratch files in the system
temp folder are fine; the pass role writes only under .lite/pass/).

Known limits: this is a regular-expression check on the raw command, so it can
be routed around (a script, an alias, an unusual spelling). It is an early
warning, not the line. The real lines are the diff check in merge.py and
branch protection on the default branch. A bare `git push` from main is not
caught, because the guard does not ask git which branch is checked out.
"""
import json
import os
import re
import sys
import tempfile

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
    import common
    import merge  # the one definition of a test file
except Exception as e:
    sys.stderr.write("guard: cannot load, allowing the call: %s\n" % e)
    sys.exit(0)

SECRETS = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bghp_[A-Za-z0-9]{20,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b"
    r"|\bsk-ant-[A-Za-z0-9_-]{10,}|\bxox[bp]-[A-Za-z0-9-]{10,}")
GIT = r"\bgit(?:\s+(?:-C\s+\S+|-c\s+\S+|--\S+))*\s+"
DELETE = re.compile(r"\brm\s+(?:[^\s;&|]+\s+)*?(?:-\w*[rR]\w*|--recursive)(?=[\s;&|)}`'\"]|$)|\bfind\b.*-delete|\brmtree\b")
PUSH = re.compile(GIT + r"push\b((?:\\\n|[^;&|\n])*)")
FORCE = re.compile(r"(?:^|\s)(?:-[a-zA-Z]*f[a-zA-Z]*|--force\S*|--mirror|--all|\+[^\s'\")]*)(?=[\s'\")]|$)")
ROLE_GIT = re.compile(GIT + r"(?:push|merge|checkout|switch|restore|apply|branch\s+(?:-\w*f|--force))\b")
GH = re.compile(r"(?<![\w./-])gh\b|(?:^|[;&|(`\n]|\$\()\s*[^\s;&|()`]*/gh(?=\s|$)")  # a path to gh counts only as the command, not as an argument
REDIRECT = re.compile(r"\d*>>?\|?\s*([^\s;&|<>()]+)|\btee\s+(?:-\S+\s+)*([^\s;&|<>()]+)")


class Refuse(Exception):
    def __init__(self, reason, step):
        super().__init__(reason)
        self.reason, self.step = reason, step


def check_everyone(command):
    if DELETE.search(command):
        raise Refuse("a recursive delete is not allowed",
                     "delete named files one at a time, or report it")
    branches = "|".join(["main", "master"] + [
        re.escape(b) for b in [os.environ.get("LITE_DEFAULT_BRANCH", "")] if b])
    protected = re.compile(r"(?:^|[\s:'\"=]|refs/heads/)(?:%s)(?=[\s'\")]|$)" % branches)
    for m in PUSH.finditer(command):
        if FORCE.search(m.group(1)):
            raise Refuse("a force, mirror or all-branch push is not allowed",
                         "push a normal fast-forward of your own branch")
        if protected.search(m.group(1)):
            raise Refuse("a push to the default branch is not allowed",
                         "push a feature branch and open a pull request")


def check_path(path, role, cwd):
    top = os.path.realpath(common.git(["rev-parse", "--show-toplevel"], cwd, check=False) or cwd)
    full = os.path.realpath(os.path.join(cwd, path))
    rel = os.path.relpath(full, top)
    if role == "reviewer" and (rel == ".." or rel.startswith(".." + os.sep)):  # scratch files, never inside the project
        if any(full == t or full.startswith(t + os.sep) for t in {os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp")}):
            return
    if role == "reviewer" or (role == "pass" and not rel.startswith(".lite/pass/")):
        raise Refuse("the %s edits nothing%s" % (role, " outside .lite/pass/" if role == "pass" else ""),
                     "describe the change in the review instead")
    allowed = {os.path.relpath(os.path.realpath(os.path.join(top, a.strip())), top)
               for a in os.environ.get("LITE_ALLOWED", "").splitlines() if a.strip()}
    protected = [x for x in os.environ.get("LITE_PROTECTED", "").split(",") if x] or common.DEFAULTS["Protected paths"].split(", ")
    if role == "builder" and rel in allowed and not merge.stop_reason(rel, protected):
        return  # the issue names this path as one the builder may change
    for locked in os.environ.get("LITE_LOCKED", "").splitlines():
        lfull = os.path.realpath(os.path.join(top, locked.strip()))
        if locked.strip() and (full == lfull or full.startswith(lfull + "/")):
            raise Refuse("%s is a locked test file" % rel,
                         "make the code pass the test; do not change the test")
    if merge.is_test_file(rel) and common.git(["ls-files", "--", full], cwd, check=False):
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


PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)


def unparsed(what):
    return Refuse("the guard cannot parse %s" % what, "make the call in a plain form, or report it")


def check_codex(data, role, cwd):
    """A Codex call: a shell command (a string or an argument list) or an apply_patch. Refuse what is not understood."""
    tool, inp = data.get("tool_name"), data.get("tool_input")
    if tool == "Bash":
        command = inp.get("command") if isinstance(inp, dict) else None
        if isinstance(command, list) and command and all(isinstance(a, str) for a in command):
            command = " ".join(command)
        if not isinstance(command, str) or not command.strip():
            raise unparsed("this shell command")
        check_everyone(command)
        if role:
            check_role_command(command, role, cwd)
        return
    if tool != "apply_patch":
        raise unparsed("the tool %r" % (tool,))
    text = inp.get("command") if isinstance(inp, dict) else inp
    paths = PATCH_PATH.findall(text) if isinstance(text, str) else []
    if not paths:
        raise unparsed("this patch")
    if SECRETS.search(text):
        raise Refuse("the content holds a secret shape", "read the secret from the environment instead")
    for path in paths if role else ():
        check_path(path, role, cwd)


def check(data):
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    cwd, role = data.get("cwd") or os.getcwd(), os.environ.get("LITE_ROLE", "")
    if os.environ.get("LITE_AGENT") == "codex":
        return check_codex(data, role, cwd)
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
        elif os.environ.get("LITE_AGENT") == "codex":
            raise unparsed("this payload")
    except Refuse as r:
        sys.stderr.write("refused: %s\nnext: %s\n" % (r.reason, r.step))
        return 2
    except Exception as e:
        if os.environ.get("LITE_AGENT") == "codex":
            sys.stderr.write("refused: the guard failed on this call: %s\nnext: make the call in a plain form, or report it\n" % e)
            return 2
        sys.stderr.write("guard: internal error, allowing the call: %s\n" % e)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
