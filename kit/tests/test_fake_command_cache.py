"""Fake commands share executable files across the test run's processes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests import helpers


class FakeCommandCacheTest(unittest.TestCase):
    def test_identical_commands_share_a_file_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second, different = [Path(folder, name) for name in ("one", "two", "other")]
            text = '#!PYTHON\nprint("cache example")\n'
            helpers.write_exe(first, text)
            before = first.stat()
            helpers.write_exe(second, text)
            helpers.write_exe(different, '#!PYTHON\nprint("different example")\n')
            for path in (first, second, different):
                self.assertTrue(path.is_symlink(), str(path) + " must point at the shared cache")
                self.assertTrue(os.access(path, os.X_OK))
                self.assertTrue(path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
                self.assertFalse(path.resolve().is_relative_to(Path(folder).resolve()))
            self.assertEqual(first.resolve(), second.resolve())
            self.assertNotEqual(first.resolve(), different.resolve())
            self.assertEqual((first.stat().st_ino, first.stat().st_mtime_ns),
                             (before.st_ino, before.st_mtime_ns))
            result = subprocess.run([str(second)], capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (0, "cache example\n"), result.stderr)
            with mock.patch.object(helpers.sys, "executable", "/another/python"):
                interpreter = Path(folder, "interpreter")
                helpers.write_exe(interpreter, text)
            self.assertTrue(interpreter.is_symlink())
            self.assertNotEqual(interpreter.resolve(), first.resolve())
            self.assertTrue(interpreter.read_text().startswith("#!/another/python -S\n"))

    def test_a_second_process_reuses_the_same_cached_command(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder, "parent"), Path(folder, "child")
            text = '#!PYTHON\nprint("shared between workers")\n'
            helpers.write_exe(first, text)
            before = first.stat()
            result = subprocess.run([
                sys.executable, "-c",
                "import sys; from kit.tests.helpers import write_exe; write_exe(sys.argv[1], sys.argv[2])",
                str(second), text], cwd=Path(helpers.HERE).parent.parent,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(first.is_symlink(), "the first process must use the cache")
            self.assertTrue(second.is_symlink(), "the second process must use the cache")
            self.assertEqual(first.resolve(), second.resolve())
            self.assertEqual((second.stat().st_ino, second.stat().st_mtime_ns),
                             (before.st_ino, before.st_mtime_ns))
