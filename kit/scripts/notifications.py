"""Tell the person when something matters: on the dashboard, and optionally on macOS.

`classify` turns one run event into a notification, `stuck` notices a run that stopped
or went quiet, and `deliver` shows a notification through macOS. Messages hold fixed
metadata only: the kind, the piece number and a typed reason. The setting lives in the
local, untracked `.loop/preferences.json`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import procs
import walkaway

QUIET_AFTER_SECONDS = 45 * 60
LATEST = 50
DEFAULTS = {"notify": {"macos": False, "sound": None}}
PLAIN_WORD = re.compile(r"[A-Za-z]{1,30}")
TITLE = "AI Loop Kit"
SCRIPT = ("on run argv\n"
          f'display notification (item 1 of argv) with title "{TITLE}"'
          " sound name (item 2 of argv)\nend run",
          "on run argv\n"
          f'display notification (item 1 of argv) with title "{TITLE}"\nend run')


def _word(value) -> str:
    """A typed reason or event name; anything else is left out."""
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z-]{0,40}", value) else ""


def classify(event: dict, previous: dict | None = None) -> dict | None:
    """One line of `.loop/events.jsonl` as `{kind, piece, message, time}`, or None."""
    name, piece = event.get("event"), event.get("piece")
    piece = piece if type(piece) is int and piece > 0 else None
    reason = _word(event.get("reason"))
    if name == "submit" and event.get("state") == "approval" and piece:
        kind, message = "ready-for-review", f"Piece {piece} is ready for review."
    elif name in ("give-back", "reject") and piece:
        if event.get("cause") == "needs-answer":
            kind, message = "question", f"Piece {piece} has a question for you."
        else:
            kind = "handed-back"
            message = f"Piece {piece} was handed back" + (f" ({reason})." if reason else ".")
    elif name == "run-stop":
        kind, message = "finished", "The run finished."
    else:
        return None
    return {"kind": kind, "piece": piece if kind != "finished" else None,
            "message": message, "time": event.get("time")}


def read_run_events(root: Path) -> list[dict]:
    """The events since the last run-start; lines that cannot be read are skipped."""
    events = []
    try:
        lines = (root / ".loop" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return events
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            if event.get("event") == "run-start":
                events = []
            events.append(event)
    return events


def _time(value) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _stuck(message: str, when: datetime | None) -> dict:
    return {"kind": "stuck", "piece": None, "message": message,
            "time": when.isoformat() if when else None}


def stuck(root: Path, now: datetime) -> dict | None:
    """A `stuck` notification when the current run stopped or looks inactive."""
    events = read_run_events(root)
    boundary = next((e for e in reversed(events) if e.get("event") in ("run-start", "run-stop")), {})
    if boundary.get("event") != "run-start":
        return None  # no run, or it finished
    try:
        pid = int(json.loads(procs.lock_path(root).read_text())["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    last = _time(events[-1].get("time"))
    if not procs.process_alive(pid):
        return _stuck("The run stopped without finishing.", last)
    started = _time(next(e for e in events if e.get("event") == "run-start").get("time"))
    try:
        beat = json.loads(walkaway.heartbeat_path(root).read_text())
        beat_time = _time(beat["time"])
    except (OSError, ValueError, KeyError, TypeError):
        beat, beat_time = {}, None
    if (beat_time and beat.get("state") != "finished" and (not started or beat_time > started)
            and (now - beat_time).total_seconds() > walkaway.STALE_AFTER_SECONDS):
        return _stuck("The run is possibly inactive: it has not reported for "
                      f"{walkaway.STALE_AFTER_SECONDS // 60} minutes.", beat_time)
    if last and (now - last).total_seconds() > QUIET_AFTER_SECONDS:
        return _stuck("The run is possibly inactive: no event for "
                      f"{QUIET_AFTER_SECONDS // 60} minutes.", last)
    return None


def current(root: Path, now: datetime | None = None) -> list[dict]:
    """The current run's notifications, newest last, at most 50."""
    found = [n for e in read_run_events(root) if (n := classify(e))]
    waiting = stuck(root, now or datetime.now(timezone.utc))
    return (found + ([waiting] if waiting else []))[-LATEST:]


def _preferences_path(root: Path) -> Path:
    return root / ".loop" / "preferences.json"


def read_preferences(root: Path) -> dict:
    """The saved setting; missing or unreadable means everything off."""
    notify = {**DEFAULTS["notify"]}
    try:
        saved = json.loads(_preferences_path(root).read_text())["notify"]
        if saved.get("macos") is True:
            notify["macos"] = True
        if isinstance(saved.get("sound"), str) and PLAIN_WORD.fullmatch(saved["sound"]):
            notify["sound"] = saved["sound"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return {"notify": notify}


def save_preferences(root: Path, body) -> tuple[int, dict]:
    """The HTTP status and answer for a change to the setting. Unknown keys are refused."""
    notify = body.get("notify") if isinstance(body, dict) and set(body) == {"notify"} else None
    if (not isinstance(notify, dict) or not notify or not set(notify) <= set(DEFAULTS["notify"])
            or ("macos" in notify and type(notify["macos"]) is not bool)
            or ("sound" in notify and notify["sound"] is not None and not (
                isinstance(notify["sound"], str) and PLAIN_WORD.fullmatch(notify["sound"])))):
        return 400, {"error": 'send {"notify": {"macos": true or false, "sound": a plain word or null}}'}
    merged = {"notify": {**read_preferences(root)["notify"], **notify}}
    path = _preferences_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"preferences.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(merged, sort_keys=True) + "\n")
        os.replace(temporary, path)
    except OSError as error:
        return 500, {"error": f"could not save the setting: {error.strerror or 'write failed'}"}
    return 200, merged


def deliver(notification: dict, preferences: dict) -> None:
    """Show the notification through macOS when it is on. Every failure is swallowed."""
    notify = (preferences or {}).get("notify") or {}
    if sys.platform != "darwin" or notify.get("macos") is not True:
        return
    sound = notify.get("sound")
    sound = sound if isinstance(sound, str) and PLAIN_WORD.fullmatch(sound) else None
    # The values travel as arguments, so a message can never become script text.
    command = ["osascript", "-e", SCRIPT[0] if sound else SCRIPT[1], str(notification.get("message", ""))]
    try:
        subprocess.run(command + ([sound] if sound else []), stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


class EventWatcher:
    """Delivers a notification for each event the run appends after it was created."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.offset = self._size()

    def _size(self) -> int:
        try:
            return (self.root / ".loop" / "events.jsonl").stat().st_size
        except OSError:
            return 0

    def poll(self) -> None:
        try:
            with (self.root / ".loop" / "events.jsonl").open("rb") as source:
                source.seek(self.offset)
                data = source.read()
            data = data[:data.rfind(b"\n") + 1]
            self.offset += len(data)
            for line in data.decode("utf-8", "replace").splitlines():
                try:
                    found = classify(json.loads(line))
                except (ValueError, AttributeError):
                    continue
                if found:
                    deliver(found, read_preferences(self.root))
        except Exception:  # a notification never stops the run
            pass


def deliver_stuck(root: Path, notifications: list[dict], sent: set) -> None:
    """Deliver the `stuck` notification once per message and run."""
    if notifications and notifications[-1]["kind"] == "stuck":
        key = (notifications[-1]["message"], notifications[-1]["time"])
        if key not in sent:
            sent.add(key)
            deliver(notifications[-1], read_preferences(root))
