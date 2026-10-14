#!/usr/bin/env python3
# contract: agent
"""records-check.py: hold the project's records to the records model.

A thin command line over loop/records.py. Run it from the project:

    records-check.py [--project DIR] [--closing N ...]

It checks that each fact has one home and stays under its limit: `AGENTS.md` at
150 lines with no section over 12, `CLAUDE.md` that only imports it, the
overview at 100 lines, an overview area table that agrees with the area map,
area docs at 300 lines, every tracked file in an area, a changelog entry for
each piece in `--closing`, no paragraph repeated across documents, and no path
or command named in a record that does not exist. `loop/records.py` lists each
rule by name.

It reads the project and writes nothing. Each fault names the rule, the place
and the next step. It exits 1 when it finds a fault, and 0 when it finds none.
The project's `checks.yml` runs it, and so does the final combined check.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, records
from loop.paths import PathError, find_project_root

PROG = "records-check.py"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", help="the project folder (default: the one around here)")
    parser.add_argument(
        "--closing",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help="a piece the merge closes; it needs a changelog entry (repeat for each piece)",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = find_project_root(Path(args.project) if args.project else Path.cwd())
    except PathError as error:
        raise cli.Failure(
            str(error), next_command=f"{PROG} --help", code=cli.ExitCode.ENVIRONMENT
        ) from error
    try:
        found = records.check(root, closing=args.closing)
    except records.RecordsError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.ENVIRONMENT
        ) from error
    if found:
        listing = "\n".join(f"{f.rule}: {f.where}: {f.message}" for f in found)
        raise cli.Failure(
            f"{len(found)} fault(s) in the records:\n{listing}",
            next_command=found[0].next_step,
            data={"faults": [f.as_dict() for f in found]},
        )
    return {"faults": [], "closing": args.closing}


def main(argv: list[str]) -> int:
    return cli.run(
        PROG, "Hold the project's records to the records model.", setup, handle, argv
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
