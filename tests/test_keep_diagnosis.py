"""Keep reports test names and only blames the judge with supporting evidence."""
from __future__ import annotations

import textwrap
import unittest
from unittest.mock import patch

from helpers import GOOD_CODE, SPEC, Project, git

# helpers puts the kit scripts on the import path.
# isort: split
import gate


class KeepDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        spec = SPEC.replace("## Judge", "## Judge\nKeep: `true`")
        n = self.p.piece(spec=spec)
        gate.move(self.p.gh, self.p.root, n, "ready")
        self.ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)

    def test_unittest_headers_supply_names_without_the_summary(self):
        failure = ("FAIL: test_example (suite.Example.test_example)\n"
                   "ERROR: test_other (suite.Example.test_other)\n"
                   "FAILED (failures=1, errors=1)\n")
        with patch.object(gate, "run_keep", side_effect=[(1, failure), (0, "OK")]):
            passed, output = gate.judge(self.p.root, self.ready)
        self.assertTrue(passed, output)
        names = output.split("Failing Keep tests: ", 1)[1]
        self.assertEqual(names, "test_example (suite.Example.test_example), "
                         "test_other (suite.Example.test_other)")

    def test_two_random_failures_do_not_prove_the_bar_is_wrong(self):
        failure = ("judge_add.py::test_D1_add_appends PASSED\n"
                   "FAIL: test_random (suite.Example.test_random)\n"
                   "FAILED (failures=1)\n")
        with patch.object(gate, "run_keep", side_effect=[
                (1, failure), (1, failure), (0, "OK")]):
            passed, output = gate.judge(self.p.root, self.ready)
        self.assertFalse(passed)
        self.assertNotIn(gate.BAR_WRONG, output)
        self.assertIn("test_random", output)

    def test_harmless_judge_warning_does_not_explain_independent_failures(self):
        (self.p.root / "keep_probe.py").write_text(textwrap.dedent('''\
            import pathlib
            import unittest
            import warnings

            counter = pathlib.Path("keep_draws")
            draw = int(counter.read_text()) + 1 if counter.exists() else 1
            counter.write_text(str(draw))
            if pathlib.Path("judge_add.py").exists():
                warnings.simplefilter("always", DeprecationWarning)
                warnings.warn_explicit("old API", DeprecationWarning, "judge_add.py", 2)

            class ExistingTests(unittest.TestCase):
                def test_independent(self):
                    self.assertGreater(draw, 2)

            unittest.main()
        '''))
        self.ready["keep"] = "python3 keep_probe.py"
        passed, output = gate.judge(self.p.root, self.ready)
        self.assertFalse(passed)
        self.assertIn("DeprecationWarning: old API", output)
        self.assertIn("FAIL: test_independent", output)
        self.assertNotIn(gate.BAR_WRONG, output)
        self.assertEqual((self.p.root / "keep_draws").read_text(), "2")

    def test_no_judge_section_contains_the_no_judge_run_output(self):
        judge_file = self.p.root / "judge_add.py"
        original = judge_file.read_bytes()

        def keep(folder, command, timeout, protected_paths):
            if judge_file.exists():
                return 1, "judge_add.py: error: assertion inside a loop\nFAILED (failures=1)"
            return 0, "Existing suite: OK\nKeep took: 0.125 seconds"

        with patch.object(gate, "run_keep", side_effect=keep):
            passed, output = gate.judge(self.p.root, self.ready)
        self.assertFalse(passed)
        self.assertIn(gate.BAR_WRONG, output)
        self.assertEqual(output.split("Without judge files it passes:\n", 1)[1],
                         "Existing suite: OK\nKeep took: 0.125 seconds")
        self.assertEqual(judge_file.read_bytes(), original)

    def test_probe_requires_the_same_judge_diagnostic_in_both_failures(self):
        with patch.object(gate, "run_keep", side_effect=[
                (1, "judge_add.py: error: assertion inside a loop"),
                (1, "FAIL: test_random (suite.Example.test_random)"),
                (0, "OK")]) as keep:
            passed, output = gate.judge(self.p.root, self.ready)
        self.assertFalse(passed)
        self.assertNotIn(gate.BAR_WRONG, output)
        self.assertEqual(keep.call_count, 2)

    def test_skipped_or_failed_probe_does_not_prove_the_bar_is_wrong(self):
        failure = ('Traceback (most recent call last):\n  File "' +
                   str(self.p.root / "judge_add.py") + '\", line 4\nAssertionError: bad judge\n')
        for probe in [(0, "OK (skipped=1)"), (1, "FAIL: test_existing")]:
            with self.subTest(probe=probe), patch.object(gate, "run_keep", side_effect=[
                    (1, failure), (1, failure), probe]) as keep:
                passed, output = gate.judge(self.p.root, self.ready)
            self.assertFalse(passed)
            self.assertNotIn(gate.BAR_WRONG, output)
            self.assertEqual(keep.call_count, 3)
            self.assertTrue((self.p.root / "judge_add.py").is_file())

    def test_explicit_lint_errors_and_exception_tracebacks_support_diagnosis(self):
        failures = ["judge_add.py:2:3: E501 line too long\n",
                    "judge_add.py:2: error: bad assertion\n",
                    'Traceback (most recent call last):\n'
                    '  File "judge_add.py", line 4\n    assert False\nAssertionError\n']
        for failure in failures:
            with self.subTest(failure=failure), patch.object(gate, "run_keep", side_effect=[
                    (1, failure), (1, failure), (0, "OK")]):
                passed, output = gate.judge(self.p.root, self.ready)
            self.assertFalse(passed)
            self.assertIn(gate.BAR_WRONG, output)

    def test_information_and_bare_frames_are_not_failure_evidence(self):
        for message in ["judge_add.py:2: note: old API",
                        "judge_add.py:2: warning: old API",
                        "judge_add.py:2: W123 old API",
                        "judge_add.py: informational message",
                        '  File "judge_add.py", line 4']:
            failure = message + "\nFAIL: test_independent (suite.ExistingTests)\n"
            with self.subTest(message=message), patch.object(gate, "run_keep", side_effect=[
                    (1, failure), (1, failure), (0, "OK")]) as keep:
                passed, output = gate.judge(self.p.root, self.ready)
            self.assertFalse(passed)
            self.assertNotIn(gate.BAR_WRONG, output)
            self.assertEqual(keep.call_count, 2)

    def test_existing_runner_names_remain_available(self):
        self.assertEqual(gate.failing_test_names(
            "FAILED tests/test_example.py::test_example - AssertionError\n"
            "not ok 2 - retains the habit\nFAIL test_flaky_keep\n"),
            ["tests/test_example.py::test_example - AssertionError",
             "retains the habit", "test_flaky_keep"])
