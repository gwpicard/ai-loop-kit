"""Repeated supervisor defects stop with evidence; intervening cycles reset them."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests import run
import loop


class RepeatedExceptionTest(unittest.TestCase):
    def run_errors(self, errors):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as folder:
            root = Path(folder)
            (root / "loop.json").write_text(json.dumps({"Test command": "true"}))
            calls, boards = [], []

            def broken_snapshot(st):
                index = len(calls)
                calls.append(index)
                error = errors[min(index, len(errors) - 1)]
                if error is not None:
                    raise error

            def wait(path, seconds):
                # Bound the old retry loop without replacing the behaviour under test.
                if len(calls) >= len(errors) + 2:
                    Path(path).touch()

            with contextlib.ExitStack() as stack:
                stack.callback(os.chdir, os.getcwd())
                os.chdir(root)
                for name in ("setup.missing", "common.restore_loop_branch", "common.warn_delete_branch_on_merge",
                             "sync_default", "drain", "clean_up", "start_builds", "answer"):
                    stack.enter_context(mock.patch("loop." + name, return_value=None))
                stack.enter_context(mock.patch("loop.setup.tidy", return_value=([], None)))
                stack.enter_context(mock.patch("loop.stray_workers", return_value=[]))
                stack.enter_context(mock.patch("loop.shutil.which", return_value=None))
                stack.enter_context(mock.patch("loop.snapshot", side_effect=broken_snapshot))
                stack.enter_context(mock.patch("loop.wait_stop", side_effect=wait))
                stack.enter_context(mock.patch("loop.write_board", side_effect=lambda p, st: boards.append(dict(st))))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                code = loop.main(["run"])
            events = [json.loads(line) for line in (root / ".loop/events.jsonl").read_text().splitlines()]
            return code, calls, boards, events

    def test_identical_errors_exit_with_crash_traceback_and_board_reason(self):
        code, calls, boards, events = self.run_errors([TypeError("snapshot signature changed")] * 3)
        self.assertNotEqual(code, 0, "the supervisor retried a permanent defect until the safety stop")
        self.assertEqual(len(calls), 3)
        crashes = [event for event in events if event["kind"] == "crash"]
        self.assertEqual(len(crashes), 1, events)
        report = json.dumps(crashes[0])
        for text in ("TypeError", "snapshot signature changed", "Traceback", "broken_snapshot"):
            self.assertIn(text, report)
        self.assertTrue(any("TypeError" in board["last"] and "snapshot signature changed" in board["last"]
                            for board in boards), boards)

    def test_different_type_message_or_success_resets_consecutive_count(self):
        cases = (
            [TypeError("first")] * 2 + [TypeError("second")] * 3,
            [TypeError("same")] * 2 + [ValueError("same")] * 3,
            [TypeError("same")] * 2 + [None] + [TypeError("same")] * 3,
        )
        for errors in cases:
            with self.subTest(errors=errors):
                code, calls, boards, events = self.run_errors(errors)
                self.assertEqual(len(calls), len(errors), "count only consecutive identical failed cycles")
                self.assertNotEqual(code, 0)
                self.assertEqual(len([event for event in events if event["kind"] == "crash"]), 1)

    def test_existing_build_retention_fixture_fails_promptly_with_type_error(self):
        code = '''
import unittest
from unittest import mock
from kit.tests.test_settings_build_retention import BuildRetentionTest
import loop
original = loop.main
def main(argv):
    with mock.patch.object(loop, "snapshot", side_effect=TypeError("snapshot fixture regression")):
        return original(argv)
with mock.patch.object(loop, "main", side_effect=main):
    suite = unittest.TestSuite([BuildRetentionTest("test_serial_build_keeps_settings_after_local_file_fails")])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(run.ROOT, "kit", "scripts")
        proc = subprocess.Popen([sys.executable, "-c", code], cwd=run.ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
        try:
            try:
                out, err = proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                self.fail("check_build hung for eight seconds instead of reporting the TypeError")
            self.assertNotEqual(proc.returncode, 0, out + err)
            self.assertIn("TypeError", out + err)
            self.assertIn("snapshot fixture regression", out + err)
        finally:
            run.kill_group(proc.pid)
            proc.communicate()
