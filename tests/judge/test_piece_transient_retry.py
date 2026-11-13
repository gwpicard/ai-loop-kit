"""A piece handed back for a cause the run can handle is built again in the same run."""
from __future__ import annotations

import io
import sys
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import GOOD_CODE, Project, git

# isort: split

import gate
import pr
import run
import run_cli
from loopkit import records


def metrics():
    return {"attempts": 1, "started": time.monotonic()}


class RunRetryTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.built: list[int] = []
        self.sleeps: list[float] = []
        self.actions: dict[int, list] = {}
        run.usage_resets.clear() if hasattr(run, "usage_resets") else None
        self.addCleanup(lambda: run.usage_resets.clear() if hasattr(run, "usage_resets") else None)

    def ready(self):
        n = self.p.piece()
        gate.move(self.gh, self.p.root, n, "ready")
        return n

    def build(self, gh, root, n, *args):
        self.built.append(n)
        gate.move(gh, root, n, "building")
        action = self.actions[n].pop(0)
        return action(n)

    def fault(self, cause="run-error"):
        def act(n):
            return run._requeue(self.gh, self.p.root, n, "the run stopped with an error",
                                cause, metrics())
        return act

    def done(self, n):
        self.gh.set_labels(n, ["state:approval"], ["state:building"])
        return f"piece {n}: built"

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        for n in list(getattr(run, "usage_resets", {})):
            run.usage_resets[n] = 0  # the reset has passed

    def run_all(self):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "build_piece", side_effect=self.build), \
                patch("time.sleep", side_effect=self.sleep), \
                redirect_stdout(out):
            status = run.main(["--attended"])
        return status, out.getvalue()

    def test_D1_a_run_error_requeue_is_built_again_in_the_same_run(self):
        a = self.ready()
        self.actions[a] = [self.fault(), self.done]
        status, out = self.run_all()
        self.assertEqual(self.built, [a, a])
        self.assertIn(f"piece {a}: built again after run-error", out)
        self.assertIn("state:approval", self.gh.issue(a)["labels"])

    def test_D2_the_third_requeue_goes_to_shaping_and_is_not_built_again(self):
        a = self.ready()
        self.actions[a] = [self.fault(), self.fault(), self.fault(), self.done]
        status, out = self.run_all()
        self.assertEqual(self.built, [a, a, a])
        self.assertIn("state:shaping", self.gh.issue(a)["labels"])
        self.assertIn("returned to ready twice", "\n".join(self.gh.comments(a)))

    def test_D3_a_usage_limit_piece_waits_for_its_reset_while_others_are_built(self):
        a = self.ready()
        b = self.ready()

        def limit(n):
            run.usage_resets[n] = time.time() + 1800
            return run._requeue(self.gh, self.p.root, n, "usage limit reached",
                                "usage-limit", metrics())

        self.actions[a] = [limit, self.done]
        self.actions[b] = [self.done]
        status, out = self.run_all()
        self.assertEqual(self.built, [a, b, a])
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(0 < self.sleeps[0] <= 1800, self.sleeps)

    def test_D6_a_dirty_build_folder_goes_to_shaping_and_is_not_built_again(self):
        a = self.ready()
        (run.worktree(self.p.root, a) / "person-work.txt").write_text("keep this work\n")
        real_build = run.build_piece
        calls = []

        def build(gh, root, n, *args, **kwargs):
            calls.append(n)
            return real_build(gh, root, n, *args, **kwargs)

        self.build = build
        status, out = self.run_all()
        self.assertEqual(calls, [a])
        self.assertIn("state:shaping", self.gh.issue(a)["labels"])
        self.assertIn("environment: 1", gate.report(self.gh))


class PullRequestRetryTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build habits")
        self.n, self.folder = n, folder

    def open(self):
        return pr.open_pull_request(self.p.gh, self.p.root, self.folder, self.n,
                                    self.p.gh.issue(self.n), 1, "ok")

    def test_D4_a_failed_creation_with_no_pull_request_is_tried_again(self):
        real = self.p.gh.create_pr
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("GitHub 502")
            return real(*args, **kwargs)

        with patch.object(self.p.gh, "create_pr", side_effect=flaky):
            result = self.open()
        url = self.p.gh.prs[f"piece/{self.n}"]["url"]
        self.assertEqual(len(calls), 2)
        self.assertIn(url, result)
        labels = self.p.gh.issue(self.n)["labels"]
        self.assertIn("state:approval", labels)
        self.assertNotIn("needs-you", labels)

    def test_D5_a_failed_creation_with_an_open_pull_request_uses_that_one(self):
        real = self.p.gh.create_pr
        calls = []

        def created_then_error(*args, **kwargs):
            calls.append(1)
            real(*args, **kwargs)
            raise RuntimeError("GitHub 502")

        with patch.object(self.p.gh, "create_pr", side_effect=created_then_error):
            result = self.open()
        url = self.p.gh.prs[f"piece/{self.n}"]["url"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.p.gh.prs), 1)
        self.assertIn(url, result)
        self.assertIn("state:approval", self.p.gh.issue(self.n)["labels"])


if __name__ == "__main__":
    unittest.main()
