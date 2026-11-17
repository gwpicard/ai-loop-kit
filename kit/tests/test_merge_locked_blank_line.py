import os
import subprocess
import tempfile
import unittest

import merge


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class LockedBlankLineTest(unittest.TestCase):
    def test_blank_line_after_tests_heading_does_not_lock_the_repository_root(self):
        body = "TESTS:\n\n- tests/test_a.py\n\nCommit: abcdef1\n"
        self.assertNotIn("", merge.locked_paths([{"body": body}]))

    def test_unrelated_source_change_is_not_a_locked_test_modification(self):
        with tempfile.TemporaryDirectory() as d:
            git(d, "init", "-q")
            git(d, "config", "user.email", "a@b")
            git(d, "config", "user.name", "a")
            os.makedirs(os.path.join(d, "tests"))
            with open(os.path.join(d, "tests", "test_a.py"), "w") as f:
                f.write("x\n")
            git(d, "add", "-A")
            git(d, "commit", "-qm", "base")
            base = git(d, "rev-parse", "HEAD")
            with open(os.path.join(d, "app.py"), "w") as f:
                f.write("y\n")
            git(d, "add", "-A")
            git(d, "commit", "-qm", "work")
            sha = git(d, "rev-parse", "HEAD")
            body = "TESTS:\n\n- tests/test_a.py\n\nCommit: %s\n" % base
            c = [{"body": body}]
            self.assertIsNone(merge.check_diff(d, base, sha, [], set(), merge.locked_paths(c), merge.locked_baseline(c)))


if __name__ == "__main__":
    unittest.main()
