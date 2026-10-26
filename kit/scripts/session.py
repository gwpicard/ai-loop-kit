"""Shared agent session execution and activity clocks."""
from __future__ import annotations
if __name__ == "__main__":
    import kit_python
    kit_python.require()

import json
import os
import re
import selectors
import signal
import subprocess
import time
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Callable, Optional

import agents
import sandbox
from loopkit import Refused, bar_hash_in, sh, untracked_paths
from procs import _untrack_process, track_process

_JUDGE_CACHE = re.compile(
    r"(^|/)(__pycache__|\.(pytest_cache|benchmarks|hypothesis|mypy_cache|ruff_cache))/")
# Ignored installed packages, where Node test tools such as Vitest keep their caches.
_JUDGE_PACKAGES = re.compile(r"(^|/)node_modules/")


def _judge_untracked(folder: Path, files: list[str]) -> dict:
    """Record unapproved untracked files without following symbolic links."""
    ignored = sh(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
                 folder).stdout.split("\0")
    skip = {name for name in ignored if _JUDGE_PACKAGES.search(name)}
    return {name: ((path := folder / name).lstat().st_mode,
                   os.readlink(path) if path.is_symlink() else bar_hash_in(folder, [name]))
            for name in untracked_paths(folder) - set(files) - skip
            if not _JUDGE_CACHE.search(name)}


def _judge_dirty(folder: Path) -> bool:
    """Ignore uncommitted tool cache folders when checking work."""
    status = sh(["git", "status", "--porcelain", "--no-renames", "-z",
                 "--untracked-files=all"], folder).stdout
    return any(not entry[3:].startswith(".loop/") and not _JUDGE_CACHE.search(entry[3:])
               for entry in status.split("\0") if entry)


def _judge_start(folder: Path, data: dict) -> tuple:
    """Check the approved write paths and preserve a clean piece baseline."""
    files = data["Files"].splitlines()
    root = folder.resolve()
    if not files or len(files) != len(set(files)) or any(
            not name.strip() or Path(name).is_absolute() or ".." in Path(name).parts
            or not (root / name).resolve().is_relative_to(root) for name in files):
        raise ValueError("judge-writer Files must name exact paths inside the project")
    branch = sh(["git", "branch", "--show-current"], folder).stdout.strip()
    if not re.fullmatch(r"piece/[1-9]\d*", branch):
        raise ValueError("judge-writer requires the piece/<n> branch")
    if _judge_dirty(folder):
        raise ValueError("judge-writer requires a clean working tree; keep existing work")
    return (files, branch, sh(["git", "rev-parse", "HEAD"], folder).stdout.strip(),
            _judge_untracked(folder, files))


def _judge_finish(folder: Path, baseline: tuple, verdict: dict) -> None:
    """Accept only declared judge changes, then commit them on the piece branch."""
    files, branch, base, before = baseline
    if sh(["git", "branch", "--show-current"], folder).stdout.strip() != branch:
        raise ValueError("judge-writer changed the piece branch")
    changed = sh(["git", "diff", "--name-only", "--no-renames", "-z", base], folder).stdout
    committed = sh(["git", "log", "--format=", "--name-only", "--no-renames", "-z",
                    f"{base}..HEAD"], folder).stdout
    untracked = _judge_untracked(folder, files)
    altered = {name for name in before.keys() | untracked.keys()
               if before.get(name) != untracked.get(name)}
    unexpected = {name for name in changed.split("\0") if name and not _JUDGE_CACHE.search(name)}
    unexpected = (unexpected | altered | set(committed.split("\0"))) - {"", *files}
    reported = verdict["judge_files"]
    unexpected |= set(reported) - set(files)
    if unexpected:
        path = sorted(unexpected)[0]
        raise Refused("judge-writer wrote or reported paths outside the approved Exit Files: "
                      + path,
                      f"inspect {path} against the approved Exit Files; keep the work in shaping")
    if not reported:
        raise ValueError("judge-writer reported no approved Exit Files")
    if any(not (folder / name).is_file() or
           not (folder / name).resolve().is_relative_to(folder.resolve()) for name in files):
        raise ValueError("judge-writer must produce the approved Exit Files inside the project")
    sh(["git", "add", "--", *files], folder)
    if sh(["git", "diff", "--cached", "--quiet", "--", *files],
          folder, check=False).returncode:
        sh(["git", "commit", "--only", "-m", "Write the approved judge", "--", *files], folder)
    if _judge_dirty(folder) or _judge_untracked(folder, files) != before:
        raise ValueError("judge-writer left uncommitted work; keep it for shaping")


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
                with suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
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
                with suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
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
                out.write(agents.log_line(line, backend, result_event))
            out.flush()
            last_output = now_seconds()
    if pending:
        out.write(agents.log_line(pending, backend, result_event))
    returncode = proc.wait()
    _untrack_process(proc)
    selector.close()
    stream.close()
    if reason:
        out.write("\nAttempt stopped after idle limit with no output.\n" if reason == "idle"
                  else f"\nThe attempt ran past {hard_seconds // 60} minutes and was stopped.\n")
    if orphaned_child:
        out.write("\nStopped a child process that kept the session pipe open after its parent exited.\n")
    return reason or (f"exit {returncode}" if returncode else "")


def _folder_activity_stamp(folder: Optional[Path]) -> float:
    """Newest useful modification time under the build folder."""
    if folder is None:
        return 0.0
    newest = folder.stat().st_mtime if folder.exists() else 0.0
    for current, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in {
            ".git", ".venv", "node_modules", "dist", "build", "__pycache__"}
                   and not (d == "cache" and Path(current).name == ".loop")]
        for name in (*dirs, *files):
            with suppress(OSError):
                newest = max(newest, (Path(current) / name).stat().st_mtime)
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


def main() -> int:
    """Run one shaping capability with approved JSON input and checked output."""
    import argparse

    from research import parse_research
    from review import _last_verdict

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--role", choices=tuple(agents.CAPABILITIES), required=True)
    parser.add_argument("--agent", choices=("claude", "codex"))
    for name in ("input", "output", "folder"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text())
        fields, tools, output = agents.CAPABILITIES[args.role]
        if isinstance(data, dict) and "Contract" in data and not isinstance(data["Contract"], str):
            raise Refused("Contract must be a string",
                          "encode Contract as one JSON string, using \\n between items")
        if not isinstance(data, dict) or set(data) != set(fields) or any(
                not isinstance(data[key], str) or (key != "Approach" and not data[key].strip())
                for key in fields):
            raise ValueError(f"{args.role} input requires only: {', '.join(fields)}")
        prompt = (agents.KIT / "briefs" / f"{args.role}.md").read_text()
        prompt += "\n\n" + json.dumps(data) + f"\nReturn {output}."
        baseline = _judge_start(args.folder, data) if args.role == "judge-writer" else None
        log = args.output.with_suffix(".log")
        events = log.with_suffix(".jsonl")
        result = {}
        backend = agents.selected(args.folder, args.agent)
        if args.role == "judge-writer":
            os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
            os.environ["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
        status = run_session(args.folder, prompt, log, 300, role=args.role,
                             backend=backend, result_event=result, raw_events=events)
        status = status or (agents.environment_evidence(log) if args.role == "researcher" else "")
        text = agents.event_text(events.read_text(), backend)
        if status or result.get("is_error") or result.get("type") == "turn.failed":
            raise ValueError(f"{args.role} requires {tools}: {status or result}; see {log}")
        if args.role == "judge-writer":
            _judge_finish(args.folder, baseline, _last_verdict(text, args.role))
        else:
            findings, gaps = parse_research(text.splitlines())
            if gaps or not findings:
                raise ValueError(f"researcher requires web-search and web-open: {gaps or text}")
        args.output.write_text(text)
        return 0
    except (OSError, ValueError, RuntimeError, Refused) as error:
        next_step = (error.next_step if isinstance(error, Refused) else
                     "restore the capability; leave the piece in shaping")
        parser.exit(2, f"refused: {error}\nnext: {next_step}\n")


if __name__ == "__main__":
    raise SystemExit(main())
