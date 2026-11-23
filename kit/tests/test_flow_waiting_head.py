"""A merge waiting for the loop branch does not consume another build round."""
import fcntl
from pathlib import Path
import unittest
from unittest import mock

import common
import merge
from kit.tests import test_flow
from kit.tests.helpers import run_git


class WaitingHeadTest(unittest.TestCase):
    def test_build_waits_without_the_merge_lock_then_retries_after_the_head_moves(self):
        test_flow.FlowTest.setUpClass()
        self.addCleanup(test_flow.FlowTest.tearDownClass)
        f = test_flow.FlowTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.tearDown)
        f.build_scenario(builder=[{"files": {"app.py": "1\n"}, "passed": True}])
        f.merge.side_effect = [
            merge.Result(False, False, "waiting for failing loop head", None, "loop-head-failed"),
            test_flow.MERGED,
        ]
        sleeps = []

        def move_head(seconds):
            sleeps.append(seconds)
            with Path(f.work, ".loop/merge.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if len(sleeps) == 2:
                run_git(["commit", "--allow-empty", "-m", "advance loop head"], f.work)
                run_git(["push", "origin", "HEAD:loop/main"], f.work)

        with mock.patch.object(common, "sleep", side_effect=move_head):
            result = f.build()
        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(sleeps, [60, 60])
        self.assertEqual(f.merge.call_count, 2)
        self.assertEqual(test_flow.roles(f.claude_calls()), ["test-writer", "builder", "reviewer"])
