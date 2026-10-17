"""Shared agent session execution and activity clocks."""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Callable, Optional

import agents
import sandbox
from procs import _untrack_process, track_process


def _pump_session(proc: subprocess.Popen, out, idle_seconds: int,
                  hard_seconds: int = 40 * 60,
                  activity_path: Optional[Path] = None,
                  result_event: Optional[dict] = None,
                  backend: str = "claude",
                  clock: Optional[Callable[[], float]] = None,
                  event_log=None) -> str:
    """Copy output to a log and stop a silent or overlong process group."""
    now_seconds = clock if clock is not None else time.monotonic
    assert proc.stdout is not None
    stream = proc.stdout
    os.set_blocking(stream.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)
    started = last_output = now_seconds()
    last_stamp = _folder_activity_stamp(activity_path) if activity_path else 0.0
    next_activity_check = started + 2
    pending = ""
    eof = False
    reason = ""
    parent_exit_deadline: Optional[float] = None
    orphaned_child = False
    while not eof or proc.poll() is None:
        now = now_seconds()
        if proc.poll() is not None and not eof:
            if parent_exit_deadline is None:
                parent_exit_deadline = now + 3
            elif now >= parent_exit_deadline:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                orphaned_child = True
                break
        if activity_path and now >= next_activity_check:
            stamp = _folder_activity_stamp(activity_path)
            next_activity_check = now + 2
            if stamp > last_stamp:
                last_stamp = stamp
                last_output = now
        if proc.poll() is None and not reason:
            if now - started >= hard_seconds:
                reason = "hard"
            elif now - last_output >= idle_seconds:
                reason = "idle"
            if reason:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        timeout = 0.1
        if proc.poll() is None and not reason:
            timeout = min(timeout, max(0.0, min(hard_seconds - (now - started),
                                                idle_seconds - (now - last_output))))
        elif parent_exit_deadline is not None and not eof:
            timeout = min(timeout, max(0.0, parent_exit_deadline - now))
        events = selector.select(timeout)
        for key, _ in events:
            try:
                chunk = os.read(key.fd, 4096)
            except BlockingIOError:
                continue
            if not chunk:
                eof = True
                selector.unregister(stream)
                continue
            if event_log is not None:
                event_log.write(chunk)
                event_log.flush()
            pending += chunk.decode(errors="replace")
            lines = pending.split("\n")
            pending = lines.pop()
            for line in lines:
                if result_event is not None:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        event = None
                    if isinstance(event, dict) and event.get("type") == "result":
                        result_event.update(event)
                out.write(agents.log_line(line, backend))
            out.flush()
            last_output = now_seconds()
    if pending:
        out.write(agents.log_line(pending, backend))
    proc.wait()
    _untrack_process(proc)
    selector.close()
    stream.close()
    if reason:
        out.write("\nAttempt stopped after idle limit with no output.\n" if reason == "idle"
                  else f"\nThe attempt ran past {hard_seconds // 60} minutes and was stopped.\n")
    if orphaned_child:
        out.write("\nStopped a child process that kept the session pipe open after its parent exited.\n")
    return reason


def _folder_activity_stamp(folder: Optional[Path]) -> float:
    """Newest useful modification time under the build folder."""
    if folder is None:
        return 0.0
    newest = folder.stat().st_mtime if folder.exists() else 0.0
    for current, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in {
            ".git", ".venv", "node_modules", "dist", "build", "__pycache__"}]
        for name in (*dirs, *files):
            try:
                newest = max(newest, (Path(current) / name).stat().st_mtime)
            except OSError:
                continue
    return newest


def run_session(folder: Path, prompt: str, logfile: Path, idle_seconds: int, *,
                role: str, backend: str = "claude", append_log: bool = False,
                result_event: dict | None = None, raw_events: Path | None = None,
                process_record: Path | None = None,
                on_wait: Callable[[int], None] | None = None, **launch_options) -> str:
    """Run a session with explicit evidence and an optional single usage retry."""
    for retry in range(2 if on_wait else 1):
        mode = "a" if append_log or retry else "w"
        events = raw_events.open(mode + "b") if raw_events else nullcontext()
        with logfile.open(mode) as out, events as event_log:
            proc = agents.start_session(backend, prompt, folder, role=role, **launch_options)
            track_process(proc)
            if process_record is not None:
                with process_record.open("a") as evidence:
                    evidence.write(f"{proc.pid}\n")
            status = _pump_session(proc, out, idle_seconds, activity_path=folder,
                                   result_event=result_event, backend=backend, event_log=event_log)
        if not launch_options.get("walk_away") or not sandbox.usage_limit_event(result_event):
            return status
        if retry or on_wait is None:
            return "usage-limit"
        seconds = sandbox.reset_wait_seconds(result_event)
        on_wait(seconds)
        time.sleep(seconds)
        result_event = {}
