#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""run.py: run the pieces the person picked, as a plain script.

    run.py [--pieces 1,2,3] [--run NAME] [--unattended] [--merge-pre-approved] [--plan]

It plans the pieces by dependency and area, claims them as builder slots free up, builds each
one attempt by attempt in a fresh `claude -p` session, routes each outcome through the gate,
and keeps the run record. It is not an agent, so it never stops to ask a question.

The order of work:

1. The pre-run check (`pre-run-check.py`) runs first. A refusal stops the run with the reason.
   `--unattended` and `--merge-pre-approved` are passed to it, and it refuses both without the
   gate's GitHub App. The policy has no key for either on purpose.
2. The lock file keeps a second copy of the same run out. A run that was killed and started
   again with the same --run NAME resumes from its run record, and never redoes a finished piece.
3. Slots are sized from free memory and capped by `builder_cap`. No two pieces in one area run
   at once. Every move goes through `gate.py`, never through a label or a record written here.
4. A stop signal (SIGTERM, SIGINT) sends each building piece back to ready by move 7 and keeps
   its branch. A spend cap, per piece or per run, parks the run until the person raises it.
5. Before the gate's App exists, a piece that needs a GitHub step parks as waiting for the
   person, with the `next:` line in the run record, and the other pieces go on.

`--plan` (the same as `--dry-run`) prints the order and the waves, and changes nothing.

On a Mac the run keeps the computer awake with `caffeinate -i`, which it starts before the
pre-run check, since the check refuses a computer that nothing holds awake. Elsewhere it prints a
line saying so. The morning summary is `.agents/runs/<name>/summary.md`.

The optional modules `watch`, `mailbox`, `inbox`, `integrate`, `review` and `pull_request` in `loop/run/`
are called when they exist (see `loop/run/__init__.py`), so later pieces add modules and do
not edit this script.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, github, moves, policy, sessions
from loop.paths import PathError, Paths, find_project_root
from loop.run import engine, plan, record

PROG = "run.py"
HERE = Path(__file__).resolve().parent


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".",
                        help="a folder inside the project (default: here)")
    parser.add_argument("--pieces", default="",
                        help="the pieces to run, as 1,2,3 (default: every piece that is ready)")
    parser.add_argument("--run", dest="run_name", default="",
                        help="the run's name; an existing name resumes that run")
    parser.add_argument("--unattended", action="store_true",
                        help="nobody watches this run: the pre-run check needs the App")
    parser.add_argument("--merge-pre-approved", action="store_true", dest="merge_pre_approved",
                        help="the person pre-approved the merge for this run (the default is no)")
    parser.add_argument("--plan", action="store_true", dest="dry_run",
                        help="the same as --dry-run: print the plan, and change nothing")


def _fail(message: str, next_command: str, code: cli.ExitCode = cli.ExitCode.REFUSED,
          **data: Any) -> cli.Failure:
    return cli.Failure(message, next_command=next_command, code=code, data=data)


def _paths(args: argparse.Namespace) -> Paths:
    try:
        return Paths.for_project(find_project_root(Path(args.project)))
    except PathError as error:
        raise _fail(str(error), "cd into the project, then run run.py again",
                    cli.ExitCode.ENVIRONMENT) from error


def _numbers(paths: Paths, text: str) -> list[int]:
    """The local numbers of the pieces to run."""
    try:
        if text.strip() and text.strip().lower() not in ("ready", "all"):
            words = [w for w in text.replace(",", " ").split() if w]
            if not words or not all(w.lstrip("#").isdigit() for w in words):
                raise _fail(f"--pieces {text!r} is not a list of piece numbers",
                            "run.py --pieces 1,2,3", cli.ExitCode.USAGE)
            found: list[int] = []
            for word in words:
                piece = moves.find_piece(paths, int(word.lstrip("#")))
                if piece is None:
                    raise _fail(f"piece {word} is not in the gate's record", "gate.py report")
                if piece.state != "ready":
                    raise _fail(f"piece {piece.number} is {piece.state}, and only a ready piece "
                                "can be run", f"gate.py report {piece.number}")
                if piece.number not in found:
                    found.append(piece.number)
            return found
        folder = paths.pieces_dir
        every = sorted(int(p.name) for p in folder.iterdir()
                       if p.is_dir() and p.name.isdigit()) if folder.is_dir() else []
        ready = []
        for number in every:
            piece = moves.read_piece(paths, number)
            if piece is not None and piece.state == "ready":
                ready.append(number)
        return ready
    except moves.MoveError as error:
        raise _fail(str(error), error.next_command) from error


def _pre_run_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "pre_run_check_for_run", HERE / "pre-run-check.py")
    if spec is None or spec.loader is None:
        raise _fail("pre-run-check.py cannot be loaded", "reinstall the kit",
                    cli.ExitCode.ENVIRONMENT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pre_run_check_for_run"] = module
    spec.loader.exec_module(module)
    return module


def _policy(paths: Paths) -> dict[str, Any]:
    try:
        return policy.load(paths.policy_file)
    except policy.PolicyError as error:
        raise _fail(f"the policy cannot be used: {error}",
                    f"fix {paths.policy_file}, then run run.py again") from error


def _pre_run_check(paths: Paths, name: str, numbers: list[int], args: argparse.Namespace,
                   command: list[str]) -> list[str]:
    """Run the pre-run check. Returns its notices. Anything but a pass is a refusal."""
    argv = [sys.executable, str(HERE / "pre-run-check.py"), "--project", str(paths.root),
            "--run", name, "--pieces", ",".join(str(n) for n in numbers),
            "--session-command", shlex.join(command), "--json"]
    if args.unattended:
        argv.append("--unattended")
    if args.merge_pre_approved:
        argv.append("--merge-pre-approved")
    try:
        done = subprocess.run(argv, capture_output=True, text=True, check=False,
                              stdin=subprocess.DEVNULL)
    except OSError as error:
        raise _fail(f"the pre-run check could not start ({error})", "reinstall the kit",
                    cli.ExitCode.ENVIRONMENT) from error
    data: dict[str, Any] = {}
    for line in reversed((done.stdout or "").strip().splitlines()):
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            data = parsed
            break
    if done.returncode == 0 and data.get("ok"):
        return [str(n) for n in data.get("notices", [])]
    raise _fail(
        str(data.get("error") or "the pre-run check did not pass, so the run will not start"),
        str(data.get("next") or "run pre-run-check.py, and fix what it names"),
        cli.ExitCode.REFUSED if done.returncode in (0, 3) else cli.ExitCode(
            done.returncode if done.returncode in (1, 2, 4) else 1),
        refusals=data.get("refusals", []), pre_run_check=True)


def _caffeinate() -> tuple[subprocess.Popen[bytes] | None, str]:
    """Keep the computer awake while this process runs. It ends when this process does."""
    if sys.platform != "darwin" or shutil.which("caffeinate") is None:
        return None, ("skipped: caffeinate is not on this computer, so nothing keeps it "
                      "awake during the run")
    proc = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return proc, "caffeinate -i holds the computer awake while the run goes"


def _first_command(paths: Paths, name: str) -> list[str]:
    return sessions.build_command(paths.run_dir(name) / "settings-check.json")


def handler(args: argparse.Namespace) -> dict[str, Any]:
    paths = _paths(args)
    name = args.run_name or time.strftime("run-%Y%m%d-%H%M%S", time.gmtime())
    try:
        paths.run_dir(name)
    except PathError as error:
        raise _fail(str(error), "run.py --run <letters, digits, . _ ->",
                    cli.ExitCode.USAGE) from error
    resuming = record.RunRecord.exists(paths, name)
    try:
        existing = record.RunRecord.load(paths, name) if resuming else None
    except record.RecordError as error:
        raise _fail(str(error), error.next_command) from error
    numbers = existing.numbers() if existing else _numbers(paths, args.pieces)
    if existing and args.pieces.strip() and args.pieces.strip().lower() not in ("ready", "all"):
        asked = sorted(int(w.lstrip("#")) for w in args.pieces.replace(",", " ").split()
                       if w.lstrip("#").isdigit())
        if asked != sorted(numbers):
            raise _fail(f"the run {name} holds pieces {numbers}, and --pieces names {asked}",
                        f"run.py --run {name} (it resumes its own pieces), or pick a new name")
    if not numbers:
        raise _fail("no piece is ready, so there is nothing to run",
                    "/shape a piece to ready, then run.py again")
    hub = github.GitHub(paths)
    loaded = _policy(paths)
    try:
        infos = engine.read_infos(paths, numbers, hub)
    except engine.EngineRefusal as error:
        raise _fail(str(error), error.next_command) from error
    module = _pre_run_module()
    free = module.free_memory_mb()
    count = plan.slots(free, floor_mb=int(loaded["min_free_memory_mb"]),
                       cap=int(loaded["builder_cap"]))
    try:
        made = plan.make_plan(infos, slots=count)
    except plan.PlanError as error:
        raise _fail(str(error), error.next_command) from error
    shown = {"run": name, "resuming": resuming, "pieces": numbers, "free_memory_mb": free,
             "plan": made.as_dict(),
             "titles": {str(i.number): i.title for i in infos},
             "areas": {str(i.number): sorted(i.areas) for i in infos}}
    if args.dry_run:
        return {**shown, "pre_run_check": "not run in a plan: run.py runs it before it starts"}

    # The pre-run check refuses a computer that nothing holds awake, so caffeinate starts first.
    awake, awake_line = _caffeinate()
    sys.stderr.write(awake_line + "\n")
    lock: record.Lock | None = None
    try:
        notices = _pre_run_check(paths, name, numbers, args, _first_command(paths, name))
        try:
            lock = record.acquire_lock(paths, name)
        except record.LockHeld as error:
            raise _fail(str(error), error.next_command, lock=True) from error
        run = existing or record.RunRecord.create(
            paths, name, numbers, attended=not args.unattended,
            merge_pre_approved=args.merge_pre_approved)
        run.set_run_status(record.RUNNING)
        run.data["starts"] = int(run.data.get("starts", 0)) + 1
        run.set_run_status(record.RUNNING, resumed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                      time.gmtime()))
        for line in [*notices, awake_line]:
            run.note(line)
        for number in run.numbers():
            info = next(i for i in infos if i.number == number)
            run.update(number, title=info.title, issue=info.issue)
        try:
            engined = engine.Engine(paths, name, run, loaded, infos, slot_count=count, hub=hub)
        except engine.EngineRefusal as error:
            raise _fail(str(error), error.next_command) from error
        saved: dict[signal.Signals, Any] = {}
        stops: tuple[signal.Signals, ...] = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
        for sig in stops:
            saved[sig] = signal.signal(sig, lambda *_: engined.request_stop())
        try:
            outcome = engined.run()
        except engine.EngineRefusal as error:
            raise _fail(str(error), error.next_command) from error
        finally:
            for sig, previous in saved.items():
                signal.signal(sig, previous)
    finally:
        if lock is not None:
            lock.release()
        if awake is not None:
            awake.terminate()
            awake.wait()
    result = {**shown, "status": outcome.status,
              "statuses": {str(n): run.status(n) for n in run.numbers()},
              "spend_usd": run.spend_total(), "summary": outcome.data.get("summary"),
              "notices": notices}
    if outcome.code != 0:
        raise cli.Failure(
            f"the run {name} is {outcome.status}" if outcome.code == 3
            else f"the run {name} ended with a problem: read the problems in its summary",
            next_command=outcome.next_command,
            code=cli.ExitCode.REFUSED if outcome.code == 3 else cli.ExitCode.FAILURE,
            data=result)
    result["next"] = outcome.next_command
    return result


def main(argv: list[str]) -> int:
    return cli.run(PROG, "Run the pieces the person picked, as a plain script.", setup, handler,
                   argv, changes_state=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
