"""The gate's records hold the cost and token use of the builder attempts."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from run_fixtures import RunFixture

# isort: split

import agents
import gate
import run
from loopkit import records

CLAUDE_EVENT = {"type": "result", "total_cost_usd": 0.25,
                "usage": {"input_tokens": 100, "output_tokens": 40,
                          "cache_read_input_tokens": 9000}}
CODEX_EVENT = {"type": "turn.completed",
               "usage": {"input_tokens": 70, "cached_input_tokens": 5,
                         "cache_write_input_tokens": 0, "output_tokens": 30,
                         "reasoning_output_tokens": 12}}


class AttemptCostTest(RunFixture, unittest.TestCase):
    def build_with(self, events, mode="good", attempts=1, status=""):
        """Build with the fake agent, then add each attempt's final event to its session."""
        calls = iter(events)
        modes = iter(mode.split(","))
        original = run.build_once

        def build_once(*args, **kwargs):
            os.environ["FAKE_MODE"] = next(modes)
            outcome = original(*args, **kwargs)
            args[10].update(next(calls))
            return status or outcome

        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch.object(run, "build_once", side_effect=build_once):
            run.build_piece(self.p.gh, self.p.root, n, attempts)
        return n

    def last(self, n, move):
        return [r for r in records(self.p.gh.comments(n)) if r.get("move") == move][-1]

    def test_D1_submit_holds_the_cost_and_tokens_summed_over_attempts(self):
        # The first attempt fails the judge; the second passes.
        n = self.build_with([CLAUDE_EVENT, {"total_cost_usd": 0.5, "usage": {
            "input_tokens": 10, "output_tokens": 5}}], mode="wrong,good", attempts=2)
        submit = self.last(n, "submit")
        self.assertEqual(submit["attempts"], 2)
        self.assertAlmostEqual(submit["cost_usd"], 0.75)
        self.assertEqual(submit["tokens"], 155)

    def test_D2_give_back_and_requeue_hold_the_attempt_figures(self):
        n = self.build_with([CLAUDE_EVENT], mode="wrong")
        give_back = self.last(n, "give-back")
        self.assertEqual((give_back["cost_usd"], give_back["tokens"]), (0.25, 140))
        other = self.p.piece()
        gate.move(self.p.gh, self.p.root, other, "ready")
        os.environ["FAKE_MODE"] = "wrong"
        original = run.build_once

        def limited(*args, **kwargs):
            original(*args, **kwargs)
            args[10].update(CLAUDE_EVENT)
            return "usage-limit"

        with patch.object(run, "build_once", side_effect=limited):
            run.build_piece(self.p.gh, self.p.root, other, 1)
        requeue = self.last(other, "requeue")
        self.assertEqual((requeue["cost_usd"], requeue["tokens"]), (0.25, 140))

    def test_D3_no_report_writes_no_key_and_one_figure_writes_one_key(self):
        n = self.build_with([{"type": "result"}], mode="wrong")
        give_back = self.last(n, "give-back")
        self.assertNotIn("cost_usd", give_back)
        self.assertNotIn("tokens", give_back)
        self.assertEqual(agents.usage_from({}), {})
        self.assertEqual(agents.usage_from({"total_cost_usd": 0.1}), {"cost_usd": 0.1})
        self.assertEqual(agents.usage_from({"usage": {"input_tokens": 3, "output_tokens": 4}}),
                         {"tokens": 7})
        only_cost = self.build_with([{"total_cost_usd": 0.1}], mode="good")
        submit = self.last(only_cost, "submit")
        self.assertEqual(submit["cost_usd"], 0.1)
        self.assertNotIn("tokens", submit)

    def test_D5_codex_turn_completed_gives_tokens_and_no_cost(self):
        seen = {}
        agents.log_line(json.dumps(CODEX_EVENT), "codex", seen)
        self.assertEqual(agents.usage_from(seen), {"tokens": 100})
        n = self.build_with([CODEX_EVENT], mode="good")
        submit = self.last(n, "submit")
        self.assertEqual(submit["tokens"], 100)
        self.assertNotIn("cost_usd", submit)

    def test_D6_total_budget_rises_by_no_more_than_the_piece_adds(self):
        import test_size_inventory as inventory
        measured = sum(lines for owner in ("kit", "extras")
                       for name, lines in inventory.python_lines(inventory.ROOT / owner).items()
                       if not f"{owner}/{name}".startswith("extras/tests/"))
        self.assertLessEqual(inventory.TOTAL_BUDGET, measured)

    def test_D4_stays_attempts_and_seconds_are_recorded_as_before(self):
        n = self.build_with([{"type": "result"}], mode="good")
        submit = self.last(n, "submit")
        self.assertEqual(submit["attempts"], 1)
        self.assertGreaterEqual(submit["seconds"], 0)
        self.assertNotIn("cost_usd", submit)


if __name__ == "__main__":
    unittest.main()
