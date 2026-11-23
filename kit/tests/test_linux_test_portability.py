"""Reproduce Linux test failures and plant faults in the portability check."""
import ast
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class LinuxTestPortabilityTest(unittest.TestCase):
    def test_restoration_tests_run_without_tmpdir(self):
        with tempfile.TemporaryDirectory(prefix="restoration-portability-") as folder:
            env = dict(os.environ, TMP=folder, TEMP=folder)
            env.pop("TMPDIR", None)
            result = subprocess.run([
                sys.executable, "kit/tests/run.py",
                "kit/tests/test_loop_branch_restoration.py",
                "kit/tests/test_worker_restoration_log.py",
            ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_orphan_hook_command_replaces_the_shell_when_it_assumes_a_python_leader(self):
        source = (ROOT / "kit/tests/test_pass_orphan_cleanup.py").read_text()
        tree = ast.parse(source)
        # A fixture which no longer equates the child's group with the Python
        # pid need not replace the shell. Its existing cleanup tests judge it.
        assumes_leader = any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual" and len(node.args) == 2
            and ast.unparse(node.args[0]) == "os.getpgid(child)"
            and ast.unparse(node.args[1]) == "leader"
            for node in ast.walk(tree))
        if not assumes_leader:
            return
        commands = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for line in node.value.splitlines():
                if line.startswith("common.run_shell("):
                    call = ast.parse(line).body[0].value
                    command = eval(compile(ast.Expression(call.args[0]), "<hook command>", "eval"),
                                   {"__builtins__": {}, "shlex": shlex,
                                    "command": [sys.executable, "-c", "pass"]})
                    commands.append(shlex.split(command))
        self.assertTrue(commands, "the orphan fixture must exercise a shell hook")
        for command in commands:
            self.assertEqual(command[:2], ["exec", sys.executable],
                             "dash keeps the shell as group leader unless the hook uses exec")

    def test_house_rules_refuse_planted_linux_portability_faults(self):
        with tempfile.TemporaryDirectory(prefix="portability-rules-") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", str(root)], check=True,
                           capture_output=True, text=True)
            planted = root / "kit/tests/test_planted_portability.py"
            planted.parent.mkdir(parents=True)
            planted.write_text("import os, subprocess, sys\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True,
                           capture_output=True, text=True)

            def check(body):
                planted.write_text("import os, subprocess, sys\n" + body)
                return subprocess.run(["sh", str(ROOT / "tests/house-rules.sh"),
                                       "--root", str(root)], cwd=ROOT,
                                      capture_output=True, text=True, timeout=30)

            clean = check("from unittest import mock\n"
                          "value = os.environ.get('TMPDIR')\n"
                          "if sys.platform == 'darwin':\n"
                          "    subprocess.run(['sysctl', '-n', 'hw.ncpu'])\n"
                          "with mock.patch('subprocess.run'):\n"
                          "    subprocess.run(['memory_pressure'])\n")
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            faults = [
                "value = os.environ[%r]\n" % "TMPDIR",
                'value = os.environ["' + 'TMPDIR"]\n',
                "def fixture():\n    return os.environ [ 'TMPDIR' ]\n",
            ]
            faults += ["subprocess.run(%r)\n" % command for command in (
                ["taskpolicy", "-b", "true"],
                ["sysctl", "-n", "hw.ncpu"],
                ["memory_pressure"],
                ["caffeinate", "true"],
                ["getconf", "DARWIN_USER_TEMP_DIR"],
            )]
            faults.append("subprocess.run('sysctl -n hw.ncpu', shell=True)\n")
            for body in faults:
                with self.subTest(body=body):
                    result = check(body)
                    self.assertNotEqual(result.returncode, 0,
                                        "house rules accepted a portability fault: " + body
                                        + result.stdout + result.stderr)
                    self.assertIn(planted.name, result.stdout + result.stderr,
                                  "the refusal must identify the planted file")
