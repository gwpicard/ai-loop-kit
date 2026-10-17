"""Refuse a claimed piece that is already checked out."""
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import Project, git

# isort: split
import gate
import run
from loopkit import Refused


class PieceCheckoutTest(unittest.TestCase):
    def test_checked_out_piece_is_reported_before_claim_or_build(self):
        for location in ("another worktree", "the current checkout"):
            with self.subTest(location=location):
                project = Project()
                self.addCleanup(project.close)
                number = project.piece()
                gate.move(project.gh, project.root, number, "ready")
                if location == "another worktree":
                    folder = Path(project.tmp.name) / "another checkout"
                    git(project.root, "worktree", "add", "--quiet", str(folder),
                        f"piece/{number}")
                else:
                    folder = project.root
                    git(folder, "switch", "--quiet", f"piece/{number}")
                before = git(folder, "rev-parse", "HEAD")
                with patch.object(run, "build_once") as builder, \
                        self.assertRaises(Refused) as caught:
                    run.build_piece(project.gh, project.root, number, 1)
                self.assertIn(f"piece/{number} is already checked out", str(caught.exception))
                self.assertIn(str(folder), str(caught.exception))
                self.assertEqual(gate.state_of(project.gh.issue(number)), "ready")
                self.assertEqual(git(folder, "rev-parse", "HEAD"), before)
                self.assertTrue(folder.is_dir())
                builder.assert_not_called()
