#!/usr/bin/env python3
# contract: agent
"""spec.py: read the spec block of a piece.

Commands:
  spec.py show <number>        read the spec of a piece (its issue, as the App)
  spec.py show --file <path>   read the spec in a file
  spec.py lint <number>        judge the spec; exit 1 when it has gaps
  spec.py needs <number>       work out what the piece still needs

`show` prints what the one shared parser (loop/spec.py) finds, as JSON. The
format is written in kit/spec-format.md. `lint` (loop/lint.py) and `needs`
(loop/needs.py) read through the same parser. All three change nothing.
The type of a piece (chore, bug or feature) comes from its `type:` label, or
from --type. It sets the length limit.

A piece is read from its GitHub issue as the gate's App, through loop/github.py.
With no App it is read from the gate's own record (.agents/pieces/<n>/), and a
piece the record does not hold is refused. It never uses the person's sign-in.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from loop import github, lint, moves, needs
from loop import spec as parser_module
from loop.cli import ExitCode, Failure, run
from loop.paths import PathError, Paths, find_project_root


def _add_source(command: argparse.ArgumentParser) -> None:
    command.add_argument("number", nargs="?", help="the issue number (a leading # is allowed)")
    command.add_argument("--file", help="read this file instead of an issue")
    command.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print JSON on standard output (the default when it is not a terminal)",
    )


def _add_judging(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--type",
        choices=sorted(lint.LENGTH_LIMITS),
        help="the type of the piece (default: its type: label, else feature)",
    )
    command.add_argument(
        "--tests",
        action="append",
        default=[],
        metavar="PATH",
        help="a test file or folder to trace against the spec IDs (repeat for more)",
    )


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    _add_source(commands.add_parser("show", help="read a spec and print its fields"))
    lint_parser = commands.add_parser("lint", help="judge a spec; exit 1 when it has gaps")
    _add_source(lint_parser)
    _add_judging(lint_parser)
    needs_parser = commands.add_parser("needs", help="list what the piece still needs")
    _add_source(needs_parser)
    _add_judging(needs_parser)


def _issue(number: str, command: str) -> tuple[str, list[str]]:
    """The body and the label names of a piece.

    With the gate's GitHub App, read from the issue as the App. With no App the
    gate's own record is the truth, so read its copy. Never the person's sign-in.
    """
    try:
        paths = Paths.for_project(find_project_root(Path.cwd()))
    except PathError as error:
        raise Failure(str(error), next_command=f"cd <the project>, then spec.py {command} "
                      + number, code=ExitCode.ENVIRONMENT) from error
    hub = github.GitHub(paths)
    try:
        if hub.available:
            issue = hub.read_issue(int(number))
            return str(issue["body"]), list(issue["labels"])
        piece = moves.find_piece(paths, int(number))
    except github.GitHubError as error:
        raise Failure(error.message, next_command=error.next_command, code=error.code) from error
    except moves.MoveError as error:
        raise Failure(error.message, next_command=error.next_command, code=error.code) from error
    if piece is None:
        raise Failure(
            f"the gate's GitHub App is not set up yet, so spec.py does not read GitHub, and "
            f"the gate's record holds no piece {number}",
            next_command=f"spec.py {command} --file <the spec>, or set up the App in the "
            "second half of /setup",
            code=ExitCode.REFUSED,
        )
    return piece.body, piece.labels()


def _load(args: argparse.Namespace) -> tuple[str, list[str], str]:
    """The body, the labels and the source name for the issue or file the arguments name."""
    command = args.command
    if bool(args.number) == bool(args.file):
        raise Failure(
            "give either an issue number or --file, not both and not neither",
            next_command=f"spec.py {command} --help",
            code=ExitCode.USAGE,
        )
    if args.file:
        path = Path(args.file)
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as error:
            raise Failure(
                f"cannot read {path} ({error.strerror})",
                next_command=f"spec.py {command} --file <path to an existing file>",
                code=ExitCode.ENVIRONMENT,
            ) from error
        return body, [], f"file {path}"
    number = str(args.number).lstrip("#")
    if not re.fullmatch(r"\d+", number):
        raise Failure(
            f"{args.number!r} is not an issue number",
            next_command=f"spec.py {command} <number>",
            code=ExitCode.USAGE,
        )
    body, labels = _issue(number, command)
    return body, labels, f"issue {number}"


def _refusal(error: parser_module.SpecError) -> Failure:
    return Failure(
        str(error),
        next_command=error.next_command,
        code=ExitCode.REFUSED if error.refused else ExitCode.FAILURE,
    )


def _type_of(args: argparse.Namespace, labels: list[str]) -> str:
    if args.type:
        return str(args.type)
    for label in labels:
        name = label.removeprefix("type:")
        if label.startswith("type:") and name in lint.LENGTH_LIMITS:
            return name
    return lint.DEFAULT_TYPE


def _read_tests(paths: list[str]) -> dict[str, str] | None:
    """The tests in the files and folders given, or None when none were given."""
    if not paths:
        return None
    found: dict[str, str] = {}
    suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".rs", ".sh"}
    for raw in paths:
        root = Path(raw)
        if not root.exists():
            raise Failure(
                f"the test path {raw} does not exist",
                next_command="spec.py lint --tests <an existing file or folder>",
                code=ExitCode.ENVIRONMENT,
            )
        if root.is_dir():
            files = sorted(p for p in root.rglob("*") if p.suffix in suffixes)
        else:
            files = [root]
        for file in files:
            try:
                text = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise Failure(
                    f"cannot read {file} ({error})",
                    next_command="spec.py lint --tests <a readable file or folder>",
                    code=ExitCode.ENVIRONMENT,
                ) from error
            for name, body in lint.read_tests(text).items():
                found[f"{file.name}::{name}"] = body
    return found


def show(args: argparse.Namespace) -> dict[str, Any]:
    body, _labels, source = _load(args)
    try:
        spec = parser_module.parse(body)
    except parser_module.SpecError as error:
        raise _refusal(error) from error
    return {**spec.to_dict(), "source": source}


def lint_command(args: argparse.Namespace) -> dict[str, Any]:
    body, labels, source = _load(args)
    issue_type = _type_of(args, labels)
    tests = _read_tests(args.tests)
    try:
        gaps = lint.lint_body(body, issue_type=issue_type, tests=tests)
    except parser_module.SpecError as error:
        raise _refusal(error) from error
    if gaps:
        shown = "; ".join(g["message"] for g in gaps[:5])
        more = f"; and {len(gaps) - 5} more" if len(gaps) > 5 else ""
        raise Failure(
            f"the spec of {source} has {len(gaps)} gap(s): {shown}{more}",
            next_command=gaps[0]["next"],
            data={"gaps": gaps, "source": source, "type": issue_type},
        )
    return {"gaps": [], "source": source, "type": issue_type}


def needs_command(args: argparse.Namespace) -> dict[str, Any]:
    body, labels, source = _load(args)
    issue_type = _type_of(args, labels)
    tests = _read_tests(args.tests)
    try:
        found = needs.needs_from_body(body, issue_type=issue_type, tests=tests)
    except parser_module.SpecError as error:
        raise _refusal(error) from error
    return {
        "needs": found,
        "count": len(found),
        "empty": not found,
        "needs_you": needs.needs_you(found),
        "source": source,
        "type": issue_type,
    }


HANDLERS = {"show": show, "lint": lint_command, "needs": needs_command}


def handle(args: argparse.Namespace) -> dict[str, Any]:
    return HANDLERS[args.command](args)


def main(argv: list[str]) -> int:
    return run(
        "spec.py",
        "Read, lint and list the needs of the spec block of a piece.",
        setup,
        handle,
        argv,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
