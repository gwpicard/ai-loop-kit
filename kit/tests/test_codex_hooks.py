import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.fake_codex_hooks import FakeCodexHooks
from kit.tests.helpers import make_repo, run_git
import common
import session

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "guard.py")
GH_TOKEN = "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"  # built from pieces: no secret shape here
FILES = {"README.md": "hi\n", "src/app.py": "x = 1\n", "tests/test_app.py": "pass\n"}


def patch(*sections):
    return "*** Begin Patch\n" + "".join(sections) + "*** End Patch\n"


def update(path, body="@@\n-x\n+y\n"):
    return "*** Update File: %s\n%s" % (path, body)


def add(path, text="+x\n"):
    return "*** Add File: %s\n%s" % (path, text)


class CodexGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.work, _ = make_repo(cls._tmp.name, dict(FILES))
        run_git(["checkout", "-b", "feature"], cls.work)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def guard(self, data, role="builder", agent="codex", raw=None, locked=()):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LITE_")}
        env["LITE_ROLE"] = role
        env["LITE_LOCKED"] = "\n".join(locked)
        if agent:
            env["LITE_AGENT"] = agent
        text = raw if raw is not None else json.dumps(dict(data, cwd=self.work))
        return subprocess.run([sys.executable, GUARD], input=text, capture_output=True, text=True, env=env)

    def refused(self, r):
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("refused: ", r.stderr)
        self.assertIn("next: ", r.stderr)

    def allowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def shell(self, command, **kw):
        return self.guard({"tool_name": "Bash", "tool_input": {"command": command}}, **kw)

    def apply(self, text, **kw):
        return self.guard({"tool_name": "apply_patch", "tool_input": {"command": text}}, **kw)

    def test_shell_commands_meet_the_claude_checks(self):
        for command in ("git push origin main", "git push --force origin feature", "rm -rf build",
                        "git merge feature", "gh pr create", "echo x > tests/test_app.py"):
            self.refused(self.shell(command))
        self.allowed(self.shell("git commit -m work"))
        self.allowed(self.shell("echo ok"))

    def test_a_shell_command_given_as_a_list_is_checked(self):
        r = self.guard({"tool_name": "Bash", "tool_input": {"command": ["bash", "-lc", "git push origin main"]}})
        self.refused(r)
        r = self.guard({"tool_name": "Bash", "tool_input": {"command": ["bash", "-lc", "echo ok"]}})
        self.allowed(r)

    def test_a_patch_to_a_tracked_test_file_is_refused(self):
        self.refused(self.apply(patch(update("tests/test_app.py"))))
        self.refused(self.apply(patch("*** Delete File: tests/test_app.py\n")))
        self.refused(self.apply(patch(update("src/app.py"), update("tests/test_app.py"))))

    def test_a_patch_that_moves_a_file_is_checked_at_both_paths(self):
        self.refused(self.apply(patch(update("src/app.py", "*** Move to: tests/test_app.py\n@@\n-x\n+y\n"))))
        self.refused(self.apply(patch(update("tests/test_app.py", "*** Move to: src/other.py\n@@\n-x\n+y\n"))))

    def test_a_patch_to_a_locked_path_is_refused(self):
        self.refused(self.apply(patch(update("src/app.py")), locked=("src/app.py",)))

    def test_a_patch_to_a_source_file_or_a_new_test_file_passes(self):
        self.allowed(self.apply(patch(update("src/app.py"))))
        self.allowed(self.apply(patch(add("tests/test_new.py"))))

    def test_a_patch_with_a_secret_shape_is_refused(self):
        self.refused(self.apply(patch(add("src/key.py", "+KEY = '%s'\n" % GH_TOKEN))))

    def test_the_reviewer_may_not_apply_a_patch(self):
        self.refused(self.apply(patch(update("src/app.py")), role="reviewer"))

    def test_the_patch_may_arrive_as_the_whole_tool_input(self):
        self.refused(self.guard({"tool_name": "apply_patch", "tool_input": patch(update("tests/test_app.py"))}))
        self.allowed(self.guard({"tool_name": "apply_patch", "tool_input": patch(update("src/app.py"))}))

    def test_a_codex_payload_it_cannot_parse_is_refused(self):
        for raw in ("not json", "[]", "null", "{}"):
            self.refused(self.guard(None, raw=raw))
        for data in ({"tool_name": "Bash", "tool_input": {}},
                     {"tool_name": "Bash", "tool_input": {"command": 7}},
                     {"tool_name": "apply_patch", "tool_input": {"command": "no headers here"}},
                     {"tool_name": "apply_patch", "tool_input": {}},
                     {"tool_name": "something_new", "tool_input": {"command": "x"}}):
            self.refused(self.guard(data))

    def test_a_claude_session_still_allows_what_it_cannot_parse(self):
        self.allowed(self.guard(None, raw="not json", agent=None))
        self.allowed(self.guard(None, raw="not json", agent="claude"))


class CodexSessionHooksTest(FakeCodexHooks):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.build()

    def build(self, test="test -f GOOD"):
        self.work, _ = make_repo(self.tmp, dict(
            FILES, **{"AGENTS.md": "## Loop\nTest command: %s\nLoop branch: loop/main\n" % test}))
        self.start = common.git(["rev-parse", "HEAD"], cwd=self.work).strip()

    def run_session(self, role="builder", resume=None, **kw):
        return session.run(role, "do it", self.work, "gpt-6", self.work, 7, resume=resume, agent="codex",
                           start=self.start, **kw)

    def reasons(self, text):
        return [c for c in self.codex_calls() if text in c["prompt"]]

    def test_the_session_is_marked_as_a_codex_session(self):
        self.codex([{"reply": "ok"}])
        self.run_session("reviewer")
        self.assertEqual(self.codex_calls()[0]["env"]["LITE_AGENT"], "codex")

    def test_the_hook_configuration_guards_every_shell_command_and_file_change(self):
        secret = patch(add("src/key.py", "+KEY = '%s'\n" % GH_TOKEN))
        calls = [
            {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}},
            {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}},
            {"tool_name": "Bash", "tool_input": {"command": "echo ok"}},
            {"tool_name": "apply_patch", "tool_input": {"command": patch(update("tests/test_app.py"))}},
            {"tool_name": "apply_patch", "tool_input": {"command": secret}},
            {"tool_name": "apply_patch", "tool_input": {"command": patch(update("src/app.py"))}},
            {"tool_name": "apply_patch", "tool_input": {"command": "garbage"}},
        ]
        self.codex([{"reply": "ok", "tool_calls": calls}])
        self.run_session("test-writer")
        results = self.hook_results()
        self.assertEqual(len(results), len(calls))
        self.assertTrue(all(r["matched"] for r in results), results)
        self.assertEqual([r["code"] for r in results], [2, 2, 2, 0, 2, 2, 0, 2])

    def test_a_locked_path_is_refused_through_the_configuration(self):
        calls = [{"tool_name": "apply_patch", "tool_input": {"command": patch(update("src/app.py"))}}]
        self.codex([{"reply": "ok", "tool_calls": calls}])
        self.run_session(locked=("src/app.py",))
        self.assertEqual([r["code"] for r in self.hook_results()], [2])

    def test_a_builder_with_a_failing_test_command_is_sent_back_with_the_reason(self):
        self.codex([{"reply": "done", "thread": "t-1"}, {"reply": "fixed", "files": {"GOOD": "x\n"}}])
        text, sid = self.run_session()
        self.assertEqual((text, sid), ("fixed", "t-1"))
        self.assertTrue(os.path.exists(os.path.join(self.work, "GOOD")))
        self.assertEqual(len(self.reasons("Test command fails")), 1)

    def test_a_builder_with_a_failing_check_command_is_sent_back(self):
        with open(os.path.join(self.work, "AGENTS.md"), "a") as f:
            f.write("Check command: test -f CLEAN\n")
        run_git(["commit", "-qam", "check"], self.work)
        self.codex([{"reply": "done", "files": {"GOOD": "x\n"}}, {"reply": "fixed", "files": {"CLEAN": "x\n"}}])
        self.run_session()
        self.assertEqual(len(self.reasons("Check command fails")), 1)

    def test_a_builder_is_sent_back_three_times_at_most(self):
        self.codex([{"reply": "done", "thread": "t-1"}])
        self.run_session()
        self.assertEqual(len(self.reasons("Test command fails")), 3)

    def test_the_builder_limit_is_shared_by_a_resumed_session(self):
        self.codex([{"reply": "done", "thread": "t-1"}])
        _, sid = self.run_session()
        before = len(self.reasons("Test command fails"))
        self.run_session(resume=sid)
        self.assertEqual((before, len(self.reasons("Test command fails"))), (3, 3))

    def test_a_builder_that_passes_is_not_sent_back(self):
        self.codex([{"reply": "done", "files": {"GOOD": "x\n"}}])
        self.run_session()
        self.assertEqual(self.reasons("fails"), [])
        self.assertEqual(len(self.codex_calls()), 1)

    def test_a_test_writer_with_no_new_test_file_is_sent_back(self):
        self.codex([{"reply": "done"}, {"reply": "wrote", "files": {"tests/test_new.py": "x\n"}}])
        self.run_session("test-writer")
        self.assertEqual(len(self.reasons("No new test file")), 1)

    def test_a_test_writer_is_sent_back_twice_at_most(self):
        self.codex([{"reply": "done"}])
        self.run_session("test-writer")
        self.assertEqual(len(self.reasons("No new test file")), 2)

    def test_a_reviewer_is_never_sent_back(self):
        self.codex([{"reply": "done"}])
        self.run_session("reviewer")
        self.assertEqual(len(self.codex_calls()), 1)


if __name__ == "__main__":
    unittest.main()
