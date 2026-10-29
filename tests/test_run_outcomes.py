"""Tests for builder stop outcomes."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_fixtures

# isort: split

import gate
import run
import walkaway
from loopkit import records


class BuilderOutcomeTest(unittest.TestCase):
    def setUp(self):
        run_fixtures.RunFixture.setUp(self)

    def test_needs_answer_returns_question_to_shaping(self):
        n, result = run_fixtures.RunFixture.build(self, "needs-answer", attempts=3)
        self.assertIn("Should this limiter use shared storage?", result)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        run_fixtures.RunFixture.assert_handback_record(self, handback, reason_type="spec-unclear",
                                                cause="needs-answer", attempts=1)
        self.assertEqual(handback["reason"], "Should this limiter use shared storage?")
        self.assertIn("needs-you", self.p.gh.issue(n)["labels"])

    def test_cited_spec_unclear_returns_to_shaping(self):
        n, result = run_fixtures.RunFixture.build(self, "spec-unclear", attempts=3)
        self.assertIn("The required interface is unspecified", result)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        run_fixtures.RunFixture.assert_handback_record(self, handback, reason_type="spec-unclear",
                                                cause="spec-unclear", attempts=1)
        self.assertIn("Citation: habits.py:1", handback["reason"])
        self.assertEqual(len(handback["reason"].split("\nCitation:")[0]), 500)

    def test_spec_unclear_accepts_spaces_in_file_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            outcome = Path(directory) / "outcome"
            outcome.write_text("spec-unclear\nReason: See the source.\n"
                               "Citation: src/my module.py:12\n")
            kind, reason = walkaway.builder_outcome(outcome)
        self.assertEqual(kind, "spec-unclear")
        self.assertIn("Citation: src/my module.py:12", reason)

    def test_uncited_spec_unclear_counts_as_a_failed_attempt(self):
        n, result = run_fixtures.RunFixture.build(self, "uncited-spec-unclear", attempts=2)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        self.assertEqual(handback["type"], "builder-failed")
        self.assertNotEqual(handback["cause"], "needs-answer")
        attempts = [c for c in self.p.gh.comments(n)
                    if c.startswith("**Run:** attempt")]
        self.assertEqual(len(attempts), 2)
        self.assertIn("back to shaping", result)
        self.assertEqual(sum("spec-unclear needs a question or a cited reason" in c
                             for c in self.p.gh.comments(n)), 2)


class RequeueTest(unittest.TestCase):
    def setUp(self):
        run_fixtures.RunFixture.setUp(self)

    def moves(self, n):
        return [r["move"] for r in records(self.p.gh.comments(n))]

    def crash_run(self, n):
        with patch("review._review_session", side_effect=OSError("cannot start")):
            return run.build_piece(self.p.gh, self.p.root, n, 1)

    def test_reviewer_crash_returns_the_piece_to_ready(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = self.crash_run(n)
        self.assertIn("returned to ready", result)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:ready", labels)
        self.assertNotIn("needs-you", labels)
        requeue = records(self.p.gh.comments(n))[-1]
        self.assertEqual((requeue["move"], requeue["type"], requeue["cause"]),
                         ("requeue", "environment", "run-error"))
        self.assertEqual(requeue["attempts"], 1)
        self.assertIn("environment / run-error: 1", gate.report(self.p.gh))

    def test_the_third_fault_goes_to_shaping_with_needs_you(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        for _ in range(2):
            self.crash_run(n)
        self.assertEqual(self.moves(n).count("requeue"), 2)
        result = self.crash_run(n)
        self.assertIn("back to shaping", result)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:shaping", labels)
        self.assertIn("needs-you", labels)
        handback = records(self.p.gh.comments(n))[-1]
        self.assertEqual(handback["move"], "give-back")
        self.assertTrue(handback["reason"].startswith("returned to ready twice; "))
        self.assertEqual(handback["type"], "environment")

    def test_a_fresh_ready_record_resets_the_count(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        for _ in range(2):
            self.crash_run(n)
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="reshape",
                  reason_type="spec-unclear")
        gate.move(self.p.gh, self.p.root, n, "ready")
        self.crash_run(n)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.moves(n)[-1], "requeue")

    def test_a_requeue_keeps_the_ready_record(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        before = self.moves(n).count("ready")
        self.crash_run(n)
        self.assertEqual(self.moves(n).count("ready"), before)
        self.assertEqual(gate.check_frozen(self.p.gh.issue(n), self.p.gh.comments(n))["move"],
                         "ready")

    def test_a_dirty_folder_still_goes_to_shaping(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        self.crash_run(n)
        (self.p.folder(n) / "stray.txt").write_text("left by hand\n")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        self.assertIn("needs-you", self.p.gh.issue(n)["labels"])
