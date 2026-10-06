"""Unit tests for loop/areas.py: the area map in the style of a CODEOWNERS file."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import areas  # noqa: E402
from loop.paths import Paths  # noqa: E402

MAP = """# a comment

docs/            project-records
src/             app
src/billing/     billing
*.md             project-records
/lib/util.py     shared
**/fixtures/**   test-data
"""


class Parsing(unittest.TestCase):
    def test_comments_and_blank_lines_are_ignored(self) -> None:
        rules = areas.parse(MAP)
        self.assertEqual([r.area for r in rules][:3], ["project-records", "app", "billing"])
        self.assertEqual(rules[0].line, 3)

    def test_names_keep_file_order_and_appear_once(self) -> None:
        self.assertEqual(
            areas.names(areas.parse(MAP)),
            ["project-records", "app", "billing", "shared", "test-data"],
        )

    def test_a_line_with_one_word_is_refused(self) -> None:
        with self.assertRaises(areas.AreaMapError) as caught:
            areas.parse("src/\n")
        self.assertIn("line 1", str(caught.exception))
        self.assertIn("docs/area-map", caught.exception.next_command)

    def test_prose_is_refused(self) -> None:
        with self.assertRaises(areas.AreaMapError):
            areas.parse("src/ the main app code\n")

    def test_an_area_name_with_a_colon_is_refused(self) -> None:
        with self.assertRaises(areas.AreaMapError):
            areas.parse("src/ app:main\n")


class Matching(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = areas.parse(MAP)

    def test_the_last_matching_rule_wins(self) -> None:
        self.assertEqual(areas.area_of(self.rules, "src/main.py"), "app")
        self.assertEqual(areas.area_of(self.rules, "src/billing/charge.py"), "billing")
        self.assertEqual(areas.area_of(self.rules, "src/notes.md"), "project-records")

    def test_a_folder_pattern_without_a_slash_in_front_matches_at_any_depth(self) -> None:
        self.assertEqual(areas.area_of(self.rules, "x/docs/a.txt"), "project-records")

    def test_a_pattern_with_a_leading_slash_is_fixed_to_the_root(self) -> None:
        self.assertEqual(areas.area_of(self.rules, "lib/util.py"), "shared")
        self.assertIsNone(areas.area_of(self.rules, "other/lib/util.py"))

    def test_double_star_crosses_folders(self) -> None:
        self.assertEqual(areas.area_of(self.rules, "a/b/fixtures/c/d.json"), "test-data")

    def test_a_path_given_with_dot_slash_is_found(self) -> None:
        self.assertEqual(areas.area_of(self.rules, "./src/main.py"), "app")

    def test_which_names_exempt_and_unclaimed_paths(self) -> None:
        self.assertEqual(areas.which(self.rules, "Makefile"), "exempt")
        self.assertEqual(areas.which(self.rules, ".github/x.yml"), "exempt")
        self.assertEqual(areas.which(self.rules, "changes/12.txt"), "exempt")
        self.assertEqual(areas.which(self.rules, "elsewhere/x.py"), "unclaimed")
        self.assertEqual(areas.which(self.rules, "src/main.py"), "app")


class Problems(unittest.TestCase):
    def test_a_true_map_has_no_problem(self) -> None:
        rules = areas.parse("src/ app\ndocs/ records\n")
        self.assertEqual(areas.problems(rules, ["src/a.py", "docs/b.md", "README.md"]), [])

    def test_a_file_in_no_area_is_named(self) -> None:
        rules = areas.parse("src/ app\n")
        found = areas.problems(rules, ["src/a.py", "tools/x.py"])
        self.assertEqual(len(found), 1)
        self.assertIn("tools/x.py", found[0])

    def test_an_area_that_matches_no_file_is_named_with_its_line(self) -> None:
        rules = areas.parse("src/ app\n\nghost/ ghosts\n")
        found = areas.problems(rules, ["src/a.py"])
        self.assertEqual(len(found), 1)
        self.assertIn("line 3", found[0])
        self.assertIn("ghosts", found[0])

    def test_a_shadowed_area_matches_no_file(self) -> None:
        rules = areas.parse("src/ app\nsrc/ other\n")
        self.assertIn("app", areas.problems(rules, ["src/a.py"])[0])


class Loading(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp())
        (base / "project" / "docs").mkdir(parents=True)
        self.paths = Paths.for_project(
            base / "project", data_base=base / "data", kit_folder=ROOT / "kit"
        )

    def test_paths_says_where_the_map_is(self) -> None:
        self.assertEqual(self.paths.area_map, self.paths.root / "docs" / "area-map")

    def test_a_missing_map_is_an_error_with_the_template_as_the_next_step(self) -> None:
        with self.assertRaises(areas.AreaMapError) as caught:
            areas.load(self.paths)
        self.assertIn("kit/templates/area-map", caught.exception.next_command)

    def test_a_missing_map_reads_as_empty_when_asked(self) -> None:
        self.assertEqual(areas.load_or_empty(self.paths), [])

    def test_the_template_is_a_valid_map(self) -> None:
        text = (ROOT / "kit" / "templates" / "area-map").read_text(encoding="utf-8")
        self.assertTrue(areas.parse(text))
        self.paths.area_map.write_text(text, encoding="utf-8")
        self.assertTrue(areas.load(self.paths))


if __name__ == "__main__":
    unittest.main()
