"""Start a walk-away run for the pieces ticked on the dashboard.

`start` checks the pieces and the walk-away checks, then starts the detached run.
It writes nothing itself: the run's log is the only file.
"""
from __future__ import annotations

import gate
import holds
import procs
import run_cli
from loopkit import Refused, last_record


def ready_risks(gh, n: int) -> dict:
    """The risks frozen in a piece's ready record; empty when it cannot be read."""
    try:
        return (last_record(gh.comments(n), "ready") or {}).get("risks") or {}
    except Exception:  # GitHub could not answer
        return {}


def _refuse(status: int, error: str, **more) -> tuple[int, dict]:
    return status, {"error": error, **more}


def start(dash, body) -> tuple[int, dict]:
    """The HTTP status and JSON answer for a request to start a run."""
    pieces = body.get("pieces") if isinstance(body, dict) else None
    keep_going = body.get("keep_going", False) if isinstance(body, dict) else None
    if (not isinstance(pieces, list) or not pieces or len(set(pieces)) != len(pieces)
            or not all(type(n) is int and n > 0 for n in pieces)
            or not isinstance(keep_going, bool)):
        return _refuse(400, "pieces must be a non-empty list of different piece numbers, "
                            "and keep_going true or false")
    with dash.start_lock:
        if dash.starting:
            return _refuse(409, "another run is being started; wait for its checks to finish")
        dash.starting = True
    dash.publish()
    try:
        return _check_and_start(dash, pieces, keep_going)
    finally:
        dash.starting = False
        dash.publish()


def _check_and_start(dash, pieces: list[int], keep_going: bool) -> tuple[int, dict]:
    gh, root = dash.gh, dash.root
    states = {n: holds.state(gh, n) for n in pieces}
    wrong = [f"piece {n} is {s}, not ready" for n, s in states.items() if s != "ready"]
    if wrong:
        return _refuse(409, "; ".join(wrong))
    holder = procs.lock_holder(root)
    if holder:
        return _refuse(409, f"another run is live (pid {holder})", pid=holder)
    warnings = []
    for n in pieces:
        risks = ready_risks(gh, n)
        if risks.get("needs_services"):
            return _refuse(409, f"piece {n} needs services ({', '.join(risks['needs_services'])}), "
                                "so a walk-away run would refuse it")
        for d in risks.get("depends_on") or []:
            if d not in pieces and (found := holds.state(gh, d)) != "done":
                warnings.append(f"piece {n} depends on piece {d}, which is {found} and not "
                                f"ticked, so piece {n} will wait")
    try:
        checks = gate.doctor(gh, root, walk_away=True, pieces=pieces)
    except Exception as error:
        return _refuse(500, f"the walk-away checks could not run: {error}")
    if not all(ok for ok, _, _ in checks):
        return _refuse(409, "a walk-away check failed", checks=[
            {"ok": ok, "what": what, "next": fix} for ok, what, fix in checks])
    argv = ["--walk-away", *map(str, pieces), *(["--keep-going"] if keep_going else [])]
    try:
        pid, log = run_cli.start_detached(root, argv)
    except Refused as error:
        return _refuse(409, f"{error.reason}; {error.next_step}")
    return 202, {"pid": pid, "log": str(log), "warnings": warnings}
