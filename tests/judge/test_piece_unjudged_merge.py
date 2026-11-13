# Intent: the gate marks a piece done at a merge later than the judged commit, and reports the difference.
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import GOOD_CODE, git

# isort: split

import gate
from loop_fixtures import GateFixture
from test_land import LandFixture

COULD_NOT = "the gate could not compare the merged head with the commit it judged"


class UnjudgedMergeTest(GateFixture, unittest.TestCase):
    def submitted(self):
        """A piece the gate judged and submitted, its branch pushed to origin."""
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.p.gh.create_pr(f"piece/{n}", "t", "b")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Build")
        judged = gate.last_record(self.p.gh.comments(n), "submit")["commit"]
        git(self.p.root, "push", "--quiet", "origin", f"piece/{n}")
        git(self.p.root, "switch", "--quiet", "main")
        return n, judged

    def push_more(self, n, files, commits=1):
        """Commits made elsewhere reach origin; the local repository never sees them."""
        other = self.p.root.parent / "elsewhere"
        git(self.p.root.parent, "clone", "--quiet", "--branch", f"piece/{n}",
            str(self.p.remote), str(other))
        git(other, "config", "user.email", "test@example.invalid")
        git(other, "config", "user.name", "Test")
        for index in range(commits):
            for name in files:
                (other / name).write_text(f"changed {index}\n")
            git(other, "add", "-A")
            git(other, "commit", "--quiet", "-m", f"More {index}")
        git(other, "push", "--quiet", "origin", f"piece/{n}")
        return git(other, "rev-parse", "HEAD")

    def merge_at(self, n, head):
        pr = self.p.gh.prs[f"piece/{n}"]
        pr["state"] = "MERGED"
        if head is not None:
            pr["headRefOid"] = head

    def merged_record(self, n):
        return gate.last_record(self.p.gh.comments(n), "merged")

    def test_D1_line_names_merged_judged_and_unjudged_count(self):
        n, judged = self.submitted()
        head = self.push_more(n, ["habits.py"], commits=2)
        self.merge_at(n, head)
        lines = gate.sync(self.p.gh, self.p.root)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])
        line = lines[0]
        self.assertTrue(line.startswith(f"{n}: approval → done (merged)."), line)
        self.assertIn(head[:7], line)
        self.assertIn(judged[:7], line)
        self.assertRegex(line, r"\b2 commits\b")
        self.assertEqual(len(lines), 1)

    def test_D2_line_names_each_changed_judge_file(self):
        n, _ = self.submitted()
        head = self.push_more(n, ["judge_add.py"])
        self.merge_at(n, head)
        line = gate.sync(self.p.gh, self.p.root)[0]
        self.assertIn("judge_add.py", line)
        self.assertNotIn("no judge file changed", line)

    def test_D2_line_says_when_no_judge_file_changed(self):
        n, _ = self.submitted()
        head = self.push_more(n, ["habits.py"])
        self.merge_at(n, head)
        line = gate.sync(self.p.gh, self.p.root)[0]
        self.assertIn("no judge file changed", line)
        self.assertNotIn("judge_add.py", line)

    def test_D3_merged_record_holds_the_difference(self):
        n, judged = self.submitted()
        head = self.push_more(n, ["judge_add.py"], commits=3)
        self.merge_at(n, head)
        gate.sync(self.p.gh, self.p.root)
        record = self.merged_record(n)
        self.assertEqual(record.get("judged"), judged)
        self.assertEqual(record.get("merged_head"), head)
        self.assertEqual(record.get("unjudged_commits"), 3)
        self.assertEqual(record.get("judge_files_changed"), ["judge_add.py"])

    def test_D3_record_lists_no_judge_files_when_none_changed(self):
        n, _ = self.submitted()
        head = self.push_more(n, ["habits.py"])
        self.merge_at(n, head)
        gate.sync(self.p.gh, self.p.root)
        record = self.merged_record(n)
        self.assertEqual(record.get("unjudged_commits"), 1)
        self.assertEqual(record.get("judge_files_changed"), [])

    def test_D4_no_merged_head_from_github_still_moves_to_done(self):
        n, _ = self.submitted()
        self.merge_at(n, None)
        lines = gate.sync(self.p.gh, self.p.root)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])
        self.assertIn(COULD_NOT, lines[0])

    def test_D4_unfetchable_merged_head_still_moves_to_done(self):
        n, _ = self.submitted()
        self.merge_at(n, "0123456789abcdef0123456789abcdef01234567")
        lines = gate.sync(self.p.gh, self.p.root)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])
        self.assertIn(COULD_NOT, lines[0])
        self.assertEqual(len(lines), 1)

    def test_D5_merge_at_the_judged_commit_adds_nothing(self):
        n, judged = self.submitted()
        self.merge_at(n, judged)
        lines = gate.sync(self.p.gh, self.p.root)
        self.assertEqual(lines, [f"{n}: approval → done (merged)."])
        self.assertNotIn("unjudged_commits", self.merged_record(n) or {})


class RunMergeTest(LandFixture, unittest.TestCase):
    def test_D6_run_merge_into_the_base_moves_the_piece_to_done(self):
        n, folder, result = self.gated()
        line = self.land(n, folder, result)
        self.assertEqual(line, f"piece {n}: merged into trip: https://example.invalid/pull/{n}")
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "done")
        self.assertRegex(line, r"^piece \d+: merged into trip")


if __name__ == "__main__":
    unittest.main()
