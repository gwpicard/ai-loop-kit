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


if __name__ == "__main__":
    unittest.main()
