"""Unit checks for the judge test linter."""
from __future__ import annotations

import sys
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

    def test_javascript_reports_empty_skipped_and_true_expect_tests(self):
        text = """test('empty', () => {});
it.skip('skipped', () => expect(1).toBe(1));
test('true', () => expect(true).toBe(true));
"""
        rules = [rule for _, rule in javascript_findings(Path("test.js"), text)]
        self.assertIn("test has no expect or assert", rules)
        self.assertIn("disabled or skipped test", rules)
        self.assertIn("expect(true)", rules)


if __name__ == "__main__":
    unittest.main()
