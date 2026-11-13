"""The live dashboard server is gone; macOS notifications are on by default for a walk-away run."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import gate
import notifications
import run
import run_cli

REPO = Path(__file__).resolve().parents[2]
KIT = REPO / "kit"


class RetiredTest(unittest.TestCase):
    def test_D10_the_server_its_helper_and_its_page_are_deleted(self):
        for name in ("dashboard_server.py", "dashboard_run.py", "dashboard_page"):
            self.assertFalse((KIT / "scripts" / name).exists(), name)

    def test_D10_notifications_keeps_classify_deliver_and_the_watcher_only(self):
        for name in ("classify", "deliver", "EventWatcher", "read_preferences"):
            self.assertTrue(hasattr(notifications, name), name)
        for name in ("stuck", "current", "save_preferences", "deliver_stuck"):
            self.assertFalse(hasattr(notifications, name), name)

    def test_D11_no_document_names_the_server_and_the_run_skill_gives_the_page_path(self):
        skill = (KIT / "skills" / "run" / "SKILL.md").read_text()
        for text in (skill, (REPO / "README.md").read_text(),
                     (REPO / "docs" / "DESIGN.md").read_text()):
            self.assertNotIn("dashboard_server.py", text)
        self.assertIn(".loop/dashboard.html", skill)


class DefaultTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def save(self, text):
        (self.root / ".loop").mkdir(exist_ok=True)
        (self.root / ".loop" / "preferences.json").write_text(text)

    def macos(self, **options):
        try:
            found = notifications.read_preferences(self.root, **options)
        except TypeError as error:
            self.fail(f"read_preferences must accept walk_away: {error}")
        return found["notify"]["macos"]

    def test_D12_without_a_saved_value_macos_is_on_for_a_walk_away_run_only(self):
        self.assertIs(self.macos(walk_away=True), True)
        self.assertIs(self.macos(walk_away=False), False)
        self.assertIs(self.macos(), False)

    def test_D12_an_unreadable_macos_value_counts_as_not_saved(self):
        for text in ("not json", '{"notify": {"macos": "yes"}}', '{"notify": {"sound": "Glass"}}',
                     '{"notify": []}', "{}"):
            self.save(text)
            self.assertIs(self.macos(walk_away=True), True, text)
            self.assertIs(self.macos(walk_away=False), False, text)

    def test_D13_a_saved_value_wins_in_both_modes(self):
        for saved in (True, False):
            self.save(json.dumps({"notify": {"macos": saved}}))
            for walk_away in (True, False):
                self.assertIs(self.macos(walk_away=walk_away), saved, (saved, walk_away))


class RunNotifiesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()

    def run_once(self, walk_away):
        """Run with no ready pieces; return the osascript commands the run started."""
        commands = []
        real = subprocess.run

        def record(command, *args, **kwargs):
            if list(command)[0] != "osascript":
                return real(command, *args, **kwargs)
            commands.append(list(command))
            return subprocess.CompletedProcess(command, 0)

        with ExitStack() as stack:
            for target, name, replacement in (
                (run_cli, "repo_root", self.root), (run_cli, "GitHub", self.gh),
                (run_cli, "choose_mode", walk_away), (run_cli, "merges_onto_base", False),
                (run, "recover_building", []), (run, "cleanup_interrupted_reviews", []),
                (run, "ready_pieces", []),
            ):
                stack.enter_context(patch.object(target, name, return_value=replacement))
            stack.enter_context(patch.object(run_cli.signal, "signal"))
            stack.enter_context(patch.object(gate, "ignore_loop_folder"))
            stack.enter_context(patch.object(gate, "sync"))
            stack.enter_context(patch.object(run_cli.walkaway, "keep_awake"))
            stack.enter_context(patch.object(run_cli.walkaway, "write_summary"))
            stack.enter_context(patch.object(run_cli.walkaway, "post_summary"))
            stack.enter_context(patch.object(notifications.sys, "platform", "darwin"))
            stack.enter_context(patch.object(notifications.subprocess, "run", side_effect=record))
            stack.enter_context(redirect_stdout(io.StringIO()))
            run.main([])
        return [c for c in commands if c and c[0] == "osascript"]

    def save(self, text):
        (self.root / ".loop").mkdir(exist_ok=True)
        (self.root / ".loop" / "preferences.json").write_text(text)

    def test_D12_a_walk_away_run_with_no_preferences_notifies_when_it_finishes(self):
        found = self.run_once(True)
        self.assertEqual([c[-1] for c in found], ["The run finished."])

    def test_D13_macos_false_in_preferences_stops_a_walk_away_run_notifying(self):
        self.save('{"notify": {"macos": false}}')
        self.assertEqual(self.run_once(True), [])

    def test_D14_an_attended_run_with_no_preferences_never_calls_osascript(self):
        self.assertEqual(self.run_once(False), [])


if __name__ == "__main__":
    unittest.main()
