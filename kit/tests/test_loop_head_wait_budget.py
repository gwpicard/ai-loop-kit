"""Exercise supervisor timeout accounting during and after a loop-head wait."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import common
import loop
import merge
from kit.tests import test_flow
from kit.tests.helpers import run_git


class LoopHeadWaitBudgetTest(unittest.TestCase):
    def test_wait_beyond_the_build_cap_preserves_the_worker_and_crash_attempts(self):
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
        proc = mock.Mock(pid=12345, returncode=None)
        proc.poll.return_value = None
        st = loop.new_state()
        st["building"][7] = ("fixture", proc)
        st["deaths"][7] = st["attempts"][7] = 1
        cap = 165 * 60
        path = Path(common.build_file(f.work, 7, "loop-wait"))
        waits = []

        def reap_at(now):
            with mock.patch.object(common.time, "time", return_value=now), \
                    mock.patch.object(loop.os, "killpg") as kill, \
                    mock.patch.object(common, "park") as park:
                loop.reap(f.work, st, cap=cap)
            kill.assert_not_called()
            park.assert_not_called()
            self.assertIn(7, st["building"])
            self.assertEqual(st["deaths"], {7: 1})
            self.assertEqual(st["attempts"], {7: 1})

        def waiting(seconds):
            self.assertEqual(seconds, 60)
            began = float(path.read_text().strip())
            st["started"][7] = began - 10
            waits.append(began)
            reap_at(began + cap * 2)
            run_git(["commit", "--allow-empty", "-m", "advance loop head"], f.work)
            run_git(["push", "origin", "HEAD:loop/main"], f.work)

        with mock.patch.object(common, "sleep", side_effect=waiting):
            result = f.build()
        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(len(waits), 1)
        begin, end = map(float, path.read_text().splitlines()[-1].split())
        self.assertEqual(begin, waits[0])
        # Model a completed long wait and verify that only later active time counts.
        end = begin + cap * 2
        path.write_text("%s\n%s %s\n" % (begin, begin, end))
        reap_at(end + 10)
        # Once active work exceeds its budget, the normal timeout still applies.
        with mock.patch.object(common.time, "time", return_value=end + cap + 1), \
                mock.patch.object(loop.os, "killpg") as kill:
            loop.reap(f.work, st, cap=cap)
        kill.assert_called_once()
        proc.wait.assert_called_once()

    def test_loop_wait_records_are_removed_when_the_worker_is_reaped(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        project = folder.name
        path = Path(common.build_file(project, 7, "loop-wait"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("100 200\n")
        Path(common.build_file(project, 7, "result")).write_text('{"last": "fixture finished"}')
        proc = mock.Mock()
        proc.poll.return_value = 0
        st = loop.new_state()
        st["building"][7] = ("fixture", proc)
        loop.reap(project, st)
        self.assertFalse(path.exists())
