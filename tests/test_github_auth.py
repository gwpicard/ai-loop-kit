"""Doctor checks active GitHub accounts and names authentication failures."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import Project

# helpers adds kit/scripts to the import path.
# isort: split

import gate
from loopkit import GitHub


class GitHubAuthTest(unittest.TestCase):
    def test_inactive_extra_account_does_not_fail_doctor(self):
        project = Project()
        self.addCleanup(project.close)
        project.gh.signed_in = GitHub(project.root).signed_in
        real_run = subprocess.run

        def run_command(args, **kwargs):
            if args[:3] == ["gh", "auth", "status"]:
                active = "github.com\n  Logged in to github.com account builder\n"
                inactive = "  Failed to log in to github.com account old-account\n"
                if "--active" in args:
                    return subprocess.CompletedProcess(args, 0, active, "")
                return subprocess.CompletedProcess(args, 1, "", active + inactive)
            return real_run(args, **kwargs)

        with patch("loopkit.subprocess.run", side_effect=run_command):
            checks = gate.doctor(project.gh, project.root)

        self.assertTrue(checks[1][0], checks[1])
        self.assertGreater(len(checks), 2, "doctor must continue past authentication")

    def test_doctor_reports_the_failed_active_account(self):
        failure = ("github.com\n"
                   "  Failed to log in to github.com account builder (keyring)\n"
                   "  - Active account: true\n")
        checks = self.failed_doctor(failure)
        self.assertFalse(checks[-1][0])
        self.assertIn("builder", checks[-1][1])
        self.assertIn("github.com", checks[-1][1])
        self.assertIn("gh auth login", checks[-1][2])
        self.assertEqual(len(checks), 2)

    def test_doctor_reports_no_signed_in_account(self):
        checks = self.failed_doctor("You are not logged into any GitHub hosts.\n")
        self.assertFalse(checks[-1][0])
        self.assertIn("not logged into any GitHub hosts", checks[-1][1])
        self.assertIn("gh auth login", checks[-1][2])

    def failed_doctor(self, message):
        origin = subprocess.CompletedProcess([], 0, "git@github.com:example/project.git\n")
        failure = subprocess.CompletedProcess([], 1, "", message)
        with patch("gate.sh", return_value=origin), \
                patch("loopkit.subprocess.run", return_value=failure):
            return gate.doctor(GitHub(Path.cwd()), Path.cwd())
