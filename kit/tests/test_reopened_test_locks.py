"""Reopened builds discard old test metadata and enforce their own test locks."""
import json
from pathlib import Path
import shlex
import sys
from unittest import mock

from kit.tests import test_reopened_after_revert as reopened
from kit.tests.helpers import run_git
import merge


TEST = ("from pathlib import Path\nimport unittest\n\n"
        "class FeatureTest(unittest.TestCase):\n"
        "    def test_feature(self):\n"
        "        self.assertTrue(Path('feature.txt').is_file())\n")


class ReopenedTestLocksTest(reopened.ReopenedAfterRevertTest):
    def revert_and_reopen(self):
        super().revert_and_reopen()
        run_git(["switch", "loop/main"], self.work)
        settings = json.loads(Path(self.work, "loop.json").read_text())
        settings["Test files command"] = shlex.quote(sys.executable) + " -m unittest {files}"
        Path(self.work, "loop.json").write_text(json.dumps(settings))
        Path(self.work, "tests/__init__.py").touch()
        run_git(["add", "loop.json", "tests/__init__.py"], self.work)
        run_git(["commit", "-qm", "Configure targeted tests"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.loop_head = reopened.REAL_GIT(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["switch", "main"], self.work)

    def build(self):
        old = {"body": "TESTS:\ntests/test_original.py\n\nCommit: " + self.old_head,
               "createdAt": reopened.MERGED_AT}
        if old not in self.comments:
            self.comments.insert(0, old)
        return super().build()

    def github(self, args, **kwargs):
        result = super().github(args, **kwargs)
        if args[:2] == ["issue", "comment"] and kwargs["input"].startswith("TESTS:"):
            self.comments[-1]["createdAt"] = reopened.REOPENED_AT
        return result

    def configure_build(self, builder):
        self.claude({
            "test-writer": [{"files": {"tests/test_rebuilt.py": TEST},
                             "reply": "TESTS:\ntests/test_rebuilt.py"}],
            "builder": builder,
            "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}],
        })

    def test_retry_keeps_only_the_current_reopening_test_locks(self):
        self.revert_and_reopen()
        self.configure_build([
            {"reply": "PARK: Which feature variant? | Keep the original."},
            {"files": {"feature.txt": "rebuilt implementation\n"},
             "reply": "BUILT:\nRestored the feature.\nDEVIATIONS:\nnone"},
        ])
        self.assertEqual(self.build().status, "parked")
        self.assertFalse(Path(self.work, "tests/test_original.py").exists())
        with mock.patch.object(merge, "full_suite_due", return_value=False):
            result = self.build()
        self.assertEqual(result.status, "merged", result.reason)
        calls = self.claude_calls()
        self.assertEqual([c["role"] for c in calls].count("test-writer"), 1)
        for call in calls:
            if call["role"] == "builder":
                self.assertEqual(call["env"]["LOOP_LOCKED"], "tests/test_rebuilt.py")
        self.assertEqual(self.new_pr["state"], "MERGED")

    def test_current_test_lock_still_blocks_a_rewrite(self):
        self.revert_and_reopen()
        self.configure_build([{
            "files": {"feature.txt": "rebuilt implementation\n",
                      "tests/test_rebuilt.py": TEST + "\n# Changed after the writer committed.\n"},
            "reply": "BUILT:\nRestored the feature.\nDEVIATIONS:\nnone",
        }])
        result = self.build()
        self.assertEqual(result.status, "parked", result.reason)
        self.assertIn("locked test modified: tests/test_rebuilt.py", result.reason)
        self.assertEqual(self.issue_state, "OPEN")
        self.assertIsNone(self.new_pr)

    def test_undated_test_comments_keep_their_locks(self):
        self.revert_and_reopen()
        self.comments = [{"body": "TESTS:\ntests/test_missing_date.py\n"}]
        self.configure_build([
            {"reply": "PARK: Which feature variant? | Keep the original."},
            {"reply": "PARK: Which feature variant? | Keep the original."},
        ])
        self.assertEqual(self.build().status, "parked")
        self.assertEqual(self.build().status, "parked")
        builder = [c for c in self.claude_calls() if c["role"] == "builder"][-1]
        self.assertEqual(set(builder["env"]["LOOP_LOCKED"].splitlines()),
                         {"tests/test_missing_date.py", "tests/test_rebuilt.py"})
