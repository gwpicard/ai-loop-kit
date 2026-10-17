"""Session activity, process cleanup and run locks."""
from __future__ import annotations

from helpers import pump_events

# isort: split

import json
import os
import signal
import stat
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import run
import procs
from loopkit import Refused, run_judge
from run_fixtures import RunFixture


class RunTest(RunFixture, unittest.TestCase):
    def test_activity_stamp_skips_generated_build_directories(self):
        import session
        root = Path(self.p.tmp.name) / "activity"
        generated = root / "build" / "large"
        generated.mkdir(parents=True)
        (generated / "output.bin").write_text("x")
        before = session._folder_activity_stamp(root)
        future = time.time() + 10
        os.utime(generated / "output.bin", (future, future))
        self.assertEqual(session._folder_activity_stamp(root), before)

    def test_activity_stamp_is_polled_at_most_twice_per_second(self):
        import session
        script = Path(self.p.tmp.name) / "activity-child.py"
        script.write_text("import time; time.sleep(.55); print('done', flush=True)\n")
        proc = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        with patch.object(session, "_folder_activity_stamp",
                          wraps=session._folder_activity_stamp) as stamp:
            with (Path(self.p.tmp.name) / "activity.log").open("w") as output:
                session._pump_session(proc, output, 2, hard_seconds=5,
                                     activity_path=Path(self.p.tmp.name))
        self.assertLessEqual(stamp.call_count, 2)

    def test_claude_result_errors_are_logged(self):
        import session
        status, output = pump_events(session, [
            '{"type":"result","is_error":true,"result":"rate limited"}',
        ], idle_seconds=5)
        self.assertEqual(status, "")
        self.assertIn("Claude result error: rate limited", output)

    def test_claude_events_reset_idle_and_logs_keep_assistant_text(self):
        import session
        events = [json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": "hello"}]}}) for _ in range(5)]
        status, output = pump_events(session, events, idle_seconds=2, clock_step=.75)
        self.assertEqual(status, "")
        self.assertEqual(output.count("hello"), 5)
        self.assertNotIn('"type":"assistant"', output)

    def test_pump_stops_group_when_child_keeps_pipe_open_after_parent_exits(self):
        script = ("import subprocess,sys; "
                  "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                  "print('parent finished', flush=True)")
        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        def cleanup_group():
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            if proc.stdout:
                proc.stdout.close()
        self.addCleanup(cleanup_group)
        from io import StringIO

        from session import _pump_session
        output = StringIO()
        finished = threading.Event()
        errors = []

        def pump():
            try:
                _pump_session(proc, output, idle_seconds=30, hard_seconds=40)
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

        started = time.monotonic()
        worker = threading.Thread(target=pump)
        worker.start()
        finished_promptly = finished.wait(5)
        if not finished_promptly:
            os.killpg(proc.pid, signal.SIGKILL)
            worker.join(3)
        self.assertTrue(finished_promptly, "the output pipe stayed open after the child exit")
        self.assertEqual(errors, [])
        self.assertLess(time.monotonic() - started, 5)
        self.assertIn("parent finished", output.getvalue())

    def test_all_claude_sessions_request_stream_json(self):
        fake = Path(self.p.tmp.name) / "argv-claude"
        fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        logfile = Path(self.p.tmp.name) / "session.log"
        run.build_once(self.p.root, "brief", [], logfile)
        self.assertIn("--output-format stream-json --verbose", logfile.read_text())

    def test_run_lock_refuses_live_runs_and_takes_over_dead_ones(self):
        lock = run.acquire_lock(self.p.root)
        with self.assertRaises(Refused) as r:
            run.acquire_lock(self.p.root)
        self.assertIn("another run is live", r.exception.reason)
        run.release_lock(lock)
        lock.write_text('{"pid": 2147483647, "started_at": 0}\n')
        taken = run.acquire_lock(self.p.root)
        self.assertEqual(taken, lock)
        run.release_lock(taken)

    def test_judge_timeout_returns_a_clear_failure(self):
        code, output = run_judge(self.p.root, "sleep 2", timeout=0.1)
        self.assertEqual(code, 124)
        self.assertIn("past 0.1 seconds", output)

    def test_run_refuses_lock_with_a_live_orphan_process_group(self):
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        def stop_sleeper():
            if sleeper.poll() is None:
                sleeper.kill()
            sleeper.wait()
        self.addCleanup(stop_sleeper)
        lock = run.lock_path(self.p.root)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 2147483647, "started_at": 0,
                                    "children": [sleeper.pid]}))
        with self.assertRaises(Refused) as refused:
            run.acquire_lock(self.p.root)
        self.assertIn("orphan", refused.exception.reason)

    def test_run_kills_tracked_process_groups_on_interrupt(self):
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        def stop_sleeper():
            if sleeper.poll() is None:
                sleeper.kill()
            sleeper.wait()
        self.addCleanup(stop_sleeper)
        procs.track_process(sleeper, self.p.root)
        self.assertTrue(run.kill_active_processes())
        sleeper.wait(timeout=2)
        self.assertNotEqual(sleeper.returncode, 0)
