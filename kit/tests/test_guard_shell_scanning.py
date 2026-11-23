import subprocess
from pathlib import Path

from kit.tests.test_guard import GuardCase
from kit.tests import test_guard_command_forms


class TestShellScanning(GuardCase):
    hook = test_guard_command_forms.TestGuardCommandForms.hook

    def test_heredoc_substitutions_keep_quoted_parentheses_and_nested_commands(self):
        for index, expression in enumerate((
                "$(printf ')'; git switch -c scan0)",
                "$(printf '('; git switch -c scan1)",
                "$(printf '%s' \"$(printf ')')\"; git switch -c scan2)",
                "`printf ')'; git switch -c scan3`")):
            command = "cat <<EOF\n" + expression + "\nEOF"
            for agent in ("claude", "codex"):
                with self.subTest(agent=agent, expression=expression):
                    self.refused(self.hook(command, agent=agent), "role-git")
            shell = subprocess.run(["/bin/sh", "-c", command], cwd=self.work,
                                   capture_output=True, text=True)
            self.assertEqual(shell.returncode, 0, shell.stderr)
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=self.work, text=True)
            self.assertEqual(branch.strip(), "scan%d" % index)

    def test_quoted_and_escaped_heredoc_substitutions_are_data(self):
        for command in ("cat <<'EOF'\n$(printf ')'; git switch x)\nEOF",
                        'cat <<"EOF"\n`git switch x`\nEOF',
                        "cat <<EOF\n\\$(git switch x)\n\\`git switch x\\`\nEOF",
                        "cat <<EOF\n$(printf '%s' 'git switch x')\nEOF"):
            for agent in ("claude", "codex"):
                with self.subTest(agent=agent, command=command):
                    self.allowed(self.hook(command, agent=agent))

    def test_continued_tee_and_redirect_after_quoted_data_check_test_targets(self):
        for command in ("printf changed | tee src/first.txt " + "\\\n" + "tests/test_app.py",
                        'printf "%s > harmless" > "tests/test_app.py"',
                        "printf '%s > harmless' > 'tests/test_app.py'",
                        'echo "$(printf changed > tests/test_app.py)"'):
            for agent in ("claude", "codex"):
                for locked in ((), ("tests/test_app.py",)):
                    with self.subTest(agent=agent, command=command, locked=locked):
                        self.refused(self.hook(command, agent=agent, locked=locked),
                                     "test-lock")
            shell = subprocess.run(["/bin/sh", "-c", command], cwd=self.work,
                                   capture_output=True, text=True)
            self.assertEqual(shell.returncode, 0, shell.stderr)
            self.assertNotEqual((Path(self.work) / "tests/test_app.py").read_text(),
                                "pass\n")

    def test_quoted_greater_than_arguments_are_data(self):
        for command in ('printf "%s > harmless"', "awk '$1>5' README.md",
                        "echo '$(printf changed > tests/test_app.py)'"):
            self.allowed(self.hook(command, role="reviewer"))
