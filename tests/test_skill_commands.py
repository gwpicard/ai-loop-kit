"""Keep gate command examples in skills accepted by the real parser."""
from __future__ import annotations

import re
import shlex
import unittest
from pathlib import Path

from helpers import KIT
import gate


class SkillCommandTest(unittest.TestCase):
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
