"""Notifications: classified events, the macOS call and the watcher."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helpers  # noqa: F401  (puts kit/scripts on the path)

# isort: split
import notifications

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
MAC = patch.object(notifications.sys, "platform", "darwin")


def stamp(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def ev(name, piece=None, state="", reason="", time=None, **more):
    return {"time": time or stamp(1), "piece": piece, "event": name, "state": state,
            "attempt": 1, "reason": reason, **more}


class ClassifyTest(unittest.TestCase):
    def test_D1_events_map_to_kinds_and_the_rest_to_nothing(self):
        kind = lambda e: (notifications.classify(e) or {}).get("kind")
        self.assertEqual(kind(ev("submit", 5, "approval")), "ready-for-review")
        self.assertEqual(kind(ev("give-back", 5, "shaping", "stopped")), "handed-back")
        self.assertEqual(kind(ev("reject", 5, "shaping", "reject")), "handed-back")
        self.assertEqual(kind(ev("give-back", 5, "shaping", "stopped", cause="needs-answer")),
                         "question")
        self.assertEqual(kind(ev("give-back", 5, "shaping", "stopped", cause="other")),
                         "handed-back")
        self.assertEqual(kind(ev("run-stop", reason="ended")), "finished")
        for name in ("claim", "ready", "run-start", "run-pieces", "capture", "base-check", "land"):
            self.assertIsNone(notifications.classify(ev(name, 5, "ready")), name)

    def test_D2_a_piece_notification_names_the_piece_and_the_typed_reason(self):
        found = notifications.classify(ev("give-back", 7, "shaping", "stopped"))
        self.assertEqual(set(found), {"kind", "piece", "message", "time"})
        self.assertEqual(found["piece"], 7)
        self.assertIn("7", found["message"])
        self.assertIn("stopped", found["message"])
        self.assertIn("7", notifications.classify(ev("submit", 7, "approval"))["message"])

    def test_D2_free_text_never_reaches_a_message(self):
        hostile = ev("give-back", 7, "shaping", "Fix the \"title\" $HOME; do shell script",
                     title="Secret title", text="builder words")
        found = notifications.classify(hostile)
        self.assertEqual(found["message"], "Piece 7 was handed back.")
        self.assertNotIn("HOME", json.dumps(found))
        self.assertEqual(notifications.classify(ev("run-stop", reason="ended"))["piece"], None)


class Quiet(unittest.TestCase):
    """A project folder holding a run's events."""

    def __enter__(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.events_path = self.root / ".loop" / "events.jsonl"
        self.write_events([ev("run-start", reason="started", time=stamp(120))])
        return self

    def write_events(self, events):
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("".join(json.dumps(e) + "\n" for e in events))


class DeliverTest(unittest.TestCase):
    on = {"notify": {"macos": True, "sound": None}}
    note = {"kind": "finished", "piece": None, "message": "The run finished.", "time": None}

    def run_deliver(self, note, preferences, platform="darwin", **options):
        with patch.object(notifications.sys, "platform", platform), \
                patch.object(notifications.subprocess, "run", **options) as run:
            notifications.deliver(note, preferences)
        return run

    def test_D5_off_or_missing_preferences_never_call_osascript(self):
        for preferences in ({}, None, {"notify": {"macos": False, "sound": "Glass"}},
                            {"notify": {"macos": "yes"}}):
            self.assertFalse(self.run_deliver(self.note, preferences).called, preferences)
        self.assertFalse(self.run_deliver(self.note, self.on, platform="linux").called)

    def test_D5_on_calls_once_with_the_message_and_a_plain_sound_as_arguments(self):
        run = self.run_deliver(self.note, self.on)
        run.assert_called_once()
        command = run.call_args[0][0]
        self.assertEqual((command[0], command[-1]), ("osascript", "The run finished."))
        run = self.run_deliver(self.note, {"notify": {"macos": True, "sound": "Glass"}})
        self.assertEqual(run.call_args[0][0][-2:], ["The run finished.", "Glass"])

    def test_D5_a_sound_that_is_not_a_plain_word_is_rejected(self):
        for sound in ('Glass" & do shell script "x', "a b", "../x", ""):
            run = self.run_deliver(self.note, {"notify": {"macos": True, "sound": sound}})
            self.assertEqual(run.call_args[0][0][-1], "The run finished.", sound)
            self.assertEqual(len(run.call_args[0][0]), 4, sound)

    def test_D6_a_hostile_message_is_an_argument_and_never_script_text(self):
        message = 'say "hi" \\ do shell script "touch x"'
        run = self.run_deliver({**self.note, "message": message}, self.on)
        command = run.call_args[0][0]
        script = command[command.index("-e") + 1]
        self.assertNotIn("do shell script", script)
        self.assertNotIn("hi", script)
        self.assertIn("item 1 of argv", script)
        self.assertEqual(command[-1], message)

    def test_D7_a_missing_osascript_or_a_failure_is_swallowed(self):
        self.run_deliver(self.note, self.on, side_effect=FileNotFoundError())
        self.run_deliver(self.note, self.on, side_effect=subprocess.TimeoutExpired("osascript", 10))
        self.run_deliver(self.note, self.on,
                         return_value=subprocess.CompletedProcess([], 1))

    def test_D7_a_failing_osascript_does_not_stop_the_watcher(self):
        quiet = Quiet()
        quiet.__enter__()
        self.addCleanup(quiet.doCleanups)
        quiet.write_events([ev("run-start", time=stamp(5))])
        (quiet.root / ".loop" / "preferences.json").write_text(json.dumps(self.on))
        watcher = notifications.EventWatcher(quiet.root)
        with MAC, patch.object(notifications.subprocess, "run", side_effect=OSError("gone")) as run:
            with quiet.events_path.open("a") as out:
                out.write(json.dumps(ev("submit", 5, "approval")) + "\n")
                out.write(json.dumps(ev("run-stop", reason="ended")) + "\n")
            watcher.poll()
        self.assertEqual(run.call_count, 2)


class WatcherTest(unittest.TestCase):
    def test_D9_the_watcher_delivers_new_events_once_and_writes_nothing(self):
        quiet = Quiet()
        quiet.__enter__()
        self.addCleanup(quiet.doCleanups)
        (quiet.root / ".loop" / "preferences.json").write_text(
            json.dumps({"notify": {"macos": True, "sound": None}}))
        before = quiet.events_path.read_bytes()
        watcher = notifications.EventWatcher(quiet.root)
        with MAC, patch.object(notifications.subprocess, "run") as run:
            watcher.poll()
            self.assertFalse(run.called)  # earlier events are not announced
            with quiet.events_path.open("a") as out:
                out.write(json.dumps(ev("give-back", 4, "shaping", "stopped")) + "\n")
                out.write(json.dumps(ev("claim", 4, "building")) + "\n")
            watcher.poll()
            watcher.poll()
        run.assert_called_once()
        self.assertTrue(quiet.events_path.read_bytes().startswith(before))
        self.assertEqual(quiet.events_path.read_text().count("\n"), 3)


if __name__ == "__main__":
    unittest.main()
