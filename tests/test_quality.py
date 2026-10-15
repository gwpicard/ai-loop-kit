"""Tests for the small quality command helpers."""
from __future__ import annotations

import importlib.util
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "kit"


def load(name: str):
    path = KIT / "quality" / name
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, capture_output=True,
                          text=True, check=True).stdout.strip()


class QualityHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "--quiet", "-b", "main")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")

    def test_mutmut_helper_selects_changed_functions(self):
        path = self.root / "src" / "module.py"
        path.parent.mkdir()
        path.write_text("def count(items):\n    return len(items)\n\n")
        (self.root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src/"]\n')
        git(self.root, "add", "src/module.py", "pyproject.toml")
        git(self.root, "commit", "--quiet", "-m", "base")
        base = git(self.root, "rev-parse", "HEAD")
        path.write_text("def count(items):\n    return len(set(items))\n\n")
        git(self.root, "commit", "--quiet", "-am", "change")
        helper = load("mutmut-changed.py")
        self.assertEqual(helper.patterns(base, self.root), ["module.x_count__mutmut_*"])

    def test_mutmut_helper_uses_mutmut_38_names_and_skips_test_files(self):
        source = self.root / "src" / "module.py"
        source.parent.mkdir()
        source.write_text("class Counter:\n    def count(self, items):\n        return len(items)\n")
        (self.root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src/"]\n')
        tests = self.root / "tests" / "test_module.py"
        tests.parent.mkdir()
        tests.write_text("def test_count():\n    assert True\n")
        git(self.root, "add", "src/module.py", "tests/test_module.py", "pyproject.toml")
        git(self.root, "commit", "--quiet", "-m", "base")
        base = git(self.root, "rev-parse", "HEAD")
        source.write_text("class Counter:\n    def count(self, items):\n        return len(set(items))\n")
        tests.write_text("def test_count():\n    assert False\n")
        git(self.root, "add", "src/module.py", "tests/test_module.py")
        git(self.root, "commit", "--quiet", "-m", "change")
        helper = load("mutmut-changed.py")
        self.assertEqual(helper.patterns(base, self.root),
                         ["module.xǁCounterǁcount__mutmut_*"])

    def test_mutmut_results_parse_recorded_38_output_and_detect_survivors(self):
        helper = load("mutmut-changed.py")
        output = ("module.x_count__mutmut_1: killed\n"
                  "module.xǁCounterǁcount__mutmut_2: killed\n"
                  "Killed mutants: 2\nSurvived mutants: 0\n")
        self.assertTrue(helper.results_pass(
            output, ["module.x_count__mutmut_*", "module.xǁCounterǁcount__mutmut_*"]))
        self.assertFalse(helper.results_pass(
            output.replace("count__mutmut_2: killed", "count__mutmut_2: survived"),
            ["module.xǁCounterǁcount__mutmut_*"]))
        self.assertTrue(helper.results_pass(
            "Killed mutants: 0\nSurvived mutants: 0\n",
            ["module.x_count__mutmut_*"]))

    @unittest.skipUnless(shutil.which("mutmut"), "mutmut is not installed")
    def test_mutmut_helper_runs_real_mutmut_on_a_tiny_fixture(self):
        source = self.root / "src" / "module.py"
        source.parent.mkdir()
        source.write_text("def count(items):\n    return len(items)\n")
        (self.root / "test_module.py").write_text(
            "from src.module import count\n\n"
            "def test_count():\n    assert count([1, 1]) == 1\n")
        (self.root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src/"]\n'
            'pytest_add_cli_args_test_selection = ["-q"]\n')
        git(self.root, "add", "src/module.py", "test_module.py", "pyproject.toml")
        git(self.root, "commit", "--quiet", "-m", "base")
        base = git(self.root, "rev-parse", "HEAD")
        source.write_text("def count(items):\n    return len(set(items))\n")
        git(self.root, "add", "src/module.py")
        git(self.root, "commit", "--quiet", "-m", "change")
        helper = load("mutmut-changed.py")
        self.assertEqual(helper.patterns(base, self.root), ["module.x_count__mutmut_*"])
        run = subprocess.run(["mutmut", "run", "module.x_count__mutmut_*"], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        results = subprocess.run(["mutmut", "results", "--all", "true"], cwd=self.root,
                                 capture_output=True, text=True)
        self.assertEqual(results.returncode, 0, results.stdout + results.stderr)
        self.assertTrue(helper.results_pass(results.stdout, ["module.x_count__mutmut_*"]),
                        results.stdout)

    def test_crap_helper_flags_a_changed_function_at_thirty(self):
        path = self.root / "module.py"
        path.write_text("def choose(x):\n    return x\n")
        git(self.root, "add", "module.py")
        git(self.root, "commit", "--quiet", "-m", "base")
        git(self.root, "switch", "-c", "piece")
        path.write_text("def choose(x):\n    if x:\n        if x > 1:\n            if x > 2:\n                if x > 3:\n                    if x > 4:\n                        return 1\n    return 0\n")
        git(self.root, "add", "module.py")
        git(self.root, "commit", "--quiet", "-m", "complex function")
        (self.root / "coverage.json").write_text(
            '{"files":{"module.py":{"executed_lines":[],"missing_lines":[1,2,3,4,5,6,7,8,9]}}}')
        script = KIT / "quality" / "crap.py"
        result = subprocess.run(["python3", str(script), "--coverage", "coverage.json",
                                 "--base", "main"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CRAP: module.py:1 choose", result.stdout)

    def test_crap_does_not_reject_a_changed_function_just_for_rising_above_main(self):
        path = self.root / "module.py"
        path.write_text("def choose(x):\n    return x\n")
        git(self.root, "add", "module.py")
        git(self.root, "commit", "--quiet", "-m", "base")
        git(self.root, "switch", "-c", "piece")
        path.write_text("def choose(x):\n    if x:\n        return 1\n    return 0\n")
        git(self.root, "add", "module.py")
        git(self.root, "commit", "--quiet", "-m", "add branch")
        (self.root / "coverage.json").write_text(
            '{"files":{"module.py":{"executed_lines":[1,2,3,4],"missing_lines":[]}}}')
        script = KIT / "quality" / "crap.py"
        result = subprocess.run(["python3", str(script), "--coverage", "coverage.json",
                                 "--base", "main"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mutmut_results_require_changed_function_coverage_and_no_survivors(self):
        helper = load("mutmut-changed.py")
        pattern = ["pkg.module.x_count__mutmut_*"]
        self.assertTrue(helper.results_pass("Killed mutants: 0\nSurvived mutants: 0\n", pattern))
        self.assertFalse(helper.results_pass(
            "Killed mutants: 1\nSurvived mutants: 1\npkg.module.x_count__mutmut_2: survived\n", pattern))
        self.assertTrue(helper.results_pass(
            "Killed mutants: 1\nSurvived mutants: 0\npkg.module.x_count__mutmut_1: killed\n", pattern))

    def test_crap_diff_ranges_keep_the_site_of_a_deleted_line(self):
        helper = load("crap.py")
        self.assertEqual(helper.changed_ranges("+++ b/module.py\n@@ -3 +2,0 @@\n"),
                         {"module.py": [(1, 2)]})

    def test_mutmut_support_requires_version_38_and_source_paths(self):
        helper = load("mutmut_support.py")
        (self.root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src/"]\n')
        self.assertEqual(helper.validation_error(self.root, "mutmut, version 3.8.0"), "")
        self.assertIn("3.8 or later", helper.validation_error(
            self.root, "mutmut, version 3.3.1"))
        (self.root / "pyproject.toml").write_text('[tool.mutmut]\n')
        self.assertIn("no mutmut source paths configured", helper.validation_error(
            self.root, "mutmut, version 3.8.0"))

    def test_mutmut_support_reads_setup_cfg_source_paths(self):
        helper = load("mutmut_support.py")
        (self.root / "setup.cfg").write_text("[mutmut]\nsource_paths = src/\n")
        self.assertEqual(helper.source_paths(self.root), ["src/"])

    def test_proposed_quality_replaces_old_loop_quality_in_fresh_copy(self):
        helper = load("proposed_quality.py")
        agents = self.root / "AGENTS.md"
        agents.write_text("# Project\n\n## The loop\nTest command: pytest\n"
                          "Quality: old-check\nPrepare command: setup\n")
        helper.apply(agents, "new-check")
        self.assertEqual(agents.read_text(), "# Project\n\n## The loop\n"
                         "Test command: pytest\nQuality: new-check\nPrepare command: setup\n")

    def test_proposed_quality_adds_a_loop_section_when_missing(self):
        helper = load("proposed_quality.py")
        agents = self.root / "AGENTS.md"
        agents.write_text("# Project\n")
        helper.apply(agents, "new-check")
        self.assertIn("## The loop\nQuality: new-check\n", agents.read_text())


if __name__ == "__main__":
    unittest.main()
