from kit.tests.test_guard import GuardCase


class TestPythonShell(GuardCase):
    def test_python_delete_through_a_shell_is_still_refused(self):
        # These commands are hook inputs; their Python code never runs.
        for shell in ("sh", "bash", "zsh", "dash"):
            for option in ("-c", "-lc"):
                command = shell + " " + option + " 'python3 -c \"import shutil; shutil.rmtree(\\\"x\\\")\"'"
                with self.subTest(command=command):
                    self.refused(self.bash(command), "rule: recursive-delete\n")

    def test_search_patterns_can_mention_python_and_the_function(self):
        for command in (
            "rg 'python3 rmtree' kit/scripts/common.py",
            "grep 'rmtree python' kit/scripts/common.py",
        ):
            with self.subTest(command=command):
                self.allowed(self.bash(command))
