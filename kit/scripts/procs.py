"""Process state shared by the run entry point and its imported helpers."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

_ACTIVE_GROUPS: set[int] = set()
_RUN_LOCK_PATH: Optional[Path] = None
_MAIN_REF_CACHE: Optional[dict[str, str]] = None


class AttemptIdle(Exception):
    pass


def cache_main_ref_for_piece() -> None:
    global _MAIN_REF_CACHE
    _MAIN_REF_CACHE = {}


def clear_main_ref_for_piece() -> None:
    global _MAIN_REF_CACHE
    _MAIN_REF_CACHE = None


def main_ref_cache() -> Optional[dict[str, str]]:
    return _MAIN_REF_CACHE


def lock_path(root: Path) -> Path:
    return root / ".loop" / "run.lock"


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _write_lock_groups() -> None:
    if not _RUN_LOCK_PATH or not _RUN_LOCK_PATH.is_file():
        return
    try:
        data = json.loads(_RUN_LOCK_PATH.read_text())
    except (ValueError, OSError):
        return
    data["children"] = sorted(_ACTIVE_GROUPS)
    _RUN_LOCK_PATH.write_text(json.dumps(data) + "\n")


def track_process(proc: subprocess.Popen, root: Optional[Path] = None) -> None:
    global _RUN_LOCK_PATH
    if root is not None:
        _RUN_LOCK_PATH = lock_path(root)
    _ACTIVE_GROUPS.add(proc.pid)
    _write_lock_groups()


def _untrack_process(proc: subprocess.Popen) -> None:
    _ACTIVE_GROUPS.discard(proc.pid)
    _write_lock_groups()


def kill_active_processes() -> bool:
    groups = list(_ACTIVE_GROUPS)
    for pgid in groups:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and any(process_group_alive(pgid) for pgid in groups):
        time.sleep(0.02)
    for pgid in groups:
        if process_group_alive(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        _ACTIVE_GROUPS.discard(pgid)
    _write_lock_groups()
    return bool(groups)


def acquire_lock(root: Path) -> Path:
    """Create the run lock, taking over only when its recorded process is dead."""
    from loopkit import Refused

    path = lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    global _RUN_LOCK_PATH
    data = json.dumps({"pid": os.getpid(), "started_at": time.time(), "children": []}) + "\n"
    for _ in range(2):
        try:
            with path.open("x") as f:
                f.write(data)
            _RUN_LOCK_PATH = path
            return path
        except FileExistsError:
            try:
                current = json.loads(path.read_text())
                pid = int(current["pid"])
            except (ValueError, KeyError, TypeError, OSError):
                current = {}
                pid = 0
            if pid and process_alive(pid):
                raise Refused(f"another run is live (pid {pid})", "wait for it to finish")
            groups = [int(value) for value in current.get("children", [])
                      if str(value).isdigit()]
            if any(process_group_alive(group) for group in groups):
                raise Refused("an orphan builder or reviewer from the previous run is still alive",
                              "stop that process group, then run again")
            path.unlink(missing_ok=True)
    raise Refused("could not take the run lock", "check .loop/run.lock and try again")


def release_lock(path: Path) -> None:
    path.unlink(missing_ok=True)
    global _RUN_LOCK_PATH
    if _RUN_LOCK_PATH == path:
        _RUN_LOCK_PATH = None
