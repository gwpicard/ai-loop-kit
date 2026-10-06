#!/usr/bin/env python3
# contract: agent
"""Refuse a change that carries a secret.

Two ways to call it, both read-only:

    secret-scan.py --staged            the changes staged in this project
    secret-scan.py --range "A..B"      every commit in a range, as a push sends them

Without an option it scans what is staged. It reads only the lines a change
adds. It finds known key shapes and long strings with high entropy. It also
runs `gitleaks` when that tool is installed, and says so when it is not.

A finding names the file, the line and the kind. It never holds the value.
There is no allow-list to edit. A real hit is removed from the change.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli
from loop.paths import PathError, find_project_root

# Known shapes, most specific first. A line gets one finding.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("stripe-key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
)

CANDIDATE = re.compile(r"[A-Za-z0-9+_=-]{32,}")
ENTROPY_LIMIT = 4.2
RANGE_WORDS = {"--not", "--remotes", "--branches", "--tags", "--all"}


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line": self.line, "kind": self.kind}


def entropy(text: str) -> float:
    """Shannon entropy in bits per character."""
    counts = Counter(text)
    total = len(text)
    return -sum(n / total * math.log2(n / total) for n in counts.values())


def kinds_in_line(line: str) -> list[str]:
    for kind, pattern in PATTERNS:
        if pattern.search(line):
            return [kind]
    for token in CANDIDATE.findall(line):
        has_letter = any(c.isalpha() for c in token)
        has_digit = any(c.isdigit() for c in token)
        if has_letter and has_digit and entropy(token) >= ENTROPY_LIMIT:
            return ["high-entropy-string"]
    return []


def scan_diff(diff: str) -> list[Finding]:
    """Scan the added lines of a unified diff."""
    findings: list[Finding] = []
    file = ""
    line_no = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:]
            file = "" if name == "/dev/null" else name.removeprefix("b/")
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            line_no = int(match.group(1)) if match else 0
        elif raw.startswith("+") and file:
            for kind in kinds_in_line(raw[1:]):
                finding = Finding(file, line_no, kind)
                if finding not in findings:
                    findings.append(finding)
            line_no += 1
    return findings


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if done.returncode != 0:
        raise cli.Failure(
            f"git {args[0]} failed: {done.stderr.strip().splitlines()[-1:] or ['no message']}",
            next_command="git status",
        )
    return done.stdout


def range_words(spec: str) -> list[str]:
    words = shlex.split(spec)
    for word in words:
        if word.startswith("-") and word not in RANGE_WORDS:
            raise cli.Failure(
                f"{word!r} is not allowed in a range",
                next_command="secret-scan.py --range 'A..B'",
                code=cli.ExitCode.USAGE,
            )
    if not words:
        raise cli.Failure(
            "the range is empty", next_command="secret-scan.py --help", code=cli.ExitCode.USAGE
        )
    return words


DIFF_FLAGS = ("--no-color", "--no-ext-diff", "--unified=0", "--no-renames", "--text")


def diff_staged(root: Path) -> str:
    return git(root, "diff", "--cached", *DIFF_FLAGS)


def diff_range(root: Path, spec: str) -> str:
    # Every commit, so a secret added and then removed in the range is still found.
    return git(root, "log", "-p", "--format=", *DIFF_FLAGS, *range_words(spec), "--")


def run_gitleaks(root: Path, spec: str | None) -> tuple[str, list[Finding]]:
    """Run gitleaks when it is installed. Returns its state and its findings."""
    exe = shutil.which("gitleaks")
    if exe is None:
        return "not installed", []
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "report.json"
        common = [
            "--no-banner",
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            str(report),
        ]
        if spec is None:
            command = [exe, "protect", "--staged", *common]
        else:
            command = [exe, "detect", *common, f"--log-opts={' '.join(range_words(spec))}"]
        done = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
        if done.returncode == 0:
            return "ran", []
        try:
            rows = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "failed", []
    findings = [
        Finding(str(r.get("File", "?")), int(r.get("StartLine", 0)), f"gitleaks:{r.get('RuleID')}")
        for r in rows
    ]
    return "ran", findings


def setup(parser: argparse.ArgumentParser) -> None:
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--staged", action="store_true", help="scan the staged changes (default)")
    where.add_argument(
        "--range",
        metavar="REVISIONS",
        help="scan every commit in a range, for example 'origin/main..HEAD'",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = find_project_root(Path.cwd())
    except PathError as exc:
        raise cli.Failure(
            str(exc),
            next_command="cd <the project> && secret-scan.py --staged",
            code=cli.ExitCode.ENVIRONMENT,
        ) from exc
    spec: str | None = args.range
    diff = diff_staged(root) if spec is None else diff_range(root, spec)
    findings = scan_diff(diff)
    state, extra = run_gitleaks(root, spec)
    for finding in extra:
        if finding not in findings:
            findings.append(finding)
    if state == "not installed":
        sys.stderr.write("note: gitleaks is not installed, so only the built-in scan ran.\n")
    rows = [f.as_dict() for f in findings]
    if findings:
        places = ", ".join(f"{f.file}:{f.line} ({f.kind})" for f in findings)
        raise cli.Failure(
            f"possible secret in {places}",
            next_command="remove the secret from the change, then run secret-scan.py again",
            code=cli.ExitCode.REFUSED,
            data={"findings": rows, "gitleaks": state},
        )
    return {"findings": rows, "gitleaks": state, "scanned": "staged" if spec is None else spec}


def main(argv: list[str]) -> int:
    return cli.run(
        "secret-scan.py",
        "Refuse a staged change or a commit range that carries a secret.",
        setup,
        handle,
        argv,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
