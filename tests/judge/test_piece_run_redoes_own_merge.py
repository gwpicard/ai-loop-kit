"""A build folder holding the run's own unfinished merge of the base is built again."""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import git
from run_fixtures import RunFixture

# isort: split

import gate
import run
from loopkit import records

def merge(folder, branch):
    """Merge a branch the way the run does; the merge is meant to stop on a conflict."""
    return subprocess.run(["git", "merge", "--no-edit", branch], cwd=folder,
                          capture_output=True, text=True)

# The fake build must not leave __pycache__ in the build folder.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


MAIN_HABITS = ("def add(items, name):\n    raise NotImplementedError(name)\n\n\n"
               "def count(items):\n    return len(items)\n")


class OwnUnfinishedMergeTest(RunFixture, unittest.TestCase):
    def built_piece(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        run.build_piece(self.p.gh, self.p.root, n, 1)
        return n, self.p.folder(n)

    def unfinished_merge_of_main(self):
        """Main gains a conflicting habits.py and a clean new file; the folder merges it, unfinished."""
        n, folder = self.built_piece()
        (self.p.root / "habits.py").write_text(MAIN_HABITS)
        (self.p.root / "from_main.txt").write_text("main\n")
        git(self.p.root, "add", "habits.py", "from_main.txt")
        git(self.p.root, "commit", "--quiet", "-m", "Main changes")
        git(self.p.root, "push", "--quiet", "origin", "main")
        merged = merge(folder, "origin/main")
        self.assertNotEqual(merged.returncode, 0)
        status = git(folder, "status", "--porcelain")
        self.assertIn("AA habits.py", status)
        self.assertIn("A  from_main.txt", status)
        return n, folder

    def unfinished_merge_of_side_branch(self):
        """The folder holds an unfinished merge of a branch that is not the base."""
        n, folder = self.built_piece()
        git(folder, "switch", "--quiet", "-c", "side")
        (folder / "habits.py").write_text("SIDE = 1\n")
        (folder / "from_side.txt").write_text("side\n")
        git(folder, "add", "habits.py", "from_side.txt")
        git(folder, "commit", "--quiet", "-m", "Side")
        git(folder, "switch", "--quiet", f"piece/{n}")
        (folder / "habits.py").write_text("PIECE = 1\n")
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Piece")
        merged = merge(folder, "side")
        self.assertNotEqual(merged.returncode, 0)
        status = git(folder, "status", "--porcelain")
        self.assertIn("UU habits.py", status)
        self.assertIn("A  from_side.txt", status)
        return n, folder

    def run_again(self, n):
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="try again", reason_type="conflict")
        gate.move(self.p.gh, self.p.root, n, "ready")
        os.environ["FAKE_MODE"] = "good"
        prompts = []
        original = run.build_once

        def build_once(*args, **kwargs):
            prompts.append(args[1])
            return original(*args, **kwargs)

        out = io.StringIO()
        with patch.object(run, "build_once", side_effect=build_once), \
                contextlib.redirect_stdout(out):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        return result, prompts, out.getvalue()

    def test_D1_own_unfinished_merge_is_built_again_with_the_merge_note(self):
        n, folder = self.unfinished_merge_of_main()
        result, prompts, _ = self.run_again(n)
        self.assertNotIn("back to shaping", result)
        self.assertIn("pull request ready", result)
        self.assertEqual(len(prompts), 1)
        self.assertIn("unfinished merge of main, with conflicts in: habits.py", prompts[0])
        git(folder, "merge-base", "--is-ancestor", "origin/main", f"piece/{n}")

    def test_D2_the_run_log_has_one_line_for_the_dropped_merge(self):
        n, _ = self.unfinished_merge_of_main()
        _, _, output = self.run_again(n)
        lines = [line for line in output.splitlines() if "unfinished merge" in line.lower()
                 and "dropped" in line.lower()]
        self.assertEqual(len(lines), 1, output)
        self.assertIn(f"piece {n}", lines[0])
        self.assertIn("redone", lines[0].lower())

    def test_D3_an_unfinished_merge_of_another_branch_is_handed_back(self):
        n, folder = self.unfinished_merge_of_side_branch()
        result, prompts, _ = self.run_again(n)
        self.assertIn("back to shaping", result)
        self.assertEqual(prompts, [])
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assertEqual(handback["type"], "environment")
        self.assertIn("build folder has uncommitted changes the run did not make",
                      handback["reason"])
        self.assertTrue(git(folder, "rev-parse", "--verify", "MERGE_HEAD"))

    def test_D3_only_a_merge_of_the_base_is_dropped(self):
        n, folder = self.unfinished_merge_of_side_branch()
        result, _, _ = self.run_again(n)
        self.assertIn("back to shaping", result)
        git(folder, "merge", "--abort")
        (self.p.root / "habits.py").write_text(MAIN_HABITS)
        (self.p.root / "from_main.txt").write_text("main\n")
        git(self.p.root, "add", "habits.py", "from_main.txt")
        git(self.p.root, "commit", "--quiet", "-m", "Main changes")
        git(self.p.root, "push", "--quiet", "origin", "main")
        self.assertNotEqual(merge(folder, "origin/main").returncode, 0)
        gate.move(self.p.gh, self.p.root, n, "ready")
        os.environ["FAKE_MODE"] = "good"
        with contextlib.redirect_stdout(io.StringIO()):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertNotIn("back to shaping", result)
        self.assertIn("pull request ready", result)

    def test_D4_an_untracked_file_is_uncommitted_changes(self):
        n, folder = self.built_piece()
        self.assertEqual(run.dirty_folder_reason(folder), "")
        (folder / "stray.txt").write_text("not recorded\n")
        self.assertIn("build folder has uncommitted changes the run did not make",
                      run.dirty_folder_reason(folder))


    def test_D5_a_stray_file_beside_the_runs_own_merge_is_handed_back(self):
        n, folder = self.unfinished_merge_of_main()
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="try again", reason_type="conflict")
        gate.move(self.p.gh, self.p.root, n, "ready")
        os.environ["FAKE_MODE"] = "good"
        calls = []
        original = run.build_once

        def build_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:  # a failed attempt: a stray file, the merge left unfinished
                (args[0] / "stray.txt").write_text("left by attempt 1\n")
                args[3].write_text("")
                return ""
            return original(*args, **kwargs)

        with patch.object(run, "build_once", side_effect=build_once), \
                contextlib.redirect_stdout(io.StringIO()):
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("back to shaping", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assertIn("build folder has uncommitted changes the run did not make",
                      handback["reason"])

if __name__ == "__main__":
    unittest.main()
