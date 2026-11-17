from kit.tests.test_guard import GuardCase


class TestComparisonIsNotARedirect(GuardCase):
    def test_reviewer_may_run_awk_with_a_greater_than_comparison(self):
        self.allowed(self.bash("awk '$1>5' README.md", role="reviewer"))
