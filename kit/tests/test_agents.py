import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path

from kit.tests import test_flow, test_pass, test_setup
from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo
import common
import session

ROLES = ("Builder", "Test writer", "Reviewer", "Pass")
SKILL = Path(__file__).resolve().parents[1] / "skills" / "loop" / "SKILL.md"


def read(extra):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "AGENTS.md").write_text("## Loop\nTest command: t\n" + extra, encoding="utf-8")
        return common.read_settings(d)


def model_of(call):
    argv = call["argv"]
    return argv[argv.index("--model") + 1]


class SettingsTest(unittest.TestCase):
    def test_each_role_defaults_to_claude_sonnet(self):
        s = read("")
        for role in ROLES:
            self.assertEqual(tuple(s[role]), ("claude", "sonnet"), role)

    def test_each_role_is_an_agent_and_model_pair(self):
        s = read("Builder: claude opus\nTest writer: claude haiku\nReviewer: claude fable\nPass: claude sonnet\n")
        self.assertEqual([tuple(s[r]) for r in ROLES],
                         [("claude", "opus"), ("claude", "haiku"), ("claude", "fable"), ("claude", "sonnet")])

    def test_a_value_that_is_not_two_words_names_the_line(self):
        for role in ROLES:
            for value in ("sonnet", "claude sonnet extra"):
                with self.assertRaises(common.SettingsError, msg=role + value) as cm:
                    read("%s: %s\n" % (role, value))
                self.assertIn(role, str(cm.exception))

    def test_an_unknown_agent_names_the_line_and_the_agents_supported(self):
        with self.assertRaises(common.SettingsError) as cm:
            read("Reviewer: codex gpt-6\n")
        self.assertIn("Reviewer", str(cm.exception))
        self.assertIn("codex", str(cm.exception))
        self.assertIn("claude", str(cm.exception))

    def test_builder_model_sets_builder_and_test_writer(self):
        s = read("Builder model: opus\n")
        self.assertEqual((tuple(s["Builder"]), tuple(s["Test writer"])), (("claude", "opus"),) * 2)
        self.assertEqual((tuple(s["Reviewer"]), tuple(s["Pass"])), (("claude", "sonnet"),) * 2)

    def test_reviewer_model_sets_reviewer_and_pass(self):
        s = read("Reviewer model: opus\n")
        self.assertEqual((tuple(s["Reviewer"]), tuple(s["Pass"])), (("claude", "opus"),) * 2)
        self.assertEqual((tuple(s["Builder"]), tuple(s["Test writer"])), (("claude", "sonnet"),) * 2)

    def test_a_new_line_wins_over_the_old_model_line(self):
        s = read("Builder model: opus\nBuilder: claude haiku\nReviewer model: opus\nPass: claude haiku\n")
        self.assertEqual(tuple(s["Builder"]), ("claude", "haiku"))
        self.assertEqual(tuple(s["Test writer"]), ("claude", "opus"))
        self.assertEqual(tuple(s["Pass"]), ("claude", "haiku"))
        self.assertEqual(tuple(s["Reviewer"]), ("claude", "opus"))

    def test_session_run_takes_the_agent(self):
        self.assertIn("agent", inspect.signature(session.run).parameters)


class FlowAgentsTest(test_flow.FlowTest):
    def agents(self, extra):
        (Path(self.work) / "AGENTS.md").write_text(test_flow.AGENTS + extra)
        common.git(["commit", "-qam", "agents"], cwd=self.work)

    def test_each_role_starts_with_its_own_model(self):
        self.agents("Builder: claude opus\nTest writer: claude haiku\nReviewer: claude fable\n")
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        got = {c["role"]: model_of(c) for c in self.claude_calls()}
        self.assertEqual(got, {"test-writer": "haiku", "builder": "opus", "reviewer": "fable"})

    def test_the_old_lines_still_choose_models(self):
        self.agents("Builder model: opus\nReviewer model: haiku\n")
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        got = {c["role"]: model_of(c) for c in self.claude_calls()}
        self.assertEqual(got, {"test-writer": "opus", "builder": "opus", "reviewer": "haiku"})


class PassAgentsTest(test_pass.PassTest):
    def test_the_pass_uses_its_own_model(self):
        self.repo(test_pass.plan(), extra="Pass: claude fable\nReviewer: claude haiku\n")
        self.claude({"pass": [test_pass.NONE] * 12})
        self.run_pass()
        models = {model_of(c) for c in self.claude_calls()}
        self.assertEqual(models, {"fable"})


class SetupAgentsTest(test_setup.SetupTest):
    def test_setup_prints_one_line_per_role(self):
        self.repo("## Loop\nTest command: true\nBuilder: claude opus\nReviewer model: haiku\n")
        self.fresh()
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 0, text)
        lines = text.splitlines()
        for line in ("Builder: claude opus", "Test writer: claude sonnet",
                     "Reviewer: claude haiku", "Pass: claude haiku"):
            self.assertIn(line, lines)

    def test_setup_refuses_an_unknown_agent(self):
        self.repo("## Loop\nTest command: true\nBuilder: codex gpt-6\n")
        self.fresh()
        code, text = test_setup.run(self.work)
        self.assertEqual(code, 1)
        self.assertIn("refused", text)
        self.assertIn("Builder", text)
        self.assertEqual(self.writes(), [])


def only_own_tests(cls):
    """Keep the base class's fixtures and drop the tests it brings along."""
    for name in dir(cls):
        if name.startswith("test_") and name not in vars(cls):
            setattr(cls, name, None)  # the loader skips what is not callable


for _cls in (FlowAgentsTest, PassAgentsTest, SetupAgentsTest):
    only_own_tests(_cls)


class SkillTest(unittest.TestCase):
    def test_the_loop_skill_confirms_the_four_lines_before_the_start(self):
        text = SKILL.read_text(encoding="utf-8")
        for line in ("Builder:", "Test writer:", "Reviewer:", "Pass:"):
            self.assertIn(line, text)
        self.assertIn("AGENTS.md", text)


if __name__ == "__main__":
    unittest.main()
