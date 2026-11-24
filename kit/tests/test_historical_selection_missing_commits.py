"""Historical selection cases skip when their Git objects are unavailable."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from kit.tests import test_targeted_import_selection as selection


class MissingHistoricalCommitsTest(unittest.TestCase):
    def test_missing_commit_or_parent_skips_each_historical_case(self):
        commits = (
            "6977672f0f438ce339c585620f0492a909d894c6",
            "7d2848630dd4abc0872b5431e033463bf2f57b8c",
        )
        real_run = subprocess.run
        for missing in ("commit", "parent"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                real_run(["git", "init", str(root)], check=True, capture_output=True)
                probes = []

                def run(args, *positional, **kwargs):
                    if list(args[:3]) == ["git", "cat-file", "-e"]:
                        probes.append(args[3])
                        # Model a shallow clone: the child object is available,
                        # but Git must still reject its absent parent.
                        if missing == "parent" and args[3] in {
                            commit + "^{commit}" for commit in commits
                        }:
                            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
                    return real_run(args, *positional, **kwargs)

                case = selection.HistoricalSelectionTest(
                    "test_both_regression_commits_select_the_tests_that_failed")
                result = unittest.TestResult()
                with mock.patch.object(selection, "ROOT", root), \
                        mock.patch.object(subprocess, "run", side_effect=run):
                    unittest.TestSuite([case]).run(result)

                self.assertEqual(result.errors, [], result.errors)
                self.assertEqual(result.failures, [], result.failures)
                self.assertEqual(len(result.skipped), len(commits), result.skipped)
                for commit in commits:
                    self.assertTrue(any(commit in reason for _, reason in result.skipped),
                                    (commit, result.skipped))
                    ref = commit + ("^" if missing == "parent" else "")
                    self.assertIn(ref + "^{commit}", probes)
