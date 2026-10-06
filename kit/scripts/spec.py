#!/usr/bin/env python3
# contract: agent
"""spec.py: read the spec block of a piece.

Commands:
  spec.py show <number>        read the spec in a GitHub issue
  spec.py show --file <path>   read the spec in a file

`show` prints what the one shared parser (loop/spec.py) finds, as JSON. The
format is written in kit/spec-format.md. `show` changes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from loop import spec as parser_module
from loop.cli import ExitCode, Failure, run


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    show = commands.add_parser("show", help="read a spec and print its fields")
    show.add_argument("number", nargs="?", help="the issue number (a leading # is allowed)")
    show.add_argument("--file", help="read this file instead of an issue")
    show.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print JSON on standard output (the default when it is not a terminal)",
    )


def _issue_body(number: str) -> str:
    try:
        done = subprocess.run(
            ["gh", "issue", "view", number, "--json", "body"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise Failure(
            f"the GitHub command-line tool could not be started ({error})",
            next_command="install gh from https://cli.github.com, then run spec.py show "
            f"{number}",
            code=ExitCode.ENVIRONMENT,
        ) from error
    if done.returncode != 0:
        lines = [line.strip() for line in done.stderr.splitlines() if line.strip()]
        raise Failure(
            f"GitHub did not give issue {number} ({lines[0] if lines else 'no message'})",
            next_command="gh auth status, then spec.py show " + number,
        )
    try:
        body = json.loads(done.stdout)["body"]
    except (ValueError, KeyError, TypeError) as error:
        raise Failure(
            f"GitHub gave an answer for issue {number} that holds no body",
            next_command="gh issue view " + number,
        ) from error
    return str(body or "")


def show(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.number) == bool(args.file):
        raise Failure(
            "give either an issue number or --file, not both and not neither",
            next_command="spec.py show --help",
            code=ExitCode.USAGE,
        )
    if args.file:
        path = Path(args.file)
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as error:
            raise Failure(
                f"cannot read {path} ({error.strerror})",
                next_command="spec.py show --file <path to an existing file>",
                code=ExitCode.ENVIRONMENT,
            ) from error
        source = f"file {path}"
    else:
        number = str(args.number).lstrip("#")
        if not re.fullmatch(r"\d+", number):
            raise Failure(
                f"{args.number!r} is not an issue number",
                next_command="spec.py show <number>",
                code=ExitCode.USAGE,
            )
        body = _issue_body(number)
        source = f"issue {number}"
    try:
        spec = parser_module.parse(body)
    except parser_module.SpecError as error:
        raise Failure(
            str(error),
            next_command=error.next_command,
            code=ExitCode.REFUSED if error.refused else ExitCode.FAILURE,
        ) from error
    return {**spec.to_dict(), "source": source}


def main(argv: list[str]) -> int:
    return run(
        "spec.py",
        "Read the spec block of a piece.",
        setup,
        show,
        argv,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
