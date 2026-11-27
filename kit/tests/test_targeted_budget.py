"""Targeted timeouts through the command, Stop hook and build flow."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge


KIT = Path(__file__).resolve().parents[1]
FILES = ["tests/test_first.py", "tests/test spaced.py"]
DRIVER = """import json
import os
from pathlib import Path
import sys
import time

def record(kind):
    with open(os.environ['TARGETED_BUDGET_CALLS'], 'a') as stream:
        stream.write(json.dumps({'kind': kind, 'args': sys.argv[1:]}) + '\\n')

record('started')
if sys.argv[1] == '--targeted':
    if Path('app.py').read_text().strip() == 'value = 1':
        print('AssertionError: the fixture needs the implementation')
        sys.exit(1)
    time.sleep(3)
record('finished')
"""
# Keep real process creation, termination and result handling. Record the budget
# the caller requested, then shorten only the sleeping fixture's wall-clock wait.
PROBE = """import json
import os
import sys
import time

sys.path.insert(0, os.environ['TARGETED_BUDGET_SCRIPTS'])
import common

original = common.run_shell
def run_shell(command, cwd, timeout, *args, **kwargs):
    if '--targeted' not in command:
        return original(command, cwd, timeout, *args, **kwargs)
    with open(os.environ['TARGETED_BUDGET_LIMITS'], 'a') as stream:
        stream.write(json.dumps(timeout) + '\\n')
    journal = os.environ['TARGETED_BUDGET_CALLS']
    before = os.path.getsize(journal) if os.path.exists(journal) else 0
    original_wait = common.wait_limited
    def wait_limited(wait, limit, project):
        # Start the shortened wait only once the fixture has recorded its start.
        # Interpreter startup can be slow on a busy test machine.
        deadline = time.monotonic() + 10
        while not os.path.exists(journal) or os.path.getsize(journal) == before:
            if time.monotonic() >= deadline:
                raise AssertionError('The sleeping fixture did not start')
            time.sleep(0.01)
        return original_wait(wait, 0.2, project)
    common.wait_limited = wait_limited
    try:
        return original(command, cwd, timeout, *args, **kwargs)
    finally:
        common.wait_limited = original_wait
common.run_shell = run_shell
"""


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class BudgetFixture:
    def __init__(self, case, minutes=15, files=FILES, parent=None):
        folder = tempfile.TemporaryDirectory(dir=parent)
        case.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.calls = self.folder / "calls.jsonl"
        self.limits = self.folder / "limits.jsonl"
        self.runtime = self.folder / "runtime"
        self.runtime.mkdir()
        probe = self.folder / "probe"
        probe.mkdir()
        (probe / "sitecustomize.py").write_text(PROBE)
        self.files = list(files)
        self.settings = {
            "Test command": shlex.quote(sys.executable) + " -S runner.py --full",
            "Test files command": shlex.quote(sys.executable) + " -S runner.py --targeted {files}",
            "Check command": shlex.quote(sys.executable) + " -S runner.py --check",
            "Session minutes": minutes,
            "Test minutes": 30,
        }
        work, _ = make_repo(folder.name, {
            ".gitignore": ".loop/\n",
            "loop.json": json.dumps(self.settings),
            "runner.py": DRIVER,
            "app.py": "value = 1\n",
            **{name: "# Locked fixture test.\n" for name in FILES},
        })
        self.work = Path(work)
        self.start = common.git(["rev-parse", "HEAD"], cwd=work)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        self.env.update(
            LOOP_PROJECT=work, LOOP_START=self.start, LOOP_ROLE="builder",
            LOOP_TMPDIR=str(self.runtime), LOOP_LOCKED="\n".join(self.files),
            TARGETED_BUDGET_SCRIPTS=str(KIT / "scripts"),
            TARGETED_BUDGET_CALLS=str(self.calls), TARGETED_BUDGET_LIMITS=str(self.limits),
            PYTHONPATH=str(probe) + os.pathsep + self.env.get("PYTHONPATH", ""))

    def implement(self):
        (self.work / "app.py").write_text("value = 2\n")
        run_git(["add", "app.py"], self.work)
        run_git(["commit", "-m", "Implement fixture behaviour"], self.work)

    def check(self, cwd=None, env=None):
        return subprocess.run([str(KIT / "bin/loop"), "check"], cwd=cwd or self.work,
                              env=env or self.env, capture_output=True, text=True, timeout=20)

    def stop(self, session):
        return subprocess.run([sys.executable, str(KIT / "hooks/stop.py")], cwd=self.work,
                              input=json.dumps({"session_id": session}), env=self.env,
                              capture_output=True, text=True, timeout=20)

    def started(self):
        return [row["args"] for row in records(self.calls) if row["kind"] == "started"]


class TargetedBudgetTest(unittest.TestCase):
    def timeout_line(self, result, seconds, count):
        output = (result.stdout + result.stderr).strip()
        self.assertNotIn("Traceback", output)
        self.assertEqual(len(output.splitlines()), 1, output)
        self.assertRegex(output.lower(), r"timed?[- ]?out|timeout")
        self.assertIn("test files command", output.lower())
        self.assertRegex(output.lower(), r"may[^\n]*(?:running|run)[^\n]*more than[^\n]*files")
        self.assertRegex(output.lower(), r"\b%d\s+(?:test\s+)?files?\b" % count)
        self.assertRegex(output.lower(), r"\b(?:%d(?:\.0+)?\s*(?:s\b|seconds?)|%d(?:\.0+)?\s*(?:m\b|minutes?))"
                         % (seconds, seconds // 60))
        return output

    def test_loop_check_stops_at_one_third_of_session_with_a_ten_minute_floor(self):
        for minutes, files in ((15, FILES[:1]), (60, list(reversed(FILES)))):
            with self.subTest(minutes=minutes, files=files):
                fixture = BudgetFixture(self, minutes, files)
                fixture.implement()
                result = fixture.check()
                budget = max(600, minutes * 20)
                self.assertEqual(records(fixture.limits), [budget],
                                 "loop check must request the targeted budget, not Test minutes")
                self.timeout_line(result, budget, len(files))
                self.assertEqual(fixture.started()[0], ["--targeted", *sorted(files)])
                self.assertFalse(any(row["kind"] == "finished" and row["args"][0] == "--targeted"
                                     for row in records(fixture.calls)),
                                 "The sleeping Test files command must be terminated")

    def test_second_loop_check_at_the_same_head_repeats_the_line_without_rerunning_tests(self):
        for files in (FILES, list(reversed(FILES)) + FILES[:1]):
            with self.subTest(files=files):
                fixture = BudgetFixture(self, files=files)
                fixture.implement()
                first = fixture.check()
                before = [args for args in fixture.started() if args[0] == "--targeted"]
                self.assertEqual(before, [["--targeted", *sorted(set(files))]])
                second = fixture.check()
                self.assertEqual([args for args in fixture.started() if args[0] == "--targeted"], before,
                                 "A timeout at this HEAD must not start the Test files command again")
                line = self.timeout_line(first, 600, len(set(files)))
                self.assertEqual((second.stdout + second.stderr).strip(), line)

    def test_stop_after_a_timeout_runs_no_command_and_allows_the_stop(self):
        fixture = BudgetFixture(self)
        fixture.implement()
        fixture.check()
        self.assertEqual([args for args in fixture.started() if args[0] == "--targeted"],
                         [["--targeted", *sorted(FILES)]])
        before = records(fixture.calls)
        result = fixture.stop("timed-out-builder")
        self.assertEqual(records(fixture.calls), before,
                         "Stop must reuse the timeout without running Test files or Check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.stdout.strip(), "The timeout must not block the stop")


class TargetedBudgetFlowTest(FakeClaudeGh):
    def test_tests_step_reuses_timeout_records_event_and_log_and_informs_reviewer(self):
        fixture = BudgetFixture(self, files=FILES[:1], parent=self.tmp)
        run_git(["push", "origin", "main:loop/main"], fixture.work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Bound the targeted test run", "body": "Exercise a slow targeted command.",
                "comments": []})}]},
            *[{"match": command, "responses": [{}]} for command in
              ("issue comment", "issue edit", "issue close", "pr edit")],
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
        ])
        self.claude({
            "test-writer": [{"files": {"tests/test_new.py": "# New locked fixture test.\n"},
                             "reply": "TESTS:\ntests/test_new.py"}],
            "builder": [{"files": {"app.py": "value = 2\n"}, "reply": "BUILT:\nUpdated app.py."}],
            "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}"}],
        })
        real_session = flow.session.run
        checks = []

        def session(*args, **kwargs):
            reply = real_session(*args, **kwargs)
            if args[0] == "builder":
                call = self.claude_calls()[-1]
                env = dict(fixture.env, **call["env"])
                # A real loop check records the timeout in this build's runtime.
                # Omit Stop so the flow must read that record itself.
                checks.append(fixture.check(cwd=call["cwd"], env=env))
            return reply

        env = {k: v for k, v in fixture.env.items()
               if not k.startswith("LOOP_")}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(flow.session, "run", side_effect=session), \
                mock.patch.object(merge, "merge", return_value=merge.Result(True, False, "merged", "abc")), \
                mock.patch.object(merge, "find_pr", return_value=None):
            result = flow.build(7, str(fixture.work))

        self.assertEqual(result.status, "merged", result.reason)
        # Fails-first runs on the base; only the builder runs the sleeping command.
        targeted = [args for args in fixture.started() if args[0] == "--targeted"]
        self.assertEqual(targeted, [["--targeted", "tests/test_new.py"]] * 2,
                         "The flow's tests step must not repeat the builder's timed-out command")
        self.assertEqual(len(checks), 1)
        line = TargetedBudgetTest.timeout_line(self, checks[0], 600, 1)
        events = [event for event in records(fixture.work / ".loop/events.jsonl")
                  if event["kind"] == "targeted-timeout"]
        self.assertTrue(events, "Record a targeted-timeout event for the timed-out run")
        for event in events:
            self.assertEqual(event["issue"], 7)
            self.assertEqual(event["files"], ["tests/test_new.py"])
            self.assertIsInstance(event["seconds"], (int, float))
            self.assertGreater(event["seconds"], 0)
        log = (fixture.work / ".loop/loop.out").read_text()
        self.assertIn(line, log)
        reviewer = next(call for call in self.claude_calls() if call["role"] == "reviewer")
        self.assertIn(line, reviewer["prompt"])


if __name__ == "__main__":
    unittest.main()
