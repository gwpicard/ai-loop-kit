"""A project can set a base branch other than main."""
from __future__ import annotations

from helpers import GOOD_CODE, JUDGE, SPEC, git

# isort: split

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import doctor
import gate
import loopkit
import run
from loop_fixtures import GateFixture
from loopkit import Refused


class BaseBranchTest(GateFixture, unittest.TestCase):
    def use_base(self, name="trip", with_code=False):
        """Set the base in AGENTS.md on main, then make the base branch from main."""
        self.p.loop_section("printf baseline")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + f"Base branch: {name}\n")
        git(self.p.root, "commit", "--quiet", "-am", "Base branch")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "switch", "--quiet", "-c", name)
        if with_code:
            (self.p.root / "habits.py").write_text(GOOD_CODE)
            git(self.p.root, "add", "habits.py")
            git(self.p.root, "commit", "--quiet", "-m", "Code on the base")
        git(self.p.root, "push", "--quiet", "-u", "origin", name)
        git(self.p.root, "switch", "--quiet", "main")

    def piece_on(self, base):
        n = gate.capture(self.p.gh, "Add a habit", SPEC)
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", base)
        (self.p.root / "judge_add.py").write_text(JUDGE)
        git(self.p.root, "add", "judge_add.py")
        git(self.p.root, "commit", "--quiet", "-m", "Judge")
        git(self.p.root, "switch", "--quiet", "main")
        return n

    def test_without_the_setting_the_base_is_main(self):
        self.p.loop_section("printf baseline")
        self.assertEqual(loopkit.base_branch(self.p.root), "main")
        self.assertEqual(loopkit.main_ref(self.p.root), "origin/main")

    def test_the_setting_moves_the_base(self):
        self.use_base()
        self.assertEqual(loopkit.base_branch(self.p.root), "trip")
        self.assertEqual(loopkit.main_ref(self.p.root), "origin/trip")

    def test_a_bad_branch_name_is_refused(self):
        for name in ("-x", "a..b", "two words"):
            with self.subTest(name=name):
                agents = self.p.root / "AGENTS.md"
                agents.write_text(f"## The loop\nTest command: `true`\nBase branch: {name}\n")
                with self.assertRaises(Refused):
                    loopkit.base_branch(self.p.root)

    def test_git_branch_names_are_accepted(self):
        for name in ("feature/x", "release-1.2", "a@b"):
            with self.subTest(name=name):
                (self.p.root / "AGENTS.md").write_text(f"## The loop\nBase branch: {name}\n")
                self.assertEqual(loopkit.base_branch(self.p.root), name)

    def test_the_setting_comes_from_main_not_the_checkout(self):
        self.use_base()
        git(self.p.root, "switch", "--quiet", "trip")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text().replace("Base branch: trip\n", ""))
        git(self.p.root, "commit", "--quiet", "-am", "No base line on trip")
        self.assertEqual(loopkit.base_branch(self.p.root), "trip")
        agents.write_text(agents.read_text() + "Base branch: other\n")
        self.assertEqual(loopkit.base_branch(self.p.root), "trip")

    def test_a_missing_base_says_how_to_make_it(self):
        self.p.loop_section("printf baseline")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Base branch: nothere\n")
        git(self.p.root, "commit", "--quiet", "-am", "Base branch")
        git(self.p.root, "push", "--quiet", "origin", "main")
        with self.assertRaises(Refused) as refusal:
            loopkit.main_ref(self.p.root)
        self.assertIn("create nothere from main", refusal.exception.next_step)

    def test_doctor_warns_when_quality_names_origin_main(self):
        self.use_base()
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: `crap --base origin/main`\n")
        checks = doctor.doctor(self.p.gh, self.p.root)
        self.assertTrue(any("Quality compares with main, not trip" in what
                            for _, what, _ in checks))

    def test_a_build_folder_cannot_change_the_base(self):
        self.use_base()
        folder = self.p.root.parent / "build"
        git(self.p.root, "worktree", "add", "--quiet", "-b", "piece/9", str(folder), "trip")
        (folder / "AGENTS.md").write_text("## The loop\nBase branch: piece/9\n")
        self.assertEqual(loopkit.base_branch(folder), "trip")

    def test_ready_judges_against_the_base_not_main(self):
        self.use_base(with_code=True)
        n = self.piece_on("trip")
        with self.assertRaises(Refused) as refusal:
            self.ready(n)
        self.assertIn("already passes", refusal.exception.reason)

    def test_ready_records_the_base(self):
        self.use_base()
        n = self.piece_on("trip")
        self.ready(n)
        record = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(record["base"], "trip")

    def test_the_gate_refuses_a_piece_made_ready_on_another_base(self):
        self.use_base()
        n = self.piece_on("trip")
        self.ready(n)
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text().replace("Base branch: trip", "Base branch: main"))
        git(self.p.root, "commit", "--quiet", "-am", "Back to main")
        git(self.p.root, "push", "--quiet", "origin", "main")
        with self.assertRaises(Refused) as refusal:
            run._build_piece(self.p.gh, self.p.root, n, attempts=1)
        self.assertIn("base branch changed", refusal.exception.reason)
        self.assertNotIn("state:building", self.p.gh.issue(n)["labels"])

    def test_an_old_ready_record_without_a_base_reads_as_main(self):
        n = self.p.piece()
        self.ready(n)
        record = dict(gate.last_record(self.p.gh.comments(n), "ready"))
        record.pop("base")
        gate.check_claim_bar(self.p.root, n, record)

    def test_quality_commands_see_the_base(self):
        self.use_base()
        self.assertEqual(loopkit.command_env(self.p.root)["LOOP_BASE"], "trip")

    def test_crap_compares_with_the_base_by_default(self):
        (self.p.root / "coverage.json").write_text('{"files":{}}')
        script = Path(loopkit.__file__).resolve().parents[1] / "quality" / "crap.py"
        result = subprocess.run([sys.executable, str(script), "--coverage", "coverage.json"],
                                cwd=self.p.root, capture_output=True, text=True,
                                env={**os.environ, "LOOP_BASE": "trip"})
        self.assertIn("origin/trip...HEAD", result.stdout + result.stderr)

    def test_pull_requests_target_the_base(self):
        self.use_base()
        github = loopkit.GitHub(self.p.root)
        with patch.object(github, "_gh", return_value="url") as call:
            github.create_pr("piece/1", "Title", "Body")
        args = call.call_args.args
        self.assertEqual(args[args.index("--base") + 1], "trip")
        with patch.object(github, "_gh", return_value="") as call:
            github.edit_pr("url", "Title", "Body")
        args = call.call_args.args
        self.assertEqual(args[args.index("--base") + 1], "trip")

    def test_sync_finishes_a_piece_merged_into_the_base(self):
        self.use_base()
        n = self.piece_on("trip")
        self.p.gh.set_labels(n, ["state:approval"], ["state:shaping"])
        self.p.gh.prs[f"piece/{n}"] = {"url": "u", "state": "MERGED"}
        gate.sync(self.p.gh, self.p.root)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])


if __name__ == "__main__":
    unittest.main()
