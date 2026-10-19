"""The project tests are required even when a piece omits or narrows Keep."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import GOOD_CODE, SPEC, Project, git

# isort: split
import gate
import loopkit
import pr
import run
from loopkit import Refused

REGRESSION = "python3 regression.py"
SUITE = '''import subprocess
import unittest
import habits
print("REGRESSION COMMIT", subprocess.check_output(
    ["git", "rev-parse", "HEAD"], text=True).strip(), flush=True)
class OldTests(unittest.TestCase):
    def test_existing_behaviour(self):
        self.assertEqual(habits.existing(), "kept")
unittest.main()
'''
BASE = 'def add(items, name):\n    return []\n\ndef existing():\n    return "kept"\n'


class RequiredRegressionTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        (self.p.root / "habits.py").write_text(BASE)
        (self.p.root / "regression.py").write_text(SUITE)
        git(self.p.root, "add", "habits.py", "regression.py")
        git(self.p.root, "commit", "--quiet", "-m", "Existing behaviour and tests")
        self.p.loop_section(REGRESSION)

    def ready(self, keep=""):
        spec = SPEC + (f"\nKeep: `{keep}`\n" if keep else "")
        n = self.p.piece(spec=spec)
        gate.move(self.p.gh, self.p.root, n, "ready")
        return n, gate.last_record(self.p.gh.comments(n), "ready")

    def candidate(self, n, broken=False):
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        code = GOOD_CODE + '\ndef existing():\n    return "kept"\n'
        if broken:
            code = code.replace('return "kept"', 'return "lost"')
        (folder / "habits.py").write_text(code)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build candidate")
        return folder

    def test_D1_submit_refuses_unrelated_regression_without_keep(self):
        n, _ = self.ready()
        folder = self.candidate(n, broken=True)
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
        self.assertIn(REGRESSION, caught.exception.reason)
        self.assertIn("regression", caught.exception.reason.lower())
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def test_D1_long_failure_still_names_regression_command(self):
        (self.p.root / "regression.py").write_text("print('x' * 5000)\n" + SUITE)
        git(self.p.root, "add", "regression.py")
        git(self.p.root, "commit", "--quiet", "-m", "Verbose project tests")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, _ = self.ready()
        folder = self.candidate(n, broken=True)
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
        self.assertIn(REGRESSION, caught.exception.reason)

    def test_D2_narrow_keep_adds_to_recorded_full_suite(self):
        observed = []
        original = loopkit.run_judge

        def observe(folder, command, **kwargs):
            observed.append((command, git(folder, "rev-parse", "HEAD")))
            return original(folder, command, **kwargs)

        with patch.object(loopkit, "run_judge", side_effect=observe):
            n, ready = self.ready("printf narrow")
            folder = self.candidate(n)
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
        self.assertEqual(ready["regression"], REGRESSION)
        self.assertEqual(ready["regression_limit"], 900)
        self.assertEqual(ready["regression_main"]["exit"], 0)
        self.assertIn("Ran 1 test", ready["regression_main"]["output"])
        self.assertEqual([c for c, _ in observed if c == REGRESSION], [REGRESSION] * 2)
        self.assertEqual([c for c, _ in observed if c == "printf narrow"], ["printf narrow"] * 2)
        self.assertIn((REGRESSION, ready["main"]), observed)
        self.assertIn((REGRESSION, git(folder, "rev-parse", "HEAD")), observed)

    def test_D3_red_main_refuses_ready_with_next_step(self):
        self.p.loop_section("python3 -c 'raise AssertionError(\"baseline broken\")'")
        n = self.p.piece()
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("regression", caught.exception.reason.lower())
        self.assertIn("main", caught.exception.reason)
        self.assertTrue(caught.exception.next_step)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])

    def test_D3_missing_test_command_cannot_be_replaced_by_keep(self):
        self.p.loop_section("")
        n = self.p.piece(spec=SPEC + "\nKeep: `true`\n")
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("Test command", caught.exception.reason)
        self.assertIn("AGENTS.md", caught.exception.next_step)

    def test_ready_accepts_passing_tests_that_log_expected_file_errors(self):
        suite = SUITE.replace("        self.assertEqual", """        try:
            with open("optional-config.json") as config:
                config.read()
        except FileNotFoundError as error:
            print(error)
        self.assertEqual""")
        (self.p.root / "regression.py").write_text(suite)
        git(self.p.root, "add", "regression.py")
        git(self.p.root, "commit", "--quiet", "-m", "Test optional configuration fallback")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, ready = self.ready()
        self.assertEqual(ready["regression_main"]["exit"], 0)
        self.assertIn("No such file or directory", ready["regression_main"]["output"])
        self.assertIn("Ran 1 test", ready["regression_main"]["output"])
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_submit_accepts_passing_tests_that_log_expected_file_errors(self):
        n, _ = self.ready()
        folder = self.candidate(n)
        code = GOOD_CODE + '''\ndef existing():
    try:
        with open("optional-config.json") as config:
            config.read()
    except FileNotFoundError as error:
        print(error)
    return "kept"
'''
        (folder / "habits.py").write_text(code)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Preserve behaviour with optional configuration")
        checked = {}
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, evidence=checked)
        self.assertIn("No such file or directory", checked["output"])
        self.assertIn("Ran 1 test", checked["output"])
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_D4_old_ready_record_requires_ready_again(self):
        n, ready = self.ready()
        for key in ("regression", "regression_limit", "regression_main"):
            ready.pop(key, None)
        self.p.gh.comment(n, loopkit.record_text(ready, "Old ready record"))
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn("run ready again", caught.exception.next_step)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_D5_pull_request_uses_final_submit_evidence_after_review_change(self):
        n, ready = self.ready()
        folder = self.candidate(n)
        passed, attempt = gate.judge(folder, ready)
        self.assertTrue(passed, attempt)
        old = git(folder, "rev-parse", "HEAD")
        with (folder / "habits.py").open("a") as out:
            out.write("\n# Reviewed\n")
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Reviewer fix")
        final = git(folder, "rev-parse", "HEAD")
        pr.open_pull_request(self.p.gh, self.p.root, folder, n, self.p.gh.issue(n), 1, attempt)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn(f"REGRESSION COMMIT {final}", body)
        self.assertNotIn(f"REGRESSION COMMIT {old}", body)
        self.assertIn(REGRESSION, body)
        submit = gate.last_record(self.p.gh.comments(n), "submit")
        self.assertEqual(submit["commit"], final)
        self.assertEqual(submit["regression"]["exit"], 0)

    def test_D6_timeout_and_zero_tests_have_distinct_reasons(self):
        for command, reason in (("python3 -c 'import time; time.sleep(3)'", "timed out"),
                                ("python3 -m unittest discover -s empty", "collected no tests"),
                                ("python3 -m missing_test_runner", "test runner")):
            with self.subTest(command=command):
                self.p.loop_section(command)
                agents = self.p.root / "AGENTS.md"
                agents.write_text(agents.read_text() + "Keep limit: 0.02\n")
                (self.p.root / "empty").mkdir(exist_ok=True)
                (self.p.root / "empty" / "__init__.py").touch()
                git(self.p.root, "add", "AGENTS.md", "empty")
                git(self.p.root, "commit", "--quiet", "-m", "Regression environment")
                git(self.p.root, "push", "--quiet", "origin", "main")
                n = self.p.piece()
                with self.assertRaises(Refused) as caught:
                    gate.move(self.p.gh, self.p.root, n, "ready")
                self.assertIn(reason, caught.exception.reason)
                self.assertIn(command, caught.exception.reason)

    def test_D6_submit_also_refuses_zero_tests_and_timeout(self):
        n, ready = self.ready()
        folder = self.candidate(n)
        for command, reason in (("printf 'Ran 0 tests'", "collected no tests"),
                                ("printf 'no tests ran'", "collected no tests"),
                                ("python3 -m missing_test_runner", "test runner"),
                                ("python3 -c 'import time; time.sleep(3)'", "timed out")):
            with self.subTest(command=command):
                passed, output = gate.judge(folder, {**ready, "regression": command,
                                                     "regression_limit": 1})
                self.assertFalse(passed, output)
                self.assertIn(reason, output)
                self.assertIn(command, output)

    def test_D7_scaffold_ready_without_test_runner(self):
        self.p.loop_section("python3 -m missing_test_runner", prepare="exit 1")
        spec = SPEC.replace("## Judge", "## Judge\nKind: scaffold")
        n = self.p.piece(spec=spec)
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def test_D8_identical_keep_runs_once_per_gate(self):
        observed = []
        original = loopkit.run_judge

        def observe(folder, command, **kwargs):
            observed.append(command)
            return original(folder, command, **kwargs)

        with patch.object(loopkit, "run_judge", side_effect=observe):
            n, _ = self.ready(REGRESSION)
            self.assertEqual(observed.count(REGRESSION), 1)
            folder = self.candidate(n)
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder)
            self.assertEqual(observed.count(REGRESSION), 2)


if __name__ == "__main__":
    unittest.main()
