# Intent: findings left by the review of a gated piece start one fresh fix builder, and the gate and a second review decide the result.
from __future__ import annotations

import os
import re
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import git
from run_fixtures import FAKE_CLAUDE, RunFixture

# isort: split

import gate
import run
from loopkit import records

try:
    import fix_round
except ImportError as error:
    if error.name != "fix_round":
        raise
    fix_round = None

GOOD = "def add(items, name):\n    return items if name in items else items + [name]\n"
BAD = "def add(items, name):\n    return items\n"
CITATION = "D1: adding a habit appends it."
FINDING = "D1 is not met."
STANDARDS_FINDING = "Rename the helper to say what it does."

STANDARDS_CASES = '''\
        standards-unfixed:*"Standards reviewer brief"*)
          printf '%s' '<verdict>{"findings":[{"rule":"Name things plainly",' \\
            '"hunk":"habits.py:1","finding":"Rename the helper to say what it does."}],' \\
            '"follow_ups":[],"changes":"none"}</verdict>'
          exit 0 ;;
        standards-fixed:*"Standards reviewer brief"*)
          printf '\\n# reviewed\\n' >> habits.py
          git add habits.py && git commit --quiet -m "Review fix"
          printf '%s' '<verdict>{"findings":[{"rule":"Name things plainly",' \\
            '"hunk":"habits.py:1","finding":"Rename the helper to say what it does.",' \\
            '"fixed":true}],"follow_ups":[],"changes":"renamed"}</verdict>'
          exit 0 ;;
        review-idle:*) sleep 5 ;;
'''

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def commit_variant(folder, code, note):
    (folder / "habits.py").write_text(code + f"# {note}\n")
    git(folder, "add", "habits.py")
    git(folder, "commit", "--quiet", "-m", f"Variant {note}")


class FixRoundTest(RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        fake = Path(os.environ["LOOP_CLAUDE"])
        fake.write_text(FAKE_CLAUDE.replace("        review-idle:*) sleep 5 ;;\n", STANDARDS_CASES))
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        agents = self.p.root / "AGENTS.md"
        self.p.loop_section("printf baseline")
        agents.write_text(agents.read_text() + "Base branch: trip\nBase merges: run\n")
        git(self.p.root, "commit", "--quiet", "-am", "Loop settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "branch", "trip")
        git(self.p.root, "push", "--quiet", "origin", "trip")
        self.p.gh.on_merge = self.merge_on_origin

    def merge_on_origin(self, branch, base):
        git(self.p.root, "fetch", "--quiet", "origin")
        git(self.p.root, "switch", "--quiet", base)
        git(self.p.root, "merge", "--quiet", "--no-ff", "-m", "Merge", f"origin/{branch}")
        git(self.p.root, "push", "--quiet", "origin", base)
        git(self.p.root, "switch", "--quiet", "main")

    def submits(self, n):
        return [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"]

    def run_piece(self, fix_code, review_modes, first_mode="contract-gap"):
        """Run one piece. The first builder passes the gate; a second one, if started,
        commits fix_code. review_modes gives FAKE_REVIEW_MODE for each review call."""
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        prompts, reviewed, reviews = [], [], []
        real_review = run.review_piece

        def builder(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            if len(prompts) == 1:
                commit_variant(folder, GOOD, "first")
                reviewed.append(git(folder, "rev-parse", "HEAD").strip())
            elif len(prompts) == 2:
                commit_variant(folder, fix_code, "fix")
            return ""

        def review(*args, **kwargs):
            reviews.append(1)
            mode = review_modes[min(len(reviews), len(review_modes)) - 1]
            if mode:
                os.environ["FAKE_REVIEW_MODE"] = mode
            else:
                os.environ.pop("FAKE_REVIEW_MODE", None)
            return real_review(*args, **kwargs)

        with patch("run.build_once", side_effect=builder), \
                patch("run.review_piece", side_effect=review):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        return n, result, prompts, reviewed[0], len(reviews)

    def test_D1_an_unreproduced_contract_finding_starts_one_fix_builder_with_the_finding_and_diff(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["contract-gap", "contract-gap"])
        self.assertIsNotNone(fix_round, "fix_round must exist")
        self.assertEqual(len(prompts), 2)
        self.assertIn(CITATION, prompts[1])
        self.assertIn(FINDING, prompts[1])
        self.assertIn("+    return items if name in items else items + [name]", prompts[1])
        self.assertEqual(reviews, 2)

    def test_D2_an_unfixed_standards_finding_starts_the_fix_builder_with_the_finding(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["standards-unfixed"])
        self.assertEqual(len(prompts), 2)
        self.assertIn(STANDARDS_FINDING, prompts[1])
        self.assertIn("Name things plainly", prompts[1])

    def test_D2_a_standards_finding_marked_fixed_and_kept_starts_no_fix_builder(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["standards-fixed"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(reviews, 1)
        self.assertIn("merged into trip", result)

    def test_D3_a_fix_that_passes_the_gate_and_second_review_is_submitted_and_merged(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["contract-gap", ""])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(reviews, 2)
        head = git(self.p.folder(n), "rev-parse", "HEAD").strip()
        self.assertNotEqual(head, reviewed)
        submit = self.submits(n)[-1]
        self.assertEqual(submit["commit"], head)
        self.assertEqual(submit["attempts"], 1)
        self.assertEqual(len(self.p.gh.merges), 1)
        self.assertEqual(self.p.gh.merges[0][2], head)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "done")
        self.assertIn("merged into trip", result)

    def test_D4_a_second_review_that_still_leaves_a_finding_waits_for_the_person(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["contract-gap", "contract-gap"])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(reviews, 2)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertTrue(body.startswith("## Unresolved review findings"))
        self.assertIn(FINDING, body)
        self.assertIn("Not merged: the contract review left findings", result)
        self.assertEqual(self.p.gh.merges, [])
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")

    def test_D5_a_fix_that_fails_the_gate_is_dropped_and_the_reviewed_commit_is_submitted(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            BAD, ["contract-gap", ""])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(reviews, 1)
        self.assertEqual(self.submits(n)[-1]["commit"], reviewed)
        remote_head = git(self.p.remote, "rev-parse", f"piece/{n}").strip()
        self.assertEqual(remote_head, reviewed)
        self.assertEqual(git(self.p.folder(n), "rev-parse", "HEAD").strip(), reviewed)
        self.assertEqual(self.p.gh.merges, [])

    def test_D6_a_review_with_no_finding_starts_no_fix_builder(self):
        n, result, prompts, reviewed, reviews = self.run_piece(GOOD, [""])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(reviews, 1)
        self.assertEqual(len(self.p.gh.merges), 1)

    def test_D6_a_reproduced_contract_finding_goes_to_shaping_with_no_fix_builder(self):
        n, result, prompts, reviewed, reviews = self.run_piece(
            GOOD, ["contract-reproduced"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(reviews, 1)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        self.assertTrue(any(re.search("judge-gap", c) for c in self.p.gh.comments(n)))


if __name__ == "__main__":
    unittest.main()
