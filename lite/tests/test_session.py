import json
import os
import time
import unittest
from unittest import mock

from lite.tests.fake_claude import FakeClaudeGh
from lite.tests.helpers import make_repo, run_git
import common
import session

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"


class SessionTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": AGENTS})

    def run_session(self, role="builder", **kw):
        return session.run(role, "do it", self.work, "sonnet", self.work, 7, **kw)

    def test_flags_and_environment(self):
        self.claude({"builder": [{"reply": "done", "session_id": "abc"}]})
        text, sid = self.run_session(locked=("a/test_x.py", "b/test_y.py"), start="abc123")
        self.assertEqual((text, sid), ("done", "abc"))
        call = self.claude_calls()[0]
        argv = call["argv"]
        self.assertEqual(argv[0], "-p")
        for flag, value in (("--output-format", "json"), ("--permission-mode", "auto"),
                            ("--model", "sonnet"), ("--setting-sources", "project")):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("--resume", argv)
        hook = json.loads(argv[argv.index("--settings") + 1])["hooks"]["PreToolUse"][0]
        command = hook["hooks"][0]["command"]
        self.assertTrue(os.path.isabs(command.split()[-1]))
        self.assertTrue(command.endswith("hooks/guard.py"))
        self.assertTrue(os.path.exists(command.split()[-1]))
        hooks = json.loads(argv[argv.index("--settings") + 1])["hooks"]
        stop = hooks["Stop"][0]["hooks"][0]
        self.assertTrue(stop["command"].endswith("hooks/stop.py"))
        self.assertTrue(os.path.exists(stop["command"].split()[-1]))
        self.assertEqual(stop["timeout"], 1800)
        env = call["env"]
        self.assertEqual(env["LITE_PROJECT"], self.work)
        self.assertEqual(env["LITE_ROLE"], "builder")
        self.assertEqual(env["LITE_LOCKED"], "a/test_x.py\nb/test_y.py")
        self.assertEqual(env["LITE_START"], "abc123")
        self.assertEqual(env["LITE_LOOP_BRANCH"], "loop/main")
        self.assertEqual(env["LITE_DEFAULT_BRANCH"], "main")
        self.assertEqual(call["prompt"], "do it")

    def test_logs_and_resume(self):
        self.run_session()
        self.run_session(resume="abc")
        logs = os.path.join(self.work, ".lite", "logs")
        self.assertEqual(sorted(os.listdir(logs)), ["7-builder-1.log", "7-builder-2.log"])
        self.assertIn(["--resume", "abc"], [self.claude_calls()[1]["argv"][-2:]])

    def test_error_result_raises_one_line(self):
        self.claude({"builder": [{"error": "Something broke\nmore detail"}]})
        with self.assertRaises(session.SessionError) as cm:
            self.run_session()
        self.assertEqual(str(cm.exception), "builder session failed: Something broke")

    def test_crash_raises_one_line(self):
        self.claude({"builder": [{"crash": True}]})
        with self.assertRaises(session.SessionError) as cm:
            self.run_session()
        self.assertIn("gave no JSON result (exit 1): claude exploded", str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_usage_limit_waits_then_resumes(self):
        reset = int(time.time()) + 600
        self.claude({"builder": [
            {"limit": "Claude AI usage limit reached|%d" % reset, "session_id": "s1"},
            {"reply": "finished", "session_id": "s1"}]})
        with mock.patch.object(common, "sleep") as sleep:
            text, sid = self.run_session()
        self.assertEqual((text, sid), ("finished", "s1"))
        wait = sleep.call_args[0][0]
        self.assertTrue(500 <= wait <= 600, wait)
        first, second = [c["argv"] for c in self.claude_calls()]
        self.assertNotIn("--resume", first)
        self.assertEqual(second[second.index("--resume") + 1], "s1")

    def test_usage_limit_without_reset_waits_thirty_minutes(self):
        self.claude({"builder": [{"limit": "5-hour limit reached"}, {"reply": "ok"}]})
        with mock.patch.object(common, "sleep") as sleep:
            self.run_session()
        sleep.assert_called_once_with(1800)

    def test_timeout_kills_the_session(self):
        self.claude({"builder": [{"sleep": 30}]})
        started = time.time()
        with mock.patch.object(session, "TIMEOUT", 1):
            with self.assertRaises(session.SessionError) as cm:
                self.run_session()
        self.assertIn("timed out", str(cm.exception))
        self.assertLess(time.time() - started, 10)

    def test_a_process_left_in_the_group_is_killed_and_logged(self):
        self.claude({"builder": [{"spawn": True, "reply": "done"}]})
        started = time.time()  # the child holds the session's stdout; the wait must not
        self.assertEqual(self.run_session()[0], "done")
        self.assertLess(time.time() - started, 20)
        with open(self.claude_path + ".pid") as f:
            pid = int(f.read())
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            os.kill(pid, 9)
            self.fail("the leftover process is still alive")
        with open(os.path.join(self.work, ".lite", "logs", "7-builder-1.log")) as f:
            self.assertRegex(f.read(), "--- cleanup: left running, killed: %d .*sleep 300" % pid)

    def fake_docker(self, sessions, **ids):
        folder = os.path.join(self.tmp, "docker")
        os.makedirs(folder)
        for kind, names in ids.items():
            with open(os.path.join(folder, kind), "w") as f:
                f.write("\n".join(names))
        script = os.path.join(self.tmp, "bin", "docker")
        with open(script, "w") as f:
            f.write(FAKE_DOCKER)
        os.chmod(script, 0o755)
        os.environ["FAKE_DOCKER"] = folder
        self.claude({"builder": [{"files": {os.path.join(folder, k): "\n".join(v) for k, v in sessions.items()}}]})
        return folder

    def kept(self, folder, kind):
        with open(os.path.join(folder, kind)) as f:
            return f.read().split()

    def test_the_docker_sweep_removes_only_this_sessions_containers(self):
        folder = self.fake_docker({"c": ["old", "mine", "bound", "other", "nolabel"], "n": ["bridge", "net1"],
                                   "v": ["vol1"], "i": ["img0", "img1"]}, c=["old"], n=["bridge"], i=["img0"])
        mine = os.path.realpath(self.work)
        for name, text in (("mine", mine + "\n"), ("bound", "\n/elsewhere\n" + mine + "/data\n"),
                           ("other", mine + "-other\n/home/me/app\n"), ("nolabel", "")):
            with open(os.path.join(folder, "inspect-" + name), "w") as f:
                f.write(text)
        self.run_session()
        self.assertEqual([self.kept(folder, k) for k in "cnvi"],
                         [["old", "other", "nolabel"], ["bridge", "net1"], ["vol1"], ["img0", "img1"]])
        kept = " (kept, not removed)"
        self.assertEqual(session.SWEPT[7], ["removed container bound", "removed container mine",
                                            "new container nolabel" + kept, "new container other" + kept,
                                            "new network net1" + kept, "new volume vol1" + kept,
                                            "new image img1" + kept])
        with open(os.path.join(self.work, ".lite", "logs", "7-builder-1.log")) as f:
            self.assertIn("--- cleanup: removed container mine", f.read())

    def test_a_container_that_exited_during_the_session_counts(self):
        folder = self.fake_docker({"c": ["gone"]}, c=[])
        with open(os.path.join(folder, "inspect-gone"), "w") as f:
            f.write(self.work + "\n")
        self.run_session()
        self.assertEqual(self.kept(folder, "c"), [])
        self.assertTrue(any(c[:3] == ["ps", "-a", "-q"] for c in self.docker_calls()))

    def docker_calls(self):
        with open(os.path.join(self.tmp, "docker", "calls")) as f:
            return [line.split() for line in f]

    def test_a_docker_that_does_not_answer_is_ignored(self):
        self.fake_docker({"c": ["new"]}, c=[])
        os.environ["FAKE_DOCKER"] = "/nonexistent"  # the fake fails on every call
        self.assertEqual(self.run_session()[0], "ok")
        self.assertEqual(session.SWEPT.get(7, []), [])

    def test_without_docker_nothing_is_swept(self):
        self.run_session()
        self.assertEqual(session.SWEPT.get(7, []), [])


FAKE_DOCKER = '''#!/usr/bin/env python3
import os, sys
a, folder = sys.argv[1:], os.environ["FAKE_DOCKER"]
with open(os.path.join(folder, "calls"), "a") as f:
    f.write(" ".join(a) + "\\n")
if a[0] == "inspect":
    path = os.path.join(folder, "inspect-" + a[-1])
    sys.stdout.write(open(path).read() if os.path.exists(path) else "")
    sys.exit(0)
kind = {"ps": "c", "rm": "c", "images": "i", "network": "n", "volume": "v"}[a[0]]
path = os.path.join(folder, kind)
ids = open(path).read().split()
if "ls" in a or a[0] in ("ps", "images"):
    print("\\n".join(ids))
else:
    open(path, "w").write("\\n".join(i for i in ids if i not in a))
'''


if __name__ == "__main__":
    unittest.main()
