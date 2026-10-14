"""Shared code for the gate and the run: the spec, the bar, git and GitHub.

Standard library only. The gate and the run import this file. Nothing here
moves a piece; that is the gate's job (gate.py).
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STATES = ("shaping", "ready", "building", "approval", "done", "dropped")
STATE_PREFIX = "state:"
NEEDS_YOU = "needs-you"
RECORD_TAG = "loop-gate"
# Comment authors whose gate records count: people who can push already.
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
JUDGE_TIMEOUT = 900
# Colour codes and terminal links that tools print. Issue comments show them raw.
_TERMINAL_CODES = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
PREPARE_TIMEOUT = 1800


class Refused(Exception):
    """A gate refusal: what is wrong, and the next step that fixes it."""

    def __init__(self, reason: str, next_step: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_step = next_step


# ---------------------------------------------------------------- the spec

@dataclass
class Spec:
    done_when: dict[str, str]
    command: str
    files: list[str]
    kind: str  # "test", or "scaffold" for the first piece of an empty project
    keep: str = ""  # a command that passes on main and must still pass after the build
    stays: tuple = ()  # Done when IDs that already hold on main and must keep holding
    settings: bool = False  # True when the piece may change the project's check settings


_ITEM = re.compile(r"^\s*[-*]\s*(D\d+)\s*(\(stays\))?\s*[:.)]\s*(\S.*)$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*(Command|Files|Kind|Keep|Settings)\s*:\s*(.*)$", re.IGNORECASE)


def _section(body: str, name: str) -> Optional[list[str]]:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == f"## {name}".lower():
            out = []
            for rest in lines[i + 1:]:
                if rest.startswith("## "):
                    break
                out.append(rest)
            return out
    return None


def parse_spec(body: str) -> Spec:
    """Read the spec from an issue body. Refuse with every gap at once."""
    gaps: list[str] = []
    done_when: dict[str, str] = {}
    stays: list[str] = []
    done = _section(body, "Done when")
    if done is None:
        gaps.append("no '## Done when' section")
    else:
        for line in done:
            m = _ITEM.match(line)
            if m:
                if m.group(1) in done_when:
                    gaps.append(f"spec ID {m.group(1)} is used twice")
                done_when[m.group(1)] = m.group(3).strip()
                if m.group(2):
                    stays.append(m.group(1))
        if not done_when:
            gaps.append("'## Done when' has no item like '- D1: ...'")

    command, kind, keep, files, settings = "", "test", "", [], False
    judge = _section(body, "Judge")
    if judge is None:
        gaps.append("no '## Judge' section")
    else:
        in_files = False
        for line in judge:
            m = _FIELD.match(line)
            if m:
                key, value = m.group(1).lower(), m.group(2).strip()
                in_files = key == "files"
                if key == "command":
                    command = value.strip("`").strip()
                elif key == "kind":
                    kind = value.strip("`").strip().lower()
                elif key == "keep":
                    keep = value.strip("`").strip()
                elif key == "settings":
                    settings = value.strip("`").strip().lower() == "may change"
                    if not settings:
                        gaps.append(f"'Settings: {value}' is unknown; use 'Settings: may change'")
                elif value:
                    files += [f.strip().strip("`") for f in value.split(",") if f.strip()]
            elif in_files and re.match(r"^\s*[-*]\s+\S", line):
                files.append(line.strip()[1:].strip().strip("`"))
        if not command:
            gaps.append("'## Judge' has no 'Command:' line")
        if kind not in ("test", "scaffold"):
            gaps.append(f"'Kind: {kind}' is unknown; use test or scaffold")
        if kind == "test" and not files:
            gaps.append("'## Judge' lists no judge files under 'Files:'")
        for f in files:
            if f.startswith("/") or ".." in Path(f).parts:
                gaps.append(f"judge file '{f}' must be a path inside the project")
    if gaps:
        raise Refused("the spec is incomplete: " + "; ".join(gaps),
                      "fix the issue body to match kit/spec-format.md")
    if done_when and len(stays) == len(done_when):
        gaps.append("every Done when item is marked (stays), so there is nothing to build")
    return Spec(done_when, command, files, kind, keep, tuple(stays), settings)


# ---------------------------------------------------------------- check settings

# Files that set how the project checks itself. A pattern with no slash
# matches the file name in any folder.
CHECK_FILES = [".gitignore", ".github/*", ".eslintrc*", "eslint.config.*", ".xo-config*",
               ".prettierrc*", "prettier.config.*", "tsconfig*.json", "jest.config.*",
               "vitest.config.*", ".mocharc*", "ava.config.*", "ruff.toml", ".ruff.toml",
               ".flake8", "setup.cfg", "tox.ini", "pytest.ini", "mypy.ini", ".mypy.ini",
               ".pylintrc", ".coveragerc", ".pre-commit-config.yaml"]
# Check settings inside files that also hold other things.
PACKAGE_KEYS = ("xo", "eslintConfig", "prettier", "jest", "ava", "mocha", "c8", "nyc", "tsd")
PACKAGE_SCRIPTS = ("test", "pretest", "posttest", "lint")
PYPROJECT_TOOLS = re.compile(r"^\[tool\.(pytest|ruff|mypy|coverage|black|isort|pylint|pyright)\b")


def _package_checks(text: str) -> dict:
    data = json.loads(text) if text.strip() else {}
    scripts = data.get("scripts") or {}
    return {**{k: data.get(k) for k in PACKAGE_KEYS},
            **{f"scripts.{k}": scripts.get(k) for k in PACKAGE_SCRIPTS}}


def _pyproject_checks(text: str) -> dict:
    sections: dict = {}
    current = None
    for line in text.splitlines():
        if line.startswith("["):
            current = line.strip() if PYPROJECT_TOOLS.match(line) else None
        if current:
            sections[current] = sections.get(current, "") + line.strip() + "\n"
    return sections


def _changed_files(folder: Path) -> tuple[str, list[str]]:
    """Where this branch left main, and the files it changes since."""
    base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
    return base, sh(["git", "diff", "--name-only", base], folder).stdout.split()


def conflict_markers(folder: Path) -> list[str]:
    """Changed files that still hold merge conflict markers."""
    _, names = _changed_files(folder)
    names = [f for f in names if (folder / f).is_file()]
    if not names:
        return []
    res = sh(["git", "grep", "-l", "-I", "-E", "^(<<<<<<<|>>>>>>>)( |$)", "--", *names],
             folder, check=False)
    return res.stdout.split()


def changed_check_settings(folder: Path) -> list[str]:
    """The check settings this branch changes, compared with where it left main."""
    base, names = _changed_files(folder)
    changed = []
    for name in names:
        short = name.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(name if "/" in p else short, p) for p in CHECK_FILES):
            changed.append(name)
        elif short in ("package.json", "pyproject.toml"):
            old = sh(["git", "show", f"{base}:{name}"], folder, check=False).stdout
            new = (folder / name).read_text(errors="replace") if (folder / name).is_file() else ""
            read = _package_checks if short == "package.json" else _pyproject_checks
            try:
                before, after = read(old), read(new)
            except ValueError:
                changed.append(f"{name} (unreadable)")
                continue
            changed += [f"{name}: {k}" for k in sorted(set(before) | set(after))
                        if before.get(k) != after.get(k)]
    return changed


def spec_hash(body: str) -> str:
    return hashlib.sha256(body.strip().encode()).hexdigest()


# ---------------------------------------------------------------- git

def sh(args: list[str], cwd: Path, check: bool = True,
       timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and res.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res


def repo_root(start: Path) -> Path:
    return Path(sh(["git", "rev-parse", "--show-toplevel"], start).stdout.strip())


def branch_name(n: int) -> str:
    return f"piece/{n}"


def rev(root: Path, ref: str) -> Optional[str]:
    res = sh(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], root, check=False)
    return res.stdout.strip() or None


def main_ref(root: Path) -> str:
    """The freshest main we can see. Fetch it when there is a remote."""
    if sh(["git", "remote"], root).stdout.strip():
        sh(["git", "fetch", "--quiet", "origin", "main"], root, check=False)
        if rev(root, "origin/main"):
            return "origin/main"
    if rev(root, "main"):
        return "main"
    raise Refused("there is no main branch with a commit",
                  "make a first commit on main and push it")


def bar_hash_at(root: Path, ref: str, files: list[str]) -> str:
    """Hash the judge files as they are in a commit."""
    h = hashlib.sha256()
    for f in sorted(files):
        res = subprocess.run(["git", "show", f"{ref}:{f}"], cwd=root, capture_output=True)
        if res.returncode != 0:
            raise Refused(f"judge file '{f}' is not in {ref}",
                          f"commit the judge files on {ref} first")
        h.update(f.encode() + b"\0" + res.stdout + b"\0")
    return h.hexdigest()


def bar_hash_in(folder: Path, files: list[str]) -> str:
    """Hash the judge files as they are on disk."""
    h = hashlib.sha256()
    for f in sorted(files):
        p = folder / f
        data = p.read_bytes() if p.is_file() else b"<missing>"
        h.update(f.encode() + b"\0" + data + b"\0")
    return h.hexdigest()


def project_root(folder: Path) -> Path:
    """The person's checkout, even from a worktree or a temporary copy."""
    common = sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], folder).stdout.strip()
    return Path(common).parent


def command_env(folder: Path) -> dict:
    """The environment for judge, prepare and builder commands. Use the folder's
    own .venv when Prepare made one, else the person's checkout's .venv."""
    env = dict(os.environ)
    for venv_bin in (folder / ".venv" / "bin", project_root(folder) / ".venv" / "bin"):
        if venv_bin.is_dir():
            env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = str(venv_bin.parent)
            break
    return env


def loop_settings(folder: Path) -> dict:
    """The project's loop settings: the lines 'Test command:' and 'Prepare
    command:' in the '## The loop' section of AGENTS.md, as committed."""
    agents = folder / "AGENTS.md"
    text = agents.read_text(errors="replace") if agents.is_file() else ""
    section = _section(text, "The loop") or []
    out = {}
    for line in section:
        m = re.match(r"^\s*[-*]?\s*(Test|Prepare) command\s*:\s*(.*)$", line, re.IGNORECASE)
        if m and m.group(2).strip().strip("`").strip():
            out[m.group(1).lower()] = m.group(2).strip().strip("`").strip()
    return out


def prepare(folder: Path) -> tuple[bool, str]:
    """Run the project's Prepare command in a fresh folder, if it has one.
    It makes a fresh copy runnable: npm ci, uv sync, docker compose build."""
    command = loop_settings(folder).get("prepare")
    if not command:
        return True, ""
    code, output = run_judge(folder, command, timeout=PREPARE_TIMEOUT)
    return code == 0, output


def run_judge(folder: Path, command: str, timeout: int = JUDGE_TIMEOUT) -> tuple[int, str]:
    """Run the judge command. The gate calls this; it never trusts a report."""
    try:
        res = subprocess.run(command, shell=True, cwd=folder, capture_output=True,
                             text=True, timeout=timeout, env=command_env(folder))
        return res.returncode, _TERMINAL_CODES.sub("", res.stdout + res.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"the judge ran past {timeout} seconds"


# ---------------------------------------------------------------- GitHub

class GitHub:
    """GitHub through the person's own `gh` sign-in."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _gh(self, *args: str, stdin: Optional[str] = None) -> str:
        res = subprocess.run(["gh", *args], cwd=self.root, capture_output=True,
                             text=True, input=stdin)
        if res.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args[:3])} failed: {res.stderr.strip()}")
        return res.stdout

    def issue(self, n: int) -> dict:
        data = json.loads(self._gh("issue", "view", str(n), "--json",
                                   "number,title,body,labels,state"))
        data["labels"] = [lab["name"] for lab in data["labels"]]
        return data

    def issues_with_label(self, label: str, closed_too: bool = False) -> list[dict]:
        state = "all" if closed_too else "open"
        data = json.loads(self._gh("issue", "list", "--state", state, "--label", label,
                                   "--limit", "200", "--json", "number,title,labels"))
        for d in data:
            d["labels"] = [lab["name"] for lab in d["labels"]]
        return data

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        args = ["issue", "create", "--title", title, "--body-file", "-"]
        for lab in labels:
            args += ["--label", lab]
        url = self._gh(*args, stdin=body).strip()
        return int(url.rstrip("/").split("/")[-1])

    def set_labels(self, n: int, add: list[str], remove: list[str]) -> None:
        args = ["issue", "edit", str(n)]
        for lab in add:
            args += ["--add-label", lab]
        for lab in remove:
            args += ["--remove-label", lab]
        if add or remove:
            self._gh(*args)

    def comment(self, n: int, text: str) -> None:
        self._gh("issue", "comment", str(n), "--body-file", "-", stdin=text)

    def comments(self, n: int) -> list[str]:
        """Comments from people who can push to the repository. On a public
        repository anyone can comment, so a gate record from anyone else is
        never read: it could carry a forged judge command."""
        data = json.loads(self._gh("issue", "view", str(n), "--json", "comments"))
        return [c["body"] for c in data["comments"] if c.get("authorAssociation") in TRUSTED]

    def close(self, n: int, reason: str) -> None:
        self._gh("issue", "close", str(n), "--reason", reason)

    def labels(self) -> list[str]:
        data = json.loads(self._gh("label", "list", "--limit", "200", "--json", "name"))
        return [d["name"] for d in data]

    def signed_in(self) -> bool:
        return subprocess.run(["gh", "auth", "status"], cwd=self.root,
                              capture_output=True).returncode == 0

    def ensure_label(self, name: str, color: str, description: str) -> None:
        self._gh("label", "create", name, "--color", color, "--description",
                 description, "--force")

    def create_pr(self, head: str, title: str, body: str) -> str:
        return self._gh("pr", "create", "--base", "main", "--head", head,
                        "--title", title, "--body-file", "-", stdin=body).strip()

    def pr_for_branch(self, branch: str) -> Optional[dict]:
        data = json.loads(self._gh("pr", "list", "--head", branch, "--state", "all",
                                   "--json", "url,state", "--limit", "1"))
        return data[0] if data else None


# ---------------------------------------------------------------- records

def record_text(record: dict, note: str) -> str:
    """A gate record is a comment with a machine line and a plain line."""
    return f"<!-- {RECORD_TAG} {json.dumps(record, sort_keys=True)} -->\n**Gate:** {note}"


def records(comments: list[str]) -> list[dict]:
    out = []
    pat = re.compile(r"<!-- " + RECORD_TAG + r" (\{.*?\}) -->")
    for body in comments:
        m = pat.search(body)
        if m:
            try:
                out.append(json.loads(m.group(1)))
            except ValueError:
                pass
    return out


def last_record(comments: list[str], move: str) -> Optional[dict]:
    found = [r for r in records(comments) if r.get("move") == move]
    return found[-1] if found else None
