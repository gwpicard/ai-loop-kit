import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import common
import loop


class ParkThroughputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.tmp.name

    def refuse(self, issue):
        env = dict(os.environ, LOOP_ROLE="builder", LOOP_PROJECT=self.project, LOOP_ISSUE=str(issue))
        env.pop("LOOP_AGENT", None)
        guard = Path(__file__).resolve().parents[1] / "hooks/guard.py"
        result = subprocess.run([sys.executable, str(guard)], env=env, text=True, capture_output=True,
                                input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git merge other"}}))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("rule: role-git", result.stderr)

    def park(self, issue):
        with mock.patch.object(common, "gh"):
            common.park(issue, "A decision", "Decide", project=self.project)

    def status(self, *args):
        output = io.StringIO()
        now = time.time() + 2
        with mock.patch.object(loop.os, "getcwd", return_value=self.project), \
                mock.patch.object(loop.time, "time", return_value=now), \
                mock.patch.object(loop, "gh", side_effect=AssertionError("network")), \
                contextlib.redirect_stdout(output):
            self.assertEqual(loop.main(["status", *args]), 0)
        return output.getvalue()

    def test_guard_rule_survives_real_park_and_status(self):
        self.refuse(7)
        common.event("session", self.project, issue=7, role="builder")
        common.event("step", self.project, issue=7, step="builder", phase="end", seconds=1)
        common.event("rule", self.project, issue=8, rule="protected-path")
        with Path(self.project, ".loop/events.jsonl").open("a") as f:
            f.write('{"partial":\n')
        self.park(7)
        events = [json.loads(line) for line in Path(self.project, ".loop/events.jsonl").read_text().splitlines()
                  if not line.startswith('{"partial":')]
        self.assertEqual(events[-1].get("rule"), "role-git")
        report = json.loads(self.status("--json"))["throughput"]
        self.assertEqual(report["parks_by_rule"], {"role-git": 1})
        self.assertIn("Parks by rule: role-git=1", self.status())

    def test_previous_steps_and_other_issues_do_not_supply_a_rule(self):
        self.refuse(7)
        common.event("step", self.project, issue=7, step="builder", phase="start")
        self.refuse(8)
        self.park(7)
        self.park(8)
        self.park(8)
        report = json.loads(self.status("--json"))["throughput"]
        self.assertEqual(report["parks_by_rule"], {"unknown": 2, "role-git": 1})

    def test_park_without_events_stays_unknown(self):
        self.park(7)
        report = json.loads(self.status("--json"))["throughput"]
        self.assertEqual(report["parks_by_rule"], {"unknown": 1})


if __name__ == "__main__":
    unittest.main()
