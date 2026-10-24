"""The kit runs on one Python, started through bin/kit-python."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from helpers import KIT

LAUNCHER = KIT / "bin" / "kit-python"
sys.path.insert(0, str(KIT / "scripts"))

# isort: split
import kit_python  # noqa: E402
import sandbox  # noqa: E402


def launch(*args, env=None, cwd=None, stdin=""):
    return subprocess.run([str(LAUNCHER), *args], capture_output=True, text=True,
                          env=env, cwd=cwd, input=stdin, check=False, timeout=60)


class LauncherTest(unittest.TestCase):
    def test_the_version_lives_in_the_launcher_only(self):
        self.assertEqual(kit_python.required(), (3, 13))
        self.assertEqual(sys.version_info[:2], (3, 13), "tests run on the kit Python")

    def test_missing_uv_refuses_with_the_install_command(self):
        result = launch("-c", "print(1)", env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("uv is not installed", result.stderr)
        self.assertIn("brew install uv", result.stderr)

    @unittest.skipUnless(shutil.which("uv"), "uv is needed")
    def test_launcher_ignores_a_read_only_cache_and_a_project_venv(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "cache"
            cache.mkdir()
            cache.chmod(0o555)
            fake_venv = Path(folder) / ".venv"
            fake_venv.mkdir()
            env = dict(os.environ, UV_CACHE_DIR=str(cache), VIRTUAL_ENV=str(fake_venv))
            result = launch("-c", "import sys; print(sys.version_info[:2], sys.prefix)",
                            env=env, cwd=folder)
            cache.chmod(0o755)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("(3, 13)", result.stdout)
        self.assertNotIn(str(fake_venv), result.stdout)


class EntryPointTest(unittest.TestCase):
    def test_an_older_python_is_refused_and_names_the_launcher(self):
        stderr = io.StringIO()
        with patch.object(kit_python.sys, "version_info", (3, 9, 6)), \
                redirect_stderr(stderr), self.assertRaises(SystemExit) as stop:
            kit_python.require()
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("kit-python", stderr.getvalue())

    def test_control_entry_points_check_and_quality_helpers_do_not(self):
        for name in ("scripts/gate.py", "scripts/run.py", "scripts/session.py",
                     "scripts/builder_prompt.py", "scripts/dashboard.py",
                     "scripts/sandbox.py", "hooks/guard.py"):
            with self.subTest(name=name):
                self.assertIn("kit_python.require()", (KIT / name).read_text())
        for path in (KIT / "quality").glob("*.py"):
            with self.subTest(name=path.name):
                self.assertNotIn("kit_python", path.read_text())

    def test_kit_python_file_stays_readable_by_old_pythons(self):
        text = (KIT / "scripts" / "kit_python.py").read_text()
        self.assertNotIn("from __future__", text)
        self.assertIsNone(re.search(r"\bmatch\b.*:\s*$|:=|\w \| \w", text, re.M))


class HookTest(unittest.TestCase):
    def hook_commands(self):
        hooks = json.loads((KIT / "hooks" / "hooks.json").read_text())
        plugin = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        commands = [plugin.replace("${CLAUDE_PLUGIN_ROOT}", str(KIT))]
        with tempfile.TemporaryDirectory() as folder:
            for walk_away in (False, True):
                settings = sandbox.session_settings(Path(folder), [], walk_away=walk_away)
                commands += [e["command"] for e in settings["hooks"]["PreToolUse"][0]["hooks"]]
        return commands

    def run_hook(self, command, stdin, env=None):
        return subprocess.run(command, shell=True, input=stdin, capture_output=True,  # noqa: S602
                              text=True, env=env, check=False, timeout=60)

    def test_every_hook_starts_through_the_launcher_and_fails_closed(self):
        commands = self.hook_commands()
        self.assertEqual(len(commands), 4)
        allowed = '{"tool_name": "Bash", "tool_input": {"command": "ls"}}'
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, LOOP_BUILD_ROOT=folder)
            for command in commands:
                with self.subTest(command=command):
                    self.assertIn("bin/kit-python", command)
                    self.assertTrue(
                        command.startswith("sh -c 'sh \"$@\" || exit 2' kit-guard "))
                    self.assertEqual(self.run_hook(command, allowed, env).returncode, 0)
                    for stdin in ("not json", "[]", "null",
                                  '{"tool_name": "Bash", "tool_input": ["x"]}',
                                  '{"tool_name": "Write", "tool_input": ["x"]}'):
                        result = self.run_hook(command, stdin, env)
                        boundary = "sandbox.py" in command
                        if ("Write" in stdin and not boundary) or ("Bash" in stdin and boundary):
                            continue  # each hook checks only its own tools
                        self.assertEqual(result.returncode, 2, stdin)

    def test_a_hook_refuses_when_the_launcher_cannot_run(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "kit-python"
            copy.write_text(LAUNCHER.read_text())
            copy.chmod(0o644)  # a plugin copy that lost its executable bit still runs
            guard = KIT / "hooks" / "guard.py"
            command = f'sh -c \'sh "$@" || exit 2\' kit-guard "{copy}" "{guard}"'
            ok = '{"tool_name": "Bash", "tool_input": {"command": "ls"}}'
            self.assertEqual(self.run_hook(command, ok).returncode, 0)
            missing = command.replace(str(copy), str(Path(folder) / "gone"))
            self.assertEqual(self.run_hook(missing, ok).returncode, 2)
            no_uv = self.run_hook(command, ok, env={"PATH": "/usr/bin:/bin", "HOME": folder})
            self.assertEqual(no_uv.returncode, 2, no_uv.stderr)

    def test_the_person_s_pythonpath_does_not_reach_the_kit(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "json.py").write_text("raise SystemExit('shadowed json')\n")
            env = dict(os.environ, PYTHONPATH=folder)
            result = launch(str(KIT / "hooks" / "guard.py"), env=env,
                            stdin='{"tool_name": "Bash", "tool_input": {"command": "ls"}}')
        self.assertNotIn("shadowed json", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_guidance_starts_a_kit_script_with_bare_python(self):
        docs = [*KIT.rglob("*.md"), *(KIT.parent / "extras").rglob("*.md")]
        prompt = (KIT / "scripts" / "builder_prompt.py").read_text()
        for path, text in [(p, p.read_text()) for p in docs] + [(Path("builder_prompt"), prompt)]:
            with self.subTest(path=str(path)):
                self.assertIsNone(re.search(r'python3? "[^"]*/(scripts|hooks)/', text))


if __name__ == "__main__":
    unittest.main()
