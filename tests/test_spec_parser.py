"""Guard the spec extraction, including existing parser quirks."""
from __future__ import annotations

import unittest
from dataclasses import asdict

from helpers import KIT

# isort: split
import loopkit
import review

INTENT = "## Intent\nKeep the result.\n\nOut of scope:\n- Display changes.\n"
CONTRACT = "## Contract\n- D1: Return the result.\n"
LEGACY = "## Judge\nCommand: `python judge.py`\nFiles: judge.py\n"
EXIT = "## Exit\n### Tests\nCommand: `python judge.py`\nFiles: judge.py\n"


class SpecParserTest(unittest.TestCase):
    def test_parser_has_its_own_module_and_loopkit_stays_small(self):
        # The extraction contract requires an independent parser below this ceiling.
        import spec
        from errors import Refused

        self.assertIs(loopkit.parse_spec, spec.parse_spec)
        self.assertIs(loopkit.Spec, spec.Spec)
        self.assertIs(loopkit.Refused, Refused)
        self.assertIs(spec.Refused, Refused)
        self.assertLess(len((KIT / "scripts/loopkit.py").read_text().splitlines()), 800)

    def test_legacy_and_exit_keep_the_same_contract_and_metadata(self):
        metadata = ("Keep: `python keep.py`\nPlaybook: fix\nSettings: may change\n"
                    "Large file: src/generated.py\nLarge file: src/generated.py\n")
        legacy = loopkit.parse_spec(INTENT + CONTRACT + LEGACY + metadata)
        modern = loopkit.parse_spec(INTENT + CONTRACT + EXIT + "## Judge\n" + metadata)
        for parsed in (legacy, modern):
            self.assertEqual(parsed.done_when, {"D1": "Return the result."})
            self.assertEqual(parsed.intent, "Keep the result.")
            self.assertEqual(parsed.out_of_scope, ("Display changes.",))
            self.assertEqual(parsed.command, "python judge.py")
            self.assertEqual(parsed.files, ["judge.py"])
            self.assertEqual(parsed.keep, "python keep.py")
            self.assertEqual(parsed.playbook, "fix")
            self.assertTrue(parsed.settings)
            self.assertEqual(parsed.large_files, ("src/generated.py",))
        left, right = asdict(legacy), asdict(modern)
        for key in ("kind", "checks"):
            left.pop(key)
            right.pop(key)
        self.assertEqual(left, right)

    def test_refusal_text_order_and_next_step_are_unchanged(self):
        cases = [
            ("", "no '## Intent' section; no '## Contract' section; "
             "no '## Exit' or '## Judge' section"),
            (INTENT + CONTRACT + LEGACY +
             "Playbook: other\nSettings: no\nLarge file: ../large.py\nFiles: /judge.py\n",
             "'Playbook:' must be 'fix'; 'Settings: no' is unknown; "
             "use 'Settings: may change'; 'Large file:' must name a path inside the project; "
             "judge file '/judge.py' must be a path inside the project"),
            (INTENT + CONTRACT + "## Exit\n### Tests\nFiles: ../judge.py\n",
             "Tests exit checks need 'Command:' and files under 'Files:'; "
             "exit file '../judge.py' must be a path inside the project"),
            (INTENT + CONTRACT + "## Exit\n",
             "'## Exit' has no checks; '## Exit' has no valid checks"),
            (INTENT + CONTRACT + "- D1: Again.\n" + LEGACY,
             "spec ID D1 is used twice"),
        ]
        for body, gaps in cases:
            with self.subTest(body=body), self.assertRaises(loopkit.Refused) as caught:
                loopkit.parse_spec(body)
            self.assertEqual(caught.exception.reason, "the spec is incomplete: " + gaps)
            self.assertEqual(str(caught.exception), caught.exception.reason)
            self.assertEqual(caught.exception.next_step,
                             "fix the issue body to match kit/spec-format.md")

    def test_duplicate_metadata_and_all_stays_keep_existing_behaviour(self):
        for judge in (LEGACY, EXIT + "## Judge\n"):
            parsed = loopkit.parse_spec(
                INTENT + CONTRACT.replace("D1:", "D1 (stays):") + judge +
                "Keep: first\nKeep: last\nPlaybook: fix\nPlaybook:\n")
            self.assertEqual(parsed.keep, "last")
            self.assertEqual(parsed.playbook, "")
            self.assertEqual(parsed.stays, ("D1",))

    def test_mixed_files_and_criteria_preserve_list_state(self):
        parsed = loopkit.parse_spec(INTENT + CONTRACT +
                                   "## Exit\n### Critics\nCapture: render\nReference: ref.png\n"
                                   "Criteria:\n- Clear\nFiles:\n- render.py\n"
                                   "Criteria:\n- More\n")
        self.assertEqual(parsed.criteria, ("Clear",))
        self.assertEqual(parsed.files, ["render.py", "More"])

    def test_section_reader_preserves_raw_lines_empty_and_missing_sections(self):
        body = "  ## ReSeArCh  \n raw \n### Child\n\n## Stop\nignored"
        expected = [" raw ", "### Child", ""]
        self.assertEqual(loopkit._section(body, "Research"), expected)
        self.assertEqual(review.contract_research(body),
                         "  ## ReSeArCh  \n raw \n### Child\n")
        self.assertEqual(loopkit._section("## Research\n## Stop", "Research"), [])
        self.assertEqual(review.contract_research("## Research\n## Stop"), "## Research")
        self.assertIsNone(loopkit._section("## Other", "Research"))
        self.assertEqual(review.contract_research("## Other"), "No outside findings.")
        self.assertEqual(loopkit._section("## Research\nfirst\n## Research\nlast", "Research"),
                         ["first"])


if __name__ == "__main__":
    unittest.main()
