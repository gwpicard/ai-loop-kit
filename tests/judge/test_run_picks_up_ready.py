"""A run with --keep-going builds pieces that become ready, or come back, during the run."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project

# isort: split

import run
import run_cli
from loopkit import record_text


class RunPicksUpReadyTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.built: list[int] = []
        self.on_build: dict[int, list] = {}  # piece -> actions, one per build
        self.reads = 0
        self.at_read: list = []  # actions for the re-reads, one per read after the first

    def fake_ready(self, depends=(), labels=("state:ready",)):
        n = self.gh.create_issue("A piece", SPEC, list(labels))
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": list(depends)},
                                        "waiting_limit": "9"}, "ready"))
        return n

    def make_ready(self, n):
        self.gh.set_labels(n, ["state:ready"], ["state:shaping", "state:approval"])

    def hand_back(self, n):
        self.gh.set_labels(n, ["state:shaping"], ["state:approval", "state:ready"])

    def ready_pieces(self):
        self.reads += 1
        if self.reads > 1 and self.at_read:
            self.at_read.pop(0)()
        return sorted(n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])

    def build(self, gh, root, n, *args):
        self.built.append(n)
        actions = self.on_build.get(n, [])
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        if actions:
            actions.pop(0)()
        return f"piece {n}: built"

    def run_all(self, *argv):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", side_effect=lambda *a: self.ready_pieces()), \
                patch.object(run, "build_piece", side_effect=self.build), \
                redirect_stdout(out):
            status = run.main(["--attended", *argv])
        return status, out.getvalue()

    def events(self):
        path = self.p.root / ".loop" / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_D1_a_new_ready_piece_is_built_before_the_run_finishes(self):
        first = self.fake_ready()
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": []},
                                           "waiting_limit": "9"}, "ready"))
        self.on_build[first] = [lambda: self.make_ready(late)]
        status, out = self.run_all("--keep-going")
        self.assertEqual((status, self.built), (0, [first, late]))

    def test_D2_a_handed_back_piece_made_ready_again_is_built_once_more_only_once(self):
        a = self.fake_ready()
        self.on_build[a] = [lambda: self.hand_back(a), lambda: self.hand_back(a)]
        self.at_read = [lambda: self.make_ready(a), lambda: self.make_ready(a)]
        status, out = self.run_all("--keep-going")
        self.assertEqual(self.built, [a, a])

    def test_D3_without_keep_going_nothing_joins_or_returns(self):
        a = self.fake_ready()
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": []},
                                           "waiting_limit": "9"}, "ready"))
        self.on_build[a] = [lambda: (self.make_ready(late), self.hand_back(a))]
        self.at_read = [lambda: self.make_ready(a)]
        before = self.reads
        status, out = self.run_all()
        self.assertEqual(self.built, [a])
        self.assertEqual(self.reads - before, 1)

    def test_D4_listed_run_builds_a_new_piece_but_not_an_unlisted_ready_one(self):
        a = self.fake_ready()
        unlisted = self.fake_ready()
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": []},
                                           "waiting_limit": "9"}, "ready"))
        self.on_build[a] = [lambda: self.make_ready(late)]
        status, out = self.run_all("--keep-going", str(a))
        self.assertEqual(self.built, [a, late])
        self.assertNotIn(unlisted, self.built)

    def test_D5_a_new_piece_that_depends_on_an_undone_piece_is_held(self):
        first = self.fake_ready()
        blocker = self.gh.create_issue("Blocker", SPEC, ["state:shaping"])
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": [blocker]},
                                           "waiting_limit": "9"}, "ready"))
        self.on_build[first] = [lambda: self.make_ready(late)]
        status, out = self.run_all("--keep-going")
        self.assertEqual(self.built, [first])
        self.assertIn(f"piece {late}: held until piece {blocker}", out)

    def test_D6_a_requested_stop_means_no_re_read(self):
        a = self.fake_ready()
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": []},
                                           "waiting_limit": "9"}, "ready"))
        stop = run.stop_path(self.p.root)
        self.on_build[a] = [lambda: (self.make_ready(late), stop.parent.mkdir(exist_ok=True),
                                     stop.write_text("stop\n"))]
        before = self.reads
        status, out = self.run_all("--keep-going")
        self.assertEqual(self.built, [a])
        self.assertEqual(self.reads - before, 1)  # the read at the start only

    def test_D7_stays_nothing_ready_at_the_start(self):
        status, out = self.run_all("--keep-going")
        self.assertEqual(status, 0)
        self.assertIn("Nothing is ready. Shape a piece first.", out)

    def test_D8_a_held_piece_runs_after_its_returned_blocker_is_ready_again(self):
        blocker = self.fake_ready()
        held = self.fake_ready([blocker])
        self.on_build[blocker] = [
            lambda: self.hand_back(blocker),
            lambda: self.gh.set_labels(blocker, ["state:done"], ["state:approval"])]
        self.at_read = [lambda: self.make_ready(blocker)]
        status, out = self.run_all("--keep-going")
        self.assertEqual(self.built, [blocker, blocker, held])

    def test_D9_joining_pieces_are_recorded_in_a_run_pieces_event(self):
        a = self.fake_ready()
        late = self.gh.create_issue("Late", SPEC, ["state:shaping"])
        self.gh.comment(late, record_text({"move": "ready", "risks": {"depends_on": []},
                                           "waiting_limit": "9"}, "ready"))
        self.on_build[a] = [lambda: self.make_ready(late)]
        self.run_all("--keep-going")
        recorded = [e["pieces"] for e in self.events() if e["event"] == "run-pieces"]
        self.assertEqual(recorded, [[a], [late]])


if __name__ == "__main__":
    unittest.main()
