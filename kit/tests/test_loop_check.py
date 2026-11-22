"""Session checks through the installed command, using real fixture tests."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
from kit.tests.test_guard import GuardCase
import loop


KIT = Path(__file__).resolve().parents[1]
PASSING = """import unittest

class Example(unittest.TestCase):
    def test_example(self):
        self.assertEqual(2 + 2, 4)

if __name__ == '__main__':
    unittest.main()
"""
FAILING = PASSING.replace(
    "self.assertEqual(2 + 2, 4)",
    "print('\\n'.join('failure-line-%d' % i for i in range(4000)))\n"
    "        self.fail('fixture assertion failed')")
DRIVER = """import json
from pathlib import Path
import subprocess
import sys

args = sys.argv[1:]
with open('calls.jsonl', 'a') as f:
    f.write(json.dumps(args) + '\\n')
print('successful command noise', flush=True)
if args == ['--check']:
    print('check output', file=sys.stderr)
    sys.exit(1 if Path('check-fails').exists() else 0)
files = ['tests/test_locked.py'] if args == ['--full'] else args[1:]
for name in files:
    result = subprocess.run([sys.executable, name])
    if result.returncode:
        sys.exit(result.returncode)
"""


class LoopCheckTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.command = shlex.quote(sys.executable) + " runner.py"
        self.settings = {
            "Test command": self.command + " --full",
            "Test files command": self.command + " --targeted {files}",
            "Check command": self.command + " --check",
        }
        work, _ = make_repo(tmp.name, {
            "loop.json": json.dumps(self.settings),
            "runner.py": DRIVER,
            "tests/test_locked.py": PASSING,
            "tests/test_second_locked.py": PASSING,
            "tests/test_changed.py": PASSING,
            "tests/test spaced.py": PASSING,
            "tests/test_untouched.py": FAILING,
            "src/app.py": "value = 1\n",
        })
        self.work = Path(work)
        self.start = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()

    def check(self, locked=()):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update(LOOP_START=self.start, LOOP_LOCKED="\n".join(locked),
                   LOOP_PROJECT=str(self.work), LOOP_ROLE="builder",
                   LOOP_TEST_COMMAND=self.settings["Test command"],
                   LOOP_TEST_FILES_COMMAND=self.settings["Test files command"])
        return subprocess.run([str(KIT / "bin/loop"), "check"], cwd=self.work,
                              env=env, capture_output=True, text=True, timeout=30)

    def calls(self):
        path = self.work / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_targeted_union_then_check_with_one_pass_line(self):
        for order in (("tests/test_locked.py", "tests/test_second_locked.py"),
                      ("tests/test_second_locked.py", "tests/test_locked.py", "tests/test_locked.py")):
            with self.subTest(locked=order):
                (self.work / "tests/test_changed.py").write_text(
                    PASSING + "\n# Input order: %r\n" % (order,))
                run_git(["add", "tests/test_changed.py"], self.work)
                run_git(["commit", "-m", "Change a test after session start"], self.work)
                (self.work / "tests/test spaced.py").write_text(PASSING + "\n# Unsaved change.\n")
                (self.work / "src/app.py").write_text("value = 2\n")
                journal = self.work / "calls.jsonl"
                if journal.exists():
                    journal.unlink()
                result = self.check(order)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                selected = sorted({*order, "tests/test_changed.py", "tests/test spaced.py"})
                self.assertEqual(self.calls(), [["--targeted", *selected], ["--check"]])
                self.assertEqual(result.stderr, "")
                self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
                self.assertIn("passed:", result.stdout.lower())
                for name in selected:
                    self.assertIn(name, result.stdout)

    def test_long_failure_names_command_and_caps_output(self):
        (self.work / "tests/test_locked.py").write_text(FAILING)
        result = self.check(["tests/test_locked.py"])
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(self.command + " --targeted tests/test_locked.py", output)
        self.assertEqual(self.calls(), [["--targeted", "tests/test_locked.py"]])
        limits = [value for name, value in vars(loop).items()
                  if name.isupper() and ("LINE" in name or "OUTPUT" in name)
                  and type(value) is int and value > 0]
        self.assertTrue(limits, "Name the output line cap as a module constant in loop.py")
        cap = max(limits)
        self.assertLess(cap, 4000, "The fixture must exceed the output cap")
        self.assertLessEqual(len(output.splitlines()), cap + 3, output)
        self.assertTrue("failure-line-" in output or "fixture assertion failed" in output, output)
        self.assertNotIn("passed:", output.lower())

    def test_check_failure_is_reported_after_passing_tests(self):
        (self.work / "check-fails").touch()
        result = self.check(["tests/test_locked.py"])
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(self.command + " --check", output)
        self.assertIn("check output", output)
        self.assertEqual(self.calls(), [["--targeted", "tests/test_locked.py"], ["--check"]])
        self.assertNotIn("passed:", output.lower())

    def test_without_test_files_command_runs_full_test_then_check(self):
        self.settings["Test files command"] = ""
        (self.work / "loop.json").write_text(json.dumps(self.settings))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls(), [["--full"], ["--check"]])
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        self.assertIn("passed:", result.stdout.lower())

    def test_empty_selection_says_so_without_running_full_suite(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no test files to run", (result.stdout + result.stderr).lower())
        self.assertEqual(self.calls(), [["--check"]])

    def test_session_briefs_name_loop_check_and_review_budget(self):
        for name in ("builder", "test-writer", "reviewer"):
            with self.subTest(brief=name):
                text = (KIT / "briefs" / (name + ".md")).read_text()
                self.assertIn("loop check", text)
        review = " ".join((KIT / "briefs/reviewer.md").read_text().lower().split())
        self.assertIn("stop hook", review)
        self.assertRegex(review, r"(?:unless|only if|only when).*finding")


class LoopCheckGuardTest(GuardCase):
    def test_full_suite_refusal_directs_every_role_to_loop_check(self):
        for role in ("builder", "test-writer", "reviewer", "pass"):
            for command in ("make test", "true && make test"):
                with self.subTest(role=role, command=command):
                    result = self.bash(command, role=role, test="make test",
                                       files="make unit {files}")
                    self.refused(result, "loop check")
