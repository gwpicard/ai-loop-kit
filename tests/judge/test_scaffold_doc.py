"""Setup leads an empty project to a scaffold spec the gate recognises."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "kit"
sys.path.insert(0, str(KIT / "scripts"))

from spec import parse_spec  # noqa: E402


class ScaffoldDocTest(unittest.TestCase):
    def test_D1_setup_links_to_a_supported_scaffold_example(self):
        setup = (KIT / "skills/setup/SKILL.md").read_text()
        self.assertTrue("<KIT>/examples/scaffold.md" in setup,
                        "setup must link directly to the scaffold example")
        guide = (KIT / "examples/scaffold.md").read_text()
        examples = re.findall(r"```markdown\n(.*?)```", guide, re.DOTALL)
        self.assertEqual(len(examples), 1)
        spec = parse_spec(examples[0])
        self.assertEqual(spec.kind, "scaffold")
        self.assertEqual(spec.checks[0]["legacy_kind"], "scaffold")
        self.assertEqual(spec.command, "python3 -m unittest discover -s tests -v")
        self.assertEqual(list(spec.done_when), ["D1"])
        self.assertIn("## Risks", examples[0])
        self.assertIn("## Exit", guide)
        self.assertNotIn("## Exit", examples[0])


if __name__ == "__main__":
    unittest.main()
