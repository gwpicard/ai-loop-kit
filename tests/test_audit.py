"""Checks for the field audit: each rule catches the failure it names."""
from __future__ import annotations

import os
import stat
import sys
import unittest
from pathlib import Path

from helpers import Project, git
from test_loop import FAKE_CLAUDE

sys.path.insert(0, str(Path(__file__).resolve().parent / "field"))
import audit  # noqa: E402
import gate  # noqa: E402
import run  # noqa: E402


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        fake = Path(self.p.tmp.name) / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        os.environ["FAKE_MODE"] = "good"
        self.addCleanup(os.environ.pop, "LOOP_CLAUDE", None)
        self.addCleanup(os.environ.pop, "FAKE_MODE", None)

    def built_and_merged(self) -> int:
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        run.build_piece(self.p.gh, self.p.root, n, 1)
        self.p.gh.prs[f"piece/{n}"]["state"] = "MERGED"
        gate.sync(self.p.gh, self.p.root)
        return n

    def build_folder(self, n: int) -> Path:
        return self.p.root / ".loop" / "worktrees" / f"piece-{n}"

    def audit(self, n: int, head: str = ""):
        branch = f"piece/{n}"
        head = head or git(self.p.root, "rev-parse", branch)
        files = git(self.p.root, "diff", "--name-only", f"main...{head}").splitlines()
        pr = {**self.p.gh.prs[branch], "head": head, "files": files} \
            if branch in self.p.gh.prs else None
        piece = {**self.p.gh.issue(n), "comments": self.p.gh.comments(n)}
        return audit.audit_piece(piece, pr, self.p.root)

    def test_a_clean_piece_breaks_no_rule(self):
        n = self.built_and_merged()
        broken, score = self.audit(n)
        self.assertEqual(broken, [])
        self.assertEqual((score["builds"], score["attempts"], score["changed_after_gate"]),
                         (1, 1, False))

    def test_a_label_set_by_hand_breaks_the_records_rule(self):
        n = self.p.piece()
        self.p.gh.set_labels(n, ["state:ready"], ["state:shaping"])
        broken, _ = self.audit(n)
        self.assertTrue(any(b.startswith("records:") for b in broken), broken)

    def test_a_commit_after_the_gate_is_scored(self):
        n = self.built_and_merged()
        folder = self.build_folder(n)
        (folder / "notes.txt").write_text("fixed by hand\n")
        git(folder, "add", "notes.txt")
        git(folder, "commit", "--quiet", "-m", "Hand fix")
        broken, score = self.audit(n)
        self.assertEqual(broken, [])
        self.assertTrue(score["changed_after_gate"])

    def test_a_changed_judge_and_generated_files_break_their_rules(self):
        n = self.built_and_merged()
        folder = self.build_folder(n)
        (folder / "judge_add.py").write_text("print('ok')\n")
        (folder / "x.pyc").write_text("")
        git(folder, "add", "-f", "judge_add.py", "x.pyc")
        git(folder, "commit", "--quiet", "-m", "Bend the bar")
        broken, _ = self.audit(n)
        self.assertTrue(any(b.startswith("bar:") for b in broken), broken)
        self.assertTrue(any(b.startswith("generated:") for b in broken), broken)

    def test_done_without_a_merged_pull_request_breaks_the_merged_rule(self):
        n = self.built_and_merged()
        self.p.gh.prs[f"piece/{n}"]["state"] = "CLOSED"
        broken, _ = self.audit(n)
        self.assertTrue(any(b.startswith("merged:") for b in broken), broken)

    def test_generated_matches_the_gates_list(self):
        for path in ("a/__pycache__/b.pyc", "node_modules/x/y.js", ".loop/logs/a",
                     "pkg.egg-info/PKG-INFO", ".DS_Store"):
            self.assertTrue(audit.generated(path), path)
        for path in ("src/loop/a.py", "docs/node.md", "README.md"):
            self.assertFalse(audit.generated(path), path)


if __name__ == "__main__":
    unittest.main()
