"""Test support files are reported, but are neither locked nor targeted."""
import os
from pathlib import Path
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
from kit.tests.test_guard import GuardCase
import common
import merge


SUPPORT = ("kit/tests/helpers.py", "kit/tests/run.py", "kit/tests/fake_codex.py",
           "tests/fixtures/data.json")


class TestModules(unittest.TestCase):
    def test_names_distinguish_modules_from_test_support_files(self):
        for path in SUPPORT:
            self.assertFalse(merge.is_test_module(path), path)
            self.assertTrue(merge.is_test_file(path), path)
        for path in ("test_a.py", "a_test.go", "a_spec.rb", "a.test.js", "a.spec.ts",
                     "tests.py", "test.py", "conftest.py", "src/FooTest.java"):
            self.assertTrue(merge.is_test_module(path), path)
        self.assertFalse(merge.is_test_module("tests/__pycache__/test_a.pyc"))

    def test_check_diff_allows_existing_support_but_locks_existing_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _ = make_repo(tmp, {p: "old\n" for p in SUPPORT + ("tests/test_a.py",)})
            base = common.git(["rev-parse", "HEAD"], cwd=work)
            for path in SUPPORT:
                Path(work, path).write_text("changed\n")
            run_git(["commit", "-am", "Support"], work)
            self.assertIsNone(merge.check_diff(work, base, "HEAD", [], set(), SUPPORT, base))
            Path(work, "tests/test_a.py").write_text("changed\n")
            run_git(["commit", "-am", "Module"], work)
            self.assertIn("existing test file changed: tests/test_a.py",
                          merge.check_diff(work, base, "HEAD", [], set(), []))

    def test_targeted_command_filters_support_from_changed_and_locked_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _ = make_repo(tmp, {p: "old\n" for p in SUPPORT})
            base = common.git(["rev-parse", "HEAD"], cwd=work)
            for path in SUPPORT + ("kit/tests/test_new.py",):
                Path(work, path).write_text("new\n")
            run_git(["add", "-A"], work)
            command, _ = merge.targeted_command({"Test command": "false",
                "Test files command": "echo {files}"}, work, base, SUPPORT + ("tests/test_locked.py",))
            self.assertEqual(command, "echo kit/tests/test_new.py tests/test_locked.py")


class SupportGuard(GuardCase):
    def test_builder_can_change_existing_support_but_not_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _ = make_repo(tmp, {p: "old\n" for p in SUPPORT + ("tests/test_a.py",)})
            start = common.git(["rev-parse", "HEAD"], cwd=work)
            for path in SUPPORT:
                self.allowed(self.call("Edit", {"file_path": os.path.join(work, path),
                    "old_string": "old", "new_string": "new"}, role="builder", cwd=work,
                    start=start, locked=list(SUPPORT)))
            self.refused(self.call("Edit", {"file_path": os.path.join(work, "tests/test_a.py"),
                "old_string": "old", "new_string": "new"}, role="builder", cwd=work,
                start=start), "existing test file")
