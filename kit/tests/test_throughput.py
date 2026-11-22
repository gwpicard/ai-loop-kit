import contextlib
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo
import loop
import session


class SessionUsageTest(FakeCodexGh):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"loop.json": '{"Test command": "true"}'})

    def recorded(self):
        path = Path(self.work, ".loop/events.jsonl")
        self.assertTrue(path.is_file(), "session.run must write its usage to events.jsonl")
        return [e for line in path.read_text().splitlines()
                if (e := json.loads(line))["kind"] == "session"]

    def test_claude_result_records_usage_without_changing_return_value(self):
        self.claude({"reviewer": [{"reply": "reviewed", "session_id": "usage-test", "num_turns": 7,
                                  "usage": {"input_tokens": 123, "cache_read_input_tokens": 456,
                                            "cache_creation_input_tokens": 89, "output_tokens": 32}}]})
        result = session.run("reviewer", "review it", self.work, "sonnet", self.work, 7)
        self.assertEqual(result, ("reviewed", "usage-test"))
        events = self.recorded()
        self.assertEqual(len(events), 1)
        expected = dict(issue=7, role="reviewer", agent="claude", model="sonnet", turns=7,
                        input_tokens=123, cached_input_tokens=456, output_tokens=32)
        self.assertEqual({k: events[0].get(k) for k in expected}, expected)
        self.assertTrue(all(k in events[0] for k in ("time", "kit", "project")))

    def test_codex_sums_usage_from_completed_turns_only(self):
        turns = [{"type": "turn.completed", "usage": {
            "input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 20}},
            {"type": "turn.started", "usage": {"input_tokens": 9999}},
            {"type": "turn.completed", "usage": {
                "input_tokens": 300, "cached_input_tokens": 90, "output_tokens": 40}}]
        self.codex([{"reply": "built", "thread": "usage-test", "events": turns}])
        result = session.run("builder", "build it", self.work, "gpt-6", self.work, 7, agent="codex")
        self.assertEqual(result, ("built", "usage-test"))
        events = self.recorded()
        self.assertEqual(len(events), 1)
        expected = dict(issue=7, role="builder", agent="codex", model="gpt-6", turns=2,
                        input_tokens=400, cached_input_tokens=170, output_tokens=60)
        self.assertEqual({k: events[0].get(k) for k in expected}, expected)
        self.assertTrue(all(k in events[0] for k in ("time", "kit", "project")))

    def test_codex_without_usage_still_records_session(self):
        for completed in ({"type": "turn.completed", "usage": {}}, {"type": "turn.completed"}):
            with self.subTest(completed=completed):
                self.codex([{"events": [completed]}])
                result = session.run("builder", "build it", self.work, "gpt-6", self.work, 7, agent="codex")
                self.assertEqual(result[0], "ok")
                event = self.recorded()[-1]
                self.assertEqual(event["turns"], 1)
                self.assertEqual((event["issue"], event["role"], event["agent"], event["model"]),
                                 (7, "builder", "codex", "gpt-6"))
                for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    self.assertIsNone(event.get(field), "unknown usage must not become zero")


NOW = datetime(2026, 11, 20, 12).timestamp()


def event(kind, hour="11:00", **fields):
    stamp = datetime.strptime("2026-11-20 " + hour, "%Y-%m-%d %H:%M").astimezone().isoformat()
    return dict(time=stamp, kind=kind, kit="test", project="test", **fields)


class ThroughputStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.tmp.name
        Path(self.project, ".loop").mkdir()
        self.events = [event("step", issue=n, step=stage, phase="end", seconds=seconds)
                       for n, stage, seconds in ((11, "builder", 2400), (12, "review", 1800),
                                                (13, "builder", 900), (14, "tests", 600),
                                                (15, "builder", 300), (16, "merge", 60))]
        self.events += [event("merged", "11:30", issue=11), event("merged", "11:40", issue=12),
                        event("parked", "11:01", issue=21, rule="test-lock", reason="A decision"),
                        event("parked", "11:02", issue=22, rule="test-lock", reason="A decision"),
                        event("parked", "11:03", issue=23, rule="protected-path", reason="A decision"),
                        event("rule", rule="test-lock"), event("rule", rule="test-lock"),
                        event("rule", rule="test-lock")]
        for role, turns, inputs, cached, outputs in (("builder", 5, 1234, 1000, 67),
                                                    ("builder", 7, 321, 200, 89),
                                                    ("reviewer", 3, 222, 111, 44)):
            self.events.append(event("session", issue=11, role=role, agent="codex", model="test",
                                     turns=turns, input_tokens=inputs, cached_input_tokens=cached,
                                     output_tokens=outputs))
        self.events.append(event("session", issue=12, role="builder", agent="codex", model="test", turns=1))
        for hour in ("09:00", "13:00"):
            self.events += [event("merged", hour, issue=99),
                            event("step", hour, issue=99, step="builder", phase="end", seconds=99999),
                            event("session", hour, role="builder", turns=999, input_tokens=99999),
                            event("parked", hour, issue=99, rule="outside", reason="outside")]

    def command(self, *args):
        output = io.StringIO()
        with mock.patch.object(loop.os, "getcwd", return_value=self.project), \
                mock.patch.object(loop.time, "time", return_value=NOW), \
                mock.patch.object(loop, "gh", side_effect=AssertionError("network")), \
                mock.patch.object(loop.subprocess, "Popen", side_effect=AssertionError("session")), \
                contextlib.redirect_stdout(output):
            code = loop.main(["status", *args])
        return code, output.getvalue()

    def write_events(self, events):
        Path(self.project, ".loop/events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n")

    def assert_numbers(self, text, label, *values):
        rows = [line for line in text.splitlines() if label.lower() in line.lower()]
        self.assertTrue(rows, "missing throughput row: " + label)
        self.assertTrue(any(all(re.search(r"(?<![\d.])%s(?:\.0+)?(?![\d.])" % value, row)
                               for value in values) for row in rows), (label, values, rows))

    def test_text_throughput_and_existing_lines_with_reordered_events(self):
        for events in (self.events, list(reversed(self.events))):
            with self.subTest(reversed=events is not self.events):
                self.write_events(events)
                code, text = self.command("--since", "2h")
                self.assertEqual(code, 0)
                legacy = ("Loop: not running\nNow: idle\nSince: 2026-11-20 10:00\nMerged:\n"
                          "  #{0}: 30.0 min, 0 rounds\n  #{1}: 40.0 min, 1 rounds\nParked:\n"
                          "  #{2}: A decision\n  #{3}: A decision\n  #{4}: A decision\nCrashes: 0\n"
                          "Rules: test-lock=3\nStage seconds (total, median; completed in window):\n"
                          "  builder: 3600, 900\n  pre-review test run: 600, 600\n"
                          "  reviewer: 1800, 1800\n  merge: 60, 60\nAgents: codex\nModels: test").format(11, 12, 21, 22, 23)
                self.assertTrue(text.startswith(legacy), text)
                self.assertIn("Throughput", text)
                throughput = text.split("Throughput", 1)[1]
                self.assert_numbers(throughput, "merged", 1)
                self.assert_numbers(throughput, "builder", 3600, 50)
                self.assert_numbers(throughput, "reviewer", 1800, 25)
                self.assert_numbers(throughput, "builder", 13, 1555, 1200, 156)
                self.assert_numbers(throughput, "reviewer", 3, 222, 111, 44)
                self.assert_numbers(throughput, "test-lock", 2)
                self.assert_numbers(throughput, "protected-path", 1)
                self.assertIn("slowest", throughput.lower())
                slowest = throughput.lower().split("slowest", 1)[1]
                self.assertEqual(re.findall(r"#(\d+)\b", slowest), ["11", "12", "13", "14", "15"])
                for issue, seconds in ((11, 2400), (12, 1800), (13, 900), (14, 600), (15, 300)):
                    self.assert_numbers(slowest, "#%d" % issue, seconds)

    def test_json_throughput_uses_same_window_and_values(self):
        self.write_events(self.events)
        for args in (("--json", "--since", "2h"), ("--since", "10:00", "--json")):
            with self.subTest(args=args):
                code, text = self.command(*args)
                self.assertEqual(code, 0, text)
                data = json.loads(text)
                self.assertIsInstance(data, dict)
                self.assertIn("throughput", data)
                report = data["throughput"]
                self.assertEqual(report["window_seconds"], 7200)
                self.assertEqual(report["merged_per_hour"], 1)
                for stage, seconds, share in (("builder", 3600, 0.5), ("review", 1800, 0.25),
                                              ("tests", 600, 1 / 12), ("merge", 60, 1 / 120)):
                    self.assertEqual(report["stages"][stage]["seconds"], seconds)
                    self.assertAlmostEqual(report["stages"][stage]["share"], share)
                for role, counts in (("builder", (13, 1555, 1200, 156)), ("reviewer", (3, 222, 111, 44))):
                    self.assertEqual(tuple(report["roles"][role][k] for k in
                                           ("turns", "input_tokens", "cached_input_tokens", "output_tokens")), counts)
                self.assertEqual(report["parks_by_rule"], {"test-lock": 2, "protected-path": 1})
                self.assertEqual([(e["issue"], e["step"], e["seconds"]) for e in report["slowest_steps"]],
                                 [(11, "builder", 2400), (12, "review", 1800), (13, "builder", 900),
                                  (14, "tests", 600), (15, "builder", 300)])


if __name__ == "__main__":
    unittest.main()
