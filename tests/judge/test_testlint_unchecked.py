"""Ready records explain judge files that test lint could not check."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import Project, git

# isort: split
import gate
import testlint
from loopkit import Refused


class TestLintUncheckedTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def test_D1_unsupported_judge_is_recorded_and_named_in_ready_message(self):
        name = "tests/judge/test_add.rb"
        judge = "print('FAIL D1 add')\nraise SystemExit(1)\n"
        spec = ("## Intent\nAdd a habit.\n\nOut of scope:\n- Editing habits.\n\n"
                "## Contract\n- D1: adding a habit appends it.\n\n"
                "## Judge\nCommand: `python3 tests/judge/test_add.rb`\n"
                "Files:\n- tests/judge/test_add.rb\n")
        number = self.p.piece(judge=judge, spec=spec)
        branch = f"piece/{number}"
        git(self.p.root, "switch", "--quiet", branch)
        (self.p.root / "judge_add.py").unlink()
        path = self.p.root / name
        path.parent.mkdir(parents=True)
        path.write_text(judge)
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Use an unsupported judge file")
        git(self.p.root, "switch", "--quiet", "main")

        note = gate.move(self.p.gh, self.p.root, number, "ready")
        record = gate.last_record(self.p.gh.comments(number), "ready")

        self.assertEqual(record["test_lint_unchecked"], [
            {"file": name, "reason": "unsupported language"}])
        self.assertIn(f"{name} not checked by the test lint", note)

    def test_D2_unreadable_unsupported_judge_is_refused_with_path(self):
        name = "tests/judge/test_add.rb"
        judge = "print('FAIL D1 add')\nraise SystemExit(1)\n"
        spec = ("## Intent\nAdd a habit.\n\nOut of scope:\n- Editing habits.\n\n"
                "## Contract\n- D1: adding a habit appends it.\n\n"
                "## Judge\nCommand: `python3 tests/judge/test_add.rb`\n"
                "Files:\n- tests/judge/test_add.rb\n")
        number = self.p.piece(judge=judge, spec=spec)
        git(self.p.root, "switch", "--quiet", f"piece/{number}")
        (self.p.root / "judge_add.py").unlink()
        path = self.p.root / name
        path.parent.mkdir(parents=True)
        path.write_text(judge)
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Use a nested unsupported judge")
        git(self.p.root, "switch", "--quiet", "main")
        original = Path.read_text

        def unreadable(candidate, *args, **kwargs):
            if candidate.name == "test_add.rb":
                raise PermissionError("denied")
            return original(candidate, *args, **kwargs)

        with patch.object(Path, "read_text", unreadable), \
                self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, number, "ready")

        self.assertIn(name, caught.exception.reason)
        self.assertNotIn("Traceback", caught.exception.reason)

    def test_D3_python_syntax_error_is_still_reported(self):
        findings = testlint.python_findings(Path("judge.py"), "def test_broken(:\n")
        self.assertEqual(findings[0][1], "python syntax error")

    def test_D4_supported_languages_are_linted(self):
        self.assertTrue(testlint.python_findings(Path("judge.py"), "def test_empty():\n    pass\n"))
        self.assertTrue(testlint.javascript_findings(Path("judge.js"), "test('empty', () => {});"))


if __name__ == "__main__":
    unittest.main()
