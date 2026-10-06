"""The run record, the lock file, the heartbeat and the spend of one run.

The run record is `.agents/runs/<name>/run.json` (`Paths.run_record`). Only the run script
writes it. It says what is done, so a run that was killed and started again never redoes a
finished piece. Where the gate's record is ahead of it, the gate wins: the engine reads the
piece's state from the gate before it resumes a piece.

The file is written whole, to a new name, then renamed over the old one, so a reader never sees
half a record. A record that cannot be read is a refusal (`RecordError`), never an empty record.

The lock file holds the process number of the live run. A second copy of the same run is
refused. A lock whose process is gone is stale, and the next run takes it over.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop.paths import Paths

VERSION = 1

# Piece statuses.
PENDING = "pending"
BUILDING = "building"
PARKED_PERSON = "parked-needs-person"  # a question; an answer resumes it (P22)
WAITING_PERSON = "waiting-for-person"  # a GitHub step or a gate refusal only the person clears
WAITING = "waiting"  # never started: a slot, an area or a blocker held it all run
PARKED_SPEND = "parked-spend"
STOPPED = "stopped"  # a stop signal sent it back to ready; the branch is kept
BUILT = "built"
SENT_BACK = "sent-back"  # back to shaping (move 3 or 6)
RETURNED = "returned-ready"  # back to ready (move 7)
STATUSES = (
    PENDING, BUILDING, PARKED_PERSON, WAITING_PERSON, WAITING, PARKED_SPEND, STOPPED, BUILT,
    SENT_BACK, RETURNED,
)
# What a run started again does with each status. Finished work is never redone.
RESUMABLE = (PENDING, BUILDING, WAITING, WAITING_PERSON, PARKED_SPEND, STOPPED)

# Run statuses.
RUNNING = "running"
FINISHED = "finished"
RUN_STOPPED = "stopped"
RUN_PARKED = "parked"


class RecordError(Exception):
    """A record, lock or heartbeat that cannot be used. The message names the next command."""

    def __init__(self, message: str, next_command: str = "") -> None:
        super().__init__(message)
        self.next_command = next_command


class LockHeld(RecordError):
    """Another copy of the run holds the lock."""


def _now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunRecord:
    """One run's record, in memory and on disk. Safe to use from several threads."""

    def __init__(self, paths: Paths, name: str, data: dict[str, Any]) -> None:
        self.paths = paths
        self.name = name
        self.data = data
        self._lock = threading.RLock()

    # --- making and reading ----------------------------------------------------------

    @classmethod
    def exists(cls, paths: Paths, name: str) -> bool:
        return paths.run_record(name).is_file()

    @classmethod
    def create(
        cls,
        paths: Paths,
        name: str,
        numbers: Sequence[int],
        *,
        attended: bool,
        merge_pre_approved: bool,
    ) -> RunRecord:
        data: dict[str, Any] = {
            "version": VERSION,
            "run": name,
            "started": _now_text(),
            "status": RUNNING,
            "attended": bool(attended),
            "merge_pre_approved": bool(merge_pre_approved),
            "order": [int(n) for n in numbers],
            "pieces": {str(int(n)): {"status": PENDING} for n in numbers},
            "spend_usd": 0.0,
            "decisions": [],
            "notes": [],
            "problems": [],
            "starts": 0,
        }
        record = cls(paths, name, data)
        record.save()
        return record

    @classmethod
    def load(cls, paths: Paths, name: str) -> RunRecord:
        path = paths.run_record(name)
        again = f"fix or move {path}, then run.py --run {name} again"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise RecordError(
                f"the run record {path} cannot be read ({error.strerror})", again
            ) from error
        try:
            data = json.loads(text)
        except ValueError as error:
            raise RecordError(f"the run record {path} is not JSON ({error})", again) from error
        if (
            not isinstance(data, dict)
            or data.get("version") != VERSION
            or not isinstance(data.get("pieces"), dict)
            or not isinstance(data.get("order"), list)
        ):
            raise RecordError(f"the run record {path} does not have the shape of a run record",
                              again)
        for number, piece in data["pieces"].items():
            if not isinstance(piece, dict) or piece.get("status") not in STATUSES:
                raise RecordError(
                    f"the run record {path} holds a piece {number} with no known status", again
                )
        return cls(paths, name, data)

    def save(self) -> None:
        with self._lock:
            path = self.paths.run_record(self.name)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(f"run.json.{os.getpid()}.{threading.get_ident()}.tmp")
            temp.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
            os.replace(temp, path)

    # --- the pieces ------------------------------------------------------------------

    def numbers(self) -> list[int]:
        return [int(n) for n in self.data["order"]]

    def piece(self, number: int) -> dict[str, Any]:
        found: dict[str, Any] = self.data["pieces"][str(int(number))]
        return found

    def status(self, number: int) -> str:
        return str(self.piece(number)["status"])

    def with_status(self, *statuses: str) -> list[int]:
        return [n for n in self.numbers() if self.status(n) in statuses]

    def resumable(self) -> list[int]:
        return self.with_status(*RESUMABLE)

    def set_status(self, number: int, status: str, **fields: Any) -> None:
        if status not in STATUSES:
            raise ValueError(f"{status!r} is not a piece status")
        with self._lock:
            piece = self.piece(number)  # KeyError for a piece that is not in the run
            piece["status"] = status
            piece.update(fields)
            if status not in (WAITING_PERSON, PARKED_PERSON, PARKED_SPEND, WAITING):
                piece.pop("next", None)
            piece["at"] = _now_text()
            self.save()

    def update(self, number: int, **fields: Any) -> None:
        with self._lock:
            self.piece(number).update(fields)
            self.save()

    # --- the run ---------------------------------------------------------------------

    def set_run_status(self, status: str, **fields: Any) -> None:
        with self._lock:
            self.data["status"] = status
            self.data.update(fields)
            self.save()

    def note(self, text: str) -> None:
        with self._lock:
            self.data["notes"].append({"at": _now_text(), "text": text})
            self.save()

    def problem(self, text: str) -> None:
        with self._lock:
            self.data["problems"].append({"at": _now_text(), "text": text})
            self.save()

    def add_decision(self, number: int | None, by: str, text: str) -> None:
        """A decision made alone: by a builder, or by the run script."""
        with self._lock:
            self.data["decisions"].append(
                {"piece": number, "by": by, "text": text, "at": _now_text()}
            )
            self.save()

    # --- spend -----------------------------------------------------------------------

    def add_spend(self, number: int, usd: float) -> None:
        if usd < 0:
            raise ValueError(f"spend cannot be negative, and {usd} is")
        with self._lock:
            piece = self.piece(number)
            piece["spend_usd"] = float(piece.get("spend_usd", 0.0)) + usd
            self.data["spend_usd"] = float(self.data.get("spend_usd", 0.0)) + usd
            self.save()

    def add_tokens(self, number: int, tokens: Mapping[str, int]) -> None:
        with self._lock:
            held: dict[str, int] = self.piece(number).setdefault("tokens", {})
            for key, value in tokens.items():
                held[key] = held.get(key, 0) + int(value)
            self.save()

    def spend_piece(self, number: int) -> float:
        return float(self.piece(number).get("spend_usd", 0.0))

    def spend_total(self) -> float:
        return float(self.data.get("spend_usd", 0.0))

    def cap_reached(
        self, *, per_piece: float | None, per_run: float | None, piece: int
    ) -> str | None:
        """Text naming the cap that is reached, or None. A cap is reached at the cap itself."""
        total = self.spend_total()
        if per_run is not None and total >= per_run - 1e-9:
            return (f"the run has spent ${total:.2f}, and the cap for the run is "
                    f"${per_run:.2f}")
        spent = self.spend_piece(piece)
        if per_piece is not None and spent >= per_piece - 1e-9:
            return (f"piece {piece} has spent ${spent:.2f}, and the cap for a piece is "
                    f"${per_piece:.2f}")
        return None


# --- the lock --------------------------------------------------------------------------


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class Lock:
    path: Path
    pid: int

    def release(self) -> None:
        """Remove the lock, but only when it still holds this process's number."""
        try:
            held = self.path.read_text(encoding="utf-8").split()
        except OSError:
            return
        if held and held[0] == str(self.pid):
            with contextlib.suppress(OSError):
                self.path.unlink()


def acquire_lock(paths: Paths, name: str, *, pid: int | None = None) -> Lock:
    """Take the run's lock, or raise `LockHeld`. A lock of a dead process is taken over."""
    mine = os.getpid() if pid is None else pid
    path = paths.lock_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    again = f"run.py --run {name}"
    for _ in range(3):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                held = path.read_text(encoding="utf-8").split()
            except OSError as error:
                raise LockHeld(f"the lock {path} cannot be read ({error.strerror})",
                               f"check {path}, then {again}") from error
            if not held or not held[0].isdigit():
                raise LockHeld(
                    f"the lock {path} holds no process number, so it cannot be told from a "
                    "live one", f"look at {path}; when no run is live, move it aside, then "
                    f"{again}") from None
            other = int(held[0])
            if other == mine or _alive(other):
                raise LockHeld(f"the run {name} is live: process {other} holds {path}",
                               "wait for that run to finish, or stop it by its process "
                               f"number, then {again}") from None
            # A stale lock: move it aside under a new name, and try again.
            stale = path.with_name(f"lock.stale-{other}-{int(time.time())}")
            with contextlib.suppress(OSError):
                os.replace(path, stale)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{mine}\n")
        return Lock(path, mine)
    raise LockHeld(f"the lock {path} would not settle", f"check {path}, then {again}")


# --- the heartbeat ---------------------------------------------------------------------


def beat(paths: Paths, name: str, *, now: float | None = None) -> None:
    """Write the heartbeat: the time and the process. The watch reads its age."""
    path = paths.heartbeat(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.time() if now is None else now
    temp = path.with_name(f"heartbeat.{os.getpid()}.tmp")
    temp.write_text(json.dumps({"pid": os.getpid(), "at": stamp}) + "\n", encoding="utf-8")
    os.replace(temp, path)


def heartbeat_age(paths: Paths, name: str, *, now: float | None = None) -> float | None:
    """Seconds since the last heartbeat, or None when there is none or it cannot be read."""
    try:
        data = json.loads(paths.heartbeat(name).read_text(encoding="utf-8"))
        at = float(data["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (time.time() if now is None else now) - at
