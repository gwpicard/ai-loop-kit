import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

import common
import loop


class BoardActivityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.tmp.name
        self.st = loop.new_state()
        self.st["factory"] = {"number": 1, "body": ""}

    def board(self):
        with mock.patch.object(loop, "gh"):
            loop.write_board(self.project, self.st)
        return self.st["factory"]["body"]

    def test_step_elapsed_minutes_and_parked_label(self):
        path = Path(common.build_file(self.project, 8, "step"))
        path.parent.mkdir(parents=True)
        path.write_text("fix round 2")
        os.utime(path, (600, 600))
        self.st["building"] = {8: ("10:00", None), 9: ("10:00", None)}
        self.st["issues"] = [{"number": 9, "title": "Decision", "body": "", "labels": {"needs-user"}}]
        with mock.patch.object(loop.time, "time", return_value=900):
            body = self.board()
        building = body.split("## Needs you")[0]
        self.assertIn("#8, fix round 2", building)
        self.assertIn("5 min in step", building)
        self.assertNotIn("#9", building)

    def test_park_event_hides_build_before_snapshot_catches_up(self):
        common.event("step", self.project, issue=8, step="builder")
        common.event("parked", self.project, issue=8, reason="Decision")
        self.st["building"] = {8: ("10:00", None)}
        self.assertNotIn("#8", self.board().split("## Needs you")[0])

    def test_why_idle_names_parked_dependency(self):
        self.st["issues"] = [
            {"number": 8, "title": "Waiting", "body": "Depends on: #9", "labels": {"ready"}},
            {"number": 9, "title": "Decision", "body": "", "labels": {"needs-user"}}]
        self.assertIn("Why idle: dependencies held by needs-user: #9 Decision", self.board())

    def test_why_idle_names_load_and_memory_deferral(self):
        self.st["issues"] = [{"number": 8, "title": "Waiting", "body": "", "labels": {"ready"}}]
        for reason in ("load", "memory"):
            self.st["deferred"] = reason
            self.assertIn("Why idle: deferred for " + reason, self.board())

    def test_drain_updates_board_before_work_starts(self):
        def drain(*args):
            self.assertIn("draining", self.st["factory"]["body"].split("## Needs you")[0])
        with mock.patch.object(loop, "gh"), mock.patch.object(loop, "_drain", side_effect=drain):
            loop.drain(self.project, {}, self.st)

    def test_pass_event_is_shown(self):
        common.event("drain", self.project, phase="start")
        common.event("pass", self.project, phase="start")
        self.assertIn("running the end-of-loop pass", self.board().split("## Needs you")[0])

    def test_board_is_updated_before_pass_session(self):
        Path(self.project, ".loop").mkdir()
        def run_pass(*args, **kwargs):
            self.assertIn("running the end-of-loop pass", self.st["factory"]["body"].split("## Needs you")[0])
            return {}, ""
        with mock.patch.object(common, "default_branch", return_value="main"), \
                mock.patch.object(loop, "git", side_effect=["head", "- Issue built"]), \
                mock.patch.object(loop.merge, "run_tests", return_value=None), \
                mock.patch.object(loop.pass_, "run_pass", side_effect=run_pass), \
                mock.patch.object(loop, "summary", return_value=""), \
                mock.patch.object(loop.report, "render", return_value=""), \
                mock.patch.object(loop, "hands_on", return_value=""), \
                mock.patch.object(loop, "decisions", return_value=""), \
                mock.patch.object(loop, "gh", return_value="[]"):
            loop._drain(self.project, {"Loop branch": "loop/main", "Test command": "true",
                        "Check command": "", "Prepare command": ""}, self.st)

    def test_next_check_has_a_date(self):
        Path(self.project, "AGENTS.md").write_text("## Loop\nTest command: true\nIdle hours: 12\n")
        Path(self.project, ".loop").mkdir()
        def snapshot(st):
            st["factory"] = self.st["factory"]
        def stop(seconds):
            Path(self.project, ".loop/stop").touch()
        bodies = []
        with mock.patch.object(loop, "snapshot", side_effect=snapshot), \
                mock.patch.object(loop, "sync_default", return_value=False), \
                mock.patch.object(loop, "drain"), mock.patch.object(loop, "clean_up"), \
                mock.patch.object(loop, "gh", side_effect=lambda *a, **kw: bodies.append(kw.get("input", ""))), \
                mock.patch.object(loop.time, "sleep", side_effect=stop):
            loop.run(self.project)
        self.assertTrue(any(re.search(r"Next check: \d{4}-\d\d-\d\d \d\d:\d\d", b) for b in bodies))


if __name__ == "__main__":
    unittest.main()
