"""Unit tests for loop/newtest_lint.py: the new-test lint. It reads text and runs nothing.

Each rule has one planted example in Python and one in TypeScript, under
tests/fixtures/test-smells/. A fixture is judged under a logical name, because
the folder it sits in would make every file a test file.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

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
        name_for(rule, language),
        read(rule, language),
        own_modules=OWN,
        **kwargs,  # type: ignore[arg-type]
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
        found = nl.lint_changes(
            [("M", "src/a.ts"), ("M", "src/__snapshots__/a.snap")], rules=enabled
        )
        self.assertEqual(found, [])

    def test_every_refusing_rule_has_a_message_and_a_hint(self) -> None:
        for rule in Rule:
            with self.subTest(rule=rule.value):
                severity, message, hint = nl.RULE_INFO[rule]
                self.assertIn(severity, ("refuse", "report"))
                self.assertTrue(message and hint)
                self.assertNotIn("—", message + hint)


VARIANTS = FIXTURES / "variants"


def variant_cases() -> list[tuple[Rule, str, str, Path]]:
    """(rule, name, language, path) for every planted variant."""
    cases = []
    for path in sorted(VARIANTS.glob("*.fixture")):
        stem, language, _ = path.name.rsplit(".", 2)
        rule, name = stem.split("--")
        cases.append((Rule(rule), name, language, path))
    return cases


def judge_variant(rule: Rule, language: str, path: Path, **kwargs: object) -> list[nl.Finding]:
    return nl.lint_text(
        name_for(rule, language),
        path.read_text(encoding="utf-8"),
        own_modules=OWN,
        **kwargs,  # type: ignore[arg-type]
    )


class EveryVariantFires(unittest.TestCase):
    """Cheap ways round a rule are refused too, each with its own planted example."""

    def test_there_are_variants_to_judge(self) -> None:
        names = {(rule.value, name, language) for rule, name, language, _ in variant_cases()}
        for wanted in (
            ("assert_true", "or_true", "py"),
            ("assert_true", "tuple", "py"),
            ("assert_true", "or_true", "ts"),
            ("no_assertion", "nested_def", "py"),
            ("no_assertion", "nested_arrow", "ts"),
            ("own_module_mock", "sys_modules", "py"),
            ("skip_added", "it_todo", "ts"),
        ):
            self.assertIn(wanted, names)

    def test_each_variant_is_refused_for_its_own_rule_only(self) -> None:
        for rule, name, language, path in variant_cases():
            with self.subTest(rule=rule.value, variant=name, language=language):
                self.assertEqual(refused(judge_variant(rule, language, path)), {rule.value})

    def test_with_the_rule_off_each_variant_passes_so_the_rule_does_the_work(self) -> None:
        for rule, name, language, path in variant_cases():
            enabled = frozenset(r for r in Rule if r is not rule)
            with self.subTest(rule=rule.value, variant=name, language=language):
                self.assertEqual(refused(judge_variant(rule, language, path, rules=enabled)), set())


def lint_py(text: str, **kwargs: object) -> set[str]:
    return refused(nl.lint_text("test_a.py", text, **kwargs))  # type: ignore[arg-type]


def lint_ts(text: str) -> set[str]:
    return refused(nl.lint_text("a.test.ts", text))


class AlwaysTrueByConstruction(unittest.TestCase):
    def test_python_forms_that_cannot_fail(self) -> None:
        for body in (
            "assert f() == 2 or True",
            "assert True or f() == 2",
            "assert 1 or f()",
            "assert (f(), 2)",
            "assert (f() == 2,)",
            "assert x == x",
            "assert x.y == x.y",
            "self.assertTrue(True)",
        ):
            text = f"def test_a(x):\n    {body}\n"
            with self.subTest(body=body):
                self.assertEqual(lint_py(text), {"assert_true"})

    def test_python_forms_that_can_fail_are_left_alone(self) -> None:
        for body in (
            "assert f() == 2 or g() == 3",
            "assert f() == 2 and True",
            "assert ()",
            "assert f() == f2()",
            "assert f() == f()",
        ):
            text = f"def test_a(x):\n    {body}\n"
            with self.subTest(body=body):
                self.assertNotIn("assert_true", lint_py(text))

    def test_typescript_forms_that_cannot_fail(self) -> None:
        for body in (
            "expect(f()).toBe(2) || true;",
            "expect(f()).toBe(2) || 1;",
            "true || expect(f()).toBe(2);",
            "expect(true).toBeDefined();",
            "expect(true).not.toBe(false);",
            "expect(x).toBe(x);",
            "expect(a.b).toEqual(a.b);",
        ):
            text = f"it('a', () => {{\n  {body}\n}});\n"
            with self.subTest(body=body):
                self.assertEqual(lint_ts(text), {"assert_true"})

    def test_typescript_forms_that_can_fail_are_left_alone(self) -> None:
        for body in (
            "expect(f()).toBe(2) || g();",
            "expect(true).toBe(false);",
            "expect(a.b).toEqual(a.bc);",
            "const y = x || true;\n  expect(y).toBe(2);",
        ):
            text = f"it('a', () => {{\n  {body}\n}});\n"
            with self.subTest(body=body):
                self.assertEqual(lint_ts(text), set())


class AssertionsThatNeverRun(unittest.TestCase):
    def test_a_nested_function_that_the_test_never_calls_does_not_count(self) -> None:
        text = "def test_a():\n    def inner():\n        assert f() == 2\n    f()\n"
        self.assertEqual(lint_py(text), {"no_assertion"})

    def test_a_nested_function_that_the_test_calls_counts(self) -> None:
        text = "def test_a():\n    def inner():\n        assert f() == 2\n    inner()\n"
        self.assertEqual(lint_py(text), set())

    def test_a_nested_function_called_by_a_called_one_counts(self) -> None:
        text = (
            "def test_a():\n    def deep():\n        assert f() == 2\n"
            "    def inner():\n        deep()\n    inner()\n"
        )
        self.assertEqual(lint_py(text), set())

    def test_an_uncalled_lambda_does_not_count_and_a_called_one_does(self) -> None:
        unused = "def test_a(self):\n    c = lambda: self.assertEqual(f(), 2)\n    f()\n"
        used = "def test_a(self):\n    c = lambda: self.assertEqual(f(), 2)\n    c()\n"
        self.assertEqual(lint_py(unused), {"no_assertion"})
        self.assertEqual(lint_py(used), set())

    def test_an_assertion_in_a_nested_function_does_not_count_as_duplicate_either(self) -> None:
        text = "def test_a():\n    def inner():\n        assert f() == 2\n    assert f() == 2\n"
        self.assertEqual(lint_py(text), set())

    def test_an_uncalled_nested_arrow_or_function_does_not_count_in_typescript(self) -> None:
        arrow = "it('a', () => {\n  const c = () => { expect(f()).toBe(2); };\n  f();\n});\n"
        func = "it('a', () => {\n  function c() { expect(f()).toBe(2); }\n  f();\n});\n"
        self.assertEqual(lint_ts(arrow), {"no_assertion"})
        self.assertEqual(lint_ts(func), {"no_assertion"})

    def test_a_called_or_passed_nested_helper_counts_in_typescript(self) -> None:
        called = "it('a', () => {\n  const c = () => { expect(f()).toBe(2); };\n  c();\n});\n"
        passed = (
            "it('a', () => {\n  const c = (x) => { expect(x).toBe(2); };\n"
            "  [f()].forEach(c);\n});\n"
        )
        inline = "it('a', () => {\n  [f()].forEach((x) => { expect(x).toBe(2); });\n});\n"
        for text in (called, passed, inline):
            with self.subTest(text=text):
                self.assertEqual(lint_ts(text), set())


class AssertionCallsMatchExactly(unittest.TestCase):
    def test_a_name_that_only_starts_like_an_assertion_does_not_count(self) -> None:
        for call in (
            "verify_nothing()",
            "failover_setup()",
            "expected_value()",
            "raisesomething()",
        ):
            text = f"def test_a():\n    f()\n    {call}\n"
            with self.subTest(call=call):
                self.assertEqual(lint_py(text), {"no_assertion"})

    def test_real_assertion_calls_count(self) -> None:
        for call in (
            "self.assertEqual(f(), 2)",
            "self.assertRaises(ValueError, f)",
            "self.fail('no')",
            "pytest.fail('no')",
            "mock.assert_called_with(2)",
            "assert_that(f(), 2)",
            "np.testing.assert_allclose(f(), 2)",
            "expect(f()).to_equal(2)",
        ):
            text = f"def test_a(self, mock):\n    {call}\n"
            with self.subTest(call=call):
                self.assertEqual(lint_py(text), set())

    def test_raises_and_warns_blocks_count(self) -> None:
        for head in (
            "pytest.raises(ValueError)",
            "pytest.warns(UserWarning)",
            "raises(ValueError)",
        ):
            text = f"def test_a():\n    with {head}:\n        f()\n"
            with self.subTest(head=head):
                self.assertEqual(lint_py(text), set())

    def test_a_helper_named_like_an_assertion_must_assert_for_its_own_sake(self) -> None:
        text = "def verify_it():\n    return 1\n\n\ndef test_a():\n    verify_it()\n"
        self.assertEqual(lint_py(text), {"no_assertion"})

    def test_pytest_fail_is_an_explicit_fail(self) -> None:
        text = "def test_a():\n    f()\n    pytest.fail('stop')\n"
        self.assertEqual(lint_py(text), set())

    def test_a_typescript_method_named_fail_is_not_a_bare_fail(self) -> None:
        text = "it('a', () => {\n  logger.fail('x');\n  f();\n});\n"
        self.assertEqual(lint_ts(text), {"no_assertion"})
        text = "it('a', () => {\n  f();\n  fail('x');\n});\n"
        self.assertEqual(lint_ts(text), set())


class OwnModuleMockSpellings(unittest.TestCase):
    def mocked(self, text: str, own: frozenset[str] = OWN) -> set[str]:
        return lint_py(text, own_modules=own)

    def test_these_spellings_all_mock_an_own_module(self) -> None:
        for body in (
            'monkeypatch.setattr(billing.rates, "lookup", f)',
            'monkeypatch.setattr(rates, "lookup", f)',
            'monkeypatch.setattr("billing.rates.lookup", f)',
            'mock.patch.object(billing.rates.Table, "lookup")',
            'patch.object(rates, "lookup")',
            'sys.modules["billing"] = Mock()',
            'sys.modules["billing.rates"] = MagicMock(name="x")',
            'monkeypatch.setitem(sys.modules, "billing", object())',
            'mock.patch.dict("sys.modules", {"billing": Mock()})',
            "create_autospec(billing.rates)",
            "mock.create_autospec(rates, spec_set=True)",
            'mocker.patch("billing.rates.lookup")',
        ):
            text = (
                "import billing.rates\nfrom billing import rates\n\n\n"
                f"def test_a(monkeypatch):\n    {body}\n    assert f() == 2\n"
            )
            with self.subTest(body=body):
                self.assertEqual(self.mocked(text), {"own_module_mock"})

    def test_these_spellings_are_not_own_modules(self) -> None:
        for body in (
            'monkeypatch.setattr(os.path, "exists", f)',
            'monkeypatch.setattr("os.path.exists", f)',
            'mock.patch.object(requests.Session, "get")',
            'sys.modules["numpy"] = Mock()',
            "create_autospec(requests)",
        ):
            text = (
                "import os\nimport requests\nimport billing.rates\n\n\n"
                f"def test_a(monkeypatch):\n    {body}\n    assert billing.rates.f() == 2\n"
            )
            with self.subTest(body=body):
                self.assertEqual(self.mocked(text), set())

    def test_a_relative_import_is_an_own_module(self) -> None:
        text = (
            "from . import rates\n\n\ndef test_a(monkeypatch):\n"
            '    monkeypatch.setattr(rates, "lookup", f)\n    assert f() == 2\n'
        )
        self.assertEqual(self.mocked(text, frozenset()), {"own_module_mock"})


class OwnModuleDetection(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def touch(self, rel: str, text: str = "") -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_package_at_any_depth_is_found(self) -> None:
        self.touch("kit/scripts/loop/__init__.py")
        self.touch("packages/x/shop/__init__.py")
        self.touch("packages/x/shop/inner/__init__.py")
        self.assertEqual(nl.detect_own_modules(self.root), frozenset({"loop", "shop"}))

    def test_tests_docs_and_vendor_folders_are_not_own(self) -> None:
        self.touch("tests/helpers/__init__.py")
        self.touch("node_modules/x/__init__.py")
        self.touch(".venv/lib/pkg/__init__.py")
        self.touch("src/app/__init__.py")
        self.assertEqual(nl.detect_own_modules(self.root), frozenset({"app"}))

    def test_a_root_named_in_pyproject_gives_its_modules(self) -> None:
        self.touch("pyproject.toml", '[tool.pytest.ini_options]\npythonpath = ["lib/py", "."]\n')
        self.touch("lib/py/helper.py")
        self.touch("lib/py/pkg_without_init/a.py")
        self.assertEqual(
            nl.detect_own_modules(self.root), frozenset({"helper", "pkg_without_init"})
        )

    def test_mypy_path_in_pyproject_and_the_environment_name_roots(self) -> None:
        self.touch("pyproject.toml", '[tool.mypy]\nmypy_path = "kit/scripts"\n')
        self.touch("kit/scripts/spec.py")
        self.touch("tools/other.py")
        found = nl.detect_own_modules(self.root, environ={"MYPYPATH": "tools:missing"})
        self.assertEqual(found, frozenset({"spec", "other", "tools"}))

    def test_a_project_with_no_module_gives_an_empty_set(self) -> None:
        self.touch("README.md")
        self.assertEqual(nl.detect_own_modules(self.root), frozenset())


class TheCommandSaysWhenItFoundNoModule(unittest.TestCase):
    SCRIPT = ROOT / "kit" / "scripts" / "newtest-lint.py"

    def run_cli(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "MYPYPATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_a_python_file_with_no_module_found_says_so_and_names_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            test = Path(folder) / "test_a.py"
            test.write_text("def test_a():\n    assert f() == 2\n", encoding="utf-8")
            done = self.run_cli(Path(folder), "--file", str(test), "--json")
            body = json.loads(done.stdout)
            self.assertEqual(done.returncode, 0)
            self.assertIn("--own-module", " ".join(body["notes"]))
            self.assertEqual(body["own_modules"], [])
            self.assertIn("note: ", done.stderr)

    def test_no_note_when_a_module_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            test = Path(folder) / "test_a.py"
            test.write_text("def test_a():\n    assert f() == 2\n", encoding="utf-8")
            done = self.run_cli(Path(folder), "--file", str(test), "--own-module", "x", "--json")
            body = json.loads(done.stdout)
            self.assertEqual(body["notes"], [])
            self.assertEqual(body["own_modules"], ["x"])

    def test_no_note_when_only_typescript_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            test = Path(folder) / "a.test.ts"
            test.write_text("it('a', () => {\n  expect(f()).toBe(2);\n});\n", encoding="utf-8")
            done = self.run_cli(Path(folder), "--file", str(test), "--json")
            self.assertEqual(json.loads(done.stdout)["notes"], [])

    def test_the_help_says_the_option_is_repeated(self) -> None:
        done = self.run_cli(ROOT, "--help")
        self.assertIn("repeat", " ".join(done.stdout.split()))


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
        self.assertEqual(nl.lint_text("test_billing.py", read("clean", "py"), own_modules=OWN), [])

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
        ts = "jest.mock('axios');\nit('a', () => {\n  expect(f()).toBe(1);\n});\n"
        self.assertEqual(nl.lint_text("a.test.ts", ts, own_modules=OWN), [])

    def test_rule_words_inside_strings_and_comments_do_not_fire(self) -> None:
        ts = (
            "it('a', () => {\n  // we do not use sleep( or console.log( here\n"
            "  expect('if (x) { for (;;) {} } sleep(1)').toBe('a');\n});\n"
        )
        self.assertEqual(nl.lint_text("a.test.ts", ts), [])
        py = 'def test_a():\n    assert "print(1) sleep(2) if x" == "a"\n'
        self.assertEqual(nl.lint_text("test_a.py", py), [])


class HelpersAreFollowedThroughTheChain(unittest.TestCase):
    def test_a_two_level_chain_reaches_the_assertion(self) -> None:
        text = (
            "def inner(x):\n    assert x == 2\n\n\ndef outer(x):\n    inner(x)\n\n\n"
            "def test_a():\n    outer(2)\n"
        )
        self.assertEqual(lint_py(text), set())

    def test_a_three_level_chain_of_methods_reaches_the_assertion(self) -> None:
        text = (
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def expect(self, x):\n        self.assertEqual(x, 2)\n\n"
            "    def check(self, x):\n        self.expect(x)\n\n"
            "    def refused(self, x):\n        self.check(x)\n\n"
            "    def test_a(self):\n        self.refused(2)\n"
        )
        self.assertEqual(lint_py(text), set())

    def test_a_three_level_chain_passes_in_typescript(self) -> None:
        text = (
            "const c = (x) => { expect(x).toBe(2); };\n"
            "const b = (x) => { c(x); };\n"
            "function a(x) { b(x); }\n"
            "it('a', () => {\n  a(2);\n});\n"
        )
        self.assertEqual(lint_ts(text), set())

    def test_a_chain_that_ends_in_no_assertion_refuses(self) -> None:
        text = (
            "def inner(x):\n    return x\n\n\ndef outer(x):\n    inner(x)\n\n\n"
            "def test_a():\n    outer(2)\n"
        )
        self.assertEqual(lint_py(text), {"no_assertion"})
        ts = (
            "const b = (x) => { log(x); };\nfunction a(x) { b(x); }\n"
            "it('a', () => {\n  a(2);\n});\n"
        )
        self.assertEqual(lint_ts(ts), {"no_assertion"})

    def test_a_helper_the_test_never_calls_does_not_count(self) -> None:
        text = (
            "def inner(x):\n    assert x == 2\n\n\ndef outer(x):\n    inner(x)\n\n\n"
            "def test_a():\n    other(2)\n"
        )
        self.assertEqual(lint_py(text), {"no_assertion"})

    def test_a_recursive_pair_with_no_assertion_refuses_without_looping(self) -> None:
        text = (
            "def ping(x):\n    pong(x)\n\n\ndef pong(x):\n    ping(x)\n\n\n"
            "def test_a():\n    ping(2)\n"
        )
        self.assertEqual(lint_py(text), {"no_assertion"})
        ts = (
            "function ping(x) { pong(x); }\nfunction pong(x) { ping(x); }\n"
            "it('a', () => {\n  ping(2);\n});\n"
        )
        self.assertEqual(lint_ts(ts), {"no_assertion"})


class MoreShapes(unittest.TestCase):
    def test_a_bare_except_pass_is_swallowed(self) -> None:
        text = "def test_a():\n    try:\n        f()\n    except:\n        pass\n    assert f()\n"
        self.assertEqual(refused(nl.lint_text("test_a.py", text)), {"swallowed_error"})

    def test_an_empty_catch_with_only_a_comment_is_swallowed(self) -> None:
        text = (
            "it('a', () => {\n  try { f(); } catch (e) { /* ignore */ }\n"
            "  expect(f()).toBe(1);\n});\n"
        )
        self.assertEqual(refused(nl.lint_text("a.test.ts", text)), {"swallowed_error"})

    def test_a_catch_that_rethrows_is_not_swallowed(self) -> None:
        text = (
            "it('a', () => {\n  try { f(); } catch (e) { throw e; }\n  expect(f()).toBe(1);\n});\n"
        )
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
        for line in ("xit('a', () => { expect(f()).toBe(1); });", "describe.skip('a', () => {});"):
            with self.subTest(line=line):
                self.assertIn("skip_added", refused(nl.lint_text("a.test.ts", line + "\n")))

    def test_it_only_is_a_debug_leftover(self) -> None:
        text = "it.only('a', () => {\n  expect(f()).toBe(1);\n});\n"
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

    def test_python_that_does_not_parse_is_reported_and_refused_as_unchecked(self) -> None:
        found = nl.lint_text("test_a.py", "def test_a(:\n    pass\n")
        self.assertEqual(refused(found), {"unchecked"})
        self.assertEqual(ids(found), {"unparsed", "unchecked"})

    def test_monkeypatch_of_an_own_module_is_a_mock_of_it(self) -> None:
        text = (
            "def test_a(monkeypatch):\n"
            '    monkeypatch.setattr("billing.rates.lookup", lambda: 3)\n    assert 1 == f()\n'
        )
        self.assertEqual(
            refused(nl.lint_text("test_a.py", text, own_modules=OWN)), {"own_module_mock"}
        )

    def test_a_relative_vi_mock_is_a_mock_of_an_own_module(self) -> None:
        text = "vi.mock('../rates');\nit('a', () => {\n  expect(f()).toBe(2);\n});\n"
        self.assertEqual(refused(nl.lint_text("a.test.ts", text)), {"own_module_mock"})


class OnlyAddedLinesCount(unittest.TestCase):
    """A change is judged on the lines it adds, not on the tests it leaves alone."""

    SOURCE = (
        "import time\n"  # 1
        "\n"  # 2
        "\n"  # 3
        "def test_old():\n"  # 4
        "    time.sleep(1)\n"  # 5
        "    assert f() == 2\n"  # 6
        "\n"  # 7
        "\n"  # 8
        "def test_new():\n"  # 9
        "    time.sleep(1)\n"  # 10
        "    assert f() == 2\n"  # 11
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
        self.assertEqual(changed["tests/test_a.py"].added, {4, 5})
        self.assertEqual(changed["src/app.py"].added, {1})

    def test_a_deletion_marks_the_lines_beside_it_as_touched(self) -> None:
        changed = nl.parse_diff(self.DIFF)
        self.assertEqual(changed["tests/test_a.py"].touched, {11, 12})

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


class CheckerCoverageRequired(unittest.TestCase):
    """Coverage refusals are separate from switchable test-smell rules."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="unchecked-tests-")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.fixture = FIXTURES / "unchecked"

    def write(self, name: str, content: str) -> Path:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(self.project), *args], capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    def command(
        self, *args: str, extra_env: dict[str, str] | None = None
    ) -> tuple[int, dict[str, Any], str]:
        done = subprocess.run(
            [sys.executable, str(ROOT / "kit/scripts/newtest-lint.py"), *args, "--json"],
            cwd=self.project,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MYPYPATH": "", **(extra_env or {})},
        )
        return done.returncode, json.loads(done.stdout), done.stderr

    def initial_commit(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("README.md", "Fixture\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "Fixture")

    def test_staged_cr_only_ts_assertion_is_refused_on_line_two(self) -> None:
        self.initial_commit()
        path = self.write("tests/new.ts", "")
        path.write_bytes(b"function test_result() {\r expect(true).toBe(true);\r}\r")
        self.git("add", "tests/new.ts")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["line"]) for f in body["refusals"]],
                         [("assert_true", 2)])

    def test_ts_mixed_cr_lf_scope_keeps_old_assertion_out(self) -> None:
        self.initial_commit()
        path = self.write("tests/mixed.ts", "")
        old = b"function test_old() {\r expect(true).toBe(true);\r}\n"
        path.write_bytes(old)
        self.git("add", "tests/mixed.ts")
        self.git("commit", "-qm", "Existing mixed TS test")
        path.write_bytes(old + b"function test_new() {\r expect(true).toBe(true);\r}\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["line"]) for f in body["refusals"]],
                         [("assert_true", 5)])

    def test_ts_cr_mode_only_scope_stays_empty(self) -> None:
        self.initial_commit()
        path = self.write("tests/old.ts", "")
        path.write_bytes(b"function test_old() {\r expect(true).toBe(true);\r}\r")
        self.git("add", "tests/old.ts")
        self.git("commit", "-qm", "Existing CR TS test")
        self.git("config", "core.filemode", "true")
        path.chmod(0o755)
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual((code, body["refusals"]), (0, []))

    def test_ts_lf_and_crlf_scope_controls(self) -> None:
        self.initial_commit()
        for index, newline in enumerate((b"\n", b"\r\n")):
            with self.subTest(newline=newline):
                name = f"tests/control{index}.ts"
                path = self.write(name, "")
                path.write_bytes(newline.join((b"function test_result() {",
                                              b" expect(true).toBe(true);", b"}", b"")))
                self.git("add", name)
                code, body, _ = self.command("--base", "HEAD")
                own = [f for f in body["refusals"] if f["file"] == name]
                self.assertEqual(code, 1)
                self.assertEqual([(f["rule"], f["line"]) for f in own], [("assert_true", 2)])

    def test_splitlines_boundaries_keep_new_line_rules_and_mask_spans(self) -> None:
        self.initial_commit()
        boundaries = "\v\f\x1c\x1d\x1e\x85\u2028\u2029"
        for index, boundary in enumerate(boundaries):
            with self.subTest(boundary=repr(boundary)):
                name = f"tests/boundary{index}.ts"
                path = self.write(name, f"/* old{boundary} comment */\n")
                self.git("add", name)
                self.git("commit", "-qm", "Existing scanner boundary")
                path.write_text(f"/* old{boundary} comment */\nconsole.log('new');\n",
                                encoding="utf-8")
                code, body, _ = self.command("--base", "HEAD")
                own = [f for f in body["refusals"] if f["file"] == name]
                self.assertEqual(code, 1)
                self.assertEqual([(f["rule"], f["line"]) for f in own], [("debug_print", 3)])

    def test_offset_scope_uses_lf_after_scanner_only_boundary(self) -> None:
        self.initial_commit()
        path = self.write("tests/offset.ts", "/* old\u2028 comment */\n")
        self.git("add", "tests/offset.ts")
        self.git("commit", "-qm", "Existing offset context")
        path.write_text("/* old\u2028 comment */\nit('new', () => {});\n", encoding="utf-8")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["line"]) for f in body["refusals"]],
                         [("no_assertion", 2)])

    def test_ast_scope_uses_lf_after_form_feed_comment(self) -> None:
        self.initial_commit()
        path = self.write("tests/ast.py", "# old\f# context\n")
        self.git("add", "tests/ast.py")
        self.git("commit", "-qm", "Existing AST context")
        path.write_text("# old\f# context\ndef test_new():\n    assert True\n", encoding="utf-8")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["line"]) for f in body["refusals"]],
                         [("assert_true", 3)])

    def test_source_splitlines_scope_excludes_old_detection(self) -> None:
        self.initial_commit()
        path = self.write("src/app.ts", "// old\v// PYTEST_CURRENT_TEST\n")
        self.git("add", "src/app.ts")
        self.git("commit", "-qm", "Existing source detection")
        path.write_text("// old\v// PYTEST_CURRENT_TEST\n// new\v// PYTEST_CURRENT_TEST\n",
                        encoding="utf-8")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["line"]) for f in body["refusals"]],
                         [("test_detect", 4)])

    def test_scope_mapping_keeps_deletion_neighbours_and_empty_changes(self) -> None:
        change = nl.FileChange(set(), {1, 2})
        self.assertEqual(nl.python_line_scope("old\rnew\nlast", change).touched, {1, 2, 3})
        self.assertEqual(nl.python_line_scope("old\rnew\nlast", nl.FileChange()),
                         nl.FileChange())
        scanner = nl.python_line_scope("old\vnew\nlast", change, scanner=True)
        self.assertEqual(scanner.added, set())
        self.assertEqual(scanner.touched, {1, 2, 3})
        self.assertEqual(nl.python_line_scope("old\vnew\nlast", nl.FileChange(), scanner=True),
                         nl.FileChange())
        beyond = nl.python_line_scope("old\vnew\nlast", nl.FileChange(set(), {0, 3}),
                                      scanner=True)
        self.assertEqual(beyond.touched, {0, 4})

    def test_staged_cr_only_python_addition_keeps_assertion_in_scope(self) -> None:
        self.initial_commit()
        path = self.write("tests/new.py", "")
        path.write_bytes(b"def test_result():\r    assert True\r")
        self.git("add", "tests/new.py")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["rule"] for entry in body["refusals"]}, {"assert_true"})
        self.assertEqual({entry["line"] for entry in body["refusals"]}, {2})

    def test_modified_cr_only_python_assertion_keeps_changed_scope(self) -> None:
        self.initial_commit()
        path = self.write("tests/changed.py", "")
        path.write_bytes(b"def test_result():\r    assert result() == 2\r")
        self.git("add", "tests/changed.py")
        self.git("commit", "-qm", "Existing CR test")
        path.write_bytes(b"def test_result():\r    assert True\r")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["rule"] for entry in body["refusals"]}, {"assert_true"})
        self.assertEqual({entry["line"] for entry in body["refusals"]}, {2})

    def test_mixed_cr_lf_change_does_not_include_unchanged_old_smell(self) -> None:
        self.initial_commit()
        path = self.write("tests/mixed.py", "")
        old = b"def test_old():\r    assert True\r\n"
        path.write_bytes(old)
        self.git("add", "tests/mixed.py")
        self.git("commit", "-qm", "Existing mixed-newline test")
        path.write_bytes(old + b"\ndef test_new():\r    assert True\r\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["rule"] for entry in body["refusals"]}, {"assert_true"})
        self.assertEqual({entry["line"] for entry in body["refusals"]}, {5})

    def test_cr_only_mode_change_does_not_judge_old_smells(self) -> None:
        self.initial_commit()
        path = self.write("tests/old.py", "")
        path.write_bytes(b"def test_old():\r    assert True\r")
        self.git("add", "tests/old.py")
        self.git("commit", "-qm", "Existing CR test")
        self.git("config", "core.filemode", "true")
        path.chmod(0o755)
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(body["refusals"], [])

    def test_mixed_crlf_lf_content_preserves_old_line_exclusion(self) -> None:
        self.initial_commit()
        path = self.write("tests/mixed.py", "")
        old = b"def test_old():\r\n    assert True\r\n"
        path.write_bytes(old)
        self.git("add", "tests/mixed.py")
        self.git("commit", "-qm", "Existing CRLF test")
        path.write_bytes(old + b"\ndef test_new():\n    assert True\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["line"] for entry in body["refusals"]}, {5})

    def test_readable_binary_attribute_cannot_hide_a_new_smell(self) -> None:
        self.initial_commit()
        self.write(".gitattributes", "tests/*.py -diff\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "Binary test attribute")
        self.write("tests/new.py", "def test_result():\n    assert True\n")
        self.git("add", "tests/new.py")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("assert_true", {entry["rule"] for entry in body["refusals"]})
        self.assertEqual([entry["path"] for entry in body["coverage"]], ["tests/new.py"])

    def test_readable_binary_mode_only_change_keeps_old_smells_outside_scope(self) -> None:
        self.initial_commit()
        self.write(".gitattributes", "tests/*.py -diff\n")
        path = self.write("tests/old.py", "def test_old():\n    assert True\n")
        self.git("add", ".gitattributes", "tests/old.py")
        self.git("commit", "-qm", "Existing attributed test")
        self.git("config", "core.filemode", "true")
        path.chmod(0o755)
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(body["refusals"], [])
        self.assertEqual([entry["path"] for entry in body["coverage"]], ["tests/old.py"])

    def test_carriage_return_and_newline_names_keep_distinct_identity(self) -> None:
        self.initial_commit()
        smelly = "tests/test_\rx.py"
        clean = "tests/test_\nx.py"
        self.write(smelly, "def test_result():\n    assert True\n")
        self.write(clean, "def test_result():\n    assert result() == 2\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["path"] for entry in body["coverage"]}, {smelly, clean})
        self.assertEqual({entry["file"] for entry in body["refusals"]}, {smelly})

    def test_literal_bracket_path_does_not_borrow_another_files_hunks(self) -> None:
        self.initial_commit()
        bracket = "tests/[ab].py"
        self.write(bracket, "def test_old():\n    assert True\n# old comment\n")
        self.write("tests/a.py", "def test_a():\n    assert result() == 2\n")
        self.git("add", "tests")
        self.git("commit", "-qm", "Existing literal bracket test")
        self.write(bracket, "def test_old():\n    assert True\n# new comment\n")
        self.write("tests/a.py", "def test_a():\n    assert result() == 3\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(body["refusals"], [])
        self.assertEqual({entry["path"] for entry in body["coverage"]}, {bracket, "tests/a.py"})

    def test_literal_pathspec_magic_name_is_checked_normally(self) -> None:
        self.initial_commit()
        name = ":(bad)/test_result.py"
        self.write(name, "def test_result():\n    assert result() == 2\n")
        self.git("--literal-pathspecs", "add", "--", name)
        self.git("commit", "-qm", "Existing literal magic path")
        self.write(name, "def test_result():\n    assert True\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["file"] for entry in body["refusals"]}, {name})
        self.assertEqual([entry["path"] for entry in body["coverage"]], [name])

    def test_one_git_hunk_failure_keeps_other_coverage_and_findings(self) -> None:
        self.initial_commit()
        names = ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"]
        for name in names:
            self.write(name, "def test_result():\n    assert result() == 2\n")
        self.git("add", "tests")
        self.git("commit", "-qm", "Existing tests")
        for name in names:
            self.write(name, "def test_result():\n    assert True\n")
        real_git = subprocess.run(
            ["which", "git"], capture_output=True, text=True, check=True
        ).stdout.strip()
        shim = self.write(
            ".git/lint-test-bin/git",
            "#!/usr/bin/env python3\nimport os, sys\nargs = sys.argv[1:]\n"
            "if '--unified=0' in args and args[-1].endswith('tests/test_b.py'):\n"
            "    sys.stderr.write('synthetic hunk failure\\n')\n    sys.exit(42)\n"
            f"os.execv({real_git!r}, [{real_git!r}, *args])\n",
        )
        shim.chmod(0o755)
        code, body, error = self.command(
            "--base", "HEAD", extra_env={"PATH": str(shim.parent) + os.pathsep + os.environ["PATH"]}
        )
        self.assertEqual(code, 4)
        self.assertEqual({entry["path"] for entry in body.get("coverage", [])}, set(names))
        self.assertEqual({entry["file"] for entry in body.get("refusals", [])}, set(names))
        self.assertEqual(
            {entry["rule"] for entry in body["refusals"]}, {"assert_true", "unchecked"}
        )
        self.assertIn("next: ", error)

    def test_invalid_python_discloses_disabled_rules_without_claiming_line_checks(self) -> None:
        for rules in (frozenset(), frozenset({Rule.ASSERT_TRUE})):
            with self.subTest(rules=rules):
                found = nl.assess_text("tests/broken.py", "def test_broken(:\n", rules=rules)
                self.assertTrue(nl.refusals(found.findings))
                self.assertNotIn("line smell rules", " ".join(found.coverage["checks_performed"]))
                self.assertIn("disabled smell rules", " ".join(found.coverage["checks_omitted"]))
        enabled = nl.assess_text(
            "tests/broken.py", "def test_broken(:\n    sleep(1)\n", rules=frozenset({Rule.SLEEP})
        )
        self.assertIn("sleep", " ".join(enabled.coverage["checks_performed"]))
        self.assertIn("Python AST test smell rules", enabled.coverage["checks_omitted"])
        self.assertIn("sleep", {entry["rule"] for entry in enabled.findings})

    def test_library_refuses_unknown_test_even_with_no_smell_rules(self) -> None:
        found = nl.lint_text(
            "tests/example.rb",
            self.fixture.joinpath("unsupported.rb.fixture").read_text(),
            rules=frozenset(),
        )
        self.assertTrue(nl.refusals(found), "unsupported required tests silently pass")

    def test_library_refuses_invalid_python_even_with_no_smell_rules(self) -> None:
        found = nl.lint_text(
            "tests/example.py",
            self.fixture.joinpath("invalid.py.fixture").read_text(),
            rules=frozenset(),
        )
        self.assertTrue(nl.refusals(found), "invalid required test syntax silently passes")

    def test_explicit_file_route_uses_test_directory_context(self) -> None:
        path = self.write("tests/example.rb", "describe('release') {}\n")
        code, body, error = self.command("--file", str(path))
        self.assertEqual(code, 1)
        self.assertFalse(body["ok"])
        self.assertIn("next: ", error)

    def test_file_route_retains_all_inputs_when_a_read_fails(self) -> None:
        clean = self.write("tests/clean.py", "def test_result():\n    assert result() == 2\n")
        missing = self.project / "tests/missing.py"
        unknown = self.write("tests/example.rb", "unknown\n")
        code, body, error = self.command(
            "--file", str(clean), "--file", str(missing), "--file", str(unknown)
        )
        self.assertEqual(code, 4)
        coverage = body.get("coverage", [])
        self.assertEqual(
            {entry["path"] for entry in coverage}, {str(clean), str(missing), str(unknown)}
        )
        self.assertIn("next: ", error)

    def test_file_route_reports_decoding_and_directory_read_failures(self) -> None:
        path = self.write("tests/binary.py", "temporary")
        path.write_bytes(b"\xff\xfe")
        directory = self.project / "tests"
        code, body, _ = self.command("--file", str(path), "--file", str(directory))
        self.assertEqual(code, 4)
        self.assertEqual(len(body.get("coverage", [])), 2)

    def test_base_route_inventories_untracked_names_with_tabs_newlines_and_quotes(self) -> None:
        self.initial_commit()
        names = [
            "tests/space name.rb",
            "tests/tab\tname.rb",
            "tests/line\nname.rb",
            'tests/quote"name.rb',
        ]
        for name in names:
            self.write(name, "unknown\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["path"] for entry in body.get("coverage", [])}, set(names))

    def test_base_route_reports_a_binary_test_without_hunks(self) -> None:
        self.initial_commit()
        path = self.write("tests/binary.py", "initial\n")
        self.git("add", "tests/binary.py")
        self.git("commit", "-qm", "Existing test")
        path.write_bytes(b"\x00\xff\xfe")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 4)
        self.assertEqual([entry["path"] for entry in body.get("coverage", [])], ["tests/binary.py"])

    def test_base_route_reports_a_mode_only_unsupported_test(self) -> None:
        self.initial_commit()
        path = self.write("tests/example.rb", "unknown\n")
        self.git("add", "tests/example.rb")
        self.git("commit", "-qm", "Existing test")
        self.git("config", "core.filemode", "true")
        path.chmod(0o755)
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(
            [entry["path"] for entry in body.get("coverage", [])], ["tests/example.rb"]
        )

    def test_tracked_odd_paths_preserve_hunk_identity_and_old_line_scope(self) -> None:
        self.initial_commit()
        names = [
            "tests/space name.py",
            "tests/tab\tname.py",
            "tests/line\nname.py",
            'tests/quote"name.py',
        ]
        for name in names:
            self.write(
                name, "import time\ndef test_old():\n    time.sleep(1)\n    assert result() == 2\n"
            )
        self.git("add", "tests")
        self.git("commit", "-qm", "Existing tests")
        for name in names:
            path = self.project / name
            path.write_text(path.read_text() + "\ndef test_new():\n    assert True\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual({entry["path"] for entry in body["coverage"]}, set(names))
        self.assertEqual({entry["file"] for entry in body["refusals"]}, set(names))
        self.assertEqual({entry["rule"] for entry in body["refusals"]}, {"assert_true"})

    def test_source_snapshot_and_deletion_have_explicit_non_test_accounting(self) -> None:
        self.initial_commit()
        deleted = self.write("tests/deleted.rb", "unsupported\n")
        self.git("add", "tests/deleted.rb")
        self.git("commit", "-qm", "Existing test")
        deleted.unlink()
        self.write("src/example.rb", "ordinary source\n")
        self.write("tests/__snapshots__/new.snap", "snapshot\n")
        code, body, _ = self.command("--base", "HEAD")
        self.assertEqual(code, 0)
        kinds = {entry["path"]: entry["kind"] for entry in body["coverage"]}
        self.assertEqual(
            kinds,
            {
                "tests/deleted.rb": "deletion",
                "src/example.rb": "source",
                "tests/__snapshots__/new.snap": "snapshot",
            },
        )
        self.assertEqual(body["refusals"], [])

    def test_read_error_precedes_smells_but_keeps_both_findings(self) -> None:
        missing = self.project / "tests/missing.py"
        smelly = self.write("tests/smelly.py", "def test_result():\n    assert True\n")
        code, body, _ = self.command("--file", str(missing), "--file", str(smelly))
        self.assertEqual(code, 4)
        self.assertEqual(
            {entry["rule"] for entry in body["refusals"]}, {"assert_true", "unchecked"}
        )
        self.assertEqual(len(body["coverage"]), 2)

    def test_library_reports_limited_language_and_omitted_module_checks(self) -> None:
        python = nl.assess_text(
            "tests/example.py", "def test_result():\n    assert result() == 2\n"
        )
        typescript = nl.assess_text(
            "tests/example.ts", "it('result', () => { expect(result()).toBe(2); });"
        )
        self.assertEqual(python.coverage["outcome"], "partial")
        self.assertIn("module", " ".join(python.coverage["checks_omitted"]))
        self.assertEqual(typescript.coverage["outcome"], "partial")
        self.assertIn("syntax validation", " ".join(typescript.coverage["checks_omitted"]))

    def test_supported_directory_named_test_still_runs_smell_rules(self) -> None:
        path = self.write("tests/example.py", "def test_result():\n    assert True\n")
        code, body, _ = self.command("--file", str(path))
        self.assertEqual(code, 1)
        self.assertIn("assert_true", {entry["rule"] for entry in body.get("refusals", [])})


if __name__ == "__main__":
    unittest.main()
