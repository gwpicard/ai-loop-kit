#!/usr/bin/env python3
# contract: agent
"""closing-words.py: only a pull request's `Closes #<n>` lines may close a piece.

GitHub closes an issue when a closing word stands before its number, even in a sentence that
says it does not. This script reads the title, the body, the commit messages and the changelog
entries of a pull request and refuses a closing word anywhere but on a `Closes #<n>` line in
the body. It also needs one such line for each piece the pull request closes, and no line twice.

    closing-words.py --title <title> --body-file <file> [--range <base>..<head>]
                     [--piece <issue number> ...] [--project DIR]

`--range` adds the commit messages in the range and the lines the range adds to `CHANGELOG.md`
and to `changes/`. The script reads and writes nothing else. It exits 0 when it finds no fault,
1 when it finds one, and 4 when Git cannot be read: a scan that did not run is never a pass.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, closing
from loop.paths import PathError, find_project_root

PROG = "closing-words.py"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", help="the project folder (default: the one around here)")
    parser.add_argument("--title", default="", help="the pull request's title")
    parser.add_argument("--body-file", help="a file that holds the pull request's body")
    parser.add_argument("--range", dest="span", metavar="BASE..HEAD",
                        help="scan the commits and the changelog lines in this range")
    parser.add_argument("--piece", type=int, action="append", default=[], metavar="N",
                        help="the issue number of a piece the pull request closes (repeat)")


def handle(args: argparse.Namespace) -> dict[str, Any]:
    if not (args.title or args.body_file or args.span):
        raise cli.Failure("nothing to scan: give --title, --body-file or --range",
                          next_command=f"{PROG} --help", code=cli.ExitCode.USAGE)
    body = ""
    if args.body_file:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except OSError as error:
            raise cli.Failure(f"cannot read {args.body_file} ({error.strerror})",
                              next_command=f"{PROG} --help", code=cli.ExitCode.ENVIRONMENT
                              ) from error
    commits: list[str] = []
    changelog: list[str] = []
    if args.span:
        base, sep, head = args.span.partition("..")
        if not sep or not base or not head:
            raise cli.Failure("--range must read BASE..HEAD", next_command=f"{PROG} --help",
                              code=cli.ExitCode.USAGE)
        try:
            root = str(find_project_root(Path(args.project) if args.project else Path.cwd()))
            commits = closing.commits_between(root, base, head)
            changelog = closing.changelog_entries(root, base, head)
        except (PathError, closing.ReadError) as error:
            raise cli.Failure(f"{error}, so nothing was scanned",
                              next_command="check the branch names, then run this again",
                              code=cli.ExitCode.ENVIRONMENT) from error
    faults = closing.scan(title=args.title, body=body, commits=commits, changelog=changelog,
                          pieces=args.piece)
    listed = [{"where": f.where, "message": f.message} for f in faults]
    if faults:
        first = faults[0]
        raise cli.Failure(
            f"{len(faults)} closing-word fault(s): {first.where} {first.message}",
            next_command="rewrite the text so only Closes lines in the body close a piece, "
            f"then run {PROG} again", data={"faults": listed})
    return {"faults": [], "scanned": {"commits": len(commits), "changelog_lines": len(changelog)}}


def main(argv: list[str]) -> int:
    return cli.run(PROG, "Refuse a closing word anywhere but a Closes line in the body.",
                   setup, handle, argv, changes_state=False)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
