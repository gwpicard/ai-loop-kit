"""Tests for builder stop outcomes."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_run
import walkaway
from loopkit import records


class BuilderOutcomeTest(unittest.TestCase):
    def setUp(self):
        test_run.RunTest.setUp(self)

    def test_needs_answer_returns_question_to_shaping(self):
        n, result = test_run.RunTest.build(self, "needs-answer", attempts=3)
        self.assertIn("Should this limiter use shared storage?", result)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        test_run.RunTest.assert_handback_record(self, handback, reason_type="spec-unclear",
                                                cause="needs-answer", attempts=1)
        self.assertEqual(handback["reason"], "Should this limiter use shared storage?")
        self.assertIn("needs-you", self.p.gh.issue(n)["labels"])

    def test_cited_spec_unclear_returns_to_shaping(self):
        n, result = test_run.RunTest.build(self, "spec-unclear", attempts=3)
        self.assertIn("The required interface is unspecified", result)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        test_run.RunTest.assert_handback_record(self, handback, reason_type="spec-unclear",
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
        n, result = test_run.RunTest.build(self, "uncited-spec-unclear", attempts=2)
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
