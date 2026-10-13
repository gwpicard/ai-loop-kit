"""The shared command-line contract for every agent script (design principle 8).

A script that uses `run` gets, without writing any of it:

- `--help`, which names the exit codes;
- `--json`, and JSON on standard output whenever it is not a terminal;
- `--dry-run`, when the script says it changes state;
- distinct exit codes (`ExitCode`);
- errors that name the next command on a `next:` line;
- no prompt, ever.

A handler gets the parsed arguments and returns a dictionary. It raises
`Failure` to refuse or to fail on purpose.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from enum import IntEnum
from typing import Any, NoReturn


class ExitCode(IntEnum):
    OK = 0
    FAILURE = 1  # the work ran and failed, or a check found a fault
    USAGE = 2  # the command line was wrong
    REFUSED = 3  # the script will not act yet; the next: line says what to do first
    ENVIRONMENT = 4  # a tool, file or setting the script needs is missing


EXIT_CODE_HELP = (
    "exit codes: 0 ok, 1 failed, 2 usage, 3 refused (see the next: line), "
    "4 missing tool or setting"
)


class Failure(Exception):
    """A stop on purpose. Carries the exit code and the next command."""

    def __init__(
        self,
        message: str,
        *,
        next_command: str,
        code: ExitCode = ExitCode.FAILURE,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.next_command = next_command
        self.code = code
        self.data = data or {}


class _Parser(argparse.ArgumentParser):
    """An argument parser that fails with the shared contract, and never exits itself."""

    def error(self, message: str) -> NoReturn:
        raise Failure(
            message,
            next_command=f"{self.prog} --help",
            code=ExitCode.USAGE,
        )


def make_parser(prog: str, description: str, *, changes_state: bool) -> argparse.ArgumentParser:
    parser = _Parser(
        prog=prog,
        description=description,
        epilog=EXIT_CODE_HELP,
        exit_on_error=False,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON on standard output (the default when it is not a terminal)",
    )
    if changes_state:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="say what would change, and change nothing",
        )
    return parser


def _emit_failure(failure: Failure, *, json_mode: bool) -> None:
    body: dict[str, Any] = {
        "ok": False,
        "error": failure.message,
        "next": failure.next_command,
        "exit_code": int(failure.code),
        **failure.data,
    }
    if json_mode:
        print(json.dumps(body, sort_keys=True))
    sys.stderr.write(f"error: {failure.message}\nnext: {failure.next_command}\n")


def run(
    prog: str,
    description: str,
    setup: Callable[[argparse.ArgumentParser], None],
    handler: Callable[[argparse.Namespace], dict[str, Any]],
    argv: Sequence[str],
    *,
    changes_state: bool = False,
    stdout_is_tty: bool | None = None,
) -> int:
    """Parse `argv`, run `handler`, print the result and return the exit code."""
    if stdout_is_tty is None:
        stdout_is_tty = sys.stdout.isatty()
    json_mode = "--json" in argv or not stdout_is_tty
    parser = make_parser(prog, description, changes_state=changes_state)
    setup(parser)
    try:
        args = parser.parse_args(list(argv))
    except Failure as failure:
        _emit_failure(failure, json_mode=json_mode)
        return int(failure.code)
    except SystemExit as stop:  # --help
        return int(stop.code or 0)
    try:
        data = handler(args)
    except Failure as failure:
        _emit_failure(failure, json_mode=json_mode)
        return int(failure.code)
    except Exception as exc:
        _emit_failure(
            Failure(f"{type(exc).__name__}: {exc}", next_command=f"{prog} --help"),
            json_mode=json_mode,
        )
        return int(ExitCode.FAILURE)
    body: dict[str, Any] = {"ok": True, **data}
    if getattr(args, "dry_run", False):
        body["dry_run"] = True
    if json_mode:
        print(json.dumps(body, sort_keys=True))
    else:
        for key, value in body.items():
            print(f"{key}: {value}")
    return int(ExitCode.OK)
