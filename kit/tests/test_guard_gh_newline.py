from kit.tests.test_guard import GuardCase


class TestGhPathOnLaterLine(GuardCase):
    def test_path_to_the_cli_on_a_second_line_is_refused(self):
        for cmd in ["echo a\n/usr/bin/gh pr list", "echo a\n./gh pr list"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd, role="builder"))
