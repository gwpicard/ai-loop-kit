"""Unit checks for the judge test linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))
from testlint import javascript_findings, python_findings


class TestLintTest(unittest.TestCase):
    def test_python_reports_missing_assertions_tautologies_and_markers(self):
        text = """import pytest
def test_empty():
    pass
def test_true():
    assert True
def test_same():
    assert value == value
@pytest.mark.xfail
def test_skipped():
    assert value
"""
        findings = python_findings(Path("test_example.py"), text)
        rules = [rule for _, rule in findings]
        self.assertIn("test has no assertion", rules)
        self.assertIn("assert True", rules)
        self.assertIn("assert expression equals itself", rules)
        self.assertIn("pytest skip or xfail marker", rules)

    def test_pytest_raises_and_assertion_methods_count(self):
        text = """import pytest
def test_error():
    with pytest.raises(ValueError):
        int('x')
def test_method():
    case.assertEqual(1, 2)
"""
        self.assertEqual(python_findings(Path("test_example.py"), text), [])

    def test_python_requires_an_outcome_beyond_not_raising(self):
        text = """def test_no_raise():
    case.assertNotRaises(do_work)
def test_return_value():
    assert do_work() == "done"
"""
        rules = [rule for _, rule in python_findings(Path("test_example.py"), text)]
        self.assertIn("test only checks that a call does not raise", rules)
        self.assertEqual(rules.count("test only checks that a call does not raise"), 1)

    def test_javascript_requires_an_outcome_beyond_not_throwing(self):
        text = """test('no throw', () => expect(() => doWork()).not.toThrow());
test('return value', () => expect(doWork()).toBe('done'));
"""
        findings = javascript_findings(Path("test.js"), text)
        rules = [rule for _, rule in findings]
        self.assertIn("test only checks that a call does not throw", rules)
        self.assertEqual(rules.count("test only checks that a call does not throw"), 1)

    def test_javascript_accepts_node_assertions_with_a_result_check(self):
        text = """test('result', () => {
    assert.doesNotThrow(work);
    assert.strictEqual(result, 42);
});
"""
        findings = javascript_findings(Path("test.js"), text)
        self.assertEqual(findings, [])

    def test_javascript_reports_empty_skipped_and_true_expect_tests(self):
        text = """test('empty', () => {});
it.skip('skipped', () => expect(1).toBe(1));
test('true', () => expect(true).toBe(true));
"""
        rules = [rule for _, rule in javascript_findings(Path("test.js"), text)]
        self.assertIn("test has no expect or assert", rules)
        self.assertIn("disabled or skipped test", rules)
        self.assertIn("expect(true)", rules)

    def test_javascript_todo_is_flagged_without_matching_regex_test_calls(self):
        text = "test.todo('later');\nconst ok = /re/.test(value);\n"
        findings = javascript_findings(Path("test.js"), text)
        self.assertTrue(any("disabled or skipped" in rule for _, rule in findings))
        self.assertFalse(any("no expect" in rule for _, rule in findings))

    def test_python_refuses_private_imports_from_project_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text("def _helper(): return 1\ndef public(): return 2\n")
            private = "from app import _helper\ndef test_private():\n    assert _helper() == 1\n"
            public = "from app import public\ndef test_public():\n    assert public() == 2\n"
            findings = python_findings(root / "judge.py", private, root)
            self.assertTrue(any("private project name" in rule for _, rule in findings))
            self.assertEqual(python_findings(root / "judge.py", public, root), [])

    def test_python_flags_skip_calls_and_private_imports_from_src_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "src" / "sample"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "_private.py").write_text("value = 1\n")
            (root / "pyproject.toml").write_text(
                '[tool.setuptools.packages.find]\nwhere = ["src"]\n')
            text = ("import pytest\nfrom sample._private import value\n"
                    "def test_skip():\n    pytest.skip('later')\n"
                    "def test_optional():\n    pytest.importorskip('sample')\n    assert value\n")
            rules = [rule for _, rule in python_findings(root / "judge.py", text, root)]
            self.assertIn("pytest skip or xfail marker", rules)
            self.assertTrue(any("sample._private" in rule for rule in rules))

    def test_javascript_refuses_private_named_imports_from_project_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.js").write_text("export const _helper = () => 1;\n")
            judge = root / "judge.js"
            text = "import { _helper } from './app.js';\ntest('D1', () => expect(_helper()).toBe(1));\n"
            findings = javascript_findings(judge, text, root)
            self.assertTrue(any("private project name" in rule for _, rule in findings))

    def test_javascript_flags_same_call_comparisons_and_source_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "src"
            source.mkdir()
            (source / "app.js").write_text("export const calculate = x => x;\n")
            judge = root / "judge.js"
            text = ("test('D1', () => expect(calculate(1)).toBe(calculate(1)));\n"
                    "test('D2', () => expect(readFileSync('src/app.js')).toBeTruthy());\n")
            findings = javascript_findings(judge, text, root)
            rules = [rule for _, rule in findings]
            self.assertIn("only assertion compares calls to the same function", rules)
            self.assertIn("test reads project source as text: src/app.js", rules)

    def test_lints_same_call_comparisons_and_source_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "src"
            source.mkdir()
            (source / "app.py").write_text("def calculate(value): return value\n")
            judge = root / "judge.py"
            text = ("def test_tautology():\n    assert calculate(1) == calculate(1)\n"
                    "def test_reads_source():\n    assert open('src/app.py').read()\n")
            findings = python_findings(judge, text, root)
            rules = [rule for _, rule in findings]
            self.assertIn("only assertion compares calls to the same function", rules)
            self.assertIn("test reads project source as text: src/app.py", rules)
            allowed = "def test_file_contract():\n    assert open('src/app.py').read()\n"
            self.assertEqual(python_findings(judge, allowed, root, "D1 checks src/app.py"), [])


if __name__ == "__main__":
    unittest.main()
