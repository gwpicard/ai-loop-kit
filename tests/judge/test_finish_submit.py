"""A piece whose submit was recorded before a crash is finished, not built again."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import GOOD_CODE, Project, git

# isort: split

import gate
import pr
import run
from loopkit import records
import test_size_inventory

ROOT = Path(__file__).resolve().parents[2]


class Crash(BaseException):
    """Stands for the run dying; BaseException so no handler in the run swallows it."""


class FinishSubmitTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def building(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build habits")
        return n, folder

    def crash_after_submit(self, n, folder, existing_pr=False):
        """Kill the run between gh.comment and gh.set_labels in gate.move."""
        if existing_pr:
            self.p.gh.create_pr(f"piece/{n}", "Earlier title", "Earlier evidence")
        original = self.p.gh.set_labels

        def die(number, add, remove):
            if "state:approval" in add:
                raise Crash()
            return original(number, add, remove)

        with patch.object(self.p.gh, "set_labels", side_effect=die), self.assertRaises(Crash):
            pr.open_pull_request(self.p.gh, self.p.root, folder, n, self.p.gh.issue(n), 1, "ok")
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])
        self.assertEqual(records(self.p.gh.comments(n))[-1]["move"], "submit")

    def moves(self, n):
        return [r["move"] for r in records(self.p.gh.comments(n))]

    def test_D1_submit_for_the_branch_head_moves_to_approval_without_a_requeue(self):
        n, folder = self.building()
        self.crash_after_submit(n, folder)
        before = self.moves(n)
        result = run.recover_building(self.p.gh, self.p.root)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:approval", labels)
        self.assertNotIn("state:building", labels)
        self.assertEqual(self.moves(n), before)
        self.assertEqual(self.moves(n).count("submit"), 1)
        self.assertEqual(result, [f"piece {n}: finished after a crash: moved to approval"])

    def test_D2_a_claim_as_newest_record_is_requeued(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        run.recover_building(self.p.gh, self.p.root)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.moves(n)[-1], "requeue")

    def test_D2_a_submit_for_another_commit_is_requeued(self):
        n, folder = self.building()
        self.crash_after_submit(n, folder)
        (folder / "habits.py").write_text(GOOD_CODE + "\n# later change\n")
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Later change")
        git(folder, "push", "--quiet", "origin", f"piece/{n}")
        run.recover_building(self.p.gh, self.p.root)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.moves(n)[-1], "requeue")
        self.assertEqual(self.p.gh.prs, {})

    def test_D3_a_crash_between_comment_and_labels_ends_in_approval_with_a_pull_request(self):
        for existing in (False, True):
            with self.subTest(pull_request_existed=existing):
                self.setUp()
                n, folder = self.building()
                self.crash_after_submit(n, folder, existing_pr=existing)
                run.recover_building(self.p.gh, self.p.root)
                self.assertIn("state:approval", self.p.gh.issue(n)["labels"])
                self.assertEqual(self.moves(n).count("submit"), 1)
                found = self.p.gh.prs[f"piece/{n}"]
                self.assertEqual(found["state"], "OPEN")
                self.assertEqual(len(self.p.gh.prs), 1)
                self.assertIn(f"Closes #{n}", found["body"])
                self.assertIn(git(folder, "rev-parse", "HEAD"), found["body"])

    def test_D5_a_failed_fetch_requeues_and_the_run_continues(self):
        n, folder = self.building()
        self.crash_after_submit(n, folder)
        git(self.p.root, "remote", "set-url", "origin", str(self.p.root / "missing.git"))
        result = run.recover_building(self.p.gh, self.p.root)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.moves(n)[-1], "requeue")
        self.assertEqual(len(result), 1)

    def test_D4_a_building_piece_with_no_submit_is_requeued_as_a_dead_run(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        for count in (1, 2, 3):
            gate.move(self.p.gh, self.p.root, n, "building")
            run.recover_building(self.p.gh, self.p.root)
            record = records(self.p.gh.comments(n))[-1]
            self.assertEqual(record["cause"], "dead-run")
            self.assertEqual(record["move"], "requeue" if count < 3 else "give-back")
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])

    def test_D6_recovery_lives_in_its_own_module_within_the_line_budgets(self):
        scripts = ROOT / "kit" / "scripts"
        self.assertTrue((scripts / "recovery.py").is_file())
        self.assertLessEqual(len((scripts / "gate.py").read_text().splitlines()), 800)
        counts = test_size_inventory.python_lines(ROOT / "kit")
        counts.update({f"extras/{k}": v for k, v in
                       test_size_inventory.python_lines(ROOT / "extras").items()})
        test_size_inventory.check_sizes(counts)


if __name__ == "__main__":
    unittest.main()
