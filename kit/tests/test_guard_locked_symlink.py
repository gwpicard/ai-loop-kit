"""A locked test's symlink target stays locked even without a test filename."""
import os
import tempfile
import unittest

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GuardCase


class LockedSymlinkGuardTest(GuardCase):
    def test_writes_through_a_locked_symlink_or_to_its_target_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/raise AssertionError": "pass\n"})
            locked = "tests/test_feature.py"
            os.symlink("raise AssertionError", os.path.join(work, locked))
            for path in (locked, "tests/raise AssertionError"):
                for role in ("builder", "test-writer"):
                    for tool in ("Write", "Edit"):
                        with self.subTest(path=path, role=role, tool=tool):
                            result = self.call(tool, {"file_path": path, "content": "pass\n"},
                                               role=role, locked=[locked], cwd=work)
                            self.refused(result, "locked test")
                            self.assertIn("rule: test-lock\n", result.stderr)


if __name__ == "__main__":
    unittest.main()
