from kit.tests.test_guard import GuardCase


class TestLineContinuation(GuardCase):
    def test_push_split_over_lines_refused(self):
        cmd = "git push \\\n  origin " + "ma" + "in"
        self.refused(self.bash(cmd), "default branch")
