"""Unit tests for loop/spec.py: the one parser for the spec block."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import spec

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "specs"


def parse(name: str) -> dict:  # type: ignore[type-arg]
    return spec.parse((FIXTURES / name).read_text(encoding="utf-8")).to_dict()


class EveryFixtureHasTheSameFields(unittest.TestCase):
    def test_same_keys_for_every_fixture(self) -> None:
        names = ["full.md", "quick.md", "route-open.md", "no-markers.md", "example-issue.md"]
        keys = [sorted(parse(name)) for name in names]
        for other in keys[1:]:
            self.assertEqual(keys[0], other)

    def test_parsing_twice_gives_the_same_answer(self) -> None:
        self.assertEqual(parse("full.md"), parse("full.md"))

    def test_the_answer_is_plain_json(self) -> None:
        json.dumps(parse("full.md"))


class FullSpec(unittest.TestCase):
    def setUp(self) -> None:
        self.s = parse("full.md")

    def test_found_version_and_path(self) -> None:
        self.assertTrue(self.s["found"])
        self.assertEqual(self.s["version"], 1)
        self.assertEqual(self.s["path"], "full")

    def test_nothing_required_is_missing(self) -> None:
        self.assertEqual(self.s["missing"], [])

    def test_fields_hold_their_text(self) -> None:
        goal = "A user can rename a saved report from its menu."
        self.assertEqual(self.s["fields"]["goal"], goal)
        self.assertIn("Opening a report", self.s["fields"]["must_stay_the_same"])

    def test_flow_and_edge_case_ids(self) -> None:
        self.assertEqual([f["id"] for f in self.s["flow"]], ["FL-1", "FL-2"])
        self.assertEqual([e["id"] for e in self.s["edge_cases"]], ["EC-1", "EC-2"])
        self.assertEqual(self.s["ids"], ["FL-1", "FL-2", "EC-1", "EC-2"])
        self.assertEqual(self.s["duplicate_ids"], [])

    def test_edge_case_trigger_and_result_cross_a_line_break(self) -> None:
        first = self.s["edge_cases"][0]
        self.assertEqual(first["trigger"], "the new name is empty")
        self.assertIn("A name is needed", first["result"])

    def test_coverage_answered_and_not_applicable(self) -> None:
        cover = self.s["coverage"]
        self.assertEqual(sorted(cover), sorted(spec.COVERAGE_CATEGORIES))
        self.assertTrue(cover["empty states"]["not_applicable"])
        self.assertIn("a report always has a name", cover["empty states"]["answer"])
        self.assertFalse(cover["permissions"]["not_applicable"])
        self.assertEqual(self.s["unanswered_coverage"], [])

    def test_judge(self) -> None:
        judge = self.s["judge"]
        self.assertEqual(judge["kind"], "acceptance tests")
        self.assertEqual(judge["command"], "pytest tests/acceptance/test_rename.py")
        self.assertEqual(judge["runner"], "pytest")
        self.assertEqual(judge["proves"], ["FL-1", "FL-2", "EC-1", "EC-2"])
        self.assertFalse(self.s["route_open"])

    def test_links_and_changes(self) -> None:
        self.assertEqual(self.s["links"]["touches"], ["reports", "menus"])
        self.assertEqual(self.s["changes"]["docs"], ["docs/reports.md"])
        self.assertEqual(self.s["changes"]["new_area"], ["report-menu"])

    def test_lists(self) -> None:
        self.assertEqual(self.s["sensitive_areas"], [])
        self.assertEqual(len(self.s["decisions"]), 1)
        self.assertEqual(len(self.s["open_questions"]), 1)

    def test_text_after_the_end_marker_is_not_in_the_spec(self) -> None:
        self.assertNotIn("Needs", json.dumps(self.s["fields"]))


class QuickPathSpec(unittest.TestCase):
    def test_quick_path_needs_only_its_own_fields(self) -> None:
        s = parse("quick.md")
        self.assertEqual(s["path"], "quick")
        self.assertEqual(s["missing"], [])
        self.assertFalse(s["fields"]["user_story"])
        self.assertEqual(s["judge"]["runner"], "npm")

    def test_quick_path_without_a_judge_is_missing_it(self) -> None:
        text = (FIXTURES / "quick.md").read_text(encoding="utf-8")
        cut = text.replace("## Judge", "## Something else")
        self.assertIn("judge", spec.parse(cut).to_dict()["missing"])


class RouteOpenSpec(unittest.TestCase):
    def test_route_open_is_marked(self) -> None:
        s = parse("route-open.md")
        self.assertTrue(s["route_open"])
        self.assertEqual(s["judge"]["hypotheses"], ["add an index", "cache the last query"])
        held_out = "fingerprint 77aa11b (stored outside git; gate only)"
        self.assertEqual(s["judge"]["held_out"], held_out)


class SpecWithNoMarkers(unittest.TestCase):
    def test_no_markers_is_not_an_error(self) -> None:
        s = parse("no-markers.md")
        self.assertFalse(s["found"])
        self.assertIsNone(s["version"])
        self.assertEqual(s["fields"]["goal"], "")
        self.assertIn("goal", s["missing"])

    def test_an_empty_body_is_the_same(self) -> None:
        self.assertFalse(spec.parse("").to_dict()["found"])


class RefusedSpecs(unittest.TestCase):
    def test_unknown_version_is_refused_with_a_next_line(self) -> None:
        with self.assertRaises(spec.SpecError) as caught:
            spec.parse((FIXTURES / "unknown-version.md").read_text(encoding="utf-8"))
        self.assertIn("version 7", str(caught.exception))
        self.assertIn("kit/spec-format.md", caught.exception.next_command)
        self.assertTrue(caught.exception.refused)

    def test_a_block_that_never_ends_is_a_fault(self) -> None:
        with self.assertRaises(spec.SpecError) as caught:
            spec.parse((FIXTURES / "unclosed.md").read_text(encoding="utf-8"))
        self.assertIn("spec:end", str(caught.exception))

    def test_markers_inside_a_code_fence_do_not_count(self) -> None:
        s = parse("fenced-markers.md")
        self.assertEqual(s["fields"]["goal"], "The real block is read.")

    def test_two_blocks_are_a_fault(self) -> None:
        one = (FIXTURES / "quick.md").read_text(encoding="utf-8")
        with self.assertRaises(spec.SpecError):
            spec.parse(one + one)


class DesignExampleIssue(unittest.TestCase):
    def setUp(self) -> None:
        self.s = parse("example-issue.md")

    def test_fields(self) -> None:
        self.assertEqual(self.s["version"], 1)
        self.assertEqual(self.s["path"], "full")
        self.assertEqual(self.s["missing"], [])
        self.assertEqual(self.s["ids"], ["FL-1", "FL-2", "FL-3", "EC-1", "EC-2"])
        self.assertEqual(self.s["judge"]["proves"], ["FL-1", "FL-2", "FL-3", "EC-1", "EC-2"])
        self.assertEqual(self.s["judge"]["runner"], "npm")
        self.assertEqual(self.s["links"]["touches"], ["invoices", "export"])
        self.assertEqual(self.s["changes"]["docs"], ["docs/invoices.md"])
        self.assertEqual(self.s["unanswered_coverage"], [])

    def test_open_question_and_decisions(self) -> None:
        self.assertEqual(len(self.s["open_questions"]), 1)
        self.assertIn("cancelled invoices", self.s["open_questions"][0])
        self.assertEqual(len(self.s["decisions"]), 2)

    def test_edge_case_two_has_its_example_value(self) -> None:
        self.assertIn("-40.00", self.s["edge_cases"][1]["result"])


class OneParser(unittest.TestCase):
    def test_no_other_script_reads_the_markers(self) -> None:
        """loop/spec.py is the only module under kit/scripts/ that names a marker."""
        found = subprocess.run(
            ["grep", "-rlE", "spec:(start|end)", str(ROOT / "kit" / "scripts")],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        found = [p for p in found if not p.endswith(".pyc")]
        self.assertEqual(found, [str(ROOT / "kit" / "scripts" / "loop" / "spec.py")])


if __name__ == "__main__":
    unittest.main()
