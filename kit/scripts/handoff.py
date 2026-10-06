#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""Hand a builder session back to the run. It is the only way a builder ends.

A builder cannot ask a question and cannot wait for an answer. It runs one of
these five commands as its last act. Each writes the one hand-off file the run
will read, then returns at once:

  done                    --summary TEXT [--decision TEXT ...]
  bar-is-wrong            --evidence TEXT
  needs-the-person        --question TEXT
  blocked-by-environment  --reason TEXT
  gave-up                 --reason TEXT

`--decision` records a choice the builder made alone, where the spec was silent.
Only `done` carries decisions. Put `--file`, `--json` and `--dry-run` before the
outcome. The file is named by `--file`, or by AI_LOOP_KIT_HANDOFF_FILE, which the
session starter sets.

The first hand-off wins. The same hand-off again changes nothing. A different one
is refused, so a session cannot change its mind after the run has read it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, sessions

PROG = "handoff.py"

STOP = "Your hand-off is written. Stop now: the run reads it and decides what happens next."


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        help="the hand-off file (default: the AI_LOOP_KIT_HANDOFF_FILE variable)",
    )
    sub = parser.add_subparsers(dest="outcome", required=True, metavar="OUTCOME")
    done = sub.add_parser("done", help="the piece is built")
    done.add_argument("--summary", required=True, help="what was built, in a few lines")
    done.add_argument(
        "--decision",
        action="append",
        default=[],
        help="a choice made alone where the spec was silent (repeat for each)",
    )
    bar = sub.add_parser("bar-is-wrong", help="the frozen bar cannot be right")
    bar.add_argument("--evidence", required=True, help="what shows the bar is wrong")
    person = sub.add_parser("needs-the-person", help="a question only the person can answer")
    person.add_argument("--question", required=True, help="the one question to ask")
    blocked = sub.add_parser("blocked-by-environment", help="the environment stops the work")
    blocked.add_argument("--reason", required=True, help="what is blocked, and by what")
    gave = sub.add_parser("gave-up", help="no route forward")
    gave.add_argument("--reason", required=True, help="what was tried, and why it failed")


def build(args: argparse.Namespace) -> dict[str, Any]:
    outcome: str = args.outcome
    data: dict[str, Any] = {
        "outcome": outcome,
        sessions.HANDOFF_FIELD[outcome]: getattr(args, sessions.HANDOFF_FIELD[outcome]),
    }
    if outcome == "done" and args.decision:
        data["decisions"] = list(args.decision)
    try:
        return sessions.validate_handoff(data)
    except sessions.SessionError as exc:
        raise cli.Failure(
            str(exc), next_command=f"{PROG} {outcome} --help", code=cli.ExitCode.USAGE
        ) from exc


def handle(args: argparse.Namespace) -> dict[str, Any]:
    data = build(args)
    target = args.file or os.environ.get(sessions.HANDOFF_ENV)
    if not target:
        raise cli.Failure(
            "no hand-off file is named",
            next_command=f"{PROG} --file <path> {args.outcome} ..., "
            f"or set {sessions.HANDOFF_ENV}",
            code=cli.ExitCode.ENVIRONMENT,
        )
    path = Path(target)
    if not path.parent.is_dir():
        raise cli.Failure(
            f"the folder for the hand-off file does not exist: {path.parent}",
            next_command="start the session through loop/sessions.py, which makes it",
            code=cli.ExitCode.ENVIRONMENT,
        )
    if path.exists():
        try:
            earlier = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            earlier = None
        if earlier == data:
            return {"outcome": data["outcome"], "file": str(path), "written": False, "stop": STOP}
        raise cli.Failure(
            f"a hand-off is already written at {path}, and it is a different one",
            next_command="stop now. The first hand-off stands, and you cannot change it",
            code=cli.ExitCode.REFUSED,
        )
    if not args.dry_run:
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "outcome": data["outcome"],
        "file": str(path),
        "written": not args.dry_run,
        "stop": STOP,
    }


if __name__ == "__main__":
    sys.exit(
        cli.run(
            PROG,
            "Write the builder's hand-off and return at once.",
            setup,
            handle,
            sys.argv[1:],
            changes_state=True,
        )
    )
