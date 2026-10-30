"""The reviewer is told which reproducer file types can run, and why one cannot."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

import review
from helpers import git
from run_fixtures import RunFixture

PY_CHECK = {"type": "tests", "command": "python3 judge_add.py", "files": ["judge_add.py"]}
JS_CHECK = {"type": "tests", "command": "node check.test.js", "files": ["check.test.js"]}


class ReproducerTypesTest(RunFixture, unittest.TestCase):
    def reproduce(self, name, ready, source="raise AssertionError('D1')\n"):
        """Run a reproducer file through the kit, recording the commands the judge receives."""
        (self.p.root / name).write_text(source)
        commands = []

        def judge(folder, command, **kwargs):
            commands.append(command)
            return 1, "FAIL D1: assertion failed"

        try:
            with patch("review.gate.run_judge", side_effect=judge):
                result = review._run_contract_reproducer(
                    self.p.root, self.p.root, git(self.p.root, "rev-parse", "HEAD"),
                    ready, Path(name), "D1", 1, 1)
        finally:
            (self.p.root / name).unlink()
        return result, commands

    def test_D1_rendered_brief_names_the_exit_file_types(self):
        prompts = []
        session = review._review_session

        def observe(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return session(folder, prompt, *args, **kwargs)

        with patch("review._review_session", side_effect=observe):
            _n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        brief = next(p for p in prompts if p.startswith("# Contract reviewer brief"))
        self.assertNotIn("{{EXIT_FILE_TYPES}}", brief)
        line = next((line for line in brief.splitlines() if "file type" in line), "")
        self.assertIn("approved Exit test", line)
        self.assertIn(".py", line)

    def test_D2_mismatched_type_is_reported_with_the_allowed_types(self):
        result, commands = self.reproduce("test_gap.rb", {"checks": [PY_CHECK, JS_CHECK]})
        self.assertEqual(commands, [])
        self.assertFalse(result["reproduced"])
        self.assertIn("no approved Exit test uses .rb; reproducers must use .py, .js",
                      result["output"])

    def test_D2_older_ready_record_uses_its_command_and_files(self):
        result, commands = self.reproduce(
            "test_gap.rb", {"command": "python3 judge_add.py", "files": ["judge_add.py"]})
        self.assertEqual(commands, [])
        self.assertFalse(result["reproduced"])
        self.assertIn("no approved Exit test uses .rb; reproducers must use .py",
                      result["output"])

    def test_D3_matching_type_runs_under_that_check_only(self):
        result, commands = self.reproduce("test_gap.py", {"checks": [PY_CHECK, JS_CHECK]})
        self.assertEqual(len(commands), 1)
        self.assertIn("test_gap.py", commands[0])
        self.assertTrue(commands[0].startswith("python3 "))
        self.assertNotIn("node", commands[0])
        self.assertTrue(result["reproduced"])
        self.assertNotIn("no approved Exit test", result["output"])


if __name__ == "__main__":
    unittest.main()
