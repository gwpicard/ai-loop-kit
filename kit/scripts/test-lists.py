#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""test-lists.py: run the two fresh test-list sessions and compare their lists.

Two sessions that carry none of the shaping conversation each list the tests
they would write for a piece. The lists are compared by the spec IDs they
cover, not by test name. An ID that one list covers and the other does not is a
difference.

  test-lists.py run --file <issue body file> --piece <number>

The ready gate runs the same code itself, inside move 2, and trusts no list that
an agent hands it. Use this command in /shape to see the differences early.
Nothing it prints is evidence. It opens two worktrees under .agents/worktrees/
and starts two `claude -p` sessions. With --dry-run it names them and starts
nothing. It exits 1 when the lists differ.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, sessions, spec, testlists
from loop.paths import PathError, Paths, find_project_root

PROG = "test-lists.py"


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    run = commands.add_parser("run", help="run the two sessions and compare their lists")
    run.add_argument("--file", required=True, help="a file that holds the piece's spec block")
    run.add_argument("--piece", type=int, required=True, help="the piece's number")


def handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        paths = Paths.for_project(find_project_root(Path.cwd()))
        text = Path(args.file).read_text(encoding="utf-8")
        parsed = spec.parse(text)
    except PathError as error:
        raise cli.Failure(
            str(error), next_command=f"{PROG} --help", code=cli.ExitCode.ENVIRONMENT
        ) from error
    except OSError as error:
        raise cli.Failure(
            f"{args.file} cannot be read ({error.strerror})",
            next_command=f"{PROG} run --help",
            code=cli.ExitCode.USAGE,
        ) from error
    except spec.SpecError as error:
        raise cli.Failure(
            str(error),
            next_command=error.next_command,
            code=cli.ExitCode.REFUSED if error.refused else cli.ExitCode.FAILURE,
        ) from error
    if not parsed.found or not parsed.ids:
        raise cli.Failure(
            "the spec holds no block, or no flow step or edge case with an ID",
            next_command="write the spec as kit/spec-format.md says, then run it again",
            code=cli.ExitCode.REFUSED,
        )
    labels = [testlists.worktree_name(args.piece, letter) for letter in testlists.LABELS]
    if args.dry_run:
        return {"would_run": labels, "ids": parsed.ids}
    try:
        found = testlists.run_two(paths, number=args.piece, block=parsed.block, ids=parsed.ids)
    except testlists.ListError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.ENVIRONMENT
        ) from error
    except sessions.SessionError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.ENVIRONMENT
        ) from error
    if found["differ"]:
        raise cli.Failure(
            "the two lists cover different IDs: " + ", ".join(found["differ"]),
            next_command="settle the difference in the spec, or split the piece, then run it again",
            data=found,
        )
    return found


def main(argv: list[str]) -> int:
    return cli.run(
        PROG,
        "Run the two fresh test-list sessions and compare their lists by spec ID.",
        setup,
        handle,
        argv,
        changes_state=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
