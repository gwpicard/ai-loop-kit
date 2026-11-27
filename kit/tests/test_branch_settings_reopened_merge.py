"""Branch-only targeted settings also govern fresh and retried reopened merges."""
from pathlib import Path
import unittest
from unittest import mock

from kit.tests import test_reopened_test_locks as reopened
import merge


class BranchSettingsReopenedMergeTest(unittest.TestCase):
    def setUp(self):
        self.fixture = reopened.ReopenedTestLocksTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def rebuild(self, retry):
        fixture = self.fixture
        fixture.revert_and_reopen()
        builder = [{"files": {"feature.txt": "rebuilt implementation\n"},
                    "reply": "BUILT:\nRestored the feature.\nDEVIATIONS:\nnone"}]
        if retry:
            builder.insert(0, {"reply": "PARK: Which feature variant? | Keep the original."})
        fixture.configure_build(builder)
        if retry:
            self.assertEqual(fixture.build().status, "parked")
        with mock.patch.object(merge, "full_suite_due", return_value=False):
            result = fixture.build()
        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(fixture.new_pr["state"], "MERGED")
        log = Path(fixture.work, ".loop/logs/7-merge.log").read_text()
        self.assertIn("-m unittest tests/test_rebuilt.py", log)
        self.assertNotIn("tests/test_original.py", log)
        calls = fixture.claude_calls()
        self.assertEqual(sum(c["role"] == "test-writer" for c in calls), 1)
        for call in calls:
            if call["role"] == "builder":
                self.assertEqual(call["env"]["LOOP_LOCKED"], "tests/test_rebuilt.py")

    def test_reopened_merge_uses_branch_targeted_settings(self):
        self.rebuild(retry=False)

    def test_reopened_retry_uses_branch_targeted_settings(self):
        self.rebuild(retry=True)
