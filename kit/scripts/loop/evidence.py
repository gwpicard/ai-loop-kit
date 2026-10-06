"""The piece record: a hash-chained file of what the gate saw, kept in `.agents/pieces/<n>/`.

Only the gate writes it. No agent calls `append`: an agent's word is never
evidence. The chain is the one `gate.chain_of` defines, so a record written here
reads in the gate and the other way round. Each line holds one entry and the
hash of the line before it. An edited or removed line breaks every hash after
it, and `read` refuses the record with a `next:` line.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

from gate import chain_of

from loop import cli
from loop.paths import PathError, Paths, find_project_root

EVIDENCE = "evidence.jsonl"


class EvidenceError(Exception):
    """A record that cannot be trusted. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


def record_path(paths: Paths, number: int) -> Path:
    return paths.piece_dir(number) / EVIDENCE


def _scan(path: Path) -> tuple[list[dict[str, Any]], str, int]:
    """The entries, the last hash and the byte length of a cut-off last line."""
    if not path.exists():
        return [], "", 0
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("\n")
    fragment = parts.pop()
    entries: list[dict[str, Any]] = []
    previous = ""
    for count, line in enumerate(parts, start=1):
        try:
            value = json.loads(line)
        except ValueError:
            value = None
        chain = value.pop("chain", None) if isinstance(value, dict) else None
        if not isinstance(value, dict) or chain != chain_of(previous, value):
            raise EvidenceError(
                f"line {count} of {path.name} was not written by the gate: it does not "
                "follow from the line before it, so the record cannot be trusted",
                next_command="stop and tell the person; only they move that file aside, "
                "then run the same command again",
            )
        previous = str(chain)
        entries.append(value)
    return entries, previous, len(fragment.encode("utf-8"))


def read(paths: Paths, number: int) -> list[dict[str, Any]]:
    """Every entry of the piece record. Raises `EvidenceError` when a line was edited."""
    return _scan(record_path(paths, number))[0]


def append(
    paths: Paths, number: int, entries: list[dict[str, Any]], *, dry_run: bool = False
) -> list[str]:
    """Add each entry as one chained line, under a lock on the piece's folder.

    Returns the notes to say, such as a cut-off last line set aside. It refuses
    to extend a record whose chain is broken.
    """
    path = record_path(paths, number)
    _, previous, cut = _scan(path)
    notes: list[str] = []
    if cut:
        notes.append(
            f"an interrupted write had left a cut-off last line in {path.name}; it was set aside"
        )
    if dry_run:
        return notes
    path.parent.mkdir(parents=True, exist_ok=True)
    fcntl: Any
    try:
        fcntl = importlib.import_module("fcntl")
    except ImportError:  # not a POSIX system; the record goes unlocked
        fcntl = None
    with open(path.parent / ".lock", "a", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        _, previous, cut = _scan(path)
        if cut:
            size = path.stat().st_size
            with open(path, "r+b") as handle:
                handle.truncate(size - cut)
        text = ""
        for entry in entries:
            chain = chain_of(previous, entry)
            text += json.dumps(dict(entry, chain=chain), sort_keys=True) + "\n"
            previous = chain
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
    return notes


# --- command line ---------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    show = commands.add_parser("show", help="read a piece record and check its chain")
    show.add_argument("--piece", type=int, required=True, help="the piece number")
    show.add_argument("--root", help="the project folder (default: the one around here)")
    show.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print JSON"
    )


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = Path(args.root) if args.root else find_project_root(Path.cwd())
        paths = Paths.for_project(root)
        entries = read(paths, args.piece)
    except PathError as error:
        raise cli.Failure(
            str(error), next_command="evidence show --help", code=cli.ExitCode.USAGE
        ) from error
    except EvidenceError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.REFUSED
        ) from error
    return {"piece": args.piece, "entries": entries, "count": len(entries)}


def main(argv: list[str]) -> int:
    return cli.run(
        "evidence",
        "Read a piece record and check its hash chain. The gate alone writes the record.",
        _setup,
        _handle,
        argv,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
