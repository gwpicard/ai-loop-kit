"""A hung test leaves a named failure and the stacks needed to diagnose it."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests import run


class HungProcessTest(unittest.TestCase):
    def test_faulthandler_is_enabled_inside_test_process(self):
        with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as folder:
            Path(folder, "handler_tests.py").write_text(
                "import faulthandler, unittest\n"
                "class HandlerTest(unittest.TestCase):\n"
                "    def test_enabled(self):\n"
                "        self.assertTrue(faulthandler.is_enabled(), 'faulthandler must be enabled')\n")
            with mock.patch.object(run, "ROOT", folder):
                module, code, count, output = run.run_job(
                    ("handler_tests", ["handler_tests.HandlerTest.test_enabled"]))
            self.assertEqual(code, 0, output)
            self.assertEqual(count, 1, output)

    def hung_job(self, method):
        with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as folder:
            Path(folder, "sleeping_tests.py").write_text(
                "import threading, time, unittest\n"
                "def waiting_worker():\n"
                "    time.sleep(60)\n"
                "class SleepingTest(unittest.TestCase):\n"
                "    def test_first_sleep(self):\n"
                "        self.sleep_here()\n"
                "    def test_second_sleep(self):\n"
                "        self.sleep_here()\n"
                "    def sleep_here(self):\n"
                "        threading.Thread(target=waiting_worker, daemon=True).start()\n"
                "        time.sleep(60)\n")
            with mock.patch.object(run, "ROOT", folder), \
                    mock.patch.object(run, "JOB_TIMEOUT", 1):
                return run.run_job(("sleeping_tests", ["sleeping_tests.SleepingTest." + method]))

    def test_timeout_reports_module_running_test_and_every_thread_stack(self):
        for method in ("test_first_sleep", "test_second_sleep"):
            with self.subTest(method=method):
                module, code, count, output = self.hung_job(method)
                self.assertNotEqual(code, 0, output)
                self.assertEqual(module, "sleeping_tests")
                self.assertIn(method, output, "the report must name the test that hung")
                self.assertIn("sleeping_tests.py", output)
                self.assertIn("sleep_here", output)
                self.assertIn("waiting_worker", output, "dump the worker thread as well")
                self.assertRegex(output, r"(?i)thread.*0x")

    def test_timeout_failure_starts_with_hung_and_names_limit(self):
        module, code, count, output = self.hung_job("test_first_sleep")
        self.assertNotEqual(code, 0, output)
        first = output.splitlines()[0]
        self.assertRegex(first, r"(?i)\bhung\b", output)
        self.assertIn("sleeping_tests", first)
        self.assertRegex(first, r"\b1(?:\.0)?\s*(?:seconds?|s)\b", output)
