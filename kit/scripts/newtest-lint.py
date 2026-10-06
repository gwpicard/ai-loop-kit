#!/usr/bin/env python3
# contract: agent
"""newtest-lint.py: refuse the test smells a script can find reliably.

Commands:
  newtest-lint.py --base <ref>        judge what the working tree adds to <ref>
  newtest-lint.py --file <path> [--file <path> ...]
                                      judge whole files (by their names only)

The lint (loop/newtest_lint.py) reads only the lines a change adds, so an old
smell is left alone. It finds: no assertion, a skip marker, `assert True`, a
duplicate assertion, an if or loop in a test, sleep, a debug print, a mock of the
project's own module, a call-count assertion, code that checks it is under test,
a snapshot rewritten with the code, a suppression comment, a swallowed error and
a debug leftover. Assertion roulette and magic numbers are only reported. The
attempt gate runs this on every attempt. The script changes nothing.

Python modules of the project are found as every folder with __init__.py at
any depth, the modules in the roots that pyproject.toml or MYPYPATH name, and
the top level and src/. Add more with --own-module. When a Python file is judged
and no module is found, the output says so in "notes". A file that is a test is
told by its path, as test-guard.sh tells it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli
from loop import newtest_lint as nl
from loop.cli import ExitCode, Failure


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base", metavar="REF", help="judge the working tree against this commit")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="PATH",
        help="judge this file whole; repeat the option for each more file",
    )
    parser.add_argument(
        "--own-module",
        action="append",
        default=[],
        metavar="NAME",
        help="a Python module of this project, which a test must not mock",
    )


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise Failure(
            f"git could not be started ({error})",
            next_command="install git, then run newtest-lint.py again",
            code=ExitCode.ENVIRONMENT,
        ) from error
    if done.returncode != 0:
        first = next((ln for ln in done.stderr.splitlines() if ln.strip()), "no message")
        raise Failure(
            f"git {args[0]} failed ({first.strip()})",
            next_command="check the --base commit with: git rev-parse --verify <ref>",
            code=ExitCode.ENVIRONMENT,
        )
    return done.stdout


def _root() -> Path:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
    except OSError:
        done = None
    if done is None or done.returncode != 0:
        raise Failure(
            "this folder is not inside a Git project",
            next_command="cd <the project>, then run newtest-lint.py --base <ref>",
            code=ExitCode.ENVIRONMENT,
        )
    return Path(done.stdout.strip())


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _detect_here() -> frozenset[str]:
    """The own modules of the project that holds the current folder, or of the folder itself."""
    try:
        root = _root()
    except Failure:
        root = Path.cwd()
    return nl.detect_own_modules(root)


def judge_base(
    base: str, extra_modules: frozenset[str]
) -> tuple[list[nl.Finding], list[str], frozenset[str]]:
    root = _root()
    own = nl.detect_own_modules(root) | extra_modules
    diff = _git(
        root, "diff", "--unified=0", "--no-color", "--no-ext-diff", "--no-renames", base, "--"
    )
    status = _git(root, "diff", "--name-status", "--no-renames", base, "--")
    untracked = [
        p for p in _git(root, "ls-files", "--others", "--exclude-standard").splitlines() if p
    ]
    changed = nl.parse_diff(diff)
    changes: list[tuple[str, str]] = []
    for line in status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append((parts[0], parts[-1]))
    changes.extend(("A", p) for p in untracked)
    findings = nl.lint_changes(changes)
    checked: list[str] = []
    wanted: dict[str, tuple[set[int] | None, set[int]]] = {
        path: (change.added, change.touched) for path, change in changed.items()
    }
    for path in untracked:
        wanted[path] = (None, set())
    for path, (added, touched) in sorted(wanted.items()):
        if nl.language_of(path) is None:
            continue
        text = _read(root / path)
        if text is None:
            continue
        checked.append(path)
        findings.extend(nl.lint_text(path, text, added=added, touched=touched, own_modules=own))
    return findings, checked, own


def judge_files(
    files: list[str], extra_modules: frozenset[str]
) -> tuple[list[nl.Finding], list[str], frozenset[str]]:
    own = _detect_here() | extra_modules
    findings: list[nl.Finding] = []
    checked: list[str] = []
    for name in files:
        path = Path(name)
        text = _read(path)
        if text is None:
            raise Failure(
                f"cannot read {name}",
                next_command="newtest-lint.py --file <path to a readable file>",
                code=ExitCode.ENVIRONMENT,
            )
        if nl.language_of(path.name) is None:
            continue
        checked.append(name)
        findings.extend(
            nl.lint_text(
                name,
                text,
                own_modules=own,
                is_test=nl.is_test_path(path.name),
            )
        )
    return findings, checked, own


def handle(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.base) == bool(args.file):
        raise Failure(
            "give either --base <ref> or --file <path>, not both and not neither",
            next_command="newtest-lint.py --help",
            code=ExitCode.USAGE,
        )
    extra = frozenset(args.own_module)
    if args.base:
        findings, checked, own = judge_base(args.base, extra)
        again = f"newtest-lint.py --base {args.base}"
    else:
        findings, checked, own = judge_files(args.file, extra)
        again = "newtest-lint.py --file " + " --file ".join(args.file)
    notes: list[str] = []
    if not own and any(nl.language_of(name) == "py" for name in checked):
        notes.append(
            "no Python module of this project was found, so own_module_mock cannot judge "
            "Python mocks; add one with --own-module NAME, or put an __init__.py in each package"
        )
        sys.stderr.write(f"note: {notes[0]}\n")
    refused = nl.refusals(findings)
    noted = nl.reports(findings)
    data: dict[str, Any] = {
        "refusals": refused,
        "reports": noted,
        "checked": checked,
        "mode": "base" if args.base else "file",
        "own_modules": sorted(own),
        "notes": notes,
    }
    if refused:
        first = refused[0]
        places = ", ".join(f"{f['file']}:{f['line']} ({f['rule']})" for f in refused[:5])
        more = f", and {len(refused) - 5} more" if len(refused) > 5 else ""
        raise Failure(
            f"{len(refused)} test smell(s) refused: {places}{more}",
            next_command=f"{first['next']}, then run {again}",
            data=data,
        )
    return data


def main(argv: list[str]) -> int:
    return cli.run(
        "newtest-lint.py",
        __doc__ or "",
        setup,
        handle,
        argv,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
