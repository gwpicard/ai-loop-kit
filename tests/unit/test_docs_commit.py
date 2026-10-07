"""Unit tests for kit/scripts/loop/run/docs_commit.py.

The project is a throwaway Git repository founded from the kit's templates. Two pieces are
joined to a combined branch, and the docs commit must apply each piece's Added, Changed and
Removed lines, add a new area to the area map and the overview, fold one changelog entry for
each piece, and leave a project that `records-check.py` passes.
"""

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import records  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import docs_commit, integrate  # noqa: E402

TEMPLATES = ROOT / "kit" / "templates"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test Person", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Person", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False, env={**os.environ, **GIT_ENV})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def view(number: int, *, touches: str, added: str = "", changed: str = "", removed: str = "",
         new_area: tuple[str, ...] = (), issue_type: str = "feature",
         title: str = "") -> integrate.PieceView:
    sp: dict[str, Any] = {
        "judge": {"command": "x"}, "must_stay_checks": [],
        "links": {"touches": [touches]},
        "changes": {"added": [added] if added else [], "changed": [changed] if changed else [],
                    "removed": [removed] if removed else [], "new_area": list(new_area),
                    "security": [], "docs": []},
    }
    return integrate.PieceView(number=number, title=title or f"Piece {number}",
                               state="review", issue=None, individual=False,
                               issue_type=issue_type, spec=sp)


class DocsCommitCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "project"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        for name in ("docs", ".agents/guard", ".agents/loop", ".claude", ".github/workflows"):
            (self.root / name).mkdir(parents=True)
        shutil.copy(TEMPLATES / "blocked-commands.md", self.root / ".agents/guard")
        shutil.copy(TEMPLATES / "claude-settings.json", self.root / ".claude/settings.json")
        shutil.copy(TEMPLATES / "AGENTS.md", self.root / "AGENTS.md")
        shutil.copy(TEMPLATES / "CLAUDE.md", self.root / "CLAUDE.md")
        shutil.copy(TEMPLATES / "CHANGELOG.md", self.root / "CHANGELOG.md")
        shutil.copy(TEMPLATES / "overview.md", self.root / "docs/overview.md")
        shutil.copy(TEMPLATES / "docs-README.md", self.root / "docs/README.md")
        shutil.copy(TEMPLATES / "area-map", self.root / "docs/area-map")
        text = (TEMPLATES / "checks.yml").read_text().replace("{{KIT_REF}}", "main")
        (self.root / ".github/workflows/checks.yml").write_text(text)
        shutil.copy(TEMPLATES / "policy.json", self.root / ".agents/loop/policy.json")
        # One real area besides the records.
        (self.root / "src").mkdir()
        (self.root / "src" / "greet.py").write_text("def greet():\n    return 'hi'\n")
        with (self.root / "docs/area-map").open("a") as handle:
            handle.write("src/ core\n")
        overview = self.root / "docs/overview.md"
        overview.write_text(overview.read_text().rstrip("\n")
                            + "\n| core | The core behaviour | no | | `docs/core.md` |\n")
        (self.root / "docs/core.md").write_text(
            "# core\n\n- The greeting says hi.\n- The greeting is short.\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Found the project")
        self.paths = Paths.for_project(self.root, data_base=self.base / "data",
                                       kit_folder=ROOT / "kit")
        self.branch = "combined-night-1"
        git(self.root, "branch", self.branch, "main")

    def join(self, number: int, files: dict[str, str]) -> None:
        git(self.root, "branch", f"piece-{number}", "main")
        folder = self.base / f"wt-{number}"
        git(self.root, "worktree", "add", "-q", str(folder), f"piece-{number}")
        for name, text in files.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"Build {number}")
        git(self.root, "worktree", "remove", str(folder))
        scratch = self.base / f"join-{number}"
        git(self.root, "worktree", "add", "-q", "--detach", str(scratch),
            f"refs/heads/{self.branch}")
        git(scratch, "merge", "--no-ff", "-q", "-m",
            f"Join piece {number}\n\nPiece: #{number}", f"piece-{number}")
        git(self.root, "update-ref", f"refs/heads/{self.branch}", git(scratch, "rev-parse",
                                                                       "HEAD"))
        git(self.root, "worktree", "remove", str(scratch))

    def apply(self, pieces: list[integrate.PieceView]) -> docs_commit.DocsResult:
        return docs_commit.apply(root=self.root, paths=self.paths, branch=self.branch,
                                 pieces=pieces, run="night-1",
                                 gate_lock=contextlib.nullcontext(), identity=[])

    def show(self, path: str) -> str:
        return git(self.root, "show", f"refs/heads/{self.branch}:{path}")

    def faults(self, closing: tuple[int, ...] = (1, 2)) -> list[str]:
        folder = self.base / "check"
        git(self.root, "worktree", "add", "-q", "--detach", str(folder),
            f"refs/heads/{self.branch}")
        try:
            return [f.message for f in records.check(folder, closing=list(closing))]
        finally:
            git(self.root, "worktree", "remove", str(folder))


class ApplyTest(DocsCommitCase):
    def test_each_piece_gets_one_changelog_entry_and_the_records_check_passes(self) -> None:
        self.join(1, {"src/farewell.py": "def bye():\n    return 'bye'\n"})
        self.join(2, {"src/shout.py": "def shout():\n    return 'HI'\n"})
        before = git(self.root, "rev-parse", f"refs/heads/{self.branch}")
        result = self.apply([
            view(1, touches="core", added="The core says goodbye.", title="Say goodbye"),
            view(2, touches="core", changed="The greeting can be shouted.", title="Shout"),
        ])
        self.assertTrue(result.committed, result)
        self.assertNotEqual(git(self.root, "rev-parse", f"refs/heads/{self.branch}"), before)
        changelog = self.show("CHANGELOG.md")
        self.assertEqual(changelog.count("The core says goodbye."), 1)
        self.assertEqual(changelog.count("The greeting can be shouted."), 1)
        self.assertIn("### Added", changelog)
        self.assertIn("### Changed", changelog)
        self.assertRegex(changelog, r"piece 1")
        self.assertRegex(changelog, r"piece 2")
        self.assertNotIn("Section:", changelog)
        self.assertEqual(self.faults((1, 2)), [])
        # The changes folder holds nothing after the fold.
        listing = git(self.root, "ls-tree", "-r", "--name-only", f"refs/heads/{self.branch}")
        self.assertNotIn("changes/", listing)

    def test_added_and_changed_lines_reach_the_area_doc_and_removed_lines_leave_it(
            self) -> None:
        self.join(1, {"src/farewell.py": "def bye():\n    return 'bye'\n"})
        self.apply([view(1, touches="core", added="The core says goodbye.",
                         removed="The greeting is short.")])
        doc = self.show("docs/core.md")
        self.assertIn("The core says goodbye.", doc)
        self.assertNotIn("The greeting is short.", doc)
        self.assertIn("The greeting says hi.", doc)

    def test_a_new_area_is_added_to_the_map_the_overview_and_an_area_doc(self) -> None:
        self.join(1, {"billing/invoice.py": "def invoice():\n    return 1\n"})
        result = self.apply([view(1, touches="billing", added="Invoices exist.",
                                  new_area=("billing",), title="Add invoices")])
        self.assertTrue(result.committed)
        self.assertRegex(self.show("docs/area-map"), r"(?m)^billing/\s+billing$")
        overview = self.show("docs/overview.md")
        self.assertRegex(overview, r"(?m)^\| billing \|")
        self.assertIn("docs/billing.md", overview)
        self.assertIn("Invoices exist.", self.show("docs/billing.md"))
        self.assertEqual(self.faults((1,)), [])

    def test_a_second_run_of_the_docs_commit_changes_nothing(self) -> None:
        self.join(1, {"src/farewell.py": "def bye():\n    return 'bye'\n"})
        pieces = [view(1, touches="core", added="The core says goodbye.")]
        first = self.apply(pieces)
        head = git(self.root, "rev-parse", f"refs/heads/{self.branch}")
        second = self.apply(pieces)
        self.assertTrue(first.committed)
        self.assertFalse(second.committed)
        self.assertEqual(git(self.root, "rev-parse", f"refs/heads/{self.branch}"), head)

    def test_a_bug_piece_goes_under_fixed(self) -> None:
        self.join(1, {"src/greet.py": "def greet():\n    return 'hello'\n"})
        self.apply([view(1, touches="core", changed="The greeting no longer clips.",
                         issue_type="bug")])
        self.assertIn("### Fixed", self.show("CHANGELOG.md"))

    def test_the_branch_is_not_moved_when_the_records_check_fails(self) -> None:
        self.join(1, {"src/farewell.py": "def bye():\n    return 'bye'\n"})
        git(self.root, "worktree", "prune")
        # A piece names a doc that cannot exist: its area has no row in the overview.
        before = git(self.root, "rev-parse", f"refs/heads/{self.branch}")
        with self.assertRaises(integrate.IntegrationRefusal) as caught:
            self.apply([view(1, touches="nowhere", added="Something.")])
        self.assertTrue(caught.exception.next_command)
        self.assertEqual(git(self.root, "rev-parse", f"refs/heads/{self.branch}"), before)
        self.assertEqual(git(self.root, "worktree", "list", "--porcelain").count("worktree "),
                         1, "a scratch copy was left behind")

    def test_the_commit_has_no_piece_trailer_so_it_is_not_a_join(self) -> None:
        self.join(1, {"src/farewell.py": "def bye():\n    return 'bye'\n"})
        self.apply([view(1, touches="core", added="The core says goodbye.")])
        log = git(self.root, "log", "--format=%B", f"refs/heads/{self.branch}", "^main")
        self.assertEqual(integrate.trailers(log), [1])


if __name__ == "__main__":
    unittest.main()
