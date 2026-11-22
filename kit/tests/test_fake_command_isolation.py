"""Replacing or editing a private fake cannot change a shared command."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import HERE, FakeGh, write_exe


class FakeCommandIsolationTest(unittest.TestCase):
    def test_workers_publish_one_complete_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            text = '#!PYTHON\nprint("concurrent publication")\n'
            # Establish the cache environment before starting independent workers.
            write_exe(Path(folder, "initial"), '#!PYTHON\nprint("initial")\n')
            paths = [Path(folder, str(i)) for i in range(8)]
            processes = []
            try:
                for path in paths:
                    processes.append(subprocess.Popen([
                        sys.executable, "-c",
                        "import sys; from kit.tests.helpers import write_exe; write_exe(sys.argv[1], sys.argv[2])",
                        str(path), text], cwd=Path(HERE).parent.parent,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                for process in processes:
                    out, err = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, out + err)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            self.assertTrue(all(path.is_symlink() for path in paths))
            self.assertEqual(len({path.resolve() for path in paths}), 1)
            result = subprocess.run([str(paths[0])], capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (0, "concurrent publication\n"), result.stderr)

    def test_replacing_a_link_does_not_change_another_command(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder, "one"), Path(folder, "two")
            original = '#!PYTHON\nprint("original")\n'
            write_exe(first, original)
            write_exe(second, original)
            write_exe(first, '#!PYTHON\nprint("replacement")\n')
            self.assertNotEqual(first.resolve(), second.resolve())
            result = subprocess.run([str(second)], capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (0, "original\n"), result.stderr)

    def test_private_copy_can_be_edited_without_changing_the_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            shared, private = Path(folder, "shared"), Path(folder, "private")
            text = '#!PYTHON\nprint("original")\n'
            write_exe(shared, text)
            write_exe(private, text)
            write_exe(private, text, shared=False)
            self.assertFalse(private.is_symlink())
            private.write_text(private.read_text().replace("original", "edited"))
            self.assertIn("original", shared.read_text())
            result = subprocess.run([str(private)], capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (0, "edited\n"), result.stderr)


class DockerIsolationTest(FakeGh):
    def test_docker_stub_is_private_for_tests_that_overwrite_it(self):
        self.assertFalse(Path(self.tmp, "bin", "docker").is_symlink())
