"""Keep gate command examples in skills accepted by the real parser."""
from __future__ import annotations

import re
import shlex
import unittest

import gate
from helpers import KIT


class SkillCommandTest(unittest.TestCase):
    def test_skill_and_brief_guidance_matches_the_spec_and_project(self):
        shape = (KIT / "skills" / "shape" / "SKILL.md").read_text()
        setup = (KIT / "skills" / "setup" / "SKILL.md").read_text()
        standards = (KIT / "briefs" / "standards-reviewer.md").read_text()
        builder = (KIT / "briefs" / "builder.md").read_text()
        ruff = (KIT.parent / "ruff.toml").read_text()

        self.assertIn("numbered Contract items", shape)
        self.assertEqual(shape.count("<KIT>/agents/researcher.md"), 1)
        self.assertNotIn("researcher subagent", shape)
        self.assertNotIn("under Notes", shape)
        self.assertEqual(setup.count("**Quality commands**"), 1)
        self.assertEqual(standards.count("small fix to non-test project code"), 1)
        self.assertIn("When a CRAP command is configured", builder)
        self.assertIn('target-version = "py39"', ruff)
        self.assertNotIn("tests/lint.sh", ruff)
        self.assertNotIn("BORROWED.md", ruff)

    def test_every_documented_gate_command_parses(self):
        found = 0
        for skill in sorted((KIT / "skills").glob("*/SKILL.md")):
            text = skill.read_text()
            for snippet in re.findall(r"`([^`]*\bgate\.py\b[^`]*)`", text):
                match = re.search(r"\bgate\.py\s+(.+)", snippet)
                if not match:
                    continue
                replacements = {"<n>": "1", "<file>": "verdict.txt",
                                "<title>": "Example", "<why>": "reason"}
                argv = [replacements.get(token, token)
                        for token in shlex.split(match.group(1))]
                parsed = gate.build_parser().parse_args(argv)
                if parsed.cmd == "move" and parsed.to == "shaping":
                    self.assertIn("--type", argv,
                                  f"{skill}: move to shaping needs a typed reason")
                found += 1
        self.assertGreater(found, 0, "no gate commands were found in the skills")


if __name__ == "__main__":
    unittest.main()
