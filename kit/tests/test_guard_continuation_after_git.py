from kit.tests.test_guard import GuardCase


class TestContinuationAfterGit(GuardCase):
    def test_push_with_the_line_continued_after_git_is_refused(self):
        cmd = "git \\\npush origin " + "ma" + "in"
        self.refused(self.bash(cmd), "default branch")

    def test_role_git_with_the_line_continued_after_git_is_refused(self):
        self.refused(self.bash("git \\\nmerge feature", role="builder"))
