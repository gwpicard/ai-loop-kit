"""Unit tests for loop/newtest_lint.py: the new-test lint. It reads text and runs nothing.

Each rule has one planted example in Python and one in TypeScript, under
tests/fixtures/test-smells/. A fixture is judged under a logical name, because
the folder it sits in would make every file a test file.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

from loop import newtest_lint as nl
from loop.newtest_lint import Rule

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "test-smells"
OWN = frozenset({"billing"})

REFUSING = [r for r in Rule if r not in nl.REPORT_ONLY]
LINE_RULES = [r for r in REFUSING if r is not Rule.SNAPSHOT_REWRITTEN]
SOURCE_RULES = {Rule.TEST_DETECT}


def name_for(rule: Rule, language: str) -> str:
    """The logical file name a fixture is judged under."""
    ext = "py" if language == "py" else "ts"
    if rule in SOURCE_RULES:
        return f"src/app.{ext}"
    return f"test_{rule.value}.py" if language == "py" else f"{rule.value}.test.ts"


def read(rule_or_name: Rule | str, language: str) -> str:
    stem = rule_or_name.value if isinstance(rule_or_name, Rule) else rule_or_name
    return (FIXTURES / f"{stem}.{language}.fixture").read_text(encoding="utf-8")


def judge(rule: Rule, language: str, **kwargs: object) -> list[nl.Finding]:
    return nl.lint_text(
        name_for(rule, language), read(rule, language), own_modules=OWN, **kwargs  # type: ignore[arg-type]
    )


def ids(findings: list[nl.Finding]) -> set[str]:
    return {f["rule"] for f in findings}


def refused(findings: list[nl.Finding]) -> set[str]:
    return {f["rule"] for f in nl.refusals(findings)}


class EveryRuleFires(unittest.TestCase):
    def test_every_planted_example_is_refused_for_its_own_rule_only(self) -> None:
        for language in ("py", "ts"):
            for rule in LINE_RULES:
                with self.subTest(rule=rule.value, language=language):
                    self.assertEqual(refused(judge(rule, language)), {rule.value})

    def test_the_snapshot_example_is_refused(self) -> None:
        for language in ("py", "ts"):
            lines = (FIXTURES / f"snapshot_rewritten.{language}.changes").read_text().splitlines()
            changes = [tuple(line.split("\t")) for line in lines]
            found = nl.lint_changes([(s, p) for s, p in changes])
            with self.subTest(language=language):
                self.assertEqual(refused(found), {"snapshot_rewritten"})

    def test_a_new_snapshot_beside_code_is_not_a_rewrite(self) -> None:
        found = nl.lint_changes([("M", "src/billing.ts"), ("A", "src/__snapshots__/new.snap")])
        self.assertEqual(found, [])

    def test_a_snapshot_changed_alone_is_not_a_rewrite_with_code(self) -> None:
        found = nl.lint_changes([("M", "tests/__snapshots__/a.ambr")])
        self.assertEqual(found, [])

    def test_a_finding_names_its_file_line_message_and_next_step(self) -> None:
        for finding in judge(Rule.SLEEP, "py"):
            self.assertEqual(
                sorted(finding), ["file", "line", "message", "next", "rule", "severity"]
            )
            self.assertTrue(finding["message"] and finding["next"])
            self.assertEqual(finding["line"], 7)

    def test_linting_twice_gives_the_same_answer(self) -> None:
        self.assertEqual(judge(Rule.SLEEP, "ts"), judge(Rule.SLEEP, "ts"))


class MutationEveryRuleIsLoadBearing(unittest.TestCase):
    """Switch one rule off and its planted example passes. So no rule is decoration."""

    def test_switching_a_rule_off_lets_its_example_through(self) -> None:
        for language in ("py", "ts"):
            for rule in LINE_RULES:
                enabled = frozenset(r for r in Rule if r is not rule)
                with self.subTest(rule=rule.value, language=language):
                    self.assertEqual(refused(judge(rule, language, rules=enabled)), set())

    def test_switching_the_snapshot_rule_off_lets_the_example_through(self) -> None:
        enabled = frozenset(r for r in Rule if r is not Rule.SNAPSHOT_REWRITTEN)
        found = nl.lint_changes([("M", "src/a.ts"), ("M", "src/__snapshots__/a.snap")], rules=enabled)
        self.assertEqual(found, [])

    def test_every_refusing_rule_has_a_message_and_a_hint(self) -> None:
        for rule in Rule:
            with self.subTest(rule=rule.value):
                severity, message, hint = nl.RULE_INFO[rule]
                self.assertIn(severity, ("refuse", "report"))
                self.assertTrue(message and hint)
                self.assertNotIn("—", message + hint)


class ReportOnly(unittest.TestCase):
    def test_assertion_roulette_is_reported_and_never_refuses(self) -> None:
        for language in ("py", "ts"):
            found = judge(Rule.ASSERTION_ROULETTE, language)
            with self.subTest(language=language):
                self.assertEqual(ids(found), {"assertion_roulette"})
                self.assertEqual(refused(found), set())
                self.assertEqual({f["severity"] for f in found}, {"report"})

    def test_magic_numbers_are_reported_and_never_refuse(self) -> None:
        for language in ("py", "ts"):
            found = judge(Rule.MAGIC_NUMBER, language)
            with self.subTest(language=language):
                self.assertEqual(ids(found), {"magic_number"})
                self.assertEqual(refused(found), set())

    def test_the_report_rules_can_be_switched_off_too(self) -> None:
        enabled = frozenset(r for r in Rule if r is not Rule.MAGIC_NUMBER)
        self.assertEqual(judge(Rule.MAGIC_NUMBER, "py", rules=enabled), [])

    def test_a_short_test_is_not_a_roulette(self) -> None:
        text = "def test_a(x):\n    assert x.a == 1\n    assert x.b == 2\n"
        self.assertEqual(nl.lint_text("test_a.py", text), [])


class CleanTestsPass(unittest.TestCase):
    def test_a_clean_python_test_passes(self) -> None:
        self.assertEqual(
            nl.lint_text("test_billing.py", read("clean", "py"), own_modules=OWN), []
        )

    def test_a_clean_typescript_test_passes(self) -> None:
        self.assertEqual(nl.lint_text("billing.test.ts", read("clean", "ts"), own_modules=OWN), [])

    def test_a_helper_that_asserts_counts_as_an_assertion(self) -> None:
        text = "def check(x):\n    assert x\n\n\ndef test_a():\n    check(1)\n"
        self.assertEqual(nl.lint_text("test_a.py", text), [])

    def test_a_mock_of_a_third_party_module_is_allowed(self) -> None:
        text = (
            "from unittest.mock import patch\n\n\ndef test_a():\n"
            '    with patch("requests.get") as get:\n        assert get is not None\n'
        )
        self.assertEqual(nl.lint_text("test_a.py", text, own_modules=OWN), [])
        ts = "jest.mock('axios');\nit('a', () => {\n  expect(1).toBe(1);\n});\n"
        self.assertEqual(nl.lint_text("a.test.ts", ts, own_modules=OWN), [])

    def test_rule_words_inside_strings_and_comments_do_not_fire(self) -> None:
        ts = (
            "it('a', () => {\n  // we do not use sleep( or console.log( here\n"
            "  expect('if (x) { for (;;) {} } sleep(1)').toBe('a');\n});\n"
        )
        self.assertEqual(nl.lint_text("a.test.ts", ts), [])
        py = 'def test_a():\n    assert "print(1) sleep(2) if x" == "a"\n'
        self.assertEqual(nl.lint_text("test_a.py", py), [])


class MoreShapes(unittest.TestCase):
    def test_a_bare_except_pass_is_swallowed(self) -> None:
        text = "def test_a():\n    try:\n        f()\n    except:\n        pass\n    assert 1\n"
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"swallowed_error"})

    def test_an_empty_catch_with_only_a_comment_is_swallowed(self) -> None:
        text = "it('a', () => {\n  try { f(); } catch (e) { /* ignore */ }\n  expect(1).toBe(1);\n});\n"
        self.assertEqual(refused(nl.lint_text("a.test.ts", text)), {"swallowed_error"})

    def test_a_catch_that_rethrows_is_not_swallowed(self) -> None:
        text = "it('a', () => {\n  try { f(); } catch (e) { throw e; }\n  expect(1).toBe(1);\n});\n"
        self.assertEqual(nl.lint_text("a.test.ts", text), [])

    def test_an_empty_python_test_is_a_test_with_no_assertion(self) -> None:
        text = "def test_a():\n    pass\n"
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"no_assertion"})

    def test_a_unittest_assertion_counts(self) -> None:
        text = (
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_a(self):\n        self.assertEqual(f(), 2)\n"
        )
        self.assertEqual(nl.lint_text("test_a.py", text), [])

    def test_xit_and_describe_skip_are_skip_markers(self) -> None:
        for line in ("xit('a', () => { expect(1).toBe(1); });", "describe.skip('a', () => {});"):
            with self.subTest(line=line):
                self.assertIn("skip_added", refused(nl.lint_text("a.test.ts", line + "\n")))

    def test_it_only_is_a_debug_leftover(self) -> None:
        text = "it.only('a', () => {\n  expect(1).toBe(1);\n});\n"
        self.assertEqual(refused(nl.lint_text("a.test.ts", text)), {"debug_leftover"})

    def test_a_new_todo_in_a_test_is_a_debug_leftover(self) -> None:
        text = "def test_a():\n    # TODO make this real\n    assert f() == 2\n"
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"debug_leftover"})

    def test_an_assert_of_equal_literals_is_assert_true(self) -> None:
        text = "def test_a():\n    f()\n    assert 3 == 3\n"
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"assert_true"})

    def test_a_class_method_if_is_conditional_logic(self) -> None:
        text = (
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_a(self):\n        if f():\n            self.assertTrue(f())\n"
        )
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"conditional_logic"})

    def test_a_python_source_file_is_judged_only_for_the_under_test_check(self) -> None:
        text = "import time\n\n\ndef f():\n    time.sleep(1)\n    print('x')\n"
        self.assertEqual(nl.lint_text("src/app.py", text), [])

    def test_python_that_does_not_parse_is_reported_not_refused(self) -> None:
        found = nl.lint_text("test_a.py", "def test_a(:\n    pass\n")
        self.assertEqual(refused(found), set())
        self.assertEqual(ids(found), {"unparsed"})

    def test_monkeypatch_of_an_own_module_is_a_mock_of_it(self) -> None:
        text = (
            "def test_a(monkeypatch):\n"
            '    monkeypatch.setattr("billing.rates.lookup", lambda: 3)\n    assert 1 == f()\n'
        )
        self.assertEqual(refused(nl.lint_text("test_a.py", text, own_modules=OWN)), {"own_module_mock"})

    def test_a_relative_vi_mock_is_a_mock_of_an_own_module(self) -> None:
        text = "vi.mock('../rates');\nit('a', () => {\n  expect(f()).toBe(2);\n});\n"
        self.assertEqual(refused(nl.lint_text("a.test.ts", text)), {"own_module_mock"})


class OnlyAddedLinesCount(unittest.TestCase):
    """A change is judged on the lines it adds, not on the tests it leaves alone."""

    SOURCE = (
        "import time\n"            # 1
        "\n"                       # 2
        "\n"                       # 3
        "def test_old():\n"        # 4
        "    time.sleep(1)\n"      # 5
        "    assert f() == 2\n"    # 6
        "\n"                       # 7
        "\n"                       # 8
        "def test_new():\n"        # 9
        "    time.sleep(1)\n"      # 10
        "    assert f() == 2\n"    # 11
    )

    def test_an_old_sleep_is_left_alone(self) -> None:
        found = nl.lint_text("test_a.py", self.SOURCE, added={9, 10, 11})
        self.assertEqual([f["line"] for f in nl.refusals(found)], [10])

    def test_no_added_line_means_nothing_is_judged(self) -> None:
        self.assertEqual(nl.lint_text("test_a.py", self.SOURCE, added=set()), [])

    def test_a_test_that_lost_its_assertion_is_caught_by_the_touched_line(self) -> None:
        text = "def test_a():\n    f()\n"
        found = nl.lint_text("test_a.py", text, added=set(), touched={2})
        self.assertEqual(refused(found), {"no_assertion"})

    def test_the_whole_file_is_judged_when_no_lines_are_given(self) -> None:
        self.assertEqual(len(nl.refusals(nl.lint_text("test_a.py", self.SOURCE))), 2)


class ReadingADiff(unittest.TestCase):
    DIFF = (
        "diff --git a/tests/test_a.py b/tests/test_a.py\n"
        "--- a/tests/test_a.py\n"
        "+++ b/tests/test_a.py\n"
        "@@ -3,0 +4,2 @@ def x():\n"
        "+    time.sleep(1)\n"
        "+    assert f()\n"
        "@@ -10,2 +11,0 @@ def y():\n"
        "-    assert g()\n"
        "-    assert h()\n"
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )

    def test_added_lines_per_file(self) -> None:
        changed = nl.parse_diff(self.DIFF)
        self.assertEqual(changed["tests/test_a.py"].added, {4, 5, 1 + 10})
        self.assertEqual(changed["src/app.py"].added, {1})

    def test_a_deletion_marks_the_lines_beside_it_as_touched(self) -> None:
        changed = nl.parse_diff(self.DIFF)
        self.assertEqual(changed["tests/test_a.py"].touched, {11, 12})
        self.assertEqual(changed["tests/test_a.py"].added & {12}, set())

    def test_an_empty_diff_has_no_files(self) -> None:
        self.assertEqual(nl.parse_diff(""), {})


class TestPaths(unittest.TestCase):
    def test_the_names_that_make_a_test_file(self) -> None:
        for path in (
            "tests/x.py",
            "src/__tests__/x.ts",
            "a/b.test.ts",
            "a/b.spec.js",
            "a/test_b.py",
            "a/b_test.go",
            "spec/x.rb",
        ):
            with self.subTest(path=path):
                self.assertTrue(nl.is_test_path(path))

    def test_the_names_that_do_not(self) -> None:
        for path in ("src/app.py", "src/contest.ts", "lib/attest.js"):
            with self.subTest(path=path):
                self.assertFalse(nl.is_test_path(path))

    def test_snapshot_paths(self) -> None:
        for path in ("a/__snapshots__/b.snap", "x.snap", "t/test_x.ambr", "x.test.ts.snap"):
            with self.subTest(path=path):
                self.assertTrue(nl.is_snapshot_path(path))
        self.assertFalse(nl.is_snapshot_path("src/app.ts"))


if __name__ == "__main__":
    unittest.main()
