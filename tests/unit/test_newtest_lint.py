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

    def test_python_that_does_not_parse_is_reported_not_refused(self) -> None:
        found = nl.lint_text("test_a.py", "def test_a(:\n    pass\n")
        self.assertEqual(refused(found), set())
        self.assertEqual(ids(found), {"unparsed"})

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


if __name__ == "__main__":
    unittest.main()
