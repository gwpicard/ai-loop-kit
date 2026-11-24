"""Network outages keep the supervisor polling; repeated defects stop it."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import common
import loop


class OutageTest(unittest.TestCase):
    def run_failed_cycles(self, error):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as folder:
            root = Path(folder)
            (root / "loop.json").write_text(json.dumps({"Test command": "true"}))
            calls, waits = [], []

            def snapshot(st):
                calls.append((root / ".loop/loop.pid").exists())
                raise error

            def wait(path, seconds):
                waits.append(seconds)
                # Stop through the command only after ten failed cycles have retried.
                if len(waits) == 10:
                    loop.main(["stop"])

            output = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.callback(os.chdir, os.getcwd())
                os.chdir(root)
                for name in ("setup.missing", "common.restore_loop_branch",
                             "common.warn_delete_branch_on_merge", "clean_up", "write_board"):
                    stack.enter_context(mock.patch("loop." + name, return_value=None))
                stack.enter_context(mock.patch("loop.setup.tidy", return_value=([], None)))
                stack.enter_context(mock.patch("loop.stray_workers", return_value=[]))
                stack.enter_context(mock.patch("loop.shutil.which", return_value=None))
                stack.enter_context(mock.patch("loop.snapshot", side_effect=snapshot))
                stack.enter_context(mock.patch("loop.wait_stop", side_effect=wait))
                stack.enter_context(contextlib.redirect_stdout(output))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                code = loop.main(["run"])

            events = [json.loads(line) for line in
                      (root / ".loop/events.jsonl").read_text().splitlines()]
            return code, calls, waits, events, output.getvalue()

    def assert_outage_keeps_polling(self, error):
        code, calls, waits, events, output = self.run_failed_cycles(error)
        self.assertEqual(len(calls), 10, "the loop must survive ten identical network failures")
        self.assertTrue(all(calls), "the supervisor must still hold its pid file each cycle")
        self.assertEqual(code, 0, output)
        self.assertEqual(waits, [loop.POLL] * 10)
        self.assertFalse(any(event["kind"] == "crash" for event in events), events)
        self.assertEqual([event["reason"] for event in events if event["kind"] == "exit"],
                         ["stop requested"])
        problems = [line for line in output.splitlines() if "problem, will check again" in line]
        self.assertEqual(len(problems), 10, output)
        self.assertTrue(all(str(error) in line for line in problems), problems)

    def test_ten_identical_github_errors_keep_polling(self):
        self.assert_outage_keeps_polling(common.GitHubError("gh issue list failed: HTTP 502"))

    def test_ten_identical_network_os_errors_keep_polling(self):
        for error in (OSError("network is unreachable"), ConnectionResetError("connection reset")):
            with self.subTest(error=error):
                self.assert_outage_keeps_polling(error)

    def test_repeated_defects_wait_poll_before_stopping_at_error_limit(self):
        for error in (TypeError("snapshot signature changed"), ValueError("invalid snapshot")):
            with self.subTest(error=error):
                code, calls, waits, events, output = self.run_failed_cycles(error)
                self.assertEqual(code, 1, output)
                self.assertEqual(len(calls), loop.ERROR_LIMIT)
                self.assertEqual(len([event for event in events if event["kind"] == "crash"]), 1)
                self.assertEqual(waits, [loop.POLL] * (loop.ERROR_LIMIT - 1))
