"""When GitHub skips a pull request's checks for a billing limit, the run says so and tests the commit itself."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import git
from test_land import LandFixture

# isort: split

import gate
import github_checks
from loopkit import record_text
from network import StepTimeout

BILLING = ("The job was not started because recent account payments have failed "
           "or your spending limit needs to be increased.")
OTHER = "Process completed with exit code 1."


class FakeApi:
    """check-runs and annotations keyed by run id: {id: (conclusion, annotation)}."""

    def __init__(self, runs, broken=False):
        self.runs, self.broken, self.paths = runs, broken, []

    def __call__(self, path):
        self.paths.append(path)
        if self.broken:
            raise RuntimeError("gh api failed: HTTP 502")
        if path.endswith("/annotations"):
            run_id = int(path.split("/")[-2])
            return json.dumps([{"message": self.runs[run_id][1]}])
        return json.dumps({"check_runs": [{"id": i, "conclusion": c}
                                          for i, (c, _) in self.runs.items()]})


class BillingFixture(LandFixture):
    def prepare_piece(self, regression="echo 1 passed", api=None):
        n, folder, result = self.gated()
        ready = {"move": "ready", "regression": regression, "regression_limit": 60,
                 "prepare": "", "protected_paths": []}
        self.p.gh.comment(n, record_text(ready, "ready"))
        self.p.gh.merge_error = "Required status check test is failing"
        self.p.gh.api = api or FakeApi({1: ("failure", BILLING)})
        return n, folder, result


class BillingLandTest(BillingFixture, unittest.TestCase):
    def test_d1_a_billing_blocked_check_is_reported_as_not_a_test_failure(self):
        n, folder, result = self.prepare_piece()
        line = self.land(n, folder, result)
        sha = git(folder, "rev-parse", "HEAD")[:10]
        self.assertIn("Not merged: GitHub did not run the checks (billing or spending limit)", line)
        self.assertIn("this is not a test failure", line)
        self.assertIn(f"Local Test command on {sha}: passed", line)
        self.assertIn("next: merge it on GitHub after a look", line)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")

    def test_d2_the_test_command_runs_in_a_clean_checkout_and_the_pull_request_gets_a_comment(self):
        ran_in = self.p.root.parent / "ran-in.txt"
        n, folder, result = self.prepare_piece(regression=f"pwd > {ran_in}; echo 1 passed")
        (folder / "dirty.txt").write_text("not committed\n")
        self.land(n, folder, result)
        checkout = Path(ran_in.read_text().strip())
        self.assertNotEqual(checkout.resolve(), folder.resolve())
        self.assertFalse(checkout.exists(), "the temporary checkout is removed")
        text = self.p.gh.comments(n)[-1]
        self.assertIn(git(folder, "rev-parse", "HEAD")[:10], text)
        self.assertIn("passed", text)

    def test_d3_a_failing_local_test_command_is_reported_and_nothing_merges(self):
        n, folder, result = self.prepare_piece(regression="echo 1 failed; exit 1")
        line = self.land(n, folder, result)
        self.assertIn("Local Test command on", line)
        self.assertIn("failed", line)
        self.assertNotIn(": passed", line)
        self.assertIn("failed", self.p.gh.comments(n)[-1])
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")

    def test_d4_another_failed_check_beside_a_billing_one_reports_the_raw_error(self):
        api = FakeApi({1: ("failure", BILLING), 2: ("failure", OTHER)})
        n, folder, result = self.prepare_piece(api=api)
        line = self.land(n, folder, result)
        self.assertEqual(line, f"{result} Not merged: Required status check test is failing")
        self.assertEqual(self.p.gh.comments(n)[-1].count("Local Test command"), 0)

    def test_d4_a_failed_lookup_reports_the_raw_error(self):
        n, folder, result = self.prepare_piece(api=FakeApi({}, broken=True))
        self.assertEqual(self.land(n, folder, result),
                         f"{result} Not merged: Required status check test is failing")

    def test_d6_a_merge_timeout_is_reported_and_no_check_lookup_runs(self):
        n, folder, result = self.prepare_piece()
        with patch.object(self.p.gh, "merge_pr", side_effect=StepTimeout("gh pr merge ran too long")):
            line = self.land(n, folder, result)
        self.assertIn("Not merged: network error: gh pr merge ran too long", line)
        self.assertEqual(self.p.gh.api.paths, [])

    def test_d5_stays_a_successful_merge_makes_no_check_lookup(self):
        n, folder, result = self.prepare_piece()
        self.p.gh.merge_error = None
        line = self.land(n, folder, result)
        self.assertEqual(line, f"piece {n}: merged into trip: https://example.invalid/pull/{n}")
        self.assertEqual(self.p.gh.api.paths, [])
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "done")


class BillingBlockTest(unittest.TestCase):
    def block(self, runs, **kw):
        return github_checks.billing_block(type("G", (), {"api": FakeApi(runs, **kw)})(), "abc")

    def test_d1_the_annotation_text_comes_back_when_every_failed_run_is_billing(self):
        self.assertIn("spending limit", self.block({1: ("failure", BILLING), 2: ("success", "")}))

    def test_d1_a_spending_limit_annotation_counts(self):
        self.assertTrue(self.block({1: ("failure", "You have reached your spending limit.")}))

    def test_d4_nothing_comes_back_for_another_failure_or_no_failure(self):
        self.assertEqual(self.block({1: ("failure", OTHER)}), "")
        self.assertEqual(self.block({1: ("success", "")}), "")
        self.assertEqual(self.block({}, broken=True), "")


if __name__ == "__main__":
    unittest.main()
