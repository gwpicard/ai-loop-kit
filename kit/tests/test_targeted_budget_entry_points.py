"""Timeouts first encountered by Stop or flow, and their lifetime across commits."""
import json
import os
from pathlib import Path
import time
import unittest
from unittest import mock

from kit.tests import test_targeted_budget as budget
from kit.tests.helpers import run_git
import common
import flow
import merge


class TargetedBudgetEntryPointsTest(unittest.TestCase):
    def test_stop_records_its_own_timeout_for_later_checks(self):
        fixture = budget.BudgetFixture(self)
        fixture.implement()
        stopped = fixture.stop("first-timeout")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertEqual(stopped.stdout + stopped.stderr, "")
        self.assertEqual(fixture.started(), [["--targeted", *sorted(budget.FILES)]])
        before = budget.records(fixture.calls)
        result = fixture.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        budget.TargetedBudgetTest.timeout_line(self, result, 600, len(budget.FILES))
        self.assertEqual(budget.records(fixture.calls), before)

    def test_a_new_commit_runs_again_after_a_timeout(self):
        fixture = budget.BudgetFixture(self)
        fixture.implement()
        first = fixture.check()
        budget.TargetedBudgetTest.timeout_line(self, first, 600, len(budget.FILES))
        run_git(["commit", "--allow-empty", "-m", "Advance the fixture head"], fixture.work)
        second = fixture.check()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        budget.TargetedBudgetTest.timeout_line(self, second, 600, len(budget.FILES))
        self.assertEqual(fixture.started(), [["--targeted", *sorted(budget.FILES)]] * 2)
        self.assertEqual(budget.records(fixture.limits), [600, 600])


class TargetedBudgetFreshFlowTest(budget.FakeClaudeGh):
    def test_flow_bounds_a_fresh_targeted_run_and_reports_the_timeout(self):
        fixture = budget.BudgetFixture(self, parent=self.tmp)
        run_git(["push", "origin", "main:loop/main"], fixture.work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Bound targeted tests", "body": "Exercise a slow targeted command.",
                "comments": []})}]},
            *[{"match": command, "responses": [{}]} for command in
              ("issue comment", "issue edit", "issue close", "pr edit")],
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
        ])
        self.claude({
            "test-writer": [{"files": {"tests/test_new.py": "# Locked fixture test.\n"},
                             "reply": "TESTS:\ntests/test_new.py"}],
            "builder": [{"files": {"app.py": "value = 2\n"}}],
            "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}"}],
        })
        real_run, real_wait = common.run_shell, common.wait_limited
        limits = []

        def run(command, cwd, timeout, *args, **kwargs):
            if "--targeted" not in command or Path(cwd, "app.py").read_text().strip() != "value = 2":
                return real_run(command, cwd, timeout, *args, **kwargs)
            limits.append(timeout)
            before = fixture.calls.stat().st_size

            def wait(waiter, limit, project):
                deadline = time.monotonic() + 10
                while fixture.calls.stat().st_size == before:
                    if time.monotonic() >= deadline:
                        raise AssertionError("The targeted fixture did not start")
                    time.sleep(0.01)
                return real_wait(waiter, 0.2, project)

            with mock.patch.object(common, "wait_limited", side_effect=wait):
                return real_run(command, cwd, timeout, *args, **kwargs)

        env = {k: v for k, v in fixture.env.items() if not k.startswith("LOOP_")}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(common, "run_shell", side_effect=run), \
                mock.patch.object(merge, "merge", return_value=merge.Result(True, False, "merged", "abc")), \
                mock.patch.object(merge, "find_pr", return_value=None):
            result = flow.build(7, str(fixture.work))

        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(limits, [600])
        self.assertEqual(fixture.started(), [["--targeted", "tests/test_new.py"]] * 2)
        events = [event for event in budget.records(fixture.work / ".loop/events.jsonl")
                  if event["kind"] == "targeted-timeout"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["files"], ["tests/test_new.py"])
        self.assertEqual(events[0]["seconds"], 600)
        prompt = next(call["prompt"] for call in self.claude_calls() if call["role"] == "reviewer")
        log = (fixture.work / ".loop/loop.out").read_text()
        warning = next(line.split(": ", 1)[1] for line in log.splitlines()
                       if "Test files command timed out" in line)
        self.assertIn(warning, prompt)
        self.assertNotIn("Latest test result: passed on this commit.", prompt)


if __name__ == "__main__":
    unittest.main()
