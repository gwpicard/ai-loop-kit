from kit.tests.test_guard import GuardCase


class TestPushWithQuotedDirectory(GuardCase):
    def test_push_to_default_branch_with_a_quoted_dir_is_refused(self):
        cmd = 'git -C "my dir" push origin ' + "ma" + "in"
        self.refused(self.bash(cmd), "default branch")
