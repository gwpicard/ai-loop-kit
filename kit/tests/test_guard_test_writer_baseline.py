import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
from kit.tests.test_guard import GUARD


class TestWriterBaselineTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work, _ = make_repo(folder.name, {
            "tests/test_existing.py": "assert True\n"})
        self.start = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.work, text=True).strip()
        run_git(["update-ref", "refs/remotes/origin/loop/main", self.start], self.work)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("LOOP_")}
        self.env.update(LOOP_ROLE="test-writer", LOOP_LOOP_BRANCH="loop/main")

    def edit(self, path, agent, role="test-writer"):
        if agent == "codex":
            tool = "apply_patch"
            inp = "*** Begin Patch\n*** Update File: %s\n@@\n-assert True\n+assert False\n*** End Patch\n" % path
        else:
            tool = "Edit"
            inp = {"file_path": path, "old_string": "True", "new_string": "False"}
        return subprocess.run(
            [sys.executable, GUARD], capture_output=True, text=True,
            env=dict(self.env, LOOP_AGENT=agent, LOOP_ROLE=role),
            input=json.dumps({"tool_name": tool, "tool_input": inp, "cwd": self.work}))

    def check_new_tests_remain_editable(self, explicit_start):
        if explicit_start:
            self.env["LOOP_START"] = self.start
        paths = ("tests/test_new.py", "tests/nested/test_other.py")
        for path in paths:
            full = os.path.join(self.work, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write("assert True\n")
        for state in ("untracked", "staged", "committed"):
            if state == "staged":
                run_git(["add", "--", *paths], self.work)
            elif state == "committed":
                run_git(["commit", "-m", "Add session tests"], self.work)
            for path in paths:
                for agent in ("claude", "codex"):
                    with self.subTest(state=state, path=path, agent=agent):
                        result = self.edit(path, agent)
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_tests_remain_editable_with_explicit_start(self):
        self.check_new_tests_remain_editable(explicit_start=True)

    def test_new_tests_remain_editable_with_merge_base(self):
        self.check_new_tests_remain_editable(explicit_start=False)

    def test_start_commit_tests_keep_existing_test_reason(self):
        for explicit_start in (True, False):
            if explicit_start:
                self.env["LOOP_START"] = self.start
            else:
                self.env.pop("LOOP_START", None)
            for agent in ("claude", "codex"):
                with self.subTest(explicit_start=explicit_start, agent=agent):
                    result = self.edit("tests/test_existing.py", agent)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("rule: test-lock\n", result.stderr)
                    self.assertIn("tests/test_existing.py is an existing test file", result.stderr)

    def test_reviewer_still_refuses_a_test_absent_from_start(self):
        self.env["LOOP_START"] = self.start
        path = "tests/test_new.py"
        with open(os.path.join(self.work, path), "w") as f:
            f.write("assert True\n")
        run_git(["add", "--", path], self.work)
        for agent in ("claude", "codex"):
            with self.subTest(agent=agent):
                result = self.edit(path, agent, role="reviewer")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("rule: role-write\n", result.stderr)
                self.assertIn("the reviewer edits nothing", result.stderr)


if __name__ == "__main__":
    unittest.main()
