# Intent: the gate checks an attempt against the judge and the touched test files when the run asks for the narrow tier.
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import GOOD_CODE, SPEC, Project, git

# isort: split
import gate
import loopkit
import run

TIER = "AI_LOOP_KIT_TIER"
FULL_SUITE = ("mkdir -p .loop\necho ran >> .loop/full.marker\n"
              "if [ -f broken.flag ]; then echo REGRESSION-BROKEN; exit 1; fi\n")
FILES_COMMAND = "mkdir -p .loop && echo {files} > .loop/files.marker"
KEEP = "mkdir -p .loop && echo ran > .loop/keep.marker"
NAMED = "tests/test_named.py"
CHANGED = "tests/test_changed.py"


class NarrowChecksTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(TIER, None)

    def setup_project(self, files_command=True):
        (self.p.root / "regression.sh").write_text(FULL_SUITE)
        lines = ["# AGENTS.md", "", "## The loop", "Test command: `sh regression.sh`"]
        if files_command:
            lines.append(f"Test files command: `{FILES_COMMAND}`")
        (self.p.root / "AGENTS.md").write_text("\n".join(lines) + "\n")
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Loop section")
        git(self.p.root, "push", "--quiet", "origin", "main")

    def ready_piece(self, files_command=True):
        self.setup_project(files_command)
        spec = SPEC.replace("- judge_add.py\n", f"- judge_add.py\n- {NAMED}\n")
        spec += f"\nKeep: `{KEEP}`\n"
        n = self.p.piece(spec=spec)
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "tests").mkdir()
        (self.p.root / NAMED).write_text("# a named test file\n")
        git(self.p.root, "add", NAMED)
        git(self.p.root, "commit", "--quiet", "-m", "Named test file")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.p.gh, self.p.root, n, "ready")
        return n, gate.last_record(self.p.gh.comments(n), "ready")

    def build(self, n, good=True, test_file=True):
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE if good else "def add(i, n):\n    return []\n")
        names = ["habits.py"]
        if test_file:
            (folder / "tests").mkdir(exist_ok=True)
            (folder / CHANGED).write_text("# a changed test file\n")
            names.append(CHANGED)
        git(folder, "add", *names)
        git(folder, "commit", "--quiet", "-m", "Build candidate")
        return folder

    def marker(self, folder, name):
        path = folder / ".loop" / name
        return path.read_text().strip() if path.exists() else None

    def test_D1_loop_settings_reads_the_test_files_command(self):
        text = "## The loop\nTest command: `pytest`\nTest files command: `pytest {files}`\n"
        self.assertEqual(loopkit.loop_settings(self.p.root, text).get("test files command"),
                         "pytest {files}")

    def test_D1_ready_freezes_the_test_files_command(self):
        _, ready = self.ready_piece()
        self.assertEqual(ready.get("regression_files"), FILES_COMMAND)

    def test_D1_ready_freezes_an_empty_string_when_the_line_is_absent(self):
        _, ready = self.ready_piece(files_command=False)
        self.assertEqual(ready.get("regression_files"), "")

    def test_D2_narrow_runs_the_test_files_command_on_changed_and_named_files(self):
        n, ready = self.ready_piece()
        folder = self.build(n)
        os.environ[TIER] = "narrow"
        passed, output = gate.judge(folder, ready)
        self.assertTrue(passed, output)
        self.assertEqual(self.marker(folder, "files.marker"), f"{CHANGED} {NAMED}")
        self.assertIsNone(self.marker(folder, "full.marker"))
        self.assertIsNone(self.marker(folder, "keep.marker"))
        self.assertIn("Narrow tests:", output)

    def test_D2_narrow_still_fails_when_the_exit_check_fails(self):
        n, ready = self.ready_piece()
        folder = self.build(n, good=False)
        os.environ[TIER] = "narrow"
        passed, _ = gate.judge(folder, ready)
        self.assertFalse(passed)

    def test_D3_narrow_runs_no_command_when_no_test_file_changed(self):
        n, ready = self.ready_piece()
        ready = {**ready, "files": ["judge_add.py"]}
        folder = self.build(n, test_file=False)
        os.environ[TIER] = "narrow"
        passed, output = gate.judge(folder, ready)
        self.assertTrue(passed, output)
        self.assertIn("no test files changed", output)
        for name in ("files.marker", "full.marker", "keep.marker"):
            self.assertIsNone(self.marker(folder, name))

    def test_D3_exit_checks_alone_decide_when_no_test_file_changed(self):
        n, ready = self.ready_piece()
        ready = {**ready, "files": ["judge_add.py"]}
        folder = self.build(n, good=False, test_file=False)
        os.environ[TIER] = "narrow"
        passed, _ = gate.judge(folder, ready)
        self.assertFalse(passed)

    def test_D4_narrow_without_a_files_command_runs_the_full_suite_and_skips_keep(self):
        n, ready = self.ready_piece(files_command=False)
        folder = self.build(n)
        os.environ[TIER] = "narrow"
        passed, output = gate.judge(folder, ready)
        self.assertTrue(passed, output)
        self.assertEqual(self.marker(folder, "full.marker"), "ran")
        self.assertIsNone(self.marker(folder, "keep.marker"))
        self.assertIsNone(self.marker(folder, "files.marker"))

    def test_D4_a_failing_full_suite_fails_the_attempt_with_its_output(self):
        n, ready = self.ready_piece(files_command=False)
        folder = self.build(n)
        (folder / "broken.flag").write_text("x")
        os.environ[TIER] = "narrow"
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertIn("REGRESSION-BROKEN", output)

    def test_D5_submit_record_names_the_narrow_tier(self):
        n, _ = self.ready_piece()
        folder = self.build(n)
        os.environ[TIER] = "narrow"
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
        submit = gate.last_record(self.p.gh.comments(n), "submit")
        self.assertEqual(submit["regression"].get("tier"), "narrow")

    def test_D6_without_the_tier_judge_runs_exit_full_suite_and_keep(self):
        n, ready = self.ready_piece()
        folder = self.build(n)
        passed, output = gate.judge(folder, ready)
        self.assertTrue(passed, output)
        self.assertEqual(self.marker(folder, "full.marker"), "ran")
        self.assertEqual(self.marker(folder, "keep.marker"), "ran")
        self.assertIsNone(self.marker(folder, "files.marker"))

    def test_D6_without_the_tier_old_tests_that_fail_fail_the_attempt(self):
        n, ready = self.ready_piece()
        folder = self.build(n)
        (folder / "broken.flag").write_text("x")
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertIn("REGRESSION-BROKEN", output)

    def test_D6_without_the_tier_the_submit_record_has_no_tier(self):
        n, _ = self.ready_piece()
        folder = self.build(n)
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
        submit = gate.last_record(self.p.gh.comments(n), "submit")
        self.assertNotIn("tier", submit["regression"])

    def test_D7_project_commands_do_not_see_the_tier(self):
        self.setup_project()
        os.environ[TIER] = "narrow"
        self.assertNotIn(TIER, loopkit.command_env(self.p.root))
        code, output = loopkit.run_judge(self.p.root, 'echo "tier=[$AI_LOOP_KIT_TIER]"')
        self.assertEqual(code, 0)
        self.assertIn("tier=[]", output)


if __name__ == "__main__":
    unittest.main()
