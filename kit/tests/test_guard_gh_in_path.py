from kit.tests.test_guard import GuardCase


class TestGhInPath(GuardCase):
    def test_file_named_gh_is_not_the_cli(self):
        for cmd in ["cat kit/scripts/gh.py", "ls docs/gh"]:
            with self.subTest(cmd=cmd):
                self.allowed(self.bash(cmd, role="builder"))
