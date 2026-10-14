#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""trim-check.py: the trim pass, the last step of a piece's build loop.

Commands:
  trim-check.py check --base REF --piece-head REF --trim-head REF [--judge-file PATH ...]
      Judge a trim commit by the trim rules. It reads git only and changes nothing.
  trim-check.py run --piece N --run NAME [--max-budget-usd AMOUNT]
      Run the whole pass on a piece that passed the attempt gate: make a scratch branch and
      worktree, run a fresh session on it, judge its commit, run the attempt checks again
      on it, and only on green move the piece branch to it by a fast-forward. With
      --dry-run it names the scratch branch and the tools it found, and changes nothing.

A trim may only remove or fold code the piece added, in one commit. It never touches a
test or any other file of the frozen bar, changes no line the piece did not add, adds no
file, and adds no net lines (`loop/trim.py` lists each rule by name). A trim that fails is
thrown away: the scratch branch is left, the piece branch is unchanged, no attempt is
counted, and the piece goes on untrimmed.

Exit codes: 0 the trim is clean (`run`: trimmed, or nothing to trim); 1 the trim broke a
rule or a check, and was thrown away; 2 usage; 3 the pass could not tell (git, a record or
a file), so it refused and kept the piece untrimmed; 4 a tool or the project is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, moves, spec, trim
from loop.gates import CheckContext, attempt
from loop.paths import PathError, Paths, find_project_root
from loop.states import by_number

PROG = "trim-check.py"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("command", choices=("check", "run"), nargs="?", help="what to do")
    parser.add_argument("--project", help="the project folder (default: the one around here)")
    parser.add_argument("--base", help="check: the piece's base commit")
    parser.add_argument("--piece-head", help="check: the piece branch's head before the trim")
    parser.add_argument("--trim-head", help="check: the scratch branch's head after the trim")
    parser.add_argument("--judge-file", action="append", default=[], metavar="PATH",
                        help="check: a judge file of the piece (repeat for each)")
    parser.add_argument("--piece", type=int, help="run: the piece number")
    parser.add_argument("--run", dest="run_name", help="run: the name of the run")
    parser.add_argument("--max-budget-usd", type=float, help="run: a cost cap for the session")


def _root(args: argparse.Namespace) -> Path:
    try:
        return find_project_root(Path(args.project) if args.project else Path.cwd())
    except PathError as error:
        raise cli.Failure(str(error), next_command=f"{PROG} --help",
                          code=cli.ExitCode.ENVIRONMENT) from error


def _missing(args: argparse.Namespace, *names: str) -> None:
    absent = [n for n in names if not getattr(args, n)]
    if absent:
        flags = ", ".join("--" + n.replace("_", "-") for n in absent)
        raise cli.Failure(f"{args.command} needs {flags}", next_command=f"{PROG} --help",
                          code=cli.ExitCode.USAGE)


def _refusal(error: trim.TrimError) -> cli.Failure:
    return cli.Failure(str(error), next_command=error.next_command, code=cli.ExitCode.REFUSED,
                       data={"outcome": "refused"})


def do_check(args: argparse.Namespace) -> dict[str, Any]:
    _missing(args, "base", "piece_head", "trim_head")
    try:
        verdict = trim.check(_root(args), args.base, args.piece_head, args.trim_head,
                             judge_files=args.judge_file)
    except trim.TrimError as error:
        raise _refusal(error) from error
    found = [v.as_dict() for v in verdict.violations]
    if found:
        raise cli.Failure(
            "the trim breaks the trim rules: " + "; ".join(v.line() for v in verdict.violations),
            next_command="throw the trim away and go on untrimmed: the scratch branch is left "
            "and the piece branch is unchanged",
            data={"violations": found, "commits": verdict.commits, "net_lines": verdict.net,
                  "files": verdict.files})
    return {"violations": [], "commits": verdict.commits, "net_lines": verdict.net,
            "files": verdict.files}


def do_run(args: argparse.Namespace) -> dict[str, Any]:
    _missing(args, "piece", "run_name")
    root = _root(args)
    paths = Paths.for_project(root)
    try:
        piece = moves.read_piece(paths, args.piece)
    except moves.MoveError as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=cli.ExitCode.REFUSED) from error
    if piece is None:
        raise cli.Failure(f"piece {args.piece} is not in the gate's record",
                          next_command="gate.py report", code=cli.ExitCode.REFUSED)
    if piece.state not in ("building", "review"):
        raise cli.Failure(
            f"piece {args.piece} is {piece.state}, and the trim pass runs on a piece that "
            "passed the attempt gate", next_command=f"gate.py report {args.piece}",
            code=cli.ExitCode.REFUSED)
    try:
        parsed: dict[str, Any] | None = spec.parse(piece.body).to_dict()
    except spec.SpecError:
        parsed = None
    ctx = CheckContext(number=piece.number, move=by_number(5), origin="building",
                       target="review", reason=None, title=piece.title, body=piece.body,
                       spec=parsed, record=piece.record, paths=paths, options={})
    try:
        answer = trim.run_pass(ctx, attempt.default_deps(paths), run=args.run_name,
                               max_budget_usd=args.max_budget_usd, dry_run=args.dry_run)
    except trim.TrimError as error:
        raise _refusal(error) from error
    if answer["outcome"] == "untrimmed":
        raise cli.Failure(
            "the trim was thrown away, and the piece goes on untrimmed: "
            + "; ".join(answer["reasons"]),
            next_command=f"the scratch branch {answer['scratch_branch']} is left to read; "
            "go on with the piece as it is", data=answer)
    return answer


def handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "check":
        return do_check(args)
    if args.command == "run":
        return do_run(args)
    raise cli.Failure("say what to do: check or run", next_command=f"{PROG} --help",
                      code=cli.ExitCode.USAGE)


def main(argv: list[str]) -> int:
    return cli.run(PROG, "Run the trim pass, and judge a trim.", setup, handle, argv,
                   changes_state=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
