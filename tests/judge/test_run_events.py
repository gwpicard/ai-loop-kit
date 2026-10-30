"""Local run events copy gate outcomes without copying private text."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import gate
import run
import run_cli
from loopkit import Refused


class RunEventsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()
        self.path = self.root / ".loop" / "events.jsonl"

    def events(self):
        self.assertTrue(self.path.is_file(), "the run must write .loop/events.jsonl")
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def piece(self, state):
        return self.gh.create_issue("A piece", "", ["state:" + state])

    def cli(self, arguments, **patches):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(run_cli, "repo_root", return_value=self.root))
        stack.enter_context(patch.object(run_cli, "GitHub", return_value=self.gh))
        stack.enter_context(patch.object(run_cli.signal, "signal"))
        stack.enter_context(patch.object(gate, "ignore_loop_folder"))
        stack.enter_context(patch.object(gate, "sync"))
        stack.enter_context(patch.object(run, "recover_building", return_value=[]))
        stack.enter_context(patch.object(run, "cleanup_interrupted_reviews", return_value=[]))
        stack.enter_context(patch.object(run, "ready_pieces", return_value=[]))
        for name, replacement in patches.items():
            stack.enter_context(patch.object(run, name, **replacement))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return run.main(["--attended", *arguments])

    def test_D1_each_successful_move_appends_one_event(self):
        for (before, after), name in gate.MOVES.items():
            with self.subTest(move=name, before=before):
                if before == "new":
                    continue
                number = self.piece(before)
                self.gh.prs[f"piece/{number}"] = {"state": "MERGED"}
                ready = {"checks": [], "keep": "", "bar": "", "regression": "true",
                         "regression_limit": 900, "test_lint_unchecked": []}
                count = len(self.events()) if self.path.exists() else 0
                with patch.object(gate, "check_ready", return_value=ready), \
                        patch.object(gate, "check_frozen", return_value=ready), \
                        patch.object(gate, "check_claim_bar"), \
                        patch.object(gate, "judge", return_value=(True, "")), \
                        patch.object(gate, "rev", return_value="commit"), \
                        patch.object(gate, "release_worktree"):
                    gate.move(self.gh, self.root, number, after, reason="person asked",
                              reason_type="stopped", attempts=2, folder=self.root)
                events = self.events()
                self.assertEqual(len(events), count + 1)
                event = events[-1]
                self.assertEqual(set(event),
                                 {"time", "piece", "event", "state", "attempt", "reason"})
                self.assertEqual((event["piece"], event["event"], event["state"],
                                  event["attempt"]), (number, name, after, 2))
                stamp = datetime.fromisoformat(event["time"])
                self.assertEqual(stamp.utcoffset(), timezone.utc.utcoffset(stamp))
                self.assertLess(abs((datetime.now(timezone.utc) - stamp).total_seconds()), 10)
                self.assertEqual(gate.state_of(self.gh.issue(number)), after)

    def test_D1_capture_records_the_initial_state(self):
        body = self.root / "body.md"
        body.write_text("body")
        with patch("gate_cli.repo_root", return_value=self.root), \
                patch("gate_cli.GitHub", return_value=self.gh), redirect_stdout(io.StringIO()):
            arguments = ["capture", "--title", "A piece", "--body-file", str(body)]
            self.assertEqual(gate.main(arguments), 0)
        self.assertEqual([(e["piece"], e["event"], e["state"], e["attempt"])
                          for e in self.events()], [(1, "capture", "shaping", 0)])

    def test_D1_refused_or_failed_label_change_writes_no_event(self):
        number = self.piece("shaping")
        with self.assertRaises(Refused):
            gate.move(self.gh, self.root, number, "done")
        with patch.object(self.gh, "set_labels", side_effect=RuntimeError("offline")), \
                self.assertRaises(RuntimeError):
            gate.move(self.gh, self.root, number, "dropped", reason="not needed")
        self.assertFalse(self.path.exists())

    def test_D2_empty_run_records_start_and_stop(self):
        self.assertEqual(self.cli([]), 0)
        events = self.events()
        self.assertEqual([e["event"] for e in events], ["run-start", "run-stop"])
        for event in events:
            self.assertIsNone(event["piece"])
            self.assertEqual(event["state"], "")
            self.assertEqual(event["attempt"], 0)
            self.assertTrue(event["reason"])

    def test_D2_interrupt_still_records_stop_and_releases_lock(self):
        number = self.piece("ready")
        with self.assertRaises(KeyboardInterrupt):
            self.cli([str(number)], build_piece={"side_effect": KeyboardInterrupt})
        self.assertEqual([e["event"] for e in self.events()], ["run-start", "run-stop"])
        self.assertFalse(run.lock_path(self.root).exists())

    def test_D2_handback_records_attempt_and_safe_reason(self):
        number = self.piece("building")
        with patch.object(gate, "release_worktree"):
            run._hand_back(self.gh, self.root, number, "the judge failed", "builder-failed",
                           {"attempts": 3, "started": time.monotonic()})
        event, = self.events()
        self.assertEqual((event["event"], event["state"], event["attempt"], event["reason"]),
                         ("give-back", "shaping", 3, "builder-failed"))

    def test_D3_untrusted_reasons_and_environment_values_stay_out(self):
        private = "private-environment-value ghp_example_token builder said private words"
        number = self.piece("building")
        with patch.dict(os.environ, {"DASHBOARD_PRIVATE": private}), \
                patch.object(gate, "release_worktree"):
            run._hand_back(self.gh, self.root, number, private, "environment",
                           {"attempts": 1, "started": time.monotonic()}, cause=private)
        self.assertEqual(self.events()[0]["reason"], "environment")
        self.assertNotIn(private, self.path.read_text())
        self.assertNotIn("ghp_example_token", self.path.read_text())
        self.assertIn(private, "\n".join(self.gh.comments(number)))

    def test_D3_untyped_moves_do_not_copy_unvalidated_reason_types(self):
        number = self.piece("shaping")
        with patch.object(gate, "release_worktree"):
            gate.move(self.gh, self.root, number, "dropped", reason="private words",
                      reason_type="private-token")
        self.assertEqual(self.events()[0]["reason"], "drop")
        self.assertNotIn("private", self.path.read_text())

    def test_D4_unwritable_events_warn_once_and_run_continues(self):
        self.path.parent.mkdir()
        self.path.mkdir()
        number = self.piece("ready")

        def build(*args):
            gate.move(self.gh, self.root, number, "shaping", reason="stop",
                      reason_type="stopped", attempts=1)
            return "back to shaping"

        errors = io.StringIO()
        with redirect_stderr(errors), patch.object(gate, "release_worktree"):
            status = self.cli([str(number)], build_piece={"side_effect": build})
        self.assertEqual(status, 1)
        self.assertEqual(gate.state_of(self.gh.issue(number)), "shaping")
        self.assertEqual(len(errors.getvalue().splitlines()), 1)
        self.assertIn("warning", errors.getvalue().lower())
        self.assertIn("events.jsonl", errors.getvalue())
        self.assertFalse(run.lock_path(self.root).exists())


if __name__ == "__main__":
    unittest.main()
