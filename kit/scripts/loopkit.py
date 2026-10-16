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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from research import parse_research

STATES = ("shaping", "ready", "building", "approval", "done", "dropped")
STATE_PREFIX = "state:"
NEEDS_YOU = "needs-you"
RECORD_TAG = "loop-gate"
REASON_TYPES = ("spec-unclear", "bar-wrong", "stopped", "environment", "builder-failed",
                "person-rejected", "conflict", "judge-gap")
CAUSES = ("bar-wrong", "builder-failed", "conflict", "dirty-worktree", "import-error",
          "idle", "judge-failed", "judge-gap", "keep-flaky", "other",
          "person-rejected", "person-request", "prepare-failed", "pull-request-failed",
          "quality-failed", "stale-after-main", "stopped", "usage-limit")
# Comment authors whose gate records count: people who can push already.
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
JUDGE_TIMEOUT = 900
DEFAULT_KEEP_LIMIT = 15
# Colour codes and terminal links that tools print. Issue comments show them raw.
_TERMINAL_CODES = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
PREPARE_TIMEOUT = 1800
SECRET_ENV_NAME = re.compile(
    r"(?:^|_)(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIALS?)(?:_|$)|^DATABASE_URL$",
    re.IGNORECASE,
)


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
    kind: str  # feature, fix, scaffold, goal, or gauntlet
    intent: str = ""
    out_of_scope: tuple = ()
    approach: str = ""
    keep: str = ""  # a command that passes on main and must still pass after the build
    stays: tuple = ()  # Done when IDs that already hold on main and must keep holding
    settings: bool = False  # True when the piece may change the project's check settings
    large_files: tuple = ()  # Explicit files allowed to cross the 1,000-line mark
    research: tuple = ()  # Sourced findings used to shape and review the piece
    measure: str = ""
    target: str = ""
    capture: str = ""
    reference: str = ""
    criteria: tuple = ()
    checks: tuple = ()
    playbook: str = ""
    risks: dict = field(default_factory=dict)


_ITEM = re.compile(r"^\s*[-*]\s*(D\d+)\s*(\(stays\))?\s*[:.)]\s*(\S.*)$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*(Command|Files|Kind|Keep|Settings|Large file|Measure|Target|"
                    r"Capture|Reference|Criteria|Playbook)\s*:\s*(.*)$", re.IGNORECASE)
_RISK_FIELD = re.compile(r"^\s*(Protected paths|New dependency|Shared files|Needs services|"
                         r"Open choices)\s*:\s*(.*)$", re.IGNORECASE)


def _risk_items(value: str) -> tuple[str, ...]:
    value = value.strip().strip("`").strip()
    if not value or value.lower() == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


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


def parse_research_section(body: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse the optional Research section through its focused module."""
    return parse_research(_section(body, "Research") or [])


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
    research, research_gaps = parse_research_section(body)
    gaps.extend(research_gaps)
    risk_lines = _section(body, "Risks")
    risk_names = {"protected paths": "protected_paths", "new dependency": "new_dependencies",
                  "shared files": "shared_files", "needs services": "needs_services",
                  "open choices": "open_choices"}
    risks = {value: () for value in risk_names.values()}
    if risk_lines is not None:
        found_risks = set()
        for line in risk_lines:
            if not line.strip():
                continue
            match = _RISK_FIELD.match(line)
            if not match:
                gaps.append(f"unexpected text in Risks section: {line.strip()}")
                continue
            key = match.group(1).lower()
            if key in found_risks:
                gaps.append(f"Risks field '{match.group(1)}' is used twice")
            found_risks.add(key)
            risks[risk_names[key]] = _risk_items(match.group(2))
            if key == "new dependency":
                for dependency in risks["new_dependencies"]:
                    name, separator, reason = dependency.partition(":")
                    if not separator or not name.strip() or not reason.strip():
                        gaps.append("Risks New dependency entries need a name and reason")
        for key in risk_names:
            if key not in found_risks:
                gaps.append(f"Risks section needs '{key.title()}:'")
        if risks["open_choices"]:
            gaps.append("Risks Open choices must be empty at ready")
        for key in ("protected_paths", "shared_files"):
            for path in risks[key]:
                if path.startswith("/") or ".." in Path(path).parts:
                    label = key.replace("_", " ")
                    gaps.append(f"Risks {label} path '{path}' must be inside the project")
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

    command, kind, keep, files, settings, large_files = "", "feature", "", [], False, []
    measure, target, capture, reference, criteria, playbook = "", "", "", "", [], ""
    judge = _section(body, "Judge")
    exit_lines = _section(body, "Exit")
    checks = []
    if exit_lines is not None:
        current = None
        for line in exit_lines:
            heading = re.match(r"^###\s+(Tests|Measure|Critics)\s*$", line, re.IGNORECASE)
            if heading:
                current = {"type": heading.group(1).lower(), "files": [], "criteria": []}
                checks.append(current)
                continue
            if current is None:
                if line.strip():
                    gaps.append("'## Exit' fields must be inside a ### Tests, ### Measure "
                                "or ### Critics check")
                continue
            field = _FIELD.match(line)
            if field:
                key, value = field.group(1).lower(), field.group(2).strip().strip("`").strip()
                if key in ("command", "measure", "capture", "reference", "target"):
                    current[key] = value
                elif key == "files":
                    current["_files"] = True
                    current["files"].extend(
                        f.strip().strip("`") for f in value.split(",") if f.strip())
                elif key == "criteria":
                    current["_criteria"] = True
                    current["criteria"].extend(
                        item.strip() for item in value.split(",") if item.strip())
                else:
                    gaps.append(f"'{field.group(1)}:' does not belong in an Exit check")
            elif (current.get("_files") and re.match(r"^\s*[-*]\s+\S", line)):
                current["files"].append(line.strip()[1:].strip().strip("`"))
            elif (current.get("_criteria") and re.match(r"^\s*[-*]\s+\S", line)):
                current["criteria"].append(line.strip()[1:].strip())
            elif line.strip() and not line.lstrip().startswith("<!--"):
                gaps.append(f"unexpected text in {current['type']} exit check: {line.strip()}")
        if not checks:
            gaps.append("'## Exit' has no checks")
        for check in checks:
            kind_name = check["type"]
            if kind_name == "tests" and (not check.get("command") or not check["files"]):
                gaps.append("Tests exit checks need 'Command:' and files under 'Files:'")
            elif kind_name == "measure" and (not check.get("command") or not check.get("target")
                                                or not check["files"]):
                gaps.append("Measure exit checks need 'Command:', 'Target:' and files "
                            "under 'Files:'")
            elif kind_name == "critics" and (not check.get("capture") or not check.get("reference")
                                                or not check["criteria"] or not check["files"]):
                gaps.append("Critics exit checks need 'Capture:', 'Reference:', non-empty "
                            "'Criteria:' and files under 'Files:'")
            for path in check["files"]:
                if path.startswith("/") or ".." in Path(path).parts:
                    gaps.append(f"exit file '{path}' must be a path inside the project")
        kind = "checks"
        files = list(dict.fromkeys(path for check in checks for path in check["files"]))
        tests = next((check for check in checks if check["type"] == "tests"), None)
        command = tests.get("command", "") if tests else ""
        if len(checks) == 1 and checks[0]["type"] == "measure":
            measure, target = checks[0]["command"], checks[0]["target"]
        if len(checks) == 1 and checks[0]["type"] == "critics":
            capture, reference, criteria = (checks[0]["capture"], checks[0]["reference"],
                                            checks[0]["criteria"])
    elif judge is None:
        gaps.append("no '## Exit' or '## Judge' section")
    else:
        in_files = False
        in_criteria = False
        for line in judge:
            m = _FIELD.match(line)
            if m:
                key, value = m.group(1).lower(), m.group(2).strip()
                in_files = key == "files"
                in_criteria = key == "criteria"
                if key == "command":
                    command = value.strip("`").strip()
                elif key == "kind":
                    kind = value.strip("`").strip().lower()
                elif key == "measure":
                    measure = value.strip("`").strip()
                elif key == "target":
                    target = value.strip("`").strip()
                elif key == "capture":
                    capture = value.strip("`").strip()
                elif key == "reference":
                    reference = value.strip("`").strip()
                elif key == "criteria":
                    criteria.extend([item.strip() for item in value.split(",") if item.strip()])
                elif key == "keep":
                    keep = value.strip("`").strip()
                elif key == "playbook":
                    playbook = value.strip("`").strip().lower()
                    if playbook not in ("", "fix"):
                        gaps.append("'Playbook:' must be 'fix'")
                elif key == "settings":
                    settings = value.strip("`").strip().lower() == "may change"
                    if not settings:
                        gaps.append(f"'Settings: {value}' is unknown; use 'Settings: may change'")
                elif key == "large file":
                    target_path = value.strip("`").strip()
                    if not target_path or target_path.startswith("/") or ".." in Path(target_path).parts:
                        gaps.append("'Large file:' must name a path inside the project")
                    else:
                        if target_path not in large_files:
                            large_files.append(target_path)
                elif value:
                    files += [f.strip().strip("`") for f in value.split(",") if f.strip()]
            elif in_files and re.match(r"^\s*[-*]\s+\S", line):
                files.append(line.strip()[1:].strip().strip("`"))
            elif in_criteria and re.match(r"^\s*[-*]\s+\S", line):
                criteria.append(line.strip()[1:].strip())
        if kind not in ("feature", "fix", "scaffold", "goal", "gauntlet"):
            gaps.append(f"'Kind: {kind}' is unknown; use feature, fix, scaffold, goal or gauntlet")
        if kind in ("feature", "fix", "scaffold") and not command:
            gaps.append("'## Judge' has no 'Command:' line")
        if kind in ("feature", "fix") and not files:
            gaps.append("'## Judge' lists no judge files under 'Files:'")
        if kind == "goal" and (not measure or not target):
            gaps.append("goal judges need 'Measure:' and 'Target:' lines")
        if kind == "goal" and not files:
            gaps.append("goal judges need files under 'Files:' to freeze the measure "
                        "and its support")
        if kind == "gauntlet" and (not capture or not reference or not criteria):
            gaps.append("gauntlet judges need 'Capture:', 'Reference:' and non-empty 'Criteria:'")
        if kind == "gauntlet" and not files:
            gaps.append("gauntlet judges need files under 'Files:' to freeze the capture "
                        "and its support")
        for f in files:
            if f.startswith("/") or ".." in Path(f).parts:
                gaps.append(f"judge file '{f}' must be a path inside the project")
        if not gaps:
            check_type = ("measure" if kind == "goal" else
                          "critics" if kind == "gauntlet" else "tests")
            checks = [{"type": check_type, "command": measure if kind == "goal" else command,
                       "target": target, "capture": capture, "reference": reference,
                       "criteria": criteria, "files": files, "legacy_kind": kind}]
    if judge is not None and exit_lines is not None:
        for line in judge:
            m = _FIELD.match(line)
            if not m:
                continue
            key, value = m.group(1).lower(), m.group(2).strip()
            if key == "keep":
                keep = value.strip("`").strip()
            elif key == "playbook":
                playbook = value.strip("`").strip().lower()
                if playbook not in ("", "fix"):
                    gaps.append("'Playbook:' must be 'fix'")
            elif key == "settings":
                settings = value.strip("`").strip().lower() == "may change"
                if not settings:
                    gaps.append(f"'Settings: {value}' is unknown; use 'Settings: may change'")
            elif key == "large file":
                target_path = value.strip("`").strip()
                if (not target_path or target_path.startswith("/") or
                        ".." in Path(target_path).parts):
                    gaps.append("'Large file:' must name a path inside the project")
                elif target_path not in large_files:
                    large_files.append(target_path)
    if exit_lines is not None and not checks:
        gaps.append("'## Exit' has no valid checks")
    if gaps:
        raise Refused("the spec is incomplete: " + "; ".join(gaps),
                      "fix the issue body to match kit/spec-format.md")
    if done_when and len(stays) == len(done_when):
        gaps.append("every Done when item is marked (stays), so there is nothing to build")
    return Spec(done_when, command, files, kind, intent, tuple(out_of_scope), approach,
                keep, tuple(stays), settings, tuple(large_files), tuple(research),
                measure, target, capture, reference, tuple(criteria), tuple(checks), playbook,
                risks)
# ---------------------------------------------------------------- check settings

# Files that set how the project checks itself. A pattern with no slash
# matches the file name in any folder.
CHECK_FILES = [".gitignore", ".github/*", ".eslintrc*", "eslint.config.*", ".xo-config*",
               ".prettierrc*", "prettier.config.*", "tsconfig*.json", "jest.config.*",
               "vitest.config.*", ".mocharc*", "ava.config.*", "ruff.toml", ".ruff.toml",
               ".flake8", "setup.cfg", "tox.ini", "pytest.ini", "mypy.ini", ".mypy.ini",
               ".pylintrc", ".coveragerc", ".pre-commit-config.yaml", "AGENTS.md"]
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
    return base, sh(["git", "diff", "--no-renames", "--name-only", base], folder).stdout.split()


def conflict_markers(folder: Path) -> list[str]:
    """Changed files that still hold merge conflict markers."""
    _, names = _changed_files(folder)
    names = [f for f in names if (folder / f).is_file()]
    if not names:
        return []
    res = sh(["git", "grep", "-l", "-I", "-E", "^(<<<<<<<|>>>>>>>)( |$)", "--", *names],
             folder, check=False)
    return res.stdout.split()


def changed_check_settings(folder: Path, extra_paths: tuple[str, ...] | list[str] = ()) -> list[str]:
    """The check settings this branch changes, compared with where it left main."""
    base, names = _changed_files(folder)
    changed = []
    for name in names:
        short = name.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(name if "/" in p else short, p)
               for p in (*CHECK_FILES, *extra_paths)):
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
    from procs import main_ref_cache
    cache = main_ref_cache()
    key = sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], root).stdout.strip()
    if cache is not None and key in cache:
        return cache[key]
    if sh(["git", "remote"], root).stdout.strip():
        sh(["git", "fetch", "--quiet", "origin", "main"], root, check=False)
        if rev(root, "origin/main"):
            result = "origin/main"
            if cache is not None:
                cache[key] = result
            return result
    if rev(root, "main"):
        result = "main"
        if cache is not None:
            cache[key] = result
        return result
    raise Refused("there is no main branch with a commit",
                  "make a first commit on main and push it")


def bar_file_list(root: Path, ref: str, files: list[str]) -> list[str]:
    """Judge files, test support files beside them, and every conftest."""
    if not files:
        return []
    tracked = sh(["git", "ls-tree", "-r", "--name-only", ref], root).stdout.splitlines()
    folders = {str(Path(name).parent) for name in files}
    source_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
                       ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php", ".cs"}
    out = set(files)
    for name in tracked:
        if Path(name).name == "conftest.py" or any(
                (folder != "." and name.startswith(folder.rstrip("/") + "/")) or
                (folder == "." and Path(name).suffix.lower() not in source_suffixes)
                for folder in folders):
            out.add(name)
    return sorted(out)


def _hash_paths(read, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.encode() + b"\0" + read(f) + b"\0")
    return h.hexdigest()


def bar_hash_at(root: Path, ref: str, files: list[str], frozen: Optional[list[str]] = None) -> str:
    """Hash the complete judge bar as it is in a commit."""
    paths = frozen if frozen is not None else bar_file_list(root, ref, files)

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


def command_env(folder: Path, protected_paths: Optional[list[str]] = None,
               scrub_secrets: bool = False,
               protected_exceptions: Optional[list[str]] = None) -> dict:  # noqa: UP045
    """The environment for judge, prepare and agent commands.

    Use only the folder's own .venv. A project checkout's environment must not
    choose the interpreter for a fresh worktree's Prepare command. Agent
    sessions can also drop secret-shaped variables.
    """
    env = dict(os.environ)
    if scrub_secrets:
        for name in secret_env_names(env):
            env.pop(name, None)
    env["AI_LOOP_KIT_ROOT"] = str(Path(__file__).resolve().parent.parent)
    frozen_paths = (loop_settings(folder).get("protected paths", [])
                    if protected_paths is None else protected_paths)
    env["LOOP_PROTECTED_PATHS"] = os.pathsep.join(frozen_paths)
    env["LOOP_PROTECTED_EXCEPTIONS"] = os.pathsep.join(protected_exceptions or [])
    project_venv_bin = (project_root(folder) / ".venv" / "bin").resolve()
    path_entries = [entry for entry in (env.get("PATH") or os.defpath).split(os.pathsep)
                    if Path(entry or ".").resolve() != project_venv_bin]
    fresh_venv = folder / ".venv"
    fresh_venv_bin = fresh_venv / "bin"
    env.pop("VIRTUAL_ENV", None)
    if fresh_venv_bin.is_dir():
        fresh_bin = str(fresh_venv_bin.resolve())
        path_entries = [entry for entry in path_entries
                        if Path(entry or ".").resolve() != Path(fresh_bin)]
        path_entries.insert(0, fresh_bin)
        env["VIRTUAL_ENV"] = str(fresh_venv.resolve())
    env["PATH"] = os.pathsep.join(path_entries)
    return env


def secret_env_names(env=None):
    """Return secret-shaped environment variable names without their values."""
    source = os.environ if env is None else env
    return sorted(name for name in source if SECRET_ENV_NAME.search(name)
                  and not re.fullmatch(r"GIT_CONFIG_KEY_\d+", name))


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
        m = re.match(
            r"^\s*[-*]?\s*(Quality|Standards|Protected paths|Waiting limit|Idle limit|Keep limit|"
            r"Keep|Agent|Sandbox domains|Secret paths)\s*:\s*(.*)$", line, re.IGNORECASE)
        if m:
            key, value = m.group(1).lower(), m.group(2).strip().strip("`").strip()
            if key == "quality":
                out.setdefault(key, []).append(value) if value else None
            elif key == "protected paths":
                out[key] = [p.strip().strip("`") for p in value.split(",") if p.strip()]
            elif key == "waiting limit":
                out[key] = value
            elif key == "idle limit":
                out[key] = value
            elif key == "secret paths":
                out[key] = [p.strip().strip("`") for p in value.split(",") if p.strip()]
            elif key == "keep limit":
                out[key] = value
            elif key == "agent":
                out[key] = value.lower()
            else:
                out[key] = value
    return out


def keep_limit_seconds(settings: dict) -> int:
    """Return the configured Keep limit in seconds, defaulting to 15 minutes."""
    value = settings.get("keep limit", str(DEFAULT_KEEP_LIMIT))
    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", value):
        raise Refused(f"Keep limit must be a positive number of minutes, not {value!r}",
                      "set `Keep limit: <minutes>` in the loop section of AGENTS.md")
    seconds = int(float(value) * 60)
    if seconds < 1:
        raise Refused("Keep limit must be at least one second",
                      "set `Keep limit: <minutes>` in the loop section of AGENTS.md")
    return seconds


def prepare(folder: Path, command: Optional[str] = None,
            protected_paths: Optional[list[str]] = None) -> tuple[bool, str]:
    """Run the project's Prepare command in a fresh folder, if it has one.
    It makes a fresh copy runnable: npm ci, uv sync, docker compose build."""
    command = command if command is not None else loop_settings(folder).get("prepare")
    if not command:
        return True, ""
    code, output = run_judge(folder, command, timeout=PREPARE_TIMEOUT,
                             protected_paths=protected_paths)
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


def run_judge(folder: Path, command: str, timeout: int = JUDGE_TIMEOUT,
              protected_paths: Optional[list[str]] = None) -> tuple[int, str]:
    """Run the judge command. The gate calls this; it never trusts a report."""
    proc = None
    try:
        proc = subprocess.Popen(command, shell=True, cwd=folder, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                env=command_env(folder, protected_paths=protected_paths),
                                start_new_session=True)
        try:
            from procs import track_process, _untrack_process
            track_process(proc)
        except ImportError:
            _untrack_process = None
        stdout, stderr = proc.communicate(timeout=timeout)
        if _untrack_process:
            _untrack_process(proc)
        return proc.returncode, _TERMINAL_CODES.sub("", stdout + stderr)
    except subprocess.TimeoutExpired:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            if "_untrack_process" in locals() and _untrack_process:
                _untrack_process(proc)
        return 124, f"the judge ran past {timeout} seconds"


QUALITY_OUTPUTS = ("mutants", ".stryker-tmp", ".coverage", "coverage.json",
                   "coverage.xml", "coverage.lcov", ".coverage.*")


def record_quality_outputs(folder: Path) -> list[str]:
    """List files and directories made under the known Quality output names."""
    found: set[str] = set()
    tracked = set(sh(["git", "ls-files"], folder, check=False).stdout.splitlines())
    for name in QUALITY_OUTPUTS:
        if "*" in name:
            for root in folder.glob(name):
                rel = root.relative_to(folder).as_posix()
                if rel in tracked:
                    continue
                found.add(rel)
                if root.is_dir() and not root.is_symlink():
                    found.update(path.relative_to(folder).as_posix() for path in root.rglob("*"))
            continue
        root = folder / name
        if root.is_symlink() or root.is_file():
            if name not in tracked:
                found.add(name)
        elif root.is_dir():
            found.add(name)
            found.update(path.relative_to(folder).as_posix() for path in root.rglob("*")
                         if path.relative_to(folder).as_posix() not in tracked)
    return sorted(found)


def clean_quality_outputs(folder: Path, recorded: list[str]) -> None:
    """Remove only recorded paths under known Quality output names, one path at a time."""
    allowed = set(QUALITY_OUTPUTS)
    paths = []
    for name in recorded:
        rel = Path(name)
        if not rel.parts or rel.is_absolute() or not any(
                fnmatch.fnmatchcase(rel.parts[0], pattern) for pattern in allowed) or ".." in rel.parts:
            continue
        paths.append(folder / rel)
    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def skipped_tests(output: str) -> bool:
    """Recognise skipped counts in pytest, vitest and jest summaries."""
    patterns = (r"\b[1-9]\d*\s+skipped\b", r"\bskipped\s*:\s*[1-9]\d*\b",
                r"\bOK\s*\(skipped\s*=\s*[1-9]\d*\)", r"^\s*#\s*skipped\s+[1-9]\d*\b")
    return any(re.search(pattern, line, re.IGNORECASE)
               for line in output.splitlines() for pattern in patterns)


def exit_ready(folder: Path, checks: tuple, contract: dict,
               stays: tuple) -> tuple[list[dict], str]:
    """Prove every Exit check is unmet on main and save its baseline."""
    import critic
    import measure

    records, outputs = [], []
    building = [item for item in contract if item not in stays]
    fail_line = re.compile(r"FAIL|ERROR|Error|not ok|_{3,}")
    wrong_reason = re.compile(
        r"^\s*(?:E\s+)?(?:SyntaxError|IndentationError|ModuleNotFoundError|"
        r"ImportError|FileNotFoundError):|^ERROR collecting(?:\s|$)", re.MULTILINE)
    for source in checks:
        check = dict(source)
        if check["type"] == "tests":
            code, output = run_judge(folder, check["command"])
            if check.get("legacy_kind") == "scaffold":
                check["main_output"] = output
            elif code == 0:
                raise Refused("the judge already passes on main, so there is nothing to build",
                              "make the judge test what the Contract items ask for")
            if (check.get("legacy_kind") != "scaffold" and
                    ((code == 127 and "command not found" in output) or
                     wrong_reason.search(output))):
                raise Refused("the judge fails on main for the wrong reason "
                              f"(a broken test, not a missing feature):\n{output.strip()[-1500:]}",
                              "fix the judge so it fails on an assertion")
            if check.get("legacy_kind") != "scaffold":
                fail_lines = "\n".join(
                    line for line in output.splitlines() if fail_line.search(line))
                named = [item for item in building if re.search(
                    rf"(?<![A-Za-z0-9]){item}(?![0-9])", fail_lines)]
                if not named:
                    raise Refused("the judge fails on main, but its output names no spec ID "
                                  f"({', '.join(building)}):\n{output.strip()[-1500:]}",
                                  "put each Contract ID in a failing test name")
                required = building
                missing = [item for item in required if item not in named]
                if missing:
                    raise Refused(f"no failing judge test names {', '.join(missing)}",
                                  "give every Contract item at least one failing test")
                failing_stays = [item for item in stays if re.search(
                    rf"(?<![A-Za-z0-9]){item}(?![0-9])", fail_lines)]
                if failing_stays:
                    raise Refused(f"{', '.join(failing_stays)} is marked (stays) but fails on main",
                                  "a (stays) item already holds today; test only what it says")
                check["main_output"] = output
        elif check["type"] == "measure":
            output, baseline = measure.ready(folder, check["command"], check["target"])
            check.update(baseline)
        else:
            output, baseline = critic.ready(folder, check["capture"], check["reference"],
                                            list(check["criteria"]))
            check.update(baseline)
        records.append(check)
        outputs.append(output.strip())
    return records, "\n\n".join(outputs)


def exit_attempt(folder: Path, checks: list[dict],
                 protected_paths: list[str] | None = None) -> tuple[int, str]:
    """Run every frozen Exit check after an attempt."""
    import critic
    import measure

    results = []
    failed = False
    for check in checks:
        if check["type"] == "tests":
            code, output = run_judge(folder, check["command"],
                                     protected_paths=protected_paths)
            if skipped_tests(output):
                code = 1
                output = "the judge reported skipped tests:\n" + output.strip()[-1500:]
        elif check["type"] == "measure":
            code, output = measure.judge_attempt(folder, check,
                                                  protected_paths=protected_paths)
        else:
            code, output = critic.judge_attempt(folder, check,
                                                 protected_paths=protected_paths)
        results.append(f"{check['type'].title()} exit check (exit {code}):\n{output.strip()}")
        if code:
            failed = True
    return (1 if failed else 0), "\n\n".join(results)


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
    encoded = json.dumps(record, sort_keys=True).replace("-->", "\\u002d\\u002d>")
    return f"<!-- {RECORD_TAG} {encoded} -->\n**Gate:** {note}"


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
