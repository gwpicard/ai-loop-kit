"""Finished worktrees release ignored artefacts without losing unfinished work."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import Project, git

# isort: split
import gate
import run
import run_start


class WorktreeCleanupTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("true")
        (self.p.root / ".gitignore").write_text(".loop/\nnode_modules/\n")
        git(self.p.root, "add", ".gitignore")
        git(self.p.root, "commit", "--quiet", "-m", "Ignore installed packages")
        git(self.p.root, "push", "--quiet", "origin", "main")
        self.n = self.p.piece()
        self.folder = run.worktree(self.p.root, self.n)
        git(self.folder, "merge", "--quiet", "main")

    def merge_piece(self):
        git(self.p.root, "merge", "--quiet", f"piece/{self.n}")
        git(self.p.root, "push", "--quiet", "origin", "main")

    def test_finished_piece_removes_worktree_with_ignored_folder(self):
        self.merge_piece()
        packages = self.folder / "node_modules"
        packages.mkdir()
        (packages / "installed.js").write_text("installed\n")
        self.p.gh.issues[self.n]["labels"] = ["state:approval"]
        self.p.gh.prs[f"piece/{self.n}"] = {"state": "MERGED"}
        gate.sync(self.p.gh, self.p.root)
        self.assertFalse(self.folder.exists())
        self.assertNotIn(str(self.folder.resolve()),
                         git(self.p.root, "worktree", "list", "--porcelain"))

    def test_uncommitted_work_is_kept_and_reported(self):
        self.merge_piece()
        for name in ("README.md", "new.txt"):
            with self.subTest(path=name):
                path = self.folder / name
                path.write_text("keep this work\n")
                output = io.StringIO()
                with redirect_stdout(output):
                    run.release_worktree(self.p.root, self.n)
                self.assertEqual(path.read_text(), "keep this work\n")
                self.assertIn(str(self.folder), output.getvalue())
                self.assertIn("uncommitted", output.getvalue())
                git(self.folder, "checkout", "--", "README.md")
                if name == "new.txt":
                    path.unlink()

    def test_unmerged_commits_are_kept_and_reported(self):
        output = io.StringIO()
        with redirect_stdout(output):
            run.release_worktree(self.p.root, self.n)
        self.assertTrue(self.folder.exists())
        self.assertIn(str(self.folder), output.getvalue())
        self.assertIn("unmerged", output.getvalue())

    def test_removal_failure_reports_git_reason(self):
        self.merge_piece()
        original = run_start.sh

        def lock_before_removal(args, root, **kwargs):
            if args[:3] == ["git", "worktree", "remove"]:
                git(root, "worktree", "lock", str(self.folder))
            return original(args, root, **kwargs)

        output = io.StringIO()
        with patch.object(run_start, "sh", side_effect=lock_before_removal), \
                redirect_stdout(output):
            run.release_worktree(self.p.root, self.n)
        self.assertTrue(self.folder.exists())
        self.assertIn(str(self.folder), output.getvalue())
        self.assertIn("locked", output.getvalue())

    def test_done_and_drop_try_to_release_build_folder(self):
        self.merge_piece()
        self.p.gh.issues[self.n]["labels"] = ["state:approval"]
        self.p.gh.prs[f"piece/{self.n}"] = {"state": "MERGED"}
        gate.sync(self.p.gh, self.p.root)
        self.assertFalse(self.folder.exists())
        self.folder = run.worktree(self.p.root, self.n)
        self.p.gh.issues[self.n]["labels"] = ["state:shaping"]
        gate.move(self.p.gh, self.p.root, self.n, "dropped", reason="abandoned")
        self.assertFalse(self.folder.exists())

    def test_interrupted_review_keeps_uncommitted_and_unmerged_work(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                branch = f"review/standards-1-{int(committed) + 1}-1234abcd"
                review = self.folder.parent / f"review-{committed}"
                git(self.p.root, "worktree", "add", "--quiet", "-b", branch,
                    str(review), "main")
                note = review / "notes.txt"
                note.write_text("unfinished review\n")
                if committed:
                    git(review, "add", "notes.txt")
                    git(review, "commit", "--quiet", "-m", "Review work")
                output = io.StringIO()
                with redirect_stdout(output):
                    run_start.cleanup_interrupted_reviews(self.p.root)
                self.assertTrue(note.exists(), "cleanup lost unfinished review work")
                self.assertEqual(note.read_text(), "unfinished review\n")
                self.assertIn("kept worktree", output.getvalue())
                self.assertIn(branch, git(self.p.root, "branch", "--list", branch))

    def test_doctor_lists_size_and_safety_for_external_build_folder(self):
        for merged in (False, True):
            with self.subTest(merged=merged):
                if merged:
                    self.merge_piece()
                checks = gate.doctor(self.p.gh, self.p.root)
                warning = next((what for _, what, _ in checks
                                if str(self.folder) in what), "")
                self.assertIn("bytes", warning)
                self.assertIn("safe to remove: " + ("yes" if merged else "no"), warning)

    def test_doctor_marks_dirty_and_locked_folders_unsafe(self):
        self.merge_piece()
        for reason in ("uncommitted", "locked"):
            with self.subTest(reason=reason):
                if reason == "uncommitted":
                    (self.folder / "notes.txt").write_text("keep me\n")
                else:
                    (self.folder / "notes.txt").unlink()
                    git(self.p.root, "worktree", "lock", str(self.folder))
                checks = gate.doctor(self.p.gh, self.p.root)
                warning = next(what for _, what, _ in checks if str(self.folder) in what)
                self.assertIn("safe to remove: no", warning)
                self.assertIn(reason, warning)

    def test_cleanup_keeps_project_checkout(self):
        with redirect_stdout(io.StringIO()):
            removed = run_start.remove_worktree(self.p.root, self.p.root)
        self.assertFalse(removed)
        self.assertTrue((self.p.root / "README.md").exists())

    def test_successful_readiness_probes_remove_injected_judge_files(self):
        self.p.loop_section(
            "true", prepare="mkdir -p node_modules; touch node_modules/installed.js")
        before = git(self.p.root, "worktree", "list", "--porcelain")
        for _ in range(2):
            record = gate.check_ready(self.p.gh, self.p.root, self.p.gh.issue(self.n))
            self.assertEqual(record["move"], "ready")
            self.assertEqual(git(self.p.root, "worktree", "list", "--porcelain"), before)

    def test_successful_quality_proposal_removes_its_probe(self):
        import doctor
        for agents_exists in (True, False):
            with self.subTest(agents_exists=agents_exists):
                if not agents_exists:
                    git(self.p.root, "rm", "AGENTS.md")
                    git(self.p.root, "commit", "--quiet", "-m", "Remove loop settings")
                    git(self.p.root, "push", "--quiet", "origin", "main")
                before = git(self.p.root, "worktree", "list", "--porcelain")
                passed, output = doctor.quality_on_fresh_main(
                    self.p.root, "main", "true", proposed_quality="true")
                self.assertTrue(passed, output)
                self.assertEqual(git(self.p.root, "worktree", "list", "--porcelain"), before)

    def test_readiness_probe_keeps_edits_after_injection(self):
        original = gate.exit_ready
        for name, staged in (("notes.txt", False), ("judge_add.py", False),
                             ("judge_add.py", True)):
            with self.subTest(path=name, staged=staged):
                folders = []

                def edit_after_check(folder, *args, name=name, staged=staged, folders=folders):
                    result = original(folder, *args)
                    path = folder / name
                    injected = path.read_bytes() if staged else None
                    path.write_text("later work\n")
                    if staged:
                        git(folder, "add", name)
                        # Keep the injected working file while changing only its index entry.
                        path.write_bytes(injected)
                    folders.append(folder)
                    return result

                with patch.object(gate, "exit_ready", side_effect=edit_after_check):
                    gate.check_ready(self.p.gh, self.p.root, self.p.gh.issue(self.n))
                folder = folders[0]
                self.assertTrue(folder.exists())
                if staged:
                    self.assertEqual(git(folder, "show", f":{name}"), "later work")
                else:
                    self.assertEqual((folder / name).read_text(), "later work\n")
                self.assertIn(str(folder.resolve()),
                              git(self.p.root, "worktree", "list", "--porcelain"))

    def test_quality_probe_keeps_later_changes_to_its_settings(self):
        import doctor
        command = "printf 'later work\\n' >> AGENTS.md"
        before = {entry["worktree"] for entry in run_start.worktrees(self.p.root)}
        passed, output = doctor.quality_on_fresh_main(
            self.p.root, "main", command, proposed_quality=command)
        self.assertTrue(passed, output)
        leftover = next(entry["worktree"] for entry in run_start.worktrees(self.p.root)
                        if entry["worktree"] not in before)
        self.assertTrue((Path(leftover) / "AGENTS.md").read_text().endswith("later work\n"))

    def test_probe_removal_failure_is_reported(self):
        import doctor
        original = doctor.sh

        def lock_probe(args, root, **kwargs):
            result = original(args, root, **kwargs)
            if args[:3] == ["git", "worktree", "add"]:
                git(root, "worktree", "lock", args[-2])
            return result

        output = io.StringIO()
        with patch.object(doctor, "sh", side_effect=lock_probe), redirect_stdout(output):
            doctor.quality_on_fresh_main(self.p.root, "main", "true")
        self.assertIn("kept worktree", output.getvalue())
        self.assertIn("locked", output.getvalue())


if __name__ == "__main__":
    unittest.main()
