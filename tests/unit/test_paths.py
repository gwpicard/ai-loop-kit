"""Unit tests for loop/paths.py: every shared path is defined once."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import paths  # noqa: E402


class ProjectPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()) / "demo"
        self.root.mkdir()
        self.data = Path(tempfile.mkdtemp())
        self.kit = Path(tempfile.mkdtemp())
        self.p = paths.Paths.for_project(self.root, data_home=self.data, kit_dir=self.kit)

    def test_run_folder_and_record(self) -> None:
        self.assertEqual(self.p.run_dir("night-1"), self.root / ".agents/runs/night-1")
        self.assertEqual(self.p.run_record("night-1"), self.root / ".agents/runs/night-1/run.json")

    def test_files_inside_the_run_folder(self) -> None:
        run = self.root / ".agents/runs/night-1"
        self.assertEqual(self.p.lock_file("night-1"), run / "lock")
        self.assertEqual(self.p.heartbeat("night-1"), run / "heartbeat")
        self.assertEqual(self.p.mailbox("night-1"), run / "mailbox")
        self.assertEqual(self.p.command_log("night-1"), run / "commands.log")

    def test_piece_records(self) -> None:
        self.assertEqual(self.p.piece_dir(7), self.root / ".agents/pieces/7")

    def test_worktrees_and_settings(self) -> None:
        self.assertEqual(self.p.worktrees_dir, self.root / ".agents/worktrees")
        self.assertEqual(self.p.policy_file, self.root / ".agents/loop/policy.json")
        self.assertEqual(self.p.local_settings, self.root / ".agents/loop/local.json")

    def test_held_out_and_key_sit_outside_the_project_and_side_by_side(self) -> None:
        self.assertEqual(self.p.held_out_dir, self.data / "demo" / "held-out")
        self.assertEqual(self.p.app_key_file, self.data / "demo" / "app-key.pem")
        self.assertEqual(self.p.held_out_dir.parent, self.p.app_key_file.parent)
        self.assertNotIn(self.root, self.p.held_out_dir.parents)

    def test_kit_folder_is_the_one_given(self) -> None:
        self.assertEqual(self.p.kit_dir, self.kit)

    def test_run_names_cannot_leave_the_run_folder(self) -> None:
        for bad in ("", "..", "a/b", "../x", ".hidden", "a b\n"):
            with self.subTest(name=bad), self.assertRaises(paths.PathError):
                self.p.run_dir(bad)

    def test_piece_numbers_must_be_positive(self) -> None:
        for bad in (0, -1):
            with self.subTest(n=bad), self.assertRaises(paths.PathError):
                self.p.piece_dir(bad)


class Resolution(unittest.TestCase):
    def test_data_home_comes_from_the_environment(self) -> None:
        data = tempfile.mkdtemp()
        env = {"AI_LOOP_KIT_DATA": data}
        self.assertEqual(paths.data_home(env), Path(data))

    def test_data_home_follows_xdg_then_home(self) -> None:
        self.assertEqual(
            paths.data_home({"XDG_DATA_HOME": "/x/share"}), Path("/x/share/ai-loop-kit")
        )
        self.assertEqual(
            paths.data_home({"HOME": "/h"}), Path("/h/.local/share/ai-loop-kit")
        )

    def test_kit_dir_in_this_repository_is_kit(self) -> None:
        repo = Path(tempfile.mkdtemp())
        (repo / "kit" / "scripts" / "loop").mkdir(parents=True)
        self.assertEqual(paths.kit_dir(repo, {}), repo / "kit")

    def test_kit_dir_in_a_founded_project_is_the_plugin_cache(self) -> None:
        project = Path(tempfile.mkdtemp())
        self.assertEqual(
            paths.kit_dir(project, {"CLAUDE_PLUGIN_ROOT": "/cache/ai-loop-kit"}),
            Path("/cache/ai-loop-kit"),
        )
        self.assertEqual(
            paths.kit_dir(project, {"HOME": "/h"}),
            Path("/h/.claude/plugins/cache/ai-loop-kit"),
        )

    def test_find_project_root_walks_up_to_git(self) -> None:
        top = Path(tempfile.mkdtemp())
        (top / ".git").mkdir()
        deep = top / "a" / "b"
        deep.mkdir(parents=True)
        self.assertEqual(paths.find_project_root(deep), top.resolve())

    def test_find_project_root_fails_outside_a_repository(self) -> None:
        lone = Path(tempfile.mkdtemp())
        if (lone / ".git").exists() or any((q / ".git").exists() for q in lone.parents):
            self.skipTest("the temporary folder sits inside a repository")
        with self.assertRaises(paths.PathError):
            paths.find_project_root(lone)

    def test_for_project_uses_the_real_environment_by_default(self) -> None:
        root = Path(tempfile.mkdtemp()) / "p"
        root.mkdir()
        old = os.environ.get("AI_LOOP_KIT_DATA")
        os.environ["AI_LOOP_KIT_DATA"] = "/somewhere/data"
        try:
            self.assertEqual(
                paths.Paths.for_project(root).app_key_file, Path("/somewhere/data/p/app-key.pem")
            )
        finally:
            if old is None:
                del os.environ["AI_LOOP_KIT_DATA"]
            else:
                os.environ["AI_LOOP_KIT_DATA"] = old


if __name__ == "__main__":
    unittest.main()
