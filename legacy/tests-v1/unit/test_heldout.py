"""Unit tests for kit/scripts/loop/heldout.py."""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import heldout  # noqa: E402
from loop.paths import Paths  # noqa: E402


class Store(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.project = self.base / "project"
        self.project.mkdir()
        self.paths = Paths.for_project(
            self.project, data_base=self.base / "data", kit_folder=self.base / "kit"
        )

    def test_store_and_read_back(self) -> None:
        heldout.store(self.paths, 4, {"H-1": "case one", "H-2": "case two"})
        self.assertEqual(heldout.read(self.paths, 4), {"H-1": "case one", "H-2": "case two"})
        self.assertTrue(str(self.paths.held_out_dir) in str(heldout.folder(self.paths, 4)))

    def test_fingerprint_is_stable_and_follows_content(self) -> None:
        one = heldout.store(self.paths, 4, {"H-1": "a", "H-2": "b"})["fingerprint"]
        same = heldout.fingerprint(self.paths, 4)
        self.assertEqual(one, same)
        with self.assertRaises(heldout.HeldOutError):
            heldout.store(self.paths, 4, {"H-1": "changed"})
        changed = heldout.store(self.paths, 4, {"H-1": "changed"}, replace=True)["fingerprint"]
        self.assertNotEqual(one, changed)

    def test_fingerprint_does_not_hold_content(self) -> None:
        result = heldout.store(self.paths, 4, {"H-1": "very-private-case"})
        self.assertNotIn("very-private-case", str(result))

    def test_storing_the_same_case_twice_is_fine(self) -> None:
        first = heldout.store(self.paths, 4, {"H-1": "a"})["fingerprint"]
        second = heldout.store(self.paths, 4, {"H-1": "a"})["fingerprint"]
        self.assertEqual(first, second)

    def test_files_are_private(self) -> None:
        heldout.store(self.paths, 4, {"H-1": "a"})
        folder = heldout.folder(self.paths, 4)
        self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
        for item in folder.iterdir():
            self.assertEqual(stat.S_IMODE(os.stat(item).st_mode), 0o600)

    def test_dry_run_writes_nothing(self) -> None:
        result = heldout.store(self.paths, 4, {"H-1": "a"}, dry_run=True)
        self.assertTrue(result["fingerprint"])
        self.assertFalse(self.paths.held_out_dir.exists())

    def test_a_case_name_cannot_leave_the_folder(self) -> None:
        for name in ("../escape", "a/b", ".hidden", ""):
            with self.subTest(name=name), self.assertRaises(heldout.HeldOutError):
                heldout.store(self.paths, 4, {name: "x"})

    def test_a_folder_inside_the_project_is_refused(self) -> None:
        inside = Paths(root=self.project, data_dir=self.project / "data", kit_dir=self.base)
        with self.assertRaises(heldout.HeldOutError) as caught:
            heldout.store(inside, 4, {"H-1": "a"})
        self.assertIn("inside the project", str(caught.exception))
        self.assertFalse((self.project / "data").exists())

    def test_nothing_reaches_git(self) -> None:
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        heldout.store(self.paths, 4, {"H-1": "a"})
        status = subprocess.run(
            ["git", "-C", str(self.project), "status", "--porcelain", "--ignored"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(status.strip(), "")

    def test_missing_piece_reads_as_empty_with_no_fingerprint_error(self) -> None:
        self.assertEqual(heldout.read(self.paths, 9), {})
        with self.assertRaises(heldout.HeldOutError):
            heldout.fingerprint(self.paths, 9)


if __name__ == "__main__":
    unittest.main()
