"""The loop waits while macOS reports memory pressure, and a stopped test run leaves no processes."""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import HERE, make_repo, write_exe
import common
import loop
import session

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"
FAKE_SYSCTL = '''#!PYTHON
import json, os, sys
if "kern.memorystatus_vm_pressure_level" not in sys.argv[1:]:
    sys.exit(1)
state = os.environ["FAKE_SYSCTL"]
levels = json.load(open(state + ".levels"))
log = state + ".log"
n = len(open(log).read().splitlines()) if os.path.exists(log) else 0
level = levels[min(n, len(levels) - 1)]
with open(log, "a") as f:
    f.write("%s %d\\n" % (level, os.path.exists(os.environ.get("MARKER", "/nonexistent"))))
if level == "fail":
    sys.exit(1)
print(level)
'''


class Pressure(FakeClaudeGh):
    """A fake sysctl on PATH answering the pressure level in order; the last answer repeats."""

    def setUp(self):
        super().setUp()
        self.state = os.path.join(self.tmp, "sysctl")
        write_exe(os.path.join(self.tmp, "bin", "sysctl"), FAKE_SYSCTL)
        os.environ["FAKE_SYSCTL"] = self.state
        for p in (mock.patch.object(sys, "platform", "darwin"),
                  mock.patch.object(common, "sleep", self.nap)):
            p.start()
            self.addCleanup(p.stop)
        self.naps = []
        self.advance = 0

    def nap(self, seconds):
        self.naps.append(seconds)
        time.sleep(self.advance)

    def levels(self, *levels):
        with open(self.state + ".levels", "w") as f:
            json.dump(list(levels), f)

    def reads(self):
        if not os.path.exists(self.state + ".log"):
            return []
        with open(self.state + ".log") as f:
            return [line.split() for line in f.read().splitlines()]


class SessionAndCommandTest(Pressure):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": AGENTS})

    def run_session(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            session.run("builder", "do it", self.work, "sonnet", self.work, 7)
        return out.getvalue()

    def test_session_is_held_while_pressure_is_2_and_starts_at_1(self):
        self.claude({"builder": [{"reply": "done"}]})
        self.levels("2", "4", "2", "1")
        # The fake claude leaves its call log when it starts; no read of 2 may see it.
        os.environ["MARKER"] = os.environ["FAKE_CLAUDE_SCENARIO"] + ".calls"
        out = self.run_session()
        self.assertEqual([r[0] for r in self.reads()], ["2", "4", "2", "1"])
        self.assertEqual([r[1] for r in self.reads()], ["0"] * 4)
        self.assertEqual(len(self.claude_calls()), 1)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("2", lines[0])
        self.assertRegex(lines[1], r"\d")

    def test_command_is_held_while_pressure_is_2_and_starts_at_1(self):
        marker = os.path.join(self.tmp, "ran")
        os.environ["MARKER"] = marker
        self.levels("2", "2", "1")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, text = common.run_shell("touch %s; echo ok" % marker, self.tmp, 60)
        self.assertEqual((code, text.strip()), (0, "ok"))
        self.assertEqual([r[0] for r in self.reads()], ["2", "2", "1"])
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

    def test_no_wait_when_sysctl_is_missing(self):
        os.remove(os.path.join(self.tmp, "bin", "sysctl"))
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self.tmp, "bin")}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(common.run_shell("echo ok", self.tmp, 60)[0], 0)
        self.assertEqual(self.naps, [])

    def test_the_wait_does_not_count_against_the_command_timeout(self):
        self.levels("2", "2", "1")
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

    def test_a_wait_repeats_its_line_every_ten_minutes(self):
        self.levels(*(["2"] * 51 + ["1"]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(common.run_shell("echo ok", self.tmp, 60)[0], 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 4)  # at 0, 10 and 20 minutes, then the end
        self.assertRegex(lines[-1], r"\d")

    def test_the_stop_hook_gives_up_after_ten_minutes_and_runs_the_command(self):
        self.levels("2")
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


class HeadroomTest(Pressure):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(os, "getloadavg", lambda: (0.0, 0.0, 0.0))
        p.start()
        self.addCleanup(p.stop)

    def test_pressure_2_or_4_is_a_reason_and_1_is_not(self):
        for level, held in (("1", False), ("2", True), ("4", True)):
            self.levels(level)
            os.path.exists(self.state + ".log") and os.remove(self.state + ".log")
            self.assertEqual(bool(loop.headroom()), held, level)

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
