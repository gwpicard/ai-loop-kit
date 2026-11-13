#!/usr/bin/env python3
"""The guard: a Claude Code PreToolUse hook that refuses the hard rules.

It reads the tool call as JSON on stdin. Exit 2 refuses the call and prints
`refused:` and `next:` lines on stderr. Exit 0 lets it through, and so does
any input it cannot parse: the guard never blocks on its own error.

For everyone:
  - no push to the default branch, main or master, and no force push;
  - no recursive delete;
  - no secret shape in written content.
When LITE_ROLE is set, also:
  - no git push, no git merge, no switch to another branch, no gh;
  - no write to a path in LITE_LOCKED (newline separated) or to an existing
    test file, except a new file by the test-writer role;
  - the reviewer role writes nothing.

This is a word check on the command string, not a shell parser.
"""
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

SECRETS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bghp_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{10,}",
    r"\bxox[bp]-[A-Za-z0-9-]{10,}",
]
TEST_NAMES = ["test_*", "*_test.*", "*.test.*", "*.spec.*"]
TEST_DIRS = {"tests", "test", "__tests__"}
WRAPPERS = {"env": "uCS", "sudo": "ugChpRrDT", "command": "", "exec": "",
            "nohup": "", "time": "fo"}


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


def protected_branches(cwd):
    names = {"main", "master"}
    code, out = git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd)
    if code == 0 and out:
        names.add(out.replace("refs/remotes/origin/", "", 1))
    return names


def split_commands(text):
    """Split on unquoted && || ; | & newline, and open $( and backtick."""
    text = re.sub(r">&\d*-?", " ", text).replace("&>", ">")
    out, cur, quote, i = [], "", "", 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'" and i + 1 < len(text):
            cur += text[i:i + 2]
            i += 2
            continue
        if quote:
            if c == quote:
                quote = ""
            cur += c
        elif c in "'\"":
            quote = c
            cur += c
        elif c in ";|&\n`()" or text.startswith("$(", i):
            out.append(cur)
            cur = ""
            i += 1 if c != "$" else 2
            continue
        else:
            cur += c
        i += 1
    out.append(cur)
    return [s for s in out if s.strip()]


def words(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def strip_prefix(w):
    while w:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]):
            w = w[1:]
        elif os.path.basename(w[0]) in WRAPPERS:
            valued = WRAPPERS[os.path.basename(w[0])]
            w = w[1:]
            while w and w[0].startswith("-"):
                skip = 2 if len(w[0]) == 2 and w[0][1] in valued else 1
                w = w[skip:]
        else:
            break
    return w


def git_parts(w):
    """Return (subcommand, args) for a git word list, skipping global options."""
    i = 1
    while i < len(w) and w[i].startswith("-"):
        i += 2 if w[i] in ("-C", "-c", "--git-dir", "--work-tree") else 1
    return (w[i], w[i + 1:]) if i < len(w) else ("", [])


def check_push(args, cwd):
    flags = [a for a in args if a.startswith("-")]
    pos, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            skip = True
        elif not a.startswith("-"):
            pos.append(a)
    protected = protected_branches(cwd)
    for a in flags:
        if a in ("-f", "--force", "--mirror", "--all") or a.startswith(
                ("--force-with-lease", "--force-if-includes")):
            raise Refuse("a force push, mirror or all-branch push is not allowed",
                         "push a normal fast-forward of your own branch")
        if re.match(r"^-[a-zA-Z]*f[a-zA-Z]*$", a):
            raise Refuse("a force push is not allowed",
                         "push a normal fast-forward of your own branch")
    refspecs = pos[1:]
    _, current = git(["symbolic-ref", "--short", "HEAD"], cwd)
    if not refspecs and current in protected:
        raise Refuse("a push from %s goes to the default branch" % current,
                     "work on a feature branch and open a pull request")
    for spec in refspecs:
        if spec.startswith("+"):
            raise Refuse("a forced refspec is not allowed",
                         "push a normal fast-forward of your own branch")
        dst = spec.split(":")[-1]
        dst = re.sub(r"^refs/heads/", "", dst)
        if dst == "HEAD":
            dst = current
        if dst in protected:
            raise Refuse("a push to %s is not allowed" % dst,
                         "push a feature branch and open a pull request")


def is_recursive_rm(w):
    for a in w[1:]:
        if a == "--recursive" or (re.match(r"^-[A-Za-z]+$", a) and (
                "r" in a or "R" in a)):
            return True
    return False


def check_everyone(w, segment, cwd, depth):
    if not w:
        return
    cmd = os.path.basename(w[0])
    if cmd in ("sh", "bash", "zsh") and "-c" in w[1:] and depth < 3:
        i = w.index("-c")
        if i + 1 < len(w):
            check_command(w[i + 1], cwd, None, depth + 1)
        return
    if cmd == "git":
        sub, args = git_parts(w)
        if sub == "push":
            check_push(args, cwd)
    elif cmd == "rm" and is_recursive_rm(w):
        raise Refuse("a recursive delete is not allowed",
                     "delete named files one at a time, or report it")
    elif cmd == "find":
        if "-delete" in w:
            raise Refuse("find -delete is a recursive delete",
                         "delete named files one at a time, or report it")
        for key in ("-exec", "-execdir"):
            if key in w:
                check_everyone(w[w.index(key) + 1:], "", cwd, depth)
    if re.search(r"\brmtree\b", segment) and re.search(r"python", segment):
        raise Refuse("rmtree is a recursive delete",
                     "delete named files one at a time, or report it")


def role_denied(w, role):
    cmd = os.path.basename(w[0])
    if cmd == "gh":
        raise Refuse("gh is not available in a %s session" % role,
                     "leave GitHub steps to the loop")
    if cmd != "git":
        return
    sub, args = git_parts(w)
    if sub in ("push", "merge"):
        raise Refuse("git %s is not allowed in a %s session" % (sub, role),
                     "commit on your branch; the loop pushes and merges")
    if sub == "switch" or (sub == "checkout" and "--" not in args):
        raise Refuse("a branch switch is not allowed in a %s session" % role,
                     "stay on your branch; restore files with git checkout -- <path>")


def write_targets(w, segment):
    """Paths a command writes to, by redirection or a few writing commands."""
    out = []
    for i, tok in enumerate(w):
        m = re.match(r"^(\d*|&)>>?(.*)$", tok)
        if m:
            target = m.group(2) or (w[i + 1] if i + 1 < len(w) else "")
            if target and target != "/dev/null" and not target.startswith("&"):
                out.append(target)
    args = [a for a in w[1:] if not a.startswith("-") and ">" not in a]
    cmd = os.path.basename(w[0])
    if cmd in ("tee", "rm", "mv", "truncate", "unlink") or (
            cmd == "sed" and any(a.startswith("-i") or a == "--in-place"
                                 for a in w[1:])):
        out += args
    elif cmd in ("cp", "install") and args:
        out.append(args[-1])
    return out


def is_test_path(rel):
    parts = rel.replace("\\", "/").split("/")
    return (any(fnmatch.fnmatch(parts[-1], p) for p in TEST_NAMES)
            or any(p in TEST_DIRS for p in parts[:-1]))


def check_path(path, role, cwd):
    """Refuse a write to `path` for a role session."""
    if role == "reviewer":
        raise Refuse("the reviewer edits nothing",
                     "describe the change in the review instead")
    code, top = git(["rev-parse", "--show-toplevel"], cwd)
    top = top if code == 0 and top else cwd
    full = os.path.realpath(os.path.join(cwd, path))
    rel = os.path.relpath(full, os.path.realpath(top))
    for locked in os.environ.get("LITE_LOCKED", "").splitlines():
        locked = locked.strip()
        if not locked:
            continue
        lfull = os.path.realpath(os.path.join(top, locked))
        if full == lfull or full.startswith(lfull.rstrip("/") + "/"):
            raise Refuse("%s is a locked test file" % rel,
                         "make the code pass the test; do not change the test")
    if is_test_path(rel):
        tracked = git(["ls-files", "--error-unmatch", "--", full], cwd)[0] == 0
        if tracked:
            raise Refuse("%s is an existing test file" % rel,
                         "leave existing tests alone; add a new test file if needed")


def check_command(command, cwd, role, depth=0):
    for segment in split_commands(command):
        w = strip_prefix(words(segment))
        check_everyone(w, segment, cwd, depth)
        if role and w:
            role_denied(w, role)
            targets = write_targets(w, segment)
            for t in targets:
                check_path(t, role, cwd)


def check_secrets(texts):
    for text in texts:
        for pattern in SECRETS:
            if re.search(pattern, text):
                raise Refuse("the content holds a secret shape",
                             "read the secret from the environment instead")


def check(data):
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    role = os.environ.get("LITE_ROLE", "")
    if tool == "Bash":
        check_command(inp.get("command", "") or "", cwd, role)
        return
    if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return
    texts = [inp.get("content"), inp.get("new_string"), inp.get("new_source")]
    texts += [e.get("new_string") for e in inp.get("edits") or []]
    check_secrets([t for t in texts if isinstance(t, str)])
    path = inp.get("file_path") or inp.get("notebook_path")
    if role and path:
        check_path(path, role, cwd)
    elif role == "reviewer":
        check_path("", role, cwd)


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            return 0
        check(data)
    except Refuse as r:
        sys.stderr.write("refused: %s\nnext: %s\n" % (r.reason, r.step))
        return 2
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
