"""Regression checks for changed-function mutmut selection and results."""
from __future__ import annotations

import importlib.util
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "kit" / "quality" / "mutmut-changed.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("mutmut_changed", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, capture_output=True,
                          text=True, check=True).stdout.strip()


class MutmutChangedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "--quiet", "-b", "main")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        (self.root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src/"]\n')
        (self.root / "src").mkdir()
        (self.root / "src" / "module.py").write_text(
            "def x_foo():\n    return 1\n\ndef x_foobar():\n    return 2\n\n"
            "def outer():\n    def inner():\n        return 3\n    return inner()\n")
        (self.root / "other").mkdir()
        (self.root / "other" / "outside.py").write_text(
            "def outside():\n    return 1\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "--quiet", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")

    def change_source(self, file: str, text: str) -> None:
        (self.root / file).write_text(text)
        git(self.root, "add", file)
        git(self.root, "commit", "--quiet", "-m", "change")

    def test_selects_only_changed_mutmut_sources_and_skips_nested_functions(self):
        self.change_source(
            "src/module.py",
            "def x_foo():\n    return 10\n\ndef x_foobar():\n    return 2\n\n"
            "def outer():\n    def inner():\n        return 3\n    return inner()\n")
        helper = load_helper()
        self.assertEqual(helper.patterns(self.base, self.root),
                         ["module.x_x_foo__mutmut_*"])

    def test_nested_function_changes_are_not_selected(self):
        self.change_source(
            "src/module.py",
            "def x_foo():\n    return 1\n\ndef x_foobar():\n    return 2\n\n"
            "def outer():\n    def inner():\n        return 30\n    return inner()\n")
        helper = load_helper()
        self.assertEqual(helper.patterns(self.base, self.root), [])

    def test_changed_file_outside_source_paths_is_ignored(self):
        self.change_source("other/outside.py", "def outside():\n    return 2\n")
        helper = load_helper()
        self.assertEqual(helper.patterns(self.base, self.root), [])

    def test_mutmut_statuses_must_be_killed_and_names_match_function_boundary(self):
        helper = load_helper()
        selected = ["module.x_foo__mutmut_*"]
        self.assertTrue(helper.results_pass(
            "module.x_foobar__mutmut_1: survived\n", selected))
        self.assertTrue(helper.results_pass(
            "module.x_foo__mutmut_1: killed\n", selected))
        self.assertFalse(helper.results_pass(
            "module.x_foo__mutmut_1: no tests\n", selected))
        self.assertFalse(helper.results_pass(
            "module.x_foo__mutmut_1: timeout\n", selected))
        self.assertFalse(helper.results_pass(
            "module.x_foo__mutmut_1: suspicious\n", selected))
        self.assertFalse(helper.results_pass(
            "module.x_foo__mutmut_1: survived\n", selected))

    def test_a_function_with_no_mutants_passes(self):
        helper = load_helper()
        self.assertTrue(helper.results_pass("Killed mutants: 0\n", [
            "module.x_foo__mutmut_*"]))

    def test_main_reports_nothing_to_mutate_and_passes(self):
        helper = load_helper()
        run = SimpleNamespace(returncode=0, stdout="", stderr="")
        results = SimpleNamespace(returncode=0, stdout="Killed mutants: 0\n", stderr="")
        output = io.StringIO()
        with patch.object(helper, "source_paths", return_value=[Path("src")]), \
             patch.object(helper, "patterns", return_value=["module.x_foo__mutmut_*"]), \
             patch.object(helper.subprocess, "run", side_effect=[run, results]), \
             patch("sys.argv", [str(SCRIPT)]), redirect_stdout(output):
            self.assertEqual(helper.main(), 0)
        self.assertIn("module.x_foo nothing to mutate", output.getvalue())

    def test_main_fails_when_no_source_paths_are_configured(self):
        helper = load_helper()
        output = io.StringIO()
        with patch.object(helper, "source_paths", return_value=[]), \
             patch("sys.argv", [str(SCRIPT)]), redirect_stderr(output):
            self.assertNotEqual(helper.main(), 0)
        self.assertIn("no mutmut source paths configured", output.getvalue())


if __name__ == "__main__":
    unittest.main()
