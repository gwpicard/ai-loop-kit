# Intent: a fix round shows in the pull request, and ends without a second review when it cannot help.
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

import run
from loopkit import records

GOOD = "def add(items, name):\n    return items if name in items else items + [name]\n"

# The fake build must not leave __pycache__ in the build folder.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def commit_variant(folder, note):
    (folder / "habits.py").write_text(GOOD + f"# {note}\n")
    git(folder, "add", "habits.py")
    git(folder, "commit", "--quiet", "-m", f"Variant {note}")


class FixRoundEndsTest(RunFixture, unittest.TestCase):
    def drive(self, fix, review_mode="contract-gap", after_review=None):
        """Build one piece. Builder call 1 is the attempt; any later call is the fix builder.

        fix(folder) runs in the fix builder and returns its status. Returns
        (n, number of builders, number of reviews, run result).
        """
        os.environ["FAKE_REVIEW_MODE"] = review_mode
        n = self.p.piece()
        from gate import move
        move(self.p.gh, self.p.root, n, "ready")
        calls = []
        reviews = []
        real_review = run.review_piece

        def builder(folder, prompt, *args, **kwargs):
            calls.append(prompt)
            if len(calls) == 1:
                commit_variant(folder, "first")
                return ""
            return fix(folder)

        def reviewer(*args, **kwargs):
            reviews.append(args)
            result = real_review(*args, **kwargs)
            if after_review:
                after_review()
            return result

        with patch("run.build_once", side_effect=builder), \
                patch("run.review_piece", side_effect=reviewer):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        return n, len(calls), len(reviews), result

    def body(self, n):
        return self.p.gh.prs[f"piece/{n}"]["body"]

    def head(self, n):
        return git(self.p.root, "rev-parse", f"piece/{n}").strip()

    def test_D1_a_fix_round_is_listed_in_the_pull_request_and_the_submit_record(self):
        n, builders, reviews, result = self.drive(lambda folder: commit_variant(folder, "fix") or "")
        self.assertIn("pull request ready", result)
        self.assertEqual((builders, reviews), (2, 2))
        body = self.body(n)
        self.assertIn("## Fix round", body)
        section = body[body.index("## Fix round"):]
        self.assertIn("D1 is not met", section)
        self.assertIn(self.head(n)[:7], section)
        self.assertGreater(body.index("## Fix round"), body.index("## Evidence"))
        self.assertTrue(body.startswith("## Unresolved review findings"))
        submit = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"][-1]
        self.assertEqual(submit["fix_round"], {"result": "findings", "commit": self.head(n)})

    def test_D2_a_fix_builder_that_changes_nothing_ends_the_round_without_a_second_review(self):
        n, builders, reviews, result = self.drive(lambda folder: "")
        self.assertIn("pull request ready", result)
        self.assertEqual((builders, reviews), (2, 1))
        body = self.body(n)
        self.assertIn("## Fix round", body)
        self.assertIn("made no change", body.lower())
        submit = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"][-1]
        self.assertEqual(submit["fix_round"]["result"], "no-change")

    def test_D3_an_outcome_from_the_fix_builder_keeps_the_piece_out_of_shaping(self):
        def fix(folder):
            (folder / ".loop").mkdir(exist_ok=True)
            (folder / ".loop" / "outcome").write_text("environment\nTool failure: disk is full\n")
            return ""

        n, builders, reviews, result = self.drive(fix)
        self.assertEqual((builders, reviews), (2, 1))
        self.assertIn("pull request ready", result)
        self.assertNotIn("state:shaping", self.p.gh.issue(n)["labels"])
        body = self.body(n)
        self.assertIn("Tool failure: disk is full", body)
        first = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"][-1]
        self.assertEqual(first["commit"], self.head(n))
        self.assertEqual(first["fix_round"]["result"], "outcome")

    def test_D3_an_idle_fix_builder_keeps_the_piece_out_of_shaping(self):
        n, builders, reviews, result = self.drive(lambda folder: "idle")
        self.assertEqual((builders, reviews), (2, 1))
        self.assertIn("pull request ready", result)
        self.assertNotIn("state:shaping", self.p.gh.issue(n)["labels"])
        self.assertIn("idle", self.body(n).lower())
        submit = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"][-1]
        self.assertEqual(submit["fix_round"]["result"], "idle")

    def test_D4_frozen_baseline_conflicts_alone_start_no_fix_builder(self):
        n, builders, reviews, result = self.drive(
            lambda folder: commit_variant(folder, "fix") or "", review_mode="baseline-conflict")
        self.assertIn("pull request ready", result)
        self.assertEqual((builders, reviews), (1, 1))
        self.assertNotIn("## Fix round", self.body(n))

    def test_D5_a_stop_request_after_the_first_review_starts_no_fix_builder(self):
        stop = self.p.root / ".loop" / "stop"

        def ask_to_stop():
            stop.parent.mkdir(exist_ok=True)
            stop.write_text("")

        n, builders, reviews, result = self.drive(
            lambda folder: commit_variant(folder, "fix") or "", after_review=ask_to_stop)
        self.assertEqual((builders, reviews), (1, 1))
        body = self.body(n)
        self.assertIn("## Fix round", body)
        self.assertIn("asked the run to stop", body)

    def test_D6_contract_findings_that_remain_head_the_pull_request(self):
        n, builders, reviews, result = self.drive(lambda folder: "")
        self.assertIn("pull request ready", result)
        body = self.body(n)
        self.assertTrue(body.startswith("## Unresolved review findings"))
        self.assertIn("D1 is not met", body)


if __name__ == "__main__":
    unittest.main()
