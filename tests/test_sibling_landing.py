"""A sibling piece landing in the same judge folder does not hand the next piece back."""
from __future__ import annotations

from helpers import JUDGE, SPEC, Project, git

# isort: split

import unittest
from unittest.mock import patch

import gate
import run


class SiblingLandingTest(unittest.TestCase):
    def test_the_builder_starts_after_a_sibling_judge_lands_beside_this_one(self):
        p = Project()
        self.addCleanup(p.close)
        (p.root / ".loop").mkdir()
        p.loop_section("true")
        n = gate.capture(p.gh, "Piece b", SPEC.replace("judge_add.py", "tests/judge/test_b.py"))
        git(p.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        (p.root / "tests/judge").mkdir(parents=True)
        (p.root / "tests/judge/test_b.py").write_text(JUDGE)
        git(p.root, "add", "-A")
        git(p.root, "commit", "--quiet", "-m", "Judge")
        git(p.root, "switch", "--quiet", "main")
        gate.move(p.gh, p.root, n, "ready")
        (p.root / "tests/judge").mkdir(parents=True, exist_ok=True)
        (p.root / "tests/judge/test_a.py").write_text(JUDGE)
        git(p.root, "add", "-A")
        git(p.root, "commit", "--quiet", "-m", "A sibling piece lands")
        git(p.root, "push", "--quiet", "origin", "main")
        with patch("run.build_once", side_effect=RuntimeError("builder started")) as builder:
            try:
                run.build_piece(p.gh, p.root, n, 1)
            except RuntimeError:
                pass
        builder.assert_called_once()
        self.assertNotIn("frozen", "\n".join(p.gh.comments(n)))


if __name__ == "__main__":
    unittest.main()
