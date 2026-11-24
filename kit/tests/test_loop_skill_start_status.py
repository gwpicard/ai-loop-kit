from pathlib import Path
import re
import unittest


class LoopSkillStartStatusTest(unittest.TestCase):
    def test_start_instructions_require_reading_status_and_reporting_what_needs_the_person(self):
        text = (Path(__file__).resolve().parents[1] / "skills/loop/SKILL.md").read_text()
        paragraphs = re.split(r"\n\s*\n", text)
        instructions = [paragraph for paragraph in paragraphs
                        if "loop status" in paragraph and re.search(r"\b(start|starts|started|starting)\b", paragraph, re.I)]
        self.assertTrue(instructions, "after starting the loop, the skill must instruct the session to read loop status")
        instruction = "\n".join(instructions)
        self.assertRegex(instruction, r"(?i)\b(after|once|then)\b")
        self.assertRegex(instruction, r"(?i)\b(tell|report|summarise|show)\b")
        self.assertRegex(instruction, r"(?i)\b(person|user)\b")
        self.assertRegex(instruction, r"(?i)\b(needs|parked|parks|decisions)\b")
