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

This is a plain word check, not a full shell parser. The gate checks state;
settings deny rules check the rest.
"""
import getopt
import json
import os
import re
import shlex
import subprocess
import sys
from typing import Optional

SPLIT = re.compile(r"&&|\|\||;|\||\n|\$\(|`")


def _path_covers(declared: str, actual: str) -> bool:
    declared = declared.replace("\\", "/").strip("/")
    actual = actual.replace("\\", "/").strip("/")
    return bool(declared) and (actual == declared or actual.startswith(declared + "/")
                               or ("/" + declared + "/") in ("/" + actual + "/"))


def _protected_paths(name: str) -> list[str]:
    return [item.strip().strip("`") for item in
            os.environ.get(name, "").split(os.pathsep) if item.strip()]


def words(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


WRAPPER_OPTIONS = {
    "env": ("i0vu:C:", ["ignore-environment", "null", "unset=", "chdir="]),
    "sudo": ("AbEHKkNnPSVu:g:h:p:C:R:D:T:r:t:", ["user=", "group=", "host=", "prompt="]),
    "command": ("pvV", []), "exec": ("cla:", []), "nohup": ("", []),
    "time": ("pvf:o:", ["portability", "verbose", "format=", "output=", "quiet"]),
}


def strip_prefix(w: list[str]) -> list[str]:
    while w:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]):
            w.pop(0)
            continue
        wrapper = os.path.basename(w[0])
        if wrapper not in WRAPPER_OPTIONS:
            break
        try:
            _, w = getopt.getopt(w[1:], *WRAPPER_OPTIONS[wrapper])
        except getopt.GetoptError as error:
            raise ValueError("unknown wrapper option") from error
    return w


def current_branch(path: str = "") -> str:
    command = ["git"]
    if path:
        command.extend(["-C", path])
    command.extend(["branch", "--show-current"])
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def redirect_to_protected(command: str) -> bool:
    protected = _protected_paths("LOOP_PROTECTED_PATHS")
    exceptions = _protected_paths("LOOP_PROTECTED_EXCEPTIONS")
    for match in re.finditer(r"(?:^|\s)(?:\d*>>?)\s*(['\"]?)([^\s'\"]+)\1", command):
        target = match.group(2).replace("\\", "/")
        parts = target.strip("/").split("/")
        if ".claude" in parts or ".githooks" in parts:
            return True
        if (any(_path_covers(item, target) for item in protected)
                and not any(_path_covers(item, target) for item in exceptions)):
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
            w = words(raw)
        if not w:
            continue
        prog, rest = os.path.basename(w[0]), w[1:]
        if prog == "eval":
            if builder:
                return "eval is not allowed. Run a plain command."
            evaluated = " ".join(rest)
            substitution = re.fullmatch(r"\$\((.*)\)", evaluated.strip())
            if substitution:
                evaluated = substitution[1]
            refused = check_command(evaluated, builder) if evaluated else None
            if refused:
                return refused
        if prog == "xargs" and any(os.path.basename(arg) == "rm" for arg in rest):
            if any(re.fullmatch(r"-[rRf]+", arg) for arg in rest):
                return "xargs rm with recursive or force flags is not allowed."
        if builder and prog in ("perl", "ruby") and "-e" in rest:
            return f"{prog} -e is not allowed in a build session."
        if prog in ("bash", "sh", "zsh"):
            option = next((arg for arg in rest if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", arg)), None)
            if option:
                index = rest.index(option)
                if builder and option != "-c":
                    return "combined shell flags are not allowed in a build session. Use plain `bash -c`."
                if index + 1 < len(rest):
                    refused = check_command(rest[index + 1], builder)
                    if refused:
                        return refused
                elif builder:
                    return "the shell command form could not be unwrapped safely."
        if prog == "git":
            index = 0
            git_cwd = ""
            while index < len(rest):
                arg = rest[index]
                if arg == "-C" and index + 1 < len(rest):
                    git_cwd = rest[index + 1]
                elif arg not in ("-C", "-c", "--git-dir", "--work-tree") and not (
                        arg.startswith("--git-dir=") or arg.startswith("--work-tree=")):
                    break
                index += 1 if "=" in arg else 2
            rest = rest[index:]
        if prog == "gh":
            while len(rest) > 1 and rest[0] in ("-R", "--repo"):
                rest = rest[2:]
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
                branch = current_branch(git_cwd)
                if not targets and branch in ("main", "master"):
                    return "an unqualified push from main is not allowed. Push a named piece branch."
                if (branch == "main" and targets == ["origin"]):
                    return "an origin push without a refspec from main is not allowed. Push a named piece branch."
                if any(re.search(r"(^|:)(refs/heads/)?(main|master)$", t) or t.startswith("+")
                       for t in targets[1:]):
                    return "pushing to main is not allowed. Open a pull request."

        if prog == "gh":
            if builder:
                return "builders never run gh. The run talks to GitHub after the gate checks your work."
            joined = " ".join(rest)
            if rest[:2] == ["pr", "merge"]:
                return "agents do not merge. The person merges the pull request."
            if ("state:" in joined and rest[:1] == ["label"] and rest[1:2]
                    and rest[1] in ("create", "edit", "delete")):
                return "state labels belong to the gate. Use gate.py."
            if "state:" in joined and (rest[:2] in (["issue", "edit"], ["pr", "edit"]) or rest[:1] == ["api"]):
                return "only the gate moves a piece. Use gate.py move."
    return None


def check_path(path: str) -> Optional[str]:
    parts = path.replace("\\", "/").split("/")
    if ".claude" in parts or ".githooks" in parts:
        return "builders never change .claude/ or .githooks/."
    protected = _protected_paths("LOOP_PROTECTED_PATHS")
    exceptions = _protected_paths("LOOP_PROTECTED_EXCEPTIONS")
    normal = path.replace("\\", "/").rstrip("/")
    if (any(_path_covers(item, normal) for item in protected)
            and not any(_path_covers(item, normal) for item in exceptions)):
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
