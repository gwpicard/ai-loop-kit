"""Unit tests for kit/scripts/loop/run/attempts.py: where each outcome goes.

Every hand-off and every gate result has one route: the gate judges (move 5), back to shaping
(move 6), back to ready (move 7), or the piece stays where it is. The attempts are counted as
the design's outcomes table says, and the run never keeps a count of its own: the gate's attempt
log is the count. "No real improvement" is decided from the judge results in that log.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402
from loop.run import attempts  # noqa: E402


def failed(n, ids=(), *, other=(), gaming=False):
    findings = []
    if ids:
        findings.append({
            "check": "visible-judge",
            "text": "the visible judge failed on an assertion naming " + ", ".join(ids),
            "gaming": False,
        })
    for check, text in other:
        findings.append({"check": check, "text": text, "gaming": gaming})
    return {"kind": "attempt", "n": n, "result": "failed", "head": "a" * 40, "base": "b" * 40,
            "at": "2026-10-07", "possible_gaming": gaming, "findings": findings}


class OutcomeTableTest(unittest.TestCase):
    """The table in design.md, section Outcomes, column "Counts as an attempt"."""

    TABLE = {
        "gate-passes": False,
        "gate-fails": True,
        "attempts-out": True,
        "no-real-improvement": True,
        "bar-is-wrong": False,
        "needs-the-person": False,
        "blocked-by-environment": False,
        "usage-limit": False,
        "stuck": True,
        "gave-up": True,
        "bar-changed": True,
        "held-out-gap": True,
    }

    def test_each_outcome_counts_as_the_design_says(self):
        for outcome, counts in self.TABLE.items():
            with self.subTest(outcome=outcome):
                self.assertEqual(attempts.counts_as_attempt(outcome), counts)

    def test_the_table_holds_every_outcome_and_no_other(self):
        self.assertEqual(set(attempts.OUTCOME_COUNTS), set(self.TABLE))

    def test_an_unknown_outcome_is_refused(self):
        with self.assertRaises(KeyError):
            attempts.counts_as_attempt("made-up")


class HandoffRouteTest(unittest.TestCase):
    def route(self, handoff, exit_code=0):
        return attempts.route_handoff(handoff, exit_code)

    def test_done_goes_to_the_gate_for_move_5(self):
        route = self.route({"outcome": "done", "summary": "Built."})
        self.assertEqual((route.action, route.move), ("judge", 5))

    def test_gave_up_is_judged_too_so_the_gate_counts_it(self):
        route = self.route({"outcome": "gave-up", "reason": "no way found"})
        self.assertEqual((route.action, route.move), ("judge", 5))

    def test_bar_is_wrong_goes_back_to_shaping_by_move_6_with_the_evidence(self):
        route = self.route({"outcome": "bar-is-wrong", "evidence": "FL-1 and EC-1 clash"})
        self.assertEqual((route.action, route.move, route.target), ("send-back", 6, "shaping"))
        self.assertIn("FL-1 and EC-1 clash", route.reason)
        self.assertFalse(route.counts)

    def test_needs_the_person_parks_the_piece_and_moves_nothing(self):
        route = self.route({"outcome": "needs-the-person", "question": "Which colour?"})
        self.assertEqual((route.action, route.move), ("park-person", None))
        self.assertIn("Which colour?", route.reason)
        self.assertFalse(route.counts)

    def test_blocked_by_environment_goes_back_to_ready_by_move_7(self):
        route = self.route({"outcome": "blocked-by-environment", "reason": "npm is refused"})
        self.assertEqual((route.action, route.move, route.target), ("give-back", 7, "ready"))
        self.assertIn("npm is refused", route.reason)
        self.assertFalse(route.counts)

    def test_no_hand_off_after_a_clean_exit_is_judged_by_the_gate(self):
        route = self.route(None, 0)
        self.assertEqual((route.action, route.move), ("judge", 5))
        self.assertIn("no hand-off", route.reason)

    def test_no_hand_off_after_a_failed_session_is_never_a_pass_or_an_attempt(self):
        route = self.route(None, 7)
        self.assertEqual((route.action, route.move), ("give-back", 7))
        self.assertIn("7", route.reason)
        self.assertFalse(route.counts)

    def test_every_hand_off_outcome_has_a_route(self):
        samples = {
            "done": {"outcome": "done", "summary": "x"},
            "bar-is-wrong": {"outcome": "bar-is-wrong", "evidence": "x"},
            "needs-the-person": {"outcome": "needs-the-person", "question": "x"},
            "blocked-by-environment": {"outcome": "blocked-by-environment", "reason": "x"},
            "gave-up": {"outcome": "gave-up", "reason": "x"},
        }
        self.assertEqual(set(samples), set(sessions.OUTCOMES))
        for name, handoff in samples.items():
            with self.subTest(outcome=name):
                self.assertIsNotNone(self.route(handoff))

    def test_a_handoff_outside_the_five_is_refused_not_routed(self):
        with self.assertRaises(ValueError):
            self.route({"outcome": "celebrated"})


class JudgedRouteTest(unittest.TestCase):
    def judged(self, **more):
        values = {"passed": False, "sent_back": False, "counted": True, "attempts": [],
                  "limit": 3, "next_command": "", "message": ""}
        values.update(more)
        return attempts.Judged(**values)

    def test_a_pass_is_built(self):
        route = attempts.route_judged(self.judged(passed=True, counted=False))
        self.assertEqual((route.action, route.move), ("built", 5))

    def test_a_failure_with_attempts_left_starts_the_next_attempt(self):
        route = attempts.route_judged(self.judged(attempts=[failed(1, ["FL-1", "EC-1"])]))
        self.assertEqual(route.action, "next-attempt")
        self.assertIsNone(route.move)

    def test_the_gate_that_sent_the_piece_back_is_final_and_not_made_again(self):
        route = attempts.route_judged(
            self.judged(sent_back=True, attempts=[failed(1, ["FL-1"]), failed(2, ["FL-1"]),
                                                  failed(3, ["FL-1"])]))
        self.assertEqual(route.action, "sent-back")
        self.assertEqual(route.move, 6)

    def test_a_refusal_that_counted_nothing_waits_for_the_person(self):
        route = attempts.route_judged(self.judged(
            counted=False, next_command="check the git repository",
            message="git failed while the gate judged the attempt"))
        self.assertEqual(route.action, "wait-person")
        self.assertIn("git failed", route.reason)
        self.assertEqual(route.next_command, "check the git repository")
        self.assertFalse(route.counts)

    def test_a_refusal_that_counted_nothing_is_never_a_pass(self):
        route = attempts.route_judged(self.judged(counted=False))
        self.assertNotEqual(route.action, "built")
        self.assertNotEqual(route.action, "next-attempt")

    def test_two_attempts_with_the_same_findings_stop_early_by_move_6(self):
        route = attempts.route_judged(
            self.judged(attempts=[failed(1, ["FL-1", "EC-1"]), failed(2, ["FL-1", "EC-1"])],
                        limit=4))
        self.assertEqual((route.action, route.move, route.target), ("send-back", 6, "shaping"))
        self.assertIn("no real improvement", route.reason.lower())
        self.assertTrue(route.counts)

    def test_two_attempts_that_improve_go_on(self):
        route = attempts.route_judged(
            self.judged(attempts=[failed(1, ["FL-1", "EC-1"]), failed(2, ["EC-1"])], limit=4))
        self.assertEqual(route.action, "next-attempt")

    def test_a_first_failure_never_stops_early(self):
        route = attempts.route_judged(self.judged(attempts=[failed(1, ["FL-1"])], limit=4))
        self.assertEqual(route.action, "next-attempt")

    def test_the_reason_names_each_attempts_findings(self):
        route = attempts.route_judged(
            self.judged(attempts=[failed(1, ["FL-1"]), failed(2, ["FL-1"])], limit=4))
        self.assertIn("attempt 1", route.reason)
        self.assertIn("attempt 2", route.reason)
        self.assertIn("FL-1", route.reason)


class ImprovementTest(unittest.TestCase):
    def test_fewer_failing_ids_is_an_improvement(self):
        self.assertTrue(attempts.improved(failed(1, ["FL-1", "EC-1"]), failed(2, ["FL-1"])))

    def test_the_same_failing_ids_is_no_improvement(self):
        self.assertFalse(attempts.improved(failed(1, ["FL-1"]), failed(2, ["FL-1"])))

    def test_more_failing_ids_is_no_improvement(self):
        self.assertFalse(attempts.improved(failed(1, ["FL-1"]), failed(2, ["FL-1", "EC-1"])))

    def test_other_ids_but_the_same_number_is_no_improvement(self):
        self.assertFalse(attempts.improved(failed(1, ["FL-1"]), failed(2, ["EC-1"])))

    def test_fewer_other_findings_with_the_same_ids_is_an_improvement(self):
        before = failed(1, ["FL-1"], other=[("touches", "outside"), ("new-test-lint", "weak")])
        after = failed(2, ["FL-1"], other=[("touches", "outside")])
        self.assertTrue(attempts.improved(before, after))

    def test_the_visible_judge_green_and_a_held_out_failure_is_an_improvement(self):
        before = failed(1, ["FL-1", "EC-1"])
        after = failed(2, [], other=[("held-out", "1 of 2 hidden cases failed")])
        self.assertTrue(attempts.improved(before, after))

    def test_an_attempt_logged_as_possible_gaming_is_never_an_improvement(self):
        before = failed(1, ["FL-1", "EC-1"])
        after = failed(2, ["FL-1"], other=[("frozen-bar", "the bar changed")], gaming=True)
        self.assertFalse(attempts.improved(before, after))

    def test_the_failing_ids_are_read_from_the_visible_judge_finding(self):
        self.assertEqual(attempts.failing_ids(failed(1, ["EC-1", "FL-1"])), {"EC-1", "FL-1"})
        self.assertEqual(attempts.failing_ids(failed(1, [])), set())

    def test_a_judge_that_names_no_id_gives_no_ids_and_so_compares_on_findings(self):
        one = {"kind": "attempt", "n": 1, "result": "failed", "possible_gaming": False,
               "findings": [{"check": "visible-judge", "gaming": False,
                             "text": "the visible judge failed on an assertion that names no "
                                     "spec ID"}]}
        two = dict(one, n=2)
        self.assertFalse(attempts.improved(one, two))


class NoImprovementTest(unittest.TestCase):
    def test_none_when_there_is_one_attempt(self):
        self.assertIsNone(attempts.no_real_improvement([failed(1, ["FL-1"])], 4))

    def test_a_reason_when_the_last_two_did_not_improve(self):
        reason = attempts.no_real_improvement(
            [failed(1, ["FL-1", "EC-1"]), failed(2, ["EC-1"]), failed(3, ["EC-1"])], 5)
        self.assertIsNotNone(reason)
        assert reason is not None
        self.assertIn("no real improvement", reason.lower())

    def test_none_when_the_limit_is_reached_because_the_gate_has_sent_it_back(self):
        self.assertIsNone(attempts.no_real_improvement(
            [failed(1, ["FL-1"]), failed(2, ["FL-1"]), failed(3, ["FL-1"])], 3))


if __name__ == "__main__":
    unittest.main()
