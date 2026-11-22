"""Loop exit handles a scratch worktree whose path contains a newline."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import run_git
import loop


class ScratchNewlineTest(unittest.TestCase):
    def test_cleanup_reports_and_removes_the_complete_worktree_path(self):
        with tempfile.TemporaryDirectory(prefix="loop-scratch-newline-", dir="/tmp") as folder:
            root = Path(folder).resolve()
            project, tree = root / "project", root / "scratch\nreview"
            project.mkdir()
            run_git(["init", "--template=", "-b", "main"], project)
            run_git(["-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "--allow-empty", "-m", "initial"], project)
            run_git(["worktree", "add", "--detach", str(tree)], project)
            try:
                with mock.patch.object(loop, "say") as say:
                    loop.clean_up(str(project), set())
                self.assertIn(str(tree), say.call_args.args[0])
                self.assertFalse(tree.exists(), "scratch worktree folder survived cleanup")
                self.assertNotIn("worktree " + str(tree),
                                 loop.git(["worktree", "list", "--porcelain", "-z"], cwd=project))
            finally:
                if tree.exists():
                    run_git(["worktree", "remove", str(tree)], project)
