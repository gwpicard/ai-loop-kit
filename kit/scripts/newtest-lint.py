#!/usr/bin/env python3
# contract: agent
"""newtest-lint.py: refuse the test smells a script can find reliably.

Commands:
  newtest-lint.py --base <ref>        judge what the working tree adds to <ref>
  newtest-lint.py --file <path> [--file <path> ...]
                                      judge whole files (with full path context)

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
            encoding="utf-8",
            errors="surrogateescape",
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


def _read(path: Path) -> tuple[str | None, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except UnicodeDecodeError:
        return None, "content is not valid UTF-8; no content checks ran"
    except OSError as error:
        return None, f"content cannot be read ({type(error).__name__}); no content checks ran"


def _detect_here() -> frozenset[str]:
    """The own modules of the project that holds the current folder, or of the folder itself."""
    try:
        root = _root()
    except Failure:
        root = Path.cwd()
    return nl.detect_own_modules(root)


def _lines(diff: str) -> nl.FileChange:
    """One path is selected by Git's argv; hunk headers cannot rename that path."""
    changed = nl.FileChange()
    for line in diff.splitlines():
        match = nl.HUNK.match(line)
        if match:
            start = int(match.group(1))
            count = 1 if match.group(2) is None else int(match.group(2))
            if count == 0:
                changed.touched.update({start, start + 1})
            else:
                changed.added.update(range(start, start + count))
    return changed


def judge_base(
    base: str, extra_modules: frozenset[str]
) -> tuple[list[nl.Finding], list[str], frozenset[str], list[nl.Coverage]]:
    root = _root()
    own = nl.detect_own_modules(root) | extra_modules
    status = _git(root, "diff", "--name-status", "-z", "--no-renames", base, "--")
    parts = status.split("\0")
    if parts[-1] == "":
        parts.pop()
    if len(parts) % 2:
        raise Failure(
            "Git returned an incomplete path inventory",
            next_command="check the Git project, then repeat the lint",
            code=ExitCode.ENVIRONMENT,
        )
    changes = list(zip(parts[::2], parts[1::2], strict=True))
    untracked = [
        p for p in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if p
    ]
    changes.extend(("?", p) for p in untracked)
    findings = nl.lint_changes(changes)
    checked: list[str] = []
    coverage: list[nl.Coverage] = []
    for state, path in sorted(changes, key=lambda entry: entry[1]):
        if state.startswith("D"):
            assessment = nl.assess_text(path, "", status=state)
        else:
            text, error = _read(root / path)
            if text is None:
                assessment = nl.unchecked(path, state, error, input_error=True)
            else:
                added: set[int] | None = None
                touched: set[int] = set()
                if state != "?":
                    diff = _git(
                        root,
                        "diff",
                        "--unified=0",
                        "--no-color",
                        "--no-ext-diff",
                        "--no-renames",
                        base,
                        "--",
                        path,
                    )
                    lines = _lines(diff)
                    added, touched = lines.added, lines.touched
                assessment = nl.assess_text(
                    path, text, status=state, added=added, touched=touched, own_modules=own
                )
        findings.extend(assessment.findings)
        coverage.append(assessment.coverage)
        if assessment.coverage["outcome"] in {"checked", "partial"}:
            checked.append(path)
    return findings, checked, own, coverage


def judge_files(
    files: list[str], extra_modules: frozenset[str]
) -> tuple[list[nl.Finding], list[str], frozenset[str], list[nl.Coverage]]:
    own = _detect_here() | extra_modules
    findings: list[nl.Finding] = []
    checked: list[str] = []
    coverage: list[nl.Coverage] = []
    for name in files:
        text, error = _read(Path(name))
        assessment = (
            nl.unchecked(name, "file", error, input_error=True)
            if text is None
            else nl.assess_text(name, text, status="file", own_modules=own)
        )
        findings.extend(assessment.findings)
        coverage.append(assessment.coverage)
        if assessment.coverage["outcome"] in {"checked", "partial"}:
            checked.append(name)
    return findings, checked, own, coverage


def handle(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.base) == bool(args.file):
        raise Failure(
            "give either --base <ref> or --file <path>, not both and not neither",
            next_command="newtest-lint.py --help",
            code=ExitCode.USAGE,
        )
    extra = frozenset(args.own_module)
    if args.base:
        findings, checked, own, coverage = judge_base(args.base, extra)
        again = f"newtest-lint.py --base {args.base}"
    else:
        findings, checked, own, coverage = judge_files(args.file, extra)
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
        "coverage": coverage,
    }
    unreadable = [entry for entry in coverage if entry["input_error"]]
    if unreadable:
        raise Failure(
            f"{len(unreadable)} input(s) could not be checked: {unreadable[0]['path']}",
            next_command=f"provide readable UTF-8 content for every input, then run {again}",
            code=ExitCode.ENVIRONMENT,
            data=data,
        )
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
