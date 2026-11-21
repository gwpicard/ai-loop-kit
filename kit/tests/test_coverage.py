import re
from pathlib import Path

from kit.tests import test_pass as tp
from kit.tests.fake_claude import FakeClaudeGh

KIT = Path(__file__).resolve().parents[1]


def words(*parts):
    return re.sub(r"\s+", " ", Path(KIT, *parts).read_text(encoding="utf-8"))


class CoverageQuestionTest(FakeClaudeGh):
    # borrow the pass fixtures without inheriting its tests
    repo, gh, run_pass = tp.PassTest.repo, tp.PassTest.gh, tp.PassTest.run_pass

    def drift_prompt(self, extra):
        self.repo(tp.plan(), extra)
        self.claude({"pass": [tp.NONE, tp.NONE, tp.NONE, tp.LESSONS]})
        self.run_pass()
        return self.claude_calls()[0]["prompt"]

    def test_drift_prompt_names_the_check_command_when_set(self):
        self.assertIn("Check command: ruff check .", self.drift_prompt("Check command: ruff check .\n"))

    def test_drift_prompt_leaves_the_check_command_out_when_not_set(self):
        self.assertNotIn("Check command", self.drift_prompt(""))

    def test_drift_brief_reports_source_folders_and_targets_the_commands_skip(self):
        text = words("briefs", "pass-drift.md")
        for word in ("Check command", "source folder", "build target", "type-check"):
            self.assertIn(word, text)

    def test_shape_skill_asks_whether_the_commands_cover_every_target_and_folder(self):
        text = words("skills", "shape", "SKILL.md")
        for word in ("every target", "every source folder", "issue that fixes", "first issue"):
            self.assertIn(word, text)
