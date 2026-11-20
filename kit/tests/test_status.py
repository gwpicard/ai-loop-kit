import contextlib
from datetime import datetime
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import loop
import status


NOW = datetime(2026, 11, 20, 12).timestamp()


def event(kind, hour="11:00", **fields):
    stamp = datetime.strptime("2026-11-20 " + hour, "%Y-%m-%d %H:%M").astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    return dict(time=stamp, kind=kind, kit="test", project="test", **fields)


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.tmp.name
        self.folder = Path(self.project, ".loop")
        self.folder.mkdir()

    def events(self, *events):
        (self.folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")

    def command(self, *args):
        out = io.StringIO()
        with mock.patch.object(loop.os, "getcwd", return_value=self.project), \
                mock.patch.object(loop.time, "time", return_value=NOW), \
                mock.patch.object(loop, "gh", side_effect=AssertionError("network")), \
                mock.patch.object(loop.subprocess, "Popen", side_effect=AssertionError("session")), \
                contextlib.redirect_stdout(out):
            code = loop.main(["status"] + list(args))
        return code, out.getvalue()

    def build(self, number, pid=None):
        builds = self.folder / "builds"
        builds.mkdir(exist_ok=True)
        path = builds / ("%d.step" % number)
        path.write_text("builder")
        os.utime(path, (NOW - 600, NOW - 600))
        if pid is not None:
            path.with_suffix(".pid").write_text(str(pid))

    def test_history_from_events_file(self):
        self.events(event("step", issue=8, step="builder", phase="end", seconds=120, agent="codex", model="test"),
                    event("step", issue=8, step="builder", phase="end", seconds=60),
                    event("step", issue=8, step="review", phase="end", seconds=60, round=2),
                    event("merged", "11:10", issue=8),
                    event("parked", issue=9, reason="May I change the settings?"),
                    event("crashed", issue=10), event("rule", rule="test-lock"), event("rule", rule="test-lock"),
                    event("rule", rule="role-git"), event("step", "00:00", step="builder", phase="end", seconds=999))
        code, text = self.command("--since", "4h")
        self.assertEqual(code, 0)
        for line in ("Loop: not running", "#8: 10.0 min, 2 rounds", "#9: May I change the settings?",
                     "Crashes: 1", "Rules: role-git=1, test-lock=2", "builder: 180, 90", "reviewer: 60, 60",
                     "Agents: codex", "Models: test"):
            self.assertIn(line, text)
        self.assertNotIn("999", text)

    def test_running_build_and_parked_build(self):
        (self.folder / "loop.pid").write_text(str(os.getpid()))
        self.build(8, os.getpid())
        self.build(9, os.getpid())
        self.events(event("step", issue=8, step="builder", phase="start"),
                    event("parked", issue=9, reason="A decision"))
        _, text = self.command()
        self.assertIn("Loop: running", text)
        self.assertIn("Now: #8 builder (10 min)", text)
        self.assertNotIn("#9 builder", text)

    def test_sequential_build_has_no_worker_pid(self):
        (self.folder / "loop.pid").write_text(str(os.getpid()))
        self.build(8)
        self.assertIn("Now: #8 builder (10 min)", self.command()[1])

    def test_dead_worker_and_stale_files_are_not_building(self):
        (self.folder / "loop.pid").write_text("0")
        self.build(8, 0)
        self.events(event("step", issue=8, step="builder", phase="start"))
        self.assertIn("Now: idle", self.command()[1])
        (self.folder / "loop.pid").write_text(str(os.getpid()))
        self.assertIn("Now: idle", self.command()[1])

    def test_pass_takes_precedence_over_drain_then_returns_to_drain(self):
        (self.folder / "loop.pid").write_text(str(os.getpid()))
        self.events(event("drain", "01:00", phase="start"), event("pass", "01:01", phase="start"))
        self.assertIn("Now: running the end-of-loop pass", self.command("--since", "1h")[1])
        with (self.folder / "events.jsonl").open("a") as f:
            f.write(json.dumps(event("pass", phase="end", seconds=30)) + "\n")
        self.assertIn("Now: draining", self.command()[1])
        with (self.folder / "events.jsonl").open("a") as f:
            f.write(json.dumps(event("drain", phase="end", seconds=50)) + "\n")
        self.assertIn("Now: idle", self.command()[1])

    def test_all_stage_names_and_medians(self):
        stages = ("test-writer", "fails-first", "builder", "tests", "review", "fix", "merge", "drain", "pass")
        self.events(*(event(s if s in ("drain", "pass") else "step", phase="end", step=s, seconds=30)
                      for s in stages))
        text = self.command()[1]
        for label in ("test writer", "fails-first", "builder", "pre-review test run", "reviewer", "fix", "merge", "drain", "pass"):
            self.assertIn(label + ": 30, 30", text)

    def test_since_formats_and_default(self):
        for value, hours in ((None, 12), ("4h", 4), ("90m", 1.5), ("10:00", 2), ("2026-11-20 09:00", 3)):
            self.assertEqual(status.since_time(value, NOW), NOW - hours * 3600)
        for value in ("yesterday", "25:00", "-4h", "2026-02-30 09:00"):
            self.assertEqual(self.command("--since", value)[0], 2)
        self.assertEqual(self.command("--since")[0], 2)

    def test_empty_or_partial_events_file_is_read_only(self):
        self.assertIn("Merged: none", self.command()[1])
        (self.folder / "events.jsonl").write_text('{"time":')
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.assertEqual(self.command()[0], 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_busy_history_stays_under_forty_lines(self):
        self.events(*(event(kind, issue=n, reason="decision") for n in range(30) for kind in ("merged", "parked")))
        text = self.command()[1]
        self.assertLessEqual(len(text.splitlines()), 40)
        self.assertIn("23 more", text)


if __name__ == "__main__":
    unittest.main()
