"""Delegation keeps branch deletion and unsupported merge targets out of the CLI."""
from pathlib import Path
import subprocess
import unittest

import common
from kit.tests import test_delegated_merges as fixtures
from kit.tests.helpers import run_git, write_exe


class RequestedMergeBoundariesTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DelegatedMergeTest()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def test_command_refuses_repository_automatic_branch_deletion(self):
        f = self.fixture
        script = Path(f.tmp, "bin", "gh")
        script.unlink()
        write_exe(script, fixtures.GH.replace(
            '"delete_branch_on_merge": False', '"delete_branch_on_merge": True'))
        result = f.command()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("delete head branches", result.stdout)
        self.assertEqual(f.recorded(["pr", "merge"]), [])

    def test_command_refuses_a_url_from_another_repository(self):
        f = self.fixture
        script = Path(f.tmp, "bin", "gh")
        script.unlink()
        write_exe(script, fixtures.GH.replace(
            'if a[:2] == ["pr", "view"]:\n    emit(pr)',
            'if a[:2] == ["pr", "view"]:\n'
            '    if "://" in a[2]:\n'
            '        pr["url"] = a[2]\n'
            '    emit(pr)'))
        result = subprocess.run([str(fixtures.KIT / "bin/loop"), "merge",
                                 "https://example.invalid/other/pull/7"],
                                cwd=f.work, text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("this repository", result.stdout)
        self.assertEqual(f.recorded(["pr", "merge"]), [])

    def test_command_refuses_a_base_outside_the_loop_and_default_branches(self):
        f = self.fixture
        f.reset(base="release/next")
        result = f.command()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("base", result.stdout)
        self.assertEqual(f.recorded(["pr", "merge"]), [])

    def test_command_refuses_drafts_and_unknown_conflict_status(self):
        f = self.fixture
        for change in ({"isDraft": True}, {"mergeable": "UNKNOWN"}):
            with self.subTest(change=change):
                f.reset()
                f.state["pr"].update(change)
                f.save()
                result = f.command()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(f.recorded(["pr", "merge"]), [])

    def test_when_green_drains_a_loop_branch_changed_while_checks_were_pending(self):
        f = self.fixture
        f.reset(check="PENDING")

        def update_branch():
            Path(f.work, "app.txt").write_text("later batch\n")
            run_git(["commit", "-am", "Issue later batch"], f.work)
            run_git(["push", "origin", "loop/main"], f.work)
            f.head = common.git(["rev-parse", "HEAD"], cwd=f.work)
            f.reset()

        f.supervise("when green", after_first=update_branch)
        args = f.assert_merged_once()
        self.assertEqual(args[args.index("--match-head-commit") + 1], f.head)
