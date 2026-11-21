import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from kit.tests import test_flow, test_setup
from kit.tests.fake_codex_check import FLAGS, FakeCodexCheck
from kit.tests.helpers import make_repo, settings_json
import common
import session

KIT = Path(__file__).resolve().parents[1]
ROLES = ("Builder", "Test writer", "Reviewer", "Pass")
LOOP = "## Loop\nTest command: true\nLoop branch: loop/main\n"
APPROVE = test_flow.APPROVE


def read(extra):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "loop.json").write_text(settings_json("## Loop\nTest command: t\n" + extra), encoding="utf-8")
        return common.read_settings(d)


def real_codex_calls(calls):
    """Session calls only: the inspection commands (--version, features, --help) are not sessions."""
    return [c for c in calls if c["argv"][:1] == ["exec"] and "--help" not in c["argv"]]


class SettingsTest(unittest.TestCase):
    def test_every_role_accepts_codex(self):
        for role in ROLES:
            self.assertEqual(tuple(read("%s: codex gpt-6\n" % role)[role]), ("codex", "gpt-6"), role)

    def test_an_unknown_agent_is_still_refused_naming_both_agents(self):
        with self.assertRaises(common.SettingsError) as cm:
            read("Reviewer: gemini pro\n")
        for word in ("Reviewer", "claude", "codex"):
            self.assertIn(word, str(cm.exception))


class LimitTest(FakeCodexCheck):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {"loop.json": settings_json(LOOP)})

    def run_session(self):
        return session.run("builder", "do it", self.work, "gpt-6", self.work, 7, agent="codex")

    def test_a_limit_reply_waits_thirty_minutes_then_resumes_the_same_thread(self):
        self.codex([{"error": "You've hit your usage limit. Try again later.", "thread": "t-1"},
                    {"reply": "finished"}])
        with mock.patch.object(common, "sleep") as sleep:
            text, sid = self.run_session()
        self.assertEqual(text, "finished")
        sleep.assert_called_once_with(1800)
        calls = real_codex_calls(self.codex_calls())
        self.assertEqual(len(calls), 2)
        self.assertNotIn("resume", calls[0]["argv"])
        self.assertEqual(calls[1]["argv"][:2], ["exec", "resume"])

    def test_a_limit_with_a_reset_time_waits_until_then(self):
        reset = int(time.time()) + 600
        self.codex([{"error": "usage limit reached|%d" % reset}, {"reply": "ok"}])
        with mock.patch.object(common, "sleep") as sleep:
            self.run_session()
        self.assertTrue(500 <= sleep.call_args[0][0] <= 600, sleep.call_args)


class SetupCheckTest(test_setup.SetupTest, FakeCodexCheck):
    def project(self, extra="Builder: codex gpt-6\n"):
        self.repo(LOOP + extra)
        self.fresh()

    def refuses(self, *words):
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 1, text)
        self.assertIn("refused", text)
        for word in words:
            self.assertIn(word, text)
        self.assertEqual(self.writes(), [])
        self.assertEqual(real_codex_calls(self.codex_calls()), [])

    def test_a_working_codex_passes(self):
        self.project()
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 0, text)

    def test_no_codex_command_is_refused_by_name(self):
        self.project()
        self.without_codex()
        self.refuses("Builder", "codex")

    def test_no_hooks_feature_is_refused_by_name(self):
        self.project()
        os.environ["FAKE_CODEX_NO_HOOKS"] = "1"
        self.refuses("Builder", "hooks")

    def test_each_missing_flag_is_refused_by_name(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                self.project()
                os.environ["FAKE_CODEX_NO_FLAG"] = flag
                self.refuses("Builder", flag)

    def test_the_check_runs_for_any_role_set_to_codex(self):
        for role in ("Test writer", "Reviewer", "Pass"):
            with self.subTest(role=role):
                self.project("%s: codex gpt-6\n" % role)
                os.environ["FAKE_CODEX_NO_HOOKS"] = "1"
                self.refuses(role, "hooks")

    def test_a_project_with_no_codex_role_does_not_need_codex(self):
        self.project(extra="")
        self.without_codex()
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 0, text)


class StartCheckTest(FakeCodexCheck):
    def start(self, env=None):
        self.work, _ = make_repo(self.tmp, {"loop.json": settings_json(LOOP + "Reviewer: codex gpt-6\n")})
        return subprocess.run([str(KIT / "bin" / "loop"), "run"], cwd=self.work, capture_output=True, text=True,
                              env=dict(os.environ, **(env or {})))

    def refused(self, r, *words):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refused", r.stdout)
        for word in words:
            self.assertIn(word, r.stdout)
        self.assertEqual(real_codex_calls(self.codex_calls()), [])

    def test_the_loop_refuses_a_missing_codex_command(self):
        self.without_codex()
        self.refused(self.start(), "Reviewer", "codex")

    def test_the_loop_refuses_a_missing_hooks_feature(self):
        self.refused(self.start({"FAKE_CODEX_NO_HOOKS": "1"}), "Reviewer", "hooks")

    def test_the_loop_refuses_each_missing_flag(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                self.refused(self.start({"FAKE_CODEX_NO_FLAG": flag}), "Reviewer", flag)


class CodexBuilderBuildTest(test_flow.FlowTest, FakeCodexCheck):
    def setUp(self):
        super().setUp()
        Path(self.work, "loop.json").write_text(settings_json(test_flow.AGENTS + "Builder: codex gpt-6\n"))
        common.git(["commit", "-qam", "agents"], cwd=self.work)

    def test_a_codex_builder_and_claude_reviewer_build_and_merge(self):
        self.claude({"test-writer": [test_flow.WRITER], "reviewer": [APPROVE]})
        self.codex([{"files": {"app.py": "1\n"}, "reply": "Built.", "thread": "t-9"}])
        self.assertEqual(self.build().status, "merged")
        self.assertEqual([c["role"] for c in self.claude_calls()], ["test-writer", "reviewer"])
        calls = real_codex_calls(self.codex_calls())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["env"]["LOOP_ROLE"], "builder")
        self.assertEqual(calls[0]["env"]["LOOP_AGENT"], "codex")
        self.assertEqual(calls[0]["env"]["LOOP_LOCKED"], "tests/test_new.py")
        self.assertTrue(any("hooks" in a for a in calls[0]["argv"]))

    def test_a_codex_limit_in_the_build_waits_and_resumes(self):
        self.claude({"test-writer": [test_flow.WRITER], "reviewer": [APPROVE]})
        self.codex([{"error": "usage limit reached", "thread": "t-9"},
                    {"files": {"app.py": "1\n"}, "reply": "Built."}])
        with mock.patch.object(common, "sleep") as sleep:
            self.assertEqual(self.build().status, "merged")
        sleep.assert_called_once_with(1800)


def only_own_tests(cls):
    """Keep the base classes' fixtures and drop the tests they bring along."""
    for name in dir(cls):
        if name.startswith("test_") and name not in vars(cls):
            setattr(cls, name, None)  # the loader skips what is not callable


for _cls in (SetupCheckTest, CodexBuilderBuildTest):
    only_own_tests(_cls)


class DocsTest(unittest.TestCase):
    def test_readme_and_design_describe_codex_and_the_check_at_start(self):
        for path in (KIT / "README.md", KIT.parent / "docs" / "DESIGN.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Codex", text, path.name)
            self.assertIn("hooks", text, path.name)
            self.assertRegex(text, r"(?i)usage limit", path.name)


if __name__ == "__main__":
    unittest.main()
