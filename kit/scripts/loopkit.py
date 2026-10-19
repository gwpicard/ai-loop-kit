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
import time
from pathlib import Path
from typing import Optional

from errors import Refused
from spec import Spec as Spec
from spec import _section
from spec import parse_research_section as parse_research_section
from spec import parse_spec as parse_spec

from extras import critics, require_extras

STATES = ("shaping", "ready", "building", "approval", "done", "dropped")
STATE_PREFIX = "state:"
NEEDS_YOU = "needs-you"
RECORD_TAG = "loop-gate"
REASON_TYPES = ("spec-unclear", "bar-wrong", "stopped", "environment", "builder-failed",
                "person-rejected", "conflict", "judge-gap")
CAUSES = ("bar-wrong", "builder-failed", "conflict", "dirty-worktree", "import-error",
          "idle", "judge-failed", "judge-gap", "keep-flaky", "needs-answer", "other",
          "person-rejected", "person-request", "prepare-failed", "pull-request-failed",
          "quality-failed", "spec-unclear", "stale-after-main", "stopped", "usage-limit")
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
            elif key in {"protected paths", "secret paths"}:
                out[key] = [p.strip().strip("`") for p in value.split(",") if p.strip()]
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


def run_keep(folder: Path, command: str, timeout: int,
             protected_paths: list[str] | None = None) -> tuple[int, str]:
    """Run Keep with its limit and report the elapsed seconds."""
    started = time.monotonic()
    code, output = run_judge(folder, command, timeout=timeout,
                             protected_paths=protected_paths)
    elapsed = time.monotonic() - started
    return code, f"{output.rstrip()}\nKeep took: {elapsed:.3f} seconds".lstrip()


def run_judge(folder: Path, command: str, timeout: int = JUDGE_TIMEOUT,
              protected_paths: Optional[list[str]] = None) -> tuple[int, str]:
    """Run the judge command. The gate calls this; it never trusts a report."""
    require_extras({"command": command})
    proc = None
    try:
        proc = subprocess.Popen(command, shell=True, cwd=folder, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                env=command_env(folder, protected_paths=protected_paths),
                                start_new_session=True)
        try:
            from procs import _untrack_process, track_process
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


_WRONG_TEST_REASON = re.compile(
    r"^\s*(?:E\s+)?(?:SyntaxError|IndentationError|ModuleNotFoundError|"
    r"ImportError|FileNotFoundError):|^ERROR collecting(?:\s|$)", re.MULTILINE)


def judge_has_runner_error(output: str, code: int) -> bool:
    """Recognise a missing test command or a broken test module."""
    return ((code == 127 and "command not found" in output)
            or bool(_WRONG_TEST_REASON.search(output)))


def judge_assertion_failed(output: str, item: str) -> bool:
    """Apply the ready gate's failure-line and named-item rule."""
    fail_line = re.compile(r"FAIL|ERROR|Error|not ok|_{3,}")
    named = re.compile(rf"(?<![A-Za-z0-9]){re.escape(item)}(?![0-9])")
    return any(fail_line.search(line) and named.search(line)
               for line in output.splitlines())


def exit_ready(folder: Path, checks: tuple, contract: dict,
               stays: tuple) -> tuple[list[dict], str]:
    """Prove every Exit check is unmet on main and save its baseline."""
    import measure

    records, outputs = [], []
    building = [item for item in contract if item not in stays]
    for source in checks:
        check = dict(source)
        if check["type"] == "tests":
            code, output = run_judge(folder, check["command"])
            if check.get("legacy_kind") == "scaffold":
                check["main_output"] = output
            elif code == 0:
                raise Refused("the judge already passes on main, so there is nothing to build",
                              "make the judge test what the Contract items ask for")
            if check.get("legacy_kind") != "scaffold" and judge_has_runner_error(output, code):
                raise Refused("the judge fails on main for the wrong reason "
                              f"(a broken test, not a missing feature):\n{output.strip()[-1500:]}",
                              "fix the judge so it fails on an assertion")
            if check.get("legacy_kind") != "scaffold":
                named = [item for item in building
                         if judge_assertion_failed(output, item)]
                if not named:
                    raise Refused("the judge fails on main, but its output names no spec ID "
                                  f"({', '.join(building)}):\n{output.strip()[-1500:]}",
                                  "put each Contract ID in a failing test name")
                required = building
                missing = [item for item in required if item not in named]
                if missing:
                    raise Refused(f"no failing judge test names {', '.join(missing)}",
                                  "give every Contract item at least one failing test")
                failing_stays = [item for item in stays
                                 if judge_assertion_failed(output, item)]
                if failing_stays:
                    raise Refused(f"{', '.join(failing_stays)} is marked (stays) but fails on main",
                                  "a (stays) item already holds today; test only what it says")
                check["main_output"] = output
        elif check["type"] == "measure":
            output, baseline = measure.ready(folder, check["command"], check["target"])
            check.update(baseline)
        else:
            output, baseline = critics().ready(folder, check["capture"], check["reference"],
                                            list(check["criteria"]))
            check.update(baseline)
        records.append(check)
        outputs.append(output.strip())
    return records, "\n\n".join(outputs)


def exit_attempt(folder: Path, checks: list[dict],
                 protected_paths: list[str] | None = None) -> tuple[int, str]:
    """Run every frozen Exit check after an attempt."""
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
            code, output = critics().judge_attempt(folder, check,
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

    def issues_with_label(self, label: str = "", closed_too: bool = False) -> list[dict]:
        state = "all" if closed_too else "open"
        labels = ["--label", label] if label else []
        data = json.loads(self._gh("issue", "list", "--state", state, *labels,
                                   "--limit", "200" if label else "1000000",
                                   "--json", "number,title,labels"))
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
        self._gh("auth", "status", "--active")
        return True

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

    def edit_pr(self, url: str, title: str, body: str) -> None:
        self._gh("pr", "edit", url, "--title", title, "--body-file", "-", stdin=body)

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
