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
AGENTS = ("claude", "codex")


class TestGuardCommandForms(GuardCase):
    def hook(self, command, role="builder", agent="claude", locked=(), cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update(LOOP_AGENT=agent, LOOP_ROLE=role, LOOP_LOCKED="\n".join(locked))
        payload = {"tool_name": "Bash", "cwd": cwd or self.work,
                   "tool_input": {"command": command}}
        return subprocess.run([sys.executable, GUARD], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_both_quoted_directories_refuse_main_pushes_in_every_role(self):
        for agent in AGENTS:
            for role in ("",) + ROLES:
                for quote in ("'", '"'):
                    command = "git -C %smy dir%s push origin main" % (quote, quote)
                    with self.subTest(agent=agent, role=role, command=command):
                        self.refused(self.hook(command, role=role, agent=agent))

    def test_prefixed_paths_to_gh_are_refused_in_every_loop_role(self):
        for agent in AGENTS:
            for role in ROLES:
                for prefix in ("env ", "sudo ", "VAR=value "):
                    for path in ("/opt/homebrew/bin/gh", "./tools/gh"):
                        command = prefix + path + " pr list"
                        with self.subTest(agent=agent, role=role, command=command):
                            self.refused(self.hook(command, role=role, agent=agent),
                                         "role-git")

    def test_every_tee_operand_is_checked_for_existing_and_locked_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test_app.py": "pass\n",
                                        "tests/test spaced.py": "pass\n"})
            for agent in AGENTS:
                for role in ("builder", "test-writer"):
                    for path, locked in (("tests/test_app.py", ()),
                                         ("tests/test spaced.py", ()),
                                         ("tests/test_new.py", ("tests/test_new.py",)),
                                         ("tests/test new.py", ("tests/test new.py",))):
                        for quote in ("'", '"'):
                            for position in range(3):
                                operands = ["first.txt", "second.txt"]
                                operands.insert(position, quote + path + quote)
                                command = "printf changed | tee -a " + " ".join(operands)
                                with self.subTest(agent=agent, role=role, path=path,
                                                  quote=quote, position=position):
                                    self.refused(self.hook(command, role=role, agent=agent,
                                                           locked=locked, cwd=work), "test-lock")

    def test_quoted_redirects_check_whole_existing_and_locked_test_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test_app.py": "pass\n",
                                        "tests/test spaced.py": "pass\n"})
            for agent in AGENTS:
                for role in ("builder", "test-writer"):
                    for path, locked in (("tests/test_app.py", ()),
                                         ("tests/test spaced.py", ()),
                                         ("tests/test_new.py", ("tests/test_new.py",)),
                                         ("tests/test new.py", ("tests/test new.py",))):
                        for quote in ("'", '"'):
                            for redirect in (">", ">>", "2>"):
                                command = "printf changed %s %s%s%s" % (redirect, quote, path, quote)
                                with self.subTest(agent=agent, role=role, command=command):
                                    self.refused(self.hook(command, role=role, agent=agent,
                                                           locked=locked, cwd=work), "test-lock")

    def test_missing_modules_refuse_shell_and_tool_writes_for_both_agents(self):
        with tempfile.TemporaryDirectory() as folder:
            hook = Path(folder) / "hooks" / "guard.py"
            hook.parent.mkdir()
            shutil.copyfile(GUARD, hook)
            clean = {k: v for k, v in os.environ.items()
                     if not k.startswith("LOOP_") and k != "PYTHONPATH"}
            for agent in AGENTS:
                writes = [{"tool_name": "Bash", "tool_input": {
                    "command": "printf changed > notes.txt"}}]
                if agent == "codex":
                    writes.append({"tool_name": "apply_patch", "tool_input": {
                        "command": "*** Begin Patch\n*** Add File: notes.txt\n+changed\n*** End Patch\n"}})
                else:
                    writes.append({"tool_name": "Write", "tool_input": {
                        "file_path": "notes.txt", "content": "changed\n"}})
                for role in ROLES:
                    env = dict(clean, LOOP_AGENT=agent, LOOP_ROLE=role)
                    for payload in writes:
                        with self.subTest(agent=agent, role=role, tool=payload["tool_name"]):
                            result = subprocess.run(
                                [sys.executable, str(hook)], cwd=folder, env=env,
                                input=json.dumps(dict(payload, cwd=folder)),
                                capture_output=True, text=True)
                            self.assertEqual(result.returncode, 2, result.stderr)
