"""Contract findings with evidence must change the run disposition."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

import gate
from helpers import git
from run_fixtures import RunFixture


class ReviewDispositionsTest(RunFixture, unittest.TestCase):
    def test_reproduced_contract_finding_returns_piece_to_shaping(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-reproduced"
        n, result = self.build("good", attempts=1)

        self.assertIn("back to shaping", result)
        self.assertNotIn(f"piece/{n}", self.p.gh.prs)
        handback = next(record for record in gate.records(self.p.gh.comments(n))
                        if record.get("move") == "give-back")
        self.assertEqual(handback["type"], "judge-gap")
        self.assertIn("reproducer", handback["reason"])
        self.assertIn("D1", handback["reason"])
        branch = self.p.folder(n)
        self.assertFalse((branch / "test_review_D1.py").exists())
        self.assertIn("check(\"test_D1_add_appends\", d1)",
                      git(branch, "show", "HEAD:judge_add.py"))

    def test_unresolved_contract_finding_heads_pr_and_removes_contract_claim(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-gap"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertTrue(body.startswith("## Unresolved review findings"))
        self.assertIn("D1 is not met", body)
        self.assertNotIn("the contract is met", body.lower())

    def test_non_reproducing_finding_keeps_pull_request_and_shows_result(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-not-reproduced"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("Unresolved review findings", body)
        self.assertIn("reproducer", body.lower())
        self.assertIn("passed", body.lower())

    def test_reproducer_failure_without_the_named_item_does_not_stop_pr(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-unrelated"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("did not reproduce it", body)
        self.assertIn("FAIL X9", body)

    def test_unparseable_contract_verdict_is_a_review_error(self):
        os.environ["FAKE_REVIEW_MODE"] = "bad-contract-verdict"
        n, result = self.build("good", attempts=1)

        self.assertIn("invalid verdict", result)
        self.assertIn("environment: 1", gate.report(self.p.gh))
        self.assertTrue(any("next:" in comment.lower()
                            for comment in self.p.gh.comments(n)))
