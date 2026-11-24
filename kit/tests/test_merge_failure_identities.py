"""Compare failing tests independently of module totals through the worker."""
import unittest

from kit.tests import test_merge_failure_reports as reports


class MergeFailureIdentitiesTest(unittest.TestCase):
    def setUp(self):
        self.fixture = reports.MergeFailureReportsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def test_same_detailed_failures_ignore_changed_module_totals(self):
        failure = "FAIL: test_save (tests.Storage)\n"
        output = self.fixture.run_worker(failure + "FAIL test_storage 13 tests\n",
                                         failure + "FAIL test_storage 12 tests\n")
        for report in output:
            self.assertIn("same failing tests", report)
            self.assertIn(failure.strip(), report)
            self.assertIn("FAIL test_storage 13 tests", report)
            self.assertIn("FAIL test_storage 12 tests", report)

    def test_module_fallback_ignores_totals_but_preserves_module_names(self):
        for baseline, comparison in (("test_storage", "same"), ("test_network", "different")):
            with self.subTest(baseline=baseline):
                output = self.fixture.run_worker("FAIL test_storage 13 tests\n",
                                                 "FAIL %s 12 tests\n" % baseline)
                for report in output:
                    self.assertIn(comparison + " failing tests", report)

    def test_different_detailed_failures_with_the_same_module_summary(self):
        output = self.fixture.run_worker(
            "FAIL: test_save (tests.Storage)\nFAIL test_storage 12 tests\n",
            "FAIL: test_load (tests.Storage)\nFAIL test_storage 12 tests\n")
        for report in output:
            self.assertIn("different failing tests", report)
