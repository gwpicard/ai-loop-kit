from kit.tests.test_guard import GuardCase


class TestGitOptionWithSeparateValue(GuardCase):
    def test_push_to_main_refused_after_git_dir_with_a_separate_value(self):
        self.refused(self.bash("git --git-dir other push origin main"))

    def test_force_push_refused_after_work_tree_with_a_separate_value(self):
        self.refused(self.bash("git --work-tree . push --force origin feature"))

    def test_role_session_checkout_refused_after_git_dir_with_a_separate_value(self):
        self.refused(self.bash("git --git-dir other checkout main", role="builder"))

    def test_role_session_checkout_refused_after_a_short_flag(self):
        self.refused(self.bash("git -P checkout main", role="builder"))
