from kit.tests.test_guard import GuardCase


class TestPythonExecution(GuardCase):
    def test_negated_conditional_and_quoted_python_calls_are_refused(self):
        # The hook receives these strings as JSON; no deletion code runs.
        program = " -c 'import shutil; shutil.rmtree(\"x\")'"
        for interpreter in ("python", "python3"):
            for command in (
                "! " + interpreter + program,
                "if true; then " + interpreter + program + "; fi",
                '"' + interpreter + '"' + program,
                "'" + interpreter + "'" + program,
            ):
                for role in (None, "builder"):
                    with self.subTest(command=command, role=role):
                        self.refused(self.bash(command, role=role), "rule: recursive-delete\n")

    def test_quoted_search_alternatives_are_not_shell_pipelines(self):
        for search in ("rg", "grep -E", "git grep -E"):
            for pattern in ("'rmtree|python3 -c'", '"rmtree|python3 -c"'):
                for role in (None, "builder"):
                    command = search + " " + pattern + " kit/scripts/common.py"
                    with self.subTest(command=command, role=role):
                        self.allowed(self.bash(command, role=role))
