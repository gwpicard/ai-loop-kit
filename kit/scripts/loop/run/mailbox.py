"""The mailbox: the person's pause, continue and stop, as lines in one file.

The file is `Paths.mailbox(name)`, in the run's folder. The person writes one word on a line:

    pause       no new session and no new piece starts. A session in flight goes on to its end.
    continue    the pause ends.
    stop        the stop signal: the sessions end, and each building piece goes back to ready
                by move 7, with its branch kept. The run ends as stopped.
    answer 4: blue
                the answer to the question piece 4 parked with, when no GitHub App reads
                comments for the run. It goes to `inbox.deliver`.

A blank line and a line that starts with `#` are ignored. Any other line is a note in the run
record, never a quiet skip. The run reads the file on every tick, in order, and each line once.
The lines that were in the file when the run started belong to an earlier run, so a stop left
there does not stop the next run. A file that is replaced (its first lines no longer the ones
that were read) is read again from its first line, since the person wrote new input.

An unreadable mailbox pauses the run, because it may hold a stop, and a note says so. The pause
ends when the file can be read again. The run record holds each command, in `mailbox`.
"""

from __future__ import annotations

import hashlib
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loop.run import inbox

COMMANDS = ("pause", "continue", "stop")
_ANSWER = re.compile(r"(?i)^answer\s+#?(\d+)\s*[:\-]?\s*(.+)$")


@dataclass
class _State:
    consumed: int = 0
    prefix: str = ""
    broken: bool = False  # the file could not be read, so the run is paused for that
    unread: set[str] = field(default_factory=set)


_STATES: dict[tuple[str, str], _State] = {}
_LOCK = threading.RLock()


def _state(context: Any) -> _State:
    with _LOCK:
        return _STATES.setdefault((str(context.paths.root), context.name), _State())


def forget(context: Any) -> None:
    with _LOCK:
        _STATES.pop((str(context.paths.root), context.name), None)


def _hash(lines: list[str]) -> str:
    return hashlib.sha1("\n".join(lines).encode("utf-8", "replace")).hexdigest()


def _read(context: Any) -> list[str] | None:
    """The lines of the file, [] when there is none, or None when it cannot be read."""
    path = context.paths.mailbox(context.name)
    try:
        text: str = path.read_text(encoding="utf-8")
        return text.splitlines()
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as error:
        _fault(context, f"the mailbox {path} cannot be read ({type(error).__name__}), so the run "
               "is paused until it can be read")
        return None


def _fault(context: Any, text: str) -> None:
    state = _state(context)
    with _LOCK:
        if text in state.unread:
            return
        state.unread.add(text)
    context.record.note(text)
    sys.stderr.write(text + "\n")


def _log(context: Any, command: str, line: str) -> None:
    rec = context.record
    with rec.lock:
        box = rec.data.setdefault("mailbox", {"events": [], "paused": False})
        box["events"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "command": command, "line": line[:200]})
        if command == "pause":
            box["paused"] = True
        elif command in ("continue", "stop"):
            box["paused"] = False
        rec.save()


def run_hook(context: Any, event: str, **data: Any) -> None:
    if event == "start":
        forget(context)
        lines = _read(context)
        state = _state(context)
        if lines is None:
            context.set_paused(True)
            state.broken = True
            return
        state.consumed, state.prefix = len(lines), _hash(lines)
        if lines:
            context.record.note(f"the mailbox held {len(lines)} line(s) from before the run "
                                "started, and they are not obeyed")
    elif event == "tick":
        _tick(context)


def _tick(context: Any) -> None:
    state = _state(context)
    lines = _read(context)
    if lines is None:
        if not state.broken:
            state.broken = True
            context.set_paused(True)
        return
    if state.broken:
        state.broken = False
        # The person's own pause stays: only the pause for the unreadable file ends.
        context.set_paused(bool(context.record.data.get("mailbox", {}).get("paused")))
        context.record.note("the mailbox can be read again, so the pause for it ends")
        with _LOCK:
            state.unread.clear()
    if len(lines) < state.consumed or _hash(lines[:state.consumed]) != state.prefix:
        context.record.note("the mailbox was replaced, so it is read again from its first line")
        state.consumed, state.prefix = 0, _hash([])
    new = lines[state.consumed:]
    if not new:
        return
    state.consumed, state.prefix = len(lines), _hash(lines)
    for raw in new:
        _obey(context, raw)


def _obey(context: Any, raw: str) -> None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return
    word = line.lower()
    if word in COMMANDS:
        _log(context, word, line)
        context.record.note(f"the mailbox said {word}")
        if word == "pause":
            context.set_paused(True)
        elif word == "continue":
            context.set_paused(False)
        else:
            context.request_stop()
        return
    answer = _ANSWER.match(line)
    if answer:
        _log(context, "answer", line)
        inbox.deliver(context, int(answer.group(1)), answer.group(2).strip(), "the mailbox")
        return
    context.record.note(f"the mailbox holds a line that is not pause, continue, stop or an "
                        f"answer, so it is ignored: {line[:80]!r}")
