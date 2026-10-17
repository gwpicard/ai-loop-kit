"""Shared session execution retains each caller's evidence and retry policy."""
from __future__ import annotations

import helpers  # noqa: F401

# isort: split

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import agents
import gate
import procs
import review
import run
from loopkit import records
from run_fixtures import RunFixture


class SessionRunnerTest(RunFixture, unittest.TestCase):
    def limited_sessions(self, limited=(True, True)):
        processes = []

        def start(*args, **kwargs):
            is_error = limited[len(processes)]
            text = f"usage limit {len(processes) + 1}" if is_error else "completed"
            event = json.dumps({"type": "result", "is_error": is_error, "result": text})
            proc = subprocess.Popen(
                [sys.executable, "-c", f"print({event!r}, flush=True)"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            processes.append(proc)
            return proc

        return processes, start

    def assert_finished(self, processes):
        self.assertEqual(len(processes), 2)
        for proc in processes:
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(proc.stdout.closed)
            self.assertNotIn(proc.pid, procs._ACTIVE_GROUPS)
            self.assertFalse(procs.process_group_alive(proc.pid))

    def test_builder_twice_limited_returns_to_shaping_with_raw_events(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        processes, start = self.limited_sessions()
        with patch.object(agents, "start_session", side_effect=start), \
                patch.object(run.time, "sleep") as wait, \
                patch.object(run.walkaway, "approved_domains", return_value=[]):
            result = run.build_piece(self.p.gh, self.p.root, n, 3, walk_away=True)
        self.assert_finished(processes)
        wait.assert_called_once_with(1800)
        self.assertIn("remained rate limited", result)
        handback = records(self.p.gh.comments(n))[-1]
        self.assertEqual(handback["type"], "environment")
        self.assertEqual(handback["attempts"], 1)
        logfile = self.p.root / ".loop/logs" / f"piece-{n}-attempt-1.log"
        for text in ("usage limit 1", "usage limit 2"):
            self.assertIn(text, logfile.read_text())
            self.assertIn(text, logfile.with_suffix(".jsonl").read_text())
        self.assertNotIn(n, self.p.gh.prs)

    def test_reviewer_twice_limited_keeps_both_process_records(self):
        processes, start = self.limited_sessions()
        logfile = self.p.root / "review.log"
        with patch.object(agents, "start_session", side_effect=start), \
                patch.object(run.time, "sleep") as wait:
            status = review._review_session(self.p.root, "brief", logfile, [], 5,
                                             walk_away=True)
        self.assertEqual(status, "usage-limit")
        self.assert_finished(processes)
        wait.assert_called_once_with(1800)
        self.assertEqual((self.p.root / "reviewer-processes").read_text().splitlines(),
                         [str(proc.pid) for proc in processes])
        for text in ("usage limit 1", "usage limit 2",
                     "Usage limit; waiting 1800 seconds before one retry."):
            self.assertIn(text, logfile.read_text())
        self.assertFalse(logfile.with_suffix(".jsonl").exists())

    def test_shared_runner_keeps_raw_events_and_launch_options(self):
        import session

        processes, start = self.limited_sessions()
        logfile = self.p.root / "shared.log"
        event = {}
        with patch.object(agents, "start_session", side_effect=start) as launcher:
            status = session.run_session(
                self.p.root, "brief", logfile, 5, role="builder", backend="claude",
                result_event=event, raw_events=logfile.with_suffix(".jsonl"),
                disallowed=["judge.py"], settings_allowed=True,
                protected_paths=["private"], protected_exceptions=["private/ok"],
                contract={"D1": "build"}, walk_away=True, domains=["pypi.org"])
        self.assertEqual(status, "usage-limit")
        self.assertEqual(event["result"], "usage limit 1")
        self.assertEqual(processes[0].returncode, 0)
        self.assertEqual(launcher.call_args.kwargs, {
            "role": "builder", "disallowed": ["judge.py"], "settings_allowed": True,
            "protected_paths": ["private"], "protected_exceptions": ["private/ok"],
            "contract": {"D1": "build"}, "walk_away": True, "domains": ["pypi.org"]})
        self.assertEqual(json.loads(logfile.with_suffix(".jsonl").read_text()), event)

    def test_events_just_before_idle_deadline_reset_the_clock(self):
        import session
        from helpers import pump_events

        events = [json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": "at the deadline"}]}})] * 4
        status, output = pump_events(session, events, idle_seconds=2, clock_step=1.999)
        self.assertEqual(status, "")
        self.assertEqual(output.count("at the deadline"), 4)

    def test_reviewer_retry_success_does_not_reuse_the_limit_event(self):
        processes, start = self.limited_sessions((True, False))
        logfile = self.p.root / "review.log"
        with patch.object(agents, "start_session", side_effect=start), \
                patch.object(run.time, "sleep") as wait:
            status = review._review_session(self.p.root, "brief", logfile, [], 5,
                                             walk_away=True)
        self.assertEqual(status, "")
        self.assert_finished(processes)
        wait.assert_called_once_with(1800)
        self.assertIn("usage limit 1", logfile.read_text())

    def test_attended_reviewer_does_not_retry_a_usage_limit(self):
        processes, start = self.limited_sessions()
        with patch.object(agents, "start_session", side_effect=start), \
                patch.object(run.time, "sleep") as wait:
            status = review._review_session(self.p.root, "brief", self.p.root / "review.log", [], 5)
        self.assertEqual(status, "")
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].returncode, 0)
        wait.assert_not_called()
