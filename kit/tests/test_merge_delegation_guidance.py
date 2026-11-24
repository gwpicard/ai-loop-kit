"""The merge delegation contract must be discoverable in shipped guidance."""
from pathlib import Path
import re
import unittest


KIT = Path(__file__).resolve().parents[1]


class MergeGuidanceTest(unittest.TestCase):
    def test_loop_skill_carries_merge_authority_and_its_boundaries(self):
        text = (KIT / "skills/loop/SKILL.md").read_text()
        self.assertRegex(text, r"loop merge\s+[^\n]+")
        self.assertRegex(text.lower(), r"without asking again|do not ask again|no further (?:approval|confirmation)")
        for pattern in (r"(?:never|do not)[^.\n]*publish[^.\n]*release",
                        r"(?:never|do not)[^.\n]*move[^.\n]*release branch",
                        r"(?:never|do not)[^.\n]*force.push",
                        r"(?:never|do not)[^.\n]*delete[^.\n]*branch"):
            self.assertRegex(re.sub(r"\s+", " ", text.lower()), pattern)

    def test_reference_documents_all_modes_the_default_and_the_command(self):
        text = (KIT / "README.md").read_text()
        self.assertIn("Final merge", text)
        for mode in ("person", "on request", "when green"):
            self.assertIn("`%s`" % mode, text)
        self.assertRegex(text, r"loop merge\s+[^\n]+")
        self.assertRegex(text.lower(), r"(?s)(?:person.{0,120}default|default.{0,120}person)")
