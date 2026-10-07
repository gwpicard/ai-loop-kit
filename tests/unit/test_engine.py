"""Unit tests for the spend and settings rules of kit/scripts/loop/run/engine.py.

A cap must hold when a session cost cannot be read, and when the trim pass comes after the last
build session. The builder settings must carry the network allowlist and refuse a malformed one.
The engine is built without its threads: each test sets only the fields its method reads.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import engine, record  # noqa: E402
from loop.run.gateway import Reply  # noqa: E402


class FakeGateway:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {"outcome": "nothing-to-trim"}
        self.calls: list[float | None] = []

    def trim(self, number: int, run: str, max_budget_usd: float | None) -> Reply:
        self.calls.append(max_budget_usd)
        return Reply(0, dict(self.data))


class EngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1], attended=True,
                                           merge_pre_approved=False)

    def make(self, *, cap_piece: float | None = None, cap_run: float | None = None,
             gateway: FakeGateway | None = None) -> engine.Engine:
        made = engine.Engine.__new__(engine.Engine)
        made.paths, made.name, made.record = self.paths, "night-1", self.rec
        made.cap_piece, made.cap_run = cap_piece, cap_run
        made.gateway = gateway or FakeGateway()  # type: ignore[assignment]
        made.hook = lambda *args, **more: None  # type: ignore[method-assign]
        return made

    def notes(self) -> str:
        return " | ".join(n["text"] for n in self.rec.data["notes"])


class TrimUnderACapTest(EngineTestCase):
    def test_a_trim_with_a_piece_cap_used_up_is_skipped_and_noted(self) -> None:
        self.rec.add_spend(1, 1.0)
        gateway = FakeGateway()
        self.make(cap_piece=1.0, gateway=gateway)._finish_piece(1)
        self.assertEqual(gateway.calls, [], "the trim session ran with no cap left")
        self.assertTrue(self.rec.piece(1)["trimmed"])
        self.assertEqual(self.rec.piece(1)["trim"], "skipped")
        self.assertIn("trim skipped", self.notes())
        self.assertEqual(self.rec.status(1), record.BUILT)

    def test_a_trim_with_a_run_cap_used_up_is_skipped_even_with_a_piece_cap_left(self) -> None:
        self.rec.add_spend(1, 2.5)
        gateway = FakeGateway()
        self.make(cap_piece=5.0, cap_run=2.0, gateway=gateway)._finish_piece(1)
        self.assertEqual(gateway.calls, [])
        self.assertEqual(self.rec.piece(1)["trim"], "skipped")

    def test_a_trim_with_some_cap_left_gets_the_smaller_amount_left(self) -> None:
        self.rec.add_spend(1, 0.6)
        gateway = FakeGateway()
        self.make(cap_piece=1.0, cap_run=5.0, gateway=gateway)._finish_piece(1)
        self.assertEqual(len(gateway.calls), 1)
        self.assertAlmostEqual(gateway.calls[0] or 0.0, 0.4)

    def test_a_trim_with_no_cap_runs_with_no_cap(self) -> None:
        gateway = FakeGateway()
        self.make(gateway=gateway)._finish_piece(1)
        self.assertEqual(gateway.calls, [None])
        self.assertEqual(self.rec.piece(1)["trim"], "nothing-to-trim")

    def test_a_trim_cost_the_pass_reports_is_added_to_the_spend(self) -> None:
        gateway = FakeGateway({"outcome": "trimmed", "cost_usd": 0.25})
        self.make(cap_piece=1.0, gateway=gateway)._finish_piece(1)
        self.assertAlmostEqual(self.rec.spend_piece(1), 0.25)
        self.assertAlmostEqual(self.rec.spend_total(), 0.25)


class UnreadableCostTest(EngineTestCase):
    def result(self, output: dict[str, Any] | None) -> sessions.Result:
        return sessions.Result(exit_code=1, stdout="not json at all", stderr="",
                               output=output, handoff=None)

    def test_a_session_with_no_readable_cost_under_a_cap_counts_its_budget(self) -> None:
        self.make(cap_piece=2.0)._spend(1, self.result(None), 0.75)
        self.assertAlmostEqual(self.rec.spend_piece(1), 0.75)
        self.assertAlmostEqual(self.rec.spend_total(), 0.75)
        self.assertIn("could not be read", self.notes())

    def test_the_budget_stands_in_for_a_cost_that_is_not_a_number(self) -> None:
        self.make(cap_run=3.0)._spend(1, self.result({"total_cost_usd": "free"}), 1.5)
        self.assertAlmostEqual(self.rec.spend_total(), 1.5)

    def test_a_cap_that_a_unreadable_session_fills_is_then_reached(self) -> None:
        self.make(cap_piece=1.0)._spend(1, self.result(None), 1.0)
        reached = self.rec.cap_reached(per_piece=1.0, per_run=None, piece=1)
        self.assertIsNotNone(reached)

    def test_a_readable_cost_is_added_as_it_is(self) -> None:
        self.make(cap_piece=2.0)._spend(1, self.result({"total_cost_usd": 0.3}), 1.9)
        self.assertAlmostEqual(self.rec.spend_piece(1), 0.3)

    def test_with_no_cap_an_unreadable_cost_adds_nothing(self) -> None:
        self.make()._spend(1, self.result(None), None)
        self.assertEqual(self.rec.spend_piece(1), 0.0)


class TemplateWriterTest(EngineTestCase):
    def allowlist(self, text: str) -> None:
        target = self.paths.agents_dir / "loop" / "network-allowlist.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def written(self) -> dict[str, Any]:
        made = self.make()
        made._write_template()
        assert made._template is not None
        loaded: dict[str, Any] = json.loads(made._template.read_text(encoding="utf-8"))
        return loaded

    def test_a_good_allowlist_reaches_the_settings_template(self) -> None:
        self.allowlist(json.dumps({"allowedDomains": ["example-registry.test", "pypi.org"]}))
        hosts = self.written()["sandbox"]["network"]["allowedDomains"]
        self.assertEqual(hosts, ["example-registry.test", "pypi.org"])

    def test_a_malformed_allowlist_is_a_refusal_that_names_the_next_command(self) -> None:
        for bad in ("{not json", json.dumps({"allowedDomains": "pypi.org"}),
                    json.dumps({"allowedDomains": [1, 2]}), json.dumps({"hosts": []}),
                    json.dumps(["pypi.org"])):
            with self.subTest(bad=bad):
                self.allowlist(bad)
                with self.assertRaises(engine.EngineRefusal) as caught:
                    self.make()._write_template()
                self.assertTrue(caught.exception.next_command)

    def test_no_allowlist_file_keeps_the_template_and_says_so(self) -> None:
        made = self.make()
        made._write_template()
        self.assertEqual(made._template, ROOT / "kit" / "templates" / "builder-settings.json")
        self.assertIn("no network allowlist", self.notes())


if __name__ == "__main__":
    unittest.main()
