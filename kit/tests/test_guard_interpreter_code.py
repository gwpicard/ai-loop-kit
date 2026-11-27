import ast
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from kit.tests.test_guard import GUARD, GuardCase


ROLES = ("builder", "test-writer", "reviewer", "pass")
TEST = "uv run python -m pytest"
FILES = TEST + " {files}"


def code_forms(words, system=False):
    for literal in (repr(list(words)), json.dumps(list(words), indent=4)):
        if system:
            code = "import os\nos.system(%s)" % json.dumps(shlex.join(words))
        else:
            code = ("import subprocess\nsubprocess.Popen(%s, stdout=subprocess.DEVNULL, "
                    "stderr=subprocess.STDOUT, start_new_session=True)" % literal)
        yield "python3 - <<'PY'\n%s\nPY" % code
        yield "python3 -c " + shlex.quote(code)
        if system:
            break
    yield "sh -c " + json.dumps(shlex.join(words))


class TestInterpreterCode(GuardCase):
    def payloads(self, command, role):
        for agent, payload in (("claude", command), ("codex", command),
                               ("codex", ["/bin/bash", "-lc", command])):
            env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT=agent, LOOP_TEST_COMMAND=TEST,
                       LOOP_TEST_FILES_COMMAND=FILES)
            if role:
                env["LOOP_ROLE"] = role
            data = {"tool_name": "Bash", "tool_input": {"command": payload},
                    "cwd": self.work}
            result = subprocess.run([sys.executable, GUARD], input=json.dumps(data),
                                    capture_output=True, text=True, env=env)
            yield agent, payload, result

    def check_commands(self, commands, roles, rule=None):
        for command in commands:
            for role in roles:
                for agent, payload, result in self.payloads(command, role):
                    with self.subTest(agent=agent, payload=payload, role=role):
                        if rule:
                            self.refused(result)
                            self.assertIn("rule: " + rule, result.stderr.splitlines())
                        else:
                            self.allowed(result)
                            self.assertNotIn("guard: internal error", result.stderr)

    def test_full_test_in_python_and_shell_input_is_refused(self):
        self.check_commands(code_forms(shlex.split(TEST)), ROLES, "full-test")

    def test_full_test_in_other_interpreters_and_wrappers_is_refused(self):
        for interpreter in ("python", "python3", "node", "sh", "bash", "zsh"):
            if interpreter.startswith("python"):
                code = "import subprocess; subprocess.Popen(%s, shell=True)" % json.dumps(TEST)
                flag, stdin = "-c", " -"
            elif interpreter == "node":
                code = "require('child_process').execSync(%s)" % json.dumps(TEST)
                flag, stdin = "-e", ""
            else:
                code = TEST
                flag, stdin = "-c", ""
            for wrapper in ("", "uv run ", "env "):
                runner = wrapper + interpreter
                commands = (runner + " " + flag + " " + shlex.quote(code),
                            runner + stdin + " <<'CODE'\n" + code + "\nCODE",
                            runner + stdin + " <<<" + shlex.quote(code))
                self.check_commands(commands, ("builder",), "full-test")

    def test_git_push_merge_and_system_calls_are_refused_in_roles(self):
        for words in (("git", "push", "origin", "feature"), ("git", "merge", "feature")):
            self.check_commands(code_forms(words), ROLES, "role-git")
        self.check_commands(code_forms(("git", "push", "origin", "feature"), system=True),
                            ROLES, "role-git")

    def test_recursive_list_deletes_are_refused_in_every_session(self):
        for flag in ("-rf", "-r"):
            self.check_commands(code_forms(("rm", flag, "build")), (None,) + ROLES,
                                "recursive-delete")

    def test_selected_files_and_safe_commands_remain_allowed(self):
        for words in (("uv", "run", "python", "-m", "pytest", "tests/test_x.py"),
                      ("git", "status"), ("git", "log"), ("rm", "notes.txt")):
            self.check_commands(code_forms(words), ROLES)

    def test_full_test_and_git_commands_remain_allowed_without_a_role(self):
        for words in (tuple(shlex.split(TEST)), ("git", "push", "origin", "feature"),
                      ("git", "merge", "feature")):
            self.check_commands(code_forms(words), (None,))
        self.check_commands(code_forms(("git", "push", "origin", "feature"), system=True),
                            (None,))

    def test_known_limits_names_interpreter_input_and_remaining_blind_spots(self):
        doc = ast.get_docstring(ast.parse(Path(GUARD).read_text()))
        paragraph = doc.split("Known limits:", 1)[1].split("\n\n", 1)[0]
        paragraph = " ".join(paragraph.replace("`", "").split()).lower()
        for pattern in (r"reads? code", r"-c\b", r"-e\b", r"here-?doc", r"here-string",
                        r"commands assembled at run[ -]?time", r"code in files",
                        r"code that a test or (?:a )?(?:project|tracked) script runs"):
            with self.subTest(pattern=pattern):
                self.assertRegex(paragraph, pattern)
