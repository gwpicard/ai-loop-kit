"""Frozen-file refusals and evidence from builder attempts."""
from __future__ import annotations

import json
import os
import stat
import unittest
from unittest.mock import patch

from helpers import Project, git

# Helpers puts the kit scripts on sys.path before these imports.
# isort: split
import gate
import run
from test_run import FAKE_CLAUDE


class FrozenEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        (self.p.root / ".loop").mkdir()
        self.p.loop_section("true")
        self.n = self.p.piece()
        gate.move(self.p.gh, self.p.root, self.n, "ready")
        self.ready = gate.last_record(self.p.gh.comments(self.n), "ready")

    def merge_new_settings(self):
        self.p.loop_section("printf newer-main")
        folder = run.worktree(self.p.root, self.n)
        git(folder, "merge", "--quiet", "--no-edit", "main")
        return folder

    def test_merged_main_settings_are_stale_frozen_files(self):
        folder = self.merge_new_settings()
        passed, reason = gate.judge(folder, self.ready)
        self.assertFalse(passed)
        self.assertIn("main changed the frozen judge bar: AGENTS.md", reason)
        self.assertNotIn("the loop settings changed", reason)

    def test_inherited_settings_do_not_hide_a_builder_judge_edit(self):
        folder = self.merge_new_settings()
        (folder / "judge_add.py").write_text("print('forged pass')\n")
        passed, reason = gate.judge(folder, self.ready)
        self.assertFalse(passed)
        self.assertIn("main changed the frozen judge bar: AGENTS.md", reason)
        self.assertIn("the build changed frozen files: judge_add.py", reason)

    def test_deleted_frozen_file_is_named_without_blame_on_settings(self):
        folder = run.worktree(self.p.root, self.n)
        (folder / "README.md").unlink()
        passed, reason = gate.judge(folder, self.ready)
        self.assertFalse(passed)
        self.assertIn("the build changed frozen files: README.md", reason)
        self.assertNotIn("AGENTS.md", reason)

    def test_deleted_shaping_judge_is_a_build_edit(self):
        folder = run.worktree(self.p.root, self.n)
        (folder / "judge_add.py").unlink()
        for committed in (False, True):
            with self.subTest(committed=committed):
                if committed:
                    git(folder, "add", "judge_add.py")
                    git(folder, "commit", "--quiet", "-m", "Delete the shaped judge")
                passed, reason = gate.judge(folder, self.ready)
                self.assertFalse(passed)
                self.assertEqual(reason, "the build changed frozen files: judge_add.py")

    def test_deletion_inherited_from_main_is_named_as_inherited(self):
        (self.p.root / "README.md").unlink()
        git(self.p.root, "add", "README.md")
        git(self.p.root, "commit", "--quiet", "-m", "Remove old readme")
        git(self.p.root, "push", "--quiet", "origin", "main")
        folder = run.worktree(self.p.root, self.n)
        git(folder, "merge", "--quiet", "--no-edit", "main")
        passed, reason = gate.judge(folder, self.ready)
        self.assertFalse(passed)
        self.assertEqual(reason, "main changed the frozen judge bar: README.md")

    def test_changed_judge_is_restored_before_next_attempt(self):
        fake = self.p.root / ".loop" / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        modes = iter(("cheat", "good"))
        build_once = run.build_once

        def build_in_order(*args, **kwargs):
            with patch.dict(os.environ, {"FAKE_MODE": next(modes)}):
                return build_once(*args, **kwargs)

        with patch.dict(os.environ, {"LOOP_CLAUDE": str(fake)}), \
                patch("run.build_once", side_effect=build_in_order) as builder:
            result = run.build_piece(self.p.gh, self.p.root, self.n, 2)
        self.assertEqual(builder.call_count, 2)
        self.assertIn("pull request ready", result)
        restored = git(self.p.root, "show", f"piece/{self.n}:judge_add.py")
        original = git(self.p.root, "show", f"{self.ready['commit']}:judge_add.py")
        self.assertEqual(restored, original)

    def test_run_returns_stale_settings_before_starting_builder(self):
        self.p.loop_section("printf newer-main")
        with patch("run.build_once") as builder:
            result = run.build_piece(self.p.gh, self.p.root, self.n, 1)
        builder.assert_not_called()
        self.assertIn("main changed the frozen judge bar: AGENTS.md", result)
        record = gate.last_record(self.p.gh.comments(self.n), "give-back")
        self.assertEqual(record["cause"], "stale-after-main")
        self.assertEqual(record["attempts"], 0)

    def test_worktree_is_printed_before_builder_starts(self):
        fake = self.p.root / ".loop" / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        messages = []
        build_once = run.build_once

        def build_with_path(*args, **kwargs):
            self.assertTrue(any(str(args[0]) in message for message in messages),
                            f"worktree missing from run output: {messages}")
            return build_once(*args, **kwargs)

        with patch.dict(os.environ, {"LOOP_CLAUDE": str(fake), "FAKE_MODE": "good"}), \
                patch("run.log", side_effect=messages.append), \
                patch("run.build_once", side_effect=build_with_path):
            result = run.build_piece(self.p.gh, self.p.root, self.n, 1)
        self.assertIn("pull request ready", result)

    def test_codex_attempt_keeps_tool_events_and_appends_retry(self):
        fake = self.p.root / ".loop" / "fake-codex"
        events = [
            {"type": "item.started", "item": {
                "id": "tool_1", "type": "command_execution", "command": "git status"}},
            {"type": "item.completed", "item": {
                "id": "tool_1", "type": "command_execution", "command": "git status",
                "exit_code": 1, "aggregated_output": "permission denied"}},
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": "The command was refused."}},
        ]
        payload = "\n".join(json.dumps(event) for event in events) + "\n"
        fake.write_text("#!/usr/bin/env python3\n"
                        f"import sys\nsys.stdout.write({payload!r})\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        logfile = self.p.root / ".loop" / "attempt.log"
        eventfile = logfile.with_suffix(".jsonl")
        with patch.dict(os.environ, {"LOOP_CODEX": str(fake)}):
            for append in (False, True):
                status = run.build_once(self.p.root, "brief", [], logfile,
                                        backend="codex", append_log=append)
                self.assertEqual(status, "")
                self.assertTrue(eventfile.is_file(), "structured attempt events are missing")
                actual = [json.loads(line) for line in eventfile.read_text().splitlines()]
                self.assertEqual(actual, events * (2 if append else 1))
        self.assertIn("The command was refused.", logfile.read_text())
        self.assertNotIn("command_execution", logfile.read_text())
