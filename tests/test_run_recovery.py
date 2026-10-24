"""Conflict retries retain the existing gate checks and stop on refusal."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import call, patch

from helpers import Project

# Helpers adds the kit scripts to sys.path before these imports.
# isort: split
import gate
import run
import run_cli
from loopkit import Refused


class ConflictRetryTest(unittest.TestCase):
    def test_cli_refusal_releases_lock_and_does_not_build(self):
        project = Project()
        try:
            errors = io.StringIO()
            with patch.object(run_cli, "repo_root", return_value=project.root), \
                    patch.object(run_cli, "GitHub", return_value=project.gh), \
                    patch.object(run_cli.signal, "signal"), \
                    patch.object(run_cli, "retry_conflict",
                                 side_effect=Refused("bar changed", "shape again")), \
                    patch.object(run, "build_piece") as build, redirect_stderr(errors):
                status = run.main(["--retry-conflict", "1"])
            self.assertEqual(status, 2)
            self.assertIn("next: shape again", errors.getvalue())
            self.assertFalse(run.lock_path(project.root).exists())
            build.assert_not_called()
        finally:
            project.close()

    def test_cli_retries_only_the_selected_piece(self):
        project = Project()
        try:
            number = project.piece()
            gate.move(project.gh, project.root, number, "ready")
            project.gh.set_labels(number, ["state:approval"], ["state:ready"])
            with patch.object(run_cli, "repo_root", return_value=project.root), \
                    patch.object(run_cli, "GitHub", return_value=project.gh), \
                    patch.object(run_cli.signal, "signal"), \
                    patch.object(run, "build_piece", return_value="retry started") as build, \
                    redirect_stdout(io.StringIO()):
                run.main(["--retry-conflict", str(number)])
            self.assertEqual(build.call_count, 1)
            self.assertEqual(build.call_args.args[2], number)
            self.assertEqual(gate.state_of(project.gh.issue(number)), "ready")
            self.assertFalse(run.lock_path(project.root).exists())
        finally:
            project.close()

    def test_retry_uses_typed_handback_before_ready(self):
        with patch.object(gate, "move") as move:
            run_cli.retry_conflict("github", "root", 1)
        self.assertEqual(move.call_args_list, [
            call("github", "root", 1, "shaping", reason_type="conflict",
                 reason="conflicts with the base branch"),
            call("github", "root", 1, "ready"),
        ])

    def test_refused_handback_does_not_try_ready(self):
        with patch.object(gate, "move", side_effect=Refused("refused", "check evidence")) as move, \
                self.assertRaises(Refused):
            run_cli.retry_conflict("github", "root", 1)
        self.assertEqual(move.call_count, 1)

    def test_refused_ready_leaves_the_piece_in_shaping(self):
        project = Project()
        try:
            number = project.piece()
            gate.move(project.gh, project.root, number, "ready")
            project.gh.set_labels(number, ["state:approval"], ["state:ready"])
            with patch.object(gate, "check_ready",
                              side_effect=Refused("bar changed", "shape again")), \
                    self.assertRaises(Refused):
                run_cli.retry_conflict(project.gh, project.root, number)
            self.assertEqual(gate.state_of(project.gh.issue(number)), "shaping")
        finally:
            project.close()


if __name__ == "__main__":
    unittest.main()
