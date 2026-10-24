#!/usr/bin/env python3
"""Command-line orchestration for the AI Loop Kit run."""
from __future__ import annotations

import argparse
import json
import signal
import sys
from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import dashboard
import gate
import holds
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


def main(argv: Optional[list[str]] = None, api=None) -> int:
    if api is None:
        import run as api
    p = argparse.ArgumentParser(prog="run.py", description=__doc__.split("\n\n")[0])
    p.add_argument("pieces", nargs="*", type=int)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--verdict-kind", choices=("judge-writer",))
    p.add_argument("--verdict-file")
    p.add_argument("--walk-away", action="store_true",
                   help="run only after the unattended sandbox checks pass")
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
    refresh_main(root)
    gh = GitHub(root)
    if args.walk_away:
        try:
            selected = args.pieces or ([args.retry_conflict] if args.retry_conflict is not None
                                      else [i["number"] for i in
                                            gh.issues_with_label(STATE_PREFIX + "ready")])
            require_extras(loop_settings(root), *(last_record(gh.comments(n), "ready") or {}
                                                 for n in selected))
        except Refused as error:
            print(f"refused: {error.reason}\nnext: {error.next_step}", file=sys.stderr)
            return 2
        if not print_checks(gate.doctor(gh, root, walk_away=True, agent=args.agent)):
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
    awake = walkaway.keep_awake(root) if args.walk_away else nullcontext()
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
        render_page()
        if not pieces:
            print("Nothing is ready. Shape a piece first.")
            final_pull_request(api, gh, root, results)
            print("\n".join(line for line in results if "final pull request" in line.lower()))
            return 0
        wants, pending, tried = holds.wanted(gh, pieces), list(pieces), {}
        while pending:
            n, held = holds.pick(gh, pending, wants, tried)
            if n is None:  # every piece left waits for one that is not done
                results.extend(held.values())
                if args.walk_away:
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
                result = api.build_piece(gh, root, n, args.attempts, args.walk_away,
                                         args.agent)
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
            if args.walk_away:
                summary_results.append(walkaway.piece_summary(root, n, result, state, started_at))
        final_pull_request(api, gh, root, results)
        print("\nRun finished.\n" + "\n".join(results))
        return int(failed)
    finally:
        gate.run_event(root, "run-stop", reason="ended")
        if api.stop_requested(root):
            api.clear_stop(root)
        if args.walk_away:
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
