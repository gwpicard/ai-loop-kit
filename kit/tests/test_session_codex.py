import os
import unittest

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo
import common
import session

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"
ENV = ("LOOP_ROLE", "LOOP_LOCKED", "LOOP_ALLOWED", "LOOP_PROTECTED", "LOOP_LOOP_BRANCH",
       "LOOP_DEFAULT_BRANCH", "LOOP_PROJECT", "LOOP_START")


class CodexSessionTest(FakeCodexGh):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": AGENTS})

    def run_session(self, resume=None, **kw):
        return session.run("builder", "do it", self.work, "gpt-6", self.work, 7,
                           resume=resume, agent="codex", **kw)

    def test_start_runs_codex_exec_and_returns_reply_and_session_id(self):
        self.codex([{"reply": "built it", "thread": "t-abc"}])
        text, sid = self.run_session()
        self.assertEqual((text, sid), ("built it", "t-abc"))
        self.assertEqual(self.claude_calls(), [])
        self.assertEqual(len(self.codex_calls()), 1)
        call = self.codex_calls()[0]
        argv = call["argv"]
        self.assertEqual(argv[0], "exec")
        self.assertNotIn("resume", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6")
        self.assertEqual(argv[argv.index("-s") + 1], "workspace-write")
        self.assertEqual(call["prompt"], "do it")
        self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.work))

    def test_a_fix_round_resumes_the_same_session(self):
        self.codex([{"reply": "first", "thread": "t-abc"}, {"reply": "fixed"}])
        _, sid = self.run_session()
        text, sid2 = self.run_session(resume=sid)
        self.assertEqual((text, sid2), ("fixed", "t-abc"))
        self.assertEqual(len(self.codex_calls()), 2)
        argv = self.codex_calls()[1]["argv"]
        self.assertEqual(argv[:3], ["exec", "resume", "t-abc"])
        self.assertEqual(self.codex_calls()[1]["prompt"], "do it")

    def test_the_session_receives_every_loop_variable(self):
        self.codex([{"reply": "ok"}])
        self.run_session(locked=("a/test_x.py", "b/test_y.py"), allowed=("src/",), start="abc123")
        self.assertEqual(len(self.codex_calls()), 1)
        env = self.codex_calls()[0]["env"]
        for name in ENV:
            self.assertIn(name, env)
        self.assertEqual(env["LOOP_PROJECT"], self.work)
        self.assertEqual(env["LOOP_ROLE"], "builder")
        self.assertEqual(env["LOOP_LOCKED"], "a/test_x.py\nb/test_y.py")
        self.assertEqual(env["LOOP_ALLOWED"], "src/")
        self.assertEqual(env["LOOP_START"], "abc123")
        self.assertEqual(env["LOOP_LOOP_BRANCH"], "loop/main")

    def test_a_failed_codex_run_raises_a_session_error(self):
        self.codex([{"error": "boom"}])
        with self.assertRaises(session.SessionError):
            self.run_session()

    def read(self, body):
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS + body)
        return common.read_settings(self.work)


if __name__ == "__main__":
    unittest.main()
