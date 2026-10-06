#!/usr/bin/env python3
# contract: agent
"""area-map.py: read the project's area map and say whether it is true.

A thin command line over loop/areas.py. The map is the file docs/area-map, one
`<pattern> <area>` line each, in the style of a CODEOWNERS file. The last
matching line wins. It holds no prose.

Commands:
  area-map.py check           every tracked file belongs to an area, and every area
                              matches a tracked file
  area-map.py which <path>... the area each path belongs to
  area-map.py areas           every area name, in the order of the map

`which` gives an area name, `unclaimed`, or `exempt` for a file at the project
root, a path under a hidden top-level folder, or a path under changes/. It
reads the map and writes nothing. `check` exits 1 and lists each fault when the
map is untrue.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import areas, cli
from loop.paths import PathError, Paths, find_project_root

PROG = "area-map.py"


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser("check", help="say whether the map is true")
    place = commands.add_parser("which", help="the area of each path")
    place.add_argument("paths", nargs="+", help="a path in the project")
    commands.add_parser("areas", help="every area name")


def _paths() -> Paths:
    try:
        return Paths.for_project(find_project_root(Path.cwd()))
    except PathError as error:
        raise cli.Failure(
            str(error), next_command=f"{PROG} --help", code=cli.ExitCode.ENVIRONMENT
        ) from error


def handle(args: argparse.Namespace) -> dict[str, Any]:
    paths = _paths()
    try:
        rules = areas.load(paths)
        if args.command == "areas":
            return {"areas": areas.names(rules)}
        if args.command == "which":
            return {"paths": {item: areas.which(rules, item) for item in args.paths}}
        faults = areas.problems(rules, areas.tracked_files(paths.root))
    except areas.AreaMapError as error:
        raise cli.Failure(
            str(error), next_command=error.next_command, code=cli.ExitCode.FAILURE
        ) from error
    if faults:
        raise cli.Failure(
            "\n".join(faults),
            next_command=f"correct {areas.MAP_FILE}, then run {PROG} check again",
            data={"problems": faults},
        )
    return {"areas": areas.names(rules), "problems": []}


def main(argv: list[str]) -> int:
    return cli.run(
        PROG, "Read the project's area map and say whether it is true.", setup, handle, argv
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
