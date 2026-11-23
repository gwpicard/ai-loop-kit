"""Setup guidance covers migrations without a plan and fresh setup commits."""
from pathlib import Path
import unittest

import setup


class SetupSkillHandoverTest(unittest.TestCase):
    def test_restart_requires_only_the_applicable_migration_steps(self):
        skill = Path(setup.__file__).resolve().parents[1] / "skills/setup/SKILL.md"
        text = " ".join(skill.read_text().split())
        self.assertRegex(text, r"complete the applicable `next:` steps before restarting the loop")

    def test_new_settings_and_ignore_lines_still_need_a_pull_request(self):
        skill = Path(setup.__file__).resolve().parents[1] / "skills/setup/SKILL.md"
        text = " ".join(skill.read_text().split())
        self.assertRegex(text, r"If it added settings or ignore lines, tell the person to commit "
                              r"`loop\.json`, any migrated removal from `AGENTS\.md`, and "
                              r"the added `\.gitignore` lines through a pull request")
