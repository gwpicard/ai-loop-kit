"""Seeded quality failures have independent oracles and complete run records."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FIELD = Path(__file__).resolve().parents[1] / "field"
FIELDS = ("Date", "Kit commit", "Backend", "Scenario", "Expected bad behaviour",
          "Escaped to approval", "False block", "Human repairs", "Attempts", "Duration")
VALUES = ("2026-10-19", "abc1234", "codex", "missing-regression", "existing test fails",
          "no", "no", "0", "1", "20s")


def invoke(*args, cwd=None):
    return subprocess.run([sys.executable, "-B", *map(str, args)], cwd=cwd,
                          capture_output=True, text=True, timeout=20, check=False)


def table(fields=FIELDS, values=VALUES):
    return ("| " + " | ".join(fields) + " |\n| " + " | ".join("---" for _ in fields)
            + " |\n| " + " | ".join(values) + " |\n")


class QualityFixturesTest(unittest.TestCase):
    def workspace(self, scenario, version):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / "project"
        shutil.copytree(FIELD / "fixtures" / scenario / version, project)
        self.assertFalse((project / "oracle").exists())
        self.assertFalse((project / "correct").exists())
        return project

    def test_D1_oracles_reject_seeds_and_accept_correct_projects(self):
        for scenario, reason in (("missing-regression", "existing items must stay"),
                                 ("missing-behaviour", "duplicates must be ignored"),
                                 ("false-alarm", "unsupported finding must not block")):
            for version, expected in (("seeded", 1), ("correct", 0)):
                with self.subTest(scenario=scenario, version=version):
                    project = self.workspace(scenario, version)
                    result = invoke(FIELD / "fixtures" / scenario / "oracle" / "check.py",
                                    project, cwd=project)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    if expected:
                        self.assertIn(reason, result.stderr)

    def test_D2_seeded_regression_passes_judge_but_fails_full_tests(self):
        project = self.workspace("missing-regression", "seeded")
        judge = invoke("judge.py", cwd=project)
        self.assertEqual(judge.returncode, 0, judge.stdout + judge.stderr)
        full = invoke("-m", "unittest", "discover", "-s", "tests", cwd=project)
        self.assertEqual(full.returncode, 1, full.stdout + full.stderr)
        self.assertIn("existing items must stay", full.stderr)

    def test_correct_projects_and_other_seeds_pass_project_tests_and_judges(self):
        for scenario in ("missing-regression", "missing-behaviour", "false-alarm"):
            for version in ("seeded", "correct"):
                project = self.workspace(scenario, version)
                judge = invoke("judge.py", cwd=project)
                self.assertEqual(judge.returncode, 0, judge.stdout + judge.stderr)
                if (scenario, version) != ("missing-regression", "seeded"):
                    full = invoke("-m", "unittest", "discover", "-s", "tests", cwd=project)
                    self.assertEqual(full.returncode, 0, full.stdout + full.stderr)
                    self.assertIn("Ran 1 test", full.stderr)

    def quality_audit(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "QUALITY.md"
        path.write_text(text)
        return invoke(FIELD / "audit.py", "--quality", path, cwd=tmp.name)

    def test_D3_audit_names_each_empty_or_absent_field(self):
        for index, field in enumerate(FIELDS):
            for missing_column in (False, True):
                with self.subTest(field=field, missing_column=missing_column):
                    fields, values = list(FIELDS), list(VALUES)
                    if missing_column:
                        fields.pop(index)
                        values.pop(index)
                    else:
                        values[index] = " "
                    result = self.quality_audit(table(fields, values))
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(field, result.stdout)

    def test_D3_audit_checks_later_rows_and_short_rows(self):
        for text in (table() + "| " + " | ".join(VALUES[:-1]) + " |\n",
                     table() + table().splitlines()[-1].replace("20s", "") + "\n"):
            result = self.quality_audit(text)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Duration", result.stdout)

    def test_D4_audit_accepts_complete_and_not_yet_run_tables(self):
        for text in (table(), "\n".join(table().splitlines()[:2]) + "\n",
                     (FIELD / "QUALITY.md").read_text()):
            result = self.quality_audit(text)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_D5_legacy_audit_keeps_accepting_existing_results(self):
        spec = importlib.util.spec_from_file_location("quality_field_audit", FIELD / "audit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        historical = (FIELD / "RESULTS.md").read_text()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "RESULTS.md").write_text(historical)
            with patch.object(module, "repo_root", return_value=root), \
                    patch.object(module, "load", return_value=[]) as load, \
                    patch.object(module, "audit_cleanup", return_value=[]), \
                    patch.object(module, "audit_quality") as quality, patch("builtins.print"):
                self.assertEqual(module.main([]), 0)
                load.assert_called_once_with(root)
                quality.assert_not_called()
            self.assertEqual((root / "RESULTS.md").read_text(), historical)


if __name__ == "__main__":
    unittest.main()
