import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import common
import loop
import pass_

HERE = Path(__file__).resolve().parent


class EventsTest(unittest.TestCase):
    def read(self, project):
        return [json.loads(l) for l in Path(project, ".loop/events.jsonl").read_text().splitlines()]

    def test_say_timestamps_every_line(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            loop.say("first\nsecond")
        self.assertEqual(len(out.getvalue().splitlines()), 2)
        for line in out.getvalue().splitlines():
            self.assertRegex(line, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d (first|second)$")

    def test_guard_records_rules_even_when_logging_fails(self):
        with tempfile.TemporaryDirectory() as project:
            env = dict(os.environ, LOOP_ROLE="builder", LOOP_PROJECT=project, LOOP_ISSUE="8")
            env.pop("LOOP_AGENT", None)
            def call():
                return subprocess.run([sys.executable, str(HERE.parent / "hooks/guard.py")],
                                      input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git merge other"}}),
                                      capture_output=True, text=True, env=env)
            first = call()
            self.assertEqual(first.returncode, 2)
            event = self.read(project)[0]
            self.assertEqual((event["kind"], event["rule"], event["role"], event["issue"]),
                             ("rule", "role-git", "builder", 8))
            # A file where the directory belongs fails even under a privileged test runner.
            env["LOOP_PROJECT"] = str(Path(project, "blocked"))
            Path(env["LOOP_PROJECT"]).mkdir()
            Path(env["LOOP_PROJECT"], ".loop").write_text("unwritable")
            second = call()
            self.assertEqual((second.returncode, second.stderr), (first.returncode, first.stderr))

    def test_every_refusal_path_names_a_rule(self):
        for path, name in ((HERE.parent / "hooks/guard.py", "Refuse"),
                           (HERE.parent / "scripts/merge.py", "_refuse")):
            calls = [n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == name]
            self.assertTrue(calls)
            for call in calls:
                self.assertGreaterEqual(len(call.args), 2, "%s:%s" % (path.name, call.lineno))
                rules = [call.args[0]]
                while rules:
                    rule = rules.pop()
                    if isinstance(rule, ast.IfExp):
                        rules += [rule.body, rule.orelse]
                    else:
                        self.assertIsInstance(rule, ast.Constant)
                        self.assertRegex(rule.value, r"^[a-z]+(?:-[a-z]+)*$")

    def test_crash_attempts_and_park_are_recorded(self):
        with tempfile.TemporaryDirectory() as project, mock.patch.object(loop.flow, "build", side_effect=RuntimeError("gone")), \
                mock.patch.object(loop, "gh"), mock.patch.object(common, "gh"):
            loop.build_attempts(project, 8, [], previous=1)
            events = self.read(project)
            self.assertEqual([e["attempt"] for e in events if e["kind"] == "crashed"], [2, 3])
            self.assertEqual(events[-1]["kind"], "parked")
            self.assertIn("gone", events[-1]["reason"])

    def test_dead_worker_continues_after_its_recorded_attempt(self):
        with tempfile.TemporaryDirectory() as project, mock.patch.object(loop, "gh"), \
                mock.patch.object(loop.flow, "build", return_value=loop.flow.Result("merged", "done")):
            path = Path(common.build_file(project, 8, "attempt"))
            path.parent.mkdir(parents=True)
            path.write_text("2")
            st = loop.new_state()
            st["building"][8] = ("10:00", mock.Mock(returncode=3, **{"poll.return_value": 3}))
            loop.reap(project, st)
            self.assertEqual(self.read(project)[0]["attempt"], 2)
            st["issues"] = [{"number": 8, "labels": {"ready"}}]
            with mock.patch.object(loop, "pick", side_effect=[8, None]), \
                    mock.patch.object(loop, "claim"), mock.patch.object(loop.subprocess, "Popen") as popen:
                popen.return_value.pid = 123
                loop.start_builds(project, {"Parallel": 2}, st)
            command = popen.call_args[0][0]
            self.assertEqual(command[-1], "2")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                loop.build_attempts(project, 8, [], previous=int(command[-1]))
            self.assertIn("building #8, attempt 3", out.getvalue())

    def test_drain_records_pass_and_failure(self):
        with tempfile.TemporaryDirectory() as project:
            for failure in (None, "test failed"):
                with mock.patch.object(loop, "_drain", return_value=failure):
                    loop.drain(project, {}, {})
            self.assertEqual([e["outcome"] for e in self.read(project) if e["phase"] == "end"], ["pass", "fail"])

    def test_pass_records_counts_and_duration(self):
        with tempfile.TemporaryDirectory() as project, mock.patch.object(common, "scratch_tree"):
            def run(project, settings, since, tree, report):
                report.update(sessions=3, confirmed=["one"], rejected=["two"],
                              issues=["a new issue", "old finding(s) added"])
            with mock.patch.object(pass_, "_pass", side_effect=run):
                pass_.run_pass(project, {"Loop branch": "loop/main"}, "base")
            start, end = self.read(project)
            self.assertEqual((start["kind"], start["phase"], end["phase"]), ("pass", "start", "end"))
            self.assertEqual((end["sessions"], end["confirmed"], end["rejected"], end["issues"]), (3, 1, 1, 1))
            self.assertIsInstance(end["seconds"], int)

    def test_timing_records_crashes_and_elapsed_seconds(self):
        with tempfile.TemporaryDirectory() as project, mock.patch.object(common.time, "monotonic", side_effect=[10, 15.9]):
            with self.assertRaises(RuntimeError):
                with common.timed("step", project, issue=8, step="builder", agent="codex", model="test"):
                    raise RuntimeError("gone")
            start, end = self.read(project)
            self.assertEqual((start["phase"], end["phase"], end["outcome"], end["seconds"]),
                             ("start", "end", "crashed", 5))


if __name__ == "__main__":
    unittest.main()
