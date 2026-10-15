#!/usr/bin/env python3
"""The guard: a Claude Code PreToolUse hook that refuses the few hard rules.

It reads the tool call as JSON on stdin. Exit 2 refuses the call, and the
message on stderr tells the agent why. Exit 0 lets it through.

Everywhere:
  - no push to main, and no force push;
  - no recursive delete;
  - no state label written by hand (only the gate moves a piece);
  - no merge by an agent (the person merges).
In a builder session (LOOP_BUILDER=1) also:
  - no push at all, and no `gh` (the run does both after the gate checks);
  - no change under .claude/ or .githooks/.

This is a plain word check, not a full shell parser. It catches the plain
forms. The gate is the second layer for state; settings deny rules are the
second layer for the rest.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from typing import Optional

SPLIT = re.compile(r"&&|\|\||;|\||\n|\$\(|`")


def words(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def strip_prefix(w: list[str]) -> list[str]:
    """Drop leading env assignments and wrappers like sudo, env, command."""
    while w and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]) or
                 w[0] in ("sudo", "env", "command", "exec", "nohup", "time")):
        w = w[1:]
    return w


def current_branch() -> str:
    result = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                            text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def redirect_to_protected(command: str) -> bool:
    protected = [item.strip().strip("`").replace("\\", "/") for item in
                 os.environ.get("LOOP_PROTECTED_PATHS", "").split(os.pathsep) if item.strip()]
    for match in re.finditer(r"(?:^|\s)(?:\d*>>?)\s*(['\"]?)([^\s'\"]+)\1", command):
        target = match.group(2).replace("\\", "/")
        parts = target.strip("/").split("/")
        if ".claude" in parts or ".githooks" in parts:
            return True
        if any(target == item.rstrip("/") or target.startswith(item.rstrip("/") + "/")
               or ("/" + item.rstrip("/") + "/") in ("/" + target.strip("/") + "/")
               for item in protected):
            return True
    return False


def check_command(cmd: str, builder: bool) -> Optional[str]:
    if builder and redirect_to_protected(cmd):
        return "builders never redirect into .claude/, .githooks/ or a protected path."
    if re.search(r"\bpython(?:3)?\b[^\n]*\s-c\s", cmd) and re.search(
            r"\bshutil\s*\.\s*rmtree\b|\brm\s+-[a-zA-Z]*[rR]", cmd):
        return "recursive delete is not allowed. Ask the person."
    if re.search(r"\bnode\b[^\n]*\s-e\s", cmd) and re.search(
            r"\brm\s+-[a-zA-Z]*[rR]", cmd):
        return "recursive delete is not allowed. Ask the person."
    for segment in SPLIT.split(cmd):
        raw = segment.strip()
        if re.search(r"(?:^|\s)GIT_CONFIG_(?:COUNT|KEY_\d+|VALUE_\d+)=", raw):
            return "GIT_CONFIG_COUNT command injection is not allowed. Use plain git commands."
        try:
            w = strip_prefix(shlex.split(raw))
        except ValueError:
            if builder:
                return "the command could not be read safely in a build session. Simplify it and try again."
            w = strip_prefix(words(raw))
        if not w:
            continue
        prog, rest = os.path.basename(w[0]), w[1:]
        if prog == "eval":
            return "eval is not allowed. Run a plain command."
        if prog == "xargs" and any(os.path.basename(arg) == "rm" for arg in rest):
            return "xargs rm is not allowed. Run rm on named files directly."
        if builder and prog in ("perl", "ruby") and "-e" in rest:
            return f"{prog} -e is not allowed in a build session."
        if prog in ("bash", "sh", "zsh"):
            option = next((arg for arg in rest if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", arg)), None)
            if option:
                index = rest.index(option)
                if builder and option != "-c":
                    return "combined shell flags are not allowed in a build session. Use plain `bash -c`."
                if index + 1 >= len(rest):
                    if builder:
                        return "the shell command form could not be unwrapped safely."
                else:
                    refused = check_command(rest[index + 1], builder)
                    if refused:
                        return refused
        if prog in ("python", "python3", "node"):
            flag = "-c" if prog.startswith("python") else "-e"
            if flag in rest:
                code = rest[rest.index(flag) + 1] if rest.index(flag) + 1 < len(rest) else ""
                if re.search(r"\bshutil\s*\.\s*rmtree\b|\brm\s+-[a-zA-Z]*[rR]", code):
                    return "recursive delete is not allowed. Ask the person."
        if prog == "git":
            index = 0
            while index < len(rest):
                if rest[index] in ("-C", "-c", "--git-dir", "--work-tree"):
                    index += 2
                elif rest[index].startswith("--git-dir=") or rest[index].startswith("--work-tree="):
                    index += 1
                else:
                    break
            rest = rest[index:]
        if prog == "gh":
            index = 0
            while index < len(rest):
                if rest[index] in ("-R", "--repo"):
                    index += 2
                else:
                    break
            rest = rest[index:]
        flags = [a for a in rest if a.startswith("-")]

        if prog == "rm" and any(a in ("-r", "-R", "--recursive") or
                                (re.match(r"^-[a-zA-Z]+$", a) and ("r" in a or "R" in a))
                                for a in flags):
            return "recursive delete is not allowed. Delete single files, or ask the person."
        if prog == "find" and ("-delete" in rest or "-exec" in rest and "rm" in rest):
            return "deleting through find is not allowed. Ask the person."

        if prog == "git" and rest:
            sub = rest[0]
            if sub == "rm" and any(a in ("-r", "-rf", "-fr") for a in flags):
                return "recursive delete is not allowed. Ask the person."
            if sub == "clean":
                return "git clean deletes untracked work. Ask the person."
            if sub == "push":
                if builder:
                    return "builders never push. The run pushes after the gate checks your work."
                if any(a in ("-f", "--force", "--force-with-lease", "--mirror", "--delete", "-d")
                       or a.startswith("--force") for a in flags):
                    return "force push and remote delete are not allowed."
                targets = [a for a in rest[1:] if not a.startswith("-")]
                if not targets and current_branch() in ("main", "master"):
                    return "an unqualified push from main is not allowed. Push a named piece branch."
                if any(re.search(r"(^|:)(refs/heads/)?(main|master)$", t) or t.startswith("+")
                       for t in targets[1:]):
                    return "pushing to main is not allowed. Open a pull request."

        if prog == "gh":
            if builder:
                return "builders never run gh. The run talks to GitHub after the gate checks your work."
            joined = " ".join(rest)
            if rest[:2] == ["pr", "merge"]:
                return "agents do not merge. The person merges the pull request."
            if rest[:1] == ["label"] and rest[1:2] and rest[1] in ("create", "edit", "delete"):
                if "state:" in joined:
                    return "state labels belong to the gate. Use gate.py."
            if "state:" in joined and (rest[:2] in (["issue", "edit"], ["pr", "edit"]) or rest[:1] == ["api"]):
                return "only the gate moves a piece. Use gate.py move."
    return None


def check_path(path: str) -> Optional[str]:
    parts = path.replace("\\", "/").split("/")
    if ".claude" in parts or ".githooks" in parts:
        return "builders never change .claude/ or .githooks/."
    protected = [item.strip().strip("`") for item in
                 os.environ.get("LOOP_PROTECTED_PATHS", "").split(os.pathsep) if item.strip()]
    normal = path.replace("\\", "/").rstrip("/")
    if any(normal == item.rstrip("/") or normal.startswith(item.rstrip("/") + "/")
           or ("/" + item.rstrip("/") + "/") in (normal + "/")
           for item in protected):
        return "builders and reviewers never edit a protected path. Shape a piece that names it."
    return None


def main() -> int:
    try:
        call = json.load(sys.stdin)
    except ValueError:
        return 0
    tool = call.get("tool_name", "")
    data = call.get("tool_input") or {}
    builder = os.environ.get("LOOP_BUILDER") == "1"
    reason = None
    if tool == "Bash":
        reason = check_command(str(data.get("command", "")), builder)
    elif builder and tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        reason = check_path(str(data.get("file_path") or data.get("notebook_path") or ""))
    if reason:
        print(f"Refused by the loop kit guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
