"""Requested merges fetch fork commits which ordinary branch fetches omit."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

import common
from kit.tests import test_delegated_merges as fixtures
from kit.tests.helpers import run_git


class RequestedMergeForkTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DelegatedMergeTest()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        f = self.fixture
        fork = str(Path(f.tmp, "fork"))
        run_git(["clone", f.origin, fork], f.tmp)
        run_git(["config", "user.name", "Test"], fork)
        run_git(["config", "user.email", "t@example.com"], fork)
        Path(fork, "fork.txt").write_text("fork change\n")
        run_git(["add", "fork.txt"], fork)
        run_git(["commit", "-m", "Requested fork fix"], fork)
        f.head = common.git(["rev-parse", "HEAD"], cwd=fork)
        # GitHub exposes a fork's head through a pull request ref in the base repository.
        run_git(["push", "origin", "HEAD:refs/pull/7/head"], fork)
        run_git(["fetch", "--no-prune", "origin"], f.work)
        self.assertNotEqual(subprocess.run(
            ["git", "cat-file", "-e", f.head + "^{commit}"], cwd=f.work,
            capture_output=True).returncode, 0)
        self.assertNotIn(f.head, common.git(
            ["for-each-ref", "--format=%(objectname)", "refs/heads/"], cwd=f.origin))

    def assert_fork_merged(self):
        f = self.fixture
        result = f.command()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = f.assert_merged_once()
        self.assertEqual(args[args.index("--match-head-commit") + 1], f.head)
        self.assertIn("Requested fork fix", args[args.index("--body") + 1])

    def test_default_branch_merge_fetches_the_fork_head_for_its_squash_message(self):
        self.fixture.reset(head="fork-fix")
        self.assert_fork_merged()

    def test_loop_branch_merge_tests_the_combined_fork_and_loop_changes(self):
        f = self.fixture
        f.reset(base="loop/main", head="fork-fix")
        marker = Path(f.tmp, "tested-fork")
        probe = Path(f.tmp, "probe.py")
        probe.write_text(
            "from pathlib import Path\n"
            "assert Path('fork.txt').read_text() == 'fork change\\n'\n"
            "assert Path('app.txt').read_text() == 'batch\\n'\n"
            "Path(%r).write_text('passed')\n" % str(marker))
        Path(f.work, "loop.json").write_text(json.dumps({
            "Test command": "%s %s" % (shlex.quote(sys.executable), shlex.quote(str(probe)))}))
        self.assert_fork_merged()
        self.assertEqual(marker.read_text(), "passed")
