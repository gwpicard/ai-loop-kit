"""Test subprocesses choose their guard role independently of the builder."""
import os
import unittest
from unittest import mock

from kit.tests import run


class RunnerRoleIsolationTest(unittest.TestCase):
    def test_copied_hooks_run_outside_the_enclosing_builder_role(self):
        with mock.patch.dict(os.environ, {"LOOP_ROLE": "builder"}):
            module, code, count, output = run.run_job(("test_guard", [
                "kit.tests.test_guard.HooksNeverCrashTest."
                "test_a_hook_that_cannot_load_allows_and_says_so",
            ]))
        self.assertEqual(code, 0, output)
        self.assertEqual(count, 1, output)


if __name__ == "__main__":
    unittest.main()
