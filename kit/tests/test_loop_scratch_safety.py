"""Loop exit preserves unsaved work in a stray scratch worktree."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import run_git
import loop


class ScratchSafetyTest(unittest.TestCase):
    def test_modified_scratch_worktree_is_reported_and_preserved(self):
        with tempfile.TemporaryDirectory(prefix="loop-scratch-safety-", dir="/tmp") as folder:
            root = Path(folder).resolve()
            project, tree = root / "project", root / "scratch"
            project.mkdir()
            run_git(["init", "--template=", "-b", "main"], project)
            run_git(["-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "--allow-empty", "-m", "initial"], project)
            run_git(["worktree", "add", "--detach", str(tree)], project)
            try:
                marker = tree / "unsaved.txt"
                marker.write_text("keep this work\n", encoding="utf-8")
                with mock.patch.object(loop, "say") as say:
                    loop.clean_up(str(project), set())
                self.assertEqual(marker.read_text(encoding="utf-8"), "keep this work\n")
                self.assertIn(str(tree), say.call_args.args[0])
                self.assertIn("worktree " + str(tree) + "\n",
                              loop.git(["worktree", "list", "--porcelain"], cwd=project))
            finally:
                run_git(["worktree", "remove", "--force", str(tree)], project)
