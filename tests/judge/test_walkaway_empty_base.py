"""The walk-away preflight accepts an empty base when a scaffold piece comes first."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import Project, git

# isort: split

import inspect
import os
from unittest import mock

import sandbox
import walkaway
from loopkit import STATE_PREFIX, record_text

SKIPPED = "skipped: the base branch has no tests yet; the scaffold piece adds them"
STEP = "shape and ready a scaffold piece first"
# Stands in for Codex: answer --version, otherwise drop the sandbox options and run the command.
FAKE_CODEX = ('#!/bin/sh\n[ "$1" = --version ] && { echo "codex 1"; exit 0; }\n'
              'while [ "$1" != sh ]; do shift; done\nexec "$@"\n')


class EmptyBaseTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        codex = Path(self.p.tmp.name) / "codex"
        codex.write_text(FAKE_CODEX)
        codex.chmod(0o755)
        for patcher in (mock.patch.dict(os.environ, {"LOOP_CODEX": str(codex)}),
                        mock.patch.object(walkaway.agents, "selected", return_value="codex"),
                        mock.patch.object(sandbox, "codex_probe", return_value=(True, "ok"))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def commit_test_file(self, branch="main"):
        (self.p.root / "tests").mkdir(exist_ok=True)
        (self.p.root / "tests" / "test_one.py").write_text("pass\n")
        git(self.p.root, "add", "tests")
        git(self.p.root, "commit", "--quiet", "-m", "Add a test")
        git(self.p.root, "push", "--quiet", "-u", "origin", branch)

    def ready_piece(self, kind):
        n = self.p.gh.create_issue(f"A {kind} piece", "body", [STATE_PREFIX + "ready"])
        self.p.gh.comment(n, record_text({"move": "ready", "kind": kind}, "ready"))
        return n

    def check(self, pieces, label):
        self.assertIn("pieces", inspect.signature(walkaway.preflight).parameters,
                      "preflight takes the run's pieces")
        checks = walkaway.preflight(self.p.gh, self.p.root, pieces=pieces)
        return next((c for c in checks if label in c[1]), None), checks

    def test_D1_an_empty_base_with_a_scaffold_first_passes_and_says_it_skipped(self):
        self.p.loop_section("exit 5")
        scaffold = self.ready_piece("scaffold")
        sandboxed, checks = self.check([scaffold], "inside the Codex builder sandbox")
        self.assertEqual([c for c in checks if not c[0]], [])
        self.assertIn(SKIPPED, sandboxed[1])
        baseline = next(c for c in checks if c[1].startswith("Test"))
        self.assertIn(SKIPPED, baseline[1])

    def test_D1_the_scaffold_must_be_the_piece_picked_first(self):
        self.p.loop_section("exit 5")
        feature, scaffold = self.ready_piece("feature"), self.ready_piece("scaffold")
        self.assertTrue(hasattr(walkaway, "empty_base_scaffold"))
        self.assertFalse(walkaway.empty_base_scaffold(self.p.gh, self.p.root, [feature, scaffold]))
        self.assertTrue(walkaway.empty_base_scaffold(self.p.gh, self.p.root, [scaffold, feature]))

    def test_D2_an_empty_base_with_a_feature_first_fails_with_the_next_step(self):
        self.p.loop_section("exit 5")
        feature = self.ready_piece("feature")
        _, checks = self.check([feature], "Test")
        failed = [c for c in checks if not c[0]]
        self.assertTrue(failed)
        self.assertTrue(all(c[2] == STEP for c in failed), failed)
        self.assertFalse(any(SKIPPED in c[1] for c in checks))

    def test_D3_tests_on_the_base_that_fail_still_fail_with_a_scaffold(self):
        self.p.loop_section("exit 1")
        self.commit_test_file()
        scaffold = self.ready_piece("scaffold")
        _, checks = self.check([scaffold], "Test")
        failed = [c for c in checks if not c[0]]
        self.assertTrue(failed)
        self.assertFalse(any(c[2] == STEP for c in failed))
        self.assertFalse(any(SKIPPED in c[1] for c in checks))

    def test_D4_run_walk_away_passes_the_selected_pieces_to_the_doctor(self):
        import doctor
        import run_cli
        self.assertIn("pieces", inspect.signature(doctor.doctor).parameters)
        self.p.loop_section("exit 0")
        piece = self.ready_piece("scaffold")
        with mock.patch.object(run_cli, "repo_root", return_value=self.p.root), \
             mock.patch.object(run_cli, "refresh_main"), \
             mock.patch.object(run_cli, "GitHub", return_value=self.p.gh), \
             mock.patch.object(run_cli.gate, "doctor", return_value=[]) as seen:
            run_cli.main(["--walk-away", str(piece)])
            run_cli.main(["--walk-away"])
        self.assertEqual([call.kwargs.get("pieces") for call in seen.call_args_list],
                         [[piece], [piece]])

    def test_D5_a_green_test_command_passes_without_the_skip_line(self):
        self.p.loop_section("exit 0")
        self.commit_test_file()
        checks = walkaway.preflight(self.p.gh, self.p.root)
        self.assertEqual([c for c in checks if not c[0]], [])
        self.assertFalse(any(SKIPPED in c[1] for c in checks))

    def test_D7_a_scaffold_merged_into_the_configured_base_counts(self):
        self.p.loop_section("test -f tests/test_one.py")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Base branch: loop-1\n")
        git(self.p.root, "commit", "--quiet", "-am", "Base branch")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "switch", "--quiet", "-c", "loop-1")
        self.commit_test_file("loop-1")
        git(self.p.root, "switch", "--quiet", "main")
        self.assertFalse(git(self.p.root, "ls-files", "tests"))
        feature = self.ready_piece("feature")
        _, checks = self.check([feature], "Test")
        self.assertEqual([c for c in checks if not c[0]], [])
        self.assertFalse(any(SKIPPED in c[1] for c in checks))


if __name__ == "__main__":
    unittest.main()
