"""Unit tests for kit/scripts/loop/run/summary.py: the morning summary."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop.paths import Paths  # noqa: E402
from loop.run import record, summary  # noqa: E402


class SummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = Path(tempfile.mkdtemp())
        (folder / ".git").mkdir()
        self.paths = Paths.for_project(folder, data_base=folder / "data", kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2, 3, 4],
                                           attended=True, merge_pre_approved=False)
        self.rec.set_status(1, record.BUILT, title="Open the menu")
        self.rec.set_status(2, record.PARKED_PERSON, title="Pick a colour",
                            question="Which colour should the menu be?")
        self.rec.set_status(3, record.WAITING_PERSON, title="Push a branch",
                            next="tell the person to run gate.py sync")
        self.rec.set_status(4, record.SENT_BACK, title="Fix the bar", reason="the bar is wrong")
        self.rec.add_decision(1, "builder", "Used a plain list for the menu items.")
        self.rec.add_decision(None, "run", "Passed built_earlier=7 to the claim of piece 3.")
        self.rec.add_spend(1, 0.5)
        self.text = summary.render(self.rec)

    def test_every_piece_and_its_state_is_named(self) -> None:
        for needle in ("Open the menu", "built", "Pick a colour", "Push a branch", "Fix the bar"):
            self.assertIn(needle, self.text)

    def test_every_decision_made_alone_is_listed_with_who_made_it(self) -> None:
        self.assertIn("Used a plain list for the menu items.", self.text)
        self.assertIn("builder", self.text)
        self.assertIn("Passed built_earlier=7", self.text)

    def test_a_parked_question_and_a_waiting_next_line_are_shown(self) -> None:
        self.assertIn("Which colour should the menu be?", self.text)
        self.assertIn("tell the person to run gate.py sync", self.text)

    def test_the_spend_is_shown(self) -> None:
        self.assertIn("0.50", self.text)

    def test_the_run_with_no_decision_says_so(self) -> None:
        run = record.RunRecord.create(self.paths, "night-2", [1], attended=True,
                                      merge_pre_approved=False)
        self.assertIn("No decision was made alone", summary.render(run))

    def test_write_puts_the_summary_in_the_run_folder(self) -> None:
        target = summary.write(self.rec)
        self.assertEqual(target.parent, self.paths.run_dir("night-1"))
        self.assertEqual(target.read_text(encoding="utf-8"), self.text)

    def test_the_summary_has_no_em_dash(self) -> None:
        self.assertNotIn("—", self.text)


if __name__ == "__main__":
    unittest.main()
