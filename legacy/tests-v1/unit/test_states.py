"""Unit tests for kit/scripts/loop/states.py: the table of states and moves, as data."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import states  # noqa: E402

# The design's transition table, written out by hand so a change to the data shows here.
TABLE = {
    (states.NEW, "shaping"): 1,
    ("shaping", "ready"): 2,
    ("ready", "shaping"): 3,
    ("ready", "building"): 4,
    ("building", "review"): 5,
    ("building", "shaping"): 6,
    ("building", "ready"): 7,
    ("approval", "ready"): 7,
    ("review", "building"): 8,
    ("review", "shaping"): 9,
    ("review", "approval"): 10,
    ("approval", "done"): 11,
    ("approval", "review"): 12,
    ("approval", "building"): 13,
    ("approval", "shaping"): 13,
    ("shaping", "dropped"): 14,
    ("ready", "dropped"): 14,
    ("dropped", "shaping"): 14,
}


class TheTable(unittest.TestCase):
    def test_seven_states(self) -> None:
        self.assertEqual(
            states.STATES,
            ("shaping", "ready", "building", "review", "approval", "done", "dropped"),
        )

    def test_fourteen_numbered_moves(self) -> None:
        self.assertEqual(sorted(m.number for m in states.MOVES), list(range(1, 15)))

    def test_every_pair_in_the_design_is_the_right_move(self) -> None:
        for (origin, target), number in TABLE.items():
            move = states.find(origin, target)
            self.assertIsNotNone(move, f"{origin} to {target} is missing")
            assert move is not None
            self.assertEqual(move.number, number, f"{origin} to {target}")

    def test_no_other_pair_is_a_move(self) -> None:
        places = (states.NEW, *states.STATES)
        for origin in places:
            for target in places:
                if (origin, target) not in TABLE:
                    self.assertIsNone(states.find(origin, target), f"{origin} to {target}")

    def test_every_move_names_a_checks_module(self) -> None:
        names = [m.checks for m in states.MOVES]
        self.assertTrue(all(n.isidentifier() for n in names))
        self.assertEqual(len(set(names)), 14, "each move has its own checks module")

    def test_moves_back_carry_a_reason(self) -> None:
        self.assertEqual(states.BACK_MOVES, frozenset({3, 6, 7, 8, 9, 12, 13, 14}))
        for move in states.MOVES:
            self.assertEqual(move.back, move.number in states.BACK_MOVES)

    def test_the_anti_circle_rule_is_for_moves_back_to_shaping_only(self) -> None:
        self.assertTrue(states.anti_circle(states.find("ready", "shaping"), "shaping"))
        self.assertTrue(states.anti_circle(states.find("building", "shaping"), "shaping"))
        self.assertTrue(states.anti_circle(states.find("review", "shaping"), "shaping"))
        self.assertTrue(states.anti_circle(states.find("approval", "shaping"), "shaping"))
        self.assertFalse(states.anti_circle(states.find("approval", "building"), "building"))
        self.assertFalse(states.anti_circle(states.find("dropped", "shaping"), "shaping"))
        self.assertFalse(states.anti_circle(states.find("building", "ready"), "ready"))
        self.assertFalse(states.anti_circle(states.find("review", "building"), "building"))

    def test_the_counted_moves_and_their_limit(self) -> None:
        self.assertEqual(states.COUNTED, frozenset({7, 8, 12}))
        self.assertEqual(states.REPEAT_LIMIT, 3)

    def test_a_counted_move_falls_back_to_shaping_from_where_it_starts(self) -> None:
        self.assertEqual(states.back_to_shaping("building").number, 6)
        self.assertEqual(states.back_to_shaping("review").number, 9)
        self.assertEqual(states.back_to_shaping("approval").number, 13)


class Labels(unittest.TestCase):
    def test_one_state_label_per_state(self) -> None:
        self.assertEqual(states.label("review"), "state:review")
        self.assertEqual(states.state_of_label("state:approval"), "approval")
        self.assertIsNone(states.state_of_label("state:in-review"))
        self.assertIsNone(states.state_of_label("needs-you"))

    def test_state_labels_picks_the_family(self) -> None:
        names = ["type:bug", "state:ready", "needs-you", "state:shaping", "shaping:raw"]
        self.assertEqual(states.state_labels(names), ["state:ready", "state:shaping"])

    def test_the_gate_label_set(self) -> None:
        names = [name for name, _colour, _text in states.LABELS]
        want = [f"state:{s}" for s in states.STATES]
        want += ["needs-you", "type:feature", "type:bug", "type:chore"]
        self.assertEqual(names, want)
        for _name, colour, text in states.LABELS:
            self.assertRegex(colour, r"^[0-9A-F]{6}$")
            self.assertTrue(text)

    def test_old_labels_are_not_in_the_set(self) -> None:
        names = {name for name, _c, _t in states.LABELS}
        for old in ("state:in-review", "shaping:raw", "review:person", "loop:fix"):
            self.assertNotIn(old, names)


if __name__ == "__main__":
    unittest.main()
