"""A project chooses the Codex model and reasoning effort."""
from __future__ import annotations

from helpers import Project, git

# isort: split

import unittest
from unittest import mock

import agents
import gate
import loopkit
from loopkit import Refused


def codex_args(folder, **options):
    with mock.patch.object(agents, "subprocess") as process:
        agents.start_session("codex", "brief", folder, role=options.pop("role", "builder"),
                             **options)
    return process.Popen.call_args.args[0]


def claude_args(folder, **options):
    with mock.patch.object(agents, "subprocess") as process:
        agents.start_session("claude", "brief", folder, role="builder", **options)
    return process.Popen.call_args.args[0]


class AgentModelTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")

    def setting(self, lines):
        agents_md = self.p.root / "AGENTS.md"
        agents_md.write_text(agents_md.read_text() + lines)
        git(self.p.root, "commit", "--quiet", "-am", "Agent settings")
        git(self.p.root, "push", "--quiet", "origin", "main")

    def test_agent_sessions_get_no_standard_input(self):
        # Codex reads standard input to its end when it is not a terminal, so an
        # inherited input that never closes made the judge-writer wait for ever.
        for backend in ("codex", "claude"):
            with self.subTest(backend=backend), mock.patch.object(agents, "subprocess") as process:
                agents.start_session(backend, "brief", self.p.root, role="judge-writer")
                self.assertIs(process.Popen.call_args.kwargs.get("stdin"), process.DEVNULL)

    def test_names_are_checked_and_effort_is_lowercased(self):
        for model in ("gpt-6-luna", "gpt-5.6-luna", "o3", "gpt-oss:20b", "org/model"):
            with self.subTest(model=model):
                self.assertEqual(loopkit.agent_options(model, "High"), (model, "high"))
        self.assertEqual(loopkit.agent_options("", ""), ("", ""))
        for model, effort in (("-m", ""), ("gpt 6", ""), ("x", "very high"), ("x", 'h"igh')):
            with self.subTest(model=model, effort=effort), self.assertRaises(Refused):
                loopkit.agent_options(model, effort)

    def test_every_codex_role_gets_exactly_the_model_and_effort_before_the_prompt(self):
        for role in ("builder", "reviewer", "critic", "probe"):
            with self.subTest(role=role):
                args = codex_args(self.p.root, role=role, model="gpt-6-luna", effort="high")
                self.assertEqual(args.count("-m"), 1)
                self.assertEqual(args[args.index("-m") + 1], "gpt-6-luna")
                self.assertIn('model_reasoning_effort="high"', args)
                self.assertLess(args.index("-m"), args.index("--cd"))
                self.assertEqual(args[-1].split("\n")[0], "brief")

    def test_without_the_settings_the_codex_command_is_unchanged(self):
        args = codex_args(self.p.root)
        self.assertNotIn("-m", args)
        self.assertFalse(any("model_reasoning_effort" in arg for arg in args))
        self.assertEqual(codex_args(self.p.root, model="", effort=""), args)

    def test_sessions_without_a_ready_record_read_main(self):
        self.setting("Agent model: gpt-6-luna\nAgent effort: High\n")
        args = codex_args(self.p.root, role="probe")
        self.assertEqual(args[args.index("-m") + 1], "gpt-6-luna")
        self.assertIn('model_reasoning_effort="high"', args)

    def test_the_claude_command_is_unchanged(self):
        self.setting("Agent model: gpt-6-luna\nAgent effort: high\n")
        self.assertEqual(claude_args(self.p.root, model="gpt-6-luna", effort="high"),
                         claude_args(self.p.root))

    def test_ready_freezes_the_settings_and_omits_them_when_unset(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        record = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertNotIn("agent_model", record)
        self.assertNotIn("agent_effort", record)
        self.setting("Agent: codex\nAgent model: gpt-6-luna\nAgent effort: High\n")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        record = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual((record["agent_model"], record["agent_effort"]), ("gpt-6-luna", "high"))

    def test_ready_refuses_a_bad_setting(self):
        self.setting("Agent model: gpt 6\n")
        n = self.p.piece()
        with self.assertRaises(Refused) as refusal:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("is not a model name", refusal.exception.reason)

    def test_the_builder_and_reviewers_use_the_frozen_record(self):
        import review
        import run
        with mock.patch.object(run, "run_session", return_value="ok") as session:
            run.build_once(self.p.root, "brief", [], self.p.root / "log", backend="codex",
                           model="gpt-6-luna", effort="high")
        self.assertEqual((session.call_args.kwargs["model"], session.call_args.kwargs["effort"]),
                         ("gpt-6-luna", "high"))
        with mock.patch.object(review, "run_session", return_value="ok") as session:
            review._review_session(self.p.root, "brief", self.p.root / "log", [], 60,
                                   backend="codex", model="gpt-6-luna", effort="high")
        self.assertEqual(session.call_args.kwargs["model"], "gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
