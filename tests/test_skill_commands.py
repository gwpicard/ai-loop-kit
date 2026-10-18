"""Keep gate command examples in skills accepted by the real parser."""
from __future__ import annotations

import re
import shlex
import unittest

import gate
from helpers import KIT


class SkillCommandTest(unittest.TestCase):
    def test_mutation_guidance_explains_adapter_permission_and_commit_rule(self):
        for path in (KIT / "spec-format.md", KIT / "skills" / "shape" / "SKILL.md"):
            text = " ".join(path.read_text().split())
            for wording in (
                "name its path in Contract so the builder may strengthen it",
                "Keep the adapter out of Exit `Files:`",
                "those files are frozen at ready",
                "selects functions from committed `base...HEAD` changes",
                "before committing may find no changed functions",
                "final gate evidence comes after the runner commits the attempt",
            ):
                with self.subTest(path=path.relative_to(KIT), wording=wording):
                    self.assertIn(wording, text)

    def test_skill_and_brief_guidance_matches_the_spec_and_project(self):
        shape = (KIT / "skills" / "shape" / "SKILL.md").read_text()
        setup = (KIT / "skills" / "setup" / "SKILL.md").read_text()
        standards = (KIT / "briefs" / "standards-reviewer.md").read_text()
        builder = (KIT / "briefs" / "builder.md").read_text()
        ruff = (KIT.parent / "ruff.toml").read_text()

        self.assertIn("numbered Contract items", shape)
        self.assertIn("session.py\" --role researcher", shape)
        self.assertIn("session.py\" --role judge-writer", shape)
        self.assertIn("If web tools are unavailable, stop shaping", shape)
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
        for skill in sorted((KIT / "skills").rglob("*.md")):
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

    def test_run_skill_classifies_rejected_pull_requests(self):
        text = (KIT / "skills" / "reject-handling" / "SKILL.md").read_text()

        self.assertIn("was something missing from the contract", text.lower())
        self.assertIn("--type judge-gap", text)
        self.assertIn("--type person-rejected", text)
        self.assertIn("taste", text.lower())


if __name__ == "__main__":
    unittest.main()
