import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from lite.tests.helpers import HERE, make_repo, run_git
import common

STOP = os.path.join(HERE, "..", "hooks", "stop.py")
AGENTS = ("## Loop\nTest command: seq 1 100; test ! -f FAIL\n"
          "Check command: test ! -f BAD\nLoop branch: loop/main\n")


class StopHookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work, _ = make_repo(self._tmp.name, {"AGENTS.md": AGENTS})
        self.start = common.git(["rev-parse", "HEAD"], cwd=self.work)

    def touch(self, name, commit=False):
        path = os.path.join(self.work, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("x\n")
        if commit:
            run_git(["add", "-A"], self.work)
            run_git(["commit", "-m", name], self.work)

    def stop(self, role, session="s1", **env):
        env = dict(dict(os.environ, LITE_ROLE=role, LITE_PROJECT=self.work,
                        LITE_START=self.start), **env)
        p = subprocess.run([sys.executable, STOP], cwd=self.work, env=env, text=True,
                           input=json.dumps({"session_id": session}), capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return json.loads(p.stdout) if p.stdout.strip() else None

    def test_builder_with_failing_tests_is_blocked_with_the_last_60_lines(self):
        self.touch("FAIL")
        out = self.stop("builder")
        self.assertEqual(out["decision"], "block")
        self.assertIn("Test command fails", out["reason"])
        self.assertIn("\n41\n42\n", out["reason"])
        self.assertNotIn("\n40\n", out["reason"])
        self.assertTrue(out["reason"].rstrip().endswith("100"))

    def test_builder_with_failing_check_is_blocked(self):
        self.touch("BAD")
        self.assertIn("Check command fails", self.stop("builder")["reason"])

    def test_builder_with_passing_checks_is_allowed(self):
        self.assertIsNone(self.stop("builder"))

    def test_builder_is_blocked_at_most_three_times_per_session(self):
        self.touch("FAIL")
        results = [self.stop("builder") for _ in range(4)]
        self.assertEqual([r is not None for r in results], [True, True, True, False])
        self.assertIsNotNone(self.stop("builder", session="s2"))

    def test_counters_are_kept_per_session(self):
        self.touch("FAIL")
        seen = [(sid, self.stop("builder", session=sid) is not None)
                for _ in range(4) for sid in ("s1", "s2")]
        self.assertEqual([b for _, b in seen if _ == "s1"], [True, True, True, False])
        self.assertEqual([b for _, b in seen if _ == "s2"], [True, True, True, False])
        self.assertEqual(sorted(f for f in os.listdir(os.path.join(self.work, ".lite"))),
                         ["stop-s1", "stop-s2"])

    def test_a_command_that_hangs_is_killed_and_blocks(self):
        sys.path.insert(0, os.path.dirname(STOP))
        import stop
        with mock.patch.object(stop, "TIMEOUT", 1):
            started = time.time()
            self.assertEqual(stop.run("sleep 30", self.work), (None, ""))
            self.assertLess(time.time() - started, 10)
            with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
                f.write("## Loop\nTest command: sleep 30\n")
            self.assertIn("timed out after 1 seconds", stop.problem("builder", self.work, self.work))

    def test_an_error_allows_the_stop(self):
        self.touch("FAIL")
        self.assertIsNone(self.stop("builder", LITE_PROJECT=os.path.join(self.work, "nowhere")))
        p = subprocess.run([sys.executable, STOP], input="not json", text=True,
                           capture_output=True, env=dict(os.environ, LITE_ROLE="builder"))
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_other_roles_are_allowed(self):
        self.touch("FAIL")
        for role in ("reviewer", "simplify", "pass"):
            self.assertIsNone(self.stop(role))

    def test_test_writer_without_a_new_test_file_is_blocked_twice_then_allowed(self):
        self.touch("app.py", commit=True)
        results = [self.stop("test-writer") for _ in range(3)]
        self.assertEqual([r is not None for r in results], [True, True, False])
        self.assertIn("No new test file", results[0]["reason"])

    def test_test_writer_with_a_committed_test_file_is_allowed(self):
        self.touch("tests/test_new.py", commit=True)
        self.assertIsNone(self.stop("test-writer"))

    def test_test_writer_with_an_uncommitted_test_file_is_blocked(self):
        self.touch("tests/test_new.py")
        self.assertIsNotNone(self.stop("test-writer"))


if __name__ == "__main__":
    unittest.main()
