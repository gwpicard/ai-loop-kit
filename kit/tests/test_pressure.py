"""Only critical memory pressure holds parallel work; a stopped test run leaves no processes."""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import HERE, make_repo, settings_json
import common
import loop
import session
import flow
import merge

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"


class Pressure(FakeCodexGh):
    """Stub pressure readings and build counts; the last reading repeats."""

    def setUp(self):
        super().setUp()
        self.pressure = mock.patch.object(common, "pressure_level").start()
        self.count = mock.patch.object(common, "build_count", return_value=2).start()
        self.addCleanup(mock.patch.stopall)
        for p in (mock.patch.object(common, "project_of", return_value=self.tmp),
                  mock.patch.object(common, "sleep", self.nap)):
            p.start()
            self.addCleanup(p.stop)
        self.naps = []
        self.advance = 0

    def nap(self, seconds):
        self.naps.append(seconds)
        time.sleep(self.advance)

    def levels(self, *levels):
        self.readings = []
        pending = iter(levels)
        def read():
            level = next(pending, levels[-1])
            self.readings.append([str(level), str(int(os.path.exists(os.environ.get("MARKER", "/nonexistent"))))])
            return int(level) if level != "fail" else None
        self.pressure.side_effect = read

    def reads(self):
        return self.readings


class SessionAndCommandTest(Pressure):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"loop.json": settings_json(AGENTS)})

    def run_session(self, agent="claude"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            session.run("builder", "do it", self.work, "sonnet", self.work, 7, agent=agent)
        return out.getvalue()

    def test_session_is_held_at_4_and_starts_at_2(self):
        self.claude({"builder": [{"reply": "done"}]})
        self.levels("4", "4", "2")
        # The fake claude leaves its call log when it starts.
        os.environ["MARKER"] = os.environ["FAKE_CLAUDE_SCENARIO"] + ".calls"
        out = self.run_session()
        self.assertEqual([r[0] for r in self.reads()], ["4", "4", "2"])
        self.assertEqual([r[1] for r in self.reads()], ["0"] * 3)
        self.assertEqual(len(self.claude_calls()), 1)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("4", lines[0])
        self.assertRegex(lines[1], r"\d")

    def test_command_is_held_at_4_and_starts_at_2(self):
        marker = os.path.join(self.tmp, "ran")
        os.environ["MARKER"] = marker
        self.levels("4", "4", "2")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, text = common.run_shell("touch %s; echo ok" % marker, self.tmp, 60)
        self.assertEqual((code, text.strip()), (0, "ok"))
        self.assertEqual([r[0] for r in self.reads()], ["4", "4", "2"])
        self.assertEqual([r[1] for r in self.reads()], ["0", "0", "0"])
        self.assertEqual(len(out.getvalue().splitlines()), 2)

    def test_no_wait_at_level_1(self):
        self.levels("1")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(common.run_shell("echo ok", self.tmp, 60)[0], 0)
        self.assertEqual((self.naps, out.getvalue()), ([], ""))
        self.assertEqual(len(self.reads()), 1)

    def test_no_wait_when_the_reading_fails(self):
        self.levels("fail")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(common.run_shell("echo ok", self.tmp, 60)[0], 0)
        self.assertEqual((self.naps, out.getvalue()), ([], ""))

    def test_sessions_and_commands_start_at_warning_or_with_one_build(self):
        for level, count in ((2, 2), (4, 1), (4, 0)):
            for agent in ("claude", "codex"):
                with self.subTest(level=level, count=count, agent=agent):
                    self.levels(str(level))
                    self.count.return_value = count
                    self.claude({"builder": [{"reply": "done"}]})
                    self.codex([{"reply": "done"}])
                    self.assertEqual(self.run_session(agent), "")
                    self.assertEqual(common.run_shell("echo ok", self.work, 1), (0, "ok\n"))
                    self.assertEqual(self.naps, [])

    def test_the_wait_does_not_count_against_the_command_timeout(self):
        self.levels("4", "4", "2")
        self.advance = 1.2  # each wait step outlasts the one-second timeout
        with contextlib.redirect_stdout(io.StringIO()):
            code, text = common.run_shell("echo ok", self.tmp, 1)
        self.assertEqual((code, text.strip()), (0, "ok"))


class LongWaitTest(Pressure):
    def setUp(self):
        super().setUp()
        self.now = 1000.0
        for name in ("time", "monotonic"):
            p = mock.patch.object(time, name, lambda: self.now)
            p.start()
            self.addCleanup(p.stop)

    def nap(self, seconds):
        self.naps.append(seconds)
        self.now += seconds

    def test_a_command_starts_after_ten_minutes_and_records_the_wait(self):
        self.levels("4")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with mock.patch.dict(os.environ, LOOP_ISSUE="7"):
                self.assertEqual(common.run_shell("echo ok", self.tmp, 60)[0], 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(self.now, 1600)
        self.assertEqual(len(lines), 2)
        self.assertIn("10 minutes; starting anyway", lines[-1])
        with open(os.path.join(self.tmp, ".loop", "loop.out")) as f:
            logged = f.read().splitlines()
        self.assertEqual(len(logged), 1)
        self.assertIn("10 minutes; starting anyway", logged[0])
        with open(os.path.join(self.tmp, ".loop", "events.jsonl")) as f:
            events = [json.loads(line) for line in f]
        self.assertEqual([(e["level"], e["seconds"]) for e in events if e["kind"] == "memory-wait"], [(4, 600)])
        self.assertEqual(common.paused_seconds(self.tmp, 1000, 7), 600)

    def test_the_stop_hook_gives_up_after_ten_minutes_and_runs_the_command(self):
        self.levels("4")
        spec = importlib.util.spec_from_file_location("stop_hook", os.path.join(HERE, "..", "hooks", "stop.py"))
        stop = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stop)
        start = self.now
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, text = stop.run("echo ok", self.tmp)
        self.assertEqual((code, text.strip()), (0, "ok"))
        self.assertGreaterEqual(self.now - start, 600)
        self.assertLess(self.now - start, 700)
        self.assertIn("10 minutes", out.getvalue())

    def test_both_agents_start_after_ten_minutes(self):
        work, _ = make_repo(self.tmp, {"loop.json": settings_json(AGENTS)})
        self.claude({"builder": [{"reply": "done"}]})
        self.codex([{"reply": "done"}])
        for agent in ("claude", "codex"):
            self.levels("4")
            start = self.now
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                reply, _ = session.run("builder", "do it", work, "sonnet", work, 7, agent=agent)
            self.assertEqual(reply, "done")
            self.assertEqual(self.now - start, 600)
            self.assertEqual(out.getvalue().count("10 minutes; starting anyway"), 1)

    def test_build_cap_leaves_finished_and_current_memory_waits_out(self):
        self.levels("4")
        proc = mock.Mock()
        proc.poll.return_value = None
        st = dict(building={7: (None, proc)}, started={7: self.now})
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(os, "killpg") as kill:
            with common.build_environment(self.tmp, 7):
                for _ in range(12):
                    self.assertEqual(common.run_shell("echo ok", self.tmp, 1), (0, "ok\n"))
            self.now += 60 * 60
            loop.reap(self.tmp, st, 165 * 60)
            kill.assert_not_called()
            self.now += 105 * 60
            def nap(seconds):
                self.now += seconds
                loop.reap(self.tmp, st, 165 * 60)
                kill.assert_not_called()
            with mock.patch.object(common, "sleep", side_effect=nap):
                common.wait_for_memory(project=self.tmp, issue=7)
            self.now += 1
            loop.reap(self.tmp, st, 165 * 60)
            kill.assert_called_once_with(proc.pid, signal.SIGKILL)

    def test_the_merge_lock_is_free_during_the_wait_and_commands_do_not_wait_inside(self):
        self.levels("4", "2")
        checked = []
        def nap(seconds):
            with open(os.path.join(self.tmp, ".loop", "merge.lock"), "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                checked.append(True)
            self.now += seconds
        def merge_one(*args):
            self.levels("4")
            self.assertEqual(common.run_shell("echo ok", self.tmp, 1), (0, "ok\n"))
            return merge.Result(True, False, "merged", "abc")
        os.makedirs(os.path.join(self.tmp, ".loop"), exist_ok=True)
        with mock.patch.object(common, "sleep", side_effect=nap), \
                mock.patch.object(flow, "git", return_value="abc"), \
                mock.patch.object(merge, "merge", side_effect=merge_one), \
                contextlib.redirect_stdout(io.StringIO()):
            landed = flow._land(7, "issue/test", "approved", self.tmp, self.tmp, {"Loop branch": "loop/main"})
        self.assertTrue(landed.result.ok)
        self.assertEqual(checked, [True])
        self.assertEqual(self.now, 1030)

    def test_a_wait_ends_when_only_one_build_remains(self):
        self.levels("4")
        self.count.side_effect = [2, 2, 1]
        with contextlib.redirect_stdout(io.StringIO()):
            common.wait_for_memory(project=self.tmp, issue=7)
        self.assertEqual(self.now, 1030)


class HeadroomTest(Pressure):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(os, "getloadavg", lambda: (0.0, 0.0, 0.0))
        p.start()
        self.addCleanup(p.stop)

    def test_only_pressure_4_defers_another_build(self):
        for level, held in (("1", False), ("2", False), ("4", True)):
            self.levels(level)
            self.assertEqual(bool(loop.headroom()), held, level)

    def test_warning_starts_two_builds_and_critical_starts_only_the_first(self):
        for level, count in (("2", 2), ("4", 1)):
            self.levels(level)
            st = loop.new_state()
            proc = mock.Mock(pid=123)
            with mock.patch.object(loop, "pick", side_effect=[7, 8, None]), \
                    mock.patch.object(loop, "claim"), \
                    mock.patch.object(subprocess, "Popen", return_value=proc) as start, \
                    contextlib.redirect_stdout(io.StringIO()):
                loop.start_builds(self.tmp, {"Parallel": 2}, st)
            self.assertEqual(start.call_count, count)
            self.assertEqual(len(st["building"]), count)

    def test_load_average_still_defers(self):
        self.levels("1")
        with mock.patch.object(os, "getloadavg", lambda: (99.0, 0.0, 0.0)):
            self.assertIn("load average", loop.headroom())

    def test_vm_stat_and_min_free_are_gone(self):
        self.assertFalse(hasattr(loop, "MIN_FREE"))
        with open(os.path.join(HERE, "..", "scripts", "loop.py")) as f:
            self.assertNotIn("vm_stat", f.read())


BLOCKER = '''import os, subprocess, unittest

class T(unittest.TestCase):
    def test_blocks(self):
        child = subprocess.Popen(["sleep", "300"])
        with open(os.environ["PIDS"], "w") as f:
            f.write("%d %d" % (os.getpid(), child.pid))
        subprocess.run(["sleep", "300"])
'''


class RunnerTest(unittest.TestCase):
    def test_sigterm_leaves_no_test_process(self):
        with tempfile.TemporaryDirectory() as root:
            tests = os.path.join(root, "kit", "tests")
            os.makedirs(tests)
            open(os.path.join(root, "kit", "__init__.py"), "w").close()
            open(os.path.join(tests, "__init__.py"), "w").close()
            shutil.copy(os.path.join(HERE, "run.py"), tests)
            with open(os.path.join(tests, "test_block.py"), "w") as f:
                f.write(BLOCKER)
            pids = os.path.join(root, "pids")
            p = subprocess.Popen([sys.executable, os.path.join(tests, "run.py")], cwd=root,
                                 env=dict(os.environ, PIDS=pids), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            found = []
            try:
                for _ in range(100):
                    if os.path.exists(pids) and open(pids).read().count(" "):
                        found = [int(x) for x in open(pids).read().split()]
                        break
                    time.sleep(0.1)
                self.assertEqual(len(found), 2, "the blocking test never started")
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=15)
                time.sleep(3)
                alive = []
                for pid in found:
                    try:
                        os.kill(pid, 0)
                        alive.append(pid)
                    except ProcessLookupError:
                        pass
                self.assertEqual(alive, [])
            finally:
                if p.poll() is None:
                    p.kill()
                for pid in found:
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
