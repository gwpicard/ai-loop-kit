#!/usr/bin/env python3
"""The command guard: a PreToolUse hook that reads each call before it runs.

Claude Code starts this hook with the call as JSON on standard input. The hook
answers in one of three ways:

- Refuse. It exits 2 and writes the reason to standard error. Claude Code shows
  the reason to the agent and does not run the call.
- Ask. It exits 0 and prints a `permissionDecision` of "ask". Claude Code shows
  its confirmation box. In a session that never asks, such as `dontAsk`, an ask
  is a refusal.
- Pass. It exits 0 and prints nothing.

Deny rules in the Claude Code settings read the words of a command as written.
This hook reads the command. It splits a line into its commands, looks inside
`sh -c`, `eval`, `$(...)`, `find -exec` and wrappers such as `env` and `sudo`,
and strips options between `git` and `push`. So `git -C . push origin main` is
caught here, though a deny rule misses it. The rules and this hook are two
independent layers for the same refusals.

What the hook refuses:

- a push to `main`, a force push, and a push that names no branch while `main`
  is checked out;
- a recursive delete, `find -delete`, `git reset --hard`, `git clean -f`, and the
  commands that throw away Git's history;
- a hand-written `state:`, `shaping:` or `review:` label, and the `needs-you`
  flag, in any `gh` form or GitHub tool call;
- `gate.py sync`, which only the person runs, also when reached through a
  variable, `env -u` or a blanked agent-session variable, or `python3 -c` with
  `runpy`;
- a read of a real env file, the App key, the held-out folder, the `gh` config
  and the keychain, and `gh auth token`;
- a write to the guards: the settings, the piece records, the policy file, the
  workflows, the git hooks and the installed kit.

What it asks about: a comment or a review posted in the person's name.

A line the hook cannot read asks. A fault in the hook asks. Input that is not
JSON is refused with exit 2, so a broken hook input never lets a call run.

Every decision is also written to the command log by `command-log.py`.

The throwaway marker below is the first line of every throwaway env file the kit
writes in a worktree. `worktree.sh` writes the same string.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import shlex
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from loop import paths as loop_paths

THROWAWAY_MARKER = "# ai-loop-kit: throwaway values. Nothing in this file is a real secret."

DENY = "deny"
ASK = "ask"
ALLOW = "allow"

HERE = Path(__file__).resolve().parent
SEMI = "__SEMICOLON__"
PROTECTED_BRANCH = "main"
LABEL_FAMILY = re.compile(r"^(state|shaping|review)(:|%3a)", re.IGNORECASE)
NEEDS_YOU = "needs-you"
ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.dist"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "ash"}
READ_TOOLS = {"Read": ("file_path",), "Grep": ("path",), "Glob": ("path",)}
WRITE_TOOLS = {
    "Edit": ("file_path",),
    "Write": ("file_path",),
    "MultiEdit": ("file_path",),
    "NotebookEdit": ("notebook_path", "file_path"),
}


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str = ""


PASS = Decision(ALLOW)


def refuse(what: str, next_step: str) -> Decision:
    return Decision(
        DENY,
        f"The guard refused this: {what}\n"
        f"next: {next_step}\n"
        "Never reach the same result another way. Tell the person which command was refused\n"
        "and what it was for, and let them decide. blocked-commands.md lists what is refused.",
    )


def ask(what: str, next_step: str) -> Decision:
    return Decision(ASK, f"The guard asks first: {what}\nnext: {next_step}")


# --- where the call runs ---------------------------------------------------------


def _real(path: str | Path) -> Path:
    return Path(os.path.realpath(path))


def _is_under(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def _git_file_target(git_file: Path) -> Path | None:
    try:
        first = git_file.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first.startswith("gitdir:"):
        return None
    target = Path(first.split(":", 1)[1].strip())
    return target if target.is_absolute() else _real(git_file.parent / target)


def _git_dir(folder: Path) -> Path | None:
    dot_git = folder / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        return _git_file_target(dot_git)
    return None


def main_folder(work_root: Path) -> Path:
    """The main folder of a project, given any folder of it, a worktree included."""
    target = _git_dir(work_root)
    # A worktree's git dir is <main>/.git/worktrees/<name>.
    if (
        (work_root / ".git").is_file()
        and target is not None
        and target.parent.name == "worktrees"
        and target.parent.parent.name == ".git"
    ):
        return target.parent.parent.parent
    return work_root


def current_branch(folder: Path) -> str | None:
    git_dir = _git_dir(folder)
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text().strip()
    except OSError:
        return None
    prefix = "ref: refs/heads/"
    return head[len(prefix) :] if head.startswith(prefix) else None


@dataclass(frozen=True)
class Context:
    cwd: Path
    env: Mapping[str, str]
    home: Path
    work_root: Path | None
    main_root: Path | None
    # Variables set earlier on the same command line, such as `D=/some/folder`.
    vars: Mapping[str, str] = field(default_factory=dict)

    @property
    def worktrees(self) -> Path | None:
        return None if self.main_root is None else self.main_root / ".agents" / "worktrees"


def build_context(cwd: str, env: Mapping[str, str]) -> Context:
    folder = _real(cwd or os.getcwd())
    home = _real(env.get("HOME") or os.path.expanduser("~"))
    work_root: Path | None
    try:
        work_root = _real(loop_paths.find_project_root(folder))
    except loop_paths.PathError:
        work_root = None
    main_root = _real(main_folder(work_root)) if work_root is not None else None
    return Context(cwd=folder, env=env, home=home, work_root=work_root, main_root=main_root)


# --- paths named in a command ------------------------------------------------------


VARIABLE = re.compile(
    r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(?::?[-=]([^}]*))?\}|([A-Za-z_][A-Za-z0-9_]*))"
)


def expand(token: str, ctx: Context) -> str:
    """Replace `~` and the variables the hook knows: the environment and this line's own."""
    home = str(ctx.home)
    known: dict[str, str] = dict(ctx.env)
    known.setdefault(loop_paths.DATA_ENV, str(_data_folder(ctx) or ""))
    known.update(ctx.vars)
    known["HOME"] = home
    out = token
    if out == "~" or out.startswith("~/"):
        out = home + out[1:]

    def value(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(3)
        if known.get(name):
            return known[name]
        # `${VAR:-default}`, `${VAR-default}` and `${VAR:=default}` give the default.
        default = match.group(2)
        return VARIABLE.sub(value, default) if default is not None else match.group(0)

    return VARIABLE.sub(value, out)


def candidates(token: str, base: Path, ctx: Context) -> list[Path]:
    """Every file a word could name: the word, the value after `=`, and glob matches."""
    texts = [token]
    if "=" in token:
        texts.append(token.split("=", 1)[1])
    found: list[Path] = []
    for text in texts:
        text = expand(text, ctx)
        if not text or "$" in text or "\n" in text or len(text) > 1000:
            continue
        full = os.path.join(base, text)
        found.append(_real(full))
        if any(ch in full for ch in "*?["):
            found.extend(_real(m) for m in glob.glob(full)[:200])
    return found


def is_env_file(path: Path) -> bool:
    name = path.name
    return name == ".env" or (name.startswith(".env.") and name not in ENV_EXAMPLES)


def has_marker(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.readline().rstrip("\r\n") == THROWAWAY_MARKER
    except OSError:
        return False


def _secret_folders(ctx: Context) -> list[Path]:
    folders = [ctx.home / ".config" / "gh", ctx.home / "Library" / "Keychains"]
    if ctx.env.get("GH_CONFIG_DIR"):
        folders.append(_real(ctx.env["GH_CONFIG_DIR"]))
    if ctx.env.get("XDG_CONFIG_HOME"):
        folders.append(_real(ctx.env["XDG_CONFIG_HOME"]) / "gh")
    return folders


def _data_folder(ctx: Context) -> Path | None:
    try:
        return _real(loop_paths.data_home(ctx.env))
    except loop_paths.PathError:
        return None


def read_block(path: Path, ctx: Context, *, write: bool = False) -> Decision | None:
    """A refusal when the path is a secret the agent must not read, or None."""
    if is_env_file(path):
        worktrees = ctx.worktrees
        in_worktree = worktrees is not None and _is_under(path, worktrees)
        if not in_worktree:
            return refuse(
                f"{path.name} outside a worktree is a real env file.",
                "read the worktree's own throwaway .env, or ask the person for the value.",
            )
        if not write and not has_marker(path):
            return refuse(
                f"{path} does not start with the kit's throwaway marker.",
                "read only the throwaway .env the kit wrote in the worktree.",
            )
    data = _data_folder(ctx)
    if data is not None and _is_under(path, data):
        return refuse(
            "this is the kit's data folder. It holds the App key, the evidence key, "
            "the head records and the held-out folder. Only the gate reads them.",
            "use the gate's own commands. Do not read or write these files.",
        )
    for folder in _secret_folders(ctx):
        if _is_under(path, folder):
            return refuse(
                "this holds a sign-in token or a keychain. A builder holds no GitHub credential.",
                "ask the person to run the command that needs the sign-in.",
            )
    return None


def covers_protected(path: Path, ctx: Context) -> Decision | None:
    """A refusal when a recursive read of this folder would reach a secret, or None."""
    data = _data_folder(ctx)
    reaches = data is not None and (_is_under(path, data) or _is_under(data, path))
    reaches = reaches or any(_is_under(folder, path) for folder in _secret_folders(ctx))
    if reaches:
        return refuse(
            "this reads every file under a folder that holds the App key, the held-out "
            "folder or a sign-in token.",
            "name the files you need, in a folder that holds no secret.",
        )
    return None


def _relative_parts(path: Path, anchor: Path | None) -> tuple[str, ...] | None:
    if anchor is None or not _is_under(path, anchor):
        return None
    return path.relative_to(anchor).parts


# The run record holds the run's pre-approval to merge, and the lock names the process that
# holds the run. Only run.py writes them.
RUN_GUARDED = {"run.json", "lock"}


def write_block(path: Path, ctx: Context) -> Decision | None:
    """A refusal when the path is one of the guards, or None."""
    anchors = [a for a in (ctx.main_root, ctx.work_root, ctx.home) if a is not None]
    for anchor in anchors:
        parts = _relative_parts(path, anchor)
        if not parts:
            continue
        guarded = (
            (parts[0] == ".claude" and len(parts) == 2 and parts[1].startswith("settings"))
            or parts[:2] == (".agents", "pieces")
            or (parts[:2] == (".agents", "runs") and len(parts) == 4 and parts[3] in RUN_GUARDED)
            or parts[:3] in {(".agents", "loop", "policy.json"), (".agents", "loop", "local.json")}
            or parts[:2] == (".github", "workflows")
            or parts[0] == ".githooks"
        )
        if guarded:
            return refuse(
                f"{'/'.join(parts)} is one of the guards. Agents never write it.",
                "tell the person which file needs a change and why.",
            )
    try:
        kit = _real(loop_paths.kit_dir(ctx.main_root or ctx.cwd, ctx.env))
    except loop_paths.PathError:
        return None
    inside = any(
        _is_under(kit, a) for a in (ctx.main_root, ctx.work_root) if a is not None
    )
    if not inside and _is_under(path, kit):
        return refuse(
            "the installed kit folder holds the hooks and the gate. Agents never write it.",
            "tell the person which kit file needs a change and why.",
        )
    return None


# --- reading a command line --------------------------------------------------------


def normalise(text: str) -> str:
    """Prepare a line for the shell lexer.

    A newline outside quotes becomes `;`. A heredoc body is dropped, since it is
    text and not a command. A backslash and a newline join the lines. `\\;`
    becomes a marker word, so that `find -exec ... \\;` keeps its end. Backticks
    outside quotes become parentheses.
    """
    out: list[str] = []
    pending: list[str] = []
    quote = ""
    tick = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote == "'":
            out.append(c)
            if c == "'":
                quote = ""
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "\n":
                i += 2
                continue
            if nxt == ";" and not quote:
                out.append(f" {SEMI} ")
            else:
                out.append(c + nxt)
            i += 2
            continue
        if quote == '"':
            out.append(c)
            if c == '"':
                quote = ""
            i += 1
            continue
        if c in "'\"":
            quote = c
            out.append(c)
        elif c.isdigit() and (i == 0 or text[i - 1] in " \t;&|(\n"):
            # A file descriptor in front of a redirect, as in `2>&1`, is not a word.
            digits = re.match(r"\d+(?=[<>])", text[i:])
            if digits:
                i += len(digits.group())
                continue
            out.append(c)
        elif c == "`":
            out.append(" ) " if tick else " ( ")
            tick = not tick
        elif c == "\n":
            out.append(" ; ")
            for delimiter in pending:
                i = _skip_heredoc(text, i + 1, delimiter) - 1
            pending.clear()
        elif c == "<" and text.startswith("<<", i) and not text.startswith("<<<", i):
            j = i + 2
            if text[j : j + 1] == "-":
                j += 1
            match = re.match(r"\s*(['\"]?)([A-Za-z0-9_.\-]+)\1", text[j:])
            if match:
                pending.append(match.group(2))
            out.append("<<")
            i += 1
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _skip_heredoc(text: str, start: int, delimiter: str) -> int:
    """The index of the newline that ends a heredoc body, or the end of the text."""
    j = start
    while j <= len(text):
        end = text.find("\n", j)
        if end == -1:
            return len(text)
        if text[j:end].strip() == delimiter:
            return end
        j = end + 1
    return len(text)


@dataclass
class Simple:
    words: list[str]
    redirects: list[tuple[str, str]]


def split_commands(text: str) -> list[Simple]:
    lexer = shlex.shlex(normalise(text), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    commands: list[Simple] = []
    current = Simple([], [])
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"[();&|]+", token):
            if current.words or current.redirects:
                commands.append(current)
            current = Simple([], [])
        elif re.fullmatch(r"[<>&]+", token) and ("<" in token or ">" in token):
            if i + 1 < len(tokens) and not re.fullmatch(r"[();&|<>]+", tokens[i + 1]):
                current.redirects.append((token, tokens[i + 1]))
                i += 1
        else:
            current.words.append(";" if token == SEMI else token)
        i += 1
    if current.words or current.redirects:
        commands.append(current)
    return commands


def substitutions(word: str) -> list[str]:
    """The commands inside `$(...)` and backticks in a quoted word."""
    found: list[str] = []
    i = 0
    while i < len(word):
        if word.startswith("$(", i):
            depth, j = 1, i + 2
            while j < len(word) and depth:
                depth += {"(": 1, ")": -1}.get(word[j], 0)
                j += 1
            found.append(word[i + 2 : j - 1 if depth == 0 else j])
            i = j
        elif word[i] == "`":
            j = word.find("`", i + 1)
            if j == -1:
                break
            found.append(word[i + 1 : j])
            i = j + 1
        else:
            i += 1
    return found


ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# wrapper: (options that take a value, positional words to skip)
WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "command": (frozenset(), 0),
    "exec": (frozenset({"-a"}), 0),
    "nohup": (frozenset(), 0),
    "time": (frozenset({"-f", "-o"}), 0),
    "builtin": (frozenset(), 0),
    "setsid": (frozenset(), 0),
    "env": (frozenset({"-u", "-C", "-S"}), 0),
    "nice": (frozenset({"-n"}), 0),
    "ionice": (frozenset({"-c", "-n", "-p"}), 0),
    "timeout": (frozenset({"-s", "-k"}), 1),
    "stdbuf": (frozenset({"-i", "-o", "-e"}), 0),
    "sudo": (frozenset({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}), 0),
    "doas": (frozenset({"-u", "-C"}), 0),
    "xargs": (frozenset({"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"}), 0),
    "caffeinate": (frozenset({"-t", "-w"}), 0),
}


def program_name(word: str) -> str:
    return os.path.basename(word.lstrip("\\"))


# Words of the shell's own grammar. They come before a command but are not the command.
KEYWORDS = frozenset(
    {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "esac"}
)


def _split_string_option(option: str, rest: list[str]) -> list[str] | None:
    """The words of `env -S 'words'` or `env --split-string=words`, or None."""
    text: str | None = None
    if option in {"-S", "--split-string"}:
        text = rest.pop(0) if rest else ""
    elif option.startswith("--split-string="):
        text = option.split("=", 1)[1]
    else:
        # Clustered short flags such as `-iS` and `-vS` split like `-S`.
        cluster = re.fullmatch(r"-[iv0]*S(.*)", option, re.DOTALL)
        if cluster:
            text = cluster.group(1) if cluster.group(1) else (rest.pop(0) if rest else "")
    if text is None:
        return None
    try:
        return shlex.split(text)
    except ValueError:
        return []


def unwrap(words: Sequence[str]) -> list[str]:
    rest = list(words)
    while rest:
        if rest[0] in KEYWORDS:
            rest.pop(0)
            continue
        if rest[0] == "function":
            del rest[:2]
            continue
        if ASSIGNMENT.match(rest[0]):
            rest.pop(0)
            continue
        name = program_name(rest[0])
        if name not in WRAPPERS:
            break
        value_options, skip = WRAPPERS[name]
        rest.pop(0)
        while rest and rest[0].startswith("-") and rest[0] != "-":
            option = rest.pop(0)
            if name == "env":
                inner = _split_string_option(option, rest)
                if inner is not None:
                    rest[0:0] = inner
                    break
            if option in value_options and rest:
                rest.pop(0)
        for _ in range(skip):
            if rest and not rest[0].startswith("-"):
                rest.pop(0)
    return rest


# --- the rules ---------------------------------------------------------------------

VALUE_PUSH_OPTIONS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
HOOKS_PATH_WHAT = "core.hooksPath moves the git hooks, so the checks in them stop running."
HOOKS_PATH_NEXT = "leave core.hooksPath alone. Ask the person to change it."
GIT_VALUE_OPTIONS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
PUSH_NEXT = (
    "push the piece's own branch, such as git push origin <branch>, then open a pull request."
)


def _has_short(arg: str, letter: str) -> bool:
    return arg.startswith("-") and not arg.startswith("--") and letter in arg[1:]


def check_push(args: Sequence[str], cwd: Path) -> Decision | None:
    force = False
    broad = ""
    delete = False
    tags = False
    positionals: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            positionals.extend(args[i + 1 :])
            break
        if arg.startswith("--"):
            name = arg.split("=", 1)[0]
            if name in {"--force", "--force-with-lease", "--force-if-includes"}:
                force = True
            elif name in {"--all", "--mirror"}:
                broad = name
            elif name == "--delete":
                delete = True
            elif name == "--tags":
                tags = True
            if name in VALUE_PUSH_OPTIONS and "=" not in arg:
                i += 1
        elif arg.startswith("-") and len(arg) > 1:
            if _has_short(arg, "f"):
                force = True
            if arg == "-o":
                i += 1
        else:
            positionals.append(arg)
        i += 1
    if force:
        return refuse("a force push can destroy work that others hold.", PUSH_NEXT)
    if broad:
        return refuse(f"git push {broad} pushes every branch, `main` included.", PUSH_NEXT)
    refspecs = positionals[1:]
    unresolved = False
    implicit = not refspecs and not tags
    for spec in refspecs:
        if any(ch in spec for ch in "$`*?["):
            unresolved = True
            continue
        if spec.startswith("+"):
            return refuse("a refspec that starts with + forces the push.", PUSH_NEXT)
        if spec in {"HEAD", "@"} and not delete:
            implicit = True
            continue
        dest = spec.split(":")[-1]
        for prefix in ("refs/heads/", "heads/"):
            if dest.startswith(prefix):
                dest = dest[len(prefix) :]
        if dest == PROTECTED_BRANCH:
            return refuse(
                f"a push to {PROTECTED_BRANCH} skips the pull request.",
                PUSH_NEXT,
            )
    if implicit and not delete:
        root = _work_folder(cwd)
        if root is not None and current_branch(root) == PROTECTED_BRANCH:
            return refuse(
                f"this push names no branch while {PROTECTED_BRANCH} is checked out.",
                PUSH_NEXT,
            )
    if unresolved:
        return ask(
            "the branch to push is held in a variable or a pattern, so it cannot be read.",
            "write the branch name in the command.",
        )
    return None


def _work_folder(cwd: Path) -> Path | None:
    try:
        return _real(loop_paths.find_project_root(cwd))
    except loop_paths.PathError:
        return None


def check_git(args: Sequence[str], cwd: Path) -> Decision | None:
    here = cwd
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            here = _real(os.path.join(here, args[i + 1]))
            i += 2
        elif args[i] in GIT_VALUE_OPTIONS:
            if (
                args[i] == "-c"
                and i + 1 < len(args)
                and args[i + 1].lower().startswith("core.hookspath")
            ):
                return refuse(HOOKS_PATH_WHAT, HOOKS_PATH_NEXT)
            i += 2
        else:
            i += 1
    if i >= len(args):
        return None
    sub, rest = args[i], list(args[i + 1 :])
    if sub == "push":
        return check_push(rest, here)
    if sub == "commit" and any(
        a == "--no-verify" or re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in rest
    ):
        return refuse(
            "git commit --no-verify skips the git hooks that check the commit.",
            "commit without --no-verify. If a hook fails, fix what it names.",
        )
    if sub == "config":
        names = [a.lower() for a in rest if not a.startswith("-")]
        reading = any(a in {"--get", "--get-all", "--list", "-l"} for a in rest)
        if not reading and any(n.startswith("core.hookspath") for n in names):
            return refuse(HOOKS_PATH_WHAT, HOOKS_PATH_NEXT)
        if any(n.startswith("alias.") for n in names) and not reading:
            return refuse(
                "a git alias can hide a refused command behind a short name.",
                "type the full git command. Ask the person to add an alias.",
            )
    if sub == "reset" and "--hard" in rest:
        return refuse(
            "git reset --hard throws away work that is not saved.",
            "git stash, or git reset --soft, and keep the work.",
        )
    if sub == "clean" and any(a == "--force" or _has_short(a, "f") for a in rest):
        return refuse(
            "git clean -f deletes files that Git does not track.",
            "git clean -n shows what it would delete. Ask the person to run the real one.",
        )
    if sub == "reflog" and rest[:1] in (["expire"], ["delete"]):
        return refuse(
            "this throws away the history Git uses to recover lost work.",
            "leave the reflog alone.",
        )
    if sub == "gc" and any(a.startswith("--prune") for a in rest):
        return refuse(
            "git gc --prune throws away the history Git uses to recover lost work.",
            "run a plain git gc, or leave it alone.",
        )
    if (
        sub == "worktree"
        and rest[:1] == ["remove"]
        and any(a == "--force" or _has_short(a, "f") for a in rest)
    ):
        return refuse(
            "a forced worktree removal can throw away unsaved work.",
            "run worktree.sh remove, which keeps a worktree that holds unsaved work.",
        )
    return None


def _label_values(args: Sequence[str]) -> list[str]:
    values: list[str] = []
    names = {"--add-label", "--remove-label", "--label", "-l"}
    i = 0
    while i < len(args):
        arg = args[i]
        raw: str | None = None
        if arg in names and i + 1 < len(args):
            raw = args[i + 1]
            i += 1
        elif arg.split("=", 1)[0] in names and "=" in arg:
            raw = arg.split("=", 1)[1]
        elif arg.startswith("-l") and len(arg) > 2 and not arg.startswith("--"):
            raw = arg[2:]
        if raw is not None:
            values.extend(part.strip().strip("\"'") for part in raw.split(","))
        i += 1
    return values


def _is_state_label(name: str) -> bool:
    return bool(LABEL_FAMILY.match(name)) or name.lower() == NEEDS_YOU


GATE_NEXT_LABEL = (
    "python3 kit/scripts/gate.py move <number> <target>. Only the gate changes these labels."
)

LABEL_MUTATIONS = (
    "addlabelstolabelable",
    "removelabelsfromlabelable",
    "clearlabelsfromlabelable",
    "createlabel",
    "updatelabel",
    "deletelabel",
)
MERGE_MUTATIONS = ("mergepullrequest", "enablepullrequestautomerge")
COMMENT_MUTATIONS = ("addcomment", "addpullrequestreview", "addpullrequestreviewcomment")


def _gh_api(args: Sequence[str]) -> Decision | None:
    value_options = {
        "-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field", "--input",
        "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview",
    }  # fmt: skip
    method = ""
    fields = False
    endpoint = ""
    field_keys: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        name = arg.split("=", 1)[0] if arg.startswith("--") else arg
        value = arg.split("=", 1)[1] if arg.startswith("--") and "=" in arg else None
        if name in value_options:
            if value is None and i + 1 < len(args):
                value = args[i + 1]
                i += 1
            if name in {"-X", "--method"} and value:
                method = value.upper()
            if name in {"-f", "--raw-field", "-F", "--field", "--input"}:
                fields = True
                if value and name != "--input":
                    field_keys.append(value.split("=", 1)[0])
        elif arg.startswith("-X") and len(arg) > 2:
            method = arg[2:].upper()
        elif not arg.startswith("-") and not endpoint:
            endpoint = arg
        i += 1
    write = method in {"POST", "PUT", "PATCH", "DELETE"} or (not method and fields)
    text = " ".join(args).lower()
    if "graphql" in endpoint:
        if any(m in text for m in LABEL_MUTATIONS):
            return refuse("this GraphQL call changes labels.", GATE_NEXT_LABEL)
        if any(m in text for m in MERGE_MUTATIONS):
            return refuse(MERGE_WHAT, MERGE_NEXT)
        if any(m in text for m in COMMENT_MUTATIONS) or re.search(r"\bmutation\b", text):
            return ask("this GraphQL call posts in the person's name.", COMMENT_NEXT)
        return None
    if write and re.search(r"(^|/)pulls/[^/]+/merge/?$", endpoint):
        return refuse(MERGE_WHAT, MERGE_NEXT)
    labels_path = bool(re.search(r"(^|/)labels(/|$)", endpoint))
    label_field = any(k.startswith("labels") for k in field_keys)
    family_text = bool(
        re.search(r"(state|shaping|review)(:|%3a)", text) or NEEDS_YOU in text
    )
    if write and (labels_path or label_field):
        return refuse("this gh api call writes labels.", GATE_NEXT_LABEL)
    if labels_path and family_text:
        return refuse("this gh api call names a state label.", GATE_NEXT_LABEL)
    if write:
        return ask("this call writes to GitHub in the person's name.", COMMENT_NEXT)
    return None


COMMENT_NEXT = "answer the box if the person is here. Otherwise write the words to a file for them."


def check_gh(args: Sequence[str]) -> Decision | None:
    rest: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-R", "--repo"}:
            i += 2
            continue
        if arg.startswith("--repo=") or (arg.startswith("-R") and len(arg) > 2):
            i += 1
            continue
        rest.append(arg)
        i += 1
    group = rest[0] if rest else ""
    action = rest[1] if len(rest) > 1 else ""
    tail = rest[2:]
    if group == "auth":
        if action == "token" or (
            action == "status" and any(a in {"-t", "--show-token"} for a in tail)
        ):
            return refuse(
                "this prints the sign-in token. A builder holds no GitHub credential.",
                "ask the person to run the command that needs the sign-in.",
            )
        return None
    if group == "config" and action == "get" and "oauth_token" in tail:
        return refuse(
            "this prints the sign-in token. A builder holds no GitHub credential.",
            "ask the person to run the command that needs the sign-in.",
        )
    if group == "pr" and action == "merge":
        return refuse(MERGE_WHAT, MERGE_NEXT)
    if group in {"issue", "pr"} and action in {"edit", "create"}:
        values = _label_values(tail)
        if any(_is_state_label(v) for v in values):
            return refuse(
                "this changes a state label or the needs-you flag by hand.", GATE_NEXT_LABEL
            )
        if any("$" in v or "`" in v for v in values):
            return ask(
                "a label is held in a variable, so it cannot be read.",
                "write the label in the command.",
            )
    if (group in {"issue", "pr"} and action in {"create", "edit", "close"}) or (
        group == "release" and action == "create"
    ):
        return ask("this posts to GitHub in the person's name.", COMMENT_NEXT)
    if group == "label" and action in {"create", "edit", "delete"}:
        names = [a for a in tail if not a.startswith("-")][:1]
        names += [
            tail[j + 1] for j, a in enumerate(tail[:-1]) if a in {"--name", "-n"}
        ]
        if any(_is_state_label(n) for n in names):
            return refuse(
                "this creates, edits or deletes a state label.",
                "python3 kit/scripts/gate.py labels --create. Only the gate manages these "
                "labels.",
            )
    if group == "api":
        return _gh_api(rest[1:])
    if group in {"issue", "pr"} and action == "comment":
        return ask("a comment is posted in the person's name.", COMMENT_NEXT)
    if group == "pr" and action == "review":
        return ask("a review is posted in the person's name.", COMMENT_NEXT)
    return None


def check_rm(args: Sequence[str]) -> Decision | None:
    for arg in args:
        if arg == "--":
            break
        if arg == "--recursive" or _has_short(arg, "r") or _has_short(arg, "R"):
            return refuse(
                "a recursive delete removes a folder with everything in it.",
                "name each file to delete, or ask the person to run it.",
            )
    return None


def check_find(args: Sequence[str], cwd: Path, ctx: Context) -> Decision | None:
    if "-delete" in args:
        return refuse(
            "find -delete is a recursive delete.",
            "name each file to delete, or ask the person to run it.",
        )
    i = 0
    while i < len(args):
        if args[i] in {"-exec", "-execdir", "-ok", "-okdir"}:
            inner: list[str] = []
            i += 1
            while i < len(args) and args[i] not in {";", "+"}:
                inner.append(args[i])
                i += 1
            found = check_words(inner, cwd, ctx, depth=1)
            if found is not None:
                return found
        i += 1
    return None


def check_gate(words: Sequence[str]) -> Decision | None:
    for index, word in enumerate(words):
        if program_name(word) != "gate.py":
            continue
        positional = [w for w in words[index + 1 :] if not w.startswith("-")]
        if positional[:1] == ["sync"]:
            return refuse(SYNC_WHAT, SYNC_NEXT)
        if positional[:1] == ["move"] and "done" in positional[1:]:
            return refuse(MERGE_WHAT, MERGE_NEXT)
    return None


MERGE_WHAT = (
    "a merge puts work into main, and only the person decides it. This is a merge, or a move "
    "that ends in a merge."
)
MERGE_NEXT = (
    "tell the person: merge the pull request yourself on GitHub, or run the merge in your own "
    "terminal. A run the person started with run.py --merge-pre-approved merges by itself "
    "when every condition holds."
)
_PULL_REQUEST_SCRIPT = ("loop.run.pull_request", "pull_request.py")


def check_pull_request_merge(words: Sequence[str]) -> Decision | None:
    """`python3 -m loop.run.pull_request merge`, or the script run by its path."""
    for index, word in enumerate(words):
        name = program_name(word)
        if name not in _PULL_REQUEST_SCRIPT and word not in _PULL_REQUEST_SCRIPT:
            continue
        positional = [w for w in words[index + 1 :] if not w.startswith("-")]
        if "merge" in positional:
            return refuse(MERGE_WHAT, MERGE_NEXT)
    return None


SYNC_WHAT = "gate.py sync writes to GitHub with a sign-in. Only the person runs it."
SYNC_NEXT = "tell the person: run gate.py sync yourself, in your own terminal."
_SYNC_WORD = re.compile(r"(?<![\w.-])sync(?![\w-])")
# Words that hide the agent session from the gate, or run a script by another road.
_HIDES_SESSION = re.compile(
    r"\b(?:CLAUDECODE|CLAUDE_CODE_ENTRYPOINT)\b"
    r"|\benv\b(?:\s+-\S+)*\s+(?:-i\b|--ignore-environment\b|-(?=\s))"
)
_INDIRECT_RUN = re.compile(
    r"\b(?:runpy|run_path|run_module|execfile|importlib|__import__|pty|subprocess)\b"
    r"|\bexec\s*\(|\bos\.(?:system|exec\w*|spawn\w*|popen)\b"
)
_SCRIPT_THEN_SYNC = re.compile(r"\.py[\"']?\s+sync(?![\w-])")
_VARIABLE_THEN_SYNC = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?[\"']?\s+sync(?![\w-])")


GATE_HIDDEN_WHAT = (
    "this gate.py command line hides a word behind a variable, a backtick, xargs, eval or an "
    "unset or blanked agent-session variable, so it could reach gate.py sync, which only the "
    "person runs."
)
GATE_HIDDEN_NEXT = (
    "run gate.py with a literal path and a literal command, such as "
    "python3 kit/scripts/gate.py report."
)
# What can build a word the text check cannot read, or hide the agent session.
_GATE_HIDES = re.compile(
    r"[$`]|\b(?:xargs|unset|eval)\b|\benv\b(?:\s+\S+)*?\s+(?:-[a-zA-Z]*[iu]|--unset|--ignore-environment)"
)
# What gives a child a pseudo-terminal, which is what sync's terminal check trusts.
_MAKES_A_TERMINAL = re.compile(r"(?:^|[\s;&|(`])(?:script|unbuffer|expect)(?=\s|$)")
PTY_WHAT = (
    "script, unbuffer and expect give a program a pretend terminal, so with python or gate.py "
    "they could pass gate.py sync's check that a person is typing."
)
PTY_NEXT = "run the python command or gate.py directly, without a pretend terminal."


def check_gate_text(text: str) -> Decision | None:
    """`gate.py sync` reached by a road the word checks cannot follow.

    A `gate.py` line may not hold a variable, a backtick, `xargs`, `eval`,
    `unset`, `env -u`, `env -i` or an agent-session name, whether or not the
    word `sync` is in it: the skills call the gate with a literal path and a
    literal command, so nothing real needs these. `script`, `unbuffer` and
    `expect` are refused beside `python` or `gate.py`. A script copied under
    another name, or Python told to run one with `sync`, is refused too. A text
    check is never complete. The layer that holds is the sandbox, which hides
    the person's GitHub sign-in from every agent session.
    """
    if _MAKES_A_TERMINAL.search(text) and re.search(r"\bpython|gate\.py", text):
        return refuse(PTY_WHAT, PTY_NEXT)
    if "gate.py" in text and (_GATE_HIDES.search(text) or _HIDES_SESSION.search(text)):
        return refuse(GATE_HIDDEN_WHAT, GATE_HIDDEN_NEXT)
    if "pull_request" in text:
        found = _pull_request_text(text)
        if found is not None:
            return found
    if not _SYNC_WORD.search(text):
        return None
    if _SCRIPT_THEN_SYNC.search(text) or _VARIABLE_THEN_SYNC.search(text):
        return refuse(SYNC_WHAT, SYNC_NEXT)
    if _INDIRECT_RUN.search(text) and re.search(r"\bpython", text):
        return refuse(SYNC_WHAT, SYNC_NEXT)
    return None


def _pull_request_text(text: str) -> Decision | None:
    """The pull request script's merge, reached by a road the word check cannot follow.

    As for `gate.py`: a line that holds the script's name may not hold a variable, a
    backtick, `xargs`, `eval`, `unset`, `env -u`, `env -i` or an agent-session name. Python
    told to run the script by `runpy` or an import, with the word `merge` in the line, is
    refused. A pretend terminal beside python is refused above. A text check is never
    complete: the in-code refusal and the sandbox hold behind it.
    """
    if _GATE_HIDES.search(text) or _HIDES_SESSION.search(text):
        return refuse(MERGE_WHAT, MERGE_NEXT)
    if re.search(r"\bmerge\b", text) and _INDIRECT_RUN.search(text) and re.search(r"\bpython", text):
        return refuse(MERGE_WHAT, MERGE_NEXT)
    if re.search(r"\bpython", text) and re.search(
        r"\b(?:import|from)\b[^;\n]*\bpull_request\b", text
    ):
        return refuse(MERGE_WHAT, MERGE_NEXT)
    return None


def check_security(args: Sequence[str]) -> Decision | None:
    if args[:1] and args[0] in {
        "find-generic-password",
        "find-internet-password",
        "dump-keychain",
    }:
        return refuse(
            "this reads a secret from the keychain.",
            "ask the person to run the command that needs the secret.",
        )
    return None


WRITES_ALL = {
    "tee", "touch", "truncate", "chmod", "chown", "unlink", "shred", "mkdir", "rmdir", "rm",
    "mv", "patch", "ed",
}  # fmt: skip
WRITES_LAST = {"cp", "rsync", "install", "ln"}


def _write_targets(prog: str, args: Sequence[str]) -> list[str]:
    plain = [a for a in args if not a.startswith("-")]
    if prog in WRITES_ALL:
        return plain
    if prog in WRITES_LAST:
        for j, arg in enumerate(args[:-1]):
            if arg in {"-t", "--target-directory"}:
                return [args[j + 1]]
        return plain[-1:]
    if prog in {"sed", "perl", "awk", "gawk"} and any(
        a == "--in-place" or a.startswith("--in-place=") or _has_short(a, "i") for a in args
    ):
        return plain
    if prog == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    return []


SEARCH_ALWAYS = {"rg", "ag", "ack", "tar", "bsdtar", "zip", "ditto", "rsync", "7z", "7za"}
GREPS = {"grep", "egrep", "fgrep", "zgrep"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}


def _reads_a_tree(prog: str, args: Sequence[str]) -> bool:
    """True when the command reads every file under the folders it is given."""
    if prog in SEARCH_ALWAYS:
        return True
    if prog in GREPS:
        return any(
            a.startswith(("--recursive", "--dereference-recursive"))
            or _has_short(a, "r")
            or _has_short(a, "R")
            or a == "recurse"
            for a in args
        )
    if prog in {"cp", "scp"}:
        return any(
            a in {"--recursive", "--archive"} or any(_has_short(a, c) for c in "rRa") for a in args
        )
    if prog == "find":
        return any(a in FIND_EXEC for a in args)
    return False


def check_paths(
    prog: str, args: Sequence[str], redirects: Sequence[tuple[str, str]], cwd: Path, ctx: Context
) -> Decision | None:
    if _reads_a_tree(prog, args):
        for arg in args:
            for path in candidates(arg, cwd, ctx):
                found = covers_protected(path, ctx)
                if found is not None:
                    return found
    if prog not in {"echo", "printf", "cd", "pushd"}:
        for arg in args:
            for path in candidates(arg, cwd, ctx):
                found = read_block(path, ctx)
                if found is not None:
                    return found
    for target in _write_targets(prog, args):
        for path in candidates(target, cwd, ctx):
            found = write_block(path, ctx) or read_block(path, ctx, write=True)
            if found is not None:
                return found
    for op, target in redirects:
        for path in candidates(target, cwd, ctx):
            if ">" in op:
                found = write_block(path, ctx) or read_block(path, ctx, write=True)
            else:
                found = read_block(path, ctx)
            if found is not None:
                return found
    return None


def _first_decision(found: Sequence[Decision | None]) -> Decision | None:
    asks = [d for d in found if d is not None and d.kind == ASK]
    for decision in found:
        if decision is not None and decision.kind == DENY:
            return decision
    return asks[0] if asks else None


def check_words(
    words: Sequence[str],
    cwd: Path,
    ctx: Context,
    redirects: Sequence[tuple[str, str]] = (),
    depth: int = 0,
) -> Decision | None:
    if depth > 8:
        return ask("the command nests too deeply to read.", "run the parts one by one.")
    found: list[Decision | None] = []
    for word in words:
        for inner in substitutions(word):
            found.append(check_command(inner, ctx, cwd, depth + 1))
    rest = unwrap(words)
    found.append(check_gate(rest))
    found.append(check_pull_request_merge(rest))
    if rest:
        prog, args = program_name(rest[0]), rest[1:]
        if prog in SHELLS:
            for j, arg in enumerate(args):
                if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                    if j + 1 < len(args):
                        found.append(check_command(args[j + 1], ctx, cwd, depth + 1))
                    break
        elif prog == "eval":
            found.append(check_command(" ".join(args), ctx, cwd, depth + 1))
        elif prog == "git":
            found.append(check_git(args, cwd))
        elif prog == "gh":
            found.append(check_gh(args))
        elif prog == "rm":
            found.append(check_rm(args))
        elif prog == "find":
            found.append(check_find(args, cwd, ctx))
        elif prog == "security":
            found.append(check_security(args))
        found.append(check_paths(prog, args, redirects, cwd, ctx))
    elif redirects:
        found.append(check_paths("", [], redirects, cwd, ctx))
    return _first_decision(found)


def check_command(
    command: str, ctx: Context, cwd: Path | None = None, depth: int = 0
) -> Decision | None:
    here = cwd or ctx.cwd
    try:
        simples = split_commands(command)
    except ValueError:
        return ask(
            "the command cannot be read, for example because a quote is not closed.",
            "write the command in a simpler form.",
        )
    found: list[Decision | None] = []
    stack: list[Path] = []
    previous: list[Path] = []
    for simple in simples:
        found.append(check_words(simple.words, here, ctx, simple.redirects, depth))
        here, ctx = _after(simple.words, here, ctx, stack, previous)
    return _first_decision(found)


def _after(
    words: Sequence[str], here: Path, ctx: Context, stack: list[Path], previous: list[Path]
) -> tuple[Path, Context]:
    """The folder and variables that the next command on the line sees."""
    rest = unwrap(words)
    if not rest:
        assigned = {w.split("=", 1)[0]: expand(w.split("=", 1)[1], ctx) for w in words
                    if ASSIGNMENT.match(w)}
        return here, replace(ctx, vars={**ctx.vars, **assigned})
    prog, args = program_name(rest[0]), rest[1:]
    if prog in {"export", "declare", "typeset", "local", "readonly"}:
        assigned = {a.split("=", 1)[0]: expand(a.split("=", 1)[1], ctx) for a in args
                    if ASSIGNMENT.match(a)}
        return here, replace(ctx, vars={**ctx.vars, **assigned})
    if prog == "popd":
        return (stack.pop() if stack else here), ctx
    if prog in {"cd", "pushd"}:
        targets = [a for a in args if not a.startswith("-") or a == "-"]
        text = expand(targets[0], ctx) if targets else str(ctx.home)
        if text == "-" and prog == "cd" and previous:
            back = previous[0]
            previous[:] = [here]
            return back, ctx
        if text == "-" or "$" in text or any(ch in text for ch in "*?["):
            return here, ctx
        new = _real(os.path.join(here, text))
        if new.is_dir():
            if prog == "pushd":
                stack.append(here)
            previous[:] = [here]
            return new, ctx
    return here, ctx


# --- tool calls --------------------------------------------------------------------


def _mcp(name: str, tool_input: Mapping[str, Any]) -> Decision | None:
    lowered = name.lower()
    if not (lowered.startswith("mcp__") and "github" in lowered):
        return None
    if "labels" in tool_input:
        names: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, str):
                names.extend(p.strip() for p in value.split(","))
            elif isinstance(value, dict):
                walk(value.get("name", ""))
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(tool_input["labels"])
        if any(_is_state_label(n) for n in names):
            return refuse(
                "this tool call changes a state label or the needs-you flag.", GATE_NEXT_LABEL
            )
    verb = lowered.split("__")[-1]
    if not verb.startswith(("get_", "list_", "search_", "read_")) and (
        "comment" in verb or "review" in verb
    ):
        return ask("this tool call posts in the person's name.", COMMENT_NEXT)
    return None


def decide(payload: Mapping[str, Any], env: Mapping[str, str]) -> Decision:
    name = str(payload.get("tool_name") or "")
    raw_input = payload.get("tool_input")
    tool_input: Mapping[str, Any] = raw_input if isinstance(raw_input, dict) else {}
    ctx = build_context(str(payload.get("cwd") or ""), env)
    found: Decision | None = None
    if name == "Bash":
        command = str(tool_input.get("command") or "")
        found = (check_gate_text(command) or check_command(command, ctx)) if command else None
    elif name in WRITE_TOOLS or name in READ_TOOLS:
        keys = WRITE_TOOLS.get(name) or READ_TOOLS[name]
        for key in keys:
            value = tool_input.get(key)
            if not isinstance(value, str) or not value:
                continue
            for path in candidates(value, ctx.cwd, ctx):
                if name in WRITE_TOOLS:
                    found = write_block(path, ctx) or read_block(path, ctx, write=True)
                else:
                    found = read_block(path, ctx)
                    if found is None and name in {"Grep", "Glob"}:
                        found = covers_protected(path, ctx)
                if found is not None:
                    break
            break
    else:
        found = _mcp(name, tool_input)
    return found or PASS


def target_of(payload: Mapping[str, Any]) -> str:
    raw = payload.get("tool_input")
    tool_input: Mapping[str, Any] = raw if isinstance(raw, dict) else {}
    for key in ("command", "file_path", "notebook_path", "path", "pattern"):
        if isinstance(tool_input.get(key), str):
            return str(tool_input[key])
    return ""


def _log(payload: Mapping[str, Any], event: str, reason: str, env: Mapping[str, str]) -> None:
    """Write the decision to the command log. A fault here never stops the guard."""
    try:
        spec = importlib.util.spec_from_file_location("command_log", HERE / "command-log.py")
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.record(payload, event, reason, env)
    except Exception:
        return


def main(
    stdin: TextIO, stdout: TextIO, stderr: TextIO, env: Mapping[str, str] | None = None
) -> int:
    env = os.environ if env is None else env
    try:
        payload = json.loads(stdin.read())
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        stderr.write(
            "The guard refused this call. It could not read the hook input, which is not "
            "a JSON object.\n"
            "next: check that Claude Code runs this hook as a PreToolUse hook.\n"
        )
        return 2
    try:
        decision = decide(payload, env)
    except Exception as error:
        decision = ask(
            f"the guard hit a fault ({type(error).__name__}) and cannot judge this call.",
            "report the fault to the person.",
        )
    event = {ALLOW: "pass", ASK: "ask", DENY: "refuse"}[decision.kind]
    _log(payload, event, decision.reason, env)
    if decision.kind == DENY:
        stderr.write(decision.reason + "\n")
        return 2
    if decision.kind == ASK:
        stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": decision.reason,
                    }
                }
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stdout, sys.stderr))
