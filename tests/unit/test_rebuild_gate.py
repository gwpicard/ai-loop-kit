"""Move 8 has a checks module, so the gate no longer refuses it as not installed."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import moves, states  # noqa: E402


class RebuildGateTest(unittest.TestCase):
    def test_move_eight_names_a_module_that_loads(self) -> None:
        move = states.by_number(8)
        self.assertEqual((move.origins, move.targets), (("review",), ("building",)))
        self.assertIsNotNone(moves.load_checks(move.checks), "move 8 has no checks module")

    def test_move_eight_is_a_counted_move_back_that_needs_a_reason(self) -> None:
        self.assertTrue(states.by_number(8).back)
        self.assertIn(8, states.COUNTED)


if __name__ == "__main__":
    unittest.main()
