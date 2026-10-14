"""Unit tests for loop/lint.py: the spec lint. It judges a spec and runs nothing."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import lint

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "specs"

EC2 = (
    'EC-2 When the new name is "Q3 plan" and that name exists, then the user sees\n'
    '"Q3 plan is taken".'
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def clean_full() -> str:
    """The full fixture. No gap stands in it."""
    return fixture("full.md")


def rules(body: str, **kwargs: object) -> list[str]:
    return [gap["rule"] for gap in lint.lint_body(body, **kwargs)]  # type: ignore[arg-type]


def messages(body: str, **kwargs: object) -> str:
    return " | ".join(g["message"] for g in lint.lint_body(body, **kwargs))  # type: ignore[arg-type]


def swap(body: str, old: str, new: str) -> str:
    assert old in body, old
    return body.replace(old, new, 1)


class CleanSpecs(unittest.TestCase):
    def test_the_full_fixture_has_no_gap(self) -> None:
        self.assertEqual(lint.lint_body(clean_full()), [])

    def test_the_quick_fixture_has_no_gap(self) -> None:
        self.assertEqual(lint.lint_body(fixture("quick.md")), [])

    def test_every_gap_names_a_rule_a_message_and_a_next_step(self) -> None:
        gaps = lint.lint_body(swap(clean_full(), "## Goal", "## Aim"))
        self.assertTrue(gaps)
        for gap in gaps:
            self.assertEqual(sorted(gap), ["message", "next", "rule"])
            self.assertTrue(gap["message"] and gap["next"])

    def test_linting_twice_gives_the_same_answer(self) -> None:
        body = swap(clean_full(), "## Goal", "## Aim")
        self.assertEqual(lint.lint_body(body), lint.lint_body(body))


class RequiredFields(unittest.TestCase):
    def test_a_missing_field_on_the_full_path(self) -> None:
        body = swap(clean_full(), "## Follow", "## Imitate")
        self.assertIn("required_field", rules(body))
        self.assertIn("Follow", messages(body))

    def test_a_field_the_quick_path_does_not_need_is_not_required_there(self) -> None:
        self.assertNotIn("required_field", rules(fixture("quick.md")))

    def test_a_field_the_quick_path_needs_is_required_there(self) -> None:
        body = swap(fixture("quick.md"), "## Links", "## Pointers")
        self.assertIn("required_field", rules(body))
        self.assertIn("Links", messages(body))

    def test_no_spec_at_all_lists_every_required_field(self) -> None:
        gaps = lint.lint_body(fixture("no-markers.md"))
        self.assertEqual({g["rule"] for g in gaps}, {"required_field"})
        self.assertGreaterEqual(len(gaps), 14)


class Coverage(unittest.TestCase):
    def test_a_category_with_no_answer(self) -> None:
        body = swap(clean_full(), "Errors: EC-1 and EC-2.\n", "")
        self.assertIn("coverage", rules(body))
        self.assertIn("errors", messages(body).lower())

    def test_not_applicable_with_no_reason(self) -> None:
        body = swap(
            clean_full(), "not applicable, because a report always has a name.", "Not applicable."
        )
        self.assertIn("coverage", rules(body))

    def test_not_applicable_with_a_reason_passes(self) -> None:
        self.assertNotIn("coverage", rules(clean_full()))


class IdTrace(unittest.TestCase):
    def test_an_id_the_judge_does_not_prove(self) -> None:
        body = swap(clean_full(), "Proves: FL-1, FL-2, EC-1, EC-2", "Proves: FL-1, FL-2, EC-1")
        self.assertIn("id_trace", rules(body))
        self.assertIn("EC-2", messages(body))

    def test_a_proved_id_the_spec_does_not_hold(self) -> None:
        body = swap(
            clean_full(),
            "Proves: FL-1, FL-2, EC-1, EC-2",
            "Proves: FL-1, FL-2, EC-1, EC-2, EC-9",
        )
        self.assertIn("id_trace", rules(body))
        self.assertIn("EC-9", messages(body))

    def test_a_repeated_id(self) -> None:
        body = swap(clean_full(), "FL-2 They", "FL-1 They")
        self.assertIn("id_trace", rules(body))

    def test_a_line_with_no_id(self) -> None:
        body = swap(clean_full(), "FL-2 They choose", "They choose")
        self.assertIn("id_trace", rules(body))

    def test_tests_that_name_every_id_pass(self) -> None:
        tests = {"test_a": "FL-1 FL-2", "test_b": "EC-1", "test_c": "EC-2"}
        self.assertEqual(lint.lint_body(clean_full(), tests=tests), [])

    def test_an_id_no_test_names(self) -> None:
        tests = {"test_a": "FL-1 FL-2", "test_b": "EC-1"}
        body = clean_full()
        self.assertIn("id_trace", rules(body, tests=tests))
        self.assertIn("EC-2", messages(body, tests=tests))

    def test_a_test_that_names_no_id(self) -> None:
        tests = {"test_a": "FL-1 FL-2", "test_b": "EC-1", "test_c": "EC-2", "test_d": "nothing"}
        self.assertIn("test_d", messages(clean_full(), tests=tests))

    def test_a_test_may_carry_its_id_in_its_name(self) -> None:
        tests = {"test_FL-1_FL-2": "", "test_EC-1": "", "test_EC-2": ""}
        self.assertEqual(lint.lint_body(clean_full(), tests=tests), [])

    def test_reading_tests_from_source(self) -> None:
        source = (
            "def test_one():\n    # FL-1 FL-2\n    pass\n\n"
            "it('shows EC-1', () => {})\n"
            'test("EC-2 case", () => {})\n'
        )
        found = lint.read_tests(source)
        self.assertEqual(len(found), 3)
        self.assertIn("FL-1", found["test_one"])
        self.assertTrue(any("EC-1" in name for name in found))


class EdgeCases(unittest.TestCase):
    def test_a_case_with_no_then(self) -> None:
        body = swap(
            clean_full(),
            "EC-1 When the new name is empty, then the old name stays",
            "EC-1 When the new name is empty the old name stays",
        )
        self.assertIn("edge_case", rules(body))

    def test_a_case_that_does_not_open_with_when(self) -> None:
        body = swap(clean_full(), "EC-2 When the new name", "EC-2 If the new name")
        self.assertIn("edge_case", rules(body))

    def test_a_case_with_no_example_value(self) -> None:
        body = swap(
            clean_full(), EC2, "EC-2 When the new name exists, then the user sees a message."
        )
        self.assertIn("edge_case", rules(body))
        self.assertIn("example", messages(body))

    def test_a_number_counts_as_an_example_value(self) -> None:
        body = swap(
            clean_full(),
            EC2,
            "EC-2 When the new name has 81 characters, then the user sees a message.",
        )
        self.assertNotIn("edge_case", rules(body))


class Limits(unittest.TestCase):
    def test_a_limit_with_no_number(self) -> None:
        body = swap(clean_full(), "Speed: none.", "Speed matters.")
        self.assertIn("limits", rules(body))

    def test_none_counts(self) -> None:
        self.assertNotIn("limits", rules(clean_full()))

    def test_a_number_counts(self) -> None:
        body = swap(clean_full(), "Speed: none.", "Speed: 200 milliseconds.")
        self.assertNotIn("limits", rules(body))


class RefusedPhrases(unittest.TestCase):
    def test_each_refused_phrase_is_found(self) -> None:
        for phrase in ("TBD", "decide during build", "for now", "a few", "several", "consider"):
            body = swap(
                clean_full(),
                "Names have at most 80 characters.",
                f"Names have at most 80 characters, {phrase}.",
            )
            self.assertIn("refused_phrase", rules(body), phrase)

    def test_a_phrase_inside_a_code_span_is_allowed(self) -> None:
        body = swap(
            clean_full(),
            "Names have at most 80 characters.",
            "Names have at most 80 characters. The word `TBD` is shown as it is.",
        )
        self.assertNotIn("refused_phrase", rules(body))

    def test_a_phrase_inside_a_word_is_allowed(self) -> None:
        body = swap(
            clean_full(),
            "Names have at most 80 characters.",
            "Names have at most 80 characters. The file is atbdx.",
        )
        self.assertNotIn("refused_phrase", rules(body))

    def test_the_open_questions_may_use_the_words(self) -> None:
        body = swap(
            clean_full(), "Should a rename be undoable?", "Should a rename be undoable for now?"
        )
        self.assertNotIn("refused_phrase", rules(body))


class VagueAdjectives(unittest.TestCase):
    def test_a_vague_word_with_no_number(self) -> None:
        body = swap(
            clean_full(),
            "The report list shows the new name at once.",
            "The report list shows the new name and is fast.",
        )
        self.assertIn("vague_word", rules(body))
        self.assertIn("fast", messages(body))

    def test_a_number_in_the_same_sentence_passes(self) -> None:
        body = swap(
            clean_full(),
            "The report list shows the new name at once.",
            "The report list shows the new name and is fast, under 200 milliseconds.",
        )
        self.assertNotIn("vague_word", rules(body))

    def test_other_vague_words(self) -> None:
        for word in ("secure", "easy", "scalable", "intuitive", "robust"):
            body = swap(
                clean_full(),
                "The report list shows the new name at once.",
                f"The report list shows the new name in a {word} way.",
            )
            self.assertIn("vague_word", rules(body), word)


class BuildSteps(unittest.TestCase):
    def test_a_numbered_list_of_build_steps(self) -> None:
        body = swap(
            clean_full(),
            "## Not in this piece\nBulk rename.",
            "## Not in this piece\n1. Add the column.\n2. Write the handler.",
        )
        self.assertIn("build_steps", rules(body))

    def test_a_numbered_list_inside_a_code_fence_is_allowed(self) -> None:
        body = swap(
            clean_full(),
            "## Not in this piece\nBulk rename.",
            "## Not in this piece\n```\n1. Add the column.\n```",
        )
        self.assertNotIn("build_steps", rules(body))


class Length(unittest.TestCase):
    def long_body(self, extra: int) -> str:
        return swap(clean_full(), "Bulk rename.", "Bulk rename." + "\n- x" * extra)

    def test_too_long_for_a_chore(self) -> None:
        self.assertIn("length", rules(self.long_body(90), issue_type="chore"))

    def test_the_same_body_fits_a_feature(self) -> None:
        self.assertNotIn("length", rules(self.long_body(90), issue_type="feature"))

    def test_the_limits_are_80_120_and_250(self) -> None:
        self.assertEqual(lint.LENGTH_LIMITS, {"chore": 80, "bug": 120, "feature": 250})

    def test_the_default_type_is_a_feature(self) -> None:
        self.assertIn("length", rules(self.long_body(300)))

    def test_an_unknown_type_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            lint.lint_body(clean_full(), issue_type="epic")

    def test_the_gate_text_below_the_block_is_not_counted(self) -> None:
        body = clean_full() + "\n- need" * 400
        self.assertNotIn("length", rules(body, issue_type="chore"))


if __name__ == "__main__":
    unittest.main()
