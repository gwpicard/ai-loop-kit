"""Render the current run as a local page with all its data included."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from loopkit import GitHub, branch_name

_EVENT_WARNED: set[Path] = set()
_EVENT_OBSERVERS: dict[Path, Callable[[], None]] = {}


@contextmanager
def watch_run_events(root: Path, observer: Callable[[], None]):
    """Notify a local viewer after an event, only while its run is active."""
    previous = _EVENT_OBSERVERS.get(root)
    _EVENT_OBSERVERS[root] = observer
    try:
        yield
    finally:
        if previous is None:
            _EVENT_OBSERVERS.pop(root, None)
        else:
            _EVENT_OBSERVERS[root] = previous


def run_event(root: Path, event: str, piece: int | None = None,
              state: str = "", attempt: int = 0, reason: str = "") -> None:
    """Append public metadata only. Callers supply fixed event names and reasons."""
    try:
        path = root / ".loop" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                     "piece": piece, "event": event, "state": state,
                                     "attempt": attempt, "reason": reason}) + "\n")
    except OSError:
        if root not in _EVENT_WARNED:
            _EVENT_WARNED.add(root)
            print("warning: could not write .loop/events.jsonl", file=sys.stderr)

    if root in _EVENT_OBSERVERS:
        _EVENT_OBSERVERS[root]()


def render(root: Path, gh: GitHub, pieces=()) -> Path:
    path = root / ".loop" / "events.jsonl"
    events, notices = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("not an event")
        except ValueError:
            notices.append("Part of the event file could not be read.")
            continue
        if event.get("event") == "run-start":
            events = []
        events.append(event)
    latest = {number: {} for number in pieces}
    for event in events:
        if event.get("piece") is not None:
            latest[event["piece"]] = event
    rows = []
    for number, event in latest.items():
        title, state, link = f"Piece {number}", event.get("state", ""), ""
        try:
            issue = gh.issue(number)
            title = issue["title"]
            labels = [label[6:] for label in issue["labels"] if label.startswith("state:")]
            if event and labels != [state]:
                notices.append(f"Piece {number}: local events and GitHub labels disagree "
                               f"(page: {state}; GitHub: {', '.join(labels) or 'no state'}). "
                               "GitHub labels are the source of truth.")
            if not event:
                state = ", ".join(labels) or "Unknown"
            pr = gh.pr_for_branch(branch_name(number))
            url = (pr or {}).get("url", "")
            if urlsplit(url).scheme in ("http", "https"):
                link = f'<a href="{escape(url, quote=True)}">Pull request</a>'
        except Exception:
            notices.append(f"Piece {number}: could not check GitHub. Showing local events.")
        values = (number, title, state, event.get("attempt", 0), event.get("time", "Waiting"))
        rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values)
                    + f"<td>{link}</td></tr>")
    boundary = next((e["event"] for e in reversed(events)
                     if e.get("event") in ("run-start", "run-stop")), "")
    status = {"run-start": "Running", "run-stop": "Finished"}.get(boundary, "No run recorded")
    last = " | ".join(str(value) for value in events[-1].values()) if events else "None"
    warnings = "".join(f'<p role="alert">{escape(note)}</p>' for note in notices)
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5"><title>Run progress</title>
<style>
body {{font: 1rem Georgia, serif; margin: 2rem; color: #20382e; background: #f5f4ed}}
h1 {{font-size: 2.4rem; margin-bottom: .5rem}}
table, [role=alert] {{font: .9rem ui-monospace, monospace}}
caption {{text-align: left; padding: 1rem 0; font-weight: bold}}
table {{border-collapse: collapse; width: 100%; background: white}}
th, td {{padding: .7rem; text-align: left; border-bottom: 1px solid #ccc; overflow-wrap: anywhere}}
[role=alert] {{border: 2px solid #934900; padding: 1rem; background: #fff0cf}}
</style></head><body><h1>Run progress</h1><p>{status}</p>
<p>This page refreshes every five seconds. Times are in UTC.</p>{warnings}
<table><caption>Pieces in this run</caption><thead><tr>
<th>Piece</th><th>Title</th><th>State</th><th>Attempt</th><th>Last change</th><th>Pull request</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Last event</h2><p>{escape(last)}</p></body></html>
'''
    destination = path.with_name("dashboard.html")
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(page, encoding="utf-8")
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    from loopkit import repo_root
    project = repo_root(Path.cwd())
    print(render(project, GitHub(project)))
