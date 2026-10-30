"""Only an assertion failure naming the item counts as failing for the right reason."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import Project, git

# isort: split
import review
from loopkit import Refused, exit_ready, judge_assertion_failed, judge_has_runner_error

CONTRACT = {"D1": "add a habit"}
ASSERTION = ("________________ test_D1_add ________________\n"
             "    def test_D1_add():\n"
             ">       assert add() == 1\n"
             "E       assert None == 1\n")
CRASH = ("________________ test_D1_runner ________________\n"
         "E       RuntimeError: D1 runner crashed\n")
UNITTEST_ERROR = ("ERROR: test_D1_add (judge.JudgeTest)\n"
                  "Traceback (most recent call last):\n"
                  "AttributeError: 'CliRunner' object has no attribute 'isolated_filesystem'\n")


class AssertionFailuresTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root

    def ready(self, judge_source):
        (self.root / "judge.py").write_text(judge_source)
        checks = ({"type": "tests", "command": f"{sys.executable} judge.py",
                   "files": ["judge.py"]},)
        return exit_ready(self.root, checks, CONTRACT, ())

    def reproduce(self, source):
        (self.root / "judge.py").write_text("print('baseline')\n")
        git(self.root, "add", "judge.py")
        git(self.root, "commit", "--quiet", "-m", "Add frozen judge")
        (self.root / "test_review_D1.py").write_text(source)
        return review._run_contract_reproducer(
            self.root, self.root, git(self.root, "rev-parse", "HEAD"),
            {"checks": [{"type": "tests", "command": f"{sys.executable} judge.py",
                         "files": ["judge.py"]}]},
            Path("test_review_D1.py"), "D1", 1, 1)

    def test_D1_runtime_error_naming_the_item_is_refused_at_ready(self):
        with self.assertRaisesRegex(Refused, "names no spec ID"):
            self.ready("raise RuntimeError('D1 runner crashed')\n")

    def test_D1_classifier_rejects_a_runtime_error_block(self):
        self.assertFalse(judge_assertion_failed(CRASH, "D1"))

    def test_D2_non_assertion_exception_does_not_reproduce_the_finding(self):
        result = self.reproduce("raise RuntimeError('D1 runner crashed')\n")
        self.assertFalse(result["reproduced"])
        self.assertIn("RuntimeError: D1 runner crashed", result["output"])

    def test_D3_assertion_still_counts_when_another_block_raises(self):
        self.assertTrue(judge_assertion_failed(CRASH + ASSERTION, "D1"))
        self.assertTrue(judge_assertion_failed(ASSERTION + CRASH, "D1"))
        self.assertFalse(judge_assertion_failed(CRASH + ASSERTION.replace("D1", "D2"), "D1"))

    def test_D3_whole_run_refusals_remain(self):
        for text in ("raise SyntaxError('D1')\n", "import missing_d1_dependency\n"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(Refused, "wrong reason"):
                    self.ready(text)
        self.assertTrue(judge_has_runner_error("sh: pytest: command not found", 127))
        self.assertTrue(judge_has_runner_error(
            "ERROR collecting test_x.py\nE   ModuleNotFoundError: No module named 'x'", 2))
        self.assertTrue(judge_has_runner_error(
            "E   FileNotFoundError: [Errno 2] No such file", 1))

    def test_D4_assertion_naming_the_item_reaches_ready(self):
        records, output = self.ready("raise AssertionError('D1 add appends')\n")
        self.assertEqual(len(records), 1)
        self.assertIn("AssertionError", output)

    def test_D5_attribute_error_in_an_error_block_is_refused_at_ready(self):
        self.assertFalse(judge_assertion_failed(UNITTEST_ERROR, "D1"))
        script = ("import unittest\n"
                  "class JudgeTest(unittest.TestCase):\n"
                  "    def test_D1_add(self):\n"
                  "        object().isolated_filesystem()\n"
                  "unittest.main()\n")
        with self.assertRaisesRegex(Refused, "names no spec ID"):
            self.ready(script)

    def test_D5_runner_formats_are_classified_per_block(self):
        cases = {
            "unittest FAIL": ("FAIL: test_D1_add (judge.T)\nAssertionError: 1 != 2\n", True),
            "unittest ERROR": ("ERROR: test_D1_add (judge.T)\nTypeError: bad\n", False),
            "node assert": ("AssertionError [ERR_ASSERTION]: D1 differs\n", True),
            "node test": ("not ok 1 - D1 adds\n  ---\n  code: 'ERR_ASSERTION'\n  ...\n", True),
            "node test error": ("not ok 1 - D1 adds\n  ---\n  code: 'ERR_X'\n  ...\n", False),
            "jest": ("  ● D1 adds\n\n    expect(received).toBe(expected)\n", True),
            "jest error": ("  ● D1 adds\n\n    TypeError: x is not a function\n", False),
            "vitest": (" FAIL  a.test.js > D1 adds\nAssertionError: expected 1 to be 2\n", True),
            "pytest summary": ("FAILED t.py::test_D1 - AssertionError: nope\n", True),
            "pytest summary error": ("FAILED t.py::test_D1 - AttributeError: nope\n", False),
        }
        for name, (output, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(judge_assertion_failed(output, "D1"), expected)

    def test_D7_runner_error_run_is_not_reproduced(self):
        result = self.reproduce("import missing_d1_dependency\n")
        self.assertFalse(result["reproduced"])
        self.assertIn("ModuleNotFoundError", result["output"])

    def test_D8_classifier_lives_in_its_own_module_within_the_line_budget(self):
        import importlib

        import loopkit
        import test_size_inventory as sizes

        kit = Path(__file__).resolve().parents[2] / "kit"
        self.assertTrue((kit / "scripts/failures.py").exists(), "failures.py is missing")
        failures = importlib.import_module("failures")
        self.assertIs(loopkit.judge_assertion_failed, failures.judge_assertion_failed)
        self.assertIs(loopkit.judge_has_runner_error, failures.judge_has_runner_error)
        self.assertNotIn("def judge_assertion_failed", (kit / "scripts/loopkit.py").read_text())
        counts = {path.relative_to(kit.parent).as_posix(): len(path.read_text().splitlines())
                  for path in sorted(kit.rglob("*.py"))}
        sizes.check_sizes(counts)


if __name__ == "__main__":
    unittest.main()
