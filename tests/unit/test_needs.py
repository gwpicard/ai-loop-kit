"""Unit tests for loop/needs.py: the computed needs list.

Each need in the design's needs table appears when its field is missing, and
clears when the field is written.
"""

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import needs

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "specs"

JUDGE_TWO_LINES = (
    "Kind: acceptance tests, first commit 1a2b3c4 on the piece branch\n"
    "Command: pytest tests/acceptance/test_rename.py\n"
)


def done_spec() -> str:
    """The full fixture, with its open question answered and the judge seen failing."""
    body = (FIXTURES / "full.md").read_text(encoding="utf-8")
    body = body.replace(
        "- Should a rename be undoable? Why it matters: users slip. "
        "Recommended: no.\n  Who: the person.",
        "None.",
    )
    body = body.replace(
        "Proves: FL-1, FL-2, EC-1, EC-2",
        "Proves: FL-1, FL-2, EC-1, EC-2\nFails today: 4 of 4 fail on their "
        "assertion; main at a1b2c3d; 5 October 2026 (written by the gate)",
    )
    body = body.replace(
        "- The folder rename uses the same rule. Source: src/folders/rename.ts.",
        "- The folder rename uses the same rule. Source: src/folders/rename.ts. "
        "Checked 3 October 2026. Rests on: fingerprint 4c1e9a2.",
    )
    return body


def swap(body: str, old: str, new: str) -> str:
    assert old in body, old
    return body.replace(old, new, 1)


def find(body: str, kind: str, **kwargs: Any) -> list[dict[str, Any]]:
    return [n for n in needs.needs_from_body(body, **kwargs) if n["kind"] == kind]


class Baseline(unittest.TestCase):
    def test_a_finished_spec_has_no_need(self) -> None:
        self.assertEqual(needs.needs_from_body(done_spec()), [])

    def test_every_need_has_the_table_columns(self) -> None:
        body = (FIXTURES / "full.md").read_text(encoding="utf-8")
        found = needs.needs_from_body(body)
        self.assertTrue(found)
        for need in found:
            self.assertEqual(sorted(need), ["kind", "needs_you", "text", "who"])
            self.assertIsInstance(need["needs_you"], bool)

    def test_no_spec_needs_the_goal_the_story_and_the_flow(self) -> None:
        found = find("Just an idea.", "missing_core")
        self.assertEqual(len(found), 3)
        self.assertTrue(all(n["needs_you"] for n in found))

    def test_the_example_issue_has_the_open_question_need(self) -> None:
        body = (FIXTURES / "example-issue.md").read_text(encoding="utf-8")
        self.assertEqual(len(find(body, "open_question")), 1)


class CoreFields(unittest.TestCase):
    def test_each_core_field_appears_then_clears(self) -> None:
        for heading in ("Goal", "User story", "Expected flow"):
            body = swap(done_spec(), f"## {heading}", f"## X{heading}")
            found = find(body, "missing_core")
            self.assertTrue(any(heading in n["text"] for n in found), heading)
            self.assertTrue(all(n["needs_you"] and "person" in n["who"] for n in found))
            self.assertEqual(find(done_spec(), "missing_core"), [])

    def test_the_quick_path_does_not_need_a_user_story(self) -> None:
        body = (FIXTURES / "quick.md").read_text(encoding="utf-8")
        self.assertEqual(find(body, "missing_core"), [])


class Coverage(unittest.TestCase):
    def test_appears_then_clears(self) -> None:
        body = swap(done_spec(), "Errors: EC-1 and EC-2.\n", "")
        found = find(body, "coverage")
        self.assertEqual(len(found), 1)
        self.assertIn("errors", found[0]["text"].lower())
        self.assertTrue(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "coverage"), [])

    def test_not_applicable_without_a_reason(self) -> None:
        body = swap(
            done_spec(), "not applicable, because a report always has a name.", "Not applicable."
        )
        self.assertEqual(len(find(body, "coverage")), 1)


class IdTrace(unittest.TestCase):
    def test_appears_then_clears(self) -> None:
        body = swap(done_spec(), "Proves: FL-1, FL-2, EC-1, EC-2", "Proves: FL-1, FL-2, EC-1")
        found = find(body, "id_trace")
        self.assertTrue(found)
        self.assertFalse(any(n["needs_you"] for n in found))
        self.assertEqual(found[0]["who"], "the agent")
        self.assertEqual(find(done_spec(), "id_trace"), [])

    def test_an_id_no_test_names(self) -> None:
        tests = {"test_a": "FL-1 FL-2", "test_b": "EC-1"}
        self.assertTrue(find(done_spec(), "id_trace", tests=tests))
        tests["test_c"] = "EC-2"
        self.assertEqual(find(done_spec(), "id_trace", tests=tests), [])


class LimitsMustFollow(unittest.TestCase):
    def test_each_appears_then_clears(self) -> None:
        for heading in ("Limits", "Must stay the same", "Follow"):
            body = swap(done_spec(), f"## {heading}", f"## X{heading}")
            found = find(body, "missing_draft")
            self.assertTrue(any(heading in n["text"] for n in found), heading)
            self.assertTrue(all(n["needs_you"] for n in found))
            self.assertIn("confirms", found[0]["who"])
        self.assertEqual(find(done_spec(), "missing_draft"), [])


class TestLists(unittest.TestCase):
    def test_two_lists_that_differ(self) -> None:
        lists = [["FL-1", "FL-2", "EC-1", "EC-2"], ["FL-1", "FL-2", "EC-1"]]
        found = find(done_spec(), "test_lists_differ", test_lists=lists)
        self.assertEqual(len(found), 1)
        self.assertIn("EC-2", found[0]["text"])
        self.assertFalse(found[0]["needs_you"])

    def test_two_lists_that_agree(self) -> None:
        same = ["FL-1", "FL-2", "EC-1", "EC-2"]
        self.assertEqual(find(done_spec(), "test_lists_differ", test_lists=[same, same]), [])

    def test_no_lists_means_no_need_yet(self) -> None:
        self.assertEqual(find(done_spec(), "test_lists_differ"), [])


class Judge(unittest.TestCase):
    def test_no_judge_appears_then_clears(self) -> None:
        body = swap(done_spec(), JUDGE_TWO_LINES, "")
        found = find(body, "no_judge")
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "no_judge"), [])

    def test_a_missing_command_is_a_missing_judge(self) -> None:
        body = swap(done_spec(), "Command: pytest tests/acceptance/test_rename.py\n", "")
        self.assertEqual(len(find(body, "no_judge")), 1)

    def test_a_metric_judge_needs_the_person(self) -> None:
        body = swap(done_spec(), JUDGE_TWO_LINES, "Kind: metric\n")
        found = find(body, "no_judge")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["needs_you"])

    def test_a_reference_judge_needs_the_person(self) -> None:
        body = swap(done_spec(), JUDGE_TWO_LINES, "Kind: reference, the live site\n")
        self.assertTrue(find(body, "no_judge")[0]["needs_you"])


class JudgeNotFailing(unittest.TestCase):
    def test_appears_then_clears(self) -> None:
        body = swap(done_spec(), "Fails today:", "Seen:")
        found = find(body, "judge_not_failing")
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["needs_you"])
        self.assertIn("gate", found[0]["who"])
        self.assertEqual(find(done_spec(), "judge_not_failing"), [])

    def test_no_judge_gives_one_need_not_two(self) -> None:
        body = swap(done_spec(), "Command: pytest tests/acceptance/test_rename.py\n", "")
        self.assertEqual(find(body, "judge_not_failing"), [])


class OpenQuestions(unittest.TestCase):
    def test_one_need_for_each_question(self) -> None:
        body = swap(
            done_spec(),
            "## Open questions\nNone.",
            "## Open questions\n- Why? Who: the person.\n- How? Who: the person.",
        )
        found = find(body, "open_question")
        self.assertEqual(len(found), 2)
        self.assertTrue(all(n["needs_you"] and n["who"] == "the person only" for n in found))

    def test_none_clears_it(self) -> None:
        self.assertEqual(find(done_spec(), "open_question"), [])


class Research(unittest.TestCase):
    def test_a_finding_without_source_date_or_basis(self) -> None:
        for old, new in (
            ("Source: src/folders/rename.ts. ", ""),
            ("Checked 3 October 2026. ", ""),
            ("Rests on: fingerprint 4c1e9a2.", ""),
        ):
            body = swap(done_spec(), old, new)
            found = find(body, "research_gap")
            self.assertEqual(len(found), 1, old)
            self.assertFalse(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "research_gap"), [])

    def test_a_basis_the_claim_cannot_read_is_a_gap(self) -> None:
        for basis in ("the docs", "package version 4.2", "fingerprint nonsense"):
            body = swap(done_spec(), "Rests on: fingerprint 4c1e9a2.", f"Rests on: {basis}.")
            found = find(body, "research_gap")
            self.assertEqual(len(found), 1, basis)
            self.assertIn("what it rests on", found[0]["text"])

    def test_a_date_not_on_the_calendar_is_a_gap(self) -> None:
        body = swap(done_spec(), "Checked 3 October 2026.", "Checked 31 February 2026.")
        found = find(body, "research_gap")
        self.assertEqual(len(found), 1)
        self.assertIn("a date", found[0]["text"])

    def test_the_example_issue_finding_is_whole(self) -> None:
        body = (FIXTURES / "example-issue.md").read_text(encoding="utf-8")
        self.assertEqual(find(body, "research_gap"), [])

    def test_an_iso_date_counts(self) -> None:
        body = swap(done_spec(), "Checked 3 October 2026.", "Checked 2026-10-03.")
        self.assertEqual(find(body, "research_gap"), [])


class Dependencies(unittest.TestCase):
    def test_an_unresolved_dependency(self) -> None:
        found = find(
            done_spec(),
            "unresolved_dependency",
            unresolved_dependencies=["blocked by 77, which does not exist"],
        )
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "unresolved_dependency"), [])


class SensitiveAreas(unittest.TestCase):
    def test_an_area_with_no_acceptance(self) -> None:
        body = swap(
            done_spec(),
            "## Sensitive areas\nNone.",
            "## Sensitive areas\n- Payments. Risk notice given.",
        )
        found = find(body, "sensitive_area")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["needs_you"])
        self.assertEqual(found[0]["who"], "the person only")

    def test_an_area_with_acceptance_clears(self) -> None:
        body = swap(
            done_spec(),
            "## Sensitive areas\nNone.",
            '## Sensitive areas\n- Payments. Risk notice given. Accepted: "I accept '
            'this risk", the person, 4 October 2026.',
        )
        self.assertEqual(find(body, "sensitive_area"), [])

    def test_acceptance_without_a_date_is_not_enough(self) -> None:
        body = swap(
            done_spec(),
            "## Sensitive areas\nNone.",
            '## Sensitive areas\n- Payments. Accepted: "I accept this risk".',
        )
        self.assertEqual(len(find(body, "sensitive_area")), 1)


class LintGaps(unittest.TestCase):
    def test_a_refused_phrase_becomes_a_need(self) -> None:
        body = swap(
            done_spec(),
            "Names have at most 80 characters.",
            "Names have at most 80 characters, TBD.",
        )
        found = find(body, "lint_gap")
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "lint_gap"), [])

    def test_a_missing_field_the_table_does_not_name(self) -> None:
        body = swap(done_spec(), "## How to observe it", "## X")
        found = find(body, "missing_field")
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["needs_you"])
        self.assertEqual(find(done_spec(), "missing_field"), [])


class NeedsYou(unittest.TestCase):
    def test_the_flag_follows_the_needs(self) -> None:
        self.assertFalse(needs.needs_you(needs.needs_from_body(done_spec())))
        body = (FIXTURES / "example-issue.md").read_text(encoding="utf-8")
        self.assertTrue(needs.needs_you(needs.needs_from_body(body)))

    def test_the_biggest_need_comes_first(self) -> None:
        order = [n["kind"] for n in needs.needs_from_body("Just an idea.")]
        self.assertEqual(order[0], "missing_core")


if __name__ == "__main__":
    unittest.main()
