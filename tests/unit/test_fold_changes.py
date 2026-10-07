"""Unit tests for kit/scripts/fold-changes.py: where an entry goes in CHANGELOG.md.

`tests/fold-at-merge-rehearsal.sh` runs the whole fold against real history. These tests
read the placement alone: the day, the section and the order of the sections.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load() -> ModuleType:
    path = ROOT / "kit" / "scripts" / "fold-changes.py"
    spec = importlib.util.spec_from_file_location("fold_changes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fold_changes"] = module
    spec.loader.exec_module(module)
    return module


fold_changes = load()
START = "# Changelog\n\nOne entry for each piece.\n"


class FoldTest(unittest.TestCase):
    def test_a_new_day_gets_its_sections_in_the_order_of_the_template(self) -> None:
        text = fold_changes.fold(START, [("2026-10-07", "Fixed", "- A fix."),
                                         ("2026-10-07", "Added", "- An addition."),
                                         ("2026-10-07", "Removed", "- A removal.")])
        order = [line for line in text.splitlines() if line.startswith("###")]
        self.assertEqual(order, ["### Added", "### Removed", "### Fixed"])
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_an_entry_joins_the_section_it_names_on_a_day_that_exists(self) -> None:
        first = fold_changes.fold(START, [("2026-10-07", "Added", "- One.")])
        text = fold_changes.fold(first, [("2026-10-07", "Added", "- Two."),
                                         ("2026-10-07", "Changed", "- Three.")])
        lines = text.splitlines()
        self.assertEqual(lines.count("## 2026-10-07"), 1)
        self.assertEqual(lines.count("### Added"), 1)
        self.assertLess(lines.index("- Two."), lines.index("- One."), "newest first")
        self.assertLess(lines.index("### Added"), lines.index("### Changed"))
        self.assertLess(lines.index("- One."), lines.index("### Changed"))

    def test_a_section_that_comes_earlier_is_put_before_one_that_is_there(self) -> None:
        first = fold_changes.fold(START, [("2026-10-07", "Fixed", "- A fix.")])
        text = fold_changes.fold(first, [("2026-10-07", "Added", "- An addition.")])
        lines = text.splitlines()
        self.assertLess(lines.index("### Added"), lines.index("### Fixed"))

    def test_an_entry_with_no_section_goes_to_the_top_of_the_day_as_before(self) -> None:
        first = fold_changes.fold(START, [("2026-10-07", None, "- Old style.")])
        text = fold_changes.fold(first, [("2026-10-07", None, "- Newer.")])
        lines = text.splitlines()
        self.assertEqual(lines.count("## 2026-10-07"), 1)
        self.assertLess(lines.index("- Newer."), lines.index("- Old style."))
        self.assertNotIn("###", text)

    def test_a_newer_day_goes_above_an_older_one(self) -> None:
        first = fold_changes.fold(START, [("2026-10-05", "Added", "- Old.")])
        text = fold_changes.fold(first, [("2026-10-07", "Added", "- New.")])
        lines = text.splitlines()
        self.assertLess(lines.index("## 2026-10-07"), lines.index("## 2026-10-05"))

    def test_a_comment_with_an_example_heading_is_not_a_day(self) -> None:
        text = fold_changes.fold(START + "\n<!-- Example:\n\n## 2026-07-14\n\n### Added\n\n"
                                 "- Example.\n-->\n", [("2026-10-07", "Added", "- Real.")])
        self.assertIn("- Real.", text)
        self.assertEqual(text.count("- Example."), 1)
        self.assertGreater(text.index("## 2026-10-07"), text.index("-->"))


class OwnEntriesTest(unittest.TestCase):
    def test_the_entries_a_branch_holds_and_main_lacks_keep_their_day_and_section(self) -> None:
        main = fold_changes.fold(START, [("2026-10-07", "Added", "- From main.")])
        branch = fold_changes.fold(main, [("2026-10-07", "Changed", "- Own change."),
                                          ("2026-10-08", "Added", "- Own addition.")])
        texts = {"branch": branch, "main": main}
        with mock.patch.object(fold_changes, "_read_changelog", lambda ref: texts[ref]):
            found = fold_changes.own_entries("branch", "main")
        self.assertEqual(sorted(found), [("2026-10-07", "Changed", "- Own change."),
                                         ("2026-10-08", "Added", "- Own addition.")])


if __name__ == "__main__":
    unittest.main()
