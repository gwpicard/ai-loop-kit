"""The frozen bar: what a piece is measured against, and every change a build made to it.

The bar is the judge and everything it rests on: the judge files, the project's
existing tests, fixtures, snapshots, the settings of the test, lint, type-check
and coverage tools, and the files that guard the project (workflows, hooks and
the Claude Code settings). A builder working alone can turn a red check green
without touching the code under test, so the gate holds the bar in two layers.
The first layer is the deny rules in each attempt's settings: `paths` lists
every file they name. The second is `changes`, the gate's byte-for-byte check.

`changes` compares the piece branch at its head with the commit it was cut from
(its base), and lists each change in seven kinds:

- `acceptance-check`: a judge file that is not byte for byte what the first
  commit held. It is the only kind that reads the judge commit, not the base.
- `existing-test`: a test, fixture or helper that existed at the base and was
  edited, deleted or moved away. A new test file is not listed.
- `skip-or-focus`: a skip, focus or expected-failure marker added to a test.
- `suppression`: a lint or type suppression added to any file.
- `tool-settings`: a test, lint, type-check or coverage tool's settings that
  gained or lost a line. Taking a setting out loosens a tool as surely as adding
  one. In `pyproject.toml`, `setup.cfg` and `tox.ini` only the sections of those
  tools count, so a builder may add a dependency.
- `snapshot`: a snapshot that existed at the base and changed.
- `guarded-file`: a change to a workflow, a hook or the Claude Code settings.

The old bar guard let a change count as named, and the person then reviewed it.
That escape is gone. Any change to the bar is a failed attempt. A builder that
believes the bar is wrong says so in its hand-off, and the piece goes back to
shaping.

Every git step that fails raises `BarError`. A check that did not run is never a
pass, so the gate turns the error into a refusal.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from loop import newtest_lint

KINDS = (
    "acceptance-check",
    "existing-test",
    "skip-or-focus",
    "suppression",
    "tool-settings",
    "snapshot",
    "guarded-file",
)

TEST_DIRS = frozenset(
    {"test", "tests", "__tests__", "spec", "specs", "e2e", "fixtures", "testdata", "cypress"}
)
CONFTEST = "conftest.py"

SKIP = re.compile(
    r"\.skip\(|\.only\(|\.todo\(|\.fixme\("
    r"|(^|[^A-Za-z0-9_.$])(xit|xdescribe|xtest|fit|fdescribe)\("
    r"|@pytest\.mark\.(skip|xfail)|pytest\.skip\(|pytest\.xfail\("
    r"|(^|[^A-Za-z0-9_])t\.Skip|@?unittest\.skip|expectedFailure"
)
SUPPRESS = re.compile(
    r"eslint-disable|@ts-ignore|@ts-expect-error|#[ \t]*type:[ \t]*ignore|#[ \t]*noqa"
    r"|#[ \t]*pylint:[ \t]*disable|//[ \t]*nolint"
)

# Settings files that count whole: any change at all.
WHOLE_SETTINGS = re.compile(
    r"^(jest\.config\..+|vitest\.config\..+|playwright\.config\..+|eslint\.config\..+"
    r"|\.eslintrc.*|\.mocharc.*|\.coveragerc|\.flake8|\.pylintrc|pytest\.ini|ruff\.toml"
    r"|\.ruff\.toml|mypy\.ini|tsconfig.*\.json)$"
)
# Settings files that hold other things too: only the sections of the tools count.
SECTIONED_SETTINGS = frozenset({"pyproject.toml", "setup.cfg", "tox.ini"})
TOOL_SECTION = re.compile(
    r"^(tool[.:])?(pytest|ruff|mypy|coverage|pyright|flake8|pylint|isort|black|bandit|"
    r"testenv|tox|unittest|nosetests)(?![A-Za-z0-9_])"
)
SECTION_HEAD = re.compile(r"^\s*\[+\s*([^\]]+?)\s*\]+\s*(?:[#;].*)?$")

GUARDED_PREFIXES = (
    ".github/workflows/",
    ".agents/hooks/",
    ".agents/tools/",
    ".agents/loop/",
    ".githooks/",
    ".husky/",
)
GUARDED_FILES = frozenset({".claude/settings.json", ".claude/settings.local.json"})


class BarError(Exception):
    """A git step failed, so the gate cannot tell what the bar holds. Carries the next command."""

    def __init__(self, message: str, *, next_command: str = "") -> None:
        super().__init__(message)
        self.next_command = next_command or (
            "check the project's git repository, then run the same move again"
        )


@dataclass(frozen=True)
class Change:
    kind: str
    path: str
    detail: str

    def text(self) -> str:
        return f"{self.kind}: {self.path} ({self.detail})"

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "path": self.path, "detail": self.detail}


# --- what a path is ---------------------------------------------------------------------


def is_test(path: str) -> bool:
    """A test, a fixture or a test helper, told by its path."""
    if newtest_lint.is_test_path(path):
        return True
    parts = PurePosixPath(path).parts
    return any(part.lower() in TEST_DIRS for part in parts[:-1]) or parts[-1] == CONFTEST


def is_snapshot(path: str) -> bool:
    return newtest_lint.is_snapshot_path(path)


def is_settings(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in SECTIONED_SETTINGS or bool(WHOLE_SETTINGS.match(name))


def is_guarded(path: str) -> bool:
    return path in GUARDED_FILES or path.startswith(GUARDED_PREFIXES)


# --- git --------------------------------------------------------------------------------


def _git(root: Any, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise BarError(f"git could not be started ({error.strerror})") from error
    if done.returncode != 0:
        first = next(
            (ln for ln in done.stderr.decode("utf-8", "replace").splitlines() if ln.strip()),
            "no message",
        )
        raise BarError(f"git {args[0]} failed ({first.strip()[:120]}), so the bar cannot be read")
    return done.stdout.decode("utf-8", "replace")


def _entry(root: Any, ref: str, path: str) -> tuple[str, str] | None:
    """The mode and the object of `path` at `ref`, or None when the commit holds no such file."""
    listing = _git(root, "ls-tree", ref, "--", path).strip()
    if not listing:
        return None
    head, _, _ = listing.partition("\t")
    mode, _kind, sha = head.split()
    return mode, sha


def _text(root: Any, ref: str, path: str) -> str | None:
    if _entry(root, ref, path) is None:
        return None
    return _git(root, "show", f"{ref}:{path}")


def _status(root: Any, base: str, head: str) -> list[tuple[str, str]]:
    """Each path that differs between `base` and `head`, as (status letter, path)."""
    raw = _git(root, "diff", "--no-renames", "--name-status", "-z", base, head, "--")
    parts = raw.split("\0")
    found: list[tuple[str, str]] = []
    for index in range(0, len(parts) - 1, 2):
        if parts[index]:
            found.append((parts[index][:1], parts[index + 1]))
    return found


def _count(pattern: re.Pattern[str], text: str | None) -> int:
    if not text:
        return 0
    return sum(1 for line in text.splitlines() if pattern.search(line))


# --- the settings of a tool ---------------------------------------------------------------


def _tool_lines(text: str | None) -> list[str]:
    """The lines inside the sections of a tool, with the section's name in front."""
    found: list[str] = []
    section: str | None = None
    for raw in (text or "").splitlines():
        head = SECTION_HEAD.match(raw)
        if head:
            section = head.group(1) if TOOL_SECTION.match(head.group(1).lower()) else None
            if section is not None:
                found.append(f"[{section}]")
            continue
        line = raw.strip()
        if section is not None and line and not line.startswith(("#", ";")):
            found.append(f"{section}: {line}")
    return found


def _settings_changed(root: Any, base: str, head: str, path: str, status: str) -> bool:
    before = _text(root, base, path) if status != "A" else None
    after = _text(root, head, path) if status != "D" else None
    if PurePosixPath(path).name in SECTIONED_SETTINGS:
        return _tool_lines(before) != _tool_lines(after)
    return before != after


# --- the listing -----------------------------------------------------------------------


def paths(root: Any, base: str, judge_files: Sequence[str]) -> list[str]:
    """Every path an attempt may not write: the first layer's list.

    It holds the judge files, and each file the base holds that is a test, a fixture, a
    snapshot, a tool's settings file or a guarded file. A new file is not on it, so a
    builder may add tests. `pyproject.toml`, `setup.cfg` and `tox.ini` are not on it,
    since a builder may add a dependency there; the gate's check reads their tool sections.
    """
    found = set(judge_files)
    for path in _git(root, "ls-tree", "-r", "--name-only", "-z", base).split("\0"):
        if not path:
            continue
        sectioned = PurePosixPath(path).name in SECTIONED_SETTINGS
        if is_test(path) or is_snapshot(path) or is_guarded(path) or (
            is_settings(path) and not sectioned
        ):
            found.add(path)
    return sorted(found)


def changes(
    root: Any,
    base: str,
    head: str,
    *,
    judge_commit: str | None,
    judge_files: Sequence[str],
) -> list[Change]:
    """Every change `head` made to the bar, in the seven kinds. An empty list is a clean bar.

    `judge_commit` and `judge_files` name the first commit of the piece branch. A scaffold
    piece has none, and then no `acceptance-check` is listed.
    """
    found: list[Change] = []
    frozen = set(judge_files)
    if judge_commit is not None:
        for path in judge_files:
            if _entry(root, head, path) != _entry(root, judge_commit, path):
                found.append(
                    Change("acceptance-check", path, "no longer byte for byte as ready froze it")
                )
    for status, path in _status(root, base, head):
        if path in frozen:
            continue
        after = _text(root, head, path) if status != "D" else None
        before = _text(root, base, path) if status != "A" else None
        if is_test(path):
            if status != "A":
                how = "deleted or moved away" if status == "D" else "edited"
                found.append(Change("existing-test", path, how))
            if _count(SKIP, after) > _count(SKIP, before):
                found.append(Change("skip-or-focus", path, "a skip or focus marker was added"))
        if _count(SUPPRESS, after) > _count(SUPPRESS, before):
            found.append(Change("suppression", path, "a lint or type suppression was added"))
        if is_settings(path) and _settings_changed(root, base, head, path, status):
            found.append(Change("tool-settings", path, "a tool's settings changed"))
        if is_snapshot(path) and status != "A":
            found.append(Change("snapshot", path, "a snapshot that existed was changed"))
        if is_guarded(path):
            found.append(Change("guarded-file", path, "a guarded file changed"))
    return found
