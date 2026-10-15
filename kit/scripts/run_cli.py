#!/usr/bin/env python3
"""Command-line orchestration for the AI Loop Kit run."""
from __future__ import annotations

import argparse
import json
import signal
import sys
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import gate
import walkaway
from loopkit import GitHub, Refused, last_record, repo_root


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
    args = p.parse_args(argv)
    if args.verdict_kind or args.verdict_file:
        try:
            if not args.verdict_kind or not args.verdict_file:
                raise Refused("verdict check needs both kind and file", "pass --verdict-kind and --verdict-file")
            from review import _logged_verdict
            print(json.dumps(_logged_verdict(Path(args.verdict_file), args.verdict_kind), sort_keys=True))
            return 0
        except Refused as error:
            print(f"refused: {error.reason}", file=sys.stderr)
            print(f"next: {error.next_step}", file=sys.stderr)
            return 2
    root = repo_root(Path.cwd())
    gh = GitHub(root)
    if args.walk_away:
        checks = gate.doctor(gh, root, walk_away=True, agent=args.agent)
        for ok, what, fix in checks:
            print(f"{'ok  ' if ok else 'FAIL'} {what}")
            if fix:
                print(f"     next: {fix}")
        if not all(ok for ok, _, _ in checks):
            print("refused: walk-away pre-run check failed", file=sys.stderr)
            return 2
    started_at = datetime.now(timezone.utc)
    try:
        lock = api.acquire_lock(root)
        signal.signal(signal.SIGTERM, api._interrupt_handler)
        signal.signal(signal.SIGINT, api._interrupt_handler)
    except Refused as r:
        print(f"refused: {r.reason}", file=sys.stderr)
        print(f"next: {r.next_step}", file=sys.stderr)
        return 2
    results = []
    summary_results = []
    awake = walkaway.keep_awake(root) if args.walk_away else nullcontext()
    awake.__enter__()
    try:
        gate.ignore_loop_folder(root)
        removed_reviews = api.cleanup_interrupted_reviews(root)
        if removed_reviews:
            api.log("removed abandoned review " + "; ".join(removed_reviews))
        results.extend(api.recover_building(gh, root))
        gate.sync(gh, root)
        pieces = args.pieces or api.ready_pieces(gh, api.log)
        if not pieces:
            print("Nothing is ready. Shape a piece first.")
            return 0
        for n in pieces:
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
                results.append(result)
                if args.walk_away:
                    try:
                        state = gate.state_of(gh.issue(n))
                    except Exception:
                        state = "unknown"
                    summary_results.append(walkaway.piece_summary(root, n, result, state,
                                                                  started_at))
            except Refused as r:
                result = f"piece {n}: refused: {r.reason}" + (f" (next: {r.next_step})" if r.next_step else "")
                results.append(result)
                if args.walk_away:
                    summary_results.append(walkaway.piece_summary(root, n, result, "unchanged",
                                                                  started_at))
            except Exception as e:  # keep going with the other pieces
                result = f"piece {n}: stopped by an error: {e}"
                results.append(result)
                if args.walk_away:
                    summary_results.append(walkaway.piece_summary(root, n, result, "unknown",
                                                                  started_at))
        print("\nRun finished.")
        print("\n".join(results))
        return 0
    finally:
        if api.stop_requested(root):
            api.clear_stop(root)
        if args.walk_away:
            finished_at = datetime.now(timezone.utc)
            try:
                path = walkaway.write_summary(root, summary_results + [
                    result for result in results if not result.startswith("piece ")
                ], started_at, finished_at)
                summary = path.read_text()
                walkaway.post_summary(gh, summary,
                                      mention=any(marker in result for result in results
                                                  for marker in ("back to shaping", "Run paused",
                                                                 "refused", "stopped by an error")))
            except Exception as error:
                api.log(f"could not save or post the run summary: {error}")
        try:
            if args.walk_away:
                awake.__exit__(None, None, None)
        finally:
            api.release_lock(lock)
