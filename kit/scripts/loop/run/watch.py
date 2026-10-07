"""The watch: stuck detection, usage limits and the real stops of a run.

The run script sees what a builder prints, so it can tell a clearly stuck attempt from a slow
one. There are no idle timers, because an idle timer kills an agent that waits on a long build.
Three patterns mean stuck, and nothing else does:

- the same error three times in a row;
- the same change undone and redone, read from the piece's folder: a state it had, then
  another, then the first again, then the second again;
- a test run past its hard timeout (the judge and the builder's own tool both say so).

A stuck attempt is stopped, and it counts as an attempt, through the gate: the engine gives the
branch to move 5, and the gate's attempt log is the only count. A usage-limit message is not
stuck and counts for nothing: the piece waits for the reset and goes on from the same place.
The module keeps no count of attempts.

The module also watches the run as a whole. These are real stops. Each notifies once (a line on
standard error and a note in the run record, until the notifications exist), and the run carries
on with the work that does not depend on them:

- two environment failures in a row, on different pieces;
- the same refused command in two pieces (the command log says which);
- the same failure in several pieces (`SEVERAL`).

The engine calls `run_hook` for the events, `session_started` when a builder session starts,
`on_output` for each line the builder prints, and `assess_session` when the session has ended.
A fault that stops the watch (a folder that cannot be read, a log that cannot be read) is a note
in the run record. It is never a quiet pass.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop import attempt_log, moves, sessions
from loop.paths import Paths

SAME_ERROR_TIMES = 3
SEVERAL = 3  # pieces that share one failure
DIGEST_SECONDS = 5.0  # how often the worktree of a building piece is read
COMMAND_LOG_ROWS = 4000
FAILED_OUTCOMES = ("blocked-by-environment", "gave-up")  # hand-offs whose words name a failure

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_ERROR = re.compile(r"(?i)\b\w*(?:error|exception)\b|\b(?:failed|failure|traceback|fatal|denied)\b"
                    r"|\bnot found\b|\bcannot\b")
_USAGE = re.compile(
    r"(?i)usage limit (?:reached|exceeded)"
    r"|(?:5-hour|five-hour|weekly|daily|session|monthly) limit (?:reached|exceeded|hit)"
    r"|you(?:'ve| have) (?:hit|reached) your (?:usage |rate )?limit"
    r"|rate limit (?:reached|exceeded)|out of (?:extra )?usage")
_TIMEOUT = re.compile(
    r"(?i)ran past the limit|timed out after|exceeded the (?:hard )?time ?out|hard time ?out"
    r"|test (?:run )?timed out")
_EPOCH = re.compile(r"(?:\||resets?(?: at)?\s*)(\d{10})\b", re.IGNORECASE)
_CLOCK = re.compile(r"(?i)\bresets?\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b")
_NUMBERS = re.compile(r"0x[0-9a-f]+|\b[0-9a-f]{7,}\b|\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """What the watch found in one builder session.

    `kind` is `stuck` or `usage-limit`. `resume_at` is the time (seconds since the epoch) a usage
    limit resets, when the message said so.
    """

    kind: str
    reason: str
    resume_at: float | None = None


def normal(line: str) -> str:
    """A line with the numbers taken out, so the same error at another line number matches."""
    text = _ANSI.sub("", line).strip().lower()
    text = _NUMBERS.sub("N", text)
    return " ".join(text.split())[:200]


def is_error(line: str) -> bool:
    return bool(_ERROR.search(line))


class Watcher:
    """One builder session, read line by line. It never reads a file or runs a program."""

    def __init__(self, now: Callable[[], float] = time.time) -> None:
        self._now = now
        self.usage: Finding | None = None
        self.stuck: Finding | None = None
        self.last_error = ""
        self._previous_line = ""
        self._errors: list[str] = []
        self._states: list[str] = []

    @property
    def finding(self) -> Finding | None:
        """A usage limit wins: a session that ended at the limit was not finished, not stuck."""
        return self.usage or self.stuck

    def feed(self, line: str) -> Finding | None:
        """Read one line. Returns a finding the first time one is made."""
        clean = _ANSI.sub("", line).rstrip()
        if not clean.strip():
            return None
        found = self._usage_in(clean)
        if found is not None:
            first = self.usage is None
            self.usage = self.usage or found
            return found if first else None
        if clean == self._previous_line:
            return None  # one output printed on several lines counts once
        self._previous_line = clean
        if self.stuck is not None:
            return None
        found = self._timeout_in(clean) or self._same_error(clean)
        if found is not None:
            self.stuck = found
        return found

    def observe_state(self, digest: str) -> Finding | None:
        """Read the state of the piece's folder. A state, another, the first, the second: stuck."""
        if self._states and self._states[-1] == digest:
            return None
        self._states.append(digest)
        last = self._states[-4:]
        if len(last) == 4 and last[0] == last[2] and last[1] == last[3] and last[0] != last[1]:
            self.stuck = self.stuck or Finding(
                "stuck", "the same change was undone and redone: the folder went back and forth "
                "between two states twice")
            return self.stuck
        return None

    def _usage_in(self, line: str) -> Finding | None:
        if not _USAGE.search(line):
            return None
        return Finding("usage-limit", line.strip()[:200], self._reset_time(line))

    def _reset_time(self, line: str) -> float | None:
        epoch = _EPOCH.search(line)
        if epoch:
            return float(epoch.group(1))
        clock = _CLOCK.search(line)
        if not clock:
            return None
        hour = int(clock.group(1)) % 12 + (12 if clock.group(3).lower() == "pm" else 0)
        now = self._now()
        today = time.localtime(now)
        at = time.mktime((today.tm_year, today.tm_mon, today.tm_mday, hour,
                          int(clock.group(2) or 0), 0, 0, 0, -1))
        return at if at > now else at + 86400

    def _timeout_in(self, line: str) -> Finding | None:
        if _TIMEOUT.search(line):
            return Finding("stuck", f"a test ran past its hard timeout: {line.strip()[:160]}")
        return None

    def _same_error(self, line: str) -> Finding | None:
        if not is_error(line):
            return None
        sign = normal(line)
        self.last_error = sign
        if self._errors and self._errors[-1] == sign:
            self._errors.append(sign)
        else:
            self._errors = [sign]
        if len(self._errors) >= SAME_ERROR_TIMES:
            return Finding("stuck", f"the same error {SAME_ERROR_TIMES} times in a row: "
                           f"{line.strip()[:160]}")
        return None


def scan(text: str) -> Finding | None:
    """The finding in a whole output, or None."""
    watcher = Watcher()
    for line in text.splitlines():
        watcher.feed(line)
    return watcher.finding


# --- the state the module keeps for each run -------------------------------------------


@dataclass
class _Piece:
    watcher: Watcher = field(default_factory=Watcher)
    polled: float = 0.0
    stopped: bool = False


@dataclass
class _Run:
    pieces: dict[int, _Piece] = field(default_factory=dict)
    last_env: int | None = None
    failures: dict[str, set[int]] = field(default_factory=dict)
    said: set[str] = field(default_factory=set)  # notes made once


_RUNS: dict[tuple[str, str], _Run] = {}
_LOCK = threading.RLock()


def _key(paths: Paths, name: str) -> tuple[str, str]:
    return (str(paths.root), name)


def _run(paths: Paths, name: str) -> _Run:
    with _LOCK:
        return _RUNS.setdefault(_key(paths, name), _Run())


def forget(paths: Paths, name: str) -> None:
    """Drop what the module kept for a run. A run started again begins from its record."""
    with _LOCK:
        _RUNS.pop(_key(paths, name), None)


def _piece(context: Any, number: int) -> _Piece:
    state = _run(context.paths, context.name)
    with _LOCK:
        return state.pieces.setdefault(number, _Piece())


def _note_once(context: Any, key: str, text: str) -> None:
    state = _run(context.paths, context.name)
    with _LOCK:
        if key in state.said:
            return
        state.said.add(key)
    context.record.note(text)


# --- the engine's calls ----------------------------------------------------------------


def session_started(context: Any, piece: int) -> None:
    """A builder session starts: it is read from the start."""
    state = _run(context.paths, context.name)
    with _LOCK:
        state.pieces[piece] = _Piece()


def on_output(context: Any, piece: int, line: str) -> None:
    """One line the builder printed. A stuck attempt is stopped here, as soon as it is clear."""
    held = _piece(context, piece)
    with _LOCK:
        found = held.watcher.feed(line)
        stop = found is not None and found.kind == "stuck" and not held.stopped
        if stop:
            held.stopped = True
    if stop and found is not None:
        context.stop_attempt(piece, found.reason)


def assess_session(context: Any, piece: int, result: sessions.Result) -> Finding | None:
    """What the watch found in a session that ended, or None. It forgets the session."""
    state = _run(context.paths, context.name)
    with _LOCK:
        held = state.pieces.pop(piece, None)
    if held is None:
        held = _Piece()
        for line in f"{result.stdout}\n{result.stderr}".splitlines():
            held.watcher.feed(line)
    return held.watcher.finding


def run_hook(context: Any, event: str, **data: Any) -> None:
    if event == "start":
        forget(context.paths, context.name)
    elif event == "tick":
        _tick(context)
    elif event == "session-ended":
        _session_ended(context, int(data["piece"]), data["result"])


# --- a change undone and redone --------------------------------------------------------


def _digest(folder: Path) -> str:
    """The state of a folder: its commit, its changed files and their changes."""
    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(folder), *args], capture_output=True,
            text=True, check=False, timeout=30, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            raise OSError((done.stderr or done.stdout).strip()[:160] or f"git {args[0]} failed")
        return done.stdout
    text = "\n".join((git("rev-parse", "HEAD"), git("status", "--porcelain=v1"),
                      git("diff", "HEAD")))
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def _tick(context: Any) -> None:
    for number in context.live_sessions():
        held = _piece(context, number)
        now = time.monotonic()
        with _LOCK:
            if held.stopped or (held.polled and now - held.polled < DIGEST_SECONDS):
                continue
            held.polled = now
        name = context.record.piece(number).get("worktree")
        if not name:
            continue
        folder = context.paths.worktrees_dir / str(name)
        try:
            digest = _digest(folder)
        except (OSError, subprocess.SubprocessError) as error:
            _note_once(context, f"folder:{number}",
                       f"piece {number}: the folder {folder} cannot be read ({error}), so the "
                       "watch cannot tell a change undone and redone there")
            continue
        with _LOCK:
            found = held.watcher.observe_state(digest)
            stop = found is not None and not held.stopped
            if stop:
                held.stopped = True
        if stop and found is not None:
            context.stop_attempt(number, found.reason)


# --- the real stops of the run ---------------------------------------------------------


def _notify(context: Any, kind: str, key: str, text: str, pieces: list[int]) -> None:
    """Notify once: a line on standard error and a note and an entry in the run record."""
    rec = context.record
    with rec.lock:
        held = rec.data.setdefault("real_stops", [])
        if any(item.get("key") == key for item in held):
            return
        held.append({"key": key, "kind": kind, "text": text, "pieces": sorted(pieces),
                     "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        rec.save()
    sys.stderr.write(f"real stop: {text}. The run goes on with the work that does not depend "
                     "on it.\n")
    rec.note(f"real stop: {text}. The run goes on with the work that does not depend on it")


def _session_ended(context: Any, number: int, result: sessions.Result) -> None:
    state = _run(context.paths, context.name)
    handoff: Mapping[str, Any] | None = result.handoff
    outcome = handoff.get("outcome") if handoff else None
    detail = ""
    if handoff and outcome in sessions.HANDOFF_FIELD:
        detail = str(handoff.get(sessions.HANDOFF_FIELD[str(outcome)], ""))
    # 1. two environment failures in a row, on different pieces
    with _LOCK:
        before = state.last_env
        state.last_env = number if outcome == "blocked-by-environment" else None
    if outcome == "blocked-by-environment" and before is not None and before != number:
        pair = sorted((before, number))
        _notify(context, "environment", f"environment:{pair[0]}-{pair[1]}",
                f"two environment failures in a row, on pieces {pair[0]} and {pair[1]} "
                f"(the last: {detail[:120]})", pair)
    # 2. the same refused command in two pieces
    _refused_commands(context)
    # 3. the same failure in several pieces
    sign = _failure_sign(context, number, result, detail)
    if sign:
        with _LOCK:
            pieces = state.failures.setdefault(sign, set())
            pieces.add(number)
            found = sorted(pieces)
        if len(found) >= SEVERAL:
            _notify(context, "same-failure", f"same-failure:{sign}",
                    f"the same failure in pieces {', '.join(str(n) for n in found)}: {sign}",
                    found)


def _failure_sign(context: Any, number: int, result: sessions.Result, detail: str) -> str:
    """What failed, as a short line that two pieces can share. It may be empty."""
    if detail and result.handoff and result.handoff.get("outcome") in FAILED_OUTCOMES:
        return normal(detail)
    watcher = Watcher()
    for line in f"{result.stdout}\n{result.stderr}".splitlines():
        watcher.feed(line)
    if watcher.last_error:
        return watcher.last_error
    try:
        piece = moves.read_piece(context.paths, number)
    except moves.MoveError:
        return ""
    if piece is None:
        return ""
    failed = [a for a in attempt_log.attempts(piece.record) if a.get("result") == "failed"]
    if failed and failed[-1].get("findings"):
        return normal(str(failed[-1]["findings"][0].get("text", "")))
    return ""


def _refused_commands(context: Any) -> None:
    log = context.paths.command_log(context.name)
    if not log.exists():
        return
    try:
        rows = log.read_text(encoding="utf-8").splitlines()[-COMMAND_LOG_ROWS:]
    except (OSError, UnicodeDecodeError) as error:
        _note_once(context, "command-log",
                   f"the command log {log} cannot be read ({type(error).__name__}), so the "
                   "watch cannot tell the same command refused in two pieces")
        return
    seen: dict[str, set[int]] = {}
    shown: dict[str, str] = {}
    for line in rows:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("event") != "refuse":
            continue
        number = _piece_of(context.paths, str(row.get("cwd", "")))
        command = " ".join(str(row.get("command", "")).split())
        if number is None or not command:
            continue
        seen.setdefault(command, set()).add(number)
        shown[command] = command[:120]
    for command, pieces in seen.items():
        if len(pieces) >= 2:
            found = sorted(pieces)
            _notify(context, "refused-command", f"refused-command:{command}",
                    f"the same command was refused in pieces "
                    f"{', '.join(str(n) for n in found)}: {shown[command]}", found)


def _piece_of(paths: Paths, cwd: str) -> int | None:
    """The piece whose folder a command ran in. A link in the path (/var and /private/var) does
    not hide it."""
    for here, base in ((Path(cwd), paths.worktrees_dir),
                       (Path(cwd).resolve(), paths.worktrees_dir.resolve())):
        try:
            first = here.relative_to(base).parts[0]
        except (ValueError, IndexError):
            continue
        break
    else:
        return None
    match = re.match(r"(\d+)-", first)
    return int(match.group(1)) if match else None
