"""A locked test must keep its file type as well as its blob contents."""
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
import common
import merge


class LockedSymlinkTest(unittest.TestCase):
    def test_builder_cannot_replace_a_locked_test_with_a_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"app.py": "pass\n"})
            base = common.git(["rev-parse", "HEAD"], cwd=work)
            tests = os.path.join(work, "tests")
            os.mkdir(tests)
            path = os.path.join(tests, "test_feature.py")
            with open(path, "w") as stream:
                stream.write("raise AssertionError")
            run_git(["add", "tests/test_feature.py"], work)
            run_git(["commit", "-m", "Write the acceptance test"], work)
            baseline = common.git(["rev-parse", "HEAD"], cwd=work)
            before = subprocess.run([sys.executable, path], capture_output=True, text=True)
            self.assertNotEqual(before.returncode, 0)
            self.assertIn("AssertionError", before.stderr)

            with open(os.path.join(tests, "raise AssertionError"), "w") as stream:
                stream.write("pass\n")
            os.unlink(path)
            os.symlink("raise AssertionError", path)
            run_git(["add", "tests"], work)
            run_git(["commit", "-m", "Replace the acceptance test"], work)
            head = common.git(["rev-parse", "HEAD"], cwd=work)
            after = subprocess.run([sys.executable, path], capture_output=True, text=True)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertIsNotNone(
                merge.check_diff(work, base, head, [], set(),
                                 ["tests/test_feature.py"], baseline),
                "The merge check accepted a symlink that replaces the failing locked test")


if __name__ == "__main__":
    unittest.main()
