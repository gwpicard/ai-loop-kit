"""Budget ceilings carry headroom so two changes need not edit the same constant."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# isort: split

from helpers import KIT

try:
    import test_size_inventory as inventory
    import test_text_budgets as text_budgets
except ImportError as error:
    if error.name not in ("test_size_inventory", "test_text_budgets"):
        raise
    inventory = text_budgets = None

ROOT = Path(__file__).resolve().parents[2]
RAISED = {
    "briefs/builder.md": 750,
    "briefs/contract-reviewer.md": 220,
    "skills/run/SKILL.md": 390,
    "skills/run/references/walk-away.md": 260,
    "skills/run-recovery/SKILL.md": 230,
    "skills/setup/SKILL.md": 1400,
    "skills/shape/SKILL.md": 1280,
    "skills/shape/references/questions.md": 260,
    "spec-format.md": 1260,
}


def measured_python():
    return sum(lines for owner in ("kit", "extras")
               for name, lines in inventory.python_lines(inventory.ROOT / owner).items()
               if not f"{owner}/{name}".startswith("extras/tests/"))


def measured_words():
    paths = [*KIT.joinpath("skills").rglob("*.md"), *KIT.joinpath("briefs").rglob("*.md"),
             *KIT.joinpath("agents").rglob("*.md"), KIT / "spec-format.md"]
    texts = {str(path.relative_to(KIT)): path.read_text() for path in paths}
    texts["extras/briefs/critic.md"] = (ROOT / "extras/briefs/critic.md").read_text()
    return texts


class CeilingHeadroomTest(unittest.TestCase):
    def test_D1_the_python_total_has_headroom_above_the_measured_size(self):
        assert inventory is not None, "tests/test_size_inventory.py must exist"
        self.assertGreaterEqual(inventory.TOTAL_BUDGET, 9650)
        self.assertGreater(inventory.TOTAL_BUDGET, measured_python())

    def test_D2_the_word_ceilings_have_headroom(self):
        assert text_budgets is not None, "tests/test_text_budgets.py must exist"
        self.assertGreaterEqual(text_budgets.TOTAL_BUDGET, 7100)
        texts = measured_words()
        self.assertGreater(text_budgets.TOTAL_BUDGET,
                           sum(len(text.split()) for text in texts.values()))
        for name, ceiling in RAISED.items():
            with self.subTest(name=name):
                self.assertGreaterEqual(text_budgets.BUDGETS[name], ceiling)
                self.assertGreater(text_budgets.BUDGETS[name], len(texts[name].split()))

    def test_D3_python_total_is_refused_one_over_and_passes_at_the_ceiling(self):
        assert inventory is not None, "tests/test_size_inventory.py must exist"
        budget = inventory.TOTAL_BUDGET
        counts = {f"scripts/p{n}.py": 700 for n in range(budget // 700)}
        counts["scripts/tail.py"] = budget - sum(counts.values())
        inventory.check_sizes(counts)
        counts["scripts/extra.py"] = 1
        with self.assertRaisesRegex(AssertionError, f"{budget + 1}.*{budget}"):
            inventory.check_sizes(counts)

    def test_D3_word_total_and_single_file_are_refused_one_over(self):
        assert text_budgets is not None, "tests/test_text_budgets.py must exist"
        budgets = {"a.md": 3, "b.md": 3}
        text_budgets.check_budgets({"a.md": "x x x", "b.md": "x x x"}, budgets, 6)
        with self.assertRaisesRegex(AssertionError, "total"):
            text_budgets.check_budgets({"a.md": "x x x", "b.md": "x x x"}, budgets, 5)
        with self.assertRaisesRegex(AssertionError, "a.md: 4 words exceeds budget 3"):
            text_budgets.check_budgets({"a.md": "x x x x", "b.md": "x"}, budgets, 99)

    def test_D4_design_says_a_ceiling_is_raised_only_at_a_release(self):
        text = " ".join((ROOT / "docs/DESIGN.md").read_text().split())
        self.assertIn("raised only at a release", text)
        self.assertIn("5 per cent", text)
        self.assertIn("rounded up", text)


if __name__ == "__main__":
    unittest.main()
