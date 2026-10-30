"""gate.py sync re-renders the run page, so a change made outside a run shows on it."""
from __future__ import annotations

import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import dashboard
import gate
import gate_cli


class Api:
    """The gate as sync sees it: one merged piece moves from approval to done."""

    def __init__(self, gh, root, lines):
        self.gh, self.root, self.lines = gh, root, lines

    def sync(self, gh, root):
        if self.lines:
            gh.set_labels(1, ["state:done"], ["state:approval"])
            gate.run_event(root, "done", 1, "done")
        return self.lines


class SyncRendersPageTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()
        self.gh.create_issue("Merged piece", "body", ["state:approval"])
        self.page = self.root / ".loop" / "dashboard.html"

    def sync(self, lines=("1: moved to done",)):
        out, err = io.StringIO(), io.StringIO()
        with patch("gate_cli.repo_root", return_value=self.root), \
                patch("gate_cli.GitHub", return_value=self.gh), \
                redirect_stdout(out), redirect_stderr(err):
            code = gate_cli.main(["sync"], api=Api(self.gh, self.root, list(lines)))
        return code, out.getvalue(), err.getvalue()

    def start_run(self):
        gate.run_event(self.root, "run-start", reason="started")
        gate.run_event(self.root, "submit", 1, "approval", 1, "submit")
        gate.run_event(self.root, "run-stop", reason="ended")

    def test_D1_sync_rewrites_the_page_with_the_state_from_github(self):
        self.start_run()
        dashboard.render(self.root, self.gh)
        self.assertIn("approval", self.page.read_text())
        self.assertEqual(self.sync()[0], 0)
        text = self.page.read_text()
        self.assertRegex(text, r"<td>1</td><td>Merged piece</td><td>done</td>")
        self.assertNotIn("disagree", text)

    def test_D2_page_shows_the_utc_time_it_was_written(self):
        self.start_run()
        dashboard.render(self.root, self.gh)
        self.assertRegex(self.page.read_text(), r"Written \d{4}-\d\d-\d\d \d\d:\d\d UTC")

    def test_D3_a_failed_render_warns_and_keeps_the_result_and_exit_status(self):
        self.start_run()
        with patch.object(dashboard, "render", side_effect=OSError("disk full")):
            code, out, err = self.sync()
        self.assertEqual(code, 0)
        self.assertIn("1: moved to done", out)
        self.assertIn("warning: could not write .loop/dashboard.html", err)

    def test_D4_without_an_event_file_sync_writes_no_page(self):
        code, out, err = self.sync(lines=())
        self.assertEqual(code, 0)
        self.assertFalse(self.page.exists())
        self.assertNotIn("warning", err)

    def test_D5_sync_prints_the_same_result_lines_as_before(self):
        self.start_run()
        self.assertEqual(self.sync(("1: moved to done", "final pull request refreshed"))[1],
                         "1: moved to done\nfinal pull request refreshed\n")
        self.start_run()
        self.assertEqual(self.sync(())[1], "ok: nothing merged since the last sync\n")


if __name__ == "__main__":
    unittest.main()
