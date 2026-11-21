import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import HERE
from pathlib import Path

ROOT = Path(HERE).parent.parent


class RunnerTest(unittest.TestCase):
    def run_tests(self, *args):
        return subprocess.run([sys.executable, str(Path(HERE, "run.py"))] + list(args),
                              cwd=ROOT, capture_output=True, text=True, timeout=20)

    def test_file_arguments_run_only_the_named_modules(self):
        result = self.run_tests("kit/tests/test_parse_block_annotated_path.py",
                                str(Path(HERE, "test_parse_block_blank_after_header.py")))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 3)
        self.assertIn("test_parse_block_annotated_path", result.stdout)
        self.assertIn("test_parse_block_blank_after_header", result.stdout)
        self.assertIn("2 tests in 2 modules, 0 failed,", result.stdout)

    def test_an_enclosing_loop_does_not_redirect_fixture_disk_checks_or_events(self):
        with tempfile.TemporaryDirectory() as project:
            with mock.patch.dict(os.environ, {"LOOP_PROJECT": project}):
                result = self.run_tests("kit/tests/test_runner_disk_isolation.py")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(project, ".loop").exists())

    def test_module_arguments_run_only_the_named_module(self):
        for name in ("test_parse_block_annotated_path", "kit.tests.test_parse_block_annotated_path"):
            with self.subTest(name=name):
                result = self.run_tests(name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 2)
                self.assertIn("1 tests in 1 modules, 0 failed,", result.stdout)

    def test_help_prints_usage_without_running_tests(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                result = self.run_tests(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, Path(HERE, "run.py").read_text().split('"""')[1])
                self.assertEqual(result.stderr, "")

    def test_invalid_arguments_fail_before_running_any_tests(self):
        for arg in ("kit/tests/test_missing.py", "kit.tests.test_missing", "kit/tests/helpers.py", "--unknown"):
            with self.subTest(arg=arg):
                result = self.run_tests("test_parse_block_annotated_path", arg)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "No test module: %r\n" % arg)


if __name__ == "__main__":
    unittest.main()
