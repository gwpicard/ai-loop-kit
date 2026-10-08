"""Closing words: the one way a pull request closes a piece.

GitHub closes an issue when a closing word stands before its number, even in a sentence that
says it does not. So only `Closes #<n>` lines in the pull request's body may close a piece, one
line for each piece, and no closing word stands before any other number anywhere: not in the
title, not in a commit message, not in a changelog entry, not in a note.

`scan` reads those four places and returns every fault. `neutralise` makes text from an agent,
a reviewer or an issue safe to put into a body: it breaks each reference, so no closing word
can reach a number. The gate scans the result anyway, so a missed spelling is still caught.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

WORDS = r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)"
REFERENCE = (
    r"(?:(?:[\w.-]+/[\w.-]+)?\#\d+|GH-\d+"
    r"|https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+)"
)
CLOSER = re.compile(
    rf"(?<![A-Za-z0-9_]){WORDS}(?![A-Za-z0-9_])[\s:]*[(\[*_`]*\s*{REFERENCE}", re.IGNORECASE
)
OWN_LINE = re.compile(r"^Closes #(\d+)$")
ANY_REFERENCE = re.compile(
    r"(?:[\w.-]+/[\w.-]+)?#(\d+)|GH-(\d+)|https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/(\d+)"
)


@dataclass(frozen=True)
class Fault:
    where: str  # title, body, commit <n> or changelog entry <n>
    message: str


def _closers(text: str) -> list[str]:
    return [found.group(0).strip() for found in CLOSER.finditer(text)]


def _loose(where: str, text: str) -> list[Fault]:
    return [
        Fault(where, f"holds the closing word in {shown!r}, which GitHub reads as a close")
        for shown in _closers(text)
    ]


def scan(
    *,
    title: str,
    body: str,
    commits: Sequence[str],
    changelog: Sequence[str],
    pieces: Collection[int],
) -> list[Fault]:
    """Every fault in the title, body, commit messages and changelog entries.

    `pieces` are the issue numbers the pull request closes: each needs one `Closes #<n>` line in
    the body, and none may be closed anywhere else.
    """
    faults = _loose("title", title)
    own: list[int] = []
    rest: list[str] = []
    for line in body.splitlines():
        found = OWN_LINE.match(line.strip())
        if found:
            own.append(int(found.group(1)))
        else:
            rest.append(line)
    faults += _loose("body", "\n".join(rest))
    wanted = sorted(set(pieces))
    for number in sorted(set(own)):
        if own.count(number) > 1:
            faults.append(Fault("body", f"closes {number} twice: one Closes line for each piece"))
        if number not in wanted:
            faults.append(
                Fault("body", f"closes {number}, which is not a piece of this pull request")
            )
    missing = [n for n in wanted if n not in own]
    if missing:
        faults.append(
            Fault("body", f"has no Closes line for {', '.join(str(n) for n in missing)}")
        )
    for index, message in enumerate(commits, start=1):
        faults += _loose(f"commit {index}", message)
    for index, entry in enumerate(changelog, start=1):
        faults += _loose(f"changelog entry {index}", entry)
    return faults


def neutralise(text: str) -> str:
    """The text with every reference to an issue or pull request turned into plain words."""

    def plain(found: re.Match[str]) -> str:
        number = next(g for g in found.groups() if g)
        return f"number {number}"

    return ANY_REFERENCE.sub(plain, text)


# --- reading a branch ---------------------------------------------------------------------


class ReadError(Exception):
    """Git could not be read, so nothing was scanned. Never a clean result."""


def _git(root: str, *args: str) -> str:
    import subprocess

    done = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        first = (done.stderr or done.stdout).strip().splitlines()[:1]
        raise ReadError(f"git {' '.join(args[:2])} failed ({first[0] if first else 'no message'})")
    return done.stdout


def commits_between(root: str, base: str, head: str) -> list[str]:
    """The full message of each commit on `head` that `base` does not hold."""
    out = _git(root, "log", "--format=%B%x00", f"{base}..{head}")
    return [m.strip() for m in out.split("\0") if m.strip()]


def changelog_entries(root: str, base: str, head: str) -> list[str]:
    """The lines the branch adds to `CHANGELOG.md` and to the files under `changes/`."""
    out = _git(root, "diff", "--no-renames", "-U0", f"{base}...{head}", "--", "CHANGELOG.md",
               "changes")
    return [line[1:].strip() for line in out.splitlines()
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip()]
