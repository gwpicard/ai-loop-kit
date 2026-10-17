"""Project environments, Prepare and setup diagnostics."""
from __future__ import annotations

from helpers import SPEC, git

# isort: split

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import doctor
import gate
import loopkit
from loop_fixtures import GateFixture
from loopkit import Refused, command_env, run_judge


class GateTest(GateFixture, unittest.TestCase):
    def test_command_environment_uses_frozen_protected_paths(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Protected paths: src/untrusted\n")
        env = command_env(self.p.root, protected_paths=["src/private"])
        self.assertEqual(env["LOOP_PROTECTED_PATHS"], "src/private")

    def test_fresh_worktree_honours_path_override_without_project_venv(self):
        project_venv = self.p.root / ".venv"
        project_bin = project_venv / "bin"
        project_bin.mkdir(parents=True)
        project_python = project_bin / "python3"
        project_python.write_text("#!/bin/sh\necho from-project-venv\n")
        project_python.chmod(0o755)
        override_bin = Path(self.p.tmp.name) / "override" / "bin"
        override_bin.mkdir(parents=True)
        override_python = override_bin / "python3"
        override_python.write_text("#!/bin/sh\necho from-path-override\n")
        override_python.chmod(0o755)
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        inherited_path = os.pathsep.join(
            [str(project_bin), str(override_bin), os.environ.get("PATH", "")])
        from loopkit import run_judge
        with patch.dict(os.environ, {"PATH": inherited_path,
                                     "VIRTUAL_ENV": str(project_venv)}):
            env = command_env(worktree)
            code, out = run_judge(worktree, "python3 --version")
        self.assertEqual(code, 0)
        self.assertIn("from-path-override", out)
        self.assertNotIn(str(project_bin), env["PATH"].split(os.pathsep))
        self.assertNotIn("VIRTUAL_ENV", env)

    def test_fresh_worktree_uses_system_path_when_caller_path_is_empty(self):
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        with patch("loopkit.project_root", return_value=self.p.root), \
                patch.dict(os.environ, {"PATH": "", "VIRTUAL_ENV": "/project/.venv"}):
            env = command_env(worktree)
        self.assertEqual(env["PATH"], os.defpath)
        self.assertNotIn("VIRTUAL_ENV", env)

    def test_fresh_worktree_venv_precedes_project_venv(self):
        project_bin = self.p.root / ".venv" / "bin"
        project_bin.mkdir(parents=True)
        project_python = project_bin / "python3"
        project_python.write_text("#!/bin/sh\necho from-project-venv\n")
        project_python.chmod(0o755)
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        fresh_bin = worktree / ".venv" / "bin"
        fresh_bin.mkdir(parents=True)
        fresh_python = fresh_bin / "python3"
        fresh_python.write_text("#!/bin/sh\necho from-fresh-venv\n")
        fresh_python.chmod(0o755)
        inherited_path = os.pathsep.join([str(project_bin), os.environ.get("PATH", "")])
        with patch.dict(os.environ, {"PATH": inherited_path,
                                     "VIRTUAL_ENV": str(self.p.root / ".venv")}):
            env = command_env(worktree)
            code, out = run_judge(worktree, "python3 --version")
        self.assertEqual(code, 0)
        self.assertIn("from-fresh-venv", out)
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(fresh_bin.resolve()))
        self.assertEqual(env["VIRTUAL_ENV"], str((worktree / ".venv").resolve()))
        self.assertNotIn(str(project_bin), env["PATH"].split(os.pathsep))

    def test_prepare_runs_in_the_fresh_copy_before_keep_and_judge(self):
        self.p.loop_section("true", prepare="touch prepared.txt")
        keep_spec = SPEC.replace("Files:", "Keep: `test -f prepared.txt`\nFiles:")
        n = self.p.piece(spec=keep_spec)
        self.ready(n)  # keep would fail without the Prepare step
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_a_failing_prepare_refuses_ready(self):
        self.p.loop_section("true", prepare="exit 3")
        n = self.p.piece()
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("Prepare command fails", r.exception.reason)

    def test_scaffold_ready_does_not_run_prepare_on_main(self):
        self.p.loop_section("true", prepare="test -f pyproject.toml")
        spec = ("## Intent\nSet up the test runner.\n\nOut of scope:\n- Product code.\n\n"
                "## Contract\n- D1: the scaffold test runs.\n\n## Judge\n"
                "Command: `true`\nKind: scaffold\n")
        n = self.p.piece(spec=spec)
        self.ready(n)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_doctor_names_each_gap_then_passes(self):
        checks = gate.doctor(self.p.gh, self.p.root)
        failed = [what for ok, what, _ in checks if not ok]
        self.assertIn("the state labels exist", failed)
        self.assertIn("AGENTS.md on main names the Test command", failed)
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("test -f prepared.txt", prepare="touch prepared.txt")
        checks = gate.doctor(self.p.gh, self.p.root)
        self.assertTrue(all(ok for ok, _, _ in checks), checks)
        self.assertTrue(any("main branch protection: unknown" == what for _, what, _ in checks))

    def test_doctor_checks_quality_commands_on_main(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: printf quality-check-failed; exit 4\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add bad quality command")
        git(self.p.root, "push", "--quiet", "origin", "main")
        checks = gate.doctor(self.p.gh, self.p.root)
        failure = next((item for item in checks if not item[0] and "Quality" in item[1]), None)
        self.assertIsNotNone(failure, checks)
        self.assertIn("quality-check-failed", failure[2])

    def test_doctor_reports_a_timed_out_keep_with_next_step(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Keep: slow keep\nKeep limit: 1\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set slow Keep")
        git(self.p.root, "push", "--quiet", "origin", "main")

        def run_slow_keep(folder, command, timeout=900, protected_paths=None):
            if command == "slow keep":
                self.assertEqual(timeout, 60)
                return 124, "the judge ran past 60 seconds"
            return 0, ""

        with patch.object(loopkit, "run_judge", side_effect=run_slow_keep), \
                patch.object(doctor, "run_judge", side_effect=run_slow_keep):
            checks = gate.doctor(self.p.gh, self.p.root)
        failed_keep = next((check for check in checks if not check[0] and "Keep" in check[1]), None)
        self.assertIsNotNone(failed_keep, checks)
        self.assertTrue(failed_keep[2], failed_keep)
        self.assertIn("Keep limit", failed_keep[2])

    def test_doctor_runs_test_before_quality_in_the_same_fresh_copy(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("touch .coverage")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: test -f .coverage\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add coverage quality check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        checks = gate.doctor(self.p.gh, self.p.root)
        quality = [item for item in checks if "Quality command" in item[1]]
        self.assertTrue(quality and all(item[0] for item in quality), checks)

    def test_doctor_applies_proposed_quality_to_fresh_main(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        proposal = "grep -q '^Quality: ' AGENTS.md"
        checks = gate.doctor(self.p.gh, self.p.root, extra_quality=[proposal])
        proposed = [item for item in checks if "Proposed Quality command" in item[1]]
        self.assertEqual(len(proposed), 1, checks)
        self.assertTrue(proposed[0][0], proposed[0])

    def test_failed_quality_probe_runs_test_before_quality_on_main(self):
        self.p.loop_section("touch .coverage")
        failed = gate.quality_fails_on_main(
            self.p.root, "test -f .coverage", "touch .coverage")
        self.assertFalse(failed)

    def test_doctor_fails_mutation_check_without_source_paths(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        helper = Path(gate.__file__).resolve().parents[1] / "quality" / "mutmut-changed.py"
        checks = gate.doctor(self.p.gh, self.p.root,
                             extra_quality=[f"python3 {helper} origin/main"])
        quality = [item for item in checks if "Quality command" in item[1]]
        self.assertTrue(quality and not quality[-1][0], checks)
        self.assertIn("no mutmut source paths configured", quality[-1][2])

    def test_doctor_uses_proposed_prepare_and_test_for_quality_probe(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true", prepare="touch old-prepare")
        proposed_quality = "printf proposed"
        with patch.object(doctor, "quality_on_fresh_main", return_value=(True, "")) as probe:
            gate.doctor(self.p.gh, self.p.root, extra_quality=[proposed_quality],
                        proposed_prepare="touch new-prepare", proposed_test="test -f new-test")
        probe.assert_called_once()
        self.assertEqual(probe.call_args.args[2:4], (proposed_quality, "test -f new-test"))
        self.assertEqual(probe.call_args.kwargs["prepare_command"], "touch new-prepare")

    def test_doctor_warns_about_old_in_project_worktrees(self):
        (self.p.root / ".loop" / "worktrees" / "old").mkdir(parents=True)
        checks = gate.doctor(self.p.gh, self.p.root)
        warning = next((item for item in checks if "old in-project worktrees" in item[1]), None)
        self.assertIsNotNone(warning, checks)
        self.assertIn(".loop/worktrees/old", warning[1])
        self.assertIn("may remove", warning[2])

    def test_doctor_catches_a_red_baseline(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("exit 1")
        checks = gate.doctor(self.p.gh, self.p.root)
        self.assertFalse(checks[-1][0])
        self.assertIn("tests pass on a fresh copy", checks[-1][1])

    def test_judge_output_loses_terminal_colour_codes(self):
        _, output = run_judge(self.p.root, r"printf '\033[31mFAIL\033[39m \033]8;;file:///a\007a.js\033]8;;\007'")
        self.assertEqual(output, "FAIL a.js")

    def test_keep_output_records_elapsed_seconds(self):
        with patch.object(loopkit.time, "monotonic", side_effect=[10.0, 12.5]), \
                patch.object(loopkit, "run_judge", return_value=(0, "passed")):
            code, output = gate.run_keep(self.p.root, "true", timeout=1200)
        self.assertEqual(code, 0)
        self.assertEqual(output, "passed\nKeep took: 2.500 seconds")
