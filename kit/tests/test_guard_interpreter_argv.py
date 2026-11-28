import json
import os
import shlex
import subprocess
import sys

from kit.tests.test_guard import GUARD, GuardCase


ROLES = ("builder", "test-writer", "reviewer", "pass")
TEST = ["uv", "run", "python", "-m", "pytest"]


def payloads(words):
    commands = (
        ["python3", "-c", "import subprocess; subprocess.Popen(%r)" % words],
        ["node", "-e", "require('child_process').execSync(%s)" % json.dumps(shlex.join(words))],
        ["sh", "-c", shlex.join(words)],
    )
    for command in commands:
        for prefix in ([], ["env"], ["uv", "run"]):
            yield prefix + command


class TestInterpreterArgv(GuardCase):
    def check_commands(self, commands, roles, rule=None):
        for role in roles:
            env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT="codex", LOOP_TEST_COMMAND=shlex.join(TEST),
                       LOOP_TEST_FILES_COMMAND=shlex.join(TEST) + " {files}")
            if role:
                env["LOOP_ROLE"] = role
            for command in commands:
                data = {"tool_name": "Bash", "tool_input": {"command": command},
                        "cwd": self.work}
                with self.subTest(role=role, command=command):
                    result = subprocess.run([sys.executable, GUARD], input=json.dumps(data),
                                            capture_output=True, text=True, env=env)
                    if rule:
                        self.refused(result)
                        self.assertIn("rule: " + rule, result.stderr.splitlines())
                    else:
                        self.allowed(result)

    def test_direct_interpreter_lists_refuse_full_test_and_git_commands(self):
        for words, rule in ((TEST, "full-test"),
                            (["git", "push", "origin", "feature"], "role-git"),
                            (["git", "merge", "feature"], "role-git")):
            self.check_commands(list(payloads(words)), ROLES, rule)
        self.check_commands([["python3", "-c", "import os; os.system('git push origin feature')"]],
                            ROLES, "role-git")

    def test_direct_interpreter_lists_refuse_recursive_deletes_without_a_role_too(self):
        for flag in ("-rf", "-r"):
            self.check_commands(list(payloads(["rm", flag, "build"])), (None,) + ROLES,
                                "recursive-delete")

    def test_direct_interpreter_lists_allow_selected_files_and_safe_commands(self):
        for words in (TEST + ["tests/test_x.py"], ["git", "status"], ["git", "log"],
                      ["rm", "notes.txt"]):
            self.check_commands(list(payloads(words)), ROLES)

    def test_direct_interpreter_lists_allow_full_test_and_git_without_a_role(self):
        for words in (TEST, ["git", "push", "origin", "feature"], ["git", "merge", "feature"]):
            self.check_commands(list(payloads(words)), (None,))

    def test_ordinary_arguments_remain_data(self):
        commands = [["printf", "%s", text] for text in
                    ("git push origin feature", "git merge feature",
                     "python3 -c \"import os; os.system('git push origin feature')\"")]
        self.check_commands(commands, ROLES)
