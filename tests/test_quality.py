"""Tests for the small quality command helpers."""
from __future__ import annotations

import importlib.util
import subprocess
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

    def test_changed_line_helper_reports_paths_and_ranges(self):
        path = self.root / "src" / "module.py"
        path.parent.mkdir()
        path.write_text("a = 1\nb = 2\n")
        git(self.root, "add", "src/module.py")
        git(self.root, "commit", "--quiet", "-m", "base")
        base = git(self.root, "rev-parse", "HEAD")
        path.write_text("a = 1\nb = 3\nc = 4\n")
        git(self.root, "commit", "--quiet", "-am", "change")
        helper = load("changed-lines.py")
        self.assertEqual(helper.changed_lines(base, self.root), {"src/module.py": [[2, 3]]})

    def test_mutmut_helper_selects_changed_functions(self):
        path = self.root / "src" / "module.py"
        path.parent.mkdir()
        path.write_text("def count(items):\n    return len(items)\n\n")
        git(self.root, "add", "src/module.py")
        git(self.root, "commit", "--quiet", "-m", "base")
        base = git(self.root, "rev-parse", "HEAD")
        path.write_text("def count(items):\n    return len(set(items))\n\n")
        git(self.root, "commit", "--quiet", "-am", "change")
        helper = load("mutmut-changed.py")
        self.assertEqual(helper.patterns(base, self.root), ["src.module.count*"])

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

    def test_crap_helper_catches_a_score_rise_above_main(self):
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
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("main=1.00", result.stdout)

    def test_crap_diff_ranges_keep_the_site_of_a_deleted_line(self):
        helper = load("crap.py")
        self.assertEqual(helper.changed_ranges("+++ b/module.py\n@@ -3 +2,0 @@\n"),
                         {"module.py": [(1, 2)]})


if __name__ == "__main__":
    unittest.main()
