"""A local page shows the current run without fetching data in the browser."""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import gate
import run
import run_cli


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.rows = []
        self.tags = []
        self.text = []
        self.row = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "tr":
            self.row = []

    def handle_endtag(self, tag):
        if tag == "tr":
            self.rows.append(" ".join(self.row))
            self.row = None

    def handle_data(self, data):
        self.text.append(data)
        if self.row is not None:
            self.row.append(data)


class RunDashboardTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()
        self.path = self.root / ".loop" / "dashboard.html"

    def event(self, name, piece=None, state="", attempt=0, reason=""):
        gate.run_event(self.root, name, piece, state, attempt, reason)

    def render(self, pieces=()):
        self.assertIsNotNone(importlib.util.find_spec("dashboard"),
                             "the local dashboard renderer is missing")
        import dashboard
        dashboard.render(self.root, self.gh, pieces)
        self.assertTrue(self.path.is_file(), "the run must write .loop/dashboard.html")
        return self.path.read_text(encoding="utf-8")

    def test_D1_lists_last_state_attempt_time_and_pull_request(self):
        a = self.gh.create_issue("Add", "", ["state:approval"])
        b = self.gh.create_issue("Format", "", ["state:shaping"])
        self.gh.prs[f"piece/{a}"] = {"url": "https://example.test/pull/1"}
        self.event("run-start")
        self.event("claim", a, "building")
        self.event("submit", a, "approval", 2)
        self.event("give-back", b, "shaping", 3, "builder-failed")
        self.event("run-stop")
        page = Page(self.render())
        self.assertEqual(len(page.rows), 3)
        self.assertIn("approval 2", page.rows[1])
        self.assertIn("shaping 3", page.rows[2])
        self.assertIn("https://example.test/pull/1", self.path.read_text())
        self.assertIn("Finished", page.text)
        self.assertIn("run-stop", " ".join(page.text))
        self.assertRegex(page.rows[1], r"\d{4}-\d\d-\d\dT")

    def test_D1_current_run_includes_unstarted_pieces_and_excludes_old_runs(self):
        old = self.gh.create_issue("Old", "", ["state:done"])
        waiting = self.gh.create_issue("Waiting", "", ["state:ready"])
        self.event("submit", old, "approval", 1)
        self.event("run-start")
        page = Page(self.render([waiting]))
        self.assertEqual(len(page.rows), 2)
        self.assertIn("Waiting ready 0", page.rows[1])
        self.assertNotIn("Old", " ".join(page.text))
        self.assertIn("Running", page.text)

    def test_D2_page_has_embedded_data_and_refresh_without_network_resources(self):
        self.event("run-start")
        page = Page(self.render())
        self.assertTrue(any(tag == "meta" and attrs.get("http-equiv") == "refresh"
                            for tag, attrs in page.tags))
        self.assertFalse(any(tag in ("script", "iframe", "link", "img", "form")
                             or "src" in attrs for tag, attrs in page.tags))
        self.assertIn("run-start", " ".join(page.text))

    def test_D3_escapes_issue_and_reason_and_refuses_executable_links(self):
        number = self.gh.create_issue('<script>alert("title")</script>', "",
                                      ["state:shaping"])
        self.gh.prs[f"piece/{number}"] = {"url": "javascript:alert(1)"}
        self.event("run-start")
        self.event("give-back", number, "shaping", 1, '<img src=x onerror="bad">')
        text = self.render()
        page = Page(text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("&lt;img", text)
        self.assertFalse(any(tag in ("script", "img") for tag, _ in page.tags))
        self.assertNotIn("javascript:", text)

    def test_D4_disagreement_is_visible_and_does_not_replace_recorded_state(self):
        number = self.gh.create_issue("Add", "", ["state:ready"])
        self.event("run-start")
        self.event("claim", number, "building", 1)
        page = Page(self.render())
        text = " ".join(page.text)
        self.assertIn("disagree", text)
        self.assertIn("GitHub", text)
        self.assertIn("ready", text)
        self.assertIn("building 1", page.rows[1])

    def test_D4_offline_github_still_renders_local_state_with_notice(self):
        self.event("run-start")
        self.event("claim", 1, "building", 1)
        with patch.object(self.gh, "issue", side_effect=RuntimeError("offline")):
            text = " ".join(Page(self.render()).text)
        self.assertIn("building", text)
        self.assertIn("could not check GitHub", text)

    def test_D5_run_prints_path_and_renders_after_each_event(self):
        number = self.gh.create_issue("Add", "", ["state:ready"])
        output = io.StringIO()

        def build(*args):
            self.assertTrue(self.path.is_file(), "the run must render its first event")
            self.assertIn("Running", self.path.read_text())
            with patch.object(gate, "release_worktree"):
                gate.move(self.gh, self.root, number, "shaping", reason="stop",
                          reason_type="stopped", attempts=2)
            self.assertIn("shaping 2", " ".join(Page(self.path.read_text()).text))
            return "back to shaping"

        with ExitStack() as stack:
            for target, name, replacement in (
                (run_cli, "repo_root", self.root), (run_cli, "GitHub", self.gh),
                (run, "recover_building", []), (run, "cleanup_interrupted_reviews", []),
                (run, "ready_pieces", [number]),
            ):
                stack.enter_context(patch.object(target, name, return_value=replacement))
            stack.enter_context(patch.object(run_cli.signal, "signal"))
            stack.enter_context(patch.object(gate, "ignore_loop_folder"))
            stack.enter_context(patch.object(gate, "sync"))
            stack.enter_context(patch.object(run, "build_piece", side_effect=build))
            stack.enter_context(redirect_stdout(output))
            self.assertEqual(run.main(["--attended"]), 1)
        self.assertIn(str(self.path), output.getvalue())
        self.assertTrue(self.path.is_file(), "the run must render its last event")
        self.assertIn("Finished", self.path.read_text())
        self.assertFalse(run.lock_path(self.root).exists())

    def test_D5_skill_reports_page_path(self):
        skill = Path(__file__).resolve().parents[2] / "kit" / "skills" / "run" / "SKILL.md"
        self.assertIn(".loop/dashboard.html", skill.read_text())


if __name__ == "__main__":
    unittest.main()
