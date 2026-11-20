import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from kit.tests.helpers import HERE, make_repo, run_git
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
        broken = "LOOP_PROJECT" in env
        env = dict(dict(os.environ, LOOP_ROLE=role, LOOP_PROJECT=self.work,
                        LOOP_START=self.start), **env)
        p = subprocess.run([sys.executable, STOP], cwd=self.work, env=env, text=True,
                           input=json.dumps({"session_id": session}), capture_output=True)
        self.assertEqual((p.returncode, "internal error" in p.stderr), (0, broken))
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
        self.assertEqual(sorted(f for f in os.listdir(os.path.join(self.work, ".loop"))),
                         ["stop-s1", "stop-s2"])

    def test_a_command_that_hangs_is_killed_and_blocks(self):
        sys.path.insert(0, os.path.dirname(STOP))
        import stop
        with mock.patch.object(stop, "TIMEOUT", 1):
            started = time.time()
            self.assertEqual(stop.run("sleep 30", self.work), (None, ""))
            self.assertLess(time.time() - started, 10)
            with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
                f.write("## Loop\nTest command: sleep 30\nSession minutes: 0.05\n")
            self.assertIn("timed out after 1 seconds", stop.problem("builder", self.work, self.work))

    def test_the_command_timeout_is_a_third_of_the_session_limit_and_at_least_ten_minutes(self):
        sys.path.insert(0, os.path.dirname(STOP))
        import stop
        for minutes, expected in (("45", 900), ("20", 600), ("90", 1800)):
            with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
                f.write("## Loop\nTest command: true\nSession minutes: %s\n" % minutes)
            with mock.patch.object(stop, "run", return_value=(None, "")) as r:
                stop.problem("builder", self.work, self.work)
            self.assertEqual(r.call_args[0][2], expected)

    def test_a_pass_on_an_unchanged_commit_is_not_repeated_and_a_change_reruns(self):
        marker = os.path.join(self.work, "..", "runs")
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write("## Loop\nTest command: echo x >> %s\n" % marker)
        run_git(["commit", "-am", "agents"], self.work)
        runs = lambda: open(marker).read().count("x")
        self.assertIsNone(self.stop("builder"))
        self.assertIsNone(self.stop("builder"))
        self.assertEqual(runs(), 1)
        self.assertIsNone(self.stop("builder", session="s2"))
        self.assertEqual(runs(), 2)
        self.touch("new.py", commit=True)
        self.assertIsNone(self.stop("builder"))
        self.assertEqual(runs(), 3)
        self.touch("dirty.py")
        self.assertIsNone(self.stop("builder"))
        self.assertEqual(runs(), 4)

    def test_a_pass_records_the_head_and_the_tail_of_the_output(self):
        self.assertIsNone(self.stop("builder"))
        with open(os.path.join(self.work, ".loop", "passed-s1")) as f:
            head, *tail = f.read().splitlines()
        self.assertEqual(head, self.start)
        self.assertIn("Test command passed: 100", tail)
        self.assertIn("Test command: full suite", tail)

    def test_only_locked_and_changed_test_files_run_before_the_check(self):
        marker = os.path.join(self._tmp.name, "runs")
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write("## Loop\nTest command: echo full >> %s\n"
                    "Test files command: echo {files} >> %s\nCheck command: echo check >> %s\n"
                    % (marker, marker, marker))
        for name in ("tests/test_old.py", "tests/test_locked.py", "tests/test_changed.py"):
            self.touch(name, commit=True)
        self.start = common.git(["rev-parse", "HEAD"], cwd=self.work)
        with open(os.path.join(self.work, "tests/test_changed.py"), "a") as f:
            f.write("changed\n")
        for name in ("tests/test_added.py", "tests/helpers.py", "tests/run.py", "app.py"):
            self.touch(name, commit=True)
        self.assertIsNone(self.stop("builder", LOOP_LOCKED="tests/test_locked.py"))
        with open(marker) as f:
            self.assertEqual(f.read().splitlines(), ["tests/test_added.py tests/test_changed.py tests/test_locked.py", "check"])
        head, tails = common.read_passed(self.work, "s1")
        self.assertEqual(head, common.git(["rev-parse", "HEAD"], cwd=self.work))
        self.assertIn("Test files command: tests/test_added.py, tests/test_changed.py, tests/test_locked.py", tails)

    def test_targeted_tests_still_block_a_failing_check(self):
        with open(os.path.join(self.work, "AGENTS.md"), "a") as f:
            f.write("Test files command: true {files}\n")
        self.touch("FAIL")
        self.touch("BAD")
        self.assertIn("Check command fails", self.stop("builder")["reason"])

    def test_a_command_is_recorded_while_it_runs_so_the_session_can_kill_it(self):
        sys.path.insert(0, os.path.dirname(STOP))
        import stop
        record = os.path.join(self.work, "groups")
        with mock.patch.dict(os.environ, {"LOOP_GROUPS": record}):
            code, _ = stop.run("sleep 0.3; cat %s > %s; echo done" % (record, os.path.join(self.work, "during")), self.work)
        self.assertEqual(code, 0)
        with open(os.path.join(self.work, "during")) as f:
            self.assertTrue(f.read().strip().isdigit())
        with open(record) as f:
            self.assertEqual(f.read().strip(), "")

    def test_an_error_allows_the_stop(self):
        self.touch("FAIL")
        self.assertIsNone(self.stop("builder", LOOP_PROJECT=os.path.join(self.work, "nowhere")))
        p = subprocess.run([sys.executable, STOP], input="not json", text=True,
                           capture_output=True, env=dict(os.environ, LOOP_ROLE="builder"))
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
