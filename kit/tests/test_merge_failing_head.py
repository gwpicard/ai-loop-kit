"""Exercise merge attempts after the full suite finds a broken loop head."""
import json
import shlex
import subprocess
import sys
import unittest
from unittest import mock

from kit.tests import test_merge_full_suite_cadence as cadence
from kit.tests.helpers import run_git


class FailingHeadTest(unittest.TestCase):
    def setUp(self):
        self.fixture = cadence.FullSuiteCadenceTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.output = ""

    def attempt(self):
        real_run = subprocess.run

        def capture(args, *positional, **keywords):
            result = real_run(args, *positional, **keywords)
            if args[:2] == [sys.executable, "-c"]:
                self.output = result.stdout
            return result

        with mock.patch.object(subprocess, "run", side_effect=capture):
            return self.fixture.merge_process()

    def broken_head(self):
        f = self.fixture
        f.seed_three_merges()
        base = f.candidate({"FAIL": "earlier regression\n"})
        run_git(["push", "origin", base + ":loop/main"], f.work)
        f.candidate()
        result = self.attempt()
        self.assertFalse(result["ok"], result)
        self.assertIn("loop branch", result["reason"].lower())
        self.assertEqual([c for c in f.commands() if c.startswith("full ")],
                         ["full " + f.sha, "full " + base])
        f.trace.write_text("")
        return base

    def test_second_merge_on_known_failing_head_runs_targeted_checks_and_waits(self):
        f = self.fixture
        base = self.broken_head()
        f.candidate({"app.py": "another issue\n", "tests/test_other.py": "test\n"})
        result = self.attempt()
        with self.subTest(behaviour="commands"):
            self.assertEqual(f.commands(), [
                "targeted " + json.dumps(["tests/test_locked.py", "tests/test_other.py"]),
                "check"], "an unchanged failing head must not cause another full run")
        with self.subTest(behaviour="waiting"):
            self.assertFalse(result["ok"], "the issue must wait for the loop branch to pass")
            self.assertFalse(result["park"], result["reason"])
            self.assertFalse(any(c[:2] == ["pr", "merge"] for c in f.calls()))
        with self.subTest(behaviour="loop output"):
            lines = [line for line in self.output.splitlines()
                     if base[:10] in line and "wait" in line.lower()
                     and not line.startswith("{")]
            self.assertEqual(len(lines), 1, self.output)

    def test_changed_loop_head_is_tested_when_the_cadence_is_due(self):
        f = self.fixture
        self.broken_head()
        # Moving the head without fixing the regression must invalidate its result too.
        changed = f.candidate({"app.py": "loop branch moved\n"})
        run_git(["push", "origin", changed + ":loop/main"], f.work)
        f.candidate()
        self.attempt()
        self.assertEqual([c for c in f.commands() if c.startswith("full ")],
                         ["full " + f.sha, "full " + changed])
        f.trace.write_text("")
        f.candidate()
        self.attempt()
        self.assertEqual(f.commands(), [
            "targeted " + json.dumps(["tests/test_locked.py"]), "check"],
            "the newly tested failing head must have its own saved result")

    def test_test_command_refusal_keeps_failure_names_in_a_bounded_tail(self):
        f = self.fixture
        cases = [
            (False, ("FAILED tests/test_alpha.py::test_empty",
                     "FAILED tests/test_beta.py::test_order")),
            (True, ("FAIL: test_order (checks.BetaTest)",
                    "FAIL: test_empty (checks.AlphaTest)")),
        ]
        for on_loop, names in cases:
            with self.subTest(output=names, on_loop=on_loop):
                run_git(["checkout", "--detach", "origin/loop/main"], f.work)
                program = (
                    "from pathlib import Path; import sys; "
                    "bad = Path('FAIL').exists(); "
                    "print('\\n'.join(['old-output-%03d' % i for i in range(300)] + "
                    + repr(list(names) + ["Some checks failed"]) + ") if bad else 'Passed'); "
                    "sys.exit(int(bad))"
                )
                target = shlex.quote(str(f.trace))
                f.configure(**{
                    "Full suite every": 1,
                    "Test command": "echo full $(git rev-parse HEAD) >> %s; %s -c %s" % (
                        target, shlex.quote(sys.executable), shlex.quote(program)),
                })
                f.candidate({"FAIL": "candidate regression\n"})
                if on_loop:
                    run_git(["push", "origin", f.sha + ":loop/main"], f.work)
                    f.candidate()
                result = self.attempt()
                self.assertFalse(result["ok"])
                self.assertEqual(result["park"], on_loop, result["reason"])
                with self.subTest(behaviour="names"):
                    for name in names:
                        self.assertIn(name, result["reason"])
                with self.subTest(behaviour="bound"):
                    self.assertNotIn("old-output-000", result["reason"])
                    # Allow a 60-line tail and refusal context for each failed command.
                    self.assertLessEqual(len(result["reason"].splitlines()), 130 if on_loop else 65)
