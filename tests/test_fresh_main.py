"""Settings merged on GitHub are seen at once: ready, doctor and the run fetch main first."""
from __future__ import annotations

from helpers import Project, git

# isort: split

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import doctor
import gate
import gate_cli
import loopkit
import run
import run_cli


class FreshMainTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")

    def merge_on_github(self, line):
        """Push a loop setting and a trip branch from another clone, as a merge would."""
        other = self.p.root.parent / "other-clone"
        git(self.p.root.parent, "clone", "--quiet", str(self.p.remote), str(other))
        git(other, "config", "user.email", "test@example.invalid")
        git(other, "config", "user.name", "Test")
        agents = other / "AGENTS.md"
        agents.write_text(agents.read_text() + line + "\n")
        git(other, "commit", "--quiet", "-am", "Merged on GitHub")
        git(other, "switch", "--quiet", "-c", "trip")
        (other / "trip.txt").write_text("only on trip\n")
        git(other, "add", "trip.txt")
        git(other, "commit", "--quiet", "-m", "Work on trip")
        git(other, "push", "--quiet", "origin", "main", "trip")
        return git(other, "rev-parse", "trip")

    def test_ready_sees_a_setting_merged_after_the_last_fetch(self):
        n = self.p.piece()
        trip = self.merge_on_github("Base branch: trip")
        self.assertEqual(loopkit.base_branch(self.p.root), "main")  # the local copy is stale
        with patch.object(gate_cli, "repo_root", return_value=self.p.root), \
                patch.object(gate_cli, "GitHub", return_value=self.p.gh), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(gate_cli.main(["move", str(n), "ready"]), 0)
        record = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual((record["base"], record["main"]), ("trip", trip))

    def test_doctor_reads_the_fresh_setting(self):
        self.merge_on_github("Base branch: trip")
        checks = doctor.doctor(self.p.gh, self.p.root)
        self.assertTrue(any(what == "trip has a commit on origin" for _, what, _ in checks))

    def test_the_run_fetches_main_before_it_reads_settings(self):
        self.merge_on_github("Base branch: trip")
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.p.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", return_value=[]), \
                redirect_stdout(io.StringIO()):
            run.main(["--attended"])
        self.assertEqual(loopkit.base_branch(self.p.root), "trip")

    def test_a_failed_fetch_warns_and_no_remote_is_quiet(self):
        git(self.p.root, "remote", "set-url", "origin", str(self.p.root.parent / "gone.git"))
        errors = io.StringIO()
        with redirect_stderr(errors):
            loopkit.refresh_main(self.p.root)
        self.assertIn("could not fetch main from origin", errors.getvalue())
        git(self.p.root, "remote", "remove", "origin")
        errors = io.StringIO()
        with redirect_stderr(errors):
            loopkit.refresh_main(self.p.root)
        self.assertEqual(errors.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
