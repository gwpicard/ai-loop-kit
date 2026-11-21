"""A parked dependency delays the drain; an intentional stop is not a crash."""
import json
import os
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

import common
import loop
from kit.tests.test_loop import AGENTS, Base, comment, issue
from kit.tests.test_loop_pause import PauseBase, SLOW, states, tree


class ParkDrainTest(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.work, ".loop"))
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS.replace("Idle hours: 0", "Idle hours: 12"))
        self.drain = mock.patch.object(loop, "drain").start()
        mock.patch.object(loop, "sync_default", return_value=False).start()

    def parked(self, minutes):
        park = dict(comment("## Needs you\n\nWhich port?\n\n" + common.MARKER),
                    createdAt=datetime.fromtimestamp(time.time() - minutes * 60, timezone.utc).isoformat())
        self.world([issue(2, ("needs-user",)), issue(3, body="Depends on: #2")], comments=[park])
        return park

    def test_recent_park_reads_replies_without_draining(self):
        park = self.parked(10)

        def reply(*args):
            self.drain.assert_not_called()
            self.world([issue(2, ("needs-user",)), issue(3, body="Depends on: #2")],
                       comments=[park, comment("Use 8080.")])
        with mock.patch.object(loop, "wait_stop", side_effect=reply), self.fake_build():
            self.run_loop()
        self.assertEqual(self.built, [(2, ["Use 8080."])])
        self.assertEqual(len(self.writes("--json comments")), 2)
        self.drain.assert_not_called()

    def test_a_chain_behind_a_parked_issue_holds_the_drain(self):
        st = loop.new_state()
        st["issues"] = [issue(2, ("needs-user",)), issue(3, ("ready",), body="Depends on: #2"),
                        issue(4, ("ready",), body="Depends on: #3"), issue(5, ("ready",), body="Depends on: #3, #4")]
        for i in st["issues"]:
            i["labels"] = {l["name"] for l in i["labels"]}
        st["parks"][2] = time.time()
        self.assertGreater(loop.park_wait(st), 3500)
        st["issues"].append(dict(issue(6), labels={"ready"}))  # an issue nothing blocks can build
        self.assertEqual(loop.park_wait(st), 0)

    def test_a_build_reaped_as_parked_holds_the_drain_in_that_cycle(self):
        self.starts.stop()
        self.world([issue(2), issue(3, body="Depends on: #2"), issue(4, body="Depends on: #2")])
        proc = mock.Mock(pid=12345, returncode=0)
        proc.poll.return_value = None
        waits = []

        def start(project, settings, st):
            if not waits:
                loop.claim(st, 2)
                st["building"][2] = ("10:00", proc)

        def park(*args):
            waits.append(1)
            if len(waits) == 1:
                common.park(2, "Which port?", "Use 8080.", project=self.work)
                result = common.build_file(self.work, 2, "result")
                os.makedirs(os.path.dirname(result), exist_ok=True)
                with open(result, "w") as f:
                    json.dump({"last": "#2 parked: Which port?"}, f)
                proc.poll.return_value = 0
                self.world([issue(2, ("building",)), issue(3, body="Depends on: #2"),
                            issue(4, body="Depends on: #2")], comments=[dict(
                                comment("## Needs you\n\nWhich port?\n\n" + common.MARKER),
                                createdAt=datetime.now(timezone.utc).isoformat())])
            else:
                self.stop_after()

        with mock.patch.object(loop, "start_builds", side_effect=start), \
                mock.patch.object(loop, "wait_stop", side_effect=park), \
                mock.patch.object(loop, "clean_up"):
            self.assertEqual(self.run_loop(), 0)
        self.assertEqual(len(waits), 2)
        self.drain.assert_not_called()
        self.assertTrue(any("Why idle: dependencies held by needs-user: #2 Piece 2; drain in 60 min" in b
                            for b in self.board_inputs()))

    def test_park_older_than_an_hour_allows_the_drain(self):
        self.parked(61)
        with mock.patch.object(loop, "wait_stop", side_effect=lambda *a: self.stop_after()):
            self.run_loop()
        self.drain.assert_called_once()

    def test_empty_queue_without_parks_drains(self):
        self.world([])
        with mock.patch.object(loop, "wait_stop", side_effect=lambda *a: self.stop_after()):
            self.run_loop()
        self.drain.assert_called_once()

    def test_idle_board_names_the_park_and_minutes_until_drain(self):
        self.parked(10)
        with mock.patch.object(loop, "wait_stop", side_effect=lambda *a: self.stop_after()):
            self.run_loop()
        self.assertTrue(any("Why idle: dependencies held by needs-user: #2 Piece 2; drain in 50 min" in b
                            for b in self.board_inputs()))


class StopTest(PauseBase):
    def test_stop_says_it_waits_for_the_issue_and_allows_it_to_finish(self):
        self.start()
        self.wait_for("the slow Test command", self.slow_running)
        stopped = self.loop_cmd("stop")
        self.assertEqual(stopped.returncode, 0)
        self.assertIn("starts nothing new and ends after its running builds finish their issue", stopped.stdout)
        self.assertIsNone(self.proc.poll())
        self.assertEqual(self.proc.wait(timeout=120), 0)
        self.assertTrue(json.load(open(os.path.join(self.gh_dir, "state.json")))["closed"])

    def test_stop_now_ends_build_trees_and_requeues_without_a_crash(self):
        self.start()
        self.wait_for("the slow Test command", self.slow_running)
        descendants = tree(self.proc.pid)
        self.assertTrue(any(SLOW in c for _, c in descendants.values()))
        self.assertTrue(any(os.path.join(self.bin, "claude") in c for _, c in descendants.values()))
        self.assertTrue(any("worker.py" in c for _, c in descendants.values()))
        began = time.time()
        stopped = self.loop_cmd("stop", "--now")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertEqual(self.proc.wait(timeout=5), 0)
        self.assertLess(time.time() - began, 5)
        self.assertFalse({p: s for p, s in states(descendants).items() if not s.startswith("Z")})
        with open(os.path.join(self.gh_dir, "state.json")) as f:
            self.assertEqual(json.load(f), {"labels": ["ready"], "closed": False})
        with open(os.path.join(self.work, ".loop", "events.jsonl")) as f:
            events = list(map(json.loads, f))
        self.assertFalse([e for e in events if e["kind"] in ("crashed", "parked")])
        self.assertEqual(len([e for e in events if e["kind"] == "exit" and e.get("issue") == 7
                              and e["reason"] == "stopped"]), 1)


class StopParallelTest(PauseBase):
    PARALLEL = 2
    test_stop_now_ends_build_trees_and_requeues_without_a_crash = StopTest.test_stop_now_ends_build_trees_and_requeues_without_a_crash


class GuidanceTest(unittest.TestCase):
    def test_guidance_describes_both_stops_and_the_park_drain_limit(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        for path in ("kit/README.md", "docs/DESIGN.md", "kit/skills/loop/SKILL.md"):
            with self.subTest(path=path), open(os.path.join(root, path)) as f:
                text = " ".join(f.read().split())
                self.assertIn("stop --now", text)
                self.assertIn("60 minutes", text)
                self.assertIn("finish their issue", text)


if __name__ == "__main__":
    unittest.main()
