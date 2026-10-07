#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""gate.py: the only way a piece changes state.

A thin command line over loop/moves.py (the moves and shared rules),
loop/states.py (the table of seven states and fourteen moves) and
loop/github.py (the gh wrapper, credential() and the push step).

Commands:
  gate.py capture [<number>] --title <title> --body-file <file> [--type feature|bug|chore]
  gate.py move <number> <state> [--reason <why>] [--option key=value ...]
  gate.py drop <number> --reason <why>
  gate.py answer <number> --question <text> --answer <text> --by <who answered>
  gate.py spec <number> --body-file <file>
  gate.py comment <number> (--text <words> | --body-file <file>)
  gate.py report [<number>] [--brief]
  gate.py labels --create
  gate.py branch <number> [--push]
  gate.py sync (--dry-run | --confirm <digest>)

A <number> is the piece's local number or, once sync has opened its issue, the
issue's number.

The gate acts on GitHub only as its GitHub App, set up in the second half of
/setup. Before the App exists it makes every move in the piece record
(.agents/pieces/<n>/), queues the GitHub writes there, and its next: line names
gate.py sync. Only the person runs gate.py sync, with their own sign-in. They
run gate.py sync --dry-run first, which lists every queued write in full and
prints a digest of the queue. Sync needs --confirm with that digest, and
refuses a queue that changed since. It also refuses unless a person is at a
terminal (standard input and output both a terminal), it refuses in an agent
session, and the guard hook refuses it too.

Every command prints JSON when standard output is not a terminal, and takes
--dry-run where it changes state.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from loop import evidence, github, moves, spec, states
from loop.cli import ExitCode, Failure, run
from loop.paths import PathError, Paths, find_project_root

PROG = "gate.py"


def _common(command: argparse.ArgumentParser, *, changes: bool = True) -> None:
    command.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print JSON on standard output (the default when it is not a terminal)",
    )
    if changes:
        command.add_argument(
            "--dry-run",
            action="store_true",
            default=argparse.SUPPRESS,
            help="say what would change, and change nothing",
        )


def _number(text: str) -> int:
    cleaned = text.lstrip("#")
    if not cleaned.isdigit() or int(cleaned) < 1:
        raise argparse.ArgumentTypeError(f"{text!r} is not a piece number")
    return int(cleaned)


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    capture = commands.add_parser("capture", help="move 1: capture an idea as a piece")
    capture.add_argument("number", nargs="?", type=_number, help="an issue that exists")
    capture.add_argument("--title", default="", help="the idea in the person's words")
    capture.add_argument("--body-file", help="a file with the body (the spec block)")
    capture.add_argument("--type", default="feature", choices=states.TYPES)
    _common(capture)

    move = commands.add_parser("move", help="move a piece by one move of the table")
    move.add_argument("number", type=_number)
    move.add_argument("target", help="the state to move to")
    move.add_argument("--reason", help="why; every move back needs one")
    move.add_argument("--option", action="append", default=[], metavar="KEY=VALUE",
                      help="a value for the move's checks (repeat for more)")
    _common(move)

    drop = commands.add_parser("drop", help="move 14: drop a piece, with a reason")
    drop.add_argument("number", type=_number)
    drop.add_argument("--reason", required=True)
    _common(drop)

    answer = commands.add_parser("answer", help="write an answer under Decisions")
    answer.add_argument("number", type=_number)
    answer.add_argument("--question", required=True, help="the open question it answers")
    answer.add_argument("--answer", required=True)
    answer.add_argument("--by", required=True,
                        help='who answered; an agent session records only "the agent"')
    answer.add_argument("--parked", action="store_true",
                        help="the question was a builder's, parked in building; the spec does "
                        "not hold it")
    _common(answer)

    spec_cmd = commands.add_parser("spec", help="hand the gate a new spec for a piece in shaping")
    spec_cmd.add_argument("number", type=_number)
    spec_cmd.add_argument("--body-file", required=True)
    _common(spec_cmd)

    comment = commands.add_parser("comment", help="post a comment on the issue as the App")
    comment.add_argument("number", type=_number)
    words = comment.add_mutually_exclusive_group(required=True)
    words.add_argument("--text")
    words.add_argument("--body-file")
    _common(comment)

    report = commands.add_parser("report", help="where each piece is and what waits")
    report.add_argument("number", nargs="?", type=_number)
    report.add_argument("--brief", action="store_true",
                        help="the short report the session start hook injects; no GitHub call")
    _common(report, changes=False)

    labels = commands.add_parser("labels", help="create the gate's own labels")
    labels.add_argument("--create", action="store_true", required=True)
    _common(labels)

    branch = commands.add_parser("branch", help="make the piece branch, and push it")
    branch.add_argument("number", type=_number)
    branch.add_argument("--push", action="store_true", help="push it, after the secret scan")
    _common(branch)

    sync = commands.add_parser("sync", help="the person sends the queued GitHub writes")
    sync.add_argument("--confirm", metavar="DIGEST",
                      help="the digest that sync --dry-run printed for the queue")
    _common(sync)


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise Failure(
            f"cannot read {path} ({error.strerror})",
            next_command=f"{PROG} --help",
            code=ExitCode.USAGE,
        ) from error


def _paths() -> Paths:
    try:
        root = find_project_root(Path.cwd())
    except PathError as error:
        raise Failure(str(error), next_command="cd <the project>, then run gate.py again",
                      code=ExitCode.ENVIRONMENT) from error
    return Paths.for_project(root)


def _options(raw: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for item in raw:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise Failure(f"--option {item!r} is not KEY=VALUE", code=ExitCode.USAGE,
                          next_command=f"{PROG} move --help")
        found[key] = value
    return found


def _branch(gate: moves.Gate, paths: Paths, args: argparse.Namespace, dry: bool) -> dict[str, Any]:
    number = gate.piece(args.number).number
    name = f"piece-{number}"
    root = str(paths.root)
    have = subprocess.run(["git", "-C", root, "rev-parse", "--verify", "-q",
                           f"refs/heads/{name}"], capture_output=True, text=True, check=False)
    made = False
    if have.returncode != 0 and not dry:
        done = subprocess.run(["git", "-C", root, "branch", name, "main"],
                              capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise Failure(f"git could not make {name} from main ({done.stderr.strip()})",
                          next_command=f"git -C {root} branch --list", code=ExitCode.FAILURE)
        made = True
    out: dict[str, Any] = {"piece": number, "branch": name, "made": made}
    if args.push and not dry:
        try:
            out.update(github.push(paths, name))
        except github.NoApp as error:
            raise Failure(
                error.message,
                next_command=f"tell the person to run, in their own terminal: cd {root} && "
                f"git push origin {name} (their pre-push hook scans for secrets)",
                code=ExitCode.REFUSED,
            ) from error
    return out


def handle(args: argparse.Namespace) -> dict[str, Any]:
    paths = _paths()
    dry = bool(getattr(args, "dry_run", False))
    command = args.command
    person = command == "sync"
    hub = github.GitHub(paths, as_person=person)
    gate = moves.Gate(paths, hub, env=os.environ)
    try:
        if command == "capture":
            body = _read(args.body_file) if args.body_file else None
            if args.number is None and body is None:
                raise Failure("a new piece needs --body-file", code=ExitCode.USAGE,
                              next_command=f'{PROG} capture --title "<t>" --body-file <file>')
            return gate.capture(title=args.title, body=body, issue_type=args.type,
                                number=args.number, dry_run=dry)
        if command == "move":
            return gate.move(args.number, args.target, reason=args.reason,
                             options=_options(args.option), dry_run=dry)
        if command == "drop":
            return gate.move(args.number, "dropped", reason=args.reason, dry_run=dry)
        if command == "answer":
            return gate.answer(args.number, question=args.question, answer=args.answer,
                               by=args.by, parked=args.parked, dry_run=dry)
        if command == "spec":
            return gate.set_spec(args.number, _read(args.body_file), dry_run=dry)
        if command == "comment":
            text = args.text if args.text is not None else _read(args.body_file)
            return gate.comment(args.number, text, dry_run=dry)
        if command == "report":
            return gate.report(brief=args.brief, number=args.number)
        if command == "labels":
            return gate.create_labels(dry_run=dry)
        if command == "branch":
            return _branch(gate, paths, args, dry)
        if command == "sync":
            if github.in_agent_session(os.environ):
                raise moves.MoveError(
                    "gate.py sync acts with the person's own sign-in, so only the person "
                    "runs it, never an agent session",
                    next_command=github.sync_command(paths.root),
                )
            return gate.sync(hub, dry_run=dry, confirm=args.confirm)
    except moves.MoveError as error:
        raise Failure(error.message, next_command=error.next_command, code=error.code,
                      data=error.data) from error
    except github.GitHubError as error:
        raise Failure(error.message, next_command=error.next_command, code=error.code) from error
    except evidence.EvidenceError as error:
        raise Failure(str(error), next_command=error.next_command,
                      code=ExitCode.REFUSED) from error
    except spec.SpecError as error:
        raise Failure(str(error), next_command=error.next_command,
                      code=ExitCode.REFUSED if error.refused else ExitCode.FAILURE) from error
    raise Failure(f"{command} is not a command", next_command=f"{PROG} --help",
                  code=ExitCode.USAGE)


def main(argv: list[str]) -> int:
    return run(PROG, "The only way a piece changes state.", setup, handle, argv,
               changes_state=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
