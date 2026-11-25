"""Exercise test role isolation through the runner's command entry point."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RunnerRoleEnvironmentTest(unittest.TestCase):
    def test_enclosing_builder_role_does_not_reach_test_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests = Path(tmp, "kit", "tests")
            tests.mkdir(parents=True)
            Path(tmp, "kit", "__init__.py").touch()
            (tests / "__init__.py").touch()
            runner = tests / "run.py"
            shutil.copyfile(Path(__file__).with_name("run.py"), runner)
            (tests / "test_role.py").write_text(
                "import os, unittest\n"
                "class RoleTest(unittest.TestCase):\n"
                "    def test_no_enclosing_role(self):\n"
                "        self.assertNotIn('LOOP_ROLE', os.environ)\n")
            result = subprocess.run(
                [sys.executable, str(runner), "test_role"], cwd=tmp,
                env=dict(os.environ, LOOP_ROLE="builder", LOOP_TEST_WORKERS="1"),
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("1 tests in 1 modules, 0 failed", result.stdout)
