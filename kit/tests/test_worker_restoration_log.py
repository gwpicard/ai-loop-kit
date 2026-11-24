"""A worker's restoration report survives the supervisor's next log write."""
import contextlib
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from kit.tests import test_loop_branch_restoration as fixtures
import common
import loop


class WorkerRestorationLogTest(unittest.TestCase):
    def test_worker_report_survives_supervisor_write(self):
        fixture = fixtures.BranchRestorationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        log = fixture.runtime / "loop.out"

        def start(project, settings, state):
            (fixture.runtime / "stop").touch()
            common.say("supervisor waiting for builds")
            fixture.delete_remote_branch()
            with (fixture.runtime / "worker.log").open("w") as worker:
                subprocess.run([
                    sys.executable, "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); import common; "
                    "common.restore_loop_branch(sys.argv[2], 'loop/main')",
                    str(Path(common.__file__).parent), fixture.work,
                ], stdout=worker, stderr=subprocess.STDOUT, check=True, timeout=30)
            self.assertIn("restored loop/main", log.read_text())
            common.say("supervisor resumed " + "next cycle " * 30)

        # The launch command redirects with >, leaving stdout without O_APPEND.
        with log.open("w") as supervisor, contextlib.redirect_stdout(supervisor), \
                mock.patch.object(loop, "snapshot"), \
                mock.patch.object(loop, "start_builds", side_effect=start), \
                mock.patch.object(loop, "write_board"), \
                mock.patch.object(loop, "clean_up"):
            self.assertEqual(loop.run(fixture.work), 0)
        self.assertEqual(fixture.remote_head(), fixture.old_head)
        self.assertEqual(len(fixture.pushes()), 1)
        fixture.assert_restoration_report("origin/loop/main")
        self.assertIn("supervisor waiting for builds", log.read_text())
        self.assertIn("supervisor resumed", log.read_text())
