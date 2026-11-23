"""Timing checks tolerate scheduling delays while still detecting missing results."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from kit.tests import test_pass_background as background
from kit.tests import test_pause_limits as pause


def number(node):
    """Read numeric bounds without evaluating test code."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp):
        left, right = number(node.left), number(node.right)
        if left is not None and right is not None:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right:
                return left / right
    return None


class TimingSafetyTest(unittest.TestCase):
    def test_background_waits_follow_completion_with_a_sixty_second_safety_net(self):
        fixture = background.BackgroundPassFixture("runTest")
        fixture.work, fixture.st = "unused", {}
        for delay in (12, 59):
            for operation in ("worker", "reap"):
                with self.subTest(delay=delay, operation=operation):
                    clock = SimpleNamespace(now=0)

                    def sleep(seconds):
                        clock.now += max(seconds, 0.25)

                    fake_time = SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep)
                    calls = []

                    def finished():
                        calls.append(clock.now)
                        return clock.now >= delay

                    with mock.patch.object(background, "time", fake_time), \
                            mock.patch.object(background.loop, "reap") as reap:
                        if operation == "worker":
                            fixture.wait_for(finished, "worker wait expired before completion")
                        else:
                            fixture.collect(finished)
                            self.assertEqual(reap.call_count, len(calls))
                    self.assertGreater(len(calls), 1, "completion must be checked repeatedly")
                    self.assertEqual(clock.now, delay, "the wait must end when its condition holds")

        source = Path(background.__file__).read_text()
        tree = ast.parse(source)
        methods = {
            "test_reap_publishes_the_report_without_another_drain",
            "test_an_old_pass_keeps_its_commit_and_the_next_drain_covers_the_new_head",
        }
        for method in ast.walk(tree):
            if not isinstance(method, ast.FunctionDef) or method.name not in methods:
                continue
            for call in ast.walk(method):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                if call.func.attr != "wait":
                    continue
                bounds = list(call.args[:1]) + [
                    kw.value for kw in call.keywords if kw.arg == "timeout"]
                for bound in bounds:
                    value = number(bound)
                    if value is not None:
                        with self.subTest(method=method.name, line=call.lineno):
                            self.assertGreaterEqual(value, 60, "completion waits need a generous safety net")

    def test_session_limit_accepts_delays_but_rejects_early_or_missing_timeouts(self):
        case = pause.PauseLimitsTest("test_session_limit_still_fires_without_a_pause")
        for seconds in (2, 19.5):
            with self.subTest(seconds=seconds), mock.patch.object(case, "plain_run", return_value={
                    "error": "session timed out", "seconds": seconds}):
                case.test_session_limit_still_fires_without_a_pause()
        for seconds, error in ((0.5, "session timed out"), (1.5, "session timed out"), (30, "")):
            with self.subTest(seconds=seconds, error=error), mock.patch.object(
                    case, "plain_run", return_value={"error": error, "seconds": seconds}):
                with self.assertRaises(AssertionError, msg="the session limit must fire after its two seconds"):
                    case.test_session_limit_still_fires_without_a_pause()

    def test_elapsed_time_assertions_have_no_upper_bound_below_ten_seconds(self):
        violations = []

        def check(path, node, elapsed, bound):
            value = number(bound)
            text = ast.unparse(elapsed).lower()
            timing = any(word in text for word in (
                "time(", "monotonic(", "elapsed", "seconds", "duration", "self.now"))
            if timing and value is not None and value < 10:
                violations.append("%s:%s: %s" % (path.name, node.lineno, ast.unparse(node)))

        for path in sorted(Path(__file__).parent.glob("test_*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("assertLess", "assertLessEqual") and len(node.args) >= 2:
                        check(path, node, node.args[0], node.args[1])
                    elif node.func.attr in ("assertGreater", "assertGreaterEqual") and len(node.args) >= 2:
                        check(path, node, node.args[1], node.args[0])
                elif isinstance(node, ast.Assert) or (
                        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "assertTrue" and node.args):
                    expression = node.test if isinstance(node, ast.Assert) else node.args[0]
                    if isinstance(expression, ast.Compare):
                        for left, op, right in zip(
                                [expression.left] + expression.comparators,
                                expression.ops, expression.comparators):
                            if isinstance(op, (ast.Lt, ast.LtE)):
                                check(path, node, left, right)
                            elif isinstance(op, (ast.Gt, ast.GtE)):
                                check(path, node, right, left)
        self.assertEqual(violations, [], "tight elapsed-time bounds:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
