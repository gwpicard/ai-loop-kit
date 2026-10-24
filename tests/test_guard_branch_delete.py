"""The guard lets an agent delete a remote branch only when its live tip is in main."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from helpers import KIT, Project, git


def load_guard():
    spec = importlib.util.spec_from_file_location("guard_delete", KIT / "hooks" / "guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BranchDeleteTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.guard = load_guard()
        root = self.p.root
        for name, merge in (("done-work", True), ("open-work", False)):
            git(root, "switch", "--quiet", "-c", name, "main")
            (root / f"{name}.txt").write_text(name + "\n")
            git(root, "add", f"{name}.txt")
            git(root, "commit", "--quiet", "-m", name)
            git(root, "push", "--quiet", "-u", "origin", name)
            git(root, "switch", "--quiet", "main")
            if merge:
                git(root, "merge", "--quiet", "--no-ff", "-m", "Merge", name)
                git(root, "push", "--quiet", "origin", "main")
        for name in ("piece/3", "stable"):
            git(root, "push", "--quiet", "origin", f"main:refs/heads/{name}")
        git(root, "tag", "v1")
        git(root, "push", "--quiet", "origin", "v1")
        git(root, "fetch", "--quiet", "origin")

    def check(self, command, builder=False):
        return self.guard.check_command(f"git -C {self.p.root} {command}", builder)

    def test_merged_branch_may_be_deleted(self):
        for command in ("push origin --delete done-work", "push origin -d done-work",
                        "push origin :done-work", "push origin --delete refs/heads/done-work"):
            with self.subTest(command=command):
                self.assertIsNone(self.check(command))

    def test_unmerged_branch_is_refused(self):
        reason = self.check("push origin --delete open-work")
        self.assertIn("not merged", reason)
        self.assertIn("not merged", self.check("push origin --delete done-work open-work"))

    def test_kept_branches_are_refused_even_when_merged(self):
        for name in ("main", "master", "stable", "piece/3", "refs/heads/main"):
            with self.subTest(name=name):
                self.assertIn("not allowed", self.check(f"push origin --delete {name}"))
                self.assertIn("not allowed", self.check(f"push origin :{name}"))

    def test_tags_and_missing_branches_are_refused(self):
        self.assertIn("no branch", self.check("push origin --delete v1"))
        self.assertIn("no branch", self.check("push origin --delete nothing-here"))

    def test_new_commits_on_the_remote_are_seen_through_a_stale_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            other = Path(folder) / "other"
            git(Path(folder), "clone", "--quiet", "-b", "done-work", str(self.p.remote), str(other))
            git(other, "config", "user.email", "o@example.invalid")
            git(other, "config", "user.name", "Other")
            (other / "late.txt").write_text("late\n")
            git(other, "add", "late.txt")
            git(other, "commit", "--quiet", "-m", "Late work")
            git(other, "push", "--quiet", "origin", "done-work")
        self.assertIn("not merged", self.check("push origin --delete done-work"))

    def test_builders_force_pushes_and_mixed_pushes_stay_refused(self):
        self.assertIn("builders never push", self.check("push origin --delete done-work", True))
        self.assertIn("force push", self.check("push --force origin --delete done-work"))
        self.assertIsNotNone(self.check("push origin :done-work main"))
        self.assertIsNotNone(self.check("push --delete"))


if __name__ == "__main__":
    unittest.main()
