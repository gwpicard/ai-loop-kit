import subprocess
from pathlib import Path

from kit.tests import test_guard_command_forms
from kit.tests.test_guard import GuardCase


class TestShellProgramWrites(GuardCase):
    hook = test_guard_command_forms.TestGuardCommandForms.hook

    def test_double_quoted_bash_program_cannot_overwrite_a_locked_test(self):
        command = 'bash -c "printf changed > tests/test_app.py"'
        for agent in ("claude", "codex"):
            with self.subTest(agent=agent):
                result = self.hook(command, agent=agent, locked=("tests/test_app.py",))
                shell = subprocess.run(["/bin/sh", "-c", command], cwd=self.work,
                                       capture_output=True, text=True)
                self.assertEqual(shell.returncode, 0, shell.stderr)
                self.assertEqual((Path(self.work) / "tests/test_app.py").read_text(),
                                 "changed")
                self.refused(result, "test-lock")

    def test_shell_program_targets_are_checked_for_both_agents(self):
        for runner in ("sh -c", "bash -lc", "zsh -c", "dash -c",
                       "env -i /bin/sh -c", "VAR=value bash -c"):
            for quote in ("'", '"'):
                for agent in ("claude", "codex"):
                    with self.subTest(runner=runner, quote=quote, agent=agent):
                        command = runner + " " + quote + "printf changed | tee tests/test_app.py" + quote
                        self.refused(self.hook(command, agent=agent), "test-lock")

    def test_literal_quoted_arguments_remain_data(self):
        for command in ('printf "%s" "bash -c print > tests/test_app.py"',
                        "printf '%s' 'x; bash -c print > tests/test_app.py'",
                        '''bash -c "printf '%s' 'changed > tests/test_app.py'"''',
                        '''bash -c "printf '%s' 'x; bash -c print > tests/test_app.py'"'''):
            for agent in ("claude", "codex"):
                with self.subTest(command=command, agent=agent):
                    self.allowed(self.hook(command, role="reviewer", agent=agent))
