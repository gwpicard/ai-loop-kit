"""Keep merge fix diagnostics accurate when a baseline or later merge cannot run."""
from pathlib import Path
import unittest

from kit.tests import test_merge_fix_round as rounds


class MergeFixDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.fixture = rounds.MergeFixRoundTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def test_issue_only_failure_does_not_claim_a_baseline_pass(self):
        fixture = self.fixture
        fixture.arrange()
        fixture.results(rounds.failed("FAIL test_new 1 tests"))
        result = fixture.merge_candidate()
        self.assertFalse(result.ok)
        self.assertFalse(result.park, result.reason)
        self.assertEqual(len(fixture.commands()), 1, "an empty baseline selection must not run the full suite")
        self.assertIn("absent from the loop branch", result.reason)
        self.assertIn("no baseline tests were run", result.reason)
        self.assertNotIn("loop branch passes", result.reason)
        self.assertIn(rounds.NEW, result.reason)
        self.assertTrue(Path(fixture.work, ".loop/logs/7-merge-baseline.log").is_file())

    def test_fix_review_failure_reports_latest_feedback_without_claiming_another_merge(self):
        fixture = self.fixture
        fixture.arrange(max_rounds=1)
        result = fixture.build([{"passed": True}] * 3,
                               reviews=(rounds.APPROVE, rounds.CHANGES, rounds.CHANGES))
        self.assertEqual(result.status, "parked", result.reason)
        self.assertEqual(len(fixture.builders()), 3)
        self.assertEqual(len([call for call in fixture.commands() if call["branch"] != "baseline"]), 1)
        self.assertIn("two merge test fix rounds", result.reason)
        self.assertIn("Last merge test failure:", result.reason)
        self.assertIn("Latest fix feedback:", result.reason)
        self.assertIn("Handle empty input.", result.reason)
        self.assertNotIn("merge tests still failed after", result.reason)

    def test_shared_failure_does_not_hide_an_issue_only_hang_without_a_failure_header(self):
        fixture = self.fixture
        fixture.arrange()
        shared = "FAIL: test_save (kit.tests.test_alpha.AlphaTest.test_save)"
        stack = '  File "tests/test_beta.py", line 31 in test_wait'
        fixture.results(rounds.failed(shared, "FAIL test_alpha 2 tests", "FAIL test_beta 0 tests",
                                      "test_beta: hung after 90 seconds", stack),
                        baseline_files=rounds.failed(shared, "FAIL test_alpha 2 tests"))
        fixture.build([{"passed": True}, rounds.STOP])
        builders = fixture.builders()
        self.assertEqual(len(builders), 2, "the new hung module still needs a builder fix")
        self.assertIn(rounds.BETA, builders[1]["prompt"])
        self.assertIn(stack, builders[1]["prompt"])
        self.assertIn("Already failing on the loop branch", builders[1]["prompt"])
