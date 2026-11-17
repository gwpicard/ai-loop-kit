from kit.tests.test_guard import GuardCase


class TestQuotedRedirectTarget(GuardCase):
    def test_reviewer_cannot_write_through_a_quoted_redirect_target(self):
        self.refused(self.bash("echo x > 'README.md'", role="reviewer"))

    def test_reviewer_cannot_write_through_a_quoted_tee_target(self):
        self.refused(self.bash("echo x | tee 'README.md'", role="reviewer"))
