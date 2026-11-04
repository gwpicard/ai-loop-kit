# Intent: every agreed piece of a split is captured at once as a stub in state:shaping.
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "kit" / "scripts"))
from helpers import Project

# isort: split

import gate
from loopkit import Refused

ROOT = HERE.parents[1]
STUB = "## Intent\nShow streaks.\n\nOpen questions:\n- Which window counts?\n"


def shape_text() -> str:
    return " ".join((ROOT / "kit/skills/shape/SKILL.md").read_text().split())


def step(n: int) -> str:
    text = (ROOT / "kit/skills/shape/SKILL.md").read_text()
    body = text.split("## Steps", 1)[1].split("## Rules", 1)[0]
    parts = re.split(r"(?m)^(?=\d+\. )", body)
    found = [p for p in parts if p.startswith(f"{n}. ")]
    assert found, f"step {n} must exist in the shape skill"
    return " ".join(found[0].split())


def rules() -> str:
    text = (ROOT / "kit/skills/shape/SKILL.md").read_text()
    return " ".join(text.split("## Rules", 1)[1].split())


class CaptureSplitTest(unittest.TestCase):
    def test_D1_step_3_captures_every_agreed_piece_as_a_stub(self):
        three = step(3)
        for phrase in ("gate.py", "capture", "--body-file", "every agreed piece",
                       "## Intent", "Open questions:", "issue number", "never by position"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, three)

    def test_D2_step_5_fills_the_stub_without_capturing(self):
        five = step(5)
        self.assertIn("gate.py", five)
        self.assertIn("spec <n> --body-file", five)
        self.assertIn("piece <n> spec replaced", five)
        self.assertNotIn("capture", five)
        returned = next(line for line in rules().split(" - ") if "Given a piece number" in line)
        self.assertIn("Skip step 3's capture", returned)
        self.assertIn("replace the body per step 5", returned)
        self.assertNotIn("step 8", returned)

    def test_D3_rules_say_to_capture_or_tell_the_person_it_will_be_lost(self):
        text = rules()
        self.assertIn("no issue number", text)
        self.assertIn("capture it", text)
        self.assertIn("lost", text)

    def test_D4_stays_a_stub_is_captured_into_shaping_and_listed(self):
        p = Project()
        self.addCleanup(p.close)
        n = gate.capture(p.gh, "Streaks", STUB)
        self.assertEqual(gate.state_of(p.gh.issue(n)), "shaping")
        shaping = next(line for line in gate.status(p.gh).splitlines()
                       if line.startswith("shaping:"))
        self.assertEqual(shaping, f"shaping: {n} Streaks")

    def test_D5_stays_a_stub_is_refused_at_ready_and_stays_in_shaping(self):
        p = Project()
        self.addCleanup(p.close)
        n = gate.capture(p.gh, "Streaks", STUB)
        with self.assertRaises(Refused) as refusal:
            gate.move(p.gh, p.root, n, "ready")
        self.assertTrue(refusal.exception.reason)
        self.assertEqual(gate.state_of(p.gh.issue(n)), "shaping")

    def test_D6_the_shape_skill_stays_within_its_ceiling_and_keeps_its_phrases(self):
        import test_pending_ready
        import test_text_budgets
        words = len(shape_text().split())
        self.assertLessEqual(words, 1280)
        self.assertLessEqual(words, test_text_budgets.BUDGETS["skills/shape/SKILL.md"])
        test_pending_ready.PendingReadyTest(
            "test_D4_the_guidance_says_what_ready_means_with_unfinished_blockers").debug()


if __name__ == "__main__":
    unittest.main()
