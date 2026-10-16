"""Staging in linked worktrees must exclude runtime files and be atomic."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import git

# isort: split
import builder_prompt


class StagingTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / ".gitignore").write_text(".loop/\nignored.txt\n")
        (self.repo / "old.py").write_text("old = True\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "Initial")

    def stage(self, folder, env=None):
        return subprocess.run(
            [sys.executable, builder_prompt.__file__, "--stage"],
            cwd=folder, env=env, capture_output=True, text=True, check=False)

    def test_ignored_runtime_in_external_and_nested_linked_worktrees(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                folder = (self.repo / ".loop/builds/piece" if nested
                          else self.base / "cache/worktrees/piece")
                git(self.repo, "worktree", "add", "-qb", f"piece-{nested}", str(folder))
                (folder / ".loop/logs").mkdir(parents=True)
                (folder / ".loop/logs/attempt").write_text("runtime\n")
                (folder / ".loop/outcome").write_text("runtime\n")
                (folder / "src").mkdir()
                (folder / "src/new.py").write_text("value = 1\n")
                (folder / "old.py").unlink()
                (folder / "ignored.txt").write_text("ignored\n")
                result = self.stage(folder / "src")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(git(folder, "diff", "--cached", "--name-status").splitlines(),
                                 ["D\told.py", "A\tsrc/new.py"])
                self.assertEqual((folder / ".loop/outcome").read_text(), "runtime\n")

    def test_failed_add_preserves_original_index(self):
        for prestaged in (False, True):
            with self.subTest(prestaged=prestaged):
                folder = self.base / f"failure-{prestaged}"
                git(self.repo, "worktree", "add", "-qb", f"failure-{prestaged}", str(folder))
                if prestaged:
                    (folder / "saved.py").write_text("saved = True\n")
                    git(folder, "add", "saved.py")
                before = git(folder, "diff", "--cached")
                (folder / "a.py").write_text("value = 1\n")
                (folder / ".gitattributes").write_text("z.py filter=broken\n")
                (folder / "z.py").write_text("value = 2\n")
                env = dict(os.environ, GIT_CONFIG_COUNT="2",
                           GIT_CONFIG_KEY_0="filter.broken.clean", GIT_CONFIG_VALUE_0="false",
                           GIT_CONFIG_KEY_1="filter.broken.required", GIT_CONFIG_VALUE_1="true")
                result = self.stage(folder, env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("clean filter 'broken' failed", result.stderr)
                self.assertEqual(git(folder, "diff", "--cached"), before)
                self.assertFalse(Path(git(folder, "rev-parse", "--absolute-git-dir"),
                                      "index.lock").exists())

    def test_partial_add_failure_does_not_publish_index(self):
        (self.repo / "a.py").write_text("value = 1\n")
        (self.repo / ".loop").mkdir()
        (self.repo / ".loop/outcome").write_text("runtime\n")
        original_run = subprocess.run

        def failing_add(command, **kwargs):
            if command[:2] == ["git", "add"]:
                command = ["git", "add", "-A", "--", ":/", ":(top).loop"]
                kwargs.pop("input", None)
            return original_run(command, **kwargs)

        previous = Path.cwd()
        try:
            os.chdir(self.repo)
            with patch.object(builder_prompt.subprocess, "run", side_effect=failing_add):
                status = builder_prompt.stage()
        finally:
            os.chdir(previous)
        self.assertNotEqual(status, 0)
        self.assertEqual(git(self.repo, "diff", "--cached", "--name-only"), "")
