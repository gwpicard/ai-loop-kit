import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GUARD, GuardCase


ROLES = ("builder", "test-writer", "reviewer", "pass")


class TestGuardCommandForms(GuardCase):
    def test_both_quoted_git_directories_refuse_main_in_every_role(self):
        for role in (None,) + ROLES:
            for quote in ("'", '"'):
                with self.subTest(role=role, quote=quote):
                    command = "git -C " + quote + "my dir" + quote + " push origin main"
                    self.refused(self.bash(command, role=role))

    def test_heredoc_quoting_controls_substitution_in_every_loop_role(self):
        for role in ROLES:
            for expression in ("$(git switch x)", "`git switch x`"):
                for header, body, end in (
                        ("<<EOF", expression, "EOF"),
                        ("<<-EOF", "\t" + expression, "\tEOF"),
                        ("<<FIRST <<EOF", "literal data\nFIRST\n" + expression, "EOF")):
                    with self.subTest(role=role, expression=expression, header=header):
                        for quoted in ("<<'EOF'", '<<"EOF"'):
                            self.allowed(self.bash("cat %s\n%s\nEOF" % (quoted, expression),
                                                   role=role))
                        self.refused(self.bash("cat %s\n%s\n%s" % (header, body, end),
                                               role=role), "role-git")

    def test_every_tee_operand_checks_existing_and_locked_tests(self):
        for role in ("builder", "test-writer"):
            for path, reason, locked in (
                    ("tests/test_app.py", "existing test", []),
                    ("new/test_locked.py", "locked test", ["new/test_locked.py"])):
                for operands in (path + " src/output.txt", "src/output.txt " + path,
                                 "src/first.txt src/second.txt " + path):
                    for options in ("", "-a "):
                        with self.subTest(role=role, operands=operands, options=options):
                            self.refused(self.bash("printf x | tee " + options + operands,
                                                   role=role, locked=locked), reason)

    def test_quoted_targets_check_existing_and_locked_tests_with_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test spaced.py": "original\n"})
            for role in ("builder", "test-writer"):
                for path, reason, locked in (
                        ("tests/test spaced.py", "existing test", []),
                        ("new/test locked.py", "locked test", ["new/test locked.py"]),
                        ("new/test_locked.py", "locked test", ["new/test_locked.py"])):
                    for quote in ("'", '"'):
                        for write in ("> ", ">> ", "| tee ", "| tee -a src/output.txt "):
                            with self.subTest(role=role, path=path, quote=quote, write=write):
                                command = "printf x " + write + quote + path + quote
                                self.refused(self.bash(command, cwd=work, role=role,
                                                       locked=locked), reason)

    def test_import_failure_refuses_loop_roles_and_allows_non_loop_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            hook = Path(folder) / "hooks" / "guard.py"
            hook.parent.mkdir()
            shutil.copyfile(GUARD, hook)
            clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("LOOP_") and k != "PYTHONPATH"}
            for agent in ("claude", "codex"):
                for role in (None,) + ROLES:
                    with self.subTest(agent=agent, role=role):
                        env = dict(clean, LOOP_AGENT=agent)
                        if role:
                            env["LOOP_ROLE"] = role
                        payload = {"tool_name": "Bash", "cwd": folder,
                                   "tool_input": {"command": "echo changed > README.md"}}
                        result = subprocess.run(
                            [sys.executable, str(hook)], input=json.dumps(payload),
                            cwd=folder, env=env, capture_output=True, text=True)
                        self.assertEqual(result.stdout, "")
                        if role:
                            self.assertEqual(result.returncode, 2, result.stderr)
                        else:
                            self.allowed(result)
                            self.assertIn("guard: cannot load, allowing the call: ",
                                          result.stderr)
