"""Protected commands stay visible through wrapper options."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from helpers import KIT


def guard(command: str, *, builder: bool = False) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "LOOP_BUILDER": "1" if builder else "0"}
    return subprocess.run(
        [sys.executable, str(KIT / "hooks" / "guard.py")],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class WrapperOptionsTest(unittest.TestCase):
    def test_env_options_do_not_hide_protected_commands(self):
        for command in (
            "env -i git push origin main",
            "env -u HOME git push origin main",
            "env A=1 git push origin main",
        ):
            with self.subTest(command=command):
                self.assertEqual(guard(command).returncode, 2)

    def test_sudo_options_do_not_hide_protected_commands(self):
        for command in (
            "sudo -E git push -f origin x",
            "sudo -u someone rm -rf x",
        ):
            with self.subTest(command=command):
                self.assertEqual(guard(command).returncode, 2)

    def test_other_wrapper_options_do_not_hide_protected_commands(self):
        for command in (
            "command -p rm -rf x",
            "nohup -- git push --force",
            "time -p rm -rf x",
            "sudo env -i nohup git push --force",
        ):
            with self.subTest(command=command):
                self.assertEqual(guard(command).returncode, 2)

    def test_unknown_wrapper_option_fails_closed_in_builder_session(self):
        result = guard("env --unknown git push origin main", builder=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not be read safely", result.stderr)

    def test_ordinary_wrapped_commands_remain_allowed(self):
        for command in ("env -i python3 -m pytest", "time -p git status"):
            with self.subTest(command=command):
                self.assertEqual(guard(command).returncode, 0)

    def test_existing_refusals_remain_in_force(self):
        for command in (
            "git push origin main",
            "git push --force origin piece",
            "rm -rf x",
            "sudo rm --recursive x",
            "gh pr merge 3 --squash",
        ):
            with self.subTest(command=command):
                self.assertEqual(guard(command).returncode, 2)

    def test_quoted_python_code_cannot_hide_recursive_delete(self):
        commands = (
            "python3 '-c' '(lambda shutil: shutil.rmtree(\"x\"))(__import__(\"shutil\"))'",
            "python3 -c \"import shutil; shutil.rmtree('x')\"",
        )
        for command in commands:
            for builder in (False, True):
                with self.subTest(command=command, builder=builder):
                    self.assertEqual(guard(command, builder=builder).returncode, 2)

    def test_quoted_node_code_cannot_hide_recursive_delete(self):
        command = "node '-e' 'require(\"child_process\").execSync(\"rm -rf x\")'"
        for builder in (False, True):
            with self.subTest(builder=builder):
                self.assertEqual(guard(command, builder=builder).returncode, 2)

    def test_command_lookup_options_remain_allowed(self):
        for command in ("command -v gh", "command -V gh"):
            with self.subTest(command=command):
                self.assertEqual(guard(command, builder=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
