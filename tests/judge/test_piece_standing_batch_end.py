"""A standing run delivers each batch's final suite, final pull request and summary when its pending list drains."""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from contextlib import contextmanager, ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import FakeGitHub, Project, git

# isort: split

import loop_pr
import run
import run_cli
import suite
import walkaway
from loopkit import STATE_PREFIX, record_text

try:
    import standing
except ImportError as error:
    if error.name != "standing" and not str(error.name).startswith("standing."):
        raise
    standing = None

TEST = "true"


class StandingBatchEndTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = FakeGitHub()
        self.p.gh = self.gh
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("AI_LOOP_KIT_TIER", None)
        os.environ.pop("AI_LOOP_KIT_STAND", None)
        self.log: list = []
        self.summaries: list[str] = []
        self.awake_state = False
        self.clock = 1000.0
        self.at_sleep: list = []  # actions, one per sleep
        self.p.loop_section(TEST)
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Base branch: trip\nBase merges: run\n")
        git(self.p.root, "commit", "--quiet", "-am", "Settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "branch", "trip", "main")
        git(self.p.root, "push", "--quiet", "-u", "origin", "trip")

    def ready_issue(self):
        n = self.gh.create_issue("A piece", "body", [STATE_PREFIX + "ready"])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []}}, "ready"))
        return n

    def stop(self):
        path = run.stop_path(self.p.root)
        path.parent.mkdir(exist_ok=True)
        path.write_text("stop\n")

    def build(self, gh, root, n, *args):
        self.log.append(f"build {n}")
        self.builds_state.append(self.awake_state)
        gh.set_labels(n, [STATE_PREFIX + "done"], [STATE_PREFIX + "ready"])
        return f"piece {n}: pull request ready"

    def fake_sleep(self, seconds):
        self.log.append("sleep")
        self.sleeps_state.append(self.awake_state)
        self.posted_at_sleep.append(len(self.summaries))
        self.clock += max(seconds, 120)
        if self.at_sleep:
            self.at_sleep.pop(0)()
        else:
            self.stop()

    def fake_final_check(self, gh, root, base, pieces):
        self.log.append(f"final_check {sorted(pieces)}")
        return f"Full suite passed on {base} ({len(pieces)} pieces)"

    def fake_final_pr(self, gh, root, results):
        self.log.append("final_pull_request")
        return "final pull request: opened"

    def fake_post(self, gh, summary, mention=False):
        self.log.append("post_summary")
        self.summaries.append(summary)

    def fake_keep_awake(self, root):
        outer = self

        class Awake:
            def waiting(self, state):
                outer.awake_state = state

        @contextmanager
        def manager():
            yield Awake()

        return manager()

    def run_main(self, argv, walk_away=True):
        self.builds_state: list = []
        self.sleeps_state: list = []
        self.posted_at_sleep: list = []
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run_cli, "choose_mode", return_value=walk_away), \
                patch.object(walkaway, "keep_awake", side_effect=self.fake_keep_awake), \
                patch.object(walkaway, "post_summary", side_effect=self.fake_post), \
                patch.object(suite, "final_check", side_effect=self.fake_final_check), \
                patch.object(loop_pr, "final_pull_request", side_effect=self.fake_final_pr), \
                patch.object(run, "final_pull_request", side_effect=self.fake_final_pr), \
                patch.object(run, "build_piece", side_effect=self.build), \
                redirect_stdout(out), ExitStack() as stack:
            if standing is not None:
                stack.enter_context(patch.object(standing, "clock", side_effect=lambda: self.clock))
                stack.enter_context(patch.object(standing, "sleep", side_effect=self.fake_sleep))
            status = run.main(argv)
        return status, out.getvalue()

    def need_standing(self):
        self.assertTrue(standing is not None and hasattr(standing, "wait_for_ready"),
                        "standing.wait_for_ready must exist")

    def test_D1_the_batch_is_delivered_before_the_standing_run_waits(self):
        self.need_standing()
        first, second = self.ready_issue(), self.ready_issue()
        self.run_main(["--stand"])
        self.assertEqual(self.log, [
            f"build {first}", f"build {second}",
            f"final_check {[first, second]}", "final_pull_request", "post_summary", "sleep"])
        self.assertEqual(len(self.summaries), 1)
        self.assertIn(f"piece {first}:", self.summaries[0])
        self.assertIn(f"piece {second}:", self.summaries[0])

    def test_D2_the_next_batch_summary_lists_only_its_piece_and_starts_later(self):
        self.need_standing()
        first = self.ready_issue()
        later = []
        self.at_sleep = [lambda: later.append(self.ready_issue())]
        self.run_main(["--stand"])
        second = later[0]
        self.assertEqual(self.log, [
            f"build {first}", f"final_check {[first]}", "final_pull_request", "post_summary", "sleep",
            f"build {second}", f"final_check {[second]}", "final_pull_request", "post_summary",
            "sleep"])
        self.assertIn(f"piece {first}:", self.summaries[0])
        self.assertNotIn(f"piece {second}:", self.summaries[0])
        self.assertIn(f"piece {second}:", self.summaries[1])
        self.assertNotIn(f"piece {first}:", self.summaries[1])
        stamp = lambda text, key: datetime.fromisoformat(re.search(rf"^{key}: (\S+)$", text, re.M).group(1))
        self.assertGreaterEqual(stamp(self.summaries[1], "Started"), stamp(self.summaries[0], "Finished"))

    def test_D3_a_drain_with_nothing_built_posts_nothing_and_runs_no_suite(self):
        self.need_standing()
        self.at_sleep = [lambda: None, lambda: self.stop()]  # two waits that find nothing
        status, out = self.run_main(["--stand"])
        self.assertEqual(status, 0)
        self.assertEqual(self.log[:2], ["sleep", "sleep"])
        self.assertEqual(self.posted_at_sleep, [0, 0])
        self.assertFalse([entry for entry in self.log if entry.startswith("final_check")])

    def test_D4_the_run_holds_idle_sleep_only_while_it_waits(self):
        self.need_standing()
        first = self.ready_issue()
        self.at_sleep = [lambda: self.ready_issue()]
        self.run_main(["--stand"])
        self.assertEqual(self.builds_state, [False, False])
        self.assertEqual(self.sleeps_state, [True, True])

    def caffeinate_calls(self, steps):
        calls = []
        popen = MagicMock()
        popen.return_value.wait.return_value = 0
        with patch.object(walkaway.subprocess, "Popen", popen), \
                patch.object(walkaway.sys, "platform", "darwin"):
            with walkaway.keep_awake(self.p.root) as awake:
                self.assertTrue(hasattr(awake, "waiting"), "keep_awake must yield waiting(state)")
                for step in steps:
                    awake.waiting(step)
                    calls = [c.args[0] for c in popen.call_args_list]
        return calls

    def test_D4_caffeinate_drops_the_display_flag_while_waiting(self):
        calls = self.caffeinate_calls([True])
        self.assertEqual(calls[0], ["caffeinate", "-dimsu"])
        self.assertEqual(calls[-1], ["caffeinate", "-i"])

    def test_D4_caffeinate_returns_to_dimsu_when_the_run_builds_again(self):
        calls = self.caffeinate_calls([True, False])
        self.assertEqual(calls[-1], ["caffeinate", "-dimsu"])

    def test_D5_a_run_that_does_not_stand_delivers_once(self):
        first, second = self.ready_issue(), self.ready_issue()
        status, out = self.run_main([])
        self.assertEqual(status, 0)
        self.assertEqual(self.log, [
            f"build {first}", f"build {second}",
            f"final_check {[first, second]}", "final_pull_request", "post_summary"])
        self.assertEqual(len(self.summaries), 1)
        self.assertIn("Run finished.", out)


if __name__ == "__main__":
    unittest.main()
