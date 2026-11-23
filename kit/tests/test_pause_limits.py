"""Time spent paused by `loop pause` does not count against the build cap, the session limit or
a Test command timeout.

A stand-in supervisor is the loop.pid of a project. It runs one limited wait under a short limit, and the
test pauses it with bin/loop for longer than that limit, resumes it and reads what the wait reported.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from kit.tests.helpers import HERE, make_repo, settings_json

ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "kit", "scripts")
HOOKS = os.path.join(ROOT, "kit", "hooks")
LOOP = os.path.join(ROOT, "kit", "bin", "loop")
AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"

CHILD = r'''
import contextlib, io, json, os, signal, subprocess, sys, time
sys.path.insert(0, %(scripts)r)
sys.path.insert(0, %(hooks)r)
project, scenario, ready, out = sys.argv[1:5]
os.chdir(project)
begin = time.time()
touch = "touch " + ready + "; "
result = {}
if scenario in ("reap", "reap-plain"):
    import loop
    proc = subprocess.Popen(["sh", "-c", touch + "sleep 30"], start_new_session=True)
    st = dict(building={7: (None, proc)}, started={7: time.time()}, deaths={}, attempts={}, last="")
    buf = io.StringIO()
    cap = 4 if scenario == "reap" else 2
    end = None
    with contextlib.redirect_stdout(buf):
        while True:
            loop.reap(project, st, cap)
            if not st["building"]:
                break
            if scenario == "reap" and end is None and time.time() - begin > 2:
                end = time.time()  # first look after the resume, well before the cap is spent
            if end is not None and time.time() - end > 1.5:
                break
            if time.time() - begin > 60:
                break
            time.sleep(0.1)
    result = dict(running=proc.poll() is None, said=buf.getvalue(), seconds=time.time() - begin)
    with contextlib.suppress(OSError):
        os.killpg(proc.pid, signal.SIGKILL)
elif scenario in ("session", "session-plain"):
    import session
    limit = 3 if scenario == "session" else 2
    command = touch + ("sleep 2" if scenario == "session" else "sleep 30")
    try:
        got = session._exec(["sh", "-c", command], "", project, dict(os.environ, LOOP_PROJECT=project),
                            os.path.join(project, "session.log"), "builder", 7, limit)
        result = dict(code=got[2], error="", seconds=time.time() - begin)
    except session.SessionError as e:
        result = dict(code=None, error=str(e), seconds=time.time() - begin)
elif scenario in ("shell", "shell-plain"):
    import common
    limit = 3 if scenario == "shell" else 2
    command = touch + ("sleep 2" if scenario == "shell" else "sleep 30")
    code, _ = common.run_shell(command, project, limit)
    result = dict(code=code, seconds=time.time() - begin)
elif scenario in ("merge", "merge-plain"):
    import merge
    merge.TEST_TIMEOUT = 3 if scenario == "merge" else 2
    command = touch + ("sleep 2" if scenario == "merge" else "sleep 30")
    result = dict(problem=merge.run_in("Test", command, project, "the branch"), seconds=time.time() - begin)
elif scenario in ("stop", "stop-plain"):
    import common, stop
    stop.TIMEOUT = 3 if scenario == "stop" else 2
    command = touch + ("sleep 2" if scenario == "stop" else "sleep 30")
    settings = {"Session minutes": 0.01, "Test command": command, "Test files command": "", "Check command": ""}
    common.read_settings = lambda p: settings
    result = dict(problem=stop.problem("builder", project, project), seconds=time.time() - begin)
with open(out, "w") as f:
    json.dump(result, f)
'''


class PauseLimitsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work, _ = make_repo(self.tmp.name, {"loop.json": settings_json(AGENTS)})
        os.makedirs(os.path.join(self.work, ".loop"), exist_ok=True)
        self.ready = os.path.join(self.tmp.name, "ready")
        self.out = os.path.join(self.tmp.name, "out.json")
        self.child = None
        self.addCleanup(self.stop_child)

    def stop_child(self):
        if self.child and self.child.poll() is None:
            for sig in ("CONT", "KILL"):
                subprocess.run(["pkill", "-" + sig, "-g", str(self.child.pid)], capture_output=True)
            self.child.kill()
            self.child.wait()

    def loop_cmd(self, word):
        return subprocess.run([LOOP, word], cwd=self.work, capture_output=True, text=True, timeout=60)

    def start(self, scenario):
        code = CHILD % dict(scripts=SCRIPTS, hooks=HOOKS)
        env = dict(os.environ, LOOP_PROJECT=self.work)
        self.child = subprocess.Popen([sys.executable, "-c", code, self.work, scenario, self.ready, self.out],
                                      cwd=self.work, env=env, start_new_session=True,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(os.path.join(self.work, ".loop", "loop.pid"), "w") as f:
            f.write(str(self.child.pid))
        end = time.time() + 30
        while not os.path.exists(self.ready):
            self.assertLess(time.time(), end, "the limited command did not start")
            time.sleep(0.05)

    def finish(self):
        self.child.wait(timeout=90)
        with open(self.out) as f:
            return json.load(f)

    def paused_run(self, scenario):
        """Run a scenario, pause it for 5 seconds (longer than every limit used) and return its result."""
        self.start(scenario)
        time.sleep(0.5)
        paused = self.loop_cmd("pause")
        self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
        time.sleep(5)
        resumed = self.loop_cmd("resume")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        return self.finish()

    def plain_run(self, scenario):
        self.start(scenario)
        return self.finish()

    def test_build_cap_leaves_paused_time_out(self):
        got = self.paused_run("reap")
        self.assertTrue(got["running"], got)
        self.assertNotIn("killing it", got["said"])
        self.assertNotIn("crash on", got["said"])

    def test_session_limit_leaves_paused_time_out(self):
        got = self.paused_run("session")
        self.assertEqual(got["error"], "")
        self.assertEqual(got["code"], 0)

    def test_merge_test_timeout_leaves_paused_time_out(self):
        got = self.paused_run("merge")
        self.assertIsNone(got["problem"])

    def test_stop_hook_timeout_leaves_paused_time_out(self):
        got = self.paused_run("stop")
        self.assertIsNone(got["problem"])

    def test_run_shell_timeout_leaves_paused_time_out(self):
        got = self.paused_run("shell")
        self.assertEqual(got["code"], 0)

    def test_limits_still_fire_without_a_pause(self):
        got = self.plain_run("reap-plain")
        self.assertFalse(got["running"], got)
        self.assertIn("killing it", got["said"])
        self.assertGreaterEqual(got["seconds"], 2)

    def test_session_limit_still_fires_without_a_pause(self):
        got = self.plain_run("session-plain")
        self.assertIn("session timed out", got["error"])
        self.assertGreaterEqual(got["seconds"], 2)

    def test_test_timeouts_still_fire_without_a_pause(self):
        for scenario, key in (("shell-plain", "code"), ("merge-plain", "problem"), ("stop-plain", "problem")):
            with self.subTest(scenario):
                os.remove(self.ready) if os.path.exists(self.ready) else None
                got = self.plain_run(scenario)
                self.assertIsNone(got[key]) if key == "code" else self.assertIn("timed out", got[key])
                self.assertGreaterEqual(got["seconds"], 2)


if __name__ == "__main__":
    unittest.main()
