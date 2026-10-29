"""The judge bar follows the Exit files, and support files are checked by the build's edits."""
from __future__ import annotations

from helpers import GOOD_CODE, JUDGE, SPEC, Project, git

# isort: split

import unittest
from pathlib import Path
from unittest.mock import patch

import frozen
import gate
import loopkit
import run

PARTIAL_CODE = '''def add(items, name):
    return items + [name]
'''


class BarFixture:
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        (self.p.root / ".loop").mkdir()
        self.p.loop_section("true")
        self.commit_on_main({"tests/judge/helpers.py": "SHARED = 1\n"}, "Shared helper")

    def commit_on_main(self, files, message):
        for name, text in files.items():
            path = self.p.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                path.unlink()
            else:
                path.write_text(text)
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", message)
        git(self.p.root, "push", "--quiet", "origin", "main")

    def piece(self, name="b", shaped=None):
        """A piece whose judge lives in tests/judge/, made ready from main."""
        judge = f"tests/judge/test_{name}.py"
        spec = SPEC.replace("judge_add.py", judge)
        n = gate.capture(self.p.gh, f"Piece {name}", spec)
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        for path, text in {judge: JUDGE, **(shaped or {})}.items():
            (self.p.root / path).write_text(text)
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Judge")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.p.gh, self.p.root, n, "ready")
        return n, gate.last_record(self.p.gh.comments(n), "ready")

    def build_folder(self, n):
        """The run's build folder with main merged in, as the run makes it."""
        folder = run.worktree(self.p.root, n)
        git(folder, "merge", "--quiet", "--no-edit", "origin/main")
        return folder



class BarNeighboursTest(BarFixture, unittest.TestCase):
    def test_ready_records_the_hash_of_the_exit_files_alone(self):
        _, ready = self.piece()
        self.assertEqual(len(ready["exit_bar"]), 64)
        self.assertNotEqual(ready["exit_bar"], ready["bar"])
        self.assertIn("tests/judge/helpers.py", ready["bar_files"])

    def test_an_old_ready_record_derives_the_exit_hash_from_its_commit(self):
        _, ready = self.piece()
        old = {key: value for key, value in ready.items() if key != "exit_bar"}
        self.assertEqual(loopkit.exit_bar(self.p.root, old), ready["exit_bar"])

    def test_a_sibling_judge_landing_in_the_same_folder_is_free(self):
        n, ready = self.piece()
        self.commit_on_main({"tests/judge/test_a.py": JUDGE}, "Sibling lands")
        folder = self.build_folder(n)
        self.assertEqual(frozen.frozen_file_reason(folder, ready), "")
        gate.check_claim_bar(self.p.root, n, ready)

    def test_a_shaped_helper_edit_survives_a_sibling_landing(self):
        n, ready = self.piece(shaped={"tests/judge/helpers.py": "SHARED = 2\n"})
        self.commit_on_main({"tests/judge/test_a.py": JUDGE}, "Sibling lands")
        self.assertEqual(frozen.frozen_file_reason(self.build_folder(n), ready), "")

    def test_a_helper_change_from_the_base_is_free(self):
        n, ready = self.piece()
        self.commit_on_main({"tests/judge/helpers.py": "SHARED = 3\n", "README.md": "new\n"},
                            "Main moves")
        self.assertEqual(frozen.frozen_file_reason(self.build_folder(n), ready), "")

    def test_builder_edits_and_deletions_of_support_files_are_caught(self):
        n, ready = self.piece()
        self.commit_on_main({"tests/judge/test_a.py": JUDGE}, "Sibling lands")
        folder = self.build_folder(n)
        (folder / "tests/judge/helpers.py").write_text("SHARED = 99\n")
        self.assertEqual(frozen.frozen_file_reason(folder, ready),
                         "the build changed frozen files: tests/judge/helpers.py")
        (folder / "tests/judge/test_a.py").unlink()
        self.assertEqual(frozen.frozen_file_reason(folder, ready),
                         "the build changed frozen files: tests/judge/helpers.py, "
                         "tests/judge/test_a.py")
        git(folder, "commit", "--quiet", "-am", "Committed edits")
        self.assertIn("tests/judge/test_a.py", frozen.frozen_file_reason(folder, ready))

    def test_the_prepare_path_check_sees_a_file_added_by_an_earlier_build(self):
        n, ready = self.piece(shaped={"early_gen.py": "EARLY = 1\n"})
        folder = self.build_folder(n)
        git_dir = Path(git(folder, "rev-parse", "--absolute-git-dir"))
        (git_dir / "info").mkdir(exist_ok=True)
        (git_dir / "info" / "ai-loop-kit-prepare-paths").write_text("early_gen.py\n")
        passed, reason = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertEqual(reason, "the piece adds files under paths Prepare created: early_gen.py")

    def test_a_builder_may_add_a_support_file(self):
        n, ready = self.piece()
        folder = self.build_folder(n)
        (folder / "tests/judge/extra.py").write_text("EXTRA = 1\n")
        self.assertEqual(frozen.frozen_file_reason(folder, ready), "")

    def test_an_exit_file_edit_is_caught(self):
        n, ready = self.piece()
        folder = self.build_folder(n)
        (folder / "tests/judge/test_b.py").write_text("print('forged pass')\n")
        passed, reason = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertEqual(reason, "the build changed frozen files: tests/judge/test_b.py")

    def test_an_exit_file_changed_on_the_base_is_named_as_inherited(self):
        self.commit_on_main({"tests/judge/test_b.py": JUDGE}, "Judge already on main")
        n, ready = self.piece(shaped={"tests/judge/notes.txt": "kept\n"})
        self.commit_on_main({"tests/judge/test_b.py": JUDGE + "# changed on main\n"},
                            "Main edits the judge")
        self.assertEqual(frozen.frozen_file_reason(self.build_folder(n), ready),
                         "main changed the frozen judge bar: tests/judge/test_b.py")

    def test_restore_puts_back_build_edits_and_keeps_inherited_files(self):
        n, ready = self.piece()
        self.commit_on_main({"tests/judge/test_a.py": JUDGE}, "Sibling lands")
        folder = self.build_folder(n)
        (folder / "tests/judge/helpers.py").write_text("SHARED = 99\n")
        (folder / "tests/judge/test_b.py").write_text("print('forged pass')\n")
        run.restore_bar(folder, ready)
        self.assertEqual(frozen.frozen_file_reason(folder, ready), "")
        self.assertEqual((folder / "tests/judge/helpers.py").read_text(), "SHARED = 1\n")
        self.assertTrue((folder / "tests/judge/test_a.py").is_file())
        self.assertEqual(git(folder, "status", "--porcelain"), "")

    def test_a_support_edit_pushed_after_ready_passes_claim_but_not_the_build(self):
        n, ready = self.piece()
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "tests/judge/helpers.py").write_text("SHARED = 7\n")
        git(self.p.root, "commit", "--quiet", "-am", "Late helper edit")
        git(self.p.root, "switch", "--quiet", "main")
        gate.check_claim_bar(self.p.root, n, ready)
        self.assertEqual(frozen.frozen_file_reason(run.worktree(self.p.root, n), ready),
                         "the build changed frozen files: tests/judge/helpers.py")

    def test_an_open_merge_skips_the_support_check(self):
        n, ready = self.piece(shaped={"tests/judge/helpers.py": "SHARED = 2\n"})
        self.commit_on_main({"tests/judge/helpers.py": "SHARED = 3\n"}, "Main edits it too")
        folder = run.worktree(self.p.root, n)
        result = loopkit.sh(["git", "merge", "--no-edit", "origin/main"], folder, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(frozen.expected_tree(folder, ready))
        self.assertEqual(frozen.neighbour_edits(folder, ready, None), [])


class AlreadySatisfiedTest(BarFixture, unittest.TestCase):
    """Before the builder, a moved base gets one run of the Exit tests."""

    def test_an_unmoved_base_runs_no_judge(self):
        n, ready = self.piece()
        with patch.object(frozen, "run_judge") as judge:
            self.assertEqual(frozen.already_satisfied(run.worktree(self.p.root, n), ready), "")
        judge.assert_not_called()

    def test_a_moved_base_with_the_judge_still_failing_goes_on(self):
        n, ready = self.piece()
        self.commit_on_main({"README.md": "moved\n"}, "Main moves")
        self.assertEqual(frozen.already_satisfied(self.build_folder(n), ready), "")

    def test_a_judge_that_now_passes_is_already_satisfied(self):
        n, ready = self.piece()
        self.commit_on_main({"habits.py": GOOD_CODE}, "A sibling built it")
        reason = frozen.already_satisfied(self.build_folder(n), ready)
        self.assertTrue(reason.startswith("already satisfied:"), reason)
        self.assertEqual(gate._cause("give-back", reason, "spec-unclear"), "already-satisfied")

    def test_a_partial_pass_still_builds(self):
        n, ready = self.piece()
        self.commit_on_main({"habits.py": PARTIAL_CODE}, "A sibling built half")
        self.assertEqual(frozen.already_satisfied(self.build_folder(n), ready), "")

    def test_code_from_an_earlier_build_skips_the_check(self):
        n, ready = self.piece()
        self.commit_on_main({"README.md": "moved\n"}, "Main moves")
        folder = self.build_folder(n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Earlier build")
        with patch.object(frozen, "run_judge") as judge:
            self.assertEqual(frozen.already_satisfied(folder, ready), "")
        judge.assert_not_called()

    def test_build_code_in_the_ready_commit_is_not_already_satisfied(self):
        n, ready = self.piece(shaped={"habits.py": GOOD_CODE})
        self.commit_on_main({"README.md": "moved\n"}, "Main moves")
        folder = self.build_folder(n)
        self.assertEqual(frozen.earlier_build_paths(folder, ready["bar_files"]), ["habits.py"])
        with patch.object(frozen, "run_judge") as judge:
            self.assertEqual(frozen.already_satisfied(folder, ready), "")
        judge.assert_not_called()

    def test_ready_warns_about_earlier_build_code_and_still_passes(self):
        n, _ = self.piece(shaped={"habits.py": GOOD_CODE})
        note = self.p.gh.comments(n)[-1]
        self.assertIn("Warning: the piece branch holds earlier build code: habits.py; "
                      "the next build starts from it.", note)

    def test_a_branch_with_only_bar_files_gets_no_warning(self):
        n, ready = self.piece(shaped={"tests/judge/helpers.py": "SHARED = 2\n"})
        self.assertNotIn("earlier build code", self.p.gh.comments(n)[-1])
        self.assertEqual(frozen.earlier_build_paths(self.p.root, ready["bar_files"],
                                                    f"piece/{n}"), [])

    def test_a_record_without_tests_checks_skips_the_check(self):
        n, ready = self.piece()
        self.commit_on_main({"habits.py": GOOD_CODE}, "A sibling built it")
        self.assertEqual(frozen.already_satisfied(self.build_folder(n), {**ready, "checks": []}),
                         "")


if __name__ == "__main__":
    unittest.main()
