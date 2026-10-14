"""The held-out store: hidden cases kept where only the gate can read them.

The folder comes from `Paths.held_out_dir`. It sits outside the project and
outside git. The sandbox blocks a builder from reading it (P10, tested in P12),
and the guard hook denies the path (P3). This module adds a third layer: it
refuses to store a case when the folder would sit inside the project, and it
makes every folder and file private to the person who owns it.

A case is a text file named by its ID. The fingerprint is a hash over the case
IDs and the hash of each case. It never holds a case.

The store keeps any text. The attempt gate (`loop/gates/attempt.py`) runs each case as a
test file, so a case written for it carries a line `held-out-path: <relative path>` in
its first five lines, usually in a comment. The gate lays the file at that path over the
attempt, runs the judge's command with it, and never shows the case to a builder.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from loop import cli
from loop.paths import PathError, Paths, find_project_root

_CASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SUFFIX = ".case"


class HeldOutError(Exception):
    """A refusal. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


def folder(paths: Paths, piece: int) -> Path:
    return paths.held_out_dir / str(paths.piece_dir(piece).name)


def _check_outside(paths: Paths) -> None:
    held = paths.held_out_dir.resolve()
    root = paths.root.resolve()
    if held == root or root in held.parents:
        raise HeldOutError(
            f"the held-out folder {held} is inside the project, where a builder could read it",
            next_command="set AI_LOOP_KIT_DATA to a folder outside the project, "
            "then run the same command again",
        )


def _check_name(name: str) -> str:
    if not _CASE_NAME.match(name) or ".." in name:
        raise HeldOutError(
            f"{name!r} is not a valid case name",
            next_command="use letters, digits, '.', '_' and '-' only, then run it again",
        )
    return name


def _digest(cases: dict[str, str]) -> str:
    lines = [
        f"{name}\0{hashlib.sha256(text.encode('utf-8')).hexdigest()}\n"
        for name, text in sorted(cases.items())
    ]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def read(paths: Paths, piece: int) -> dict[str, str]:
    """Every stored case of a piece. A piece with none reads as empty."""
    where = folder(paths, piece)
    if not where.is_dir():
        return {}
    return {
        item.name[: -len(SUFFIX)]: item.read_text(encoding="utf-8")
        for item in sorted(where.iterdir())
        if item.name.endswith(SUFFIX)
    }


def fingerprint(paths: Paths, piece: int) -> str:
    cases = read(paths, piece)
    if not cases:
        raise HeldOutError(
            f"piece {piece} has no held-out cases",
            next_command=f"loop.heldout store --piece {piece} --case ID=FILE",
        )
    return _digest(cases)


def store(
    paths: Paths,
    piece: int,
    cases: dict[str, str],
    *,
    replace: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Store cases for a piece. Returns their IDs and the fingerprint, never a case.

    A case already stored with other text is refused unless `replace` is set.
    The same text again is not a change.
    """
    _check_outside(paths)
    for name in cases:
        _check_name(name)
    if not cases:
        raise HeldOutError(
            "no case was given",
            next_command=f"loop.heldout store --piece {piece} --case ID=FILE",
        )
    existing = read(paths, piece)
    for name, text in cases.items():
        if name in existing and existing[name] != text and not replace:
            raise HeldOutError(
                f"case {name} of piece {piece} is stored with other text",
                next_command=f"run the same command with --replace to overwrite case {name}",
            )
    merged = {**existing, **cases}
    result: dict[str, Any] = {
        "piece": piece,
        "cases": sorted(merged),
        "fingerprint": _digest(merged),
        "changed": merged != existing,
    }
    if dry_run:
        return result
    where = folder(paths, piece)
    for parent in (paths.held_out_dir, where):
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)
    for name, text in cases.items():
        target = where / f"{name}{SUFFIX}"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(target, 0o600)
    return result


# --- command line ---------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, text in (
        ("store", "store held-out cases (changes state)"),
        ("fingerprint", "print the fingerprint of a piece's cases"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--piece", type=int, required=True, help="the piece number")
        sub.add_argument("--root", help="the project folder (default: the one around here)")
        sub.add_argument(
            "--json", action="store_true", default=argparse.SUPPRESS, help="print JSON"
        )
        if name == "store":
            sub.add_argument(
                "--case", action="append", default=[], metavar="ID=FILE",
                help="a case ID and the file that holds its text (repeat for each case)",
            )
            sub.add_argument("--replace", action="store_true", help="overwrite a stored case")
            sub.add_argument(
                "--dry-run", action="store_true", default=argparse.SUPPRESS,
                help="say what would change, and change nothing",
            )


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = Path(args.root) if args.root else find_project_root(Path.cwd())
        paths = Paths.for_project(root)
        if args.command == "fingerprint":
            return {"piece": args.piece, "fingerprint": fingerprint(paths, args.piece)}
        cases: dict[str, str] = {}
        for item in args.case:
            name, sep, source = item.partition("=")
            if not sep:
                raise HeldOutError(
                    f"{item!r} is not ID=FILE", next_command="loop.heldout store --help"
                )
            try:
                cases[name] = Path(source).read_text(encoding="utf-8")
            except OSError as error:
                raise HeldOutError(
                    f"the file {source} could not be read ({error.strerror})",
                    next_command="check the path, then run the same command again",
                ) from error
        return store(
            paths, args.piece, cases,
            replace=args.replace, dry_run=getattr(args, "dry_run", False),
        )
    except PathError as error:
        raise cli.Failure(
            str(error), next_command="loop.heldout --help", code=cli.ExitCode.USAGE
        ) from error
    except HeldOutError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.REFUSED
        ) from error


def main(argv: list[str]) -> int:
    return cli.run(
        "heldout",
        "Keep hidden cases outside the project, where only the gate reads them.",
        _setup,
        _handle,
        argv,
        changes_state=True,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
