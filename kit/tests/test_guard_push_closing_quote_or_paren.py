from kit.tests.test_guard import GuardCase


class TestPushBeforeClosingQuoteOrParen(GuardCase):
    def test_short_force_flag_before_closing_quote_refused(self):
        self.refused(self.bash("bash -c 'git push -f'"), "force")

    def test_push_to_default_branch_in_subshell_refused(self):
        cmd = "(git push origin " + "ma" + "in)"
        self.refused(self.bash(cmd), "default branch")

    def test_push_to_default_branch_in_substitution_refused(self):
        cmd = "echo $(git push origin " + "ma" + "in)"
        self.refused(self.bash(cmd), "default branch")
