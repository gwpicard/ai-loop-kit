#!/usr/bin/env python3
"""The guard: a Claude Code PreToolUse hook that warns early about hard rules.

It reads the tool call as JSON on stdin. Exit 2 refuses the call and prints
`refused:` and `next:` lines on stderr. Exit 0 lets it through, and so does
any input it cannot parse: the guard never blocks on its own error. A Codex
session (LOOP_AGENT=codex) is the exception: it sends shell commands and
apply_patch calls, and the guard refuses a payload or an error it cannot parse.
If its modules cannot load, it refuses calls when LOOP_ROLE is set and
otherwise allows the call with a warning.

Everywhere: no push to main, master or the default branch (LOOP_DEFAULT_BRANCH
names it), no force push, no recursive delete, no secret shape in written
content. When LOOP_ROLE is set, also: no git push, merge, checkout, switch,
restore, apply or branch -f, no gh, no write to a path in LOOP_LOCKED (newline
separated) or to a tracked test file (except an exact path in LOOP_ALLOWED,
for the builder only). Builders cannot write paths on the stops list unless
the issue allows them. The reviewer role writes nothing in the project (scratch files in the system
temp folder are fine; the pass role writes only under .loop/pass/).

Known limits: the guard reads code passed by `-c`, `-e`, a heredoc or a
here-string and, in loop sessions, the first script operand when it is new,
changed since LOOP_START or outside the project. It cannot see commands
assembled at run time, code in files generated or fetched at run time,
or code that a test or a project script runs. It checks literal text and is
an early warning. The diff check in merge.py and branch protection on the
default branch provide further protection. A bare `git push` from main is
not caught, because the guard does not ask git which branch is checked out.
"""
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
    import common
    import merge  # the one definition of a test file
except Exception as e:
    if os.environ.get("LOOP_ROLE"):
        sys.stderr.write("refused: the guard cannot load: %s\nrule: guard-error\n"
                         "next: repair the guard before continuing\n" % e)
        sys.exit(2)
    sys.stderr.write("guard: cannot load, allowing the call: %s\n" % e)
    sys.exit(0)

SECRETS = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\bgh[pousr]_[A-Za-z0-9]{20,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b"
    r"|\bsk-ant-[A-Za-z0-9_-]{10,}|\bxox[abprs]-[A-Za-z0-9-]{10,}")
SHELL_WORD = r'''(?:'[^']*'|"(?:\\.|[^"\\])*"|\\.|[^\s;&|<>()'"\\])+'''
GIT = (r"\bgit(?:(?:\s|\\\n)+(?:-(?:C|c)(?:\s|\\\n)+" + SHELL_WORD
       + r"|--(?:git-dir|work-tree|namespace|super-prefix|config-env|exec-path)(?:\s|\\\n)+"
       + SHELL_WORD + r"|--\S+|-[A-Za-z]+))*(?:\s|\\\n)+")
DELETE = re.compile(r"\brm\s+(?:[^\s;&|]+\s+)*?(?:-\w*[rR]\w*|--recursive)(?=[\s;&|)}`'\"]|$)|\bfind\b.*-delete|\brmtree\b")
PUSH = re.compile(GIT + r"push\b((?:\\\n|[^;&|\n])*)")
FORCE = re.compile(r"(?:^|\s)(?:-[a-zA-Z]*f[a-zA-Z]*|--force\S*|--mirror|--all|\+[^\s'\")]*)(?=[\s'\")]|$)")
ROLE_GIT = re.compile(GIT + r"(?:push|merge(?!(?:-base|-tree)(?=\s|$))|checkout|switch|restore|apply|branch\s+(?:-\w*f|--force))\b")
GH = re.compile(r"(?<![\w./-])gh\b|(?:^|[;&|(`\n]|\$\()\s*"
                r"(?:(?:\w+=\S+|(?:\S*/)?env(?:\s+(?:-[uC]|--(?:unset|chdir))\s+\S+|\s+-\S+)*"
                r"|(?:\S*/)?sudo(?:\s+(?:-[ughpCRDTrt]|--(?:user|group|host|prompt|close-from|chroot|chdir|command-timeout|role|type))"
                r"\s+\S+|\s+-\S+)*)\s+)*"
                r"[^\s;&|()`]*/gh(?=\s|$)")  # a path to gh counts only as the command, not as an argument
SHELL_DATA = re.compile(r'''(?<!<)<<(?!<)(-?)[ \t]*(['"]?)([^\s'";&|<>()]+)\2|'[^']*'|"(?:\\.|[^"\\])*"|\n''')
SHELLS = ("sh", "bash", "zsh", "dash")
RUNNER = re.compile(r"(?:^|[;&|(`\n])\s*(?:\w+=\S+\s+)*(?:(?:\S*/)?env\s+(?:-\S+\s+|\w+=\S+\s+)*)?(?:\S*/)?(?:"
                    + "|".join(SHELLS) + r"|eval|xargs)(?=\s|$)")
REDIRECT = re.compile(r'''('[^']*'|"(?:\\.|[^"\\])*")|\d*>>?(&)?\|?\s*('''
                      + SHELL_WORD + r")|\btee\s+(" + SHELL_WORD
                      + r"(?:[ \t]+" + SHELL_WORD + r")*)")
SUBSTITUTION = re.compile(r"(?<!\\)(?:\$\((?:[^()]|\([^()]*\))*\)|`(?:\\.|[^`\\])*`)")
INPUT = re.compile(r'''(?<!<)<<(?!<)(-?)[ \t]*(['"]?)([^\s'";&|<>()]+)\2|<<<|[;&|()\n]|'''
                   + SHELL_WORD)
CODE_STRING = r'''(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")'''
# Also join a command and its literal argv, as in spawnSync("git", ["push"]).
CODE_LITERALS = re.compile(CODE_STRING + r"(?:\s*,\s*(?:\[\s*)?" + CODE_STRING + r")*")


class Refuse(Exception):
    def __init__(self, rule, reason, step):
        super().__init__(reason)
        self.rule, self.reason, self.step = rule, reason, step


def interpreter(words):
    words = list(words)
    while words and re.fullmatch(r"\w+=\S*", words[0]):
        words.pop(0)
    if words and os.path.basename(words[0]) == "env":
        words.pop(0)
        while words and (words[0].startswith("-") or re.fullmatch(r"\w+=\S*", words[0])):
            option = words.pop(0)
            if option in ("-u", "-C", "--unset", "--chdir") and words:
                words.pop(0)
    if len(words) >= 2 and os.path.basename(words[0]) == "uv" and words[1] == "run":
        words = words[2:]
    return bool(words) and os.path.basename(words[0]) in ("python", "python3", "node") + SHELLS


def interpreter_inputs(command, scripts=False):
    """Read inline code, or first script operands, without evaluating code."""
    command = command.replace("\\\n", "")
    words, pending, pos, here_string = [], [], 0, False
    while pos < len(command):
        m = INPUT.search(command, pos)
        if not m:
            break
        pos = m.end()
        token = m.group()
        if m.group(3):
            pending.append((m.group(1), m.group(3), interpreter(words)))
        elif token == "\n":
            for strip, delimiter, executable in pending:
                end = re.search(r"(?m)^" + (r"\t*" if strip else "") + re.escape(delimiter)
                                + r"(?:\n|$)", command[pos:])
                body = command[pos:pos + end.start()] if end else command[pos:]
                if executable and not scripts:
                    yield body
                pos = pos + end.end() if end else len(command)
            words, pending, here_string = [], [], False
        elif token in (";", "&", "|", "(", ")"):
            words, here_string = [], False
        elif token == "<<<":
            here_string = interpreter(words)
        else:
            try:
                word = shlex.split(token)[0]
            except (ValueError, IndexError):
                continue  # incomplete shell text is still checked by the raw rules
            if scripts:
                if (not words and word.startswith("./") or
                        len(words) == 1 and os.path.basename(words[0]) in
                        ("bash", "sh", "zsh", "python3", "python", "node")
                        and not word.startswith("-")):
                    yield word
            elif here_string or (interpreter(words) and words
                                 and re.fullmatch(r"-[a-zA-Z]*[ce][a-zA-Z]*", words[-1])):
                yield word
            here_string = False
            words.append(word)


def interpreter_commands(command, full=False):
    for code in interpreter_inputs(command):
        yield from code_commands(code, full)


def code_commands(code, full=False):
    yield code
    for m in CODE_LITERALS.finditer(code):
        try:
            literals = [ast.literal_eval(s) for s in re.findall(CODE_STRING, m.group())]
        except (ValueError, SyntaxError):
            continue
        yield from literals
        # A named file after the Test command makes a targeted run. Do not
        # match a prefix of a list that has further string literals.
        if len(literals) > 1 and (not full or (
                code[:m.start()].rstrip().endswith("[")
                and re.match(r'''[^'"\]]*\]''', code[m.end():]))):
            yield shlex.join(literals)


def check_everyone(command):
    commands = [command, *interpreter_commands(command)]
    if any(DELETE.search(c) for c in commands):
        raise Refuse("recursive-delete", "a recursive delete is not allowed",
                     "delete named files one at a time, or report it")
    branches = "|".join(["main", "master"] + [
        re.escape(b) for b in [os.environ.get("LOOP_DEFAULT_BRANCH", "")] if b])
    protected = re.compile(r"(?:^|[\s:'\"=]|refs/heads/)(?:%s)(?=[\s'\")]|$)" % branches)
    for m in PUSH.finditer("\n".join(commands)):
        if FORCE.search(m.group(1)):
            raise Refuse("force-push", "a force, mirror or all-branch push is not allowed",
                         "push a normal fast-forward of your own branch")
        if protected.search(m.group(1)):
            raise Refuse("default-branch", "a push to the default branch is not allowed",
                         "push a feature branch and open a pull request")


def check_path(path, role, cwd):
    top = os.path.realpath(common.git(["rev-parse", "--show-toplevel"], cwd, check=False) or cwd)
    full = os.path.realpath(os.path.join(cwd, path))
    rel = os.path.relpath(full, top)
    if role == "reviewer" and (rel == ".." or rel.startswith(".." + os.sep)):  # scratch files, never inside the project
        if any(full == t or full.startswith(t + os.sep) for t in {os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp")}):
            return
    if role == "reviewer" or (role == "pass" and not rel.startswith(".loop/pass/")):
        raise Refuse("role-write", "the %s edits nothing%s" % (role, " outside .loop/pass/" if role == "pass" else ""),
                     "describe the change in the review instead")
    allowed = {os.path.relpath(os.path.realpath(os.path.join(top, a.strip())), top)
               for a in os.environ.get("LOOP_ALLOWED", "").splitlines() if a.strip()}
    protected = [x for x in os.environ.get("LOOP_PROTECTED", "").split(",") if x] or common.DEFAULTS["Protected paths"]
    if role == "builder":
        if rel in allowed:
            return  # the issue names this path as one the builder may change
        why = merge.stop_reason(rel, protected, top)
        if why:
            raise Refuse("stop", "%s: %s" % (why, rel),
                         "park the issue if this change is needed")
    for locked in os.environ.get("LOOP_LOCKED", "").splitlines():
        lfull = os.path.realpath(os.path.join(top, locked.strip()))
        if (locked.strip() and (merge.is_test_module(rel) or merge.is_test_module(locked.strip()))
                and (full == lfull or full.startswith(lfull + "/"))):
            raise Refuse("test-lock", "%s is a locked test file" % rel,
                         "make the code pass the test; do not change the test")
    command = ["ls-files", "--", full]
    if role in {"builder", "test-writer"}:
        start = os.environ.get("LOOP_START")
        if not start:
            loop = os.environ.get("LOOP_LOOP_BRANCH", "loop/main")
            start = common.git(["merge-base", "HEAD", "origin/" + loop], cwd, check=False)
        if start and common.git(["rev-parse", "--verify", start + "^{commit}"], top, check=False):
            command = ["ls-tree", "--name-only", start, "--", rel]
            cwd = top
    if merge.is_test_module(rel) and common.git(command, cwd, check=False):
        raise Refuse("test-lock", "%s is an existing test file" % rel,
                     "leave existing tests alone; add a new test file if needed")


def role_commands(command):
    command = command.replace("\\\n", "")
    parts, pending, pos = [], [], 0
    while pos < len(command):
        m = SHELL_DATA.search(command, pos)
        if not m:
            break
        parts.append(command[pos:m.start()])
        pos = m.end()
        if m.group(3):
            pending.append((m.group(1), m.group(2), m.group(3)))
            parts.append("<<_ ")
        elif m.group() == "\n":
            parts.append("\n")
            for strip, quoted, word in pending:
                end = re.search(r"(?m)^" + (r"\t*" if strip else "") + re.escape(word) + r"(?:\n|$)", command[pos:])
                body = command[pos:pos + end.start()] if end else command[pos:]
                if not quoted:
                    parts.extend("\n" + role_commands(s.group()) + "\n"
                                 for s in SUBSTITUTION.finditer(body))
                pos = pos + end.end() if end else len(command)
            pending.clear()
        elif m.group().startswith('"') and ("$(" in m.group() or "`" in m.group()):
            parts.append(m.group())  # a command substitution inside double quotes still runs
        else:
            parts.append("_")
    parts.append(command[pos:])
    text = "".join(parts)
    return command if RUNNER.search(text) else text


def full_test_files(command, template, cwd):
    before, marker, after = template.partition("{files}")
    if not marker:
        return False
    command = re.sub(
        r'''('[^']*'|"(?:\\.|[^"\\])*"|\\.)|(?:(?<!\S)\d+)?(?:>>?|<)&?[ \t]*(?:'[^']*'|"(?:\\.|[^"\\])*"|[^\s;&|<>]+)''',
        lambda m: m.group(1) or "", command)
    try:
        args, prefix, suffix = map(shlex.split, (command, before, after))
    except ValueError:
        return False
    if (len(args) < len(prefix) + len(suffix) or args[:len(prefix)] != prefix
            or suffix and args[-len(suffix):] != suffix):
        return False
    selected = args[len(prefix):len(args) - len(suffix) if suffix else None]
    if not selected:
        return True
    top = common.git(["rev-parse", "--show-toplevel"], cwd, check=False) or cwd
    paths = common.git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"], top, check=False)
    modules = {p: os.path.realpath(os.path.join(top, p)) for p in paths.split("\0")
               if p and merge.is_test_module(p) and os.path.isfile(os.path.join(top, p))}
    names = {name: full for p, full in modules.items() if p.endswith(".py")
             for name in (p[:-3].replace("/", "."), os.path.basename(p)[:-3])}
    chosen = {names.get(p, os.path.realpath(os.path.join(cwd, p))) for p in selected}
    return bool(modules) and set(modules.values()) <= chosen


def check_full_test(commands, role, cwd):
    files = os.environ.get("LOOP_TEST_FILES_COMMAND")
    if role in ("builder", "reviewer", "test-writer", "pass") and files and any(
            s.strip() == os.environ.get("LOOP_TEST_COMMAND") or full_test_files(s, files, cwd)
            for c in commands
            for s in re.split(r"&&|\|\||[;|\n]", c)):
        raise Refuse("full-test", "the full Test command is reserved for merge",
                     "use <plugin>/bin/loop check; for selected files, use the Test files command: " + files)


def check_session_scripts(command, role, cwd):
    paths = list(interpreter_inputs(command, scripts=True))
    if not paths:
        return
    top = os.path.realpath(common.git(["rev-parse", "--show-toplevel"], cwd, check=False) or cwd)
    start = os.environ.get("LOOP_START")
    for path in paths:
        full = os.path.realpath(os.path.join(cwd, path))
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as script:
            content = script.read()
        rel = os.path.relpath(full, top)
        if (start and rel != ".." and not rel.startswith(".." + os.sep)
                and common.git(["ls-files", "--", rel], top, check=False)):
            original = subprocess.run(["git", "show", start + ":" + rel], cwd=top,
                                      capture_output=True, timeout=common.TIMEOUT)
            if original.returncode == 0 and original.stdout == content:
                continue
        code = content.decode("utf-8", errors="replace")
        try:
            commands = list(code_commands(code))
            if any(DELETE.search(c) for c in commands):
                raise Refuse("recursive-delete", "a recursive delete is not allowed",
                             "leave scratch space in the temporary folder; park if the issue needs this outcome")
            if re.search(GIT + r"(?:push|merge(?!(?:-base|-tree)(?=\s|$)))\b", "\n".join(commands)):
                raise Refuse("role-git", "git push and merge are not allowed in a %s session" % role,
                             "commit on your branch; the loop pushes and merges")
            check_full_test(code_commands(code, full=True), role, cwd)
        except Refuse as r:
            r.reason = "%s: %s" % (path, r.reason)
            raise


def check_role_command(command, role, cwd):
    check_full_test((command, *interpreter_commands(command, full=True)), role, cwd)
    check_session_scripts(command, role, cwd)
    executable = "\n".join((role_commands(command), *interpreter_commands(command)))
    if ROLE_GIT.search(executable) or GH.search(executable):
        raise Refuse("role-git", "git push, merge, branch changes and gh are not allowed in a %s session" % role,
                     "commit on your branch; the loop pushes and merges")
    for m in REDIRECT.finditer(command):
        if m.group(1):  # quoted arguments are data, not redirections
            continue
        targets = shlex.split(m.group(3) or m.group(4))
        options = bool(m.group(4))
        for target in targets:
            if options and target == "--":
                options = False
                continue
            if options and target.startswith("-"):
                continue
            if m.group(2) and re.fullmatch(r"\d+-?|-", target):  # >&2 and >&- duplicate or close a descriptor
                continue
            if target and target != "/dev/null":
                check_path(target, role, cwd)


PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)


def unparsed(what):
    return Refuse("guard-input", "the guard cannot parse %s" % what, "make the call in a plain form, or report it")


def check_codex(data, role, cwd):
    """A Codex call: a shell command (a string or an argument list) or an apply_patch. Refuse what is not understood."""
    tool, inp = data.get("tool_name"), data.get("tool_input")
    if tool == "Bash":
        command = inp.get("command") if isinstance(inp, dict) else None
        if isinstance(command, list) and command and all(isinstance(a, str) for a in command):
            if len(command) == 3 and os.path.basename(command[0]) in SHELLS and re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", command[1]):
                command = command[2]
            else:
                command = shlex.join(command)
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
        raise Refuse("secret", "the content holds a secret shape", "read the secret from the environment instead")
    for path in paths if role else ():
        check_path(path, role, cwd)


def check(data):
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    cwd, role = data.get("cwd") or os.getcwd(), os.environ.get("LOOP_ROLE", "")
    if os.environ.get("LOOP_AGENT") == "codex":
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
        raise Refuse("secret", "the content holds a secret shape",
                     "read the secret from the environment instead")
    if role:
        check_path(inp.get("file_path") or inp.get("notebook_path") or "", role, cwd)


def refuse(r):
    project = os.environ.get("LOOP_PROJECT")
    if project:
        try:
            fields = dict(rule=r.rule, reason=r.reason)
            if os.environ.get("LOOP_ROLE"):
                fields["role"] = os.environ["LOOP_ROLE"]
            if os.environ.get("LOOP_ISSUE"):
                issue = os.environ["LOOP_ISSUE"]
                fields["issue"] = int(issue) if issue.isdigit() else issue
            common.event("rule", project, **fields)
        except Exception:
            pass
    sys.stderr.write("refused: %s\nrule: %s\nnext: %s\n" % (r.reason, r.rule, r.step))
    return 2


def main():
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            check(data)
        elif os.environ.get("LOOP_AGENT") == "codex":
            raise unparsed("this payload")
    except Refuse as r:
        return refuse(r)
    except Exception as e:
        if os.environ.get("LOOP_AGENT") == "codex":
            return refuse(Refuse("guard-error", "the guard failed on this call: %s" % e,
                                 "make the call in a plain form, or report it"))
        sys.stderr.write("guard: internal error, allowing the call: %s\n" % e)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
