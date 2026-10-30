#!/usr/bin/env python3
"""Command-line orchestration for the AI Loop Kit run."""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import agents
import base_check
import dashboard
import gate
import holds
import procs
import walkaway
from doctor import print_checks
from loopkit import (STATE_PREFIX, GitHub, Refused, last_record, loop_settings, refresh_main,
                     repo_root)

from extras import require_extras


def retry_conflict(gh: GitHub, root: Path, number: int) -> None:
    """Return a conflicting piece through the existing gates before retrying."""
    gate.move(gh, root, number, "shaping", reason_type="conflict",
              reason="conflicts with the base branch")
    gate.move(gh, root, number, "ready")


def final_pull_request(api, gh: GitHub, root: Path, results: list[str]) -> None:
    """Add the base branch's pull request into main to the results. It never stops a run."""
    try:
        line = api.final_pull_request(gh, root, results)
    except Exception as error:  # the pieces are built; report and finish
        line = f"could not open the final pull request: {error}"
    if line:
        results.append(line)


def record_pieces(root: Path, pieces: list[int], known: list[int]) -> list[int]:
    """Record the run's selection for the live view, and again when pieces join it.
    Returns every piece recorded so far. An empty selection writes nothing."""
    if not set(pieces) - set(known):
        return known
    gate.run_event(root, "run-pieces", pieces=list(pieces))
    return list(known) + [p for p in pieces if p not in known]


def start_detached(root: Path, argv: list[str],
                   command: Optional[list[str]] = None) -> tuple[int, Path]:
    """Start a run in its own session, so closing the caller does not end it."""
    holder = procs.lock_holder(root)
    if holder:
        raise Refused(f"another run is live (pid {holder})", "wait for it to finish")
    log = root / ".loop" / "logs" / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = command or [sys.executable, str(Path(__file__).with_name("run.py")), *argv]
    with log.open("ab") as out:
        child = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.STDOUT, start_new_session=True)
    print(f"Run started in the background (pid {child.pid}). Log: {log}")
    return child.pid, log


def choose_mode(args, gh: GitHub, root: Path, selected: list[int]) -> Optional[bool]:
    """True for a walk-away run, False for an attended one, None to refuse (`--walk-away`)."""
    if args.attended:
        return False
    ready = {n: last_record(gh.comments(n), "ready") or {} for n in selected}
    if not args.walk_away:
        needing = {n: r["risks"]["needs_services"] for n, r in ready.items()
                   if r.get("risks", {}).get("needs_services")}
        for n, services in needing.items():
            print(f"piece {n} needs services ({', '.join(services)}), so this run is attended.")
        if needing:
            return False
        print("Checking whether this run can walk away. This starts a short agent session.")
    checks = gate.doctor(gh, root, walk_away=True, agent=args.agent, pieces=selected)
    if args.walk_away:
        if not print_checks(checks):
            return None
    elif not all(ok for ok, _, _ in checks):
        print_checks([check for check in checks if not check[0]])
        print("Falling back to an attended run.")
        return False
    if any(agents.selected(root, args.agent or record.get("agent")) == "codex"
           for record in ready.values()):
        print("Note: the Codex backend is a preview.")
    return True


def main(argv: Optional[list[str]] = None, api=None) -> int:
    if api is None:
        import run as api
    p = argparse.ArgumentParser(prog="run.py", description=__doc__.split("\n\n")[0])
    p.add_argument("pieces", nargs="*", type=int)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--verdict-kind", choices=("judge-writer",))
    p.add_argument("--verdict-file")
    p.add_argument("--walk-away", action="store_true",
                   help="refuse to run unless the unattended sandbox checks pass")
    p.add_argument("--attended", action="store_true",
                   help="skip the unattended checks and run attended")
    p.add_argument("--detach", action="store_true",
                   help="start the run in its own session and return, logging to .loop/logs")
    p.add_argument("--keep-going", action="store_true",
                   help="also build pieces that become ready, or come back, during the run")
    p.add_argument("--agent", choices=("claude", "codex"),
                   help="override the ready record's non-interactive agent for this run")
    p.add_argument("--retry-conflict", type=int, metavar="PIECE",
                   help="move a conflicting piece through shaping and ready, then retry it")
    args = p.parse_args(argv)
    if args.verdict_kind or args.verdict_file:
        try:
            if not args.verdict_kind or not args.verdict_file:
                raise Refused("verdict check needs both kind and file", "pass --verdict-kind and --verdict-file")
            from review import _logged_verdict
            print(json.dumps(_logged_verdict(Path(args.verdict_file), args.verdict_kind), sort_keys=True))
            return 0
        except Refused as error:
            print(f"refused: {error.reason}\nnext: {error.next_step}", file=sys.stderr)
            return 2
    root = repo_root(Path.cwd())
    if args.detach:
        try:
            start_detached(root, [a for a in (sys.argv[1:] if argv is None else argv)
                                  if a != "--detach"])
            return 0
        except Refused as error:
            print(f"refused: {error.reason}\nnext: {error.next_step}", file=sys.stderr)
            return 2
    refresh_main(root)
    gh = GitHub(root)
    try:
        selected = args.pieces or ([args.retry_conflict] if args.retry_conflict is not None
                                  else [i["number"] for i in
                                        gh.issues_with_label(STATE_PREFIX + "ready")])
        if args.walk_away:
            require_extras(loop_settings(root), *(last_record(gh.comments(n), "ready") or {}
                                                 for n in selected))
    except Refused as error:
        print(f"refused: {error.reason}\nnext: {error.next_step}", file=sys.stderr)
        return 2
    if args.walk_away and args.attended:
        print("refused: --walk-away and --attended cannot be used together", file=sys.stderr)
        return 2
    walk_away = choose_mode(args, gh, root, selected)
    if walk_away is None:
        print("refused: walk-away pre-run check failed", file=sys.stderr)
        return 2
    started_at = datetime.now(timezone.utc)
    try:
        lock = api.acquire_lock(root)
        signal.signal(signal.SIGTERM, api._interrupt_handler)
        signal.signal(signal.SIGINT, api._interrupt_handler)
    except Refused as r:
        print(f"refused: {r.reason}\nnext: {r.next_step}", file=sys.stderr)
        return 2
    failed = False
    results = []
    summary_results = []
    awake = walkaway.keep_awake(root) if walk_away else nullcontext()
    pieces = list(args.pieces)
    page_warned = False

    def render_page():
        nonlocal page_warned
        if not (root / ".loop" / "events.jsonl").is_file():
            return
        try:
            dashboard.render(root, gh, pieces)
        except Exception:
            if not page_warned:
                print("warning: could not write .loop/dashboard.html", file=sys.stderr)
                page_warned = True

    watching = ExitStack()
    watching.enter_context(awake)
    watching.enter_context(dashboard.watch_run_events(root, render_page))
    print(f"Run page: {root / '.loop' / 'dashboard.html'}")
    try:
        gate.run_event(root, "run-start", reason="started")
        if args.retry_conflict is not None:
            try:
                retry_conflict(gh, root, args.retry_conflict)
            except Refused as error:
                print(f"refused: {error.reason}\nnext: {error.next_step}", file=sys.stderr)
                return 2
            args.pieces = [args.retry_conflict]
        gate.ignore_loop_folder(root)
        removed_reviews = api.cleanup_interrupted_reviews(root)
        if removed_reviews:
            api.log("removed abandoned review " + "; ".join(removed_reviews))
        results.extend(api.recover_building(gh, root))
        gate.sync(gh, root)
        pieces = args.pieces or api.ready_pieces(gh, api.log)
        recorded = record_pieces(root, pieces, [])
        initial = set(api.ready_pieces(gh, api.log)) if args.keep_going and args.pieces \
            else set(pieces)
        render_page()
        if not pieces:
            print("Nothing is ready. Shape a piece first.")
            final_pull_request(api, gh, root, results)
            print("\n".join(line for line in results if "final pull request" in line.lower()))
            return 0
        wants, pending, tried = holds.wanted(gh, pieces), list(pieces), {}
        handed_back: set[int] = set()
        rejoined: set[int] = set()

        def join_ready() -> bool:
            """Add pieces that became ready, or came back, since the run began."""
            nonlocal recorded
            found = [n for n in api.ready_pieces(gh, api.log) if n not in pending and (
                (n not in initial and n not in tried and n not in pieces)
                or (n in handed_back and n not in rejoined))]
            if not found:
                return False
            rejoined.update(n for n in found if n in tried)
            wants.update(holds.wanted(gh, found))
            pending.extend(found)
            pieces.extend(n for n in found if n not in pieces)
            recorded = record_pieces(root, [n for n in found if n not in recorded], recorded)
            render_page()
            return True

        while True:
            n, held = holds.pick(gh, pending, wants, tried) if pending else (None, {})
            if n is None:  # nothing is left, or every piece left waits for one not done
                if args.keep_going and not api.stop_requested(root) and join_ready():
                    continue
                results.extend(held.values())
                if walk_away:
                    summary_results.extend(walkaway.piece_summary(root, p, line, "ready", started_at)
                                           for p, line in held.items())
                break
            pending.remove(n)
            if api.stop_requested(root):
                api.log("stop requested; ending before the next piece")
                break
            first_ready = last_record(gh.comments(n), "ready")
            waiting = api.waiting_limit_note(gh, root, first_ready)
            if waiting:
                print(waiting)
                results.append(waiting)
                break
            try:
                try:
                    base_check.confirm(gh, root, n)
                except Refused as r:  # hand the piece back; the run carries on
                    result, state, failed = base_check.hand_back(gh, root, n, r), "shaping", True
                else:
                    result = api.build_piece(gh, root, n, args.attempts, walk_away, args.agent)
                    state = gate.state_of(gh.issue(n))
                    failed = state not in ("approval", "done") or failed
            except Refused as r:
                failed = True
                state = "unchanged"
                result = f"piece {n}: refused: {r.reason}" + (f" (next: {r.next_step})" if r.next_step else "")
            except Exception as e:  # keep going with the other pieces
                failed = True
                state = "unknown"
                result = f"piece {n}: stopped by an error: {e}"
            results.append(result)
            tried[n] = result
            if state == "shaping":
                handed_back.add(n)
            if walk_away:
                summary_results.append(walkaway.piece_summary(root, n, result, state, started_at))
        final_pull_request(api, gh, root, results)
        print("\nRun finished.\n" + "\n".join(results))
        return int(failed)
    finally:
        gate.run_event(root, "run-stop", reason="ended")
        if api.stop_requested(root):
            api.clear_stop(root)
        if walk_away:
            try:
                summary = walkaway.write_summary(root, summary_results + [
                    result for result in results if not result.startswith("piece ")
                ], started_at, datetime.now(timezone.utc)).read_text()
                walkaway.post_summary(gh, summary,
                                      mention=any(marker in result for result in results
                                                  for marker in walkaway.BLOCKERS))
            except Exception as error:
                api.log(f"could not save or post the run summary: {error}")
        try:
            watching.close()
        finally:
            api.release_lock(lock)
