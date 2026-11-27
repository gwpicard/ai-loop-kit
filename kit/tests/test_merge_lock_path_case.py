"""Locked paths follow Git's path casing on case-insensitive repositories."""
import os
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
import common
import merge


class LockPathCaseTest(unittest.TestCase):
    def check_change(self, delete=False, baseline=True, ignorecase=True):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"app.py": "pass\n"})
            base = common.git(["rev-parse", "HEAD"], cwd=work)
            path = "Tests/test_feature.py"
            os.mkdir(os.path.join(work, "Tests"))
            full = os.path.join(work, path)
            with open(full, "w") as stream:
                stream.write("raise AssertionError\n")
            run_git(["add", path], work)
            run_git(["commit", "-m", "Write the acceptance test"], work)
            writer = common.git(["rev-parse", "HEAD"], cwd=work)
            run_git(["config", "core.ignorecase", str(ignorecase).lower()], work)
            if delete:
                os.unlink(full)
            else:
                with open(full, "w") as stream:
                    stream.write("pass\n")
            run_git(["add", "-A"], work)
            run_git(["commit", "-m", "Change the locked test"], work)
            head = common.git(["rev-parse", "HEAD"], cwd=work)
            return merge.check_diff(work, base, head, [], set(), ["tests/test_feature.py"],
                                    writer if baseline else None)

    def test_modified_alias_is_locked_at_the_writer_commit(self):
        self.assertEqual(self.check_change(), "locked test modified: tests/test_feature.py")

    def test_deleted_alias_is_locked_at_the_writer_commit(self):
        self.assertEqual(self.check_change(delete=True), "locked test deleted: tests/test_feature.py")

    def test_modified_alias_is_locked_without_a_posted_baseline(self):
        self.assertEqual(self.check_change(baseline=False), "locked test modified: tests/test_feature.py")

    def test_case_sensitive_repositories_keep_distinct_paths(self):
        self.assertIsNone(self.check_change(ignorecase=False))
