"""A standing run waits at the waiting limit, carries on after the merge, and re-checks a stale start."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project, git

# isort: split

import gate
import run
import run_cli
import walkaway
from loopkit import record_text

try:
    import standing
except ImportError as error:
    if error.name != "standing" and not str(error.name).startswith("standing."):
        raise
    standing = None

HOUR = 3600
PASSING = [(True, "sandbox is checked", "")]


class StandingLimitsTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.now = 1_000_000.0
        self.start = self.now
        self.sleeps = 0
        self.at: list[tuple[float, object]] = []  # (seconds into the wait, action), in order
        self.order: list[str] = []
        self.doctor_calls: list[dict] = []
        self.doctor_results = [PASSING]
        # One piece already waits in approval; the limit of 1 pauses the run before piece B.
        self.waiting = self.gh.create_issue("Waiting", SPEC, ["state:approval"])
        self.gh.create_pr(f"piece/{self.waiting}", "Waiting", "body")
        self.ready = self.gh.create_issue("Next", SPEC, ["state:ready"])
        self.gh.comment(self.ready, record_text(
            {"move": "ready", "risks": {"depends_on": []}, "waiting_limit": "1"}, "ready"))

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps += 1
        if self.sleeps > 20_000:
            raise AssertionError("the run kept waiting")
        self.now += seconds
        while self.at and self.now - self.start >= self.at[0][0]:
            self.at.pop(0)[1]()

    def merge_waiting(self):
        self.gh.prs[f"piece/{self.waiting}"]["state"] = "MERGED"

    def move_base(self):
        base = Path(self.p.tmp.name) / "other"
        git(Path(self.p.tmp.name), "clone", "--quiet", str(self.p.remote), str(base))
        git(base, "config", "user.email", "test@example.invalid")
        git(base, "config", "user.name", "Test")
        (base / "change.txt").write_text("a person merged\n")
        git(base, "add", "-A")
        git(base, "commit", "--quiet", "-m", "A person's merge")
        git(base, "push", "--quiet", "origin", "main")

    def doctor(self, gh, root, **kwargs):
        self.order.append("doctor")
        self.doctor_calls.append(kwargs)
        index = min(len(self.doctor_calls), len(self.doctor_results)) - 1
        return self.doctor_results[index]

    def build(self, gh, root, n, *args):
        self.order.append(f"build {n}")
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        return f"piece {n}: built"

    def run_all(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        patches = [
            patch.object(run_cli, "repo_root", return_value=self.p.root),
            patch.object(run_cli, "GitHub", return_value=self.gh),
            patch.object(run_cli.signal, "signal"),
            patch.object(run, "ready_pieces", side_effect=lambda *a: sorted(
                n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])),
            patch.object(run, "build_piece", side_effect=self.build),
            patch.object(gate, "doctor", side_effect=self.doctor),
            patch.object(walkaway, "keep_awake", return_value=nullcontext()),
        ]
        if standing is not None:
            patches += [patch.object(standing, "clock", self.clock),
                        patch.object(standing, "sleep", self.sleep)]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        with redirect_stdout(out), redirect_stderr(err):
            status = run.main(list(argv))
        return status, out.getvalue() + err.getvalue()

    def needs_standing(self):
        self.assertTrue(standing is not None and hasattr(standing, "needs_recheck")
                        and hasattr(standing, "wait_for_ready"),
                        "standing.wait_for_ready and standing.needs_recheck must exist")

    def test_D1_a_standing_run_waits_at_the_limit_then_builds_after_the_merge(self):
        self.needs_standing()
        self.at = [(600, self.merge_waiting)]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order, ["doctor", f"build {self.ready}"])
        self.assertIn("state:done", self.gh.issue(self.waiting)["labels"])
        self.assertEqual(out.count("Run paused"), 1)
        self.assertGreaterEqual(self.now - self.start, 600)
        self.assertEqual(status, 0)

    def test_D2_a_run_that_does_not_stand_pauses_and_stops_at_the_limit(self):
        self.at = [(600, self.merge_waiting)]
        status, out = self.run_all("--attended")
        self.assertIn("Run paused", out)
        self.assertIn("next:", out)
        self.assertEqual(self.order, [])
        self.assertEqual(self.sleeps, 0)
        self.assertNotIn("state:done", self.gh.issue(self.waiting)["labels"])

    def test_D3_after_a_seven_hour_wait_the_start_check_runs_again_before_the_claim(self):
        self.needs_standing()
        self.at = [(7 * HOUR, self.merge_waiting)]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order, ["doctor", "doctor", f"build {self.ready}"])
        again = self.doctor_calls[1]
        self.assertIs(again.get("walk_away"), True)
        self.assertEqual(again.get("pieces"), [self.ready])

    def test_D3_the_reason_for_the_second_check_is_printed(self):
        self.needs_standing()
        self.at = [(7 * HOUR, self.merge_waiting)]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order.count("doctor"), 2)
        self.assertIn(standing.needs_recheck(7 * HOUR, "a", "a"), out)

    def test_D3_a_base_that_moved_during_a_short_wait_runs_the_check_again(self):
        self.needs_standing()
        self.at = [(600, lambda: (self.move_base(), self.merge_waiting()))]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order, ["doctor", "doctor", f"build {self.ready}"])

    def test_D3_needs_recheck_gives_a_reason_after_more_than_six_hours_or_a_new_base(self):
        self.needs_standing()
        self.assertNotEqual(standing.needs_recheck(6 * HOUR + 1, "abc", "abc"), "")
        self.assertNotEqual(standing.needs_recheck(60, "abc", "def"), "")

    def test_D4_a_short_wait_with_an_unmoved_base_does_not_run_the_check_again(self):
        self.needs_standing()
        self.at = [(600, self.merge_waiting)]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order, ["doctor", f"build {self.ready}"])
        self.assertEqual(len(self.doctor_calls), 1)

    def test_D4_needs_recheck_is_empty_for_a_short_wait_on_the_same_base(self):
        self.needs_standing()
        self.assertEqual(standing.needs_recheck(6 * HOUR, "abc", "abc"), "")
        self.assertEqual(standing.needs_recheck(0, "abc", "abc"), "")

    def test_D5_a_failed_repeat_check_ends_the_run_and_claims_no_piece(self):
        self.needs_standing()
        self.doctor_results = [PASSING, [(False, "sandbox cannot reach pypi.org",
                                          "allow pypi.org in the sandbox domains")]]
        self.at = [(7 * HOUR, self.merge_waiting)]
        status, out = self.run_all("--stand", "--walk-away")
        self.assertEqual(self.order, ["doctor", "doctor"])
        self.assertIn("sandbox cannot reach pypi.org", out)
        self.assertIn("next: allow pypi.org in the sandbox domains", out)
        self.assertIn("state:ready", self.gh.issue(self.ready)["labels"])
        self.assertNotEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
