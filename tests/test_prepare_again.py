"""A dependency the builder declares is installed by Prepare before the judge."""
from __future__ import annotations

from helpers import git

# isort: split

import unittest
from unittest.mock import patch

import gate
import run
from loopkit import records
from run_fixtures import RunFixture

# Prepare "installs" the module only when the attempt declared it.
INSTALL = "if [ -f requirements.txt ]; then printf 'X = 1\\n' > installedmod.py; fi"


class PrepareAgainTest(RunFixture, unittest.TestCase):
    def build_with(self, prepare, mode):
        self.p.loop_section("printf baseline", prepare)
        return self.build(mode, attempts=1)

    def test_a_declared_dependency_is_installed_before_the_judge(self):
        _, result = self.build_with(INSTALL, "adds-dependency")
        self.assertIn("pull request ready", result)

    def test_an_environment_report_about_the_missing_package_is_set_aside(self):
        n, result = self.build_with(INSTALL, "adds-dependency-env")
        self.assertIn("pull request ready", result)
        self.assertFalse(any("reports environment" in c for c in self.p.gh.comments(n)))

    def test_an_attempt_that_changes_no_dependency_file_does_not_prepare_again(self):
        real = run.prepare
        with patch.object(run, "prepare", side_effect=real) as prepare:
            _, result = self.build_with(INSTALL, "good")
        self.assertIn("pull request ready", result)
        self.assertEqual(prepare.call_count, 1)

    def test_a_prepare_that_fails_after_the_attempt_returns_the_piece(self):
        failing = "if [ -f requirements.txt ]; then echo 'no registry' >&2; exit 3; fi"
        n, result = self.build_with(failing, "adds-dependency")
        self.assertIn("the Prepare command failed after the attempt changed a dependency file",
                      result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assertEqual((handback["type"], handback["cause"]), ("environment", "prepare-failed"))
        self.assertIn("no registry", self.p.gh.comments(n)[-2])

    def test_the_installed_files_are_not_committed(self):
        n, _ = self.build_with(INSTALL, "adds-dependency")
        tracked = git(self.p.root, "ls-tree", "-r", "--name-only", f"origin/piece/{n}")
        self.assertIn("requirements.txt", tracked)
        self.assertNotIn("installedmod.py", tracked)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")


if __name__ == "__main__":
    unittest.main()
