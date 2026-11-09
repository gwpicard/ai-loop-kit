# Intent: a rejected piece is rebuilt with the reason and its rejected commit is never submitted again.
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import git
from run_fixtures import RunFixture

# isort: split

import gate
import run
from loopkit import records

GOOD = "def add(items, name):\n    return items if name in items else items + [name]\n"
REASON = "Rename nothing, but explain the duplicate check in a comment"


def commit_variant(folder, note):
    (folder / "habits.py").write_text(GOOD + f"# {note}\n")
    git(folder, "add", "habits.py")
    git(folder, "commit", "--quiet", "-m", f"Variant {note}")


class RebuildAfterRejectTest(RunFixture, unittest.TestCase):
    def submits(self, n):
        return [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"]

    def rejected_piece(self):
        """Build and submit a piece, then reject it and queue it again."""
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        rejected = self.submits(n)[-1]["commit"]
        gate.move(self.p.gh, self.p.root, n, "shaping", reason=REASON,
                  reason_type="person-rejected")
        gate.move(self.p.gh, self.p.root, n, "ready")
        return n, rejected

    def run_with_builders(self, n, behaviours, attempts=2):
        """Run the piece; each builder call does the next behaviour: 'same' or a note."""
        prompts = []

        def builder(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            what = behaviours[len(prompts) - 1]
            if what != "same":
                commit_variant(folder, what)
            return ""

        with patch("run.build_once", side_effect=builder):
            result = run.build_piece(self.p.gh, self.p.root, n, attempts)
        return prompts, result

    def test_D1_a_rejected_build_that_passes_the_judge_starts_a_builder_with_the_reason(self):
        n, rejected = self.rejected_piece()
        prompts, result = self.run_with_builders(n, ["after the rejection"])
        self.assertEqual(len(prompts), 1)
        self.assertIn(REASON, prompts[0])
        submits = self.submits(n)
        self.assertEqual(len(submits), 2)
        self.assertNotEqual(submits[-1]["commit"], rejected)
        self.assertEqual(submits[-1]["attempts"], 1)
        self.assertIn("pull request ready", result)

    def test_D2_an_attempt_left_at_the_rejected_commit_is_not_submitted(self):
        n, rejected = self.rejected_piece()
        seen = []
        prompts = []

        def builder(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            seen.append(len(self.submits(n)))
            if len(prompts) == 2:
                commit_variant(folder, "second attempt")
            return ""

        with patch("run.build_once", side_effect=builder):
            run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertEqual(len(prompts), 2)
        self.assertEqual(seen, [1, 1])
        self.assertIn("rejected commit", prompts[1].lower())
        submits = self.submits(n)
        self.assertEqual(len(submits), 2)
        self.assertNotEqual(submits[-1]["commit"], rejected)
        self.assertEqual(submits[-1]["attempts"], 2)

    def test_D3_every_attempt_at_the_rejected_commit_hands_the_piece_back(self):
        n, rejected = self.rejected_piece()
        prompts, result = self.run_with_builders(n, ["same", "same"])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(len(self.submits(n)), 1)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assertIn(rejected[:7], handback["reason"])
        self.assertIn("back to shaping", result)

    def earlier_build(self, code):
        """A piece made ready, given earlier build code, then given back and queued again."""
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(code)
        git(self.p.root, "add", "habits.py")
        git(self.p.root, "commit", "--quiet", "-m", "Earlier build")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.p.gh, self.p.root, n, "building")
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="stopped by the person",
                  reason_type="stopped")
        gate.move(self.p.gh, self.p.root, n, "ready")
        return n

    def test_D4_a_given_back_piece_with_a_passing_earlier_build_goes_straight_to_review(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.earlier_build(GOOD)
        with patch("run.build_once") as builder:
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        builder.assert_not_called()
        self.assertIn("pull request ready", result)
        self.assertEqual(self.submits(n)[-1]["attempts"], 0)

    def test_D5_a_failing_earlier_build_starts_attempt_one_with_the_judge_output(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.earlier_build("def add(items, name):\n    return items\n")
        prompts, _ = self.run_with_builders(n, ["fixed"])
        self.assertEqual(len(prompts), 1)
        self.assertIn("The earlier build code failed", prompts[0])


if __name__ == "__main__":
    unittest.main()
