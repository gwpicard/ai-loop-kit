"""Notifications: classified events, a stuck run, the macOS call and the preference."""
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge.test_dashboard_server import Base, Served, issue

# isort: split
import notifications
import procs
import walkaway

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

    def test_D2_stuck_describes_the_run_and_holds_no_piece(self):
        quiet = Quiet().__enter__()
        self.addCleanup(quiet.doCleanups)
        quiet.lock(alive=False)
        found = notifications.stuck(quiet.root, NOW)
        self.assertEqual((found["kind"], found["piece"]), ("stuck", None))
        self.assertNotIn("Piece", found["message"])


class Quiet(Base):
    """A project folder with a run's lock, events and heartbeat."""

    def __enter__(self):
        super().setUp()
        self.write_events([ev("run-start", reason="started", time=stamp(120))])
        return self

    def write_events(self, events):
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("".join(json.dumps(e) + "\n" for e in events))

    def lock(self, alive=True):
        path = procs.lock_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pid": os.getpid(), "children": []}))
        self.alive = patch.object(procs, "process_alive", return_value=alive)
        self.alive.start()
        self.addCleanup(self.alive.stop)

    def beat(self, minutes_ago, state="active"):
        walkaway.heartbeat_path(self.root).write_text(json.dumps(
            {"time": stamp(minutes_ago), "piece": 5, "attempt": 1, "state": state}))


class StuckTest(unittest.TestCase):
    def case(self):
        quiet = Quiet()
        quiet.__enter__()
        self.addCleanup(quiet.doCleanups)
        return quiet

    def test_D3_a_lock_with_a_dead_pid_is_stuck(self):
        quiet = self.case()
        quiet.lock(alive=False)
        self.assertIn("without finishing", notifications.stuck(quiet.root, NOW)["message"])

    def test_D3_a_stale_heartbeat_written_during_this_run_is_stuck(self):
        quiet = self.case()
        quiet.lock()
        quiet.write_events([ev("run-start", reason="started", time=stamp(120)),
                            ev("claim", 5, "building", time=stamp(5))])
        quiet.beat(11)
        found = notifications.stuck(quiet.root, NOW)
        self.assertEqual(found["kind"], "stuck")
        self.assertIn("possibly inactive", found["message"])

    def test_D3_a_heartbeat_from_an_earlier_run_is_ignored(self):
        quiet = self.case()
        quiet.lock()
        quiet.write_events([ev("run-start", reason="started", time=stamp(20)),
                            ev("claim", 5, "building", time=stamp(2))])
        quiet.beat(60)
        self.assertIsNone(notifications.stuck(quiet.root, NOW))

    def test_D3_a_live_run_with_no_event_for_45_minutes_is_possibly_inactive(self):
        quiet = self.case()
        quiet.lock()
        quiet.write_events([ev("run-start", reason="started", time=stamp(120)),
                            ev("claim", 5, "building", time=stamp(46))])
        quiet.beat(1)  # an attended run has no heartbeat; a fresh one does not hide silence
        self.assertIn("possibly inactive", notifications.stuck(quiet.root, NOW)["message"])
        quiet.write_events([ev("run-start", reason="started", time=stamp(120)),
                            ev("claim", 5, "building", time=stamp(44))])
        self.assertIsNone(notifications.stuck(quiet.root, NOW))

    def test_D3_a_finished_run_and_a_healthy_run_are_not_stuck(self):
        quiet = self.case()
        quiet.lock(alive=False)
        quiet.write_events([ev("run-start", time=stamp(120)), ev("run-stop", time=stamp(60))])
        self.assertIsNone(notifications.stuck(quiet.root, NOW))
        quiet.write_events([ev("run-start", time=stamp(120)), ev("claim", 5, time=stamp(1))])
        quiet.alive.stop()
        quiet.lock()
        quiet.beat(1)
        self.assertIsNone(notifications.stuck(quiet.root, NOW))


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

    def test_D7_the_run_goes_on_and_the_dashboard_still_lists_the_notification(self):
        quiet = Quiet()
        quiet.__enter__()
        self.addCleanup(quiet.doCleanups)
        quiet.write_events([ev("run-start", time=stamp(5))])
        (quiet.root / ".loop" / "preferences.json").write_text(json.dumps(self.on))
        watcher = notifications.EventWatcher(quiet.root)
        with MAC, patch.object(notifications.subprocess, "run", side_effect=OSError("gone")) as run:
            with quiet.events_path.open("a") as out:
                out.write(json.dumps(ev("submit", 5, "approval")) + "\n")
            watcher.poll()
        run.assert_called_once()
        self.assertEqual([n["kind"] for n in notifications.current(quiet.root, NOW)],
                         ["ready-for-review"])


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


class ServedTest(Served):
    def post(self, body, path="/api/preferences", token=True, cookie=True):
        headers = {"Content-Type": "application/json", "Host": f"127.0.0.1:{self.server.port}"}
        if token:
            headers["X-Loop-Token"] = self.server.token if token is True else token
        if cookie:
            headers["Cookie"] = "loop_dashboard=" + self.server.token
        data = json.dumps(body).encode()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("POST", path, data, {**headers, "Content-Length": str(len(data))})
        response = connection.getresponse()
        text = response.read()
        return response.status, json.loads(text) if text.startswith(b"{") else text

    def preferences(self):
        path = self.root / ".loop" / "preferences.json"
        return json.loads(path.read_text()) if path.exists() else None

    def test_D4_the_state_lists_the_runs_notifications_newest_last_at_most_50(self):
        issue(self.gh, "approval")
        self.event("submit", 1, "approval", reason="before")
        self.event("run-start", reason="started")
        for attempt in range(2, 60):
            self.event("submit", 1, "approval", attempt)
        self.event("run-stop", reason="ended")
        self.serve()
        found = self.state()["notifications"]
        self.assertEqual(len(found), 50)
        self.assertEqual(found[-1]["kind"], "finished")
        self.assertEqual({n["kind"] for n in found[:-1]}, {"ready-for-review"})

    def test_D4_a_run_that_stopped_without_finishing_ends_the_list_with_stuck(self):
        issue(self.gh, "approval")
        self.event("run-start", reason="started")
        self.event("submit", 1, "approval")
        self.hold_lock()
        with patch.object(procs, "process_alive", return_value=False):
            self.serve()
            found = self.state()["notifications"]
        self.assertEqual([n["kind"] for n in found], ["ready-for-review", "stuck"])

    def test_D8_a_post_with_the_token_saves_the_setting_and_nothing_else(self):
        self.serve()
        before = sorted(p.name for p in (self.root / ".loop").iterdir())
        status, answer = self.post({"notify": {"macos": True, "sound": "Glass"}})
        self.assertEqual(status, 200)
        self.assertEqual(self.preferences(), {"notify": {"macos": True, "sound": "Glass"}})
        self.assertEqual(answer, self.preferences())
        self.assertEqual(sorted(p.name for p in (self.root / ".loop").iterdir()),
                         sorted(before + ["preferences.json"]))
        self.assertTrue(self.state()["preferences"]["notify"]["macos"])

    def test_D8_a_post_without_the_token_or_cookie_changes_nothing(self):
        self.serve()
        self.assertEqual(self.post({"notify": {"macos": True}}, token=False)[0], 403)
        self.assertEqual(self.post({"notify": {"macos": True}}, cookie=False)[0], 403)
        self.assertEqual(self.post({"notify": {"macos": True}}, token="wrong")[0], 403)
        self.assertIsNone(self.preferences())

    def test_D8_unknown_keys_and_bad_values_are_refused(self):
        self.serve()
        for body in ({"notify": {"macos": True, "email": "x"}}, {"other": 1},
                     {"notify": {"macos": "yes"}}, {"notify": {"sound": "two words"}},
                     {"notify": {}}, {"notify": {"macos": True}, "extra": 1}, []):
            self.assertEqual(self.post(body)[0], 400, body)
        self.assertIsNone(self.preferences())

    def test_D8_a_change_keeps_the_other_value_and_missing_preferences_mean_off(self):
        self.assertEqual(notifications.read_preferences(self.root),
                         {"notify": {"macos": False, "sound": None}})
        self.serve()
        self.post({"notify": {"sound": "Ping"}})
        self.post({"notify": {"macos": True}})
        self.assertEqual(self.preferences(), {"notify": {"macos": True, "sound": "Ping"}})


if __name__ == "__main__":
    unittest.main()
