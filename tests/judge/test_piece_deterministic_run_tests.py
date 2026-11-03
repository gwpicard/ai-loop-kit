# Intent: tests that start a real run or the fake-claude stand-in cannot wait for ever, and the pid wait is exact.
from __future__ import annotations

import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))

try:
    import helpers
except ImportError as error:
    if error.name != "helpers" and not str(error.name).startswith("helpers."):
        raise
    helpers = None

try:
    import run_fixtures
except ImportError as error:
    if error.name != "run_fixtures" and not str(error.name).startswith("run_fixtures."):
        raise
    run_fixtures = None


class WaitForPidTest(unittest.TestCase):
    def test_D1_empty_file_keeps_waiting_then_returns_number(self):
        self.assertTrue(helpers is not None and hasattr(helpers, "wait_for_pid"),
                        "helpers.wait_for_pid must exist")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "child.pid"
            path.write_text("")
            timer = threading.Timer(0.4, path.write_text, args=("4242\n",))
            timer.start()
            try:
                value = helpers.wait_for_pid(path, timeout=10)
            finally:
                timer.join()
            self.assertEqual(value, 4242)
            self.assertIsInstance(value, int)

    def test_D1_file_empty_past_timeout_raises_naming_file(self):
        self.assertTrue(helpers is not None and hasattr(helpers, "wait_for_pid"),
                        "helpers.wait_for_pid must exist")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "never-written.pid"
            path.write_text("")
            with self.assertRaises(AssertionError) as caught:
                helpers.wait_for_pid(path, timeout=0.3)
            self.assertIn("never-written.pid", str(caught.exception))


class FakeClaudeVersionTest(unittest.TestCase):
    def test_D2_version_answers_without_reading_standard_input(self):
        self.assertTrue(run_fixtures is not None and hasattr(run_fixtures, "FAKE_CLAUDE"),
                        "run_fixtures.FAKE_CLAUDE must exist")
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "fake-claude"
            fake.write_text(run_fixtures.FAKE_CLAUDE)
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            work = Path(folder) / "work"
            work.mkdir()
            process = subprocess.Popen(
                [str(fake), "--version"], cwd=work, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                start_new_session=True)
            try:
                try:
                    output = process.stdout.read() if process.wait(timeout=5) is not None else ""
                except subprocess.TimeoutExpired:
                    self.fail("fake-claude --version waited for standard input")
                self.assertEqual(process.returncode, 0)
                self.assertIn("2.1.300", output)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                process.stdout.close()
                process.stdin.close()


class _Sleeper(unittest.TestCase):
    __test__ = False

    def runTest(self):
        pass


class TimeLimitTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(run_fixtures is not None and hasattr(run_fixtures, "arm_time_limit"),
                        "run_fixtures.arm_time_limit must exist")
        self.old_handler = signal.getsignal(signal.SIGALRM)
        self.addCleanup(signal.setitimer, signal.ITIMER_REAL, 0)
        self.addCleanup(lambda: signal.signal(signal.SIGALRM, self.old_handler))

    def test_D3_long_test_fails_naming_test_and_limit(self):
        case = _Sleeper()
        run_fixtures.arm_time_limit(case, seconds=0.3)
        started = time.monotonic()
        with self.assertRaises(TimeoutError) as caught:
            time.sleep(10)
        self.assertLess(time.monotonic() - started, 5)
        self.assertIn(case.id(), str(caught.exception))
        self.assertIn("0.3", str(caught.exception))
        case.doCleanups()
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0)
        self.assertIs(signal.getsignal(signal.SIGALRM), self.old_handler)

    def test_D3_default_limit_is_600_without_attribute(self):
        case = _Sleeper()
        run_fixtures.arm_time_limit(case)
        remaining = signal.getitimer(signal.ITIMER_REAL)[0]
        case.doCleanups()
        self.assertGreater(remaining, 590)
        self.assertLessEqual(remaining, 600)

    def test_D3_time_limit_seconds_attribute_sets_the_limit(self):
        case = _Sleeper()
        case.time_limit_seconds = 0.3
        run_fixtures.arm_time_limit(case)
        with self.assertRaises(TimeoutError) as caught:
            time.sleep(10)
        case.doCleanups()
        self.assertIn("0.3", str(caught.exception))

    def test_D3_run_fixture_setup_arms_the_limit(self):
        class Built(run_fixtures.RunFixture, unittest.TestCase):
            time_limit_seconds = 30

            def runTest(self):
                pass

        case = Built()
        try:
            case.setUp()
            remaining = signal.getitimer(signal.ITIMER_REAL)[0]
            self.assertGreater(remaining, 20)
            self.assertLessEqual(remaining, 30)
        finally:
            case.doCleanups()
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0)

    def test_D3_every_test_file_writing_fake_claude_arms_a_limit(self):
        offenders = []
        for path in sorted(TESTS.glob("*.py")):
            if path.name == "run_fixtures.py":
                continue
            text = path.read_text()
            if "FAKE_CLAUDE" in text and "arm_time_limit" not in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])


class SigtermScenarioTest(unittest.TestCase):
    def test_D4_sigterm_test_uses_wait_for_pid_and_closed_stdin(self):
        source = (TESTS / "test_scenarios.py").read_text()
        match = re.search(
            r"    def test_real_run_sigterm_stops_a_child_during_review\(self\):(.*?)(?=\n    def |\Z)",
            source, re.S)
        self.assertIsNotNone(match, "the SIGTERM scenario test must exist")
        body = match.group(1)
        self.assertIn("wait_for_pid(child_pid_file", body)
        self.assertNotIn("int(child_pid_file.read_text())", body)
        self.assertEqual(body.count("stdin=subprocess.DEVNULL"), 2)


if __name__ == "__main__":
    unittest.main()
