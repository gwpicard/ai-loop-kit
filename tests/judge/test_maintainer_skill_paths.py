"""The maintainer skills name only files that exist in the repository."""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIXES = ("kit/", "docs/", "tests/", ".agents/")
PLACEHOLDERS = ("<", "*", "YYYY")
OUTPUT_FOLDER = ".agents/tmp/"
KEPT = ("humanizer", "release-notes", "review-issues", "review-public-docs",
        "writing-review")


def tracked(*patterns):
    out = subprocess.run(["git", "ls-files", *patterns], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return out.splitlines()


def named_paths(text):
    for span in re.findall(r"`([^`\n]+)`", text):
        if (span.startswith(PREFIXES) and not any(p in span for p in PLACEHOLDERS)
                and not span.startswith(OUTPUT_FOLDER) and not re.search(r"\s", span)):
            yield span


class MaintainerSkillPathsTest(unittest.TestCase):
    def test_D1_stack_research_is_gone(self):
        self.assertNotIn(".agents/maintainer-skills/stack-research/SKILL.md",
                         tracked(".agents/maintainer-skills"))
        self.assertFalse(
            (ROOT / ".agents/maintainer-skills/stack-research/SKILL.md").exists())
        self.assertNotIn("stack-research", (ROOT / "AGENTS.md").read_text())

    def test_D2_every_input_path_in_a_skill_exists(self):
        skills = tracked(".agents/maintainer-skills/*/SKILL.md")
        self.assertTrue(skills)
        missing = [f"{skill}: {path}" for skill in skills
                   for path in named_paths((ROOT / skill).read_text())
                   if not (ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_D2_output_folders_and_placeholders_are_not_checked(self):
        text = ("`.agents/tmp/public-docs-review/` `kit/<name>.md` `docs/*.md` "
                "`tests/YYYY.md` `kit/real.md` `kit/a b`")
        self.assertEqual(list(named_paths(text)), ["kit/real.md"])

    def test_D3_other_skills_stay(self):
        agents = (ROOT / "AGENTS.md").read_text()
        for name in KEPT:
            with self.subTest(name=name):
                self.assertTrue(
                    (ROOT / ".agents/maintainer-skills" / name / "SKILL.md").is_file())
                self.assertIn(f"`{name}`", agents)


if __name__ == "__main__":
    unittest.main()
