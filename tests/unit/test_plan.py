"""Unit tests for kit/scripts/loop/run/plan.py: the order of a run and its builder slots.

The plan puts dependencies first and shows each serial chain before the single pieces. It
never lets two pieces in one area run at once, and it sizes the slots from free memory,
capped by the policy. It reads no file and starts nothing.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop.run import plan  # noqa: E402


def piece(number, *, areas=(), blockers=(), issue=None):
    return plan.PieceInfo(
        number=number,
        title=f"piece {number}",
        issue=issue,
        areas=frozenset(areas),
        blockers=frozenset(blockers),
    )


class SlotsTest(unittest.TestCase):
    def test_a_roomy_computer_is_capped_by_the_policy(self):
        self.assertEqual(plan.slots(65536, floor_mb=2048, cap=3), 3)

    def test_a_tight_computer_gets_fewer_slots_than_the_cap(self):
        # 1 slot at the floor, one more for each further slot's worth of memory.
        self.assertEqual(plan.slots(2048 + plan.SLOT_MEMORY_MB, floor_mb=2048, cap=3), 2)

    def test_free_memory_at_the_floor_gives_one_slot(self):
        self.assertEqual(plan.slots(2048, floor_mb=2048, cap=3), 1)

    def test_free_memory_below_the_floor_still_gives_one_slot(self):
        # The pre-run check refuses a computer below the floor. The plan never returns zero.
        self.assertEqual(plan.slots(100, floor_mb=2048, cap=3), 1)

    def test_unknown_free_memory_gives_one_slot(self):
        self.assertEqual(plan.slots(None, floor_mb=2048, cap=3), 1)

    def test_a_cap_of_one_is_one(self):
        self.assertEqual(plan.slots(65536, floor_mb=2048, cap=1), 1)


class OrderTest(unittest.TestCase):
    def test_dependencies_come_first(self):
        pieces = [
            piece(1, issue=11, blockers=[12]),  # 1 waits for the issue of piece 2
            piece(2, issue=12),
        ]
        made = plan.make_plan(pieces, slots=3)
        self.assertLess(made.order.index(2), made.order.index(1))

    def test_serial_chains_are_shown_before_single_pieces(self):
        pieces = [
            piece(1, areas=["a"]),
            piece(2, areas=["b"], issue=22),
            piece(3, areas=["c"], issue=23, blockers=[22]),
            piece(4, areas=["d"]),
        ]
        made = plan.make_plan(pieces, slots=3)
        self.assertEqual(made.chains, ((2, 3),))
        self.assertEqual(made.singles, (1, 4))
        self.assertEqual(made.order, (2, 3, 1, 4))

    def test_a_longer_chain_is_shown_first(self):
        pieces = [
            piece(1, issue=21),
            piece(2, issue=22, blockers=[21]),
            piece(3, issue=23),
            piece(4, issue=24, blockers=[23]),
            piece(5, issue=25, blockers=[24]),
        ]
        made = plan.make_plan(pieces, slots=3)
        self.assertEqual(made.chains, ((3, 4, 5), (1, 2)))

    def test_a_blocker_outside_the_run_does_not_change_the_order(self):
        pieces = [piece(1, issue=11, blockers=[999]), piece(2, issue=12)]
        made = plan.make_plan(pieces, slots=3)
        self.assertEqual(made.chains, ())
        self.assertEqual(made.order, (1, 2))

    def test_a_cycle_is_refused_and_names_the_pieces(self):
        pieces = [piece(1, issue=11, blockers=[12]), piece(2, issue=12, blockers=[11])]
        with self.assertRaises(plan.PlanError) as caught:
            plan.make_plan(pieces, slots=3)
        self.assertIn("1", str(caught.exception))
        self.assertIn("2", str(caught.exception))
        self.assertTrue(caught.exception.next_command)

    def test_the_same_pieces_give_the_same_plan(self):
        pieces = [piece(3), piece(1), piece(2)]
        self.assertEqual(plan.make_plan(pieces, slots=2), plan.make_plan(reversed(pieces), slots=2))

    def test_no_pieces_is_an_empty_plan(self):
        made = plan.make_plan([], slots=3)
        self.assertEqual(made.order, ())
        self.assertEqual(made.waves, ())


class WavesTest(unittest.TestCase):
    def test_two_pieces_in_one_area_never_share_a_wave(self):
        pieces = [piece(1, areas=["menus"]), piece(2, areas=["menus"]), piece(3, areas=["docs"])]
        made = plan.make_plan(pieces, slots=3)
        for wave in made.waves:
            areas = [a for n in wave for a in {p.number: p for p in pieces}[n].areas]
            self.assertEqual(len(areas), len(set(areas)), wave)
        self.assertEqual(sorted(n for wave in made.waves for n in wave), [1, 2, 3])
        self.assertEqual(len(made.waves), 2)

    def test_a_wave_holds_no_more_pieces_than_slots(self):
        pieces = [piece(n, areas=[f"a{n}"]) for n in range(1, 6)]
        made = plan.make_plan(pieces, slots=2)
        self.assertEqual([len(w) for w in made.waves], [2, 2, 1])

    def test_a_dependent_waits_for_a_later_wave_than_its_blocker(self):
        pieces = [piece(1, issue=11, blockers=[12], areas=["a"]), piece(2, issue=12, areas=["b"])]
        made = plan.make_plan(pieces, slots=3)
        self.assertEqual(made.waves, ((2,), (1,)))

    def test_a_piece_that_touches_none_clashes_with_nothing(self):
        pieces = [piece(1), piece(2), piece(3)]
        made = plan.make_plan(pieces, slots=3)
        self.assertEqual(made.waves, ((1, 2, 3),))

    def test_the_plan_prints_as_data(self):
        made = plan.make_plan([piece(1, areas=["a"])], slots=2)
        data = made.as_dict()
        self.assertEqual(data["slots"], 2)
        self.assertEqual(data["order"], [1])
        self.assertEqual(data["waves"], [[1]])


class RunnableTest(unittest.TestCase):
    def setUp(self):
        self.pieces = [
            piece(1, areas=["menus"]),
            piece(2, areas=["menus"]),
            piece(3, areas=["docs"]),
            piece(4, areas=["api"], issue=14, blockers=[13]),
            piece(5, areas=["web"], issue=13),
        ]
        self.order = (5, 4, 1, 2, 3)

    def ask(self, **more):
        arguments = {
            "pending": [1, 2, 3, 4, 5],
            "built": [],
            "occupied": [],
            "free_slots": 3,
        }
        arguments.update(more)
        return plan.runnable(self.pieces, order=self.order, **arguments)

    def test_it_takes_the_first_pieces_in_plan_order_up_to_the_free_slots(self):
        # 4 waits for 5. 1 and 2 share an area, so only 1 goes with 5.
        self.assertEqual(self.ask(), [5, 1, 3])

    def test_a_dependent_goes_once_its_blocker_is_built(self):
        self.assertEqual(self.ask(pending=[4], built=[5]), [4])

    def test_a_dependent_never_goes_before_its_blocker_is_built(self):
        self.assertEqual(self.ask(pending=[4]), [])

    def test_an_area_held_by_a_running_piece_is_not_given_to_another(self):
        self.assertEqual(self.ask(pending=[2, 3], occupied=[1]), [3])

    def test_no_free_slot_gives_nothing(self):
        self.assertEqual(self.ask(free_slots=0), [])

    def test_a_pending_piece_not_in_the_plan_is_ignored(self):
        self.assertEqual(self.ask(pending=[3, 99]), [3])


if __name__ == "__main__":
    unittest.main()
