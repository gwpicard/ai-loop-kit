"""Every gh call and every network git call has a time limit that names the step."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
import run_fixtures
from helpers import Project

# isort: split

import bootstrap
import gate
import landing
import loop_pr
import network
import pr
import recovery
import run
import test_size_inventory
from loopkit import GitHub, records, refresh_main, sh

ROOT = Path(__file__).resolve().parents[2]
REAL_RUN = subprocess.run


def hanging(*words):
    """A stand-in for subprocess.run that times out when the command starts with `words`."""
    def fake(args, *a, **kw):
        if list(args[:len(words)]) == list(words):
            raise subprocess.TimeoutExpired(args, kw.get("timeout") or 0)
        return REAL_RUN(args, *a, **kw)
    return fake


class SlowGh(unittest.TestCase):
    """A real `gh` on the path that never answers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        gh = Path(self.tmp.name) / "gh"
        gh.write_text("#!/bin/sh\nexec sleep 30\n")
        gh.chmod(0o755)
        for patcher in (patch.dict(os.environ, {"PATH": f"{self.tmp.name}:{os.environ['PATH']}"}),
                        patch.object(network, "NETWORK_TIMEOUT", 1)):
            patcher.start()
            self.addCleanup(patcher.stop)


class GhLimitTest(SlowGh):
    def test_D1_a_gh_call_that_hangs_raises_a_step_timeout_naming_the_call(self):
        with self.assertRaisesRegex(network.StepTimeout, "gh issue comment ran past 1 seconds"):
            GitHub(Path(self.tmp.name))._gh("issue", "comment", "5", "--body", "x")

    def test_D1_the_limit_is_120_seconds_and_the_message_says_so(self):
        with patch.object(network, "NETWORK_TIMEOUT", 120), \
                patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 120)) as call:
            with self.assertRaises(network.StepTimeout) as caught:
                GitHub(ROOT)._gh("issue", "comment", "5")
        self.assertEqual(str(caught.exception), "gh issue comment ran past 120 seconds")
        self.assertEqual(call.call_args.kwargs["timeout"], 120)
        self.assertTrue(issubclass(network.StepTimeout, RuntimeError))

    def test_D1_a_gh_failure_keeps_its_error_text(self):
        failed = subprocess.CompletedProcess(["gh"], 1, "", "boom\nmore")
        with patch("subprocess.run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "gh issue view 5 failed: boom$"):
                GitHub(ROOT)._gh("issue", "view", "5")

    def test_D6_main_protection_lets_a_timeout_through_and_names_the_step(self):
        with self.assertRaisesRegex(network.StepTimeout, "gh repo view ran past"):
            GitHub(Path(self.tmp.name)).main_protection()
        with patch.object(GitHub, "_gh", return_value="owner/name\n"):
            with self.assertRaisesRegex(network.StepTimeout, "gh api ran past"):
                GitHub(Path(self.tmp.name)).main_protection()

    def test_D6_bootstrap_run_limits_gh_and_push_and_names_the_step(self):
        with self.assertRaisesRegex(network.StepTimeout, "gh repo view ran past"):
            bootstrap.run(["gh", "repo", "view"], Path(self.tmp.name))
        with patch("subprocess.run", side_effect=hanging("git", "push")):
            with self.assertRaisesRegex(network.StepTimeout, "git push ran past"):
                bootstrap.run(["git", "push", "--quiet"], Path(self.tmp.name))

    def test_D5_bootstrap_leaves_a_local_command_unlimited(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as call:
            bootstrap.run(["git", "status"], ROOT)
        self.assertNotIn("timeout", call.call_args.kwargs)


class GitLimitTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def test_D2_a_push_that_hangs_raises_a_step_timeout_naming_the_push(self):
        with patch("subprocess.run", side_effect=hanging("git", "push")), \
                self.assertRaisesRegex(network.StepTimeout, r"^git push ran past 120 seconds$"):
            pr.open_pull_request(MagicMock(), self.p.root, self.p.root, 1, {}, 1, "ok")

    def test_D2_a_fetch_in_run_that_hangs_raises_a_step_timeout(self):
        with patch("subprocess.run", side_effect=hanging("git", "fetch")), \
                self.assertRaisesRegex(network.StepTimeout, "git fetch ran past 120 seconds"):
            run.check_pushed_branch(self.p.root, 1)

    def test_D2_a_fetch_in_landing_that_hangs_raises_a_step_timeout(self):
        with patch("subprocess.run", side_effect=hanging("git", "fetch")), \
                patch.object(landing, "base_merges", return_value=True), \
                patch.object(landing, "base_branch", return_value="main"), \
                self.assertRaisesRegex(network.StepTimeout, "git fetch ran past 120 seconds"):
            landing.land(MagicMock(), self.p.root, self.p.root, 1, "done", {})

    def test_D2_a_merge_that_hangs_is_reported_as_a_network_error_not_a_failed_merge(self):
        gh = MagicMock()
        gh.merge_pr.side_effect = network.StepTimeout("gh pr merge ran past 120 seconds")
        with patch.object(landing, "base_merges", return_value=True), \
                patch.object(landing, "base_branch", return_value="main"):
            result = landing.land(gh, self.p.root, self.p.root, 1, "done", {})
        self.assertIn("network error", result)
        self.assertIn("gh pr merge ran past 120 seconds", result)
        gh.pr_for_branch.assert_called_once()  # no second gh call after the timeout

    def test_D2_a_fetch_in_loop_pr_that_hangs_raises_a_step_timeout(self):
        with patch("subprocess.run", side_effect=hanging("git", "fetch")), \
                patch.object(loop_pr, "base_branch", return_value="loop/x"), \
                self.assertRaisesRegex(network.StepTimeout, "git fetch ran past 120 seconds"):
            loop_pr.final_pull_request(MagicMock(), self.p.root, [])

    def test_D2_a_fetch_in_recovery_that_hangs_counts_as_a_failed_fetch(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        with patch("subprocess.run", side_effect=hanging("git", "fetch")), \
                patch.object(recovery, "records", return_value=[{"move": "submit", "commit": "a"}]):
            self.assertFalse(recovery.finish_submit(self.p.gh, self.p.root, n))

    def test_D4_refresh_main_warns_and_continues_when_the_fetch_times_out(self):
        err = io.StringIO()
        with patch("subprocess.run", side_effect=hanging("git", "fetch")), redirect_stderr(err):
            refresh_main(self.p.root)
        self.assertIn("could not fetch main", err.getvalue())

    def test_D5_a_local_git_command_with_no_timeout_is_not_limited(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as call:
            sh(["git", "status"], self.p.root)
        self.assertIsNone(call.call_args.kwargs["timeout"])


class RunErrorTest(unittest.TestCase):
    def setUp(self):
        run_fixtures.RunFixture.setUp(self)

    def moves(self, n):
        return [r["move"] for r in records(self.p.gh.comments(n))]

    def crash_run(self, n):
        stuck = network.StepTimeout("git push ran past 120 seconds")
        with patch("review._review_session", side_effect=stuck):
            return run.build_piece(self.p.gh, self.p.root, n, 1)

    def test_D3_a_step_timeout_requeues_with_run_error_and_the_third_goes_to_shaping(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        for _ in range(2):
            self.assertIn("returned to ready", self.crash_run(n))
            requeue = records(self.p.gh.comments(n))[-1]
            self.assertEqual((requeue["move"], requeue["cause"]), ("requeue", "run-error"))
            self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
            self.assertIn("git push ran past 120 seconds", requeue["reason"])
        self.assertIn("back to shaping", self.crash_run(n))
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])


class BudgetTest(unittest.TestCase):
    def test_D7_the_network_module_exists_and_the_budgets_hold(self):
        scripts = ROOT / "kit" / "scripts"
        self.assertTrue((scripts / "network.py").is_file())
        self.assertEqual(network.NETWORK_TIMEOUT, 120)
        counts = test_size_inventory.python_lines(ROOT / "kit")
        counts.update({f"extras/{k}": v for k, v in
                       test_size_inventory.python_lines(ROOT / "extras").items()})
        test_size_inventory.check_sizes(counts)


if __name__ == "__main__":
    unittest.main()
