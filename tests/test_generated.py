"""Generated files cannot pass submit, even when a builder force-adds them."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import GOOD_CODE, Project, git

sys.path.insert(0, str(Path(__file__).resolve().parent / "field"))
import audit
import gate
import run
from loopkit import Refused, records


class GeneratedTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def claimed(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build")
        return n, folder

    def test_submit_refuses_force_added_runtime_and_generated_files(self):
        n, folder = self.claimed()
        paths = (".loop/why.md", ".loop/outcome", ".loop/hypothesis",
                 ".loop/hypotheses", ".loop/logs/attempt.log", "pkg/__pycache__/a.pyc",
                 "node_modules/pkg/index.js", ".coverage", "mutants/result.txt")
        for name in paths:
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("runtime output\n")
            git(folder, "add", "--force", name)
            git(folder, "commit", "--quiet", "-m", "Add runtime output")
            self.assertTrue(audit.generated(name))
            with self.assertRaises(Refused) as refused:
                gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
            self.assertIn(name, refused.exception.reason)
            self.assertIn("state:building", self.p.gh.issue(n)["labels"])
            git(folder, "rm", "--", name)
            git(folder, "commit", "--quiet", "-m", "Remove runtime output")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_gate_and_audit_share_generated_path_rules(self):
        paths = {
            ".loop/why.md": True, ".loop/outcome": True, ".loop/hypothesis": True,
            "a/__pycache__/b.pyc": True, "pkg.egg-info/PKG-INFO": True,
            ".DS_Store": True, "src/coverage.xml": True,
            "src/loop/a.py": False, "docs/node.md": False, "README.md": False,
            "nested/.loop/example.txt": False,
        }
        for path, expected in paths.items():
            with self.subTest(path=path):
                self.assertEqual(audit.generated(path), expected)
                self.assertEqual(gate.generated(path), expected)

    def test_submit_refuses_staged_generated_files(self):
        n, folder = self.claimed()
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/why.md").write_text("runtime output\n")
        git(folder, "add", "--force", ".loop/why.md")
        with self.assertRaises(Refused) as refused:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn(".loop/why.md", refused.exception.reason)
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def assert_quoted_generated_files_refused(self, committed):
        paths = (".loop/café.md", ".loop/tab\tname.md", ".loop/line\nname.md",
                 '.loop/"quoted".md')
        for name in paths:
            with self.subTest(path=name):
                n, folder = self.claimed()
                (folder / ".loop").mkdir(exist_ok=True)
                (folder / name).write_text("runtime output\n")
                git(folder, "add", "--force", name)
                if committed:
                    git(folder, "commit", "--quiet", "-m", "Add runtime output")
                self.assertTrue(audit.generated(name))
                with self.assertRaises(Refused) as refused:
                    gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
                self.assertIn(name, refused.exception.reason)
                self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def test_submit_refuses_committed_quoted_generated_files(self):
        self.assert_quoted_generated_files_refused(committed=True)

    def test_submit_refuses_staged_quoted_generated_files(self):
        self.assert_quoted_generated_files_refused(committed=False)

    def test_untracked_generated_files_do_not_block_submit(self):
        n, folder = self.claimed()
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/why.md").write_text("runtime output\n")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_blocked_cleanup_returns_an_environment_failure(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        calls = []

        def build(folder, *args, **kwargs):
            calls.append(folder)
            (folder / ".loop").mkdir(exist_ok=True)
            if len(calls) == 1:
                (folder / "habits.py").write_text(GOOD_CODE)
                (folder / ".loop/why.md").write_text("runtime output\n")
                git(folder, "add", "--force", "habits.py", ".loop/why.md")
                git(folder, "commit", "--quiet", "-m", "Build with runtime output")
            else:
                (folder / ".loop/outcome").write_text(
                    "environment\nCleanup of .loop/why.md was blocked by permissions.\n")
            return "done"

        with patch.object(run, "build_once", side_effect=build), patch.object(
                run, "review_piece", side_effect=AssertionError("unexpected review")):
            result = run.build_piece(self.p.gh, self.p.root, n, 3)
        seen = records(self.p.gh.comments(n))
        handback = [record for record in seen if record.get("move") == "give-back"][-1]
        self.assertEqual(handback["type"], "environment")
        self.assertEqual(handback["attempts"], 2)
        self.assertIn("Cleanup of .loop/why.md", handback["reason"])
        self.assertIn("back to shaping", result)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(record.get("move") == "submit" for record in seen))
        self.assertEqual(self.p.gh.prs, {})


if __name__ == "__main__":
    unittest.main()
