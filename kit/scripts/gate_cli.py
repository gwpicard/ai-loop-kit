"""Command-line parsing and dispatch for the gate."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loopkit import REASON_TYPES, STATES, GitHub, Refused, repo_root


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gate.py",
        description="The gate: the only code that moves a piece from one state to another.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("capture")
    c.add_argument("--title", required=True)
    c.add_argument("--body-file", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("n", type=int)
    m = sub.add_parser("move")
    m.add_argument("n", type=int)
    m.add_argument("to", choices=STATES)
    m.add_argument("--reason", default="")
    m.add_argument("--type", dest="reason_type", choices=REASON_TYPES, default="")
    s = sub.add_parser("spec")
    s.add_argument("n", type=int)
    s.add_argument("--body-file", required=True)
    sub.add_parser("sync")
    sub.add_parser("status")
    d = sub.add_parser("doctor")
    d.add_argument("--quality-command", action="append", default=[],
                   help="also dry-run this proposed Quality command on fresh main")
    d.add_argument("--prepare-command",
                   help="use this proposed Prepare command for doctor dry-runs")
    d.add_argument("--test-command",
                   help="use this proposed Test command for doctor dry-runs")
    d.add_argument("--walk-away", action="store_true",
                   help="also check the active sandbox and unattended-run prerequisites")
    sub.add_parser("report")
    sub.add_parser("stop")
    return p


def main(argv: list[str] | None = None, api=None) -> int:
    if api is None:
        import gate as api
    args = build_parser().parse_args(argv)

    root = repo_root(Path.cwd())
    gh = GitHub(root)
    try:
        if args.cmd == "init":
            api.init(gh, root)
            print("ok: labels made, .loop/ ignored locally")
        elif args.cmd == "capture":
            n = api.capture(gh, args.title, Path(args.body_file).read_text())
            print(f"ok: captured piece {n} in shaping")
        elif args.cmd == "check":
            issue = gh.issue(args.n)
            rec = api.check_ready(gh, root, issue)
            print(f"ok: piece {args.n} would pass the ready gate (bar {rec['bar'][:12]})")
        elif args.cmd == "move":
            print("ok: " + api.move(gh, root, args.n, args.to, args.reason,
                                  args.reason_type))
        elif args.cmd == "spec":
            api.replace_spec(gh, args.n, Path(args.body_file).read_text())
            print(f"ok: piece {args.n} spec replaced")
        elif args.cmd == "sync":
            print("\n".join(api.sync(gh, root)) or "ok: nothing merged since the last sync")
        elif args.cmd == "status":
            print(api.status(gh, root))
        elif args.cmd == "doctor":
            checks = api.doctor(gh, root, args.quality_command,
                            args.prepare_command, args.test_command, args.walk_away)
            for ok, what, fix in checks:
                print(f"{'ok  ' if ok else 'FAIL'} {what}")
                if fix:
                    print(f"     next: {fix}")
            if not all(ok for ok, _, _ in checks):
                return 2
        elif args.cmd == "report":
            print(api.report(gh))
        elif args.cmd == "stop":
            print("ok: " + api.request_stop(root))
    except Refused as r:
        print(f"refused: {r.reason}", file=sys.stderr)
        if r.next_step:
            print(f"next: {r.next_step}", file=sys.stderr)
        return 2
    return 0
