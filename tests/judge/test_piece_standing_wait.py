"""A standing run waits for ready pieces instead of ending, and ends on a stop or its limit."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project, git

# isort: split

import gate
import procs
import run
import run_cli
from loopkit import record_text

try:
    import standing
except ImportError as error:
    if error.name != "standing":
        raise
    standing = None

START = 1_000_000.0
WAIT_CAP = 3 * 86400


class StandingWaitTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.now = START
        self.built: list[int] = []
        self.built_at: list[float] = []
        self.read_times: list[float] = []
        self.at_sleep: list = []  # (seconds after the start, action), each run once
        self.on_build: dict[int, list] = {}

    def piece(self, state="state:ready"):
        n = self.gh.create_issue("A piece", SPEC, [state])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []},
                                        "waiting_limit": "9"}, "ready"))
        return n

    def make_ready(self, n):
        self.gh.set_labels(n, ["state:ready"], ["state:shaping", "state:approval"])

    def fake_sleep(self, seconds):
        self.now += seconds
        if self.now - START > WAIT_CAP:
            raise AssertionError("the standing run never ended")
        due = [item for item in self.at_sleep if self.now - START >= item[0]]
        for item in due:
            self.at_sleep.remove(item)
            item[1]()

    def ready_pieces(self):
        self.read_times.append(self.now)
        return sorted(n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])

    def build(self, gh, root, n, *args):
        self.built.append(n)
        self.built_at.append(self.now)
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        for action in self.on_build.get(n, []):
            action()
        return f"piece {n}: built"

    def stand(self, *argv):
        self.assertTrue(standing is not None and hasattr(standing, "wait_for_ready"),
                        "standing.wait_for_ready must exist")
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(standing, "clock", lambda: self.now), \
                patch.object(standing, "sleep", self.fake_sleep), \
                patch.object(run, "ready_pieces", side_effect=lambda *a: self.ready_pieces()), \
                patch.object(run, "build_piece", side_effect=self.build), \
                redirect_stdout(out):
            status = run.main(["--attended", "--stand", *argv])
        return status, out.getvalue()

    def events(self):
        path = self.p.root / ".loop" / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def stop(self):
        gate.request_stop(self.p.root)

    def assert_polled_every_two_minutes(self):
        self.assertTrue(self.read_times)
        later = [t for t in self.read_times if t > START]
        self.assertTrue(later, "the run never re-read the ready label while waiting")
        times = [START] + later
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(gap >= 120 for gap in gaps), f"ready label read too often: {gaps}")

    def test_D1_nothing_ready_at_the_start_a_piece_ready_later_is_built(self):
        late = self.piece("state:shaping")
        self.on_build[late] = [self.stop]
        self.at_sleep = [(180, lambda: self.make_ready(late))]
        status, out = self.stand()
        self.assertEqual((status, self.built), (0, [late]))
        self.assertGreaterEqual(self.built_at[0], START + 180)
        self.assertLessEqual(self.built_at[0], START + 180 + 130)
        self.assert_polled_every_two_minutes()

    def test_D1_after_building_every_ready_piece_a_piece_ready_later_is_built(self):
        first = self.piece()
        late = self.piece("state:shaping")
        self.on_build[late] = [self.stop]
        self.at_sleep = [(180, lambda: self.make_ready(late))]
        status, out = self.stand()
        self.assertEqual((status, self.built), (0, [first, late]))
        self.assertEqual(self.built_at[0], START)
        self.assertGreaterEqual(self.built_at[1], START + 180)
        self.assertLessEqual(self.built_at[1], START + 180 + 130)
        self.assert_polled_every_two_minutes()

    def test_D2_gate_stop_ends_a_waiting_run_without_moving_a_piece(self):
        shaping = self.piece("state:shaping")
        stopped_at = []
        self.at_sleep = [(30, lambda: (stopped_at.append(self.now), self.stop()))]
        status, out = self.stand()
        self.assertEqual(status, 0)
        self.assertEqual(self.built, [])
        self.assertEqual(self.gh.issues[shaping]["labels"], ["state:shaping"])
        self.assertLessEqual(self.now - stopped_at[0], 10)
        self.assertFalse(procs.lock_path(self.p.root).exists())
        self.assertIn("run-stop", [e["event"] for e in self.events()])

    def test_D3_a_run_with_nothing_to_build_ends_at_the_standing_limit(self):
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Standing limit: 1\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Standing limit")
        git(self.p.root, "push", "--quiet", "origin", "main")
        status, out = self.stand()
        self.assertEqual(status, 0)
        self.assertEqual(self.built, [])
        self.assertIn("Standing limit", out)
        self.assertGreaterEqual(self.now - START, 3600)
        self.assertLessEqual(self.now - START, 3600 + 130)
        self.assertFalse(procs.lock_path(self.p.root).exists())

    def test_D4_detach_starts_a_standing_run_with_the_command_unchanged(self):
        seen = {}

        def popen(command, **kwargs):
            seen["command"] = list(command)
            seen["env"] = dict(kwargs.get("env") or os.environ)
            return MagicMock(pid=4242)

        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli.subprocess, "Popen", side_effect=popen), \
                redirect_stdout(io.StringIO()):
            status = run.main(["--detach", "--attended"])
        self.assertEqual(status, 0)
        self.assertEqual(seen["command"],
                         [sys.executable, str(Path(run_cli.__file__).with_name("run.py")),
                          "--attended"])
        self.assertEqual(seen["env"].get("AI_LOOP_KIT_STAND"), "1")

    def test_D5_detach_is_refused_while_a_standing_run_holds_the_lock(self):
        lock = procs.lock_path(self.p.root)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": os.getpid(), "children": [], "standing": True}))
        err = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli.subprocess, "Popen") as popen, redirect_stderr(err):
            status = run.main(["--detach"])
        self.assertEqual(status, 2)
        popen.assert_not_called()
        self.assertIn(f"a standing run is live (pid {os.getpid()})", err.getvalue())
        self.assertIn("gate.py stop", err.getvalue())

    def test_D6_a_foreground_run_without_stand_ends_when_nothing_is_ready(self):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", return_value=[]), \
                redirect_stdout(out):
            status = run.main(["--attended"])
        self.assertEqual(status, 0)
        self.assertIn("Nothing is ready. Shape a piece first.", out.getvalue())


if __name__ == "__main__":
    unittest.main()
