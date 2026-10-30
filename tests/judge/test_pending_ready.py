"""A piece with unfinished blockers is ready with its base check pending."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project, git

# isort: split

import gate
from loopkit import Refused, last_record

ROOT = Path(__file__).resolve().parents[2]
RISKS = """
## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none
Depends on: {depends}
"""
BODY = """## Intent
Use the helper.

Out of scope:
- Anything else.

## Contract
- D1: the helper answers.

## Exit
### Tests
Command: `python3 judge_dep.py`
Files:
- judge_dep.py
"""
# Records that it ran, then fails by assertion naming D1, as a real judge does.
JUDGE = '''import sys
open({marker!r}, "a").write("ran\\n")
print("FAIL test_D1_helper AssertionError helper missing")
sys.exit(1)
'''
PASSING = "open({marker!r}, 'a').write('ran\\n')\nprint('ok test_D1_helper')\n"


class PendingReadyTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.marker = Path(self.p.tmp.name) / "ran.txt"
        self.p.loop_section(f"touch {self.marker}")
        self.blocker = self.p.gh.create_issue("Blocker", SPEC, ["state:shaping"])

    def piece(self, depends=None, judge=JUDGE):
        body = BODY + RISKS.format(depends=depends if depends is not None else self.blocker)
        n = gate.capture(self.p.gh, "Dependent", body)
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        (self.p.root / "judge_dep.py").write_text(judge.format(marker=str(self.marker)))
        git(self.p.root, "add", "judge_dep.py")
        git(self.p.root, "commit", "--quiet", "-m", "Judge")
        git(self.p.root, "switch", "--quiet", "main")
        return n

    def ready_record(self, n):
        return last_record(self.p.gh.comments(n), "ready")

    def test_D1_unfinished_blocker_gives_a_pending_ready_without_running_checks(self):
        n = self.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        record = self.ready_record(n)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "ready")
        self.assertEqual((record["base_check"], record["blockers"]), ("pending", [self.blocker]))
        self.assertEqual(record["checks"][0]["type"], "tests")
        self.assertFalse(self.marker.exists(), "neither the Test command nor the judge ran")
        note = self.p.gh.notes[n][-1][1]
        self.assertIn(f"{self.blocker}", note)
        self.assertNotIn("fails on main as it should", note)

    def test_D2_self_missing_and_dropped_blockers_are_still_refused(self):
        dropped = self.p.gh.create_issue("Dropped", SPEC, ["state:dropped"])
        for depends, words in (("{n}", "depends on itself"), ("99", "which is missing"),
                               (str(dropped), "which is dropped")):
            with self.subTest(depends=depends):
                n = len(self.p.gh.issues) + 1
                self.piece(depends.format(n=n))
                with self.assertRaises(Refused) as refusal:
                    gate.move(self.p.gh, self.p.root, n, "ready")
                self.assertIn(words, refusal.exception.reason)

    def test_D2_a_missing_judge_commit_is_refused(self):
        n = gate.capture(self.p.gh, "No judge", BODY + RISKS.format(depends=self.blocker))
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn(f"there is no branch piece/{n}", refusal.exception.reason)

    def test_D2_a_judge_with_a_lint_problem_is_refused(self):
        n = self.piece(judge="def broken(:\n")
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("quality problems", refusal.exception.reason)
        self.assertFalse(self.marker.exists())

    def test_D3_a_claim_on_a_pending_piece_names_the_blockers(self):
        n = self.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn(f"the base check has not run; it runs when pieces {self.blocker} are done",
                      refusal.exception.reason)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "ready")

    def test_D4_the_guidance_says_what_ready_means_with_unfinished_blockers(self):
        design = " ".join((ROOT / "docs/DESIGN.md").read_text().split())
        self.assertIn("the contract is approved and the judge is captured", design)
        self.assertIn("the base check runs when its blockers are done", design)
        shape = " ".join((ROOT / "kit/skills/shape/SKILL.md").read_text().split())
        for phrase in ("its Approach names how its tests build inputs through each blocker's "
                       "public interface",
                       "the judge calls that interface as the blocker's Approach describes it",
                       "`Dependencies` (each blocker's Approach, headed by its number; "
                       "empty when there is none)",
                       "reports the base check as pending and runs the static checks only",
                       "the run does the base check when the blockers are done",
                       "hands the piece back to shaping with the reason if it refuses",
                       "for a piece with unfinished blockers, at its base check"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, shape)
        self.assertNotIn("stub that code", shape)
        spec = " ".join((ROOT / "kit/spec-format.md").read_text().split())
        self.assertIn("base check", spec)
        self.assertNotIn("the judge must still fail by assertion", spec)

    def test_D5_status_marks_a_ready_piece_with_a_pending_base_check(self):
        n = self.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        lines = gate.status(self.p.gh).splitlines()
        ready = next(line for line in lines if line.startswith("ready:"))
        self.assertIn(f"{n} (base check pending) Dependent", ready)

    def test_D7_the_budgets_cover_the_measured_guidance_and_python(self):
        import test_size_inventory
        import test_text_budgets
        test_text_budgets.TextBudgetTest("test_guidance_word_budgets").debug()
        test_size_inventory.SizeInventoryTest(
            "test_kit_python_budgets_and_install_size").debug()

    def test_D6_stays_a_finished_blocker_gets_the_full_check(self):
        self.p.gh.set_labels(self.blocker, ["state:done"], ["state:shaping"])
        n = self.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        record = self.ready_record(n)
        self.assertNotIn("base_check", record)
        self.assertTrue(self.marker.exists(), "the Test command and the judge ran")

    def test_D6_stays_no_blocker_gets_the_full_check_and_a_passing_judge_is_refused(self):
        n = self.piece(depends="none", judge=PASSING)
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("already passes on main", refusal.exception.reason)

    def test_D6_stays_a_passing_judge_is_refused_when_the_blocker_is_done(self):
        self.p.gh.set_labels(self.blocker, ["state:done"], ["state:shaping"])
        n = self.piece(judge=PASSING)
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("already passes on main", refusal.exception.reason)


if __name__ == "__main__":
    unittest.main()
