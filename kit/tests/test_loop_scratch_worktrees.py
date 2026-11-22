"""Sessions confine scratch copies to the build; loop exit clears stray worktrees."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import run_git
import flow
import loop


class ScratchBriefTest(unittest.TestCase):
    def test_every_session_receives_the_build_scratch_folder_instruction(self):
        roles = sorted(p.stem for p in Path(flow.BRIEFS).glob("*.md")
                       if p.stem != "preamble")
        self.assertIn("reviewer", roles)
        for role in roles:
            with self.subTest(role=role):
                paragraphs = [" ".join(p.split()) for p in flow.brief(role).split("\n\n")
                              if "TMPDIR" in p]
                self.assertTrue(paragraphs, "%s has no TMPDIR instruction" % role)
                instruction = " ".join(paragraphs).lower()
                self.assertRegex(instruction, r"scratch cop(?:y|ies)")
                self.assertIn("git worktree", instruction)
                self.assertIn("build", instruction)
                self.assertRegex(instruction, r"remov|clean|delet")
                self.assertRegex(instruction, r"(?:never|not|avoid)[^.]*system temp")


class ScratchWorktreeTest(unittest.TestCase):
    def setUp(self):
        # Use the system temp folder even when the enclosing build sets TMPDIR.
        self.folder = tempfile.TemporaryDirectory(prefix="loop-scratch-test-", dir="/tmp")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        run_git(["init", "--template=", "-b", "main"], self.project)
        run_git(["-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "--allow-empty", "-m", "initial"], self.project)
        self.trees = []
        self.addCleanup(self.remove_trees)

    def remove_trees(self):
        for tree in reversed(self.trees):
            if tree.exists():
                run_git(["worktree", "remove", "--force", str(tree)], self.project)

    def add_tree(self, relative):
        tree = self.root / relative
        tree.parent.mkdir(parents=True, exist_ok=True)
        run_git(["worktree", "add", "--detach", str(tree)], self.project)
        self.trees.append(tree)
        return tree

    def test_cleanup_names_and_removes_each_system_temp_worktree_using_git(self):
        trees = [self.add_tree("review-base"),
                 self.add_tree(".loop-worktrees-extra/review with spaces")]
        with mock.patch.object(loop, "say") as say, \
                mock.patch.object(loop, "git", wraps=loop.git) as git, \
                mock.patch.object(loop.shutil, "rmtree", side_effect=AssertionError(
                    "cleanup must use git worktree remove")):
            loop.clean_up(str(self.project), set())
        line = next(c.args[0] for c in say.call_args_list
                    if c.args[0].startswith("left behind:"))
        commands = [c.args[0] for c in git.call_args_list]
        self.assertEqual(commands[0], ["worktree", "prune"])
        registered = loop.git(["worktree", "list", "--porcelain"], cwd=self.project)
        for tree in trees:
            with self.subTest(tree=tree):
                self.assertIn(str(tree), line)
                self.assertFalse(tree.exists(), "scratch worktree was left in system temp")
                self.assertNotIn("worktree " + str(tree) + "\n", registered)
                self.assertTrue(any(c[:2] == ["worktree", "remove"] and str(tree) in c
                                    for c in commands), "worktree was not removed through git")

    def test_cleanup_does_not_report_or_remove_a_running_build_worktree(self):
        tree = self.add_tree(".loop-worktrees/project-active")
        marker = tree / "unsaved.txt"
        marker.write_text("running build\n", encoding="utf-8")
        with mock.patch.object(loop, "say") as say:
            loop.clean_up(str(self.project), set())
        line = next(c.args[0] for c in say.call_args_list
                    if c.args[0].startswith("left behind:"))
        self.assertTrue(tree.is_dir())
        self.assertEqual(marker.read_text(encoding="utf-8"), "running build\n")
        self.assertIn("worktree " + str(tree) + "\n",
                      loop.git(["worktree", "list", "--porcelain"], cwd=self.project))
        self.assertNotIn(str(tree), line, "running build was reported as stray")
