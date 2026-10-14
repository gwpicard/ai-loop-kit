"""The policy schema and its defaults (loop/policy.py)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import policy


def keys(problems: list[policy.Problem]) -> list[str]:
    return [problem.key for problem in problems]


class DefaultsTest(unittest.TestCase):
    def test_the_agreed_defaults(self) -> None:
        merged = policy.with_defaults({})
        self.assertEqual(merged["builder_cap"], 3)
        self.assertEqual(merged["attempt_limit"], 3)
        self.assertEqual(merged["review_rounds"], 2)
        self.assertEqual(merged["question_cap"], 5)
        self.assertEqual(merged["length_limits"], {"chore": 80, "bug": 120, "feature": 250})
        self.assertEqual(merged["billing"]["mode"], "subscription")
        self.assertIsNone(merged["billing"]["spend_cap_per_run_usd"])

    def test_an_empty_policy_is_valid(self) -> None:
        self.assertEqual(policy.validate({}), [])

    def test_a_given_value_beats_the_default(self) -> None:
        merged = policy.with_defaults({"builder_cap": 2, "length_limits": {"bug": 100}})
        self.assertEqual(merged["builder_cap"], 2)
        self.assertEqual(merged["length_limits"]["bug"], 100)
        self.assertEqual(merged["length_limits"]["feature"], 250)

    def test_the_template_is_valid_and_matches_the_defaults(self) -> None:
        template = Path(__file__).resolve().parents[2] / "kit" / "templates" / "policy.json"
        data = json.loads(template.read_text())
        self.assertEqual(policy.validate(data), [])
        self.assertEqual(policy.with_defaults(data), policy.with_defaults({}))

    def test_there_is_no_pre_approval_key(self) -> None:
        self.assertFalse([k for k in policy.DEFAULTS if "approv" in k or "merge" in k])


class ValueTest(unittest.TestCase):
    def test_a_wrong_type_names_the_key(self) -> None:
        self.assertEqual(keys(policy.validate({"builder_cap": "three"})), ["builder_cap"])

    def test_a_true_is_not_a_number(self) -> None:
        self.assertEqual(keys(policy.validate({"attempt_limit": True})), ["attempt_limit"])

    def test_a_number_out_of_range_names_the_key(self) -> None:
        self.assertEqual(keys(policy.validate({"builder_cap": 0})), ["builder_cap"])
        self.assertEqual(keys(policy.validate({"review_rounds": 99})), ["review_rounds"])

    def test_each_bad_key_is_named_once(self) -> None:
        found = keys(policy.validate({"builder_cap": 0, "question_cap": "x"}))
        self.assertEqual(sorted(found), ["builder_cap", "question_cap"])

    def test_nested_keys_are_named_with_a_dot(self) -> None:
        self.assertEqual(keys(policy.validate({"billing": {"mode": "free"}})), ["billing.mode"])
        self.assertEqual(
            keys(policy.validate({"length_limits": {"bug": "long"}})), ["length_limits.bug"]
        )

    def test_a_nested_object_must_be_an_object(self) -> None:
        self.assertEqual(keys(policy.validate({"billing": "api_key"})), ["billing"])

    def test_an_unknown_key_is_refused(self) -> None:
        problems = policy.validate({"builders": 3})
        self.assertEqual(keys(problems), ["builders"])
        self.assertIn("builder_cap", problems[0].message)

    def test_an_unknown_nested_key_is_refused(self) -> None:
        self.assertEqual(
            keys(policy.validate({"length_limits": {"epic": 500}})), ["length_limits.epic"]
        )

    def test_a_pre_approval_key_can_never_be_set(self) -> None:
        for name in ("merge_pre_approved", "pre_approved", "auto_merge"):
            problems = policy.validate({name: True})
            self.assertEqual(keys(problems), [name])
            self.assertIn("--merge-pre-approved", problems[0].message)

    def test_a_spend_cap_must_be_a_positive_number_or_null(self) -> None:
        good = {"billing": {"spend_cap_per_run_usd": 25.5, "spend_cap_per_piece_usd": None}}
        self.assertEqual(policy.validate(good), [])
        for bad in (0, -1, "5", True):
            self.assertEqual(
                keys(policy.validate({"billing": {"spend_cap_per_run_usd": bad}})),
                ["billing.spend_cap_per_run_usd"],
            )

    def test_an_api_key_needs_both_caps(self) -> None:
        missing = policy.validate({"billing": {"mode": "api_key"}})
        self.assertEqual(
            sorted(keys(missing)),
            ["billing.spend_cap_per_piece_usd", "billing.spend_cap_per_run_usd"],
        )
        full = {
            "billing": {
                "mode": "api_key",
                "spend_cap_per_piece_usd": 5,
                "spend_cap_per_run_usd": 20,
            }
        }
        self.assertEqual(policy.validate(full), [])

    def test_the_policy_must_be_an_object(self) -> None:
        self.assertEqual(keys(policy.validate([])), [""])


class LoadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())

    def write(self, text: str) -> Path:
        path = self.folder / "policy.json"
        path.write_text(text)
        return path

    def test_a_good_file_loads_with_defaults(self) -> None:
        loaded = policy.load(self.write('{"builder_cap": 2}'))
        self.assertEqual(loaded["builder_cap"], 2)
        self.assertEqual(loaded["attempt_limit"], 3)

    def test_a_missing_file_is_refused_by_name(self) -> None:
        with self.assertRaises(policy.PolicyError) as caught:
            policy.load(self.folder / "absent.json")
        self.assertIn("absent.json", str(caught.exception))

    def test_a_file_that_is_not_json_is_refused(self) -> None:
        with self.assertRaises(policy.PolicyError) as caught:
            policy.load(self.write("{not json"))
        self.assertIn("not valid JSON", str(caught.exception))

    def test_a_bad_value_is_refused_with_its_key(self) -> None:
        with self.assertRaises(policy.PolicyError) as caught:
            policy.load(self.write('{"question_cap": -2}'))
        self.assertEqual(keys(caught.exception.problems), ["question_cap"])
        self.assertIn("question_cap", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
