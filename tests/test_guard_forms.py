"""Regression checks for the command forms handled by the guard."""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "kit" / "hooks" / "guard.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("loop_guard_forms", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=True)


class GuardFormsTest(unittest.TestCase):
    def test_eval_checks_the_unwrapped_pyenv_command(self):
        self.assertIsNone(load_guard().check_command('eval "$(pyenv init -)"', False))

    def test_eval_checks_the_unwrapped_force_push(self):
        self.assertIsNotNone(load_guard().check_command('eval "git push --force"', False))

    def test_eval_remains_refused_in_build_sessions(self):
        self.assertIsNotNone(load_guard().check_command('eval "$(pyenv init -)"', True))

    def test_xargs_rm_without_recursive_or_force_flags_is_allowed(self):
        self.assertIsNone(load_guard().check_command("printf x | xargs rm file", False))

    def test_xargs_rm_with_recursive_flag_is_refused(self):
        self.assertIsNotNone(load_guard().check_command("printf x | xargs rm -r file", False))

    def test_xargs_rm_with_uppercase_recursive_flag_is_refused(self):
        self.assertIsNotNone(load_guard().check_command("printf x | xargs rm -R file", False))

    def test_xargs_rm_with_force_flag_is_refused(self):
        self.assertIsNotNone(load_guard().check_command("printf x | xargs rm -f file", False))

    def test_origin_push_without_refspec_is_refused_on_main(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git(root, "init", "--quiet", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Test")
            git(root, "commit", "--allow-empty", "--quiet", "-m", "base")
            guard = load_guard()
            self.assertIsNotNone(guard.check_command(f"git -C {root} push origin", False))

    def test_upstream_origin_push_without_refspec_is_refused_on_main(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git(root, "init", "--quiet", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Test")
            git(root, "commit", "--allow-empty", "--quiet", "-m", "base")
            guard = load_guard()
            self.assertIsNotNone(guard.check_command(f"git -C {root} push -u origin", False))


if __name__ == "__main__":
    unittest.main()
