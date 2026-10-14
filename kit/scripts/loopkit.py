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
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STATES = ("shaping", "ready", "building", "approval", "done", "dropped")
STATE_PREFIX = "state:"
NEEDS_YOU = "needs-you"
RECORD_TAG = "loop-gate"
REASON_TYPES = ("spec-unclear", "bar-wrong", "environment", "builder-failed",
                "person-rejected", "conflict", "judge-gap")
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
    kind: str  # feature, fix, or scaffold
    intent: str = ""
    out_of_scope: tuple = ()
    approach: str = ""
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
    intent_lines = _section(body, "Intent")
    intent = ""
    out_of_scope: list[str] = []
    if intent_lines is None:
        gaps.append("no '## Intent' section")
    else:
        in_scope = False
        for line in intent_lines:
            if re.match(r"^\s*Out of scope\s*:", line, re.IGNORECASE):
                in_scope = True
                continue
            if line.startswith("## "):
                in_scope = False
            elif in_scope:
                if re.match(r"^\s*[-*]\s+\S", line):
                    out_of_scope.append(line.strip()[1:].strip())
            elif line.strip():
                intent += ("\n" if intent else "") + line.strip()
        if not intent:
            gaps.append("'## Intent' is empty")
        if not out_of_scope:
            gaps.append("'## Intent' has no non-empty 'Out of scope:' list")
    approach_lines = _section(body, "Approach")
    approach = "\n".join(line.strip() for line in (approach_lines or []) if line.strip())
    done_when: dict[str, str] = {}
    stays: list[str] = []
    done = _section(body, "Contract")
    if done is None:
        done = _section(body, "Done when")
    if done is None:
        gaps.append("no '## Contract' section")
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
            gaps.append("'## Contract' has no item like '- D1: ...'")

    command, kind, keep, files, settings = "", "feature", "", [], False
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
        if kind not in ("feature", "fix", "scaffold"):
            gaps.append(f"'Kind: {kind}' is unknown; use feature, fix or scaffold")
        if kind != "scaffold" and not files:
            gaps.append("'## Judge' lists no judge files under 'Files:'")
        for f in files:
            if f.startswith("/") or ".." in Path(f).parts:
                gaps.append(f"judge file '{f}' must be a path inside the project")
    if gaps:
        raise Refused("the spec is incomplete: " + "; ".join(gaps),
                      "fix the issue body to match kit/spec-format.md")
    if done_when and len(stays) == len(done_when):
        gaps.append("every Done when item is marked (stays), so there is nothing to build")
    return Spec(done_when, command, files, kind, intent, tuple(out_of_scope), approach,
                keep, tuple(stays), settings)


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


def bar_file_list(root: Path, ref: str, files: list[str]) -> list[str]:
    """Judge files, test support files beside them, and every conftest."""
    if not files:
        return []
    tracked = sh(["git", "ls-tree", "-r", "--name-only", ref], root).stdout.splitlines()
    folders = {str(Path(name).parent) for name in files}
    out = set(files)
    for name in tracked:
        if Path(name).name == "conftest.py" or any(
                folder == "." or name.startswith(folder.rstrip("/") + "/")
                for folder in folders):
            out.add(name)
    return sorted(out)


def _hash_paths(read, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.encode() + b"\0" + read(f) + b"\0")
    return h.hexdigest()


def bar_hash_at(root: Path, ref: str, files: list[str]) -> str:
    """Hash the complete judge bar as it is in a commit."""
    paths = bar_file_list(root, ref, files)

    def read(path: str) -> bytes:
        res = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True)
        if res.returncode != 0:
            raise Refused(f"judge support file '{path}' is not in {ref}",
                          f"commit the judge files and support files on {ref} first")
        return res.stdout

    return _hash_paths(read, paths)


def bar_hash_in(folder: Path, files: list[str]) -> str:
    """Hash the judge files as they are on disk."""
    def read(path: str) -> bytes:
        p = folder / path
        return p.read_bytes() if p.is_file() else b"<missing>"
    return _hash_paths(read, files)


def project_root(folder: Path) -> Path:
    """The person's checkout, even from a worktree or a temporary copy."""
    common = sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], folder).stdout.strip()
    return Path(common).parent


def command_env(folder: Path) -> dict:
    """The environment for judge, prepare and builder commands. Use the folder's
    own .venv when Prepare made one, else the person's checkout's .venv."""
    env = dict(os.environ)
    env["AI_LOOP_KIT_ROOT"] = str(Path(__file__).resolve().parent.parent)
    env["LOOP_PROTECTED_PATHS"] = os.pathsep.join(loop_settings(folder).get("protected paths", []))
    for venv_bin in (folder / ".venv" / "bin", project_root(folder) / ".venv" / "bin"):
        if venv_bin.is_dir():
            env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = str(venv_bin.parent)
            break
    return env


def loop_settings(folder: Path) -> dict:
    """Read test, prepare, quality and boundary settings from AGENTS.md."""
    agents = folder / "AGENTS.md"
    text = agents.read_text(errors="replace") if agents.is_file() else ""
    section = _section(text, "The loop") or []
    out = {}
    for line in section:
        m = re.match(r"^\s*[-*]?\s*(Test|Prepare) command\s*:\s*(.*)$", line, re.IGNORECASE)
        if m and m.group(2).strip().strip("`").strip():
            out[m.group(1).lower()] = m.group(2).strip().strip("`").strip()
            continue
        m = re.match(r"^\s*[-*]?\s*(Quality|Standards|Protected paths)\s*:\s*(.*)$",
                     line, re.IGNORECASE)
        if m:
            key, value = m.group(1).lower(), m.group(2).strip().strip("`").strip()
            if key == "quality":
                out.setdefault(key, []).append(value) if value else None
            elif key == "protected paths":
                out[key] = [p.strip().strip("`") for p in value.split(",") if p.strip()]
            else:
                out[key] = value
    return out


def prepare(folder: Path) -> tuple[bool, str]:
    """Run the project's Prepare command in a fresh folder, if it has one.
    It makes a fresh copy runnable: npm ci, uv sync, docker compose build."""
    command = loop_settings(folder).get("prepare")
    if not command:
        return True, ""
    code, output = run_judge(folder, command, timeout=PREPARE_TIMEOUT)
    return code == 0, output


def untracked_paths(folder: Path) -> set[str]:
    """List untracked paths, including files already ignored by the project."""
    commands = (["git", "ls-files", "--others", "--exclude-standard", "-z"],
                ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"])
    return {path for command in commands for path in sh(command, folder).stdout.split("\0") if path}


def record_prepare_outputs(folder: Path, before: set[str], before_dirs: set[str]) -> list[str]:
    """Exclude new Prepare output in this worktree and record it for the gate."""
    added = untracked_paths(folder) - before
    paths = set()
    for path in added:
        first, separator, _ = path.partition("/")
        paths.add(first + "/" if separator and first not in before_dirs else path)
    if not paths:
        return []

    git_dir = Path(sh(["git", "rev-parse", "--absolute-git-dir"], folder).stdout.strip())
    info = git_dir / "info"
    info.mkdir(parents=True, exist_ok=True)
    marker = info / "ai-loop-kit-prepare-paths"
    exclude = Path(sh(["git", "rev-parse", "--path-format=absolute", "--git-path",
                       "info/exclude"], folder).stdout.strip())
    recorded = set(marker.read_text().splitlines()) if marker.exists() else set()
    recorded.update(paths)
    marker.write_text("\n".join(sorted(recorded)) + "\n")

    existing = exclude.read_text().splitlines() if exclude.exists() else []
    patterns = {"/" + path for path in paths}
    missing = sorted(patterns - set(existing))
    if missing:
        text = exclude.read_text() if exclude.exists() else ""
        exclude.write_text(text + ("" if not text or text.endswith("\n") else "\n")
                           + "\n".join(missing) + "\n")
    return sorted(recorded)


def run_judge(folder: Path, command: str, timeout: int = JUDGE_TIMEOUT) -> tuple[int, str]:
    """Run the judge command. The gate calls this; it never trusts a report."""
    proc = None
    try:
        proc = subprocess.Popen(command, shell=True, cwd=folder, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=command_env(folder),
                                start_new_session=True)
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, _TERMINAL_CODES.sub("", stdout + stderr)
    except subprocess.TimeoutExpired:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
        return 124, f"the judge ran past {timeout} seconds"


def skipped_tests(output: str) -> bool:
    """Recognise skipped counts in pytest, vitest and jest summaries."""
    patterns = (r"\b[1-9]\d*\s+skipped\b", r"\bskipped\s*:\s*[1-9]\d*\b")
    return any(re.search(pattern, line, re.IGNORECASE)
               for line in output.splitlines() for pattern in patterns)


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

    def edit_body(self, n: int, body: str) -> None:
        self._gh("issue", "edit", str(n), "--body-file", "-", stdin=body)

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

    def main_protection(self) -> str:
        """Report main's protection without turning a missing rule into a doctor failure."""
        try:
            repo = self._gh("repo", "view", "--json", "nameWithOwner", "--jq",
                            ".nameWithOwner").strip()
        except (RuntimeError, AttributeError):
            return "unknown"
        result = subprocess.run(["gh", "api", f"repos/{repo}/branches/main/protection"],
                                cwd=self.root, capture_output=True, text=True)
        if result.returncode == 0:
            return "enabled"
        if "404" in result.stderr or "Not Found" in result.stderr:
            return "disabled"
        return "unknown"

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
