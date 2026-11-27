"""Timeouts first encountered by Stop, and their lifetime across commits."""
import unittest

from kit.tests import test_targeted_budget as budget
from kit.tests.helpers import run_git


class TargetedBudgetEntryPointsTest(unittest.TestCase):
    def test_stop_records_its_own_timeout_for_later_checks(self):
        fixture = budget.BudgetFixture(self)
        fixture.implement()
        stopped = fixture.stop("first-timeout")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertEqual(stopped.stdout + stopped.stderr, "")
        self.assertEqual(fixture.started(), [["--targeted", *sorted(budget.FILES)]])
        before = budget.records(fixture.calls)
        result = fixture.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        budget.TargetedBudgetTest.timeout_line(self, result, 600, len(budget.FILES))
        self.assertEqual(budget.records(fixture.calls), before)

    def test_a_new_commit_runs_again_after_a_timeout(self):
        fixture = budget.BudgetFixture(self)
        fixture.implement()
        first = fixture.check()
        budget.TargetedBudgetTest.timeout_line(self, first, 600, len(budget.FILES))
        run_git(["commit", "--allow-empty", "-m", "Advance the fixture head"], fixture.work)
        second = fixture.check()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        budget.TargetedBudgetTest.timeout_line(self, second, 600, len(budget.FILES))
        self.assertEqual(fixture.started(), [["--targeted", *sorted(budget.FILES)]] * 2)
        self.assertEqual(budget.records(fixture.limits), [600, 600])


if __name__ == "__main__":
    unittest.main()
